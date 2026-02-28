"""Map Matching 엔드포인트"""

import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Header

from ..map_matching.models import MapMatchingRequest, MapMatchingSummary, MapMatchingResponse, StandardResponse
from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/map-matching")


@router.post("/match", response_model=StandardResponse)
async def map_matching_match(
    request_body: MapMatchingRequest,
    x_api_key: Optional[str] = Header(None)
) -> StandardResponse:
    """GPS 궤적 맵 매칭"""
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    start_time = time.time()

    try:
        trajectory = request_body.trajectory
        logger.info(f"[Map Matching] 요청: {len(trajectory)}개 포인트")

        for i in range(1, len(trajectory)):
            if trajectory[i][2] < trajectory[i - 1][2]:
                raise HTTPException(
                    status_code=400,
                    detail=f"포인트 {i}: 시간 순서가 올바르지 않습니다"
                )

        matching_result = await c.map_matcher.match_trajectory_selective(
            trajectory,
            accuracy_threshold=20.0,
            enable_debug=request_body.enable_debug
        )

        filtered_trajectory = []
        for point in matching_result.get('matched_trace', []):
            if len(point) >= 6:
                filtered_trajectory.append([point[0], point[1], point[2], point[5]])
            elif len(point) >= 4:
                filtered_trajectory.append([point[0], point[1], point[2], point[3] if len(point) > 5 else 1.0])

        summary = matching_result.get('summary', {})
        matched_points = summary.get('corrected_points', summary.get('matched_points', 0))

        response_data = MapMatchingResponse(
            matched_trace=filtered_trajectory,
            summary=MapMatchingSummary(
                total_points=len(filtered_trajectory),
                matched_points=matched_points
            ),
            debug_info=matching_result.get('debug_info')
        )

        elapsed = time.time() - start_time
        logger.info(
            f"[Map Matching] 완료: {matched_points}/{len(filtered_trajectory)}개 매칭 ({elapsed:.2f}s)"
        )

        return StandardResponse(
            status="success",
            message="맵 매칭이 성공적으로 완료되었습니다",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Map Matching] 오류: {e}")
        raise HTTPException(status_code=500, detail=f"맵 매칭 처리 중 오류: {str(e)}")


@router.get("/health")
async def map_matching_health() -> Dict[str, Any]:
    """Map Matching 서비스 상태 확인"""
    c = get_components()
    try:
        test_route = await c.map_matcher._get_connecting_route(
            [126.9780, 37.5665], [126.9864, 37.5659]
        )

        if test_route:
            return {
                "status": "healthy",
                "message": "Map Matching 서비스가 정상 작동 중입니다",
                "osrm_url": config.OSRM_URL,
                "osrm_status": "connected",
                "timestamp": int(time.time())
            }
        else:
            return {
                "status": "unhealthy",
                "message": "OSRM 서비스에서 응답이 없습니다",
                "osrm_url": config.OSRM_URL,
                "osrm_status": "no_response",
                "timestamp": int(time.time())
            }

    except Exception as e:
        logger.error(f"[Map Matching Health] 오류: {e}")
        return {
            "status": "error",
            "message": f"상태 확인 중 오류: {str(e)}",
            "osrm_url": config.OSRM_URL,
            "timestamp": int(time.time())
        }


@router.post("/validate")
async def map_matching_validate(
    request_body: MapMatchingRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """GPS 궤적 유효성 검증 및 품질 분석"""
    verify_api_key(x_api_key)

    c = get_components()

    try:
        trajectory = request_body.trajectory
        logger.info(f"[Trajectory Validation] 검증: {len(trajectory)}개 포인트")

        result = {
            "is_valid": True,
            "total_points": len(trajectory),
            "issues": [],
            "recommendations": [],
            "quality_score": 1.0,
            "metrics": {
                "temporal_consistency": 1.0,
                "spatial_consistency": 1.0,
                "accuracy_distribution": 1.0,
                "speed_consistency": 1.0,
            }
        }

        for i, point in enumerate(trajectory):
            lon, lat, ts, acc, spd = point
            if not -180 <= lon <= 180:
                result["issues"].append({
                    "type": "coordinate_error", "point_index": i,
                    "message": f"포인트 {i}: 경도 범위 초과 ({lon})"
                })
                result["is_valid"] = False
            if not -90 <= lat <= 90:
                result["issues"].append({
                    "type": "coordinate_error", "point_index": i,
                    "message": f"포인트 {i}: 위도 범위 초과 ({lat})"
                })
                result["is_valid"] = False

        outliers = c.map_matcher.outlier_detector.detect_outliers(trajectory)
        for outlier in outliers:
            result["issues"].append({
                "type": "gps_outlier",
                "point_index": outlier["index"],
                "outlier_type": outlier["outlier_type"],
                "severity": outlier["severity"],
                "message": f"포인트 {outlier['index']}: GPS 이상값 ({outlier['outlier_type']}, 심각도: {outlier['severity']:.2f})"
            })

        time_intervals = [trajectory[i][2] - trajectory[i-1][2] for i in range(1, len(trajectory))]
        if time_intervals:
            avg_interval = sum(time_intervals) / len(time_intervals)
            if avg_interval > 0:
                variance = sum((t - avg_interval) ** 2 for t in time_intervals) / len(time_intervals)
                result["metrics"]["temporal_consistency"] = max(0, 1.0 - variance / (avg_interval ** 2))

        accuracies = [p[3] for p in trajectory]
        avg_accuracy = sum(accuracies) / len(accuracies)
        result["metrics"]["accuracy_distribution"] = max(0, 1.0 - avg_accuracy / 100.0)

        speeds = [p[4] for p in trajectory]
        if len(speeds) > 1:
            speed_changes = [abs(speeds[i] - speeds[i-1]) for i in range(1, len(speeds))]
            avg_change = sum(speed_changes) / len(speed_changes)
            result["metrics"]["speed_consistency"] = max(0, 1.0 - avg_change / 50.0)

        result["quality_score"] = round(
            sum(result["metrics"].values()) / len(result["metrics"]), 3
        )

        if result["quality_score"] < 0.8:
            result["recommendations"].append("궤적 품질이 낮습니다. GPS 정확도가 높은 환경에서 데이터를 수집해보세요.")
        outlier_count = sum(1 for i in result["issues"] if i["type"] == "gps_outlier")
        if outlier_count > 0:
            result["recommendations"].append(f"{outlier_count}개의 GPS 이상값이 감지되었습니다. 맵 매칭 시 자동으로 보정됩니다.")
        if result["metrics"]["accuracy_distribution"] < 0.7:
            result["recommendations"].append("GPS 정확도가 낮습니다. 실내나 터널 구간을 피해보세요.")
        if result["metrics"]["temporal_consistency"] < 0.7:
            result["recommendations"].append("GPS 포인트 간 시간 간격이 불규칙합니다.")

        return result

    except Exception as e:
        logger.error(f"[Trajectory Validation] 오류: {e}")
        raise HTTPException(status_code=500, detail=f"궤적 검증 오류: {str(e)}")

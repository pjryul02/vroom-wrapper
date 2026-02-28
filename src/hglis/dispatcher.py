"""
HGLIS 배차 오케스트레이터

Phase 2 파이프라인:
  1. 검증 (validator)
  2. 스킬 인코딩 (skill_encoder)
  3. VROOM JSON 조립 (vroom_assembler)
  4. VROOM 실행 (기존 controller 재사용)
  5. 결과 매핑 (VROOM → HGLIS 응답)
"""

import time
import logging
from typing import Dict, Any, List, Optional

from .models import (
    HglisDispatchRequest, HglisDispatchResponse,
    DispatchResult, DriverSummary, UnassignedJob,
)
from .validator import validate_request, ValidationResult
from .skill_encoder import encode_skills, SkillEncodeResult
from .vroom_assembler import assemble_vroom_input

logger = logging.getLogger(__name__)


class HglisDispatcher:
    """HGLIS 배차 파이프라인 오케스트레이터"""

    def __init__(self, controller):
        """
        Args:
            controller: OptimizationController (기존 래퍼 컴포넌트)
        """
        self.controller = controller

    async def dispatch(self, request: HglisDispatchRequest) -> HglisDispatchResponse:
        """
        배차 실행 전체 파이프라인

        Returns: HglisDispatchResponse
        """
        start_time = time.time()

        # Step 1: 비즈니스 검증
        validation = validate_request(request)
        if not validation.is_valid:
            return self._error_response(
                f"검증 실패: {len(validation.errors)}건 에러",
                validation,
                start_time,
            )

        # Step 2: 스킬 인코딩 (C4, C7, C8, 소파)
        skill_result = encode_skills(request.jobs, request.vehicles)

        # Step 3: VROOM JSON 조립
        vroom_input = assemble_vroom_input(request, skill_result)

        # Step 4: VROOM 실행
        vroom_result = await self._execute_vroom(vroom_input)

        # Step 5: 결과 매핑
        response = self._build_response(
            request, vroom_result, skill_result, validation, start_time
        )

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(
            f"HGLIS 배차 완료: "
            f"오더 {len(request.jobs)}건, 기사 {len(request.vehicles)}명, "
            f"배정 {len(response.results)}건, 미배정 {len(response.unassigned)}건, "
            f"{elapsed}ms"
        )

        return response

    async def _execute_vroom(self, vroom_input: Dict[str, Any]) -> Dict[str, Any]:
        """VROOM 엔진 호출"""
        if self.controller.executor:
            result = await self.controller.executor.execute(
                vroom_input,
                geometry=vroom_input.get("options", {}).get("g", True),
            )
        else:
            # HTTP 폴백
            import httpx
            from .. import config
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(config.VROOM_URL, json=vroom_input)
                resp.raise_for_status()
                result = resp.json()

        return result

    def _build_response(
        self,
        request: HglisDispatchRequest,
        vroom_result: Dict[str, Any],
        skill_result: SkillEncodeResult,
        validation: ValidationResult,
        start_time: float,
    ) -> HglisDispatchResponse:
        """VROOM 결과 → HGLIS 응답 변환"""

        # 오더 ID → HglisJob 매핑
        job_map = {j.id: j for j in request.jobs}
        vehicle_map = {v.id: v for v in request.vehicles}

        # 배차 결과 추출
        results: List[DispatchResult] = []
        driver_stats: Dict[int, Dict[str, Any]] = {}  # vehicle_id → 통계

        for route in vroom_result.get("routes", []):
            vid = route.get("vehicle")
            vehicle = vehicle_map.get(vid)
            if not vehicle:
                continue

            # 기사별 통계 초기화
            if vid not in driver_stats:
                driver_stats[vid] = {
                    "assigned_count": 0,
                    "total_fee": 0,
                    "distance_km": route.get("distance", 0) / 1000,
                }
            else:
                driver_stats[vid]["distance_km"] = route.get("distance", 0) / 1000

            seq = 0
            for step in route.get("steps", []):
                if step.get("type") != "job":
                    continue

                job_id = step.get("id")
                job = job_map.get(job_id)
                if not job:
                    continue

                seq += 1
                total_fee = sum(p.fee * p.quantity for p in job.products)

                results.append(DispatchResult(
                    order_id=job.order_id,
                    dispatch_type="단독",
                    driver_id=vehicle.driver_id,
                    driver_name=vehicle.driver_name,
                    delivery_sequence=seq,
                    scheduled_arrival=self._format_arrival(step.get("arrival")),
                    install_fee=total_fee,
                    geometry=step.get("geometry"),
                ))

                driver_stats[vid]["assigned_count"] += 1
                driver_stats[vid]["total_fee"] += total_fee

        # 미배정 오더
        unassigned: List[UnassignedJob] = []
        for u in vroom_result.get("unassigned", []):
            job_id = u.get("id")
            job = job_map.get(job_id)
            if job:
                unassigned.append(UnassignedJob(
                    order_id=job.order_id,
                    constraint=self._guess_constraint(u, job, skill_result),
                    reason=u.get("description", "VROOM 미배정"),
                ))

        # 기사별 요약
        driver_summary: List[DriverSummary] = []
        for v in request.vehicles:
            stats = driver_stats.get(v.id, {})
            driver_summary.append(DriverSummary(
                driver_id=v.driver_id,
                driver_name=v.driver_name,
                skill_grade=v.skill_grade,
                service_grade=v.service_grade,
                assigned_count=stats.get("assigned_count", 0),
                total_fee=stats.get("total_fee", 0),
                distance_km=round(stats.get("distance_km", 0), 1),
            ))

        # 통계
        elapsed_ms = int((time.time() - start_time) * 1000)
        assigned_count = len(results)
        total_count = len(request.jobs)
        assignment_rate = round(assigned_count / total_count * 100, 1) if total_count > 0 else 0

        status = "success" if assignment_rate >= 95 else "partial" if assigned_count > 0 else "failed"

        return HglisDispatchResponse(
            status=status,
            meta={
                "request_id": request.meta.request_id,
                "date": request.meta.date,
                "execution_time_ms": elapsed_ms,
                "engine": "direct" if self.controller.executor else "http",
                "vroom_code": vroom_result.get("code", -1),
            },
            statistics={
                "total_orders": total_count,
                "assigned_orders": assigned_count,
                "unassigned_orders": len(unassigned),
                "assignment_rate": assignment_rate,
                "total_vehicles": len(request.vehicles),
                "active_vehicles": len(driver_stats),
                "total_distance_km": round(
                    sum(s.get("distance_km", 0) for s in driver_stats.values()), 1
                ),
            },
            results=results,
            driver_summary=driver_summary,
            unassigned=unassigned,
            warnings=validation.warnings,
        )

    def _error_response(
        self, message: str, validation: ValidationResult, start_time: float,
    ) -> HglisDispatchResponse:
        """검증 실패 응답"""
        elapsed_ms = int((time.time() - start_time) * 1000)
        return HglisDispatchResponse(
            status="failed",
            meta={
                "execution_time_ms": elapsed_ms,
                "error": message,
                "validation": validation.to_dict(),
            },
            statistics={},
        )

    def _format_arrival(self, arrival_ts: Optional[int]) -> Optional[str]:
        """Unix timestamp → HH:MM 문자열"""
        if arrival_ts is None:
            return None
        try:
            from datetime import datetime
            dt = datetime.fromtimestamp(arrival_ts)
            return dt.strftime("%H:%M")
        except Exception:
            return None

    def _guess_constraint(
        self,
        unassigned_item: Dict,
        job: Any,
        skill_result: SkillEncodeResult,
    ) -> str:
        """미배정 오더의 추정 제약조건"""
        # VROOM의 description에서 힌트 추출
        desc = str(unassigned_item.get("description", "")).lower()

        if "skill" in desc:
            job_skills = skill_result.job_skills.get(job.id, [])
            if any(1 <= s <= 4 for s in job_skills):
                return "C4_기능도"
            if any(100 <= s <= 199 for s in job_skills):
                return "C7_신제품"
            if any(300 <= s <= 399 for s in job_skills):
                return "C8_미결이력"
            if 500 in job_skills:
                return "소파_권역"
            return "SKILL_미매칭"

        if "time" in desc or "window" in desc:
            return "C3_시간대"

        if "capacity" in desc or "load" in desc:
            return "C5_CBM"

        return "기타"

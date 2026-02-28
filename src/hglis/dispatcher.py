"""
HGLIS 배차 오케스트레이터

파이프라인:
  1. 검증 (validator)
  2. 합배차 전처리 (joint_dispatch) — C1
  3. 스킬 인코딩 (skill_encoder) — C4, C7, C8, 소파
  4. 권역 분할 (region_splitter)
  5. VROOM JSON 조립 + 실행 (권역별 병렬)
  6. 결과 병합 + 후처리 (C2 거리비, C6 월상한)
  7. 응답 매핑
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional

from .models import (
    HglisDispatchRequest, HglisDispatchResponse,
    DispatchResult, DriverSummary, UnassignedJob,
    HglisJob, HglisVehicle,
)
from .validator import validate_request, ValidationResult
from .skill_encoder import encode_skills, SkillEncodeResult
from .vroom_assembler import assemble_vroom_input
from .region_splitter import split_by_region, merge_vroom_results
from .joint_dispatch import (
    process_joint_dispatch, apply_joint_skills,
    build_secondary_vroom_jobs, JointDispatchResult,
)
from .fee_validator import validate_c2
from .monthly_cap import validate_c6

logger = logging.getLogger(__name__)


class HglisDispatcher:
    """HGLIS 배차 파이프라인 오케스트레이터"""

    def __init__(self, controller):
        self.controller = controller

    async def dispatch(self, request: HglisDispatchRequest) -> HglisDispatchResponse:
        """배차 실행 전체 파이프라인"""
        start_time = time.time()
        all_warnings: List[Dict[str, Any]] = []

        # Step 1: 비즈니스 검증
        validation = validate_request(request)
        if not validation.is_valid:
            return self._error_response(
                f"검증 실패: {len(validation.errors)}건 에러",
                validation, start_time,
            )
        all_warnings.extend(validation.warnings)

        # Step 2: 합배차 전처리 (C1)
        joint_result = None
        if request.options.enable_joint_dispatch:
            joint_result = process_joint_dispatch(request.jobs, request.vehicles)
            working_jobs = joint_result.jobs
            working_vehicles = joint_result.vehicles
        else:
            working_jobs = list(request.jobs)
            working_vehicles = list(request.vehicles)

        # Step 3: 스킬 인코딩 (C4, C7, C8, 소파)
        skill_result = encode_skills(working_jobs, working_vehicles)

        # Step 3.5: 합배차 그룹 skill 추가
        if joint_result and joint_result.joint_groups:
            apply_joint_skills(
                skill_result.job_skills, skill_result.vehicle_skills,
                joint_result, working_vehicles,
            )
            skill_result.skill_legend.update(joint_result.skill_legend)

        # Step 4: 권역 분할
        regions = split_by_region(request)

        # Step 5: 권역별 VROOM 실행
        if len(regions) == 1:
            # 단일 권역 — 분할 불필요
            vroom_input = assemble_vroom_input(request, skill_result)

            # 합배차 secondary job 추가
            if joint_result and joint_result.joint_groups:
                secondary_jobs = build_secondary_vroom_jobs(
                    joint_result, skill_result.job_skills, request.meta.date,
                )
                vroom_input["jobs"].extend(secondary_jobs)

            vroom_result = await self._execute_vroom(vroom_input)
        else:
            # 다중 권역 — 병렬 실행
            vroom_result = await self._execute_parallel(
                request, regions, skill_result, joint_result,
            )

        # Step 6: 결과 매핑 + 후처리
        response = self._build_response(
            request, vroom_result, skill_result, joint_result, start_time,
        )

        # Step 6.5: C2 거리비 검증
        c2_warnings = validate_c2(
            response.driver_summary, list(request.vehicles), vroom_result,
        )
        all_warnings.extend(c2_warnings)

        # Step 6.6: C6 월상한 검증
        c6_warnings = validate_c6(
            response.driver_summary, list(request.vehicles),
        )
        all_warnings.extend(c6_warnings)

        response.warnings = all_warnings

        elapsed = int((time.time() - start_time) * 1000)
        response.meta["execution_time_ms"] = elapsed
        response.meta["regions_processed"] = list(regions.keys())

        logger.info(
            f"HGLIS 배차 완료: "
            f"오더 {len(request.jobs)}건, 기사 {len(request.vehicles)}명, "
            f"배정 {len(response.results)}건, 미배정 {len(response.unassigned)}건, "
            f"경고 {len(all_warnings)}건, {elapsed}ms"
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
            import httpx
            from .. import config
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(config.VROOM_URL, json=vroom_input)
                resp.raise_for_status()
                result = resp.json()

        return result

    async def _execute_parallel(
        self,
        request: HglisDispatchRequest,
        regions: Dict,
        skill_result: SkillEncodeResult,
        joint_result: Optional[JointDispatchResult],
    ) -> Dict[str, Any]:
        """권역별 병렬 VROOM 실행 + 결과 병합"""

        async def run_region(region_code: str, jobs: List, vehicles: List):
            # 권역 서브 요청 조립
            from .models import HglisDispatchRequest, DispatchMeta, DispatchOptions
            sub_request = HglisDispatchRequest(
                meta=request.meta,
                jobs=jobs,
                vehicles=vehicles,
                options=request.options,
            )
            vroom_input = assemble_vroom_input(sub_request, skill_result)

            # 합배차 secondary job 추가 (해당 권역의 것만)
            if joint_result and joint_result.joint_groups:
                region_job_ids = {j.id for j in jobs}
                relevant_groups = {
                    gid: g for gid, g in joint_result.joint_groups.items()
                    if g["primary_job_id"] in region_job_ids
                }
                if relevant_groups:
                    from .joint_dispatch import build_secondary_vroom_jobs
                    # 임시 joint_result 생성
                    temp_joint = JointDispatchResult()
                    temp_joint.joint_groups = relevant_groups
                    temp_joint.jobs = jobs
                    secondary_jobs = build_secondary_vroom_jobs(
                        temp_joint, skill_result.job_skills, request.meta.date,
                    )
                    vroom_input["jobs"].extend(secondary_jobs)

            return await self._execute_vroom(vroom_input)

        # 병렬 실행
        tasks = {}
        for region_code, (jobs, vehicles) in regions.items():
            if not vehicles:
                logger.warning(f"권역 {region_code}: 기사 없음, 전체 미배정 처리")
                continue
            tasks[region_code] = asyncio.create_task(
                run_region(region_code, jobs, vehicles)
            )

        region_results = {}
        for region_code, task in tasks.items():
            try:
                region_results[region_code] = await task
            except Exception as e:
                logger.error(f"권역 {region_code} VROOM 실패: {e}")
                region_results[region_code] = {
                    "code": 1, "routes": [], "unassigned": [],
                    "summary": {"cost": 0},
                }

        # 기사 없는 권역의 오더 → 미배정 처리
        for region_code, (jobs, vehicles) in regions.items():
            if not vehicles and region_code not in region_results:
                region_results[region_code] = {
                    "code": 0, "routes": [],
                    "unassigned": [{"id": j.id, "description": f"권역 {region_code} 기사 없음"} for j in jobs],
                    "summary": {"cost": 0, "unassigned": len(jobs)},
                }

        return merge_vroom_results(region_results)

    def _build_response(
        self,
        request: HglisDispatchRequest,
        vroom_result: Dict[str, Any],
        skill_result: SkillEncodeResult,
        joint_result: Optional[JointDispatchResult],
        start_time: float,
    ) -> HglisDispatchResponse:
        """VROOM 결과 → HGLIS 응답 변환"""

        job_map = {j.id: j for j in request.jobs}
        vehicle_map = {v.id: v for v in request.vehicles}

        # 합배차 secondary ID 집합
        secondary_ids = set()
        if joint_result and joint_result.joint_groups:
            secondary_ids = {g["secondary_job_id"] for g in joint_result.joint_groups.values()}

        # 배차 결과 추출
        results: List[DispatchResult] = []
        driver_stats: Dict[int, Dict[str, Any]] = {}

        for route in vroom_result.get("routes", []):
            vid = route.get("vehicle")
            vehicle = vehicle_map.get(vid)
            if not vehicle:
                continue

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

                # secondary job은 건너뛰기 (primary에서 합산)
                if job_id in secondary_ids:
                    continue

                job = job_map.get(job_id)
                if not job:
                    continue

                seq += 1

                # 합배차 여부 판단
                dispatch_type = "단독"
                total_fee = sum(p.fee * p.quantity for p in job.products)

                if joint_result and joint_result.is_joint.get(job_id):
                    dispatch_type = "합배차_주"
                    total_fee = int(total_fee * 0.6)  # 60% (primary)

                results.append(DispatchResult(
                    order_id=job.order_id,
                    dispatch_type=dispatch_type,
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
            if job_id in secondary_ids:
                continue  # secondary 미배정은 무시
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

        joint_count = sum(1 for r in results if r.dispatch_type.startswith("합배차"))
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
                "joint_dispatch_count": joint_count,
                "total_vehicles": len(request.vehicles),
                "active_vehicles": len(driver_stats),
                "total_distance_km": round(
                    sum(s.get("distance_km", 0) for s in driver_stats.values()), 1
                ),
            },
            results=results,
            driver_summary=driver_summary,
            unassigned=unassigned,
            warnings=[],  # 호출자가 채움
        )

    def _error_response(
        self, message: str, validation: ValidationResult, start_time: float,
    ) -> HglisDispatchResponse:
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

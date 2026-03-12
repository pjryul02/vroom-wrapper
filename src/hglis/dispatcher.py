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
from .region_splitter import split_by_region, merge_vroom_results, get_adjacent_vehicles
from .joint_dispatch import (
    process_joint_dispatch, apply_joint_skills,
    build_secondary_vroom_jobs, JointDispatchResult,
)
from .fee_validator import validate_c2
from .monthly_cap import validate_c6
from ..preprocessing.vroom_matrix_preparer import VroomMatrixPreparer
from ..preprocessing.chunked_matrix import OSRMChunkedMatrix
from ..preprocessing.valhalla_eta import ValhallaEtaUpdater
from ..postprocessing import ResultAnalyzer, StatisticsGenerator
from ..postprocessing.constraint_checker import ConstraintChecker
from .. import config

logger = logging.getLogger(__name__)


class HglisDispatcher:
    """HGLIS 배차 파이프라인 오케스트레이터"""

    def __init__(
        self,
        controller,
        enable_matrix_prep: Optional[bool] = None,
        valhalla_eta_updater: Optional[ValhallaEtaUpdater] = None,
    ):
        self.controller = controller
        self.matrix_preparer: Optional[VroomMatrixPreparer] = None
        _enable = enable_matrix_prep if enable_matrix_prep is not None else config.MATRIX_PREP_ENABLED
        if _enable:
            osrm_matrix = OSRMChunkedMatrix(
                osrm_url=config.OSRM_URL,
                chunk_size=config.OSRM_CHUNK_SIZE,
                max_workers=config.OSRM_MAX_WORKERS,
            )
            self.matrix_preparer = VroomMatrixPreparer(osrm_matrix=osrm_matrix)
        self.valhalla_eta_updater: Optional[ValhallaEtaUpdater] = valhalla_eta_updater

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
        debug_vroom_input = None
        if len(regions) == 1:
            # 단일 권역 — 분할 불필요
            vroom_input = assemble_vroom_input(request, skill_result)

            # 합배차 secondary job 추가
            if joint_result and joint_result.joint_groups:
                secondary_jobs = build_secondary_vroom_jobs(
                    joint_result, skill_result.job_skills, request.meta.date,
                )
                vroom_input["jobs"].extend(secondary_jobs)

            # 중간 VROOM 입력 저장 (디버그용)
            import copy
            debug_vroom_input = copy.deepcopy(vroom_input)

            vroom_result = await self._execute_vroom(vroom_input)
        else:
            # 다중 권역 — 병렬 실행
            vroom_result = await self._execute_parallel(
                request, regions, skill_result, joint_result,
            )

        # Step 5.5: flexible 모드 — 미배정 오더 인접 권역 재시도
        if (request.meta.region_mode == "flexible"
                and vroom_result.get("unassigned")):
            vroom_result, flex_warnings = await self._retry_flexible(
                request, vroom_result, skill_result, joint_result,
            )
            all_warnings.extend(flex_warnings)

        # ── Pass 3: Valhalla ETA 업데이트 ──────────────────────────────────────
        # VROOM이 결정한 경로 순서는 그대로 유지.
        # 각 step의 도착 시간(arrival)만 Valhalla time-dependent routing으로 재계산.
        # 현재: enabled=False (pass-through). TODO: valhalla_eta.py 구현 완료 후 활성화.
        if self.valhalla_eta_updater:
            try:
                vroom_result = await self.valhalla_eta_updater.update(vroom_result)
            except Exception as e:
                logger.warning(f"Pass3 ETA 업데이트 실패 (비치명적 — OSRM ETA 유지): {e}")
        # ─────────────────────────────────────────────────────────────────────

        # Step 6: 결과 매핑 + 후처리
        response = self._build_response(
            request, vroom_result, skill_result, joint_result, start_time,
        )

        # Step 6.1: VROOM routes 포함 (지도 표출용)
        response.routes = vroom_result.get("routes", [])

        # Step 6.2: 분석 (ResultAnalyzer + StatisticsGenerator)
        try:
            analyzer = ResultAnalyzer()
            analysis = analyzer.analyze(
                debug_vroom_input or {}, vroom_result,
            )
            response.analysis = analysis
        except Exception as e:
            logger.warning(f"분석 실패 (비치명적): {e}")

        # Step 6.3: 미배정 정밀 사유 분석 (ConstraintChecker)
        if vroom_result.get("unassigned") and debug_vroom_input:
            try:
                checker = ConstraintChecker(debug_vroom_input)
                reasons_map = checker.analyze_unassigned(vroom_result["unassigned"])
                # 기존 추론 사유에 정밀 분석 추가
                for uj in response.unassigned:
                    job = next((j for j in request.jobs if j.order_id == uj.order_id), None)
                    if job and job.id in reasons_map:
                        uj.reason = "; ".join(reasons_map[job.id])
            except Exception as e:
                logger.warning(f"미배정 정밀 분석 실패 (비치명적): {e}")

        # Step 6.4: 디버그 정보 (중간 VROOM 입출력)
        if debug_vroom_input:
            response.debug = {
                "vroom_input": debug_vroom_input,
                "vroom_output": {
                    "code": vroom_result.get("code"),
                    "summary": vroom_result.get("summary"),
                    "unassigned_count": len(vroom_result.get("unassigned", [])),
                    "routes_count": len(vroom_result.get("routes", [])),
                },
                "skill_legend": skill_result.skill_legend,
            }

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

        response.warnings.extend(all_warnings)

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

    async def _retry_flexible(
        self,
        request: HglisDispatchRequest,
        vroom_result: Dict[str, Any],
        skill_result: SkillEncodeResult,
        joint_result: Optional[JointDispatchResult],
    ) -> tuple:
        """
        flexible 모드: 미배정 오더를 인접 권역 기사에 재시도.

        Returns: (updated_vroom_result, warnings)
        """
        warnings: List[Dict[str, Any]] = []
        job_map = {j.id: j for j in request.jobs}

        # 미배정 오더 추출
        unassigned_ids = [u.get("id") for u in vroom_result.get("unassigned", [])]
        unassigned_jobs = [job_map[jid] for jid in unassigned_ids if jid in job_map]

        if not unassigned_jobs:
            return vroom_result, warnings

        # 이미 배정된 기사 ID
        assigned_vids = {r.get("vehicle") for r in vroom_result.get("routes", [])}

        # 인접 권역 기사 후보 탐색
        flex_groups = get_adjacent_vehicles(
            unassigned_jobs, list(request.vehicles), assigned_vids,
        )

        if not flex_groups:
            return vroom_result, warnings

        # 인접 권역 후보가 있는 미배정 오더만 모아서 VROOM 재실행
        retry_jobs = []
        retry_vehicles = []
        seen_vids = set()
        for region, (jobs, vehicles) in flex_groups.items():
            retry_jobs.extend(jobs)
            for v in vehicles:
                if v.id not in seen_vids:
                    retry_vehicles.append(v)
                    seen_vids.add(v.id)

        if not retry_jobs or not retry_vehicles:
            return vroom_result, warnings

        # 서브 요청 조립
        from .models import HglisDispatchRequest as _Req
        sub_request = _Req(
            meta=request.meta,
            jobs=retry_jobs,
            vehicles=retry_vehicles,
            options=request.options,
        )
        retry_skill = encode_skills(retry_jobs, retry_vehicles)
        retry_vroom = assemble_vroom_input(sub_request, retry_skill)
        retry_result = await self._execute_vroom(retry_vroom)

        # 재시도에서 배정된 건수
        retry_assigned = len([
            s for r in retry_result.get("routes", [])
            for s in r.get("steps", []) if s.get("type") == "job"
        ])

        if retry_assigned == 0:
            return vroom_result, warnings

        # 재시도 결과를 원본에 병합
        # 1) routes 추가
        for route in retry_result.get("routes", []):
            route["_flexible_retry"] = True
            vroom_result["routes"].append(route)

        # 2) unassigned 교체: 원본 미배정에서 재시도 배정된 건 제거
        retry_assigned_ids = set()
        for route in retry_result.get("routes", []):
            for step in route.get("steps", []):
                if step.get("type") == "job":
                    retry_assigned_ids.add(step.get("id"))

        vroom_result["unassigned"] = [
            u for u in vroom_result.get("unassigned", [])
            if u.get("id") not in retry_assigned_ids
        ]
        # 재시도에서도 미배정인 건 추가
        for u in retry_result.get("unassigned", []):
            if u.get("id") not in retry_assigned_ids:
                # 이미 원본 unassigned에 있으므로 추가 불필요
                pass

        logger.info(
            f"flexible 재시도: {len(retry_jobs)}건 시도 → {retry_assigned}건 추가 배정"
        )

        warnings.append({
            "type": "FLEXIBLE_RETRY",
            "message": f"인접 권역 재시도로 {retry_assigned}건 추가 배정",
            "retry_jobs": len(retry_jobs),
            "retry_assigned": retry_assigned,
        })

        return vroom_result, warnings

    async def _execute_vroom(self, vroom_input: Dict[str, Any]) -> Dict[str, Any]:
        """VROOM 엔진 호출 — 매트릭스 사전 계산 + controller.optimize() 경유"""
        # OSRM 매트릭스 사전 계산 (있으면)
        if self.matrix_preparer and "matrices" not in vroom_input:
            try:
                vroom_input = await self.matrix_preparer.prepare(vroom_input)
            except Exception as e:
                logger.warning(f"매트릭스 사전 계산 실패: {e} - VROOM 직접 OSRM 호출로 fallback")

        return await self.controller.optimize(
            vroom_input, enable_auto_retry=True,
        )

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

        # 합배차 secondary ID → primary ID 매핑
        secondary_ids = set()
        secondary_to_primary: Dict[int, int] = {}  # secondary_job_id → primary_job_id
        if joint_result and joint_result.joint_groups:
            for g in joint_result.joint_groups.values():
                sid = g["secondary_job_id"]
                secondary_ids.add(sid)
                secondary_to_primary[sid] = g["primary_job_id"]

        # secondary job이 어떤 기사에 배정됐는지 추적
        secondary_assignment: Dict[int, int] = {}  # secondary_job_id → vehicle_id
        for route in vroom_result.get("routes", []):
            vid = route.get("vehicle")
            for step in route.get("steps", []):
                if step.get("type") == "job" and step.get("id") in secondary_ids:
                    secondary_assignment[step["id"]] = vid

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
                sec_driver_id = None
                sec_driver_name = None

                if joint_result and joint_result.is_joint.get(job_id):
                    dispatch_type = "합배차_주"
                    total_fee = int(total_fee * 0.6)  # 60% (primary)

                    # secondary 기사 정보 추적
                    for sid, pid in secondary_to_primary.items():
                        if pid == job_id and sid in secondary_assignment:
                            sec_vid = secondary_assignment[sid]
                            sec_vehicle = vehicle_map.get(sec_vid)
                            if sec_vehicle:
                                sec_driver_id = sec_vehicle.driver_id
                                sec_driver_name = sec_vehicle.driver_name
                            break

                results.append(DispatchResult(
                    order_id=job.order_id,
                    dispatch_type=dispatch_type,
                    driver_id=vehicle.driver_id,
                    driver_name=vehicle.driver_name,
                    secondary_driver_id=sec_driver_id,
                    secondary_driver_name=sec_driver_name,
                    delivery_sequence=seq,
                    scheduled_arrival=self._format_arrival(step.get("arrival")),
                    install_fee=total_fee,
                    geometry=step.get("geometry"),
                ))

                driver_stats[vid]["assigned_count"] += 1
                driver_stats[vid]["total_fee"] += total_fee

        # 미배정 오더
        unassigned: List[UnassignedJob] = []
        secondary_unassigned_warnings: List[Dict[str, Any]] = []
        for u in vroom_result.get("unassigned", []):
            job_id = u.get("id")
            if job_id in secondary_ids:
                # secondary 미배정 → 경고 생성 (primary 오더 ID 포함)
                primary_id = secondary_to_primary.get(job_id)
                primary_job = job_map.get(primary_id)
                if primary_job:
                    secondary_unassigned_warnings.append({
                        "type": "JOINT_SECONDARY_UNASSIGNED",
                        "message": f"합배차 보조 기사 미배정: 오더 {primary_job.order_id}",
                        "order_id": primary_job.order_id,
                    })
                continue
            job = job_map.get(job_id)
            if job:
                desc = u.get("description", "VROOM 미배정")
                if "기사 없음" in desc:
                    constraint = "기사_부재"
                else:
                    constraint = self._guess_constraint(u, job, skill_result)
                unassigned.append(UnassignedJob(
                    order_id=job.order_id,
                    constraint=constraint,
                    reason=desc,
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
            warnings=secondary_unassigned_warnings,  # + 호출자가 추가
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
            from zoneinfo import ZoneInfo
            dt = datetime.fromtimestamp(arrival_ts, tz=ZoneInfo("Asia/Seoul"))
            return dt.strftime("%H:%M")
        except Exception:
            return None

    def _guess_constraint(
        self,
        unassigned_item: Dict,
        job: Any,
        skill_result: SkillEncodeResult,
    ) -> str:
        """
        미배정 사유 추론.

        VROOM은 미배정 이유를 직접 제공하지 않으므로,
        job에 부여된 skill 종류를 분석하여 가장 유력한 제약을 추론한다.
        우선순위: C8(미결) > C7(신제품) > 소파 > C4(기능도) > C5(CBM) > C3(시간) > 기타
        """
        job_skills = skill_result.job_skills.get(job.id, [])

        # C8 미결이력 스킬이 있으면 → 회피 모델 매칭 실패 가능성 높음
        if any(300 <= s <= 399 for s in job_skills):
            return "C8_미결이력"

        # C7 신제품 스킬이 있으면
        if any(100 <= s <= 199 for s in job_skills):
            return "C7_신제품"

        # 소파 전용 스킬
        if 500 in job_skills:
            return "소파_권역"

        # C4 기능도 — S급(4) 오더인데 기사가 부족할 가능성
        c4_skills = [s for s in job_skills if 1 <= s <= 4]
        if c4_skills and max(c4_skills) >= 3:  # A등급 이상
            return "C4_기능도"

        # C5 CBM — 고용량 오더
        total_cbm = sum(p.cbm * p.quantity for p in job.products)
        if total_cbm > 5.0:
            return "C5_CBM"

        return "기타"

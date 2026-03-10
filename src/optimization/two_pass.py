"""
TwoPassOptimizer - 2단계 최적화

Roouty Engine (Go)의 2-Pass 패턴을 Python으로 구현:
- Pass 1: 초기 배정 (어떤 차량에 어떤 작업) - 높은 스레드
- Pass 2: 경로별 최적화 (방문 순서) - 낮은 스레드, 워커 풀 병렬

참고: roouty-engine/pkg/features/distribute/run.go
  - RunWithBound() → Pass 1
  - RunPlan() / RunPlanWithSingleRoute() → Pass 2
"""

import asyncio
import logging
import copy
from typing import Any, Dict, List, Optional

from .vroom_executor import VROOMExecutor

logger = logging.getLogger(__name__)


class TwoPassOptimizer:
    """
    2단계 최적화 엔진

    Pass 1: 전체 문제를 한 번에 풀어 차량별 작업 배정
    Pass 2: 각 경로를 독립적으로 재최적화 (병렬)
    """

    def __init__(
        self,
        executor: VROOMExecutor,
        max_workers: int = 4,
        initial_threads: int = 16,
        route_threads: int = 4,
        initial_exploration: int = 5,
        route_exploration: int = 5,
    ):
        self.executor = executor
        self.max_workers = max_workers
        self.initial_threads = initial_threads
        self.route_threads = route_threads
        self.initial_exploration = initial_exploration
        self.route_exploration = route_exploration

    async def optimize(
        self,
        vrp_input: Dict[str, Any],
        geometry: bool = False,
    ) -> Dict[str, Any]:
        """
        2-Pass 최적화 실행

        Args:
            vrp_input: VROOM 입력 (vehicles, jobs, matrices 등)
            geometry: 경로 형상 반환 여부

        Returns:
            최적화 결과 (routes, summary, unassigned)
        """
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Pass 1: 초기 배정 (높은 스레드)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info(
            f"[PASS 1] 초기 배정 시작 - threads={self.initial_threads}, "
            f"jobs={len(vrp_input.get('jobs', []))}, "
            f"vehicles={len(vrp_input.get('vehicles', []))}"
        )

        pass1_result = await self.executor.execute(
            vrp_input,
            threads=self.initial_threads,
            exploration=self.initial_exploration,
            geometry=False,  # Pass 1에서는 geometry 불필요
        )

        routes = pass1_result.get("routes", [])
        if not routes:
            logger.warning("[PASS 1] 배정된 경로 없음 - Pass 2 스킵")
            return pass1_result

        # 작업이 1개 이하인 경로는 재최적화 불필요
        routes_to_optimize = [r for r in routes if len(r.get("steps", [])) > 3]

        if not routes_to_optimize:
            logger.info("[PASS 1] 재최적화 필요한 경로 없음 - Pass 2 스킵")
            if geometry:
                return await self.executor.execute(
                    vrp_input,
                    threads=self.initial_threads,
                    exploration=self.initial_exploration,
                    geometry=True,
                )
            return pass1_result

        logger.info(
            f"[PASS 1] 완료 - {len(routes)} 경로, "
            f"{len(routes_to_optimize)} 경로 재최적화 대상"
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Pass 2: 경로별 재최적화 (워커 풀 병렬)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info(
            f"[PASS 2] 경로별 최적화 시작 - "
            f"routes={len(routes_to_optimize)}, "
            f"max_workers={self.max_workers}, "
            f"threads={self.route_threads}"
        )

        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = []

        for i, route in enumerate(routes):
            if route in routes_to_optimize:
                tasks.append(
                    self._optimize_single_route(
                        semaphore, vrp_input, route, i, geometry
                    )
                )
            else:
                # 작업 적은 경로는 Pass 1 결과 그대로 사용
                tasks.append(self._passthrough_route(route))

        route_results = await asyncio.gather(*tasks, return_exceptions=True)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 결과 병합
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        final_result = self._merge_results(pass1_result, route_results)

        logger.info(
            f"[PASS 2] 완료 - cost={final_result.get('summary', {}).get('cost', 0)}"
        )

        return final_result

    async def _optimize_single_route(
        self,
        semaphore: asyncio.Semaphore,
        original_input: Dict[str, Any],
        route: Dict[str, Any],
        route_index: int,
        geometry: bool,
    ) -> Dict[str, Any]:
        """
        단일 경로 재최적화

        Roouty의 RunPlanWithSingleRoute() 패턴:
        1. Pass 1 결과에서 해당 경로의 job ID 추출
        2. 해당 job + vehicle만으로 축소된 입력 생성
        3. VROOM 호출로 방문 순서 재최적화

        Args:
            semaphore: 워커 풀 제한
            original_input: 원본 VROOM 입력
            route: Pass 1에서 나온 경로
            route_index: 경로 인덱스
            geometry: geometry 반환 여부

        Returns:
            재최적화된 경로 결과
        """
        async with semaphore:
            vehicle_id = route.get("vehicle")
            logger.debug(f"[PASS 2] Route {route_index} (vehicle={vehicle_id}) 최적화 시작")

            try:
                single_input = self._build_single_route_input(
                    original_input, route
                )

                if not single_input:
                    return route

                result = await self.executor.execute(
                    single_input,
                    threads=self.route_threads,
                    exploration=self.route_exploration,
                    geometry=geometry,
                )

                optimized_routes = result.get("routes", [])
                if optimized_routes:
                    logger.debug(
                        f"[PASS 2] Route {route_index} 완료 - "
                        f"cost={optimized_routes[0].get('cost', 0)}"
                    )
                    return optimized_routes[0]

                # 최적화 실패 시 Pass 1 결과 사용
                return route

            except Exception as e:
                logger.warning(
                    f"[PASS 2] Route {route_index} 최적화 실패: {e} - Pass 1 결과 사용"
                )
                return route

    async def _passthrough_route(self, route: Dict[str, Any]) -> Dict[str, Any]:
        """작업 적은 경로는 그대로 반환"""
        return route

    def _build_single_route_input(
        self,
        original_input: Dict[str, Any],
        route: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        단일 경로용 VROOM 입력 생성

        Roouty의 RunPlanWithSingleRoute에서:
        1. route.steps에서 job/shipment ID 추출
        2. 원본 입력에서 해당 ID만 필터
        3. 해당 vehicle만 포함
        """
        vehicle_id = route.get("vehicle")
        steps = route.get("steps", [])

        # step에서 job/shipment ID 추출
        job_ids = set()
        shipment_ids = set()

        for step in steps:
            step_type = step.get("type")
            if step_type == "job":
                job_ids.add(step.get("id"))
            elif step_type in ("pickup", "delivery"):
                shipment_ids.add(step.get("id"))

        if not job_ids and not shipment_ids:
            return None

        # vehicle 필터 (deepcopy: _extract_sub_matrix가 인덱스를 재매핑하므로)
        vehicles = [
            copy.deepcopy(v) for v in original_input.get("vehicles", [])
            if v.get("id") == vehicle_id
        ]

        if not vehicles:
            return None

        # jobs 필터
        jobs = [
            copy.deepcopy(j) for j in original_input.get("jobs", [])
            if j.get("id") in job_ids
        ]

        # shipments 필터
        shipments = [
            copy.deepcopy(s) for s in original_input.get("shipments", [])
            if s.get("id") in shipment_ids
        ]

        single_input: Dict[str, Any] = {
            "vehicles": vehicles,
        }

        if jobs:
            single_input["jobs"] = jobs
        if shipments:
            single_input["shipments"] = shipments

        # matrices가 있으면 관련 인덱스만 추출
        if "matrices" in original_input:
            single_input["matrices"] = self._extract_sub_matrix(
                original_input, vehicles, jobs, shipments
            )

        return single_input

    def _extract_sub_matrix(
        self,
        original_input: Dict[str, Any],
        vehicles: List[Dict],
        jobs: List[Dict],
        shipments: List[Dict],
    ) -> Dict[str, Any]:
        """
        전체 매트릭스에서 단일 경로에 필요한 인덱스만 추출.
        인덱스를 0부터 순차적으로 재매핑.

        1. vehicle start_index/end_index + job location_index에서 고유 인덱스 수집
        2. 해당 행/열만 추출해서 서브매트릭스 생성
        3. vehicles/jobs의 *_index를 새 인덱스로 업데이트
        """
        matrices = original_input.get("matrices", {})
        if not matrices:
            return {}

        # 1. 필요한 원본 인덱스 수집 (순서 유지)
        needed_indices = []
        seen = set()

        def _add_index(idx):
            if idx is not None and idx not in seen:
                needed_indices.append(idx)
                seen.add(idx)

        for v in vehicles:
            _add_index(v.get("start_index"))
            _add_index(v.get("end_index"))
        for j in jobs:
            _add_index(j.get("location_index"))
        for s in shipments:
            if "pickup" in s:
                _add_index(s["pickup"].get("location_index"))
            if "delivery" in s:
                _add_index(s["delivery"].get("location_index"))

        if not needed_indices:
            return {}

        # 2. 원본 인덱스 → 새 인덱스 매핑
        old_to_new = {old: new for new, old in enumerate(needed_indices)}

        # 3. 서브매트릭스 추출
        new_matrices = {}
        for profile, profile_data in matrices.items():
            new_profile = {}
            for key in ("durations", "distances"):
                full = profile_data.get(key)
                if full:
                    sub = []
                    for src_idx in needed_indices:
                        row = [full[src_idx][dst_idx] for dst_idx in needed_indices]
                        sub.append(row)
                    new_profile[key] = sub
            new_matrices[profile] = new_profile

        # 4. vehicles/jobs의 *_index를 새 인덱스로 재매핑
        for v in vehicles:
            if "start_index" in v:
                v["start_index"] = old_to_new[v["start_index"]]
            if "end_index" in v:
                v["end_index"] = old_to_new[v["end_index"]]
        for j in jobs:
            if "location_index" in j:
                j["location_index"] = old_to_new[j["location_index"]]
        for s in shipments:
            if "pickup" in s and "location_index" in s.get("pickup", {}):
                s["pickup"]["location_index"] = old_to_new[s["pickup"]["location_index"]]
            if "delivery" in s and "location_index" in s.get("delivery", {}):
                s["delivery"]["location_index"] = old_to_new[s["delivery"]["location_index"]]

        return new_matrices

    def _merge_results(
        self,
        pass1_result: Dict[str, Any],
        route_results: List[Any],
    ) -> Dict[str, Any]:
        """
        Pass 2 결과를 하나의 응답으로 병합

        Roouty의 appendSingleResponse() 패턴.
        """
        # delivery/pickup 차원을 결과에서 동적으로 파악 (HGLIS: [cbm,0,0] 3차원)
        dim = 1
        for result in route_results:
            if isinstance(result, dict):
                for key in ("delivery", "pickup"):
                    d = result.get(key, [])
                    if len(d) > dim:
                        dim = len(d)

        merged = {
            "code": 0,
            "routes": [],
            "unassigned": pass1_result.get("unassigned", []),
            "summary": {
                "cost": 0,
                "unassigned": pass1_result.get("summary", {}).get("unassigned", 0),
                "delivery": [0] * dim,
                "pickup": [0] * dim,
                "service": 0,
                "duration": 0,
                "waiting_time": 0,
                "priority": 0,
                "distance": 0,
            },
        }

        for result in route_results:
            if isinstance(result, Exception):
                logger.warning(f"경로 최적화 실패: {result}")
                continue

            if isinstance(result, dict):
                merged["routes"].append(result)
                self._add_route_to_summary(merged["summary"], result)

        return merged

    def _add_route_to_summary(
        self,
        summary: Dict[str, Any],
        route: Dict[str, Any],
    ):
        """경로 지표를 summary에 누적"""
        summary["cost"] += route.get("cost", 0)
        summary["service"] += route.get("service", 0)
        summary["duration"] += route.get("duration", 0)
        summary["waiting_time"] += route.get("waiting_time", 0)
        summary["priority"] += route.get("priority", 0)
        summary["distance"] += route.get("distance", 0)

        # 다차원 delivery/pickup 합산
        route_delivery = route.get("delivery", [0])
        route_pickup = route.get("pickup", [0])

        for i, val in enumerate(route_delivery):
            if i < len(summary["delivery"]):
                summary["delivery"][i] += val
            else:
                summary["delivery"].append(val)

        for i, val in enumerate(route_pickup):
            if i < len(summary["pickup"]):
                summary["pickup"][i] += val
            else:
                summary["pickup"].append(val)

"""
ValhallaEtaUpdater — Pass 3 (ETA 업데이트)

VROOM 2-Pass 최적화 결과에서 경로 순서는 그대로 유지하고,
각 step의 도착 시간(arrival)을 Valhalla time-dependent routing으로 재계산한다.

역할:
  - Pass 1+2 (VROOM+OSRM): 배정 결정 + 경로 순서 결정
  - Pass 3 (Valhalla): 시간대별 교통 반영 ETA 재계산

Valhalla /route API 사용:
  - POST /route
  - costing: "auto" (소형화물차 기본값)
  - date_time.type 1 = "depart_at" (출발 시각 기준)
  - locations: VROOM step 순서 그대로 (순서 변경 없음)

현재 상태: 틀만 잡힌 상태 (pass-through)
TODO: Valhalla /route API 호출 구현
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ValhallaEtaUpdater:
    """
    VROOM 결과의 ETA를 Valhalla time-dependent routing으로 재계산한다.

    사용 흐름:
        vroom_result = await two_pass_optimizer.optimize(...)   # Pass 1+2
        vroom_result = await eta_updater.update(vroom_result)   # Pass 3

    업데이트 대상:
        routes[].steps[].arrival  (Unix timestamp, 초 단위)
        routes[].steps[].duration (누적 주행 시간)
        routes[].duration         (경로 총 주행 시간)

    NOTE:
        - 경로 순서(steps 배열 순서)는 절대 변경하지 않음
        - service_time, waiting_time은 그대로 유지
        - geometry는 OSRM 기반 그대로 (Valhalla geometry로 교체 옵션은 미구현)
    """

    def __init__(
        self,
        valhalla_url: str = "http://localhost:8002",
        costing: str = "auto",           # 소형화물차 기본값 ("auto" = 일반 승용/화물차)
        timeout: int = 30,
        enabled: bool = True,
    ):
        self.valhalla_url = valhalla_url.rstrip("/")
        self.costing = costing
        self.timeout = timeout
        self.enabled = enabled

    async def update(self, vroom_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        VROOM 결과에서 각 route의 ETA를 Valhalla로 재계산.

        Args:
            vroom_result: VROOM 최적화 결과 (routes, summary, unassigned 포함)

        Returns:
            ETA가 업데이트된 vroom_result (실패 시 원본 반환, 비치명적)
        """
        if not self.enabled:
            return vroom_result

        routes = vroom_result.get("routes", [])
        if not routes:
            return vroom_result

        updated_routes = []
        for route in routes:
            try:
                updated_route = await self._update_route_eta(route)
                updated_routes.append(updated_route)
            except Exception as e:
                logger.warning(
                    f"ETA 업데이트 실패 (vehicle {route.get('vehicle')}, "
                    f"비치명적 — OSRM 기반 유지): {e}"
                )
                updated_routes.append(route)

        vroom_result = dict(vroom_result)
        vroom_result["routes"] = updated_routes
        vroom_result["_eta_engine"] = "valhalla"
        return vroom_result

    async def _update_route_eta(self, route: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 route의 ETA 업데이트.

        Valhalla /route 요청 형식:
            {
              "locations": [
                {"lon": 126.978, "lat": 37.566, "type": "break"},
                ...
              ],
              "costing": "auto",
              "date_time": {"type": 1, "value": "2026-03-12T08:00"}
            }

        Valhalla /route 응답에서 추출:
            trip.legs[i].summary.time  → 각 구간 소요 시간(초)
        """
        steps = route.get("steps", [])
        if not steps:
            return route

        # TODO: Valhalla /route API 호출 구현
        #
        # 1. steps에서 location 좌표 추출 (type: start/job/end)
        # 2. 출발 시각(steps[0].arrival) → ISO 포맷 변환 (Unix → "YYYY-MM-DDTHH:MM")
        # 3. Valhalla /route POST 호출
        # 4. 응답 legs[i].summary.time으로 각 step.arrival 재계산
        # 5. route.duration 업데이트
        #
        # 구현 예정 — 현재는 pass-through (OSRM ETA 그대로 유지)

        logger.debug(
            f"[ETA TODO] vehicle {route.get('vehicle')}: "
            f"steps {len(steps)}개 Valhalla ETA 업데이트 자리 (미구현)"
        )
        return route

    def _build_valhalla_route_request(
        self,
        locations: List[List[float]],
        depart_at_unix: int,
    ) -> Dict[str, Any]:
        """
        Valhalla /route 요청 바디 조립.

        Args:
            locations: [[lon, lat], ...] VROOM 표준 순서
            depart_at_unix: 출발 Unix timestamp (초)

        Returns:
            Valhalla POST /route 요청 바디
        """
        import datetime

        depart_dt = datetime.datetime.fromtimestamp(depart_at_unix)
        depart_iso = depart_dt.strftime("%Y-%m-%dT%H:%M")

        return {
            "locations": [
                {"lon": loc[0], "lat": loc[1], "type": "break"}
                for loc in locations
            ],
            "costing": self.costing,
            "date_time": {
                "type": 1,          # 1 = depart_at
                "value": depart_iso,
            },
            "directions_type": "none",  # 경로 텍스트 불필요, 시간만 필요
        }

    async def _call_valhalla_route(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valhalla POST /route 호출.

        TODO: 실제 구현에서 사용 예정
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.valhalla_url}/route",
                json=request_body,
            )
            resp.raise_for_status()
            return resp.json()

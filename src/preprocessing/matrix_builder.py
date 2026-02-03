"""
Matrix Builder - 하이브리드 매트릭스 생성

거리: OSRM (도로망 기반)
시간: 외부 API (TMap/Kakao/Naver) 실시간 교통 반영
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class TrafficProvider(str, Enum):
    """실시간 교통 정보 제공자"""
    TMAP = "tmap"
    KAKAO = "kakao"
    NAVER = "naver"
    OSRM = "osrm"  # fallback (실시간 아님)


@dataclass
class Location:
    """좌표 정보"""
    lon: float
    lat: float
    id: Optional[int] = None

    def to_tuple(self) -> Tuple[float, float]:
        return (self.lon, self.lat)

    def to_tmap_str(self) -> str:
        """TMap 형식: lon,lat"""
        return f"{self.lon},{self.lat}"

    def to_kakao_str(self) -> str:
        """Kakao 형식: lon,lat"""
        return f"{self.lon},{self.lat}"


@dataclass
class MatrixResult:
    """매트릭스 결과"""
    durations: List[List[int]]  # 초 단위
    distances: List[List[int]]  # 미터 단위
    locations: List[Location]
    provider: str
    cached: bool = False
    build_time_ms: int = 0


class MatrixCache:
    """매트릭스 캐시 (동일 구간 반복 호출 방지)"""

    def __init__(self, ttl_seconds: int = 300):  # 5분 기본
        self.ttl = ttl_seconds
        self._cache: Dict[str, Tuple[int, Any]] = {}

    def _make_key(self, origin: Location, dest: Location) -> str:
        """캐시 키 생성"""
        return f"{origin.lon:.5f},{origin.lat:.5f}-{dest.lon:.5f},{dest.lat:.5f}"

    def get(self, origin: Location, dest: Location) -> Optional[Tuple[int, int]]:
        """캐시에서 조회 (duration, distance)"""
        key = self._make_key(origin, dest)
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, origin: Location, dest: Location, duration: int, distance: int):
        """캐시에 저장"""
        key = self._make_key(origin, dest)
        self._cache[key] = (time.time(), (duration, distance))

    def get_stats(self) -> Dict[str, int]:
        """캐시 통계"""
        valid_count = sum(1 for ts, _ in self._cache.values() if time.time() - ts < self.ttl)
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "ttl_seconds": self.ttl
        }


class BaseTrafficProvider(ABC):
    """교통 정보 제공자 기본 클래스"""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout
        self.cache = MatrixCache()

    @abstractmethod
    async def get_duration(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """
        두 지점 간 소요시간과 거리 반환

        Returns:
            (duration_seconds, distance_meters)
        """
        pass

    async def get_duration_batch(
        self,
        origins: List[Location],
        destinations: List[Location]
    ) -> List[List[Tuple[int, int]]]:
        """
        다대다 매트릭스 계산 (기본: 개별 호출)

        오버라이드하여 배치 API 사용 가능
        """
        results = []
        for origin in origins:
            row = []
            for dest in destinations:
                if origin.lon == dest.lon and origin.lat == dest.lat:
                    row.append((0, 0))
                else:
                    # 캐시 확인
                    cached = self.cache.get(origin, dest)
                    if cached:
                        row.append(cached)
                    else:
                        duration, distance = await self.get_duration(origin, dest)
                        self.cache.set(origin, dest, duration, distance)
                        row.append((duration, distance))
            results.append(row)
        return results


class TMapProvider(BaseTrafficProvider):
    """
    TMap 실시간 교통 정보 제공자

    API 문서: https://openapi.sk.com/products/detail?svcSeq=4&menuSeq=36
    """

    BASE_URL = "https://apis.openapi.sk.com/tmap/routes"

    async def get_duration(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """TMap 경로 API 호출"""

        if not self.api_key:
            raise ValueError("TMap API key required")

        headers = {
            "appKey": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "startX": str(origin.lon),
            "startY": str(origin.lat),
            "endX": str(dest.lon),
            "endY": str(dest.lat),
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "searchOption": "0",  # 추천 경로
            "trafficInfo": "Y"    # 실시간 교통 정보 사용
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                # 결과 파싱
                properties = data.get("features", [{}])[0].get("properties", {})
                duration = properties.get("totalTime", 0)  # 초
                distance = properties.get("totalDistance", 0)  # 미터

                return (int(duration), int(distance))

            except httpx.HTTPError as e:
                logger.error(f"TMap API error: {e}")
                raise
            except (KeyError, IndexError) as e:
                logger.error(f"TMap response parsing error: {e}")
                raise ValueError(f"Invalid TMap response: {e}")


class KakaoProvider(BaseTrafficProvider):
    """
    Kakao 실시간 교통 정보 제공자

    API 문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide
    """

    BASE_URL = "https://apis-navi.kakaomobility.com/v1/directions"

    async def get_duration(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """Kakao 길찾기 API 호출"""

        if not self.api_key:
            raise ValueError("Kakao API key required")

        headers = {
            "Authorization": f"KakaoAK {self.api_key}",
            "Content-Type": "application/json"
        }

        params = {
            "origin": f"{origin.lon},{origin.lat}",
            "destination": f"{dest.lon},{dest.lat}",
            "priority": "RECOMMEND",  # 추천 경로
            "car_fuel": "GASOLINE",
            "car_hipass": "false",
            "summary": "true"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    self.BASE_URL,
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                # 결과 파싱
                routes = data.get("routes", [])
                if not routes:
                    raise ValueError("No route found")

                summary = routes[0].get("summary", {})
                duration = summary.get("duration", 0)  # 초
                distance = summary.get("distance", 0)  # 미터

                return (int(duration), int(distance))

            except httpx.HTTPError as e:
                logger.error(f"Kakao API error: {e}")
                raise


class NaverProvider(BaseTrafficProvider):
    """
    Naver 실시간 교통 정보 제공자

    API 문서: https://api.ncloud-docs.com/docs/ai-naver-mapsdirections
    """

    BASE_URL = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        super().__init__(timeout=timeout)
        self.client_id = client_id
        self.client_secret = client_secret

    async def get_duration(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """Naver 길찾기 API 호출"""

        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret
        }

        params = {
            "start": f"{origin.lon},{origin.lat}",
            "goal": f"{dest.lon},{dest.lat}",
            "option": "trafast"  # 실시간 빠른 경로
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    self.BASE_URL,
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                # 결과 파싱
                route = data.get("route", {}).get("trafast", [{}])[0]
                summary = route.get("summary", {})
                duration = summary.get("duration", 0) // 1000  # ms → 초
                distance = summary.get("distance", 0)  # 미터

                return (int(duration), int(distance))

            except httpx.HTTPError as e:
                logger.error(f"Naver API error: {e}")
                raise


class OSRMProvider(BaseTrafficProvider):
    """
    OSRM 제공자 (Fallback, 실시간 아님)

    실시간 교통 정보 없이 도로망 기반 시간 계산
    """

    def __init__(self, base_url: str = "http://localhost:5000", timeout: float = 10.0):
        super().__init__(timeout=timeout)
        self.base_url = base_url.rstrip("/")

    async def get_duration(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """OSRM route API 호출"""

        url = f"{self.base_url}/route/v1/driving/{origin.lon},{origin.lat};{dest.lon},{dest.lat}"
        params = {
            "overview": "false",
            "alternatives": "false"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != "Ok":
                    raise ValueError(f"OSRM error: {data.get('message')}")

                route = data.get("routes", [{}])[0]
                duration = route.get("duration", 0)  # 초
                distance = route.get("distance", 0)  # 미터

                return (int(duration), int(distance))

            except httpx.HTTPError as e:
                logger.error(f"OSRM API error: {e}")
                raise

    async def get_table(
        self,
        locations: List[Location]
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """
        OSRM Table API로 전체 매트릭스 한번에 계산

        Returns:
            (durations_matrix, distances_matrix)
        """
        coords = ";".join([f"{loc.lon},{loc.lat}" for loc in locations])
        url = f"{self.base_url}/table/v1/driving/{coords}"
        params = {
            "annotations": "duration,distance"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "Ok":
                raise ValueError(f"OSRM table error: {data.get('message')}")

            durations = data.get("durations", [])
            distances = data.get("distances", [])

            # float → int 변환
            durations = [[int(d) if d else 0 for d in row] for row in durations]
            distances = [[int(d) if d else 0 for d in row] for row in distances]

            return (durations, distances)


class HybridMatrixBuilder:
    """
    하이브리드 매트릭스 빌더

    거리: OSRM (도로망 기반)
    시간: 외부 API (실시간 교통)
    """

    def __init__(
        self,
        traffic_provider: BaseTrafficProvider,
        osrm_url: str = "http://localhost:5000",
        parallel_requests: int = 10,
        use_osrm_distance: bool = True
    ):
        """
        Args:
            traffic_provider: 실시간 교통 정보 제공자
            osrm_url: OSRM 서버 URL (거리 계산용)
            parallel_requests: 병렬 요청 수
            use_osrm_distance: True면 거리는 OSRM, False면 traffic_provider 사용
        """
        self.traffic_provider = traffic_provider
        self.osrm = OSRMProvider(base_url=osrm_url)
        self.parallel_requests = parallel_requests
        self.use_osrm_distance = use_osrm_distance
        self._semaphore = asyncio.Semaphore(parallel_requests)

    def _extract_locations(self, vrp_input: Dict[str, Any]) -> List[Location]:
        """VRP 입력에서 모든 좌표 추출"""
        locations = []
        location_set = set()  # 중복 제거

        # 차량 시작/종료 위치
        for vehicle in vrp_input.get("vehicles", []):
            if "start" in vehicle:
                coord = tuple(vehicle["start"])
                if coord not in location_set:
                    locations.append(Location(lon=coord[0], lat=coord[1], id=f"v{vehicle['id']}_start"))
                    location_set.add(coord)
            if "end" in vehicle:
                coord = tuple(vehicle["end"])
                if coord not in location_set:
                    locations.append(Location(lon=coord[0], lat=coord[1], id=f"v{vehicle['id']}_end"))
                    location_set.add(coord)

        # Job 위치
        for job in vrp_input.get("jobs", []):
            if "location" in job:
                coord = tuple(job["location"])
                if coord not in location_set:
                    locations.append(Location(lon=coord[0], lat=coord[1], id=f"j{job['id']}"))
                    location_set.add(coord)

        # Shipment pickup/delivery 위치
        for shipment in vrp_input.get("shipments", []):
            if "pickup" in shipment and "location" in shipment["pickup"]:
                coord = tuple(shipment["pickup"]["location"])
                if coord not in location_set:
                    locations.append(Location(lon=coord[0], lat=coord[1], id=f"s{shipment['id']}_pickup"))
                    location_set.add(coord)
            if "delivery" in shipment and "location" in shipment["delivery"]:
                coord = tuple(shipment["delivery"]["location"])
                if coord not in location_set:
                    locations.append(Location(lon=coord[0], lat=coord[1], id=f"s{shipment['id']}_delivery"))
                    location_set.add(coord)

        return locations

    async def _get_duration_with_semaphore(
        self,
        origin: Location,
        dest: Location
    ) -> Tuple[int, int]:
        """세마포어로 동시 요청 수 제한"""
        async with self._semaphore:
            return await self.traffic_provider.get_duration(origin, dest)

    async def build(
        self,
        vrp_input: Dict[str, Any],
        include_in_input: bool = True
    ) -> MatrixResult:
        """
        하이브리드 매트릭스 생성

        Args:
            vrp_input: VROOM VRP 입력
            include_in_input: True면 vrp_input에 matrix 필드 추가

        Returns:
            MatrixResult
        """
        start_time = time.time()

        # 1. 모든 좌표 추출
        locations = self._extract_locations(vrp_input)
        n = len(locations)

        if n == 0:
            raise ValueError("No locations found in VRP input")

        if n > 100:
            logger.warning(f"Large matrix: {n}x{n} = {n*n} API calls")

        logger.info(f"Building {n}x{n} matrix ({n*n} cells)")

        # 2. 거리 매트릭스 (OSRM Table API - 한번에)
        if self.use_osrm_distance:
            logger.info("Fetching distances from OSRM...")
            _, distances = await self.osrm.get_table(locations)
        else:
            distances = None

        # 3. 시간 매트릭스 (실시간 교통 API - 병렬)
        logger.info(f"Fetching durations from {type(self.traffic_provider).__name__}...")

        durations = [[0] * n for _ in range(n)]
        if distances is None:
            distances = [[0] * n for _ in range(n)]

        # 병렬 요청 생성
        tasks = []
        task_indices = []

        for i, origin in enumerate(locations):
            for j, dest in enumerate(locations):
                if i != j:  # 대각선(자기자신)은 0
                    tasks.append(self._get_duration_with_semaphore(origin, dest))
                    task_indices.append((i, j))

        # 병렬 실행
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(results):
                i, j = task_indices[idx]
                if isinstance(result, Exception):
                    logger.error(f"Failed to get duration [{i}][{j}]: {result}")
                    # Fallback: OSRM 시간 사용
                    durations[i][j] = distances[i][j] // 15 if distances[i][j] else 0  # 대략 시속 54km 가정
                else:
                    duration, distance = result
                    durations[i][j] = duration
                    if not self.use_osrm_distance:
                        distances[i][j] = distance

        # 4. 결과 생성
        build_time = int((time.time() - start_time) * 1000)

        result = MatrixResult(
            durations=durations,
            distances=distances,
            locations=locations,
            provider=type(self.traffic_provider).__name__,
            build_time_ms=build_time
        )

        # 5. VRP 입력에 매트릭스 추가
        if include_in_input:
            vrp_input["matrix"] = {
                "durations": durations,
                "distances": distances
            }
            logger.info("Matrix added to VRP input")

        logger.info(f"Matrix built in {build_time}ms")

        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            "traffic_provider": self.traffic_provider.cache.get_stats(),
            "osrm": self.osrm.cache.get_stats()
        }


# ============================================================
# 팩토리 함수
# ============================================================

def create_matrix_builder(
    provider: TrafficProvider = TrafficProvider.TMAP,
    api_key: Optional[str] = None,
    osrm_url: str = "http://localhost:5000",
    **kwargs
) -> HybridMatrixBuilder:
    """
    매트릭스 빌더 생성 팩토리

    Args:
        provider: 교통 정보 제공자 (tmap, kakao, naver, osrm)
        api_key: API 키
        osrm_url: OSRM 서버 URL
        **kwargs: 추가 설정 (naver의 경우 client_id, client_secret)

    Returns:
        HybridMatrixBuilder
    """
    if provider == TrafficProvider.TMAP:
        traffic = TMapProvider(api_key=api_key)
    elif provider == TrafficProvider.KAKAO:
        traffic = KakaoProvider(api_key=api_key)
    elif provider == TrafficProvider.NAVER:
        traffic = NaverProvider(
            client_id=kwargs.get("client_id", ""),
            client_secret=kwargs.get("client_secret", "")
        )
    elif provider == TrafficProvider.OSRM:
        traffic = OSRMProvider(base_url=osrm_url)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return HybridMatrixBuilder(
        traffic_provider=traffic,
        osrm_url=osrm_url,
        parallel_requests=kwargs.get("parallel_requests", 10),
        use_osrm_distance=kwargs.get("use_osrm_distance", True)
    )


# ============================================================
# 사용 예시
# ============================================================

async def example_usage():
    """사용 예시"""

    # 1. 매트릭스 빌더 생성
    builder = create_matrix_builder(
        provider=TrafficProvider.TMAP,
        api_key="YOUR_TMAP_API_KEY",
        osrm_url="http://localhost:5000",
        parallel_requests=10,
        use_osrm_distance=True  # 거리는 OSRM, 시간은 TMap
    )

    # 2. VRP 입력
    vrp_input = {
        "vehicles": [
            {"id": 1, "start": [126.9780, 37.5665]},
            {"id": 2, "start": [127.0276, 37.4979]}
        ],
        "jobs": [
            {"id": 1, "location": [127.0017, 37.5642]},
            {"id": 2, "location": [126.9831, 37.5296]},
            {"id": 3, "location": [127.0507, 37.5047]}
        ]
    }

    # 3. 매트릭스 생성 (vrp_input에 자동 추가됨)
    result = await builder.build(vrp_input, include_in_input=True)

    print(f"Matrix size: {len(result.locations)}x{len(result.locations)}")
    print(f"Build time: {result.build_time_ms}ms")
    print(f"Provider: {result.provider}")

    # 4. 이제 vrp_input에 matrix가 포함됨
    # VROOM에 전달하면 OSRM 호출 없이 이 매트릭스 사용
    print(f"Matrix in input: {'matrix' in vrp_input}")

    return vrp_input


if __name__ == "__main__":
    # OSRM만으로 테스트 (API 키 없이)
    async def test():
        builder = create_matrix_builder(
            provider=TrafficProvider.OSRM,
            osrm_url="http://localhost:5000"
        )

        vrp_input = {
            "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
            "jobs": [
                {"id": 1, "location": [127.0276, 37.4979]},
                {"id": 2, "location": [127.0017, 37.5642]}
            ]
        }

        result = await builder.build(vrp_input)
        print(f"Durations: {result.durations}")
        print(f"Distances: {result.distances}")

    asyncio.run(test())

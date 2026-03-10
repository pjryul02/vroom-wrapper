"""
ValhallaChunkedMatrix - Valhalla sources_to_targets API 기반 매트릭스

OSRMChunkedMatrix의 Valhalla 버전.

차이점:
  - GET /table/v1 (OSRM) → POST /sources_to_targets (Valhalla)
  - JSON 바디에 sources/targets를 lat/lon 객체로 전달
  - 응답: sources_to_targets[i][j].time (초), .distance (km → 미터 변환)
  - Valhalla 기본 매트릭스 한도: 소스 50개 × 타깃 50개
    → chunk_size 기본값 50 (OSRM의 75보다 작음)

참고: https://valhalla.github.io/valhalla/api/matrix/api-reference/
"""

import asyncio
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

UNREACHABLE_DURATION = 999999
UNREACHABLE_DISTANCE = 999999


class ValhallaChunkedMatrix:
    """
    Valhalla sources_to_targets API를 청킹하여 대규모 매트릭스 생성.

    Valhalla 기본 한도(50×50)로 인해 청킹이 OSRM보다 더 중요.
    """

    def __init__(
        self,
        valhalla_url: str = "http://localhost:8002",
        chunk_size: int = 50,
        max_workers: int = 4,
        timeout: int = 30,
        costing: str = "auto",
    ):
        self.valhalla_url = valhalla_url.rstrip("/")
        self.chunk_size = chunk_size
        self.max_workers = max_workers
        self.timeout = timeout
        self.costing = costing  # auto, bicycle, pedestrian, truck 등

    async def build_matrix(
        self,
        locations: List[List[float]],
        profile: str = "driving",  # OSRMChunkedMatrix 인터페이스 호환 (Valhalla에서는 무시됨)
    ) -> Dict[str, List[List[int]]]:
        """
        전체 거리/소요시간 매트릭스 생성

        Args:
            locations: [[lon, lat], ...] (VROOM 표준 형식)
            profile: OSRMChunkedMatrix 호환 파라미터 (Valhalla에서는 무시, costing은 생성자에서 설정)

        Returns:
            {"durations": [[int, ...], ...], "distances": [[int, ...], ...]}
            durations: 초, distances: 미터
        """
        n = len(locations)

        if n == 0:
            return {"durations": [], "distances": []}

        if n == 1:
            return {"durations": [[0]], "distances": [[0]]}

        if n <= self.chunk_size:
            logger.info(f"[VALHALLA-MATRIX] 소규모 ({n}x{n}) - 단일 호출")
            return await self._fetch_full_matrix(locations)

        logger.info(
            f"[VALHALLA-MATRIX] 대규모 ({n}x{n}) - "
            f"chunk_size={self.chunk_size}, max_workers={self.max_workers}"
        )

        chunks = self._split_into_chunks(n)
        logger.info(f"[VALHALLA-MATRIX] {len(chunks)}개 청크")

        durations = [[0] * n for _ in range(n)]
        distances = [[0] * n for _ in range(n)]

        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = [
            self._fetch_chunk(semaphore, locations, src_range, dst_range)
            for src_range, dst_range in chunks
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (src_range, dst_range), result in zip(chunks, results):
            if isinstance(result, Exception):
                logger.error(f"[VALHALLA-MATRIX] 청크 실패: {result}")
                for si in src_range:
                    for di in dst_range:
                        durations[si][di] = UNREACHABLE_DURATION
                        distances[si][di] = UNREACHABLE_DISTANCE
                continue

            chunk_dur, chunk_dist = result
            for si_local, si in enumerate(src_range):
                for di_local, di in enumerate(dst_range):
                    durations[si][di] = chunk_dur[si_local][di_local]
                    distances[si][di] = chunk_dist[si_local][di_local]

        logger.info(f"[VALHALLA-MATRIX] {n}x{n} 완성")
        return {"durations": durations, "distances": distances}

    def _split_into_chunks(self, n: int) -> List[Tuple[List[int], List[int]]]:
        chunks = []
        num_chunks = math.ceil(n / self.chunk_size)
        for si in range(num_chunks):
            src_start = si * self.chunk_size
            src_end = min(src_start + self.chunk_size, n)
            src_range = list(range(src_start, src_end))
            for di in range(num_chunks):
                dst_start = di * self.chunk_size
                dst_end = min(dst_start + self.chunk_size, n)
                dst_range = list(range(dst_start, dst_end))
                chunks.append((src_range, dst_range))
        return chunks

    def _to_valhalla_loc(self, loc: List[float]) -> Dict[str, float]:
        """[lon, lat] → {"lon": x, "lat": y}"""
        return {"lon": loc[0], "lat": loc[1]}

    async def _fetch_full_matrix(
        self,
        locations: List[List[float]],
    ) -> Dict[str, List[List[int]]]:
        """소규모: sources=locations, targets=locations (전체 N×N)"""
        vl = [self._to_valhalla_loc(l) for l in locations]
        return await self._call_api(vl, vl)

    async def _fetch_chunk(
        self,
        semaphore: asyncio.Semaphore,
        locations: List[List[float]],
        src_indices: List[int],
        dst_indices: List[int],
    ) -> Tuple[List[List[int]], List[List[int]]]:
        async with semaphore:
            sources = [self._to_valhalla_loc(locations[i]) for i in src_indices]
            targets = [self._to_valhalla_loc(locations[i]) for i in dst_indices]
            return await self._call_api(sources, targets)

    async def _call_api(
        self,
        sources: List[Dict],
        targets: List[Dict],
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """
        POST /sources_to_targets 호출 → (durations, distances)

        Valhalla 응답:
          sources_to_targets[i][j].time     → 초
          sources_to_targets[i][j].distance → km (→ 미터로 변환)
        """
        payload = {
            "sources": sources,
            "targets": targets,
            "costing": self.costing,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.valhalla_url}/sources_to_targets",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        matrix = data.get("sources_to_targets", [])

        n_src = len(sources)
        n_dst = len(targets)
        durations: List[List[int]] = []
        distances: List[List[int]] = []

        for i in range(n_src):
            row_dur = []
            row_dist = []
            for j in range(n_dst):
                cell = matrix[i][j] if i < len(matrix) and j < len(matrix[i]) else None
                if cell is None or cell.get("time") is None:
                    row_dur.append(UNREACHABLE_DURATION)
                    row_dist.append(UNREACHABLE_DISTANCE)
                else:
                    row_dur.append(int(cell["time"] + 0.5))
                    # distance는 km 단위 → 미터 변환
                    dist_km = cell.get("distance", 0) or 0
                    row_dist.append(int(dist_km * 1000 + 0.5))
            durations.append(row_dur)
            distances.append(row_dist)

        return durations, distances

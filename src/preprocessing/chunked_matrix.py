"""
OSRMChunkedMatrix - 대규모 매트릭스 병렬 청킹

Roouty Engine (Go)의 패턴을 Python으로 구현:
- 대규모 매트릭스를 chunk_size x chunk_size로 분할
- 병렬 OSRM 호출 (asyncio.Semaphore로 동시 요청 제한)
- 결과를 전체 매트릭스로 조립
- null 값 → 큰 값으로 변환 (도달 불가능 마커)

참고: roouty-engine/pkg/routing/osrm/osrm.go
  - RequestCostMatrix() → table() → splitIntoChunks() → tableChunk()
"""

import asyncio
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# OSRM이 null 반환 시 대체값 (Roouty와 동일)
UNREACHABLE_DURATION = 999999
UNREACHABLE_DISTANCE = 999999


class OSRMChunkedMatrix:
    """
    OSRM Table API를 청킹하여 대규모 매트릭스 생성

    250개 위치 = 250x250 = 62,500 셀
    → 75x75 청크 = 12개 → 병렬 처리
    """

    def __init__(
        self,
        osrm_url: str = "http://localhost:5000",
        chunk_size: int = 75,
        max_workers: int = 8,
        timeout: int = 30,
    ):
        self.osrm_url = osrm_url.rstrip("/")
        self.chunk_size = chunk_size
        self.max_workers = max_workers
        self.timeout = timeout

    async def build_matrix(
        self,
        locations: List[List[float]],
        profile: str = "driving",
    ) -> Dict[str, List[List[int]]]:
        """
        전체 거리/소요시간 매트릭스 생성

        Args:
            locations: [[lon, lat], ...] 좌표 리스트
            profile: OSRM 프로필 (driving, cycling, foot)

        Returns:
            {"durations": [[int]], "distances": [[int]]}
        """
        n = len(locations)

        if n == 0:
            return {"durations": [], "distances": []}

        # 소규모: 청킹 불필요
        if n <= self.chunk_size:
            logger.info(f"[MATRIX] 소규모 ({n}x{n}) - 단일 OSRM 호출")
            return await self._fetch_full_matrix(locations, profile)

        # 대규모: 청킹 + 병렬
        logger.info(
            f"[MATRIX] 대규모 ({n}x{n}) - "
            f"chunk_size={self.chunk_size}, max_workers={self.max_workers}"
        )

        chunks = self._split_into_chunks(n)
        logger.info(f"[MATRIX] {len(chunks)}개 청크 생성")

        # 결과 매트릭스 초기화
        durations = [[0] * n for _ in range(n)]
        distances = [[0] * n for _ in range(n)]

        # 병렬 청크 처리
        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = []

        for src_range, dst_range in chunks:
            tasks.append(
                self._fetch_chunk(
                    semaphore, locations, src_range, dst_range, profile
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 조립
        for i, ((src_range, dst_range), result) in enumerate(
            zip(chunks, results)
        ):
            if isinstance(result, Exception):
                logger.error(f"[MATRIX] 청크 {i} 실패: {result}")
                # 실패한 청크는 큰 값으로 채움
                for si, src_idx in enumerate(src_range):
                    for di, dst_idx in enumerate(dst_range):
                        durations[src_idx][dst_idx] = UNREACHABLE_DURATION
                        distances[src_idx][dst_idx] = UNREACHABLE_DISTANCE
                continue

            chunk_dur, chunk_dist = result
            for si, src_idx in enumerate(src_range):
                for di, dst_idx in enumerate(dst_range):
                    durations[src_idx][dst_idx] = chunk_dur[si][di]
                    distances[src_idx][dst_idx] = chunk_dist[si][di]

        logger.info(f"[MATRIX] {n}x{n} 매트릭스 완성")
        return {"durations": durations, "distances": distances}

    def _split_into_chunks(
        self, n: int
    ) -> List[Tuple[List[int], List[int]]]:
        """
        인덱스를 chunk_size 단위로 분할

        Roouty의 splitIntoChunks() 패턴.
        모든 src x dst 조합 생성.
        """
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

    async def _fetch_full_matrix(
        self,
        locations: List[List[float]],
        profile: str,
    ) -> Dict[str, List[List[int]]]:
        """소규모 매트릭스: 단일 OSRM 호출"""
        coords = ";".join(f"{loc[0]},{loc[1]}" for loc in locations)
        url = f"{self.osrm_url}/table/v1/{profile}/{coords}"
        params = {"annotations": "duration,distance"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        return {
            "durations": self._sanitize_matrix(
                data.get("durations", []), UNREACHABLE_DURATION
            ),
            "distances": self._sanitize_matrix(
                data.get("distances", []), UNREACHABLE_DISTANCE
            ),
        }

    async def _fetch_chunk(
        self,
        semaphore: asyncio.Semaphore,
        locations: List[List[float]],
        src_indices: List[int],
        dst_indices: List[int],
        profile: str,
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """
        단일 청크 OSRM 호출

        Roouty의 tableChunk() 패턴:
        - 좌표 결합: sources + destinations
        - sources/destinations 파라미터로 인덱스 지정
        - 결과 매핑
        """
        async with semaphore:
            # 중복 없이 좌표 결합
            all_indices = list(dict.fromkeys(src_indices + dst_indices))
            coords = ";".join(
                f"{locations[i][0]},{locations[i][1]}" for i in all_indices
            )

            # 로컬 인덱스 매핑
            idx_map = {orig: local for local, orig in enumerate(all_indices)}
            sources = ";".join(str(idx_map[i]) for i in src_indices)
            destinations = ";".join(str(idx_map[i]) for i in dst_indices)

            url = f"{self.osrm_url}/table/v1/{profile}/{coords}"
            params = {
                "sources": sources,
                "destinations": destinations,
                "annotations": "duration,distance",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            chunk_durations = self._sanitize_matrix(
                data.get("durations", []), UNREACHABLE_DURATION
            )
            chunk_distances = self._sanitize_matrix(
                data.get("distances", []), UNREACHABLE_DISTANCE
            )

            return chunk_durations, chunk_distances

    def _sanitize_matrix(
        self,
        matrix: List[List[Optional[float]]],
        default: int,
    ) -> List[List[int]]:
        """
        OSRM 매트릭스 정리

        - null → UNREACHABLE 값 변환
        - float → int 반올림
        """
        result = []
        for row in matrix:
            sanitized_row = []
            for val in row:
                if val is None:
                    sanitized_row.append(default)
                else:
                    sanitized_row.append(int(val + 0.5))
            result.append(sanitized_row)
        return result

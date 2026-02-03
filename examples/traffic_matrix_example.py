#!/usr/bin/env python3
"""
실시간 교통 매트릭스 사용 예시

이 예시는 TMap/Kakao/Naver API를 사용하여
실시간 교통 정보 기반의 소요시간을 계산하는 방법을 보여줍니다.

실행 전:
1. OSRM 서버가 실행 중이어야 합니다 (거리 계산용)
2. 사용할 교통 API 키가 필요합니다
"""

import asyncio
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing.matrix_builder import (
    create_matrix_builder,
    TrafficProvider,
    HybridMatrixBuilder
)
from src.preprocessing.preprocessor import PreProcessor


# ============================================================
# 예시 1: OSRM만 사용 (API 키 없이 테스트)
# ============================================================

async def example_osrm_only():
    """OSRM만 사용하여 매트릭스 생성 (실시간 교통 없음)"""

    print("=" * 50)
    print("예시 1: OSRM 매트릭스 (실시간 교통 없음)")
    print("=" * 50)

    # 매트릭스 빌더 생성
    builder = create_matrix_builder(
        provider=TrafficProvider.OSRM,
        osrm_url="http://localhost:5000"
    )

    # VRP 입력
    vrp_input = {
        "vehicles": [
            {"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665]},  # 서울시청
        ],
        "jobs": [
            {"id": 1, "location": [127.0276, 37.4979]},  # 강남역
            {"id": 2, "location": [127.0017, 37.5642]},  # 종로
            {"id": 3, "location": [126.9831, 37.5296]},  # 용산
        ]
    }

    # 매트릭스 빌드
    result = await builder.build(vrp_input, include_in_input=True)

    # 결과 출력
    print(f"\n지점 수: {len(result.locations)}")
    print(f"빌드 시간: {result.build_time_ms}ms")
    print(f"제공자: {result.provider}")

    print("\n시간 매트릭스 (초):")
    for i, row in enumerate(result.durations):
        print(f"  {i}: {row}")

    print("\n거리 매트릭스 (미터):")
    for i, row in enumerate(result.distances):
        print(f"  {i}: {row}")

    print("\nVRP 입력에 매트릭스 포함됨:", "matrix" in vrp_input)

    return vrp_input


# ============================================================
# 예시 2: TMap 실시간 교통 사용
# ============================================================

async def example_tmap():
    """TMap API로 실시간 교통 기반 소요시간 계산"""

    print("=" * 50)
    print("예시 2: TMap 실시간 교통")
    print("=" * 50)

    # TMap API 키 확인
    tmap_key = os.getenv("TMAP_API_KEY")
    if not tmap_key:
        print("⚠️  TMAP_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export TMAP_API_KEY=your_api_key")
        return None

    # 하이브리드 빌더: 거리=OSRM, 시간=TMap
    builder = create_matrix_builder(
        provider=TrafficProvider.TMAP,
        api_key=tmap_key,
        osrm_url="http://localhost:5000",
        parallel_requests=5,  # TMap API 동시 요청 제한
        use_osrm_distance=True  # 거리는 OSRM 사용
    )

    vrp_input = {
        "vehicles": [
            {"id": 1, "start": [126.9780, 37.5665]},  # 서울시청
        ],
        "jobs": [
            {"id": 1, "location": [127.0276, 37.4979]},  # 강남역
            {"id": 2, "location": [127.0017, 37.5642]},  # 종로
        ]
    }

    result = await builder.build(vrp_input, include_in_input=True)

    print(f"\n빌드 시간: {result.build_time_ms}ms")
    print(f"제공자: {result.provider}")
    print("\n실시간 소요시간 (초):")
    for i, row in enumerate(result.durations):
        print(f"  {i}: {row}")

    # 캐시 통계
    stats = builder.get_cache_stats()
    print(f"\n캐시 통계: {stats}")

    return vrp_input


# ============================================================
# 예시 3: PreProcessor 통합 사용
# ============================================================

async def example_preprocessor_integration():
    """PreProcessor에서 교통 매트릭스 사용"""

    print("=" * 50)
    print("예시 3: PreProcessor 통합")
    print("=" * 50)

    # PreProcessor 생성 (OSRM 사용)
    preprocessor = PreProcessor(
        enable_validation=True,
        enable_normalization=True,
        enable_business_rules=True,
        enable_traffic_matrix=True,
        traffic_provider=TrafficProvider.OSRM,
        osrm_url="http://localhost:5000"
    )

    vrp_input = {
        "vehicles": [
            {"id": 1, "start": [126.9780, 37.5665]},
        ],
        "jobs": [
            {"id": 1, "location": [127.0276, 37.4979], "description": "VIP 고객"},
            {"id": 2, "location": [127.0017, 37.5642]},
        ]
    }

    # 전처리 실행 (Phase 1 + 1.5)
    result = await preprocessor.process(vrp_input)

    print("\n전처리 완료!")
    print(f"- 매트릭스 포함: {'matrix' in result}")
    print(f"- VIP 스킬 부여: {10000 in result['jobs'][0].get('skills', [])}")

    # 매트릭스 통계
    stats = preprocessor.get_matrix_stats()
    if stats:
        print(f"\n매트릭스 통계:")
        print(f"  - 크기: {stats['matrix_size']}x{stats['matrix_size']}")
        print(f"  - 빌드 시간: {stats['build_time_ms']}ms")

    return result


# ============================================================
# 예시 4: 런타임에 제공자 변경
# ============================================================

async def example_change_provider():
    """런타임에 교통 정보 제공자 변경"""

    print("=" * 50)
    print("예시 4: 런타임 제공자 변경")
    print("=" * 50)

    preprocessor = PreProcessor(
        enable_traffic_matrix=False  # 초기에는 비활성화
    )

    # 런타임에 TMap으로 활성화
    tmap_key = os.getenv("TMAP_API_KEY")
    if tmap_key:
        preprocessor.set_traffic_provider(
            provider=TrafficProvider.TMAP,
            api_key=tmap_key
        )
        print("TMap 제공자로 변경됨")
    else:
        # API 키 없으면 OSRM 사용
        preprocessor.set_traffic_provider(
            provider=TrafficProvider.OSRM
        )
        print("OSRM 제공자로 변경됨 (API 키 없음)")

    vrp_input = {
        "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
        "jobs": [{"id": 1, "location": [127.0276, 37.4979]}]
    }

    result = await preprocessor.process(vrp_input)
    print(f"매트릭스 포함: {'matrix' in result}")

    return result


# ============================================================
# 예시 5: OSRM과 TMap 비교
# ============================================================

async def example_compare_providers():
    """OSRM (정적) vs TMap (실시간) 소요시간 비교"""

    print("=" * 50)
    print("예시 5: OSRM vs TMap 소요시간 비교")
    print("=" * 50)

    tmap_key = os.getenv("TMAP_API_KEY")

    # 테스트 지점
    origin = (126.9780, 37.5665)  # 서울시청
    dest = (127.0276, 37.4979)    # 강남역

    vrp_input = {
        "vehicles": [{"id": 1, "start": list(origin)}],
        "jobs": [{"id": 1, "location": list(dest)}]
    }

    # OSRM 결과
    osrm_builder = create_matrix_builder(
        provider=TrafficProvider.OSRM,
        osrm_url="http://localhost:5000"
    )
    osrm_result = await osrm_builder.build(vrp_input.copy())
    osrm_duration = osrm_result.durations[0][1]

    print(f"\nOSRM (정적 도로망):")
    print(f"  서울시청 → 강남역: {osrm_duration}초 ({osrm_duration//60}분)")

    # TMap 결과
    if tmap_key:
        tmap_builder = create_matrix_builder(
            provider=TrafficProvider.TMAP,
            api_key=tmap_key,
            osrm_url="http://localhost:5000"
        )
        tmap_result = await tmap_builder.build(vrp_input.copy())
        tmap_duration = tmap_result.durations[0][1]

        print(f"\nTMap (실시간 교통):")
        print(f"  서울시청 → 강남역: {tmap_duration}초 ({tmap_duration//60}분)")

        diff = tmap_duration - osrm_duration
        diff_pct = (diff / osrm_duration) * 100 if osrm_duration > 0 else 0
        print(f"\n차이: {diff:+d}초 ({diff_pct:+.1f}%)")

        if diff > 0:
            print("→ 현재 교통 체증이 있습니다")
        elif diff < 0:
            print("→ 현재 도로 상황이 원활합니다")
    else:
        print("\n⚠️  TMap 비교 건너뜀 (API 키 없음)")


# ============================================================
# 메인
# ============================================================

async def main():
    """모든 예시 실행"""

    print("\n" + "=" * 60)
    print("실시간 교통 매트릭스 예시")
    print("=" * 60 + "\n")

    # 예시 1: OSRM만 (API 키 불필요)
    try:
        await example_osrm_only()
    except Exception as e:
        print(f"❌ 예시 1 실패: {e}")
        print("   OSRM 서버가 실행 중인지 확인하세요.")
        return

    print("\n")

    # 예시 3: PreProcessor 통합
    try:
        await example_preprocessor_integration()
    except Exception as e:
        print(f"❌ 예시 3 실패: {e}")

    print("\n")

    # 예시 5: 비교 (TMap 키 있으면)
    try:
        await example_compare_providers()
    except Exception as e:
        print(f"❌ 예시 5 실패: {e}")

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

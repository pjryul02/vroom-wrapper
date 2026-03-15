#!/usr/bin/env python3
"""
VROOM Wrapper v2.0 데모

실제 데이터로 전체 파이프라인 검증
"""

import sys
sys.path.insert(0, 'src')

import asyncio
import json
from preprocessing import PreProcessor
from control import OptimizationController, ControlLevel
from postprocessing import ResultAnalyzer

# 실제 서울 데이터
SAMPLE_DATA = {
    "vehicles": [
        {
            "id": 1,
            "start": [126.9780, 37.5665],  # 서울시청
            "capacity": [100]
        },
        {
            "id": 2,
            "start": [127.0276, 37.4979],  # 강남역
            "capacity": [100]
        }
    ],
    "jobs": [
        {
            "id": 1,
            "location": [127.0276, 37.4979],  # 강남역
            "service": 300,
            "delivery": [10],
            "description": "일반 배송"
        },
        {
            "id": 2,
            "location": [126.9780, 37.5665],  # 서울시청
            "service": 300,
            "delivery": [15],
            "description": "VIP customer delivery"
        },
        {
            "id": 3,
            "location": [127.1086, 37.3595],  # 판교
            "service": 600,
            "delivery": [20],
            "description": "Urgent delivery"
        },
        {
            "id": 4,
            "location": [126.9520, 37.4783],  # 사당
            "service": 300,
            "delivery": [12],
            "priority": 50
        }
    ]
}


async def main():
    print("=" * 70)
    print("VROOM Wrapper v2.0 전체 파이프라인 데모")
    print("=" * 70)

    # Phase 1: 전처리
    print("\n[Phase 1] 전처리 중...")
    preprocessor = PreProcessor()
    processed = preprocessor.process(SAMPLE_DATA.copy())

    print(f"✓ 입력 검증 완료")
    print(f"✓ 정규화 완료")
    print(f"✓ 비즈니스 규칙 적용 완료")
    print(f"  - 차량: {len(processed['vehicles'])}개")
    print(f"  - 작업: {len(processed['jobs'])}개")

    # VIP/긴급 체크
    vip_jobs = [j for j in processed['jobs'] if 10000 in j.get('skills', [])]
    urgent_jobs = [j for j in processed['jobs'] if 10001 in j.get('skills', [])]

    if vip_jobs:
        print(f"  - VIP 작업: {len(vip_jobs)}개 (Job #{[j['id'] for j in vip_jobs]})")
    if urgent_jobs:
        print(f"  - 긴급 작업: {len(urgent_jobs)}개 (Job #{[j['id'] for j in urgent_jobs]})")

    # Phase 2: 최적화
    print("\n[Phase 2] VROOM 최적화 중...")
    controller = OptimizationController(vroom_url="http://localhost:3000")

    try:
        result = await controller.optimize(
            processed,
            control_level=ControlLevel.STANDARD,
            enable_auto_retry=True
        )

        print(f"✓ 최적화 완료")
        print(f"  - 경로 수: {len(result['routes'])}")
        print(f"  - 총 비용: {result['summary'].get('cost', 0)}")
        print(f"  - 총 거리: {result['summary'].get('distance', 0)}m")
        print(f"  - 총 시간: {result['summary'].get('duration', 0)}초")
        print(f"  - 미배정: {len(result.get('unassigned', []))}개")

        # 경로 상세
        print("\n  경로 상세:")
        for route in result['routes']:
            vehicle_id = route['vehicle']
            jobs = [s for s in route['steps'] if s['type'] == 'job']
            job_ids = [s['job'] for s in jobs]

            print(f"    차량 #{vehicle_id}: {len(jobs)}개 작업 → Job {job_ids}")

        # Phase 3: 분석
        print("\n[Phase 3] 결과 분석 중...")
        analyzer = ResultAnalyzer()
        analysis = analyzer.analyze(processed, result)

        print(f"✓ 분석 완료")
        print(f"  - 품질 점수: {analysis['quality_score']:.1f}/100")
        print(f"  - 배정률: {analysis['assignment_rate']:.1f}%")
        print(f"  - 경로 균형도: {analysis['route_balance']['balance_score']:.1f}/100")

        # 개선 제안
        print(f"\n  개선 제안:")
        for suggestion in analysis['suggestions']:
            print(f"    • {suggestion}")

        # 최종 요약
        print("\n" + "=" * 70)
        print("최종 결과 요약")
        print("=" * 70)
        print(f"품질 점수: {analysis['quality_score']:.1f}/100")
        print(f"배정률: {analysis['assignment_rate']:.1f}%")
        print(f"총 비용: {result['summary'].get('cost', 0)}")
        print(f"총 거리: {result['summary'].get('distance', 0)}m")
        print(f"총 시간: {result['summary'].get('duration', 0) // 60}분 {result['summary'].get('duration', 0) % 60}초")
        print(f"미배정: {len(result.get('unassigned', []))}개")
        print("=" * 70)

        # JSON 출력 (선택 사항)
        print("\n[선택] 전체 결과를 JSON으로 저장하시겠습니까? (y/N): ", end='')

        return {
            'processed_input': processed,
            'optimization_result': result,
            'analysis': analysis
        }

    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        print(f"\n참고: VROOM 서버가 실행 중인지 확인하세요 (http://localhost:3000)")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())

    if result:
        print("\n✅ v2.0 전체 파이프라인 검증 완료!")
    else:
        print("\n❌ 파이프라인 실행 실패")

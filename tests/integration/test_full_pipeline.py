#!/usr/bin/env python3
"""
통합 테스트: 전체 파이프라인 (Phase 1-3)

실제 데이터로 검증:
- Phase 1: 전처리
- Phase 2: 최적화 (VROOM 서버 필요)
- Phase 3: 후처리
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
import asyncio
from preprocessing import PreProcessor
from control import OptimizationController, ControlLevel
from postprocessing import ResultAnalyzer


# 실제 VRP 데이터 샘플
SAMPLE_VRP_DATA = {
    "vehicles": [
        {
            "id": 1,
            "start": [126.9780, 37.5665],  # 서울시청
            "end": [126.9780, 37.5665],
            "capacity": [100]
        },
        {
            "id": 2,
            "start": [127.0276, 37.4979],  # 강남역
            "end": [127.0276, 37.4979],
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


class TestFullPipeline:
    """전체 파이프라인 통합 테스트"""

    def test_phase1_preprocessing(self):
        """Phase 1: 전처리 테스트"""
        print("\n=== Phase 1: Pre-processing ===")

        preprocessor = PreProcessor()

        # 전처리 실행
        processed = preprocessor.process(SAMPLE_VRP_DATA.copy())

        # 검증
        assert 'vehicles' in processed
        assert 'jobs' in processed
        assert len(processed['vehicles']) == 2
        assert len(processed['jobs']) == 4

        # VIP 스킬 확인
        vip_job = next(j for j in processed['jobs'] if j['id'] == 2)
        assert 10000 in vip_job['skills'], "VIP 스킬이 추가되어야 함"

        # 긴급 스킬 확인
        urgent_job = next(j for j in processed['jobs'] if j['id'] == 3)
        assert 10001 in urgent_job['skills'], "긴급 스킬이 추가되어야 함"

        # 기본값 확인
        for vehicle in processed['vehicles']:
            assert 'end' in vehicle
            assert vehicle['end'] == vehicle['start']

        print(f"✓ 전처리 완료: {len(processed['jobs'])}개 작업, {len(processed['vehicles'])}개 차량")
        print(f"✓ VIP 작업 탐지: Job #{vip_job['id']}")
        print(f"✓ 긴급 작업 탐지: Job #{urgent_job['id']}")

    @pytest.mark.asyncio
    async def test_phase2_optimization_basic(self):
        """Phase 2: BASIC 레벨 최적화 테스트"""
        print("\n=== Phase 2: Optimization (BASIC) ===")

        preprocessor = PreProcessor()
        controller = OptimizationController(vroom_url="http://localhost:3000")

        # 전처리
        processed = preprocessor.process(SAMPLE_VRP_DATA.copy())

        # BASIC 레벨 최적화
        result = await controller.optimize(
            processed,
            control_level=ControlLevel.BASIC,
            enable_auto_retry=False
        )

        # 검증
        assert 'routes' in result
        assert 'summary' in result

        print(f"✓ BASIC 최적화 완료")
        print(f"  - 경로 수: {len(result['routes'])}")
        print(f"  - 총 비용: {result['summary'].get('cost', 0)}")
        print(f"  - 총 거리: {result['summary'].get('distance', 0)}m")
        print(f"  - 미배정: {len(result.get('unassigned', []))}개")

        return result

    @pytest.mark.asyncio
    async def test_phase2_optimization_standard(self):
        """Phase 2: STANDARD 레벨 최적화 테스트"""
        print("\n=== Phase 2: Optimization (STANDARD) ===")

        preprocessor = PreProcessor()
        controller = OptimizationController(vroom_url="http://localhost:3000")

        # 전처리
        processed = preprocessor.process(SAMPLE_VRP_DATA.copy())

        # STANDARD 레벨 최적화
        result = await controller.optimize(
            processed,
            control_level=ControlLevel.STANDARD,
            enable_auto_retry=True
        )

        # 검증
        assert 'routes' in result
        assert 'summary' in result

        print(f"✓ STANDARD 최적화 완료")
        print(f"  - 경로 수: {len(result['routes'])}")
        print(f"  - 총 비용: {result['summary'].get('cost', 0)}")
        print(f"  - 총 거리: {result['summary'].get('distance', 0)}m")
        print(f"  - 미배정: {len(result.get('unassigned', []))}개")

        # 경로 상세 출력
        for route in result['routes']:
            vehicle_id = route['vehicle']
            num_jobs = len([s for s in route['steps'] if s['type'] == 'job'])
            print(f"  - 차량 #{vehicle_id}: {num_jobs}개 작업")

        return result

    @pytest.mark.asyncio
    async def test_phase3_analysis(self):
        """Phase 3: 결과 분석 테스트"""
        print("\n=== Phase 3: Post-processing ===")

        preprocessor = PreProcessor()
        controller = OptimizationController(vroom_url="http://localhost:3000")
        analyzer = ResultAnalyzer()

        # 전처리 + 최적화
        processed = preprocessor.process(SAMPLE_VRP_DATA.copy())
        result = await controller.optimize(
            processed,
            control_level=ControlLevel.STANDARD
        )

        # 분석
        analysis = analyzer.analyze(processed, result)

        # 검증
        assert 'quality_score' in analysis
        assert 'assignment_rate' in analysis
        assert 'suggestions' in analysis

        print(f"✓ 분석 완료")
        print(f"  - 품질 점수: {analysis['quality_score']}/100")
        print(f"  - 배정률: {analysis['assignment_rate']:.1f}%")
        print(f"  - 경로 균형도: {analysis['route_balance']['balance_score']:.1f}")

        print(f"\n📋 개선 제안:")
        for suggestion in analysis['suggestions']:
            print(f"  • {suggestion}")

        return analysis

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """전체 파이프라인 통합 테스트"""
        print("\n" + "="*60)
        print("전체 파이프라인 통합 테스트")
        print("="*60)

        # Phase 1
        preprocessor = PreProcessor()
        processed = preprocessor.process(SAMPLE_VRP_DATA.copy())
        print("\n✓ Phase 1 완료 (전처리)")

        # Phase 2
        controller = OptimizationController(vroom_url="http://localhost:3000")
        result = await controller.optimize(
            processed,
            control_level=ControlLevel.STANDARD
        )
        print("✓ Phase 2 완료 (최적화)")

        # Phase 3
        analyzer = ResultAnalyzer()
        analysis = analyzer.analyze(processed, result)
        print("✓ Phase 3 완료 (분석)")

        print("\n" + "="*60)
        print("최종 결과")
        print("="*60)
        print(f"품질 점수: {analysis['quality_score']}/100")
        print(f"배정률: {analysis['assignment_rate']:.1f}%")
        print(f"총 비용: {result['summary'].get('cost', 0)}")
        print(f"총 거리: {result['summary'].get('distance', 0)}m")
        print(f"미배정: {len(result.get('unassigned', []))}개")
        print("="*60)

        # 최종 검증
        assert analysis['quality_score'] > 0
        assert analysis['assignment_rate'] > 0
        assert len(result['routes']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

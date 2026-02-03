# 모듈화된 Wrapper 설계: 플러그인 아키텍처

**핵심 아이디어**: Wrapper를 독립적인 모듈로 분리하여 MoE(Mixture of Experts)처럼 조합

---

## 1. 왜 모듈화인가?

### 1.1 현재 문제 (Monolithic Wrapper)

```python
# 현재 (v1.0): 하나의 큰 Wrapper
@app.post("/optimize")
async def optimize(vrp_input):
    # 전처리
    vrp_input = preprocess(vrp_input)

    # VROOM 호출
    result = call_vroom(vrp_input)

    # 후처리
    result = postprocess(result)

    return result
```

**문제점**:
- ❌ 특정 기능만 사용 불가 (all or nothing)
- ❌ 기능 추가 시 전체 코드 수정 필요
- ❌ 병렬 실행 어려움
- ❌ 재사용성 낮음

### 1.2 모듈화 후 (Pluggable Wrapper)

```python
# 모듈화 (v2.0): 독립 모듈 조합
from modules import (
    ValidationModule,
    NormalizationModule,
    BusinessRuleModule,
    VROOMCallerModule,
    ETAEnrichmentModule,
    AnalysisModule
)

# 파이프라인 구성
pipeline = Pipeline([
    ValidationModule(),
    NormalizationModule(),
    BusinessRuleModule(),
    VROOMCallerModule(),
    ETAEnrichmentModule(use_realtime=True),
    AnalysisModule()
])

result = await pipeline.execute(vrp_input)
```

**장점**:
- ✅ 필요한 모듈만 선택 가능
- ✅ 모듈 독립 개발/테스트
- ✅ 병렬 실행 가능
- ✅ 재사용성 높음

---

## 2. 모듈 아키텍처

### 2.1 기본 구조

```python
# module_base.py

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class WrapperModule(ABC):
    """Wrapper 모듈 베이스 클래스"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        모듈 실행

        Args:
            context: 이전 모듈의 출력 + 공유 컨텍스트

        Returns:
            업데이트된 context
        """
        pass

    def validate_input(self, context: Dict) -> bool:
        """입력 검증 (선택적)"""
        return True

    def get_dependencies(self) -> List[str]:
        """의존성 모듈 목록 (선택적)"""
        return []

    async def __call__(self, context: Dict) -> Dict:
        """편의를 위한 호출 인터페이스"""
        logger.info(f"[{self.name}] Starting...")

        if not self.validate_input(context):
            raise ValueError(f"[{self.name}] Invalid input")

        result = await self.execute(context)

        logger.info(f"[{self.name}] Completed")
        return result
```

### 2.2 Pipeline 클래스

```python
# pipeline.py

from typing import List, Dict, Any
from module_base import WrapperModule
import asyncio
import logging

logger = logging.getLogger(__name__)

class Pipeline:
    """모듈 실행 파이프라인"""

    def __init__(self, modules: List[WrapperModule]):
        self.modules = modules
        self._validate_pipeline()

    def _validate_pipeline(self):
        """파이프라인 유효성 검증 (의존성 체크)"""
        module_names = {m.name for m in self.modules}

        for module in self.modules:
            deps = module.get_dependencies()
            for dep in deps:
                if dep not in module_names:
                    raise ValueError(
                        f"Missing dependency: {module.name} requires {dep}"
                    )

    async def execute(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """파이프라인 실행"""
        context = initial_context.copy()
        context['_pipeline_metadata'] = {
            'modules_executed': [],
            'module_timings': {}
        }

        for module in self.modules:
            import time
            start = time.time()

            try:
                context = await module(context)

                duration = time.time() - start
                context['_pipeline_metadata']['modules_executed'].append(module.name)
                context['_pipeline_metadata']['module_timings'][module.name] = duration

                logger.info(f"✓ {module.name} ({duration:.3f}s)")

            except Exception as e:
                logger.error(f"✗ {module.name} failed: {e}")
                raise

        return context

    def add_module(self, module: WrapperModule, position: int = None):
        """런타임에 모듈 추가"""
        if position is None:
            self.modules.append(module)
        else:
            self.modules.insert(position, module)

        self._validate_pipeline()

    def remove_module(self, module_name: str):
        """런타임에 모듈 제거"""
        self.modules = [m for m in self.modules if m.name != module_name]


class ParallelPipeline(Pipeline):
    """병렬 실행 파이프라인"""

    async def execute_parallel(
        self,
        initial_context: Dict[str, Any],
        parallel_groups: List[List[WrapperModule]]
    ) -> Dict[str, Any]:
        """
        그룹별 병렬 실행

        parallel_groups = [
            [Module1, Module2],  # 이 2개는 병렬
            [Module3],           # 이건 이후 순차
        ]
        """
        context = initial_context.copy()

        for group in parallel_groups:
            # 그룹 내 모듈 병렬 실행
            tasks = [module(context.copy()) for module in group]
            results = await asyncio.gather(*tasks)

            # 결과 병합 (마지막 결과 우선)
            for result in results:
                context.update(result)

        return context
```

---

## 3. 핵심 모듈 구현

### 3.1 전처리 모듈

```python
# modules/preprocessing.py

from module_base import WrapperModule
from typing import Dict, Any

class ValidationModule(WrapperModule):
    """입력 검증 모듈"""

    async def execute(self, context: Dict) -> Dict:
        from models import VRPInput

        vrp_input = context.get('vrp_input')
        validated = VRPInput(**vrp_input)

        context['vrp_input'] = validated.dict()
        context['_validation_passed'] = True

        return context


class NormalizationModule(WrapperModule):
    """정규화 모듈"""

    async def execute(self, context: Dict) -> Dict:
        from normalizer import InputNormalizer

        normalizer = InputNormalizer()
        context['vrp_input'] = normalizer.normalize(context['vrp_input'])
        context['_normalized'] = True

        return context


class BusinessRuleModule(WrapperModule):
    """비즈니스 규칙 모듈"""

    async def execute(self, context: Dict) -> Dict:
        from business_rules import BusinessRuleEngine

        rules = context.get('business_rules')
        if not rules:
            return context

        engine = BusinessRuleEngine()
        context['vrp_input'] = engine.apply_rules(
            context['vrp_input'],
            rules
        )
        context['_business_rules_applied'] = True

        return context
```

### 3.2 최적화 모듈

```python
# modules/optimization.py

class VROOMCallerModule(WrapperModule):
    """VROOM 호출 모듈"""

    def __init__(self, vroom_url: str = "http://localhost:3000"):
        super().__init__()
        self.vroom_url = vroom_url

    async def execute(self, context: Dict) -> Dict:
        import httpx

        vrp_input = context['vrp_input']

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.vroom_url,
                json=vrp_input,
                timeout=300
            )
            result = response.json()

        context['vroom_result'] = result
        context['_vroom_called'] = True

        return context


class MultiScenarioModule(WrapperModule):
    """다중 시나리오 최적화 모듈"""

    async def execute(self, context: Dict) -> Dict:
        from multi_scenario import MultiScenarioEngine

        engine = MultiScenarioEngine()
        result = await engine.optimize_multi(context['vrp_input'])

        context['vroom_result'] = result
        context['_multi_scenario_used'] = True

        return context


class ConstraintTunerModule(WrapperModule):
    """제약조건 튜닝 모듈"""

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        from constraint_tuner import ConstraintTuner

        initial_result = context['vroom_result']
        vrp_input = context['vrp_input']

        tuner = ConstraintTuner()
        tuned_result = tuner.auto_tune(vrp_input, initial_result)

        context['vroom_result'] = tuned_result
        context['_constraint_tuned'] = True

        return context
```

### 3.3 Enrichment 모듈

```python
# modules/enrichment.py

class UnassignedReasonModule(WrapperModule):
    """미배정 사유 분석 모듈 (v1.0 기능)"""

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        from vroom_wrapper import ConstraintChecker

        result = context['vroom_result']
        vrp_input = context['vrp_input']

        if result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(result['unassigned'])

            for unassigned in result['unassigned']:
                unassigned['reasons'] = reasons_map[unassigned['id']]

            context['_unassigned_reasons_added'] = True

        return context


class ETAEnrichmentModule(WrapperModule):
    """실시간 ETA enrichment 모듈"""

    def __init__(self, use_realtime: bool = False):
        super().__init__()
        self.use_realtime = use_realtime

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        if not self.use_realtime:
            return context

        from eta_calculator import ETACalculator

        result = context['vroom_result']
        departure_time = context.get('departure_time')

        if not departure_time:
            from datetime import datetime
            departure_time = datetime.now()

        calculator = ETACalculator()
        result['routes'] = await calculator.enrich_routes_with_realtime_eta(
            result['routes'],
            departure_time
        )

        context['vroom_result'] = result
        context['_realtime_eta_added'] = True

        return context


class WeatherEnrichmentModule(WrapperModule):
    """날씨 정보 추가 모듈"""

    async def execute(self, context: Dict) -> Dict:
        from external_api import ExternalAPIIntegrator

        api = ExternalAPIIntegrator()
        context['vrp_input'] = await api._add_weather_info(
            context['vrp_input']
        )
        context['_weather_enriched'] = True

        return context
```

### 3.4 분석 모듈

```python
# modules/analysis.py

class ResultAnalysisModule(WrapperModule):
    """결과 분석 모듈"""

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        from result_analyzer import ResultAnalyzer

        analyzer = ResultAnalyzer()
        analysis = analyzer.analyze(
            context['vrp_input'],
            context['vroom_result']
        )

        context['analysis'] = analysis
        context['_analyzed'] = True

        return context


class StatisticsModule(WrapperModule):
    """통계 생성 모듈"""

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        from statistics_generator import StatisticsGenerator

        generator = StatisticsGenerator()
        stats = generator.generate(context['vroom_result'])

        context['statistics'] = stats
        context['_statistics_generated'] = True

        return context


class CostCalculationModule(WrapperModule):
    """비용 계산 모듈"""

    def get_dependencies(self) -> List[str]:
        return ['VROOMCallerModule']

    async def execute(self, context: Dict) -> Dict:
        result = context['vroom_result']
        summary = result.get('summary', {})

        total_distance = summary.get('distance', 0) / 1000  # km
        total_duration = summary.get('duration', 0) / 3600  # hours

        # 비용 계산 (가정)
        fuel_cost = total_distance * 1500  # 1500원/km
        labor_cost = total_duration * 15000  # 15000원/시간
        carbon = total_distance * 0.2  # 0.2kg CO2/km

        context['costs'] = {
            'fuel_cost_krw': int(fuel_cost),
            'labor_cost_krw': int(labor_cost),
            'total_cost_krw': int(fuel_cost + labor_cost),
            'carbon_footprint_kg': round(carbon, 2)
        }
        context['_costs_calculated'] = True

        return context
```

---

## 4. 사용 시나리오

### 시나리오 1: 기본 최적화 (v1.0 호환)

```python
# 최소 구성
pipeline = Pipeline([
    VROOMCallerModule(),
    UnassignedReasonModule()
])

context = {'vrp_input': {...}}
result = await pipeline.execute(context)
```

### 시나리오 2: 전체 기능 (v2.0 풀스택)

```python
# 모든 모듈 활성화
pipeline = Pipeline([
    ValidationModule(),
    NormalizationModule(),
    BusinessRuleModule(),
    WeatherEnrichmentModule(),
    VROOMCallerModule(),
    UnassignedReasonModule(),
    ETAEnrichmentModule(use_realtime=True),
    ResultAnalysisModule(),
    StatisticsModule(),
    CostCalculationModule()
])

context = {
    'vrp_input': {...},
    'business_rules': {...},
    'departure_time': datetime(2024, 1, 23, 8, 0)
}
result = await pipeline.execute(context)
```

### 시나리오 3: 커스텀 조합 (선택적 모듈)

```python
# 실시간 ETA만 필요
pipeline = Pipeline([
    ValidationModule(),
    VROOMCallerModule(),
    ETAEnrichmentModule(use_realtime=True)
])

# 분석 기능만 필요
pipeline = Pipeline([
    VROOMCallerModule(),
    ResultAnalysisModule(),
    StatisticsModule()
])

# 비즈니스 규칙 + 튜닝
pipeline = Pipeline([
    NormalizationModule(),
    BusinessRuleModule(),
    VROOMCallerModule(),
    ConstraintTunerModule()
])
```

### 시나리오 4: 병렬 실행

```python
# 분석/통계/비용을 병렬로
parallel_pipeline = ParallelPipeline([
    ValidationModule(),
    VROOMCallerModule()
])

parallel_groups = [
    # 첫 번째 그룹: 순차 실행
    [ValidationModule(), VROOMCallerModule()],

    # 두 번째 그룹: 병렬 실행 (VROOM 결과 분석)
    [
        UnassignedReasonModule(),
        ResultAnalysisModule(),
        StatisticsModule(),
        CostCalculationModule()
    ],

    # 세 번째 그룹: 순차 실행 (ETA는 API 호출이 필요하므로 나중에)
    [ETAEnrichmentModule(use_realtime=True)]
]

result = await parallel_pipeline.execute_parallel(context, parallel_groups)
```

---

## 5. FastAPI 통합

### 5.1 프리셋 엔드포인트

```python
# main.py

from fastapi import FastAPI
from pipeline import Pipeline
from modules.preprocessing import *
from modules.optimization import *
from modules.enrichment import *
from modules.analysis import *

app = FastAPI()

# 프리셋 1: 기본 (v1.0 호환)
@app.post("/optimize/basic")
async def optimize_basic(vrp_input: Dict):
    """기본 최적화 (미배정 사유만)"""
    pipeline = Pipeline([
        VROOMCallerModule(),
        UnassignedReasonModule()
    ])

    context = {'vrp_input': vrp_input}
    result = await pipeline.execute(context)

    return result['vroom_result']


# 프리셋 2: 스탠다드 (검증 + 정규화 + 분석)
@app.post("/optimize/standard")
async def optimize_standard(
    vrp_input: Dict,
    business_rules: Optional[Dict] = None
):
    """표준 최적화"""
    pipeline = Pipeline([
        ValidationModule(),
        NormalizationModule(),
        BusinessRuleModule(),
        VROOMCallerModule(),
        UnassignedReasonModule(),
        ResultAnalysisModule()
    ])

    context = {
        'vrp_input': vrp_input,
        'business_rules': business_rules
    }
    result = await pipeline.execute(context)

    return {
        'result': result['vroom_result'],
        'analysis': result.get('analysis')
    }


# 프리셋 3: 프리미엄 (모든 기능)
@app.post("/optimize/premium")
async def optimize_premium(
    vrp_input: Dict,
    business_rules: Optional[Dict] = None,
    departure_time: Optional[datetime] = None,
    use_realtime_eta: bool = True
):
    """프리미엄 최적화 (모든 기능)"""
    pipeline = Pipeline([
        ValidationModule(),
        NormalizationModule(),
        BusinessRuleModule(),
        WeatherEnrichmentModule(),
        VROOMCallerModule(),
        UnassignedReasonModule(),
        ETAEnrichmentModule(use_realtime=use_realtime_eta),
        ResultAnalysisModule(),
        StatisticsModule(),
        CostCalculationModule()
    ])

    context = {
        'vrp_input': vrp_input,
        'business_rules': business_rules,
        'departure_time': departure_time or datetime.now()
    }
    result = await pipeline.execute(context)

    return {
        'result': result['vroom_result'],
        'analysis': result.get('analysis'),
        'statistics': result.get('statistics'),
        'costs': result.get('costs'),
        '_metadata': result.get('_pipeline_metadata')
    }


# 프리셋 4: 커스텀 (사용자 정의 파이프라인)
@app.post("/optimize/custom")
async def optimize_custom(
    vrp_input: Dict,
    modules: List[str]  # ["ValidationModule", "VROOMCallerModule", ...]
):
    """사용자가 모듈 선택"""
    available_modules = {
        'ValidationModule': ValidationModule(),
        'NormalizationModule': NormalizationModule(),
        'BusinessRuleModule': BusinessRuleModule(),
        'VROOMCallerModule': VROOMCallerModule(),
        'MultiScenarioModule': MultiScenarioModule(),
        'UnassignedReasonModule': UnassignedReasonModule(),
        'ETAEnrichmentModule': ETAEnrichmentModule(use_realtime=True),
        'ResultAnalysisModule': ResultAnalysisModule(),
        'StatisticsModule': StatisticsModule(),
        'CostCalculationModule': CostCalculationModule()
    }

    selected_modules = [available_modules[name] for name in modules]
    pipeline = Pipeline(selected_modules)

    context = {'vrp_input': vrp_input}
    result = await pipeline.execute(context)

    return result
```

---

## 6. 모듈 재사용 및 조합

### 6.1 MoE (Mixture of Experts) 패턴

```python
# 여러 최적화 전략을 병렬로 실행하고 최선 선택
class MoEOptimizationModule(WrapperModule):
    """복수 최적화 전략 실행 후 최선 선택"""

    async def execute(self, context: Dict) -> Dict:
        strategies = [
            VROOMCallerModule(),
            MultiScenarioModule(),
        ]

        # 병렬 실행
        tasks = [strategy(context.copy()) for strategy in strategies]
        results = await asyncio.gather(*tasks)

        # 최선의 결과 선택 (미배정 최소)
        best_result = min(
            results,
            key=lambda r: len(r['vroom_result'].get('unassigned', []))
        )

        context.update(best_result)
        context['_moe_used'] = True

        return context


# 사용
pipeline = Pipeline([
    ValidationModule(),
    MoEOptimizationModule(),  # 여러 전략 중 최선 자동 선택
    UnassignedReasonModule()
])
```

### 6.2 Conditional 모듈

```python
# 조건부 실행
class ConditionalETAModule(WrapperModule):
    """VIP 고객이 포함된 경우만 실시간 ETA 계산"""

    async def execute(self, context: Dict) -> Dict:
        result = context['vroom_result']

        # VIP 고객 포함 여부 체크
        has_vip = any(
            job.get('customer_type') == 'VIP'
            for route in result.get('routes', [])
            for step in route.get('steps', [])
            if step['type'] == 'job'
            for job in context['vrp_input']['jobs']
            if job['id'] == step.get('id')
        )

        if has_vip:
            eta_module = ETAEnrichmentModule(use_realtime=True)
            context = await eta_module(context)

        return context
```

---

## 7. 모듈 개발 가이드

### 7.1 새 모듈 추가하기

```python
# modules/my_custom_module.py

from module_base import WrapperModule
from typing import Dict, List

class MyCustomModule(WrapperModule):
    """커스텀 모듈 예시"""

    def __init__(self, custom_param: str = "default"):
        super().__init__()
        self.custom_param = custom_param

    def get_dependencies(self) -> List[str]:
        """이 모듈이 의존하는 다른 모듈"""
        return ['VROOMCallerModule']  # VROOM 결과 필요

    def validate_input(self, context: Dict) -> bool:
        """입력 검증"""
        return 'vroom_result' in context

    async def execute(self, context: Dict) -> Dict:
        """실제 로직"""
        result = context['vroom_result']

        # 여기에 커스텀 로직 작성
        # ...

        context['_my_custom_executed'] = True
        return context


# 사용
pipeline = Pipeline([
    VROOMCallerModule(),
    MyCustomModule(custom_param="test")
])
```

### 7.2 모듈 테스트

```python
# tests/test_my_module.py

import pytest
from modules.my_custom_module import MyCustomModule

@pytest.mark.asyncio
async def test_my_custom_module():
    """모듈 단위 테스트"""
    module = MyCustomModule(custom_param="test")

    context = {
        'vrp_input': {...},
        'vroom_result': {...}
    }

    result = await module(context)

    assert result['_my_custom_executed'] == True
```

---

## 8. 요약

| 기능 | Monolithic (v1.0) | Modular (v2.0) |
|-----|------------------|----------------|
| **유연성** | ❌ 고정 | ✅ 자유 조합 |
| **재사용** | ❌ 어려움 | ✅ 쉬움 |
| **병렬화** | ❌ 불가 | ✅ 가능 |
| **테스트** | ⚠️ 통합만 | ✅ 단위+통합 |
| **확장** | ❌ 전체 수정 | ✅ 모듈 추가 |
| **유지보수** | ⚠️ 복잡 | ✅ 간단 |

**핵심**: 모듈화로 MoE처럼 전문 모듈을 조합하여 최적의 결과 도출! 🚀

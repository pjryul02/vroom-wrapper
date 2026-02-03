#!/usr/bin/env python3
"""
PreProcessor - Phase 1 통합 클래스

Phase 1: InputValidator, InputNormalizer, BusinessRuleEngine 통합
Phase 1.5: MatrixBuilder (실시간 교통 정보 기반 시간 매트릭스)
"""

from typing import Dict, Any, Optional
import logging

from .validator import InputValidator
from .normalizer import InputNormalizer
from .business_rules import BusinessRuleEngine
from .matrix_builder import (
    HybridMatrixBuilder,
    create_matrix_builder,
    TrafficProvider,
    MatrixResult
)

logger = logging.getLogger(__name__)


class PreProcessor:
    """전처리 파이프라인 통합"""

    def __init__(
        self,
        enable_validation: bool = True,
        enable_normalization: bool = True,
        enable_business_rules: bool = True,
        # Phase 1.5: 실시간 교통 매트릭스
        enable_traffic_matrix: bool = False,
        traffic_provider: TrafficProvider = TrafficProvider.OSRM,
        traffic_api_key: Optional[str] = None,
        osrm_url: str = "http://localhost:5000"
    ):
        """
        Args:
            enable_validation: 입력 검증 활성화
            enable_normalization: 정규화 활성화
            enable_business_rules: 비즈니스 규칙 활성화
            enable_traffic_matrix: 실시간 교통 매트릭스 활성화
            traffic_provider: 교통 정보 제공자 (tmap, kakao, naver, osrm)
            traffic_api_key: 외부 API 키
            osrm_url: OSRM 서버 URL (거리 계산용)
        """
        self.enable_validation = enable_validation
        self.enable_normalization = enable_normalization
        self.enable_business_rules = enable_business_rules
        self.enable_traffic_matrix = enable_traffic_matrix

        self.validator = InputValidator()
        self.normalizer = InputNormalizer()
        self.business_engine = BusinessRuleEngine()

        # Phase 1.5: 매트릭스 빌더 (활성화된 경우만)
        self.matrix_builder: Optional[HybridMatrixBuilder] = None
        self.last_matrix_result: Optional[MatrixResult] = None

        if enable_traffic_matrix:
            self.matrix_builder = create_matrix_builder(
                provider=traffic_provider,
                api_key=traffic_api_key,
                osrm_url=osrm_url,
                parallel_requests=10,
                use_osrm_distance=True  # 거리는 OSRM, 시간은 외부 API
            )
            logger.info(f"Traffic matrix enabled: {traffic_provider.value}")

    async def process(
        self,
        vrp_input: Dict[str, Any],
        business_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        전처리 파이프라인 실행 (async)

        Args:
            vrp_input: 원본 VRP 입력
            business_rules: 비즈니스 규칙 설정 (옵션)

        Returns:
            전처리된 VRP 입력

        Raises:
            ValueError: 검증 실패 시
        """
        result = vrp_input.copy()
        total_steps = 3 + (1 if self.enable_traffic_matrix else 0)
        current_step = 0

        # 1. 입력 검증
        if self.enable_validation:
            current_step += 1
            logger.info(f"Step {current_step}/{total_steps}: Validating input...")
            try:
                validated = self.validator.validate(result)
                result = validated.dict(exclude_none=True)
                logger.info("✓ Validation passed")
            except Exception as e:
                logger.error(f"✗ Validation failed: {e}")
                raise ValueError(f"Input validation failed: {e}")

        # 2. 정규화
        if self.enable_normalization:
            current_step += 1
            logger.info(f"Step {current_step}/{total_steps}: Normalizing input...")
            result = self.normalizer.normalize(result)
            logger.info("✓ Normalization complete")

        # 3. 비즈니스 규칙 적용
        if self.enable_business_rules:
            current_step += 1
            logger.info(f"Step {current_step}/{total_steps}: Applying business rules...")
            result = self.business_engine.apply_rules(result, business_rules)
            logger.info("✓ Business rules applied")

        # 4. 실시간 교통 매트릭스 (Phase 1.5)
        if self.enable_traffic_matrix and self.matrix_builder:
            current_step += 1
            logger.info(f"Step {current_step}/{total_steps}: Building traffic matrix...")
            try:
                self.last_matrix_result = await self.matrix_builder.build(
                    result,
                    include_in_input=True
                )
                logger.info(f"✓ Traffic matrix built ({self.last_matrix_result.build_time_ms}ms)")
            except Exception as e:
                logger.error(f"✗ Matrix build failed: {e}")
                logger.warning("Continuing without traffic matrix (OSRM fallback)")

        logger.info("Pre-processing complete")
        return result

    def process_sync(
        self,
        vrp_input: Dict[str, Any],
        business_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        동기 버전 (매트릭스 빌드 제외)

        traffic_matrix가 비활성화된 경우 사용
        """
        if self.enable_traffic_matrix:
            raise RuntimeError("Use async process() when traffic_matrix is enabled")

        result = vrp_input.copy()

        if self.enable_validation:
            validated = self.validator.validate(result)
            result = validated.dict(exclude_none=True)

        if self.enable_normalization:
            result = self.normalizer.normalize(result)

        if self.enable_business_rules:
            result = self.business_engine.apply_rules(result, business_rules)

        return result

    def validate_only(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """검증만 수행"""
        validated = self.validator.validate(vrp_input)
        return validated.dict(exclude_none=True)

    def normalize_only(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """정규화만 수행"""
        return self.normalizer.normalize(vrp_input)

    def apply_business_rules_only(
        self,
        vrp_input: Dict[str, Any],
        rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """비즈니스 규칙만 적용"""
        return self.business_engine.apply_rules(vrp_input, rules)

    async def build_matrix_only(
        self,
        vrp_input: Dict[str, Any],
        include_in_input: bool = True
    ) -> Optional[MatrixResult]:
        """
        매트릭스만 빌드 (Phase 1.5)

        Args:
            vrp_input: VRP 입력
            include_in_input: True면 vrp_input에 matrix 필드 추가

        Returns:
            MatrixResult 또는 None (비활성화된 경우)
        """
        if not self.matrix_builder:
            logger.warning("Matrix builder not enabled")
            return None

        result = await self.matrix_builder.build(vrp_input, include_in_input)
        self.last_matrix_result = result
        return result

    def get_matrix_stats(self) -> Optional[Dict[str, Any]]:
        """매트릭스 빌드 통계 조회"""
        if not self.last_matrix_result:
            return None

        return {
            "matrix_size": len(self.last_matrix_result.locations),
            "provider": self.last_matrix_result.provider,
            "build_time_ms": self.last_matrix_result.build_time_ms,
            "cached": self.last_matrix_result.cached,
            "cache_stats": self.matrix_builder.get_cache_stats() if self.matrix_builder else None
        }

    def set_traffic_provider(
        self,
        provider: TrafficProvider,
        api_key: Optional[str] = None,
        osrm_url: str = "http://localhost:5000"
    ):
        """
        실시간 교통 제공자 변경

        Args:
            provider: tmap, kakao, naver, osrm
            api_key: API 키
            osrm_url: OSRM URL
        """
        self.matrix_builder = create_matrix_builder(
            provider=provider,
            api_key=api_key,
            osrm_url=osrm_url
        )
        self.enable_traffic_matrix = True
        logger.info(f"Traffic provider changed to: {provider.value}")

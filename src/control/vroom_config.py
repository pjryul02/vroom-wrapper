#!/usr/bin/env python3
"""
VROOMConfigManager - VROOM 설정 관리

Phase 2.2: 4단계 제어 레벨 (BASIC/STANDARD/PREMIUM/CUSTOM)
"""

from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ControlLevel(str, Enum):
    """제어 레벨"""
    BASIC = "basic"           # 기본 최적화만
    STANDARD = "standard"     # 일반적인 제약조건
    PREMIUM = "premium"       # 고급 최적화 + 다중 시나리오
    CUSTOM = "custom"         # 사용자 정의


class VROOMConfigManager:
    """
    VROOM 설정 관리자

    4단계 제어 레벨 제공:
    - BASIC: 빠른 최적화, 기본 설정
    - STANDARD: 균형잡힌 최적화
    - PREMIUM: 고품질 최적화 (느리지만 최고 품질)
    - CUSTOM: 사용자 정의
    """

    def __init__(self):
        # VROOM 기본 설정
        self.default_config = {
            'exploration_level': 5,
            'timeout': 30000  # 30초
        }

    def get_config(
        self,
        level: ControlLevel = ControlLevel.STANDARD,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        제어 레벨에 따른 VROOM 설정 반환

        Args:
            level: 제어 레벨
            custom_config: 사용자 정의 설정 (CUSTOM 레벨 시)

        Returns:
            VROOM 설정 딕셔너리
        """
        if level == ControlLevel.BASIC:
            return self._get_basic_config()
        elif level == ControlLevel.STANDARD:
            return self._get_standard_config()
        elif level == ControlLevel.PREMIUM:
            return self._get_premium_config()
        elif level == ControlLevel.CUSTOM:
            if custom_config:
                return self._merge_config(self.default_config, custom_config)
            else:
                logger.warning("CUSTOM level requires custom_config, using STANDARD")
                return self._get_standard_config()
        else:
            logger.warning(f"Unknown level {level}, using STANDARD")
            return self._get_standard_config()

    def _get_basic_config(self) -> Dict[str, Any]:
        """
        BASIC 레벨 설정

        - 빠른 최적화 (exploration_level=3)
        - 짧은 타임아웃 (10초)
        - 기본 제약조건만

        사용 사례:
        - 실시간 응답이 중요한 경우
        - 프로토타이핑
        - 대략적인 결과만 필요한 경우
        """
        return {
            'exploration_level': 3,
            'timeout': 10000,  # 10초
            'description': 'BASIC: Fast optimization with minimal exploration'
        }

    def _get_standard_config(self) -> Dict[str, Any]:
        """
        STANDARD 레벨 설정

        - 균형잡힌 최적화 (exploration_level=5)
        - 적절한 타임아웃 (30초)
        - 일반적인 제약조건

        사용 사례:
        - 일반적인 배송 계획
        - 품질과 속도의 균형
        """
        return {
            'exploration_level': 5,
            'timeout': 30000,  # 30초
            'description': 'STANDARD: Balanced optimization'
        }

    def _get_premium_config(self) -> Dict[str, Any]:
        """
        PREMIUM 레벨 설정

        - 고품질 최적화 (exploration_level=8)
        - 긴 타임아웃 (60초)
        - 모든 제약조건 활용

        사용 사례:
        - 중요한 배송 계획
        - 최고 품질의 경로 필요
        - VIP 고객 서비스
        """
        return {
            'exploration_level': 8,
            'timeout': 60000,  # 60초
            'description': 'PREMIUM: High-quality optimization with extensive exploration'
        }

    def _merge_config(
        self,
        base_config: Dict[str, Any],
        custom_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """사용자 정의 설정 병합"""
        merged = base_config.copy()
        merged.update(custom_config)
        merged['description'] = 'CUSTOM: User-defined configuration'
        return merged

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        설정 유효성 검증

        Args:
            config: VROOM 설정

        Returns:
            유효하면 True
        """
        # exploration_level 범위 체크
        if 'exploration_level' in config:
            level = config['exploration_level']
            if not (0 <= level <= 10):
                logger.error(f"Invalid exploration_level: {level} (must be 0-10)")
                return False

        # timeout 범위 체크
        if 'timeout' in config:
            timeout = config['timeout']
            if timeout < 1000:
                logger.warning(f"Very short timeout: {timeout}ms")
            if timeout > 300000:  # 5분
                logger.warning(f"Very long timeout: {timeout}ms")

        return True

    def tune_for_problem_size(
        self,
        config: Dict[str, Any],
        num_jobs: int,
        num_vehicles: int
    ) -> Dict[str, Any]:
        """
        문제 크기에 따라 설정 자동 조정

        Args:
            config: 기본 설정
            num_jobs: 작업 수
            num_vehicles: 차량 수

        Returns:
            조정된 설정
        """
        tuned = config.copy()

        # 작업 수가 많으면 exploration_level 낮춤 (속도 우선)
        if num_jobs > 100:
            original_level = tuned.get('exploration_level', 5)
            tuned['exploration_level'] = max(3, original_level - 2)
            logger.info(
                f"Large problem ({num_jobs} jobs), "
                f"reduced exploration_level to {tuned['exploration_level']}"
            )

        # 작업 수가 매우 많으면 타임아웃 증가
        if num_jobs > 200:
            original_timeout = tuned.get('timeout', 30000)
            tuned['timeout'] = min(120000, int(original_timeout * 1.5))
            logger.info(
                f"Very large problem ({num_jobs} jobs), "
                f"increased timeout to {tuned['timeout']}ms"
            )

        # 차량 대비 작업 비율이 높으면 (배정이 어려움)
        job_vehicle_ratio = num_jobs / num_vehicles if num_vehicles > 0 else 0
        if job_vehicle_ratio > 20:
            original_level = tuned.get('exploration_level', 5)
            tuned['exploration_level'] = min(8, original_level + 1)
            logger.info(
                f"High job/vehicle ratio ({job_vehicle_ratio:.1f}), "
                f"increased exploration_level to {tuned['exploration_level']}"
            )

        return tuned

    def get_config_for_priority_jobs(
        self,
        base_config: Dict[str, Any],
        has_vip: bool = False,
        has_urgent: bool = False
    ) -> Dict[str, Any]:
        """
        VIP/긴급 작업이 있을 때 설정 조정

        Args:
            base_config: 기본 설정
            has_vip: VIP 작업 포함 여부
            has_urgent: 긴급 작업 포함 여부

        Returns:
            조정된 설정
        """
        config = base_config.copy()

        # VIP 또는 긴급 작업이 있으면 품질 우선
        if has_vip or has_urgent:
            original_level = config.get('exploration_level', 5)
            config['exploration_level'] = min(8, original_level + 2)
            logger.info(
                f"Priority jobs detected, "
                f"increased exploration_level to {config['exploration_level']}"
            )

        return config

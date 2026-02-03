#!/usr/bin/env python3
"""
BusinessRuleEngine - 비즈니스 규칙 적용

Phase 1.2.3: VIP/긴급/지역 제약 등 비즈니스 규칙을 VROOM 제약조건으로 변환
"""

from typing import Dict, List, Any, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Priority(Enum):
    """우선순위 레벨"""
    VIP = 100
    URGENT = 80
    HIGH = 60
    NORMAL = 0
    LOW = -20


class BusinessRuleEngine:
    """비즈니스 규칙 엔진"""

    def __init__(self):
        # VIP 스킬 ID (10000번대)
        self.VIP_SKILL = 10000

        # 긴급 스킬 ID (10001번)
        self.URGENT_SKILL = 10001

        # 지역별 스킬 ID (20000번대)
        self.REGION_SKILL_BASE = 20000

        # 알려진 지역 매핑
        self.region_mapping = {
            'seoul': 20000,
            'busan': 20001,
            'incheon': 20002,
            'daegu': 20003,
            'daejeon': 20004,
            'gwangju': 20005,
            'ulsan': 20006,
        }

    def apply_rules(
        self,
        vrp_input: Dict[str, Any],
        rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        비즈니스 규칙 적용

        Args:
            vrp_input: 정규화된 VRP 입력
            rules: 적용할 규칙 (None이면 자동 탐지)

        Returns:
            규칙이 적용된 VRP 입력
        """
        result = vrp_input.copy()

        # 기본 규칙이 없으면 자동 탐지
        if rules is None:
            rules = self._detect_rules(vrp_input)

        # 1. VIP 규칙 적용
        if rules.get('enable_vip', True):
            result = self._apply_vip_rules(result)

        # 2. 긴급 규칙 적용
        if rules.get('enable_urgent', True):
            result = self._apply_urgent_rules(result)

        # 3. 지역 제약 적용
        if rules.get('enable_region_constraints', False):
            result = self._apply_region_constraints(result, rules)

        # 4. 시간대별 우선순위 적용
        if rules.get('enable_time_priority', False):
            result = self._apply_time_priority(result, rules)

        # 5. 용량 최적화 규칙
        if rules.get('enable_capacity_optimization', False):
            result = self._optimize_capacity(result)

        return result

    def _detect_rules(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        입력 데이터에서 자동으로 규칙 탐지

        - 'vip', 'urgent' 같은 키워드를 description에서 찾기
        - priority 값 분석
        - region, area 정보 탐지
        """
        rules = {
            'enable_vip': False,
            'enable_urgent': False,
            'enable_region_constraints': False,
            'enable_time_priority': False,
            'enable_capacity_optimization': False
        }

        # Job description 분석
        for job in vrp_input.get('jobs', []):
            desc = job.get('description', '').lower()

            if 'vip' in desc:
                rules['enable_vip'] = True
            if 'urgent' in desc or 'emergency' in desc:
                rules['enable_urgent'] = True
            if 'region' in desc or 'area' in desc:
                rules['enable_region_constraints'] = True

            # priority 값이 설정되어 있으면
            if job.get('priority', 0) > 0:
                rules['enable_time_priority'] = True

        logger.info(f"Auto-detected rules: {rules}")
        return rules

    def _apply_vip_rules(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        VIP 규칙 적용

        - VIP 작업 탐지 (description에 'vip' 또는 priority >= 90)
        - VIP 스킬(10000) 부여
        - VIP 전용 차량 지정 또는 모든 차량에 VIP 스킬 추가
        """
        result = vrp_input.copy()

        vip_jobs: Set[int] = set()

        # VIP 작업 탐지
        for job in result.get('jobs', []):
            is_vip = False

            # description에 'vip' 포함
            desc = job.get('description', '').lower()
            if 'vip' in desc:
                is_vip = True

            # priority >= 90
            if job.get('priority', 0) >= 90:
                is_vip = True

            if is_vip:
                # VIP 스킬 추가
                if 'skills' not in job:
                    job['skills'] = []

                if self.VIP_SKILL not in job['skills']:
                    job['skills'].append(self.VIP_SKILL)

                # priority 최대치로 설정
                job['priority'] = Priority.VIP.value

                vip_jobs.add(job['id'])

                logger.info(f"Job {job['id']} marked as VIP")

        # VIP 작업이 있으면 차량에도 VIP 스킬 추가
        if vip_jobs:
            for vehicle in result.get('vehicles', []):
                # 모든 차량이 VIP 처리 가능하도록 설정
                # (특정 차량만 VIP 전용으로 하려면 별도 로직 필요)
                if 'skills' not in vehicle:
                    vehicle['skills'] = []

                if self.VIP_SKILL not in vehicle['skills']:
                    vehicle['skills'].append(self.VIP_SKILL)

            logger.info(f"Added VIP skill to all vehicles (VIP jobs: {len(vip_jobs)})")

        return result

    def _apply_urgent_rules(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        긴급 규칙 적용

        - 긴급 작업 탐지 (description에 'urgent', 'emergency' 또는 priority >= 70)
        - 긴급 스킬(10001) 부여
        - 시간창을 더 엄격하게 조정
        """
        result = vrp_input.copy()

        urgent_jobs: Set[int] = set()

        for job in result.get('jobs', []):
            is_urgent = False

            # description에 'urgent' 또는 'emergency' 포함
            desc = job.get('description', '').lower()
            if 'urgent' in desc or 'emergency' in desc:
                is_urgent = True

            # priority >= 70
            if job.get('priority', 0) >= 70:
                is_urgent = True

            if is_urgent:
                # 긴급 스킬 추가
                if 'skills' not in job:
                    job['skills'] = []

                if self.URGENT_SKILL not in job['skills']:
                    job['skills'].append(self.URGENT_SKILL)

                # priority 높게 설정
                if job.get('priority', 0) < Priority.URGENT.value:
                    job['priority'] = Priority.URGENT.value

                urgent_jobs.add(job['id'])

                logger.info(f"Job {job['id']} marked as URGENT")

        # 긴급 작업이 있으면 차량에도 긴급 스킬 추가
        if urgent_jobs:
            for vehicle in result.get('vehicles', []):
                if 'skills' not in vehicle:
                    vehicle['skills'] = []

                if self.URGENT_SKILL not in vehicle['skills']:
                    vehicle['skills'].append(self.URGENT_SKILL)

            logger.info(f"Added URGENT skill to all vehicles (urgent jobs: {len(urgent_jobs)})")

        return result

    def _apply_region_constraints(
        self,
        vrp_input: Dict[str, Any],
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        지역 제약 적용

        - 작업을 지역별로 분류
        - 각 지역에 고유 스킬 부여
        - 차량을 특정 지역에만 할당

        Example:
            rules = {
                'region_assignment': {
                    'seoul': [1, 2],  # 차량 1, 2는 서울 담당
                    'busan': [3, 4]   # 차량 3, 4는 부산 담당
                }
            }
        """
        result = vrp_input.copy()

        region_assignment = rules.get('region_assignment', {})
        if not region_assignment:
            logger.warning("Region constraints enabled but no region_assignment provided")
            return result

        # 1. 작업에 지역 스킬 부여
        for job in result.get('jobs', []):
            job_region = self._detect_job_region(job)

            if job_region and job_region in self.region_mapping:
                region_skill = self.region_mapping[job_region]

                if 'skills' not in job:
                    job['skills'] = []

                if region_skill not in job['skills']:
                    job['skills'].append(region_skill)

                logger.debug(f"Job {job['id']} assigned to region '{job_region}' (skill {region_skill})")

        # 2. 차량에 담당 지역 스킬 부여
        for region, vehicle_ids in region_assignment.items():
            if region not in self.region_mapping:
                logger.warning(f"Unknown region: {region}")
                continue

            region_skill = self.region_mapping[region]

            for vehicle in result.get('vehicles', []):
                if vehicle['id'] in vehicle_ids:
                    if 'skills' not in vehicle:
                        vehicle['skills'] = []

                    if region_skill not in vehicle['skills']:
                        vehicle['skills'].append(region_skill)

                    logger.info(f"Vehicle {vehicle['id']} assigned to region '{region}' (skill {region_skill})")

        return result

    def _detect_job_region(self, job: Dict[str, Any]) -> Optional[str]:
        """
        작업의 지역 탐지

        - description에서 지역명 추출
        - 또는 좌표 기반 지역 판별 (TODO: geocoding)
        """
        desc = job.get('description', '').lower()

        for region in self.region_mapping.keys():
            if region in desc:
                return region

        # TODO: 좌표 기반 지역 판별
        # location = job.get('location')
        # return self._geocode_region(location)

        return None

    def _apply_time_priority(
        self,
        vrp_input: Dict[str, Any],
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        시간대별 우선순위 적용

        오전 작업은 우선순위 높게, 오후 작업은 낮게
        """
        result = vrp_input.copy()

        morning_cutoff = rules.get('morning_cutoff', 43200)  # 12:00 (정오)

        for job in result.get('jobs', []):
            time_windows = job.get('time_windows')

            if time_windows and len(time_windows) > 0:
                # 첫 번째 시간창의 시작 시간
                first_tw_start = time_windows[0][0]

                if first_tw_start < morning_cutoff:
                    # 오전 작업: 우선순위 +10
                    job['priority'] = job.get('priority', 0) + 10
                    logger.debug(f"Job {job['id']} is morning task, priority boosted")

        return result

    def _optimize_capacity(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        용량 최적화

        - 작업의 실제 요구량 분석
        - 차량 용량을 최적화
        """
        result = vrp_input.copy()

        # 전체 요구량 계산
        total_demand = [0] * len(result['vehicles'][0].get('capacity', [1000]))

        for job in result.get('jobs', []):
            delivery = job.get('delivery', [0])
            for i, amount in enumerate(delivery):
                if i < len(total_demand):
                    total_demand[i] += amount

        logger.info(f"Total demand: {total_demand}")

        # 차량 용량 자동 조정 (옵션)
        # TODO: 필요시 구현

        return result

    def apply_custom_rule(
        self,
        vrp_input: Dict[str, Any],
        rule_name: str,
        rule_fn: callable
    ) -> Dict[str, Any]:
        """
        사용자 정의 규칙 적용

        Args:
            vrp_input: VRP 입력
            rule_name: 규칙 이름
            rule_fn: 규칙 함수 (vrp_input -> vrp_input)

        Returns:
            규칙이 적용된 VRP 입력
        """
        try:
            logger.info(f"Applying custom rule: {rule_name}")
            result = rule_fn(vrp_input)
            return result
        except Exception as e:
            logger.error(f"Custom rule '{rule_name}' failed: {e}")
            return vrp_input

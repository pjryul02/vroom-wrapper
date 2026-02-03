#!/usr/bin/env python3
"""
Unit tests for Phase 1: Pre-processing layer
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from preprocessing import (
    InputValidator,
    InputNormalizer,
    BusinessRuleEngine,
    PreProcessor,
    Priority
)


class TestInputValidator:
    """InputValidator 테스트"""

    def test_valid_input(self):
        """정상 입력 검증"""
        valid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        result = InputValidator.validate(valid_input)
        assert result is not None
        assert len(result.vehicles) == 1
        assert len(result.jobs) == 1

    def test_invalid_longitude(self):
        """잘못된 경도 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [200, 37.5]}  # lon=200 (범위 초과)
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        with pytest.raises(ValueError, match="Longitude.*out of range"):
            InputValidator.validate(invalid_input)

    def test_invalid_latitude(self):
        """잘못된 위도 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 100]}  # lat=100 (범위 초과)
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        with pytest.raises(ValueError, match="Latitude.*out of range"):
            InputValidator.validate(invalid_input)

    def test_no_vehicles(self):
        """차량 없음 거부"""
        invalid_input = {
            "vehicles": [],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        with pytest.raises(ValueError, match="At least one vehicle required"):
            InputValidator.validate(invalid_input)

    def test_no_jobs_or_shipments(self):
        """작업 없음 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ]
        }

        with pytest.raises(ValueError, match="Either jobs or shipments required"):
            InputValidator.validate(invalid_input)

    def test_duplicate_vehicle_ids(self):
        """차량 ID 중복 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]},
                {"id": 1, "start": [127.1, 37.6]}  # 중복 ID
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        with pytest.raises(ValueError, match="Duplicate vehicle IDs"):
            InputValidator.validate(invalid_input)

    def test_duplicate_job_ids(self):
        """작업 ID 중복 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]},
                {"id": 1, "location": [127.2, 37.7]}  # 중복 ID
            ]
        }

        with pytest.raises(ValueError, match="Duplicate job IDs"):
            InputValidator.validate(invalid_input)

    def test_invalid_time_window(self):
        """잘못된 시간창 거부"""
        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "time_windows": [[1000, 500]]  # end < start
                }
            ]
        }

        with pytest.raises(ValueError, match="Time window end.*must be >= start"):
            InputValidator.validate(invalid_input)


class TestInputNormalizer:
    """InputNormalizer 테스트"""

    def test_normalize_vehicle_end(self):
        """차량 end 기본값 설정"""
        normalizer = InputNormalizer()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}  # end 없음
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        result = normalizer.normalize(input_data)

        # end가 start와 동일하게 설정되어야 함
        assert result['vehicles'][0]['end'] == [127.0, 37.5]

    def test_normalize_job_service(self):
        """작업 service 기본값 설정"""
        normalizer = InputNormalizer()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}  # service 없음
            ]
        }

        result = normalizer.normalize(input_data)

        # service 기본값 300초
        assert result['jobs'][0]['service'] == 300

    def test_normalize_time_base(self):
        """절대 시간 → 상대 시간 변환"""
        normalizer = InputNormalizer()

        input_data = {
            "time_base": "2026-01-24T09:00:00",
            "vehicles": [
                {
                    "id": 1,
                    "start": [127.0, 37.5],
                    "time_window": ["2026-01-24T09:00:00", "2026-01-24T18:00:00"]
                }
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "time_windows": [["2026-01-24T10:00:00", "2026-01-24T12:00:00"]]
                }
            ]
        }

        result = normalizer.normalize(input_data)

        # time_base 제거됨
        assert 'time_base' not in result

        # 차량 시간창: 0초 ~ 32400초 (9시간)
        assert result['vehicles'][0]['time_window'] == [0, 32400]

        # 작업 시간창: 3600초 ~ 10800초 (1~3시간)
        assert result['jobs'][0]['time_windows'] == [[3600, 10800]]

    def test_round_coordinates(self):
        """좌표 반올림"""
        normalizer = InputNormalizer()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.123456789, 37.987654321]}
            ],
            "jobs": [
                {"id": 1, "location": [127.111111111, 37.222222222]}
            ]
        }

        result = normalizer.round_coordinates(input_data, precision=6)

        # 소수점 6자리로 반올림
        assert result['vehicles'][0]['start'] == [127.123457, 37.987654]
        assert result['jobs'][0]['location'] == [127.111111, 37.222222]


class TestBusinessRuleEngine:
    """BusinessRuleEngine 테스트"""

    def test_vip_detection(self):
        """VIP 작업 탐지"""
        engine = BusinessRuleEngine()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "description": "VIP customer delivery"
                }
            ]
        }

        result = engine.apply_rules(input_data)

        # VIP 스킬(10000) 추가됨
        assert 10000 in result['jobs'][0]['skills']
        assert result['jobs'][0]['priority'] == Priority.VIP.value

        # 차량에도 VIP 스킬 추가됨
        assert 10000 in result['vehicles'][0]['skills']

    def test_urgent_detection(self):
        """긴급 작업 탐지"""
        engine = BusinessRuleEngine()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "description": "Urgent delivery"
                }
            ]
        }

        result = engine.apply_rules(input_data)

        # 긴급 스킬(10001) 추가됨
        assert 10001 in result['jobs'][0]['skills']
        assert result['jobs'][0]['priority'] == Priority.URGENT.value

        # 차량에도 긴급 스킬 추가됨
        assert 10001 in result['vehicles'][0]['skills']

    def test_priority_threshold(self):
        """우선순위 임계값 탐지"""
        engine = BusinessRuleEngine()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "priority": 95  # VIP 임계값 초과
                }
            ]
        }

        # VIP 규칙을 명시적으로 활성화
        rules = {'enable_vip': True}
        result = engine.apply_rules(input_data, rules)

        # VIP로 인식됨
        assert 'skills' in result['jobs'][0]
        assert 10000 in result['jobs'][0]['skills']
        assert result['jobs'][0]['priority'] == Priority.VIP.value


class TestPreProcessor:
    """PreProcessor 통합 테스트"""

    def test_full_pipeline(self):
        """전체 파이프라인 테스트"""
        preprocessor = PreProcessor()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {
                    "id": 1,
                    "location": [127.1, 37.6],
                    "description": "VIP customer"
                }
            ]
        }

        result = preprocessor.process(input_data)

        # 검증 통과
        assert 'vehicles' in result
        assert 'jobs' in result

        # 정규화 적용 (end 추가됨)
        assert result['vehicles'][0]['end'] == [127.0, 37.5]

        # 비즈니스 규칙 적용 (VIP 스킬 추가됨)
        assert 10000 in result['jobs'][0]['skills']

    def test_validation_only(self):
        """검증만 수행"""
        preprocessor = PreProcessor()

        input_data = {
            "vehicles": [
                {"id": 1, "start": [127.0, 37.5]}
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        result = preprocessor.validate_only(input_data)
        assert result is not None

    def test_invalid_input_rejected(self):
        """잘못된 입력 거부"""
        preprocessor = PreProcessor()

        invalid_input = {
            "vehicles": [
                {"id": 1, "start": [200, 37.5]}  # 잘못된 경도
            ],
            "jobs": [
                {"id": 1, "location": [127.1, 37.6]}
            ]
        }

        with pytest.raises(ValueError):
            preprocessor.process(invalid_input)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
HGLIS Skill 인코딩 (C4, C7, C8, 소파)

명세서 11.3 Skill 코드 체계:
  1~4:     C4 기능도 계층 (1=C, 2=B, 3=A, 4=S)
  100~199: C7 신제품 (동적 할당)
  300~399: C8 미결 이력 모델 (동적 할당)
  500:     소파 전용
  2001~:   합배차 그룹 (Phase 3)
"""

import logging
from typing import List, Dict, Set, Tuple
from .models import HglisJob, HglisVehicle, METRO_REGIONS, LOCAL_REGIONS

logger = logging.getLogger(__name__)

# C4: 기능도 → skill ID (계층적)
GRADE_SKILL: Dict[str, int] = {"C": 1, "B": 2, "A": 3, "S": 4}

# 기사 기능도 → 처리 가능한 skill 목록 (자기 등급 이하 전부)
GRADE_SKILLS_MAP: Dict[str, List[int]] = {
    "S": [1, 2, 3, 4],
    "A": [1, 2, 3],
    "B": [1, 2],
    "C": [1],
}

# 스킬 ID 베이스
C7_BASE = 100   # 신제품
C8_BASE = 300   # 미결 이력
SOFA_SKILL = 500


class SkillEncodeResult:
    """스킬 인코딩 결과"""

    def __init__(self):
        # job_id → 부여된 skill 목록
        self.job_skills: Dict[int, List[int]] = {}
        # vehicle_id → 부여된 skill 목록
        self.vehicle_skills: Dict[int, List[int]] = {}
        # 역매핑: skill_id → 의미 설명
        self.skill_legend: Dict[int, str] = {
            1: "기능도 C", 2: "기능도 B", 3: "기능도 A", 4: "기능도 S",
            SOFA_SKILL: "소파 전용",
        }

    def to_dict(self) -> Dict:
        return {
            "job_skills": self.job_skills,
            "vehicle_skills": self.vehicle_skills,
            "skill_legend": self.skill_legend,
        }


def encode_skills(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
) -> SkillEncodeResult:
    """
    전체 스킬 인코딩 실행.

    1) C4 기능도 (하드 — 계층적)
    2) C7 신제품 (하드 — 동적)
    3) C8 미결 이력 (하드 — 동적, 역방향)
    4) 소파 전용 (하드 — 고정 500)
    """
    result = SkillEncodeResult()

    # 초기화
    for j in jobs:
        result.job_skills[j.id] = []
    for v in vehicles:
        result.vehicle_skills[v.id] = []

    _encode_c4_grade(jobs, vehicles, result)
    _encode_c7_new_product(jobs, vehicles, result)
    _encode_c8_avoid_model(jobs, vehicles, result)
    _encode_sofa(jobs, vehicles, result)

    # 로그
    total_job_skills = sum(len(s) for s in result.job_skills.values())
    total_veh_skills = sum(len(s) for s in result.vehicle_skills.values())
    logger.info(
        f"스킬 인코딩 완료: 오더 {len(jobs)}건 (총 {total_job_skills}개 skill), "
        f"기사 {len(vehicles)}명 (총 {total_veh_skills}개 skill), "
        f"범례 {len(result.skill_legend)}항목"
    )

    return result


def _encode_c4_grade(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
    result: SkillEncodeResult,
):
    """C4 기능도: 오더에 최고 필요등급 1개, 기사에 자기 이하 전부"""
    for j in jobs:
        max_grade = max(
            (p.required_grade for p in j.products),
            key=lambda g: GRADE_SKILL[g]
        )
        skill_id = GRADE_SKILL[max_grade]
        result.job_skills[j.id].append(skill_id)

    for v in vehicles:
        skills = GRADE_SKILLS_MAP.get(v.skill_grade, [1])
        result.vehicle_skills[v.id].extend(skills)


def _encode_c7_new_product(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
    result: SkillEncodeResult,
):
    """
    C7 신제품:
    - 전체 신제품 모델코드 수집 → 정렬 → 100, 101, ... 매핑
    - 오더: 포함된 신제품의 skill 부여
    - 기사: new_product_restricted=False 이면 모든 신제품 skill 부여
    """
    # 1. 전체 신제품 모델코드 수집
    new_product_models: Set[str] = set()
    for j in jobs:
        for p in j.products:
            if p.is_new_product:
                new_product_models.add(p.model_code)

    if not new_product_models:
        return

    # 2. 정렬 후 skill ID 할당
    sorted_models = sorted(new_product_models)
    c7_map: Dict[str, int] = {}
    for i, model in enumerate(sorted_models):
        skill_id = C7_BASE + i
        c7_map[model] = skill_id
        result.skill_legend[skill_id] = f"C7 신제품: {model}"

    logger.info(f"C7 신제품 {len(c7_map)}종: {c7_map}")

    # 3. 오더에 skill 부여
    for j in jobs:
        for p in j.products:
            if p.is_new_product and p.model_code in c7_map:
                skill_id = c7_map[p.model_code]
                if skill_id not in result.job_skills[j.id]:
                    result.job_skills[j.id].append(skill_id)

    # 4. 기사에 skill 부여 (제한 아닌 기사만)
    all_c7_skills = list(c7_map.values())
    for v in vehicles:
        if not v.new_product_restricted:
            result.vehicle_skills[v.id].extend(all_c7_skills)


def _encode_c8_avoid_model(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
    result: SkillEncodeResult,
):
    """
    C8 미결 이력:
    - 전체 회피 모델코드 수집 → 정렬 → 300, 301, ... 매핑
    - 오더: 해당 모델 포함 시 skill 부여
    - 기사: avoid_models에 **없는** 모델의 skill만 부여 (역방향)
    """
    # 1. 전체 회피 모델코드 수집
    all_avoid_models: Set[str] = set()
    for v in vehicles:
        for am in v.avoid_models:
            all_avoid_models.add(am.model)

    if not all_avoid_models:
        return

    # 2. 정렬 후 skill ID 할당
    sorted_models = sorted(all_avoid_models)
    c8_map: Dict[str, int] = {}
    for i, model in enumerate(sorted_models):
        skill_id = C8_BASE + i
        c8_map[model] = skill_id
        result.skill_legend[skill_id] = f"C8 회피모델: {model}"

    logger.info(f"C8 회피모델 {len(c8_map)}종: {c8_map}")

    # 3. 오더에 skill 부여 (제품 모델이 회피 목록에 있으면)
    for j in jobs:
        for p in j.products:
            if p.model_code in c8_map:
                skill_id = c8_map[p.model_code]
                if skill_id not in result.job_skills[j.id]:
                    result.job_skills[j.id].append(skill_id)

    # 4. 기사에 skill 부여 (역방향: 회피 안 하는 모델만)
    all_c8_skills = set(c8_map.values())
    for v in vehicles:
        driver_avoid = {am.model for am in v.avoid_models}
        for model, skill_id in c8_map.items():
            if model not in driver_avoid:
                result.vehicle_skills[v.id].append(skill_id)


def _encode_sofa(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
    result: SkillEncodeResult,
):
    """
    소파 전용:
    - 소파 오더에 skill 500 부여
    - W1 기사 및 지방 기사에 skill 500 부여
    - Y1/Y2/Y3/Y5 기사에는 미부여
    """
    has_sofa = False
    for j in jobs:
        if any(p.is_sofa for p in j.products):
            result.job_skills[j.id].append(SOFA_SKILL)
            has_sofa = True

    if not has_sofa:
        return

    for v in vehicles:
        if v.region_code == "W1" or v.region_code in LOCAL_REGIONS:
            result.vehicle_skills[v.id].append(SOFA_SKILL)

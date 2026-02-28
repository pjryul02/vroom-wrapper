"""
C1 합배차 처리

2인 오더 처리:
1. 우선 2인팀(crew.size=2) 기사에 배정 시도
2. 2인팀 부족 시 → 합배차 가능(is_filler=True) 1인 기사 2명 조합
3. job 복제: primary(기능도 skill + 그룹 skill, CBM, fee 60%)
              secondary(그룹 skill만, CBM 0, fee 40%)

합배차 그룹 skill: 2001~ (동적 할당)
"""

import logging
from typing import List, Dict, Tuple, Optional
from .models import HglisJob, HglisVehicle

logger = logging.getLogger(__name__)

JOINT_SKILL_BASE = 2001


class JointDispatchResult:
    """합배차 처리 결과"""

    def __init__(self):
        # 확장된 job/vehicle 목록 (복제 포함)
        self.jobs: List[HglisJob] = []
        self.vehicles: List[HglisVehicle] = []
        # 합배차 매핑: group_id → {"order_id", "primary_job_id", "secondary_job_id", "skill_id"}
        self.joint_groups: Dict[int, Dict] = {}
        # 원본 job_id → 합배차 여부
        self.is_joint: Dict[int, bool] = {}
        # 추가 skill 범례
        self.skill_legend: Dict[int, str] = {}
        # 합배차 안 된 2인 오더 (2인팀/합배차 기사 부족)
        self.unresolved_two_person: List[HglisJob] = []


def process_joint_dispatch(
    jobs: List[HglisJob],
    vehicles: List[HglisVehicle],
) -> JointDispatchResult:
    """
    합배차 전처리.

    2인 오더를 찾아서 job 복제 + 그룹 skill 할당.
    1인 오더와 2인팀 기사는 그대로 통과.
    """
    result = JointDispatchResult()

    two_person_jobs = [j for j in jobs if j.constraints.crew_type == "2인"]
    other_jobs = [j for j in jobs if j.constraints.crew_type != "2인"]

    # 2인팀 기사 수 확인
    two_person_vehicles = [v for v in vehicles if v.crew.size == 2]
    filler_vehicles = [v for v in vehicles if v.crew.size == 1 and v.crew.is_filler]

    if not two_person_jobs:
        # 합배차 대상 없음
        result.jobs = list(jobs)
        result.vehicles = list(vehicles)
        for j in jobs:
            result.is_joint[j.id] = False
        return result

    logger.info(
        f"합배차 대상: 2인오더 {len(two_person_jobs)}건, "
        f"2인팀 {len(two_person_vehicles)}명, 합배차가능 1인 {len(filler_vehicles)}명"
    )

    # 1인 오더는 그대로
    result.jobs.extend(other_jobs)
    for j in other_jobs:
        result.is_joint[j.id] = False

    # 2인 오더 처리
    # 2인팀 기사가 충분하면 → job 복제 불필요, 그대로 할당 (crew.size=2가 매칭)
    # 2인팀 부족 시 → 합배차 1인 기사 쌍으로 job 복제
    remaining_two_person = len(two_person_jobs) - len(two_person_vehicles)

    group_id = 0
    used_id_max = max((j.id for j in jobs), default=0)
    secondary_id_base = used_id_max + 10000  # 충분히 큰 offset

    for i, job in enumerate(two_person_jobs):
        if i < len(two_person_vehicles):
            # 2인팀 기사가 처리 가능 → 복제 불필요
            result.jobs.append(job)
            result.is_joint[job.id] = False
        elif len(filler_vehicles) >= 2:
            # 합배차 필요: job 복제
            group_id += 1
            skill_id = JOINT_SKILL_BASE + group_id - 1

            primary_job = job  # 원본이 primary
            secondary_job_id = secondary_id_base + group_id

            # secondary job은 모델 수준에서 복제해야 하는데,
            # Pydantic 모델은 immutable이므로 딕셔너리 단에서 처리하는 게 나음.
            # → skill_encoder와 vroom_assembler에서 joint 정보를 참조

            result.jobs.append(primary_job)
            result.is_joint[primary_job.id] = True

            result.joint_groups[group_id] = {
                "order_id": job.order_id,
                "primary_job_id": primary_job.id,
                "secondary_job_id": secondary_job_id,
                "skill_id": skill_id,
                "fee_split": (0.6, 0.4),
            }

            result.skill_legend[skill_id] = f"합배차 그룹: {job.order_id}"
            logger.info(f"합배차 그룹 {group_id}: {job.order_id} (skill={skill_id})")
        else:
            # 합배차 기사도 부족 → 미해결
            result.jobs.append(job)
            result.is_joint[job.id] = False
            result.unresolved_two_person.append(job)
            logger.warning(f"합배차 불가: {job.order_id} — 2인팀/합배차 기사 부족")

    result.vehicles = list(vehicles)

    logger.info(
        f"합배차 처리 완료: {len(result.joint_groups)}개 그룹 생성, "
        f"미해결 {len(result.unresolved_two_person)}건"
    )

    return result


def apply_joint_skills(
    job_skills: Dict[int, List[int]],
    vehicle_skills: Dict[int, List[int]],
    joint_result: JointDispatchResult,
    vehicles: List[HglisVehicle],
):
    """
    합배차 그룹 skill을 job/vehicle skill에 추가.

    - primary job: 기존 skill + 그룹 skill
    - secondary job: 그룹 skill만 (기능도 skill 제거)
    - 합배차 가능 기사: 그룹 skill 부여
    """
    if not joint_result.joint_groups:
        return

    filler_vehicle_ids = {v.id for v in vehicles if v.crew.size == 1 and v.crew.is_filler}

    for group_id, group in joint_result.joint_groups.items():
        skill_id = group["skill_id"]
        primary_id = group["primary_job_id"]
        secondary_id = group["secondary_job_id"]

        # primary job에 그룹 skill 추가
        if primary_id in job_skills:
            job_skills[primary_id].append(skill_id)

        # secondary job: 그룹 skill만
        job_skills[secondary_id] = [skill_id]

        # 합배차 가능 기사에 그룹 skill 부여
        for vid in filler_vehicle_ids:
            if vid in vehicle_skills:
                vehicle_skills[vid].append(skill_id)


def build_secondary_vroom_jobs(
    joint_result: JointDispatchResult,
    job_skills: Dict[int, List[int]],
    base_date: str,
) -> List[Dict]:
    """
    합배차 secondary job들의 VROOM job dict 생성.

    secondary 특성:
    - 기능도 skill 없음 (그룹 skill만)
    - CBM = 0
    - fee 40%
    - 동일 time_window, 동일 location
    """
    from .time_converter import convert_job_time_windows, calc_service_seconds

    secondary_jobs = []
    job_map = {j.id: j for j in joint_result.jobs}

    for group_id, group in joint_result.joint_groups.items():
        primary_job = job_map.get(group["primary_job_id"])
        if not primary_job:
            continue

        secondary_id = group["secondary_job_id"]
        skills = job_skills.get(secondary_id, [group["skill_id"]])

        secondary_jobs.append({
            "id": secondary_id,
            "description": f"{primary_job.order_id}_보조",
            "location": primary_job.location,
            "service": calc_service_seconds(primary_job),
            "delivery": [0, 0, 0],  # CBM 0
            "skills": skills,
            "time_windows": convert_job_time_windows(primary_job, base_date),
            "priority": 90,  # 높은 우선순위 (합배차는 반드시 배정되어야)
        })

    return secondary_jobs


def merge_joint_results(
    results: List[Dict],
    joint_result: JointDispatchResult,
) -> List[Dict]:
    """
    합배차 결과 후처리.

    VROOM 결과에서 primary/secondary를 매칭하여
    동일 오더의 두 기사 정보를 합친다.
    """
    if not joint_result.joint_groups:
        return results

    secondary_ids = {g["secondary_job_id"] for g in joint_result.joint_groups.values()}

    merged = []
    for r in results:
        if r.get("_secondary_job_id") in secondary_ids:
            continue  # secondary는 별도 처리
        merged.append(r)

    return merged

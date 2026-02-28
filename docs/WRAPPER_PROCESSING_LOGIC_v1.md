# VROOM Wrapper 처리 로직 상세 명세 v1.0

**기준 문서**: HGLIS_배차엔진_통합명세서_v8.3
**대상**: vroom-wrapper-project (`src/`)
**작성일**: 2026-02-28

---

## 전체 파이프라인

```
시뮬레이터/HGLIS  ──→  래퍼 수신
                           │
                    ┌──────┴──────┐
                    │ Step 1      │ 데이터 수신 및 검증
                    ├─────────────┤
                    │ Step 2      │ 오더 분석 모듈 (리포트 생성)
                    ├─────────────┤
                    │ Step 3      │ 전처리 (VROOM Input 생성)
                    │  3-1 권역 분할
                    │  3-2 C6 월상한 필터링
                    │  3-3 C1 합배차 job 복제
                    │  3-4 C4 기능도 skill 매핑
                    │  3-5 C7 신제품 skill 매핑
                    │  3-6 C8 미결이력 skill 매핑
                    │  3-7 소파 skill 매핑
                    │  3-8 C3 time_windows 변환
                    │  3-9 C5 CBM → capacity/delivery 변환
                    │  3-10 service/setup 시간 변환
                    │  3-11 priority 계산
                    │  3-12 VROOM JSON 조립
                    ├─────────────┤
                    │ Step 4      │ VROOM 엔진 실행 (권역별 병렬)
                    ├─────────────┤
                    │ Step 5      │ 후처리
                    │  5-1 권역별 결과 병합
                    │  5-2 합배차 결과 병합
                    │  5-3 C2 설치비 하한 검증 (거리비 포함)
                    │  5-4 C6 월상한 재검증
                    │  5-5 미배정 사유 분석
                    │  5-6 기사별 통계 집계
                    ├─────────────┤
                    │ Step 6      │ 결과 출력
                    └─────────────┘
```

---

## Step 1: 데이터 수신 및 검증

### 1.1 수신 포맷

시뮬레이터/HGLIS는 비즈니스 언어 JSON을 보냄. VROOM 포맷 아님.

```
POST /dispatch
Content-Type: application/json
X-API-Key: xxx

{
  "meta": { ... },
  "jobs": [ ... ],
  "vehicles": [ ... ],
  "options": { ... }
}
```

### 1.2 필수 필드 검증 — Job

| 필드 | 타입 | 필수 | 검증 규칙 |
|------|------|------|-----------|
| `id` | int | O | 양수, 유니크 |
| `order_id` | string | O | 비어있지 않음 |
| `location` | [float, float] | O | lon: 124~132, lat: 33~39 (한국 범위) |
| `region_code` | string | O | 유효한 권역코드 (Y1,Y2,Y3,Y5,W1,지방7개) |
| `products` | array | O | 최소 1개 |
| `products[].model_code` | string | O | 비어있지 않음 |
| `products[].cbm` | float | O | 0 이상 |
| `products[].fee` | int | O | 0 이상 |
| `products[].is_new_product` | bool | O | |
| `products[].required_grade` | string | O | S/A/B/C 중 하나 |
| `scheduling.preferred_time_slot` | string | O | 오전1/오후1/오후2/오후3/하루종일 |
| `scheduling.service_minutes` | int | O | 양수 |
| `constraints.crew_type` | string | O | "1인"/"2인"/"any" |

### 1.3 필수 필드 검증 — Vehicle

| 필드 | 타입 | 필수 | 검증 규칙 |
|------|------|------|-----------|
| `id` | int | O | 양수, 유니크 |
| `driver_id` | string | O | 비어있지 않음 |
| `skill_grade` | string | O | S/A/B/C |
| `service_grade` | string | O | S/A/B/C |
| `capacity_cbm` | float | O | 양수 |
| `location.start` | [float, float] | O | 한국 범위 |
| `location.end` | [float, float] | O | 한국 범위 |
| `region_code` | string | O | 유효한 권역코드 |
| `crew.size` | int | O | 1 또는 2 |
| `crew.is_filler` | bool | O | |
| `new_product_restricted` | bool | O | 관리자 체크값 |
| `exclusions.avoid_models` | string[] | O | (빈 배열 허용) |
| `fee_status.monthly_accumulated` | int | O | 0 이상 |

### 1.4 검증 실패 시

```json
{
  "status": "error",
  "code": "VALIDATION_FAILED",
  "errors": [
    {"field": "jobs[3].location", "message": "좌표 범위 초과 (lon=200)"},
    {"field": "vehicles[0].skill_grade", "message": "유효하지 않은 기능도: X"}
  ]
}
```

---

## Step 2: 오더 분석 모듈

VROOM 호출 전에 전체 데이터를 분석해서 리포트 생성.
실제 배차 로직에는 영향 없지만, 관리자/시뮬레이터에 선제적 인사이트 제공.

### 2.1 기본 집계

```python
report = {
    "total_orders": len(jobs),
    "total_cbm": sum(j.total_cbm for j in jobs),
    "total_fee": sum(j.total_fee for j in jobs),
    "by_region": Counter(j.region_code for j in jobs),
    "two_person_count": sum(1 for j in jobs if j.crew_type == "2인"),
    "two_person_ratio": two_person_count / total_orders,
}
```

### 2.2 제약조건별 분석

```python
# C1: 2인 오더 vs 2인팀/합배차 가용
c1 = {
    "two_person_orders": count_two_person_orders,
    "two_person_teams": count(v for v in vehicles if v.crew.size == 2),
    "filler_available": count(v for v in vehicles if v.crew.is_filler),
    "joint_dispatch_needed": max(0, two_person_orders - two_person_teams),
}

# C3: 시간대별 오더 분포
c3 = Counter(j.scheduling.preferred_time_slot for j in jobs)

# C4: 기능도별 오더 분포 vs 기사 분포
c4 = {
    "orders_by_grade": Counter(j.max_required_grade for j in jobs),
    "vehicles_by_grade": Counter(v.skill_grade for v in vehicles),
}

# C5: CBM 분포
c5 = {
    "avg_cbm": mean(j.total_cbm for j in jobs),
    "max_cbm": max(j.total_cbm for j in jobs),
    "over_capacity_risk": count(j for j in jobs if j.total_cbm > min_vehicle_cbm),
}

# C6: 월상한 현황
MONTHLY_CAP = {"S": 12000000, "A": 11000000, "B": 9000000, "C": 7000000}
c6 = {
    "over_limit": [v for v in vehicles if v.monthly_accumulated >= MONTHLY_CAP[v.service_grade]],
    "near_limit_90pct": [v for v in vehicles
        if v.monthly_accumulated >= MONTHLY_CAP[v.service_grade] * 0.9],
}

# C7: 신제품 오더 vs 가능 기사
c7 = {
    "new_product_orders": count(j for j in jobs if j.has_new_product),
    "restricted_drivers": count(v for v in vehicles if v.new_product_restricted),
    "available_drivers": count(v for v in vehicles if not v.new_product_restricted),
}

# C8: 회피 모델 충돌 건수
c8_conflicts = 0
for j in jobs:
    for v in vehicles:
        if set(j.model_codes) & set(v.avoid_models):
            c8_conflicts += 1
```

### 2.3 수급 매칭 검증

```python
warnings = []

# 2인 오더 수급
if c1["joint_dispatch_needed"] > c1["filler_available"] // 2:
    warnings.append({
        "level": "CRITICAL",
        "message": f"합배차 가용 기사 부족: 필요 {c1['joint_dispatch_needed']}건, "
                   f"가능 조합 {c1['filler_available'] // 2}건"
    })

# 고기능 오더 수급
for grade in ["S", "A"]:
    need = c4["orders_by_grade"].get(grade, 0)
    have = sum(1 for v in vehicles if grade_gte(v.skill_grade, grade))
    if need > have * 12:  # 기사당 최대 12건 가정
        warnings.append({
            "level": "WARNING",
            "message": f"{grade}급 오더 {need}건, {grade}급 이상 기사 {have}명 — 부족 가능"
        })
```

리포트는 응답의 `analysis` 필드에 포함.

---

## Step 3: 전처리 (VROOM Input 생성)

비즈니스 JSON → 순수 VROOM JSON 변환. 이 단계가 래퍼의 핵심.

### 3-1. 권역 분할

**원칙**: 같은 권역의 기사와 오더만 같은 VROOM 문제로 묶는다.

```python
def split_by_region(jobs, vehicles, region_mode):
    """
    region_mode:
      - "strict": 기사 권역 = 오더 권역만 매칭
      - "flexible": 인접 권역 허용
      - "ignore": 전체 하나의 문제로
    """
    if region_mode == "ignore":
        return [{"region": "ALL", "jobs": jobs, "vehicles": vehicles}]

    # 소파 분리: 소파 오더 → W1 권역으로 강제 (경인권만)
    sofa_jobs = []
    normal_jobs = []
    for j in jobs:
        if j.is_sofa and j.region_code in ("Y1", "Y2", "Y3", "Y5"):
            sofa_jobs.append(j)  # W1으로 보냄
        else:
            normal_jobs.append(j)

    # 권역별 그룹핑
    groups = {}

    # W1 소파 그룹
    if sofa_jobs:
        w1_vehicles = [v for v in vehicles if v.region_code == "W1"]
        groups["W1"] = {"jobs": sofa_jobs, "vehicles": w1_vehicles}

    # Y/지방 권역 그룹핑
    for j in normal_jobs:
        region = j.region_code
        if region not in groups:
            groups[region] = {"jobs": [], "vehicles": []}
        groups[region]["jobs"].append(j)

    for v in vehicles:
        if v.region_code == "W1":
            continue  # W1은 위에서 처리
        region = v.region_code
        if region_mode == "strict":
            if region in groups:
                groups[region]["vehicles"].append(v)
        elif region_mode == "flexible":
            # 본인 권역 + 인접 권역
            targets = [region] + ADJACENT_REGIONS.get(region, [])
            for r in targets:
                if r in groups:
                    groups[r]["vehicles"].append(v)

    return [{"region": k, **v} for k, v in groups.items()]
```

**인접 권역 테이블** (경인권만):
```python
ADJACENT_REGIONS = {
    "Y1": ["Y2", "Y3"],
    "Y2": ["Y1", "Y3", "Y5"],
    "Y3": ["Y1", "Y2"],
    "Y5": ["Y2"],
    "W1": ["Y1", "Y2"],  # W1은 소파 전용이라 실제로는 사용 안 됨
}
# 지방 권역은 인접 없음 (독립 운영)
```

**소파 판단 기준**:
```python
def is_sofa(job):
    """products 중 소파 품목이 있는지"""
    SOFA_CATEGORIES = ["소파", "쇼파", "카우치"]
    return any(p.category in SOFA_CATEGORIES for p in job.products)
```

### 3-2. C6 월상한 필터링

소프트 제약이지만 전처리에서 경고/제한적 필터링 수행.

```python
MONTHLY_CAP = {"S": 12000000, "A": 11000000, "B": 9000000, "C": 7000000}

def filter_monthly_cap(vehicles, options):
    """
    월상한 초과 기사 처리.
    소프트 제약이므로 완전 제외하지 않음 — 옵션에 따라 결정.
    """
    result = []
    c6_warnings = []

    for v in vehicles:
        cap = MONTHLY_CAP.get(v.service_grade, 7000000)
        remaining = cap - v.fee_status.monthly_accumulated
        ratio = v.fee_status.monthly_accumulated / cap

        if remaining <= 0:
            if options.get("c6_hard_filter", False):
                # 옵션: 하드 필터 (완전 제외)
                c6_warnings.append({
                    "driver_id": v.driver_id,
                    "action": "EXCLUDED",
                    "monthly_accumulated": v.fee_status.monthly_accumulated,
                    "cap": cap,
                })
                continue
            else:
                # 기본: 경고만, 배차는 허용
                c6_warnings.append({
                    "driver_id": v.driver_id,
                    "action": "WARNING_OVER_CAP",
                    "monthly_accumulated": v.fee_status.monthly_accumulated,
                    "cap": cap,
                })
        elif ratio >= 0.9:
            c6_warnings.append({
                "driver_id": v.driver_id,
                "action": "WARNING_NEAR_CAP",
                "ratio": round(ratio * 100, 1),
                "remaining": remaining,
            })

        result.append(v)

    return result, c6_warnings
```

### 3-3. C1 합배차 job 복제

2인 필요 오더 중 2인팀이 부족한 경우, job을 복제하여 1인 기사 2명에게 분배.

```python
def process_joint_dispatch(jobs, vehicles):
    """
    Returns:
      - modified_jobs: 원본 + 복제된 job 목록
      - joint_meta: 합배차 메타정보 (후처리용)
    """
    two_person_orders = [j for j in jobs if j.constraints.crew_type == "2인"]
    two_person_teams = [v for v in vehicles if v.crew.size == 2]
    filler_pool = [v for v in vehicles if v.crew.size == 1 and v.crew.is_filler]

    # 2인팀 수만큼은 그대로 (2인팀이 처리)
    # 나머지 = 합배차 필요
    remaining_2p = len(two_person_orders) - len(two_person_teams)

    joint_meta = {}
    new_jobs = list(jobs)  # 원본 복사

    if remaining_2p <= 0:
        return new_jobs, joint_meta  # 2인팀으로 충분

    # 합배차 대상 오더: 2인 오더 중 뒤에서부터 (우선순위 낮은 것부터)
    joint_candidates = two_person_orders[-remaining_2p:]

    JOINT_GROUP_BASE = 2001
    group_id = JOINT_GROUP_BASE

    for order in joint_candidates:
        # 원본 job을 primary로 변경
        order._joint = {
            "role": "primary",
            "pair_id": order.id,
            "group_skill": group_id,
            "fee_ratio": 0.6,
        }

        # secondary job 복제
        sub_job = deepcopy(order)
        sub_job.id = f"{order.id}_sub"
        sub_job._joint = {
            "role": "secondary",
            "pair_id": order.id,
            "group_skill": group_id,
            "fee_ratio": 0.4,
        }
        # secondary는 CBM 0 (이중 적재 방지)
        sub_job._zero_cbm = True

        new_jobs.append(sub_job)

        joint_meta[order.id] = {
            "group_skill": group_id,
            "primary_job_id": order.id,
            "secondary_job_id": sub_job.id,
            "original_fee": order.total_fee,
        }

        group_id += 1

    return new_jobs, joint_meta
```

### 3-4. C4 기능도 skill 매핑

**명세서 기준 계층형 매핑**:

```python
# 기능도 skill 코드 (명세서 §11.3)
GRADE_SKILLS = {
    "C": [1],
    "B": [1, 2],
    "A": [1, 2, 3],
    "S": [1, 2, 3, 4],
}

def encode_grade_skills_job(job):
    """
    오더: 필요기능도에 해당하는 skill 1개만 부여.
    예) B급 필요 → skills: [2]
    VROOM 매칭: job.skills ⊆ vehicle.skills 이므로
    B급 필요 오더(skill=2)는 B급 이상 기사(skills에 2 포함)만 가능.
    """
    max_grade = max_required_grade(job.products)
    grade_map = {"C": 1, "B": 2, "A": 3, "S": 4}
    return [grade_map[max_grade]]

def encode_grade_skills_vehicle(vehicle):
    """
    기사: 자신 등급 이하 모든 skill 부여.
    예) A급 기사 → skills: [1, 2, 3]
    """
    return GRADE_SKILLS[vehicle.skill_grade]

def max_required_grade(products):
    """오더 내 제품 중 가장 높은 필요기능도 반환"""
    order = {"S": 4, "A": 3, "B": 2, "C": 1}
    return max(products, key=lambda p: order[p.required_grade]).required_grade
```

**합배차 특례**:
```python
def encode_grade_skills_job_joint(job):
    """
    합배차 secondary job은 기능도 skill 부여하지 않음.
    명세서: "둘 중 1명만 기능도 충족해도 OK"
    → primary에만 기능도 skill 부여, secondary는 합배차그룹 skill만.
    """
    if job._joint and job._joint["role"] == "secondary":
        return []  # 기능도 skill 없음
    return encode_grade_skills_job(job)
```

### 3-5. C7 신제품 skill 매핑

**원칙**: 신제품 오더에 고유 skill 부여 → 해당 skill 없는 기사(신제품 제한)는 매칭 불가.

```python
C7_SKILL_BASE = 100

def encode_c7_skills(jobs, vehicles):
    """
    1. 신제품 포함 오더에서 고유 신제품 목록 추출
    2. 각 신제품에 skill ID 할당 (100, 101, ...)
    3. 오더: 포함된 신제품의 skill 부여
    4. 기사: new_product_restricted=False인 기사만 해당 skill 부여
    """
    # 신제품 목록 추출
    new_products = set()
    for j in jobs:
        for p in j.products:
            if p.is_new_product:
                new_products.add(p.model_code)

    if not new_products:
        return {}, {}  # 신제품 없으면 패스

    # skill ID 매핑
    np_skill_map = {}
    for i, model in enumerate(sorted(new_products)):
        np_skill_map[model] = C7_SKILL_BASE + i
    # 예: {"NP-MODEL-A": 100, "NP-MODEL-B": 101}

    # 오더 skill 추가
    job_skills = {}  # job_id → [skill_ids]
    for j in jobs:
        skills = []
        for p in j.products:
            if p.is_new_product and p.model_code in np_skill_map:
                skills.append(np_skill_map[p.model_code])
        if skills:
            job_skills[j.id] = skills

    # 기사 skill 추가
    vehicle_skills = {}  # vehicle_id → [skill_ids]
    for v in vehicles:
        if not v.new_product_restricted:
            # 제한 없는 기사 → 모든 신제품 skill 부여
            vehicle_skills[v.id] = list(np_skill_map.values())
        # 제한 기사 → 신제품 skill 없음 → 매칭 불가

    return job_skills, vehicle_skills
```

### 3-6. C8 미결이력 모델 회피 skill 매핑

**원칙**: 회피 모델이 있는 기사는 해당 모델 오더에 매칭 불가.
C7과 동일 패턴이지만 **기사별로 다른 회피 목록**.

```python
C8_SKILL_BASE = 300

def encode_c8_skills(jobs, vehicles):
    """
    1. 모든 기사의 avoid_models에서 고유 모델 목록 추출
    2. 각 모델에 skill ID 할당 (300, 301, ...)
    3. 오더: 포함된 모델의 skill 부여
    4. 기사: 해당 모델이 avoid_models에 없는 기사만 skill 부여
    """
    # 회피 대상 모델 전체 추출
    avoid_models_all = set()
    for v in vehicles:
        avoid_models_all.update(v.exclusions.avoid_models)

    if not avoid_models_all:
        return {}, {}

    # skill ID 매핑
    avoid_skill_map = {}
    for i, model in enumerate(sorted(avoid_models_all)):
        avoid_skill_map[model] = C8_SKILL_BASE + i
    # 예: {"BED-A01": 300, "SOFA-B03": 301}

    # 오더 skill 추가
    job_skills = {}
    for j in jobs:
        skills = []
        for p in j.products:
            if p.model_code in avoid_skill_map:
                skills.append(avoid_skill_map[p.model_code])
        if skills:
            job_skills[j.id] = skills

    # 기사 skill 추가 (회피 모델이 아닌 것만)
    vehicle_skills = {}
    for v in vehicles:
        skills = []
        for model, skill_id in avoid_skill_map.items():
            if model not in v.exclusions.avoid_models:
                skills.append(skill_id)
            # 회피 모델이면 skill 미부여 → 매칭 불가
        if skills:
            vehicle_skills[v.id] = skills

    return job_skills, vehicle_skills
```

### 3-7. 소파 skill 매핑

```python
SOFA_SKILL = 500

def encode_sofa_skill(jobs, vehicles):
    """
    소파 오더 → skill 500 부여
    W권역 기사 → skill 500 부여
    경인권 Y권역 기사 → skill 500 없음 → 소파 매칭 불가
    지방 기사 → skill 500 부여 (지방은 구분 없음)
    """
    job_skills = {}
    for j in jobs:
        if is_sofa(j):
            job_skills[j.id] = [SOFA_SKILL]

    vehicle_skills = {}
    for v in vehicles:
        if v.region_code == "W1":
            vehicle_skills[v.id] = [SOFA_SKILL]
        elif v.region_code not in ("Y1", "Y2", "Y3", "Y5"):
            # 지방 권역: 소파 가능
            vehicle_skills[v.id] = [SOFA_SKILL]

    return job_skills, vehicle_skills
```

### 3-8. C3 time_windows 변환

```python
TIME_SLOTS = {
    "오전1": ("08:00", "12:00"),
    "오후1": ("12:00", "16:00"),
    "오후2": ("16:00", "19:00"),
    "오후3": ("19:00", "23:59"),
    "하루종일": ("08:00", "23:59"),
}

BUFFER_MINUTES = 60  # ±1시간 룸

def time_slot_to_window(slot, date_str):
    """
    명세서 §8.4 기준:
    오전1 (08:00~12:00) → 실제 허용 07:00~13:00 (±1시간)
    """
    start_str, end_str = TIME_SLOTS[slot]

    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    start_dt = base_date + parse_time(start_str) - timedelta(minutes=BUFFER_MINUTES)
    end_dt = base_date + parse_time(end_str) + timedelta(minutes=BUFFER_MINUTES)

    # 하루종일은 버퍼 적용 안 함
    if slot == "하루종일":
        start_dt = base_date + parse_time("08:00")
        end_dt = base_date + parse_time("23:59")

    return [int(start_dt.timestamp()), int(end_dt.timestamp())]
```

**기사 time_window**:
```python
def vehicle_time_window(vehicle, date_str):
    """
    명세서 §10.3: 시작 08:00 고정, 종료 제한 없음
    → 실질적으로 08:00 ~ 23:59 (당일 내)
    """
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    start = base_date + timedelta(hours=8)

    # work_time이 지정되어 있으면 사용, 없으면 기본값
    if vehicle.work_time:
        end = base_date + parse_time(vehicle.work_time.end)
    else:
        end = base_date + timedelta(hours=23, minutes=59)

    return [int(start.timestamp()), int(end.timestamp())]
```

### 3-9. C5 CBM → capacity/delivery 변환

```python
CBM_MULTIPLIER = 100  # float → int 변환 (소수점 2자리 보존)

def encode_cbm_job(job):
    """
    오더: 모든 제품의 CBM 합산 → delivery[0]
    합배차 secondary는 CBM 0 (이중 적재 방지)
    """
    if getattr(job, '_zero_cbm', False):
        return [0, 0, 0]

    total_cbm = sum(p.cbm for p in job.products)
    return [int(total_cbm * CBM_MULTIPLIER), 0, 0]

def encode_cbm_vehicle(vehicle):
    """
    기사: 차량 CBM → capacity[0]
    """
    return [int(vehicle.capacity_cbm * CBM_MULTIPLIER), 0, 0]
```

### 3-10. service/setup 시간 변환

```python
BASE_STAY_MINUTES = 25  # 기본체류시간 (양중15 + 마무리10)

def encode_service(job):
    """
    VROOM service = (총설치소요시간 + 기본체류시간) × 60 (초 변환)
    setup은 별도 지정 시 사용
    """
    service_min = job.scheduling.service_minutes + BASE_STAY_MINUTES
    service_sec = service_min * 60

    setup_sec = 0
    if job.scheduling.setup_minutes:
        setup_sec = job.scheduling.setup_minutes * 60

    return service_sec, setup_sec
```

### 3-11. priority 계산

```python
def encode_priority(job):
    """
    VROOM priority: 높을수록 우선 배정
    명세서에 명시적 우선순위 체계 없음 — 래퍼에서 정의:
      기본: 0
      VIP: +50
      긴급: +100
      2인 오더: +10 (미배정 방지)
    """
    p = job.priority.level if job.priority else 0
    if job.priority and job.priority.is_urgent:
        p += 100
    if job.priority and job.priority.is_vip:
        p += 50
    if job.constraints.crew_type == "2인":
        p += 10
    return min(p, 100)  # VROOM 최대 100
```

### 3-12. VROOM JSON 조립

모든 인코딩 결과를 합쳐서 순수 VROOM 입력 생성.

```python
def assemble_vroom_input(jobs, vehicles, joint_meta, date_str, options):
    """
    각 인코딩 결과를 수집하여 VROOM 표준 JSON 조립
    """
    # skill 인코딩 수집
    c7_job_sk, c7_veh_sk = encode_c7_skills(jobs, vehicles)
    c8_job_sk, c8_veh_sk = encode_c8_skills(jobs, vehicles)
    sofa_job_sk, sofa_veh_sk = encode_sofa_skill(jobs, vehicles)

    vroom_jobs = []
    for j in jobs:
        # skill 합산
        skills = []
        skills.extend(encode_grade_skills_job_joint(j))  # C4 (합배차 특례 포함)
        skills.extend(c7_job_sk.get(j.id, []))             # C7
        skills.extend(c8_job_sk.get(j.id, []))             # C8
        skills.extend(sofa_job_sk.get(j.id, []))           # 소파

        # 합배차 그룹 skill
        if hasattr(j, '_joint') and j._joint:
            skills.append(j._joint["group_skill"])

        service_sec, setup_sec = encode_service(j)

        vroom_job = {
            "id": j.id,
            "description": f"{j.order_id}_{j.customer.name if j.customer else ''}",
            "location": j.location,
            "service": service_sec,
            "delivery": encode_cbm_job(j),
            "skills": skills,
            "time_windows": [time_slot_to_window(j.scheduling.preferred_time_slot, date_str)],
            "priority": encode_priority(j),
        }
        if setup_sec > 0:
            vroom_job["setup"] = setup_sec

        vroom_jobs.append(vroom_job)

    vroom_vehicles = []
    for v in vehicles:
        # skill 합산
        skills = []
        skills.extend(encode_grade_skills_vehicle(v))       # C4
        skills.extend(c7_veh_sk.get(v.id, []))              # C7
        skills.extend(c8_veh_sk.get(v.id, []))              # C8
        skills.extend(sofa_veh_sk.get(v.id, []))            # 소파

        # 2인팀: 합배차 대상 오더의 그룹 skill 부여
        if v.crew.size == 2:
            # 2인팀은 모든 합배차 그룹에 참여 가능
            for meta in joint_meta.values():
                skills.append(meta["group_skill"])

        # 합배차 가능 1인 기사: 합배차 그룹 skill 부여
        if v.crew.size == 1 and v.crew.is_filler:
            for meta in joint_meta.values():
                skills.append(meta["group_skill"])

        tw = vehicle_time_window(v, date_str)

        vroom_vehicle = {
            "id": v.id,
            "description": f"{v.driver_id}_{v.driver_name}",
            "start": v.location.start,
            "end": v.location.end,
            "capacity": encode_cbm_vehicle(v),
            "skills": skills,
            "time_window": tw,
            "max_tasks": options.get("max_orders_per_driver", 12),
        }

        # breaks (점심 등)
        if v.work_time and v.work_time.breaks:
            vroom_vehicle["breaks"] = [
                {
                    "id": f"break_{v.id}_{i}",
                    "time_windows": [[
                        int((datetime.strptime(date_str, "%Y-%m-%d") +
                             parse_time(b.start)).timestamp()),
                        int((datetime.strptime(date_str, "%Y-%m-%d") +
                             parse_time(b.end)).timestamp()),
                    ]],
                    "service": (parse_time(b.end) - parse_time(b.start)).seconds,
                }
                for i, b in enumerate(v.work_time.breaks)
            ]

        vroom_vehicles.append(vroom_vehicle)

    return {
        "jobs": vroom_jobs,
        "vehicles": vroom_vehicles,
        "options": {"g": True},  # geometry 항상 필요 (거리비 계산용)
    }
```

### Skill ID 체계 종합 (명세서 기준)

```
 ID 범위    | 용도                  | 예시
 -----------|-----------------------|---------------------------
 1~4        | C4 기능도 계층        | 1=C, 2=B, 3=A, 4=S
 100~199    | C7 신제품             | 100=신제품A, 101=신제품B
 300~399    | C8 미결이력 모델      | 300=BED-A01, 301=SOFA-B03
 500        | 소파 전용             | W권역/지방 기사만 보유
 2001~2999  | 합배차 그룹           | 2001=ORD-001용, 2002=ORD-002용
```

---

## Step 4: VROOM 엔진 실행

### 4.1 권역별 병렬 실행

```python
async def execute_by_region(region_problems, executor, config):
    """
    각 권역 문제를 병렬로 VROOM 실행.
    결과를 권역별로 수집.
    """
    tasks = []
    for problem in region_problems:
        if not problem["jobs"] or not problem["vehicles"]:
            continue  # 빈 권역 스킵

        vroom_input = assemble_vroom_input(
            problem["jobs"], problem["vehicles"],
            problem.get("joint_meta", {}),
            config["date"],
            config["options"],
        )
        tasks.append({
            "region": problem["region"],
            "input": vroom_input,
            "future": executor.execute(
                vroom_input,
                threads=config.get("threads", 4),
                exploration=config.get("exploration", 5),
                geometry=True,
            ),
        })

    results = {}
    for task in tasks:
        result = await task["future"]
        results[task["region"]] = {
            "input": task["input"],
            "result": result,
        }

    return results
```

### 4.2 미배정 자동 재시도

VROOM 결과에 미배정(unassigned)이 있으면 제약 완화 후 재시도.

```python
async def retry_with_relaxation(vroom_input, result, executor, max_retry=2):
    """
    미배정 발생 시:
    1차 재시도: time_windows ±30분 확장
    2차 재시도: time_windows ±60분 추가 확장
    skills/capacity는 완화하지 않음 (하드 제약 유지)
    """
    unassigned = result.get("unassigned", [])
    if not unassigned:
        return result

    for attempt in range(max_retry):
        # time_windows만 확장 (가장 안전한 완화)
        relaxed = deepcopy(vroom_input)
        expansion = (attempt + 1) * 30 * 60  # 30분씩 추가

        for job in relaxed["jobs"]:
            if job["id"] in [u["id"] for u in unassigned]:
                for tw in job.get("time_windows", []):
                    tw[0] -= expansion
                    tw[1] += expansion

        new_result = await executor.execute(relaxed, geometry=True)

        # 개선되었으면 채택
        if len(new_result.get("unassigned", [])) < len(unassigned):
            result = new_result
            unassigned = new_result.get("unassigned", [])

        if not unassigned:
            break

    return result
```

---

## Step 5: 후처리

### 5-1. 권역별 결과 병합

```python
def merge_region_results(region_results):
    """여러 권역 VROOM 결과를 하나로 병합"""
    merged = {
        "routes": [],
        "unassigned": [],
        "summary": {"cost": 0, "routes": 0, "unassigned": 0, "delivery": [0,0,0]},
    }
    for region, data in region_results.items():
        result = data["result"]
        for route in result.get("routes", []):
            route["_region"] = region
            merged["routes"].append(route)
        merged["unassigned"].extend(result.get("unassigned", []))
        merged["summary"]["cost"] += result.get("summary", {}).get("cost", 0)
        merged["summary"]["routes"] += result.get("summary", {}).get("routes", 0)
        merged["summary"]["unassigned"] += result.get("summary", {}).get("unassigned", 0)

    return merged
```

### 5-2. 합배차 결과 병합

```python
def merge_joint_dispatch(vroom_result, joint_meta, original_jobs):
    """
    VROOM이 배정한 primary/secondary job을 하나의 합배차 결과로 병합.
    """
    # job_id → route/vehicle 매핑
    job_assignments = {}
    for route in vroom_result["routes"]:
        vehicle_id = route["vehicle"]
        for step in route["steps"]:
            if step["type"] == "job":
                job_assignments[step["id"]] = {
                    "vehicle_id": vehicle_id,
                    "arrival": step["arrival"],
                    "departure": step["departure"],
                }

    joint_results = []
    for pair_id, meta in joint_meta.items():
        primary_id = meta["primary_job_id"]
        secondary_id = meta["secondary_job_id"]

        primary_assign = job_assignments.get(primary_id)
        secondary_assign = job_assignments.get(secondary_id)

        if primary_assign and secondary_assign:
            # 둘 다 배정됨 → 합배차 성공
            original = next(j for j in original_jobs if j.id == pair_id)
            joint_results.append({
                "order_id": original.order_id,
                "dispatch_type": "joint",
                "drivers": [
                    {"vehicle_id": primary_assign["vehicle_id"], "role": "primary"},
                    {"vehicle_id": secondary_assign["vehicle_id"], "role": "secondary"},
                ],
                "scheduled_time": primary_assign["arrival"],
                "fee_split": {
                    "primary": int(meta["original_fee"] * 0.6),
                    "secondary": int(meta["original_fee"] * 0.4),
                },
            })
        elif primary_assign and not secondary_assign:
            # secondary 미배정 → 합배차 실패, primary만 단독? or 미배정?
            # 정책: 합배차 실패 시 둘 다 미배정 처리
            vroom_result["unassigned"].append({"id": primary_id, "type": "job"})
            joint_results.append({
                "order_id": original.order_id,
                "dispatch_type": "joint_failed",
                "reason": "보조기사 미배정",
            })

    # VROOM 결과에서 합배차 job들을 제거 (중복 방지)
    # → 최종 결과에는 joint_results로 대체

    return joint_results
```

### 5-3. C2 설치비 하한 검증 (거리비 포함)

```python
# 명세서 §8.3 기준
FEE_THRESHOLD = {
    "2인팀": 400000,
    "S": 280000,
    "A": 250000,
    "B": 220000,
    "C": 180000,
}

# 거리비 테이블 (명세서 §8.3.1)
DISTANCE_FEE_METRO = [  # 수도권
    (30,  0),
    (50,  24000),
    (70,  36500),
    (100, 48000),
    (150, 81000),
    (999, 81000),  # 150km 초과
]
DISTANCE_FEE_LOCAL = [  # 지방
    (70,  0),
    (100, 40500),
    (150, 81000),
    (200, 93000),
    (999, 118000),  # 200km 초과
]

def calc_distance_fee(max_distance_km, is_metro):
    """상차지→최장배송지 실경로 거리 기준 거리비 산출"""
    table = DISTANCE_FEE_METRO if is_metro else DISTANCE_FEE_LOCAL
    for threshold, fee in table:
        if max_distance_km < threshold:
            return fee
    return table[-1][1]

async def validate_c2(routes, vehicles_map, jobs_map, depot_locations, osrm_client):
    """
    각 기사별:
    1. 배정된 오더의 설치비 합산
    2. 상차지(depot) → 최장 배송지 실경로 거리 계산 (OSRM)
    3. 거리비 산출
    4. 일일 수익 = 설치비 합 + 거리비
    5. 하한 비교 → 미달 시 경고
    """
    c2_results = []

    for route in routes:
        vehicle_id = route["vehicle"]
        vehicle = vehicles_map[vehicle_id]

        # 배정된 오더의 설치비 합산
        total_fee = 0
        job_locations = []
        for step in route["steps"]:
            if step["type"] == "job":
                job = jobs_map[step["id"]]
                total_fee += job.total_fee
                job_locations.append(step["location"])

        if not job_locations:
            continue

        # 상차지(depot) 좌표 — 권역별 물류센터
        depot = depot_locations.get(vehicle.region_code)
        if not depot:
            depot = vehicle.location.start  # 폴백: 기사 출발지

        # 상차지 → 최장 배송지 실경로 거리 (OSRM route API)
        max_distance_km = 0
        for loc in job_locations:
            dist = await osrm_client.route_distance(depot, loc)
            if dist and dist > max_distance_km:
                max_distance_km = dist

        # 거리비 산출
        is_metro = vehicle.region_code in ("Y1", "Y2", "Y3", "Y5", "W1")
        distance_fee = calc_distance_fee(max_distance_km, is_metro)

        # 일일 수익
        daily_income = total_fee + distance_fee

        # 하한 기준
        if vehicle.crew.size == 2:
            threshold_key = "2인팀"
        else:
            threshold_key = vehicle.skill_grade  # C2는 기능도 기준 (명세서 확인 필요)
        threshold = FEE_THRESHOLD.get(threshold_key, 180000)

        c2_results.append({
            "driver_id": vehicle.driver_id,
            "driver_name": vehicle.driver_name,
            "grade": threshold_key,
            "assigned_orders": len([s for s in route["steps"] if s["type"] == "job"]),
            "install_fee_total": total_fee,
            "distance_fee": distance_fee,
            "max_distance_km": round(max_distance_km, 1),
            "daily_income": daily_income,
            "threshold": threshold,
            "status": "OK" if daily_income >= threshold else "BELOW_THRESHOLD",
            "shortfall": max(0, threshold - daily_income),
        })

    return c2_results
```

### 5-4. C6 월상한 재검증

```python
MONTHLY_CAP = {"S": 12000000, "A": 11000000, "B": 9000000, "C": 7000000}

def validate_c6(routes, vehicles_map, jobs_map):
    """
    배차 후 월누적 + 당일 배정 설치비 vs 월상한 재검증.
    소프트 제약 → 배차 취소 안 함, 경고만.
    """
    c6_results = []

    for route in routes:
        vehicle_id = route["vehicle"]
        vehicle = vehicles_map[vehicle_id]

        # 당일 배정 설치비 합산
        today_fee = sum(
            jobs_map[step["id"]].total_fee
            for step in route["steps"]
            if step["type"] == "job"
        )

        monthly_after = vehicle.fee_status.monthly_accumulated + today_fee
        cap = MONTHLY_CAP.get(vehicle.service_grade, 7000000)
        ratio = monthly_after / cap

        status = "OK"
        if ratio >= 1.0:
            status = "OVER_CAP"
        elif ratio >= 0.9:
            status = "NEAR_CAP"

        c6_results.append({
            "driver_id": vehicle.driver_id,
            "service_grade": vehicle.service_grade,
            "monthly_before": vehicle.fee_status.monthly_accumulated,
            "today_fee": today_fee,
            "monthly_after": monthly_after,
            "monthly_cap": cap,
            "ratio_pct": round(ratio * 100, 1),
            "status": status,
        })

    return c6_results
```

### 5-5. 미배정 사유 분석

```python
def analyze_unassigned(unassigned, vroom_input, original_jobs, original_vehicles):
    """
    VROOM은 미배정 이유를 주지 않음. 역추적으로 분석.
    각 미배정 오더에 대해 모든 기사와 매칭 시도 → 실패 사유 수집.
    """
    reasons = []
    jobs_map = {j["id"]: j for j in vroom_input["jobs"]}
    vehicles_list = vroom_input["vehicles"]

    for u in unassigned:
        job_id = u["id"]
        job = jobs_map.get(job_id)
        if not job:
            continue

        job_reasons = []

        for v in vehicles_list:
            # C4/C7/C8: skill 체크
            if not set(job.get("skills", [])).issubset(set(v.get("skills", []))):
                missing = set(job["skills"]) - set(v["skills"])
                job_reasons.append({
                    "vehicle_id": v["id"],
                    "constraint": "SKILLS",
                    "detail": decode_missing_skills(missing),
                })
                continue

            # C5: capacity 체크
            if job.get("delivery") and v.get("capacity"):
                if any(d > c for d, c in zip(job["delivery"], v["capacity"])):
                    job_reasons.append({
                        "vehicle_id": v["id"],
                        "constraint": "CAPACITY",
                        "detail": f"job CBM {job['delivery'][0]} > vehicle {v['capacity'][0]}",
                    })
                    continue

            # C3: time_window 체크
            # (간소화 — 실제로는 경로 내 다른 오더까지 고려해야 정확)
            job_tw = job.get("time_windows", [[0, 999999999]])[0]
            v_tw = v.get("time_window", [0, 999999999])
            if job_tw[1] < v_tw[0] or job_tw[0] > v_tw[1]:
                job_reasons.append({
                    "vehicle_id": v["id"],
                    "constraint": "TIME_WINDOW",
                    "detail": "시간창 불일치",
                })
                continue

            # max_tasks 체크 (이미 가득 찬 기사)
            job_reasons.append({
                "vehicle_id": v["id"],
                "constraint": "ROUTE_FULL",
                "detail": "경로 최적화 상 배정 불가 (비용/시간 초과)",
            })

        # 가장 빈번한 사유 집계
        constraint_counts = Counter(r["constraint"] for r in job_reasons)
        primary_reason = constraint_counts.most_common(1)[0] if constraint_counts else ("UNKNOWN", 0)

        # 비즈니스 언어로 변환
        original = next((j for j in original_jobs if j.id == job_id), None)
        reasons.append({
            "job_id": job_id,
            "order_id": original.order_id if original else str(job_id),
            "primary_constraint": primary_reason[0],
            "reason_ko": REASON_MAP.get(primary_reason[0], "알 수 없음"),
            "detail_counts": dict(constraint_counts),
        })

    return reasons

REASON_MAP = {
    "SKILLS": "기능도/신제품/미결이력 매칭 실패",
    "CAPACITY": "CBM 용량 초과",
    "TIME_WINDOW": "희망배송시간 매칭 실패",
    "ROUTE_FULL": "가용 기사 경로 포화",
    "UNKNOWN": "원인 미상",
}

def decode_missing_skills(missing_ids):
    """skill ID를 비즈니스 언어로 변환"""
    decoded = []
    for sid in missing_ids:
        if 1 <= sid <= 4:
            grade = {1:"C", 2:"B", 3:"A", 4:"S"}[sid]
            decoded.append(f"C4 기능도 {grade}급 필요")
        elif 100 <= sid <= 199:
            decoded.append(f"C7 신제품 skill#{sid}")
        elif 300 <= sid <= 399:
            decoded.append(f"C8 미결이력 모델 skill#{sid}")
        elif sid == 500:
            decoded.append("소파 전용 (W권역 필요)")
        elif 2001 <= sid <= 2999:
            decoded.append(f"합배차 그룹 #{sid}")
        else:
            decoded.append(f"unknown skill#{sid}")
    return ", ".join(decoded)
```

### 5-6. 기사별 통계 집계

```python
def generate_driver_summary(routes, vehicles_map, jobs_map, c2_results, c6_results):
    """
    기사별 최종 통계:
    - 배정 건수, 총 CBM, 총 설치비
    - 이동거리/시간
    - C2 하한 상태
    - C6 월상한 상태
    """
    c2_map = {r["driver_id"]: r for r in c2_results}
    c6_map = {r["driver_id"]: r for r in c6_results}

    summaries = []
    for route in routes:
        vid = route["vehicle"]
        v = vehicles_map[vid]
        c2 = c2_map.get(v.driver_id, {})
        c6 = c6_map.get(v.driver_id, {})

        assigned = [s for s in route["steps"] if s["type"] == "job"]

        summaries.append({
            "driver_id": v.driver_id,
            "driver_name": v.driver_name,
            "skill_grade": v.skill_grade,
            "service_grade": v.service_grade,
            "region": v.region_code,
            "crew_size": v.crew.size,

            "assigned_count": len(assigned),
            "total_cbm": sum(jobs_map[s["id"]].total_cbm for s in assigned),
            "total_fee": sum(jobs_map[s["id"]].total_fee for s in assigned),

            "distance_km": round(route.get("distance", 0) / 1000, 1),
            "duration_min": round(route.get("duration", 0) / 60, 1),
            "service_min": round(route.get("service", 0) / 60, 1),
            "waiting_min": round(route.get("waiting_time", 0) / 60, 1),

            "daily_income": c2.get("daily_income"),
            "c2_status": c2.get("status"),
            "c2_threshold": c2.get("threshold"),

            "monthly_after": c6.get("monthly_after"),
            "c6_status": c6.get("status"),
            "c6_cap": c6.get("monthly_cap"),
        })

    return summaries
```

---

## Step 6: 결과 출력

### 6.1 최종 응답 구조

```json
{
  "status": "success",
  "meta": {
    "request_id": "SIM-20260120-W1Y1-001",
    "date": "2026-01-20",
    "execution_time_ms": 12500,
    "engine": "vroom",
    "regions_processed": ["Y1", "W1"]
  },

  "statistics": {
    "total_orders": 500,
    "assigned_orders": 480,
    "unassigned_orders": 20,
    "assignment_rate": 96.0,
    "joint_dispatch_count": 45,
    "joint_dispatch_success": 42,
    "total_distance_km": 3250.5,
    "total_duration_hours": 85.3
  },

  "results": [
    {
      "order_id": "ORD-001",
      "dispatch_type": "single",
      "driver": {"id": "D001", "name": "김철수"},
      "delivery_sequence": 1,
      "scheduled_arrival": "2026-01-20T08:30:00",
      "install_fee": 85000,
      "geometry": "encoded_polyline..."
    },
    {
      "order_id": "ORD-002",
      "dispatch_type": "joint",
      "drivers": [
        {"id": "D003", "name": "이영수", "role": "primary"},
        {"id": "D007", "name": "박민호", "role": "secondary"}
      ],
      "delivery_sequence": 2,
      "scheduled_arrival": "2026-01-20T10:30:00",
      "install_fee": 150000,
      "fee_split": {"primary": 90000, "secondary": 60000}
    }
  ],

  "driver_summary": [
    {
      "driver_id": "D001",
      "driver_name": "김철수",
      "skill_grade": "S",
      "service_grade": "S",
      "assigned_count": 6,
      "total_fee": 520000,
      "distance_km": 45.2,
      "daily_income": 544000,
      "c2_status": "OK",
      "c2_threshold": 280000,
      "monthly_after": 9020000,
      "c6_status": "OK",
      "c6_cap": 12000000
    }
  ],

  "unassigned": [
    {
      "order_id": "ORD-499",
      "constraint": "SKILLS",
      "reason": "C4 기능도 S급 필요 — 가용 S급 기사 없음"
    }
  ],

  "warnings": [
    {"type": "C2_BELOW", "driver_id": "D015", "message": "일일 수익 ₩180,000 < 하한 ₩220,000"},
    {"type": "C6_NEAR_CAP", "driver_id": "D023", "message": "월 누적 92.3% (₩10,150,000 / ₩11,000,000)"}
  ],

  "analysis": {
    "order_report": { ... },
    "quality_score": 87.5,
    "balance_index": 0.12,
    "suggestions": [
      "Y1 권역 S급 기사 1명 추가 필요",
      "합배차 3건 보조기사 미배정 — 합배차가능 기사 풀 확대 권고"
    ]
  }
}
```

### 6.2 검증 기준 (명세서 §10.2)

```python
def validate_result(statistics, driver_summary):
    """배차 결과 품질 검증"""
    checks = []

    # 배정률 ≥ 95%
    if statistics["assignment_rate"] < 95:
        checks.append({
            "check": "assignment_rate",
            "status": "FAIL",
            "value": statistics["assignment_rate"],
            "target": 95,
        })

    # 균등도 σ ≤ 15%
    counts = [d["assigned_count"] for d in driver_summary if d["assigned_count"] > 0]
    if counts:
        mean_count = sum(counts) / len(counts)
        variance = sum((c - mean_count) ** 2 for c in counts) / len(counts)
        std_ratio = (variance ** 0.5) / mean_count if mean_count > 0 else 0
        if std_ratio > 0.15:
            checks.append({
                "check": "balance",
                "status": "FAIL",
                "value": round(std_ratio * 100, 1),
                "target": 15,
            })

    return checks
```

---

## 구현 파일 매핑

| 처리 단계 | 파일 (신규/수정) | 비고 |
|-----------|-----------------|------|
| Step 1 검증 | `src/preprocessing/dispatch_validator.py` | 신규 |
| Step 2 오더분석 | `src/preprocessing/order_analyzer.py` | 신규 |
| Step 3-1 권역분할 | `src/preprocessing/region_splitter.py` | 신규 |
| Step 3-2 C6 필터 | `src/preprocessing/monthly_cap_filter.py` | 신규 |
| Step 3-3 C1 합배차 | `src/preprocessing/joint_dispatch.py` | 신규 |
| Step 3-4~8 Skill | `src/preprocessing/skill_encoder.py` | 신규 (C4+C7+C8+소파 통합) |
| Step 3-8 시간변환 | `src/preprocessing/time_converter.py` | 신규 |
| Step 3-9~12 조립 | `src/preprocessing/vroom_assembler.py` | 신규 |
| Step 4 실행 | `src/control/controller.py` | 수정 (권역별 병렬 + 재시도) |
| Step 5-1 병합 | `src/postprocessing/region_merger.py` | 신규 |
| Step 5-2 합배차병합 | `src/postprocessing/joint_merger.py` | 신규 |
| Step 5-3 C2 검증 | `src/postprocessing/fee_validator.py` | 신규 (거리비 포함) |
| Step 5-4 C6 재검증 | `src/postprocessing/monthly_cap_validator.py` | 신규 |
| Step 5-5 미배정사유 | `src/postprocessing/constraint_checker.py` | 수정 (C1~C8 확장) |
| Step 5-6 통계 | `src/postprocessing/statistics.py` | 수정 (설치비/거리비 추가) |
| Step 6 출력 | `src/api/dispatch_response.py` | 신규 |
| 엔드포인트 | `src/main_v3.py` | 수정 (POST /dispatch 추가) |
| 설정 | `src/config.py` | 수정 (제약조건 설정 추가) |

---

## 미해결 사항 (확인 필요)

1. **C2 하한 기준 — 기능도 vs 서비스등급?**
   명세서에 "1인 S급: 28만원"이라고만 되어있음. 이게 기능도 S급인지 서비스등급 S인지 확인 필요.

2. **상차지(depot) 좌표 데이터**
   거리비 계산에 필수. 권역별 물류센터 좌표를 어디서 받는지 — meta에 포함? 별도 마스터?

3. **소파 판단 기준**
   제품 카테고리에 "소파"가 있으면 되는지, 별도 플래그가 있는지.

4. **합배차 그룹 skill — 2인팀도 받아야 하나?**
   명세서: "우선 → 2인팀 배정, 부족 시 → 합배차". 2인팀이 합배차 그룹 skill을 가지면
   2인팀이 합배차 오더도 가져갈 수 있음. 의도인지 확인 필요.

5. **종료 시간 "제한 없음"의 실제 의미**
   VROOM에 time_window 필수. 23:59로 설정하면 되는지, 아니면 다음날 새벽까지?

6. **오더 소요시간 = service_minutes에 기본체류시간 포함인지 별도인지**
   시뮬레이터가 이미 합산해서 주는지, 래퍼가 +25분 해야 하는지.

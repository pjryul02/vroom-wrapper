# VROOM 커스텀 제약 조건 추가 가이드

> **레거시 문서 (v1.0~v2.0 기준)** — 최신 기술 문서는 [`docs/TECHNICAL-ARCHITECTURE.md`](TECHNICAL-ARCHITECTURE.md)를 참조하세요. 이 문서는 참고용으로만 보존됩니다.


## VROOM 기본 제약 조건 (Built-in Constraints)

VROOM이 기본적으로 지원하는 제약 조건들:

### 1. 시간 제약 (Time Constraints)

#### Time Windows (시간 윈도우)
```json
{
  "jobs": [{
    "id": 1,
    "location": [127.0276, 37.4979],
    "time_windows": [[32400, 36000]]  // 09:00 ~ 10:00 (초 단위)
  }],
  "vehicles": [{
    "id": 1,
    "time_window": [28800, 64800]  // 차량 운행 시간: 08:00 ~ 18:00
  }]
}
```

**코드 위치**: `/home/shawn/vroom/src/structures/vroom/time_window.h`
```cpp
struct TimeWindow {
  Duration start;  // 시작 시간
  Duration end;    // 종료 시간
  bool contains(Duration time) const;
};
```

#### Service Duration (작업 시간)
```json
{
  "jobs": [{
    "service": 300  // 5분 (300초) 작업 시간
  }]
}
```

#### Setup Time (준비 시간)
```json
{
  "jobs": [{
    "setup": 120  // 2분 준비 시간
  }]
}
```

---

### 2. 용량 제약 (Capacity Constraints)

#### Vehicle Capacity
```json
{
  "vehicles": [{
    "capacity": [100, 50]  // 다차원 용량: [무게, 부피]
  }],
  "jobs": [{
    "delivery": [10, 5],   // 배송량
    "pickup": [5, 3]       // 픽업량
  }]
}
```

**코드 위치**: `/home/shawn/vroom/src/structures/vroom/raw_route.cpp` (라인 161-201)
```cpp
bool RawRoute::is_valid_addition_for_capacity(
  const Input&,
  const Amount& pickup,
  const Amount& delivery,
  const Index rank) const {
  return (_fwd_peaks[rank] + delivery <= capacity) &&
         (_bwd_peaks[rank] + pickup <= capacity);
}
```

---

### 3. 기술 제약 (Skills Constraints)

```json
{
  "vehicles": [{
    "skills": [1, 3, 5]  // 차량이 보유한 기술
  }],
  "jobs": [{
    "skills": [3]  // 필요한 기술 - 차량은 반드시 3번 기술 보유해야 함
  }]
}
```

**코드 위치**: `/home/shawn/vroom/src/structures/vroom/job.h`
```cpp
Skills skills;  // 필요한 기술 집합
```

---

### 4. 우선순위 제약 (Priority Constraints)

```json
{
  "jobs": [{
    "id": 1,
    "priority": 10  // 높은 우선순위 (0-100)
  }, {
    "id": 2,
    "priority": 1   // 낮은 우선순위
  }]
}
```

---

### 5. 차량 범위 제약 (Vehicle Range Constraints)

#### Max Travel Time
```json
{
  "vehicles": [{
    "max_travel_time": 28800  // 최대 8시간 운행
  }]
}
```

#### Max Distance
```json
{
  "vehicles": [{
    "max_distance": 100000  // 최대 100km
  }]
}
```

**코드 위치**: `/home/shawn/vroom/src/structures/vroom/vehicle.h` (라인 131-144)
```cpp
bool ok_for_travel_time(Duration d) const {
  return d <= max_travel_time;
}

bool ok_for_distance(Distance d) const {
  return d <= max_distance;
}
```

---

### 6. 최대 작업 수 제약 (Max Tasks)

```json
{
  "vehicles": [{
    "max_tasks": 20  // 최대 20개 작업만 처리
  }]
}
```

---

### 7. 휴식 시간 제약 (Break Constraints)

```json
{
  "vehicles": [{
    "breaks": [{
      "id": 1,
      "time_windows": [[43200, 46800]],  // 12:00 ~ 13:00
      "service": 3600,                    // 1시간 휴식
      "max_load": [50, 25]                // 휴식 중 최대 허용 하중
    }]
  }]
}
```

**코드 위치**: `/home/shawn/vroom/src/structures/vroom/break.cpp`
```cpp
bool Break::is_valid_for_load(const Amount& load) const {
  return !max_load.has_value() || load <= max_load.value();
}
```

---

### 8. 픽업-배송 연결 제약 (Shipment/Precedence)

```json
{
  "shipments": [{
    "pickup": {
      "id": 1,
      "location": [126.9780, 37.5665]
    },
    "delivery": {
      "id": 2,
      "location": [127.0276, 37.4979]
    }
  }]
}
```

---

### 9. 위반 타입 (Violation Types)

**코드 위치**: `/home/shawn/vroom/src/structures/typedefs.h` (라인 145-157)

```cpp
enum class VIOLATION : std::uint8_t {
  LEAD_TIME,           // 시간 윈도우보다 일찍 도착
  DELAY,               // 시간 윈도우 초과
  LOAD,                // 하중 제약 위반
  MAX_TASKS,           // 최대 작업 수 초과
  SKILLS,              // 필요 기술 부족
  PRECEDENCE,          // 선행 조건 위반
  MISSING_BREAK,       // 휴식 시간 미충족
  MAX_TRAVEL_TIME,     // 최대 이동 시간 초과
  MAX_LOAD,            // 최대 하중 초과
  MAX_DISTANCE         // 최대 거리 초과
};
```

---

## 커스텀 제약 조건 추가 방법

이제 **기본 제약에 없는 새로운 제약**을 추가하는 방법을 설명합니다.

### 예시: "차량별 작업 지역 제한" 제약 추가

특정 차량은 특정 지역(구역)의 작업만 처리할 수 있다는 제약을 추가해봅시다.

---

## Step 1: 제약 조건 타입 정의

**파일**: `/home/shawn/vroom/src/structures/typedefs.h`

```cpp
enum class VIOLATION : std::uint8_t {
  LEAD_TIME,
  DELAY,
  LOAD,
  MAX_TASKS,
  SKILLS,
  PRECEDENCE,
  MISSING_BREAK,
  MAX_TRAVEL_TIME,
  MAX_LOAD,
  MAX_DISTANCE,
  ZONE_RESTRICTION  // 추가: 지역 제약 위반
};
```

---

## Step 2: 입력 데이터 구조 확장

### A. Job에 zone 필드 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/job.h`

```cpp
struct Job {
  Id id;
  Location location;
  Duration setup;
  Duration service;
  Amount delivery;
  Amount pickup;
  Skills skills;
  Priority priority;
  std::vector<TimeWindow> tws;
  std::string description;

  // 추가: 작업 지역 (예: 1=강남구, 2=서초구, 3=송파구)
  unsigned zone;  // 새 필드

  Job(Id id,
      const Location& location,
      Duration setup,
      Duration service,
      const Amount& delivery,
      const Amount& pickup,
      const Skills& skills,
      Priority priority,
      const std::vector<TimeWindow>& tws,
      const std::string& description,
      unsigned zone = 0);  // 생성자에 추가
};
```

**파일**: `/home/shawn/vroom/src/structures/vroom/job.cpp`

```cpp
Job::Job(Id id,
         const Location& location,
         Duration setup,
         Duration service,
         const Amount& delivery,
         const Amount& pickup,
         const Skills& skills,
         Priority priority,
         const std::vector<TimeWindow>& tws,
         const std::string& description,
         unsigned zone)
  : id(id),
    location(location),
    setup(setup),
    service(service),
    delivery(std::move(delivery)),
    pickup(std::move(pickup)),
    skills(std::move(skills)),
    priority(priority),
    tws(tws),
    description(description),
    zone(zone) {  // 초기화
}
```

### B. Vehicle에 allowed_zones 필드 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/vehicle.h`

```cpp
struct Vehicle {
  Id id;
  std::optional<Location> start;
  std::optional<Location> end;
  std::string profile;
  Amount capacity;
  Skills skills;
  TimeWindow tw;
  std::vector<Break> breaks;
  std::string description;
  UserCost cost_wrapper;
  Duration max_travel_time;
  Distance max_distance;
  unsigned max_tasks;
  std::vector<VehicleStep> steps;

  // 추가: 허용된 지역 집합
  std::unordered_set<unsigned> allowed_zones;  // 새 필드

  Vehicle(Id id,
          const std::optional<Location>& start,
          const std::optional<Location>& end,
          const std::string& profile,
          const Amount& capacity,
          const Skills& skills,
          const TimeWindow& tw,
          const std::vector<Break>& breaks,
          const std::string& description,
          const UserCost& cost_wrapper,
          const Duration max_travel_time,
          const Distance max_distance,
          const unsigned max_tasks,
          const std::vector<VehicleStep>& steps,
          const std::unordered_set<unsigned>& allowed_zones = {});  // 생성자에 추가
};
```

---

## Step 3: JSON 입력 파싱 수정

**파일**: `/home/shawn/vroom/src/structures/vroom/input/input.cpp`

Job 파싱 부분에 zone 추가:

```cpp
// input.cpp의 add_job 함수 수정
void Input::add_job(const rapidjson::Value& json_job) {
  // ... 기존 코드 ...

  // zone 파싱 (선택적)
  unsigned zone = 0;
  if (json_job.HasMember("zone")) {
    zone = json_job["zone"].GetUint();
  }

  jobs.emplace_back(job_id,
                    location,
                    setup,
                    service,
                    delivery,
                    pickup,
                    skills,
                    priority,
                    tws,
                    description,
                    zone);  // zone 전달
}
```

Vehicle 파싱 부분에 allowed_zones 추가:

```cpp
// input.cpp의 add_vehicle 함수 수정
void Input::add_vehicle(const rapidjson::Value& json_vehicle) {
  // ... 기존 코드 ...

  // allowed_zones 파싱 (선택적)
  std::unordered_set<unsigned> allowed_zones;
  if (json_vehicle.HasMember("allowed_zones")) {
    for (const auto& zone : json_vehicle["allowed_zones"].GetArray()) {
      allowed_zones.insert(zone.GetUint());
    }
  }

  vehicles.emplace_back(vehicle_id,
                       start,
                       end,
                       profile,
                       capacity,
                       skills,
                       tw,
                       breaks,
                       description,
                       cost_wrapper,
                       max_travel_time,
                       max_distance,
                       max_tasks,
                       steps,
                       allowed_zones);  // allowed_zones 전달
}
```

---

## Step 4: 제약 조건 검증 로직 추가

### A. Vehicle 클래스에 검증 메서드 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/vehicle.h`

```cpp
struct Vehicle {
  // ... 기존 필드 ...
  std::unordered_set<unsigned> allowed_zones;

  // 새 메서드: 차량이 해당 zone의 작업을 처리할 수 있는지 확인
  bool can_serve_zone(unsigned zone) const {
    // allowed_zones가 비어있으면 모든 지역 가능
    if (allowed_zones.empty()) {
      return true;
    }
    // 지정된 zone이 allowed_zones에 있는지 확인
    return allowed_zones.find(zone) != allowed_zones.end();
  }
};
```

### B. Input 클래스에 호환성 체크 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/input/input.h`

```cpp
class Input {
public:
  // ... 기존 메서드 ...

  // 새 메서드: 차량이 작업을 처리할 수 있는지 확인 (zone 포함)
  bool vehicle_ok_with_job(Index v_rank, Index j_rank) const {
    const auto& vehicle = vehicles[v_rank];
    const auto& job = jobs[j_rank];

    // 기존 체크 (skills 등)
    if (!vehicle.has_skills(job.skills)) {
      return false;
    }

    // 새로운 zone 체크
    if (!vehicle.can_serve_zone(job.zone)) {
      return false;
    }

    return true;
  }
};
```

---

## Step 5: Operator의 is_valid() 수정

모든 local search operator들이 zone 제약을 확인하도록 수정합니다.

**예시: Relocate Operator**

**파일**: `/home/shawn/vroom/src/problems/cvrp/operators/relocate.cpp`

```cpp
bool Relocate::is_valid() {
  assert(gain_computed);

  // 기존 검증
  bool basic_valid = is_valid_for_source_range_bounds() &&
                     is_valid_for_target_range_bounds() &&
                     target.is_valid_addition_for_capacity(_input,
                                                           _input.jobs[s_route[s_rank]].pickup,
                                                           _input.jobs[s_route[s_rank]].delivery,
                                                           t_rank);

  if (!basic_valid) {
    return false;
  }

  // 새로운 zone 검증 추가
  Index job_rank = s_route[s_rank];
  if (!_input.vehicle_ok_with_job(t_vehicle, job_rank)) {
    return false;  // Zone 제약 위반
  }

  return true;
}
```

모든 operator 파일에 동일하게 적용:
- `relocate.cpp`
- `swap_star.cpp`
- `cross_exchange.cpp`
- `mixed_exchange.cpp`
- `two_opt.cpp`
- `or_opt.cpp`
- `intra_relocate.cpp`
- ... 등

---

## Step 6: 초기 해 생성 시 제약 확인

**파일**: `/home/shawn/vroom/src/structures/vroom/input/input.cpp`

```cpp
// 초기 해 생성 시 vehicle-job 호환성 확인
void Input::set_vehicle_to_job_compatibility() {
  vehicle_to_job_compatibility.resize(vehicles.size());

  for (Index v = 0; v < vehicles.size(); ++v) {
    vehicle_to_job_compatibility[v].resize(jobs.size());

    for (Index j = 0; j < jobs.size(); ++j) {
      // Zone 제약 포함한 호환성 체크
      vehicle_to_job_compatibility[v][j] = vehicle_ok_with_job(v, j);
    }
  }
}
```

---

## Step 7: Violation 추적 및 보고

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/route.cpp`

경로 검증 시 zone violation을 추적:

```cpp
Violations Route::get_violations() const {
  Violations v;

  for (const auto& step : steps) {
    if (step.job_type == JOB_TYPE::SINGLE) {
      const auto& job = _input.jobs[step.rank];
      const auto& vehicle = _input.vehicles[this->vehicle];

      // Zone violation 체크
      if (!vehicle.can_serve_zone(job.zone)) {
        v.types.insert(VIOLATION::ZONE_RESTRICTION);
      }
    }
  }

  return v;
}
```

---

## Step 8: 출력 포맷에 violation 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/solution.cpp`

JSON 출력에 zone violation 포함:

```cpp
void Solution::write_violations_to_json(rapidjson::Writer<rapidjson::StringBuffer>& writer,
                                       const Violations& v) const {
  writer.StartArray();

  for (const auto& violation : v.types) {
    switch (violation) {
      case VIOLATION::ZONE_RESTRICTION:
        writer.String("zone_restriction");
        break;
      // ... 기타 케이스들 ...
    }
  }

  writer.EndArray();
}
```

---

## Step 9: 빌드 및 테스트

```bash
cd /home/shawn/vroom

# 빌드
make clean
make -j$(nproc)

# 테스트용 JSON 생성
cat > test_zone_constraint.json << 'EOF'
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "end": [126.9780, 37.5665],
      "allowed_zones": [1, 2]
    },
    {
      "id": 2,
      "start": [127.0594, 37.5140],
      "end": [127.0594, 37.5140],
      "allowed_zones": [3, 4]
    }
  ],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "zone": 1
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "zone": 3
    },
    {
      "id": 3,
      "location": [126.9910, 37.5512],
      "zone": 1
    },
    {
      "id": 4,
      "location": [127.0100, 37.5400],
      "zone": 4
    }
  ]
}
EOF

# 실행 테스트
./bin/vroom -i test_zone_constraint.json -g
```

---

## Step 10: Docker 이미지 재빌드

커스텀 VROOM을 Docker에 통합:

```bash
cd /home/shawn/vroom-docker

# Dockerfile 수정하여 커스텀 VROOM 사용
cat > Dockerfile.custom << 'EOF'
FROM debian:trixie-slim AS builder
WORKDIR /

RUN apt-get -y update && apt-get -y install \
    git-core build-essential g++ \
    libssl-dev libasio-dev libglpk-dev pkg-config

# 로컬 커스텀 VROOM 복사
COPY ../vroom /vroom
RUN cd /vroom && make -j$(nproc)

ARG VROOM_EXPRESS_RELEASE=master
RUN git clone --branch $VROOM_EXPRESS_RELEASE --single-branch \
    https://github.com/VROOM-Project/vroom-express.git

FROM node:20-bookworm-slim AS runstage
COPY --from=builder /vroom-express/. /vroom-express
COPY --from=builder /vroom/bin/vroom /usr/local/bin

WORKDIR /vroom-express
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libssl3 curl libglpk40 && \
    rm -rf /var/lib/apt/lists/* && \
    npm install && \
    mkdir /conf

COPY ./docker-entrypoint.sh /docker-entrypoint.sh
ENV VROOM_DOCKER=osrm VROOM_LOG=/conf

HEALTHCHECK --start-period=10s CMD curl --fail -s http://localhost:3000/health || exit 1
EXPOSE 3000
ENTRYPOINT ["/bin/bash"]
CMD ["/docker-entrypoint.sh"]
EOF

# 빌드
docker build -f Dockerfile.custom -t vroom-custom-zone:latest .

# docker-compose.yml 수정
# services:
#   vroom:
#     image: vroom-custom-zone:latest

# 재시작
cd /home/shawn
docker-compose down
docker-compose up -d
```

---

## 다른 커스텀 제약 조건 예시

### 1. 작업 간 최소/최대 시간 간격

```cpp
// Job에 추가
struct Job {
  std::optional<Duration> min_time_after_previous;  // 이전 작업 후 최소 시간
  std::optional<Duration> max_time_after_previous;  // 이전 작업 후 최대 시간
};

// TWRoute에서 검증
bool TWRoute::is_valid_for_time_gaps(Index rank) const {
  if (rank == 0) return true;

  const auto& current_job = input.jobs[route[rank]];
  Duration gap = earliest[rank] - (earliest[rank-1] + action_time[rank-1]);

  if (current_job.min_time_after_previous.has_value() &&
      gap < current_job.min_time_after_previous.value()) {
    return false;
  }

  if (current_job.max_time_after_previous.has_value() &&
      gap > current_job.max_time_after_previous.value()) {
    return false;
  }

  return true;
}
```

### 2. 차량별 작업 유형 제한

```cpp
// Job에 작업 타입 추가
enum class JOB_CATEGORY {
  DELIVERY,
  INSTALLATION,
  REPAIR,
  INSPECTION
};

struct Job {
  JOB_CATEGORY category;
};

// Vehicle에 허용 타입 추가
struct Vehicle {
  std::unordered_set<JOB_CATEGORY> allowed_categories;

  bool can_do_job_category(JOB_CATEGORY cat) const {
    return allowed_categories.empty() ||
           allowed_categories.find(cat) != allowed_categories.end();
  }
};
```

### 3. 작업 시퀀스 제약 (특정 작업 후에만 가능)

```cpp
struct Job {
  std::vector<Id> must_come_after;  // 이 작업들이 먼저 완료되어야 함
};

// Route 검증
bool Route::is_valid_sequence() const {
  std::unordered_set<Id> completed_jobs;

  for (const auto& step : steps) {
    if (step.job_type == JOB_TYPE::SINGLE) {
      const auto& job = input.jobs[step.rank];

      // 선행 작업 확인
      for (const auto& required_job_id : job.must_come_after) {
        if (completed_jobs.find(required_job_id) == completed_jobs.end()) {
          return false;  // 선행 작업이 완료되지 않음
        }
      }

      completed_jobs.insert(job.id);
    }
  }

  return true;
}
```

### 4. 시간대별 도로 통행 제약

```cpp
struct Vehicle {
  // 특정 시간대에 특정 도로/지역 통행 불가
  std::map<TimeWindow, std::unordered_set<unsigned>> time_restricted_zones;

  bool can_visit_zone_at_time(unsigned zone, Duration time) const {
    for (const auto& [tw, restricted_zones] : time_restricted_zones) {
      if (tw.contains(time) && restricted_zones.find(zone) != restricted_zones.end()) {
        return false;  // 해당 시간에 해당 zone 방문 불가
      }
    }
    return true;
  }
};
```

---

## 요약

### 커스텀 제약 추가 체크리스트

1. [ ] `typedefs.h`에 새 VIOLATION 타입 정의
2. [ ] 관련 구조체(Job/Vehicle)에 필드 추가
3. [ ] JSON 파싱 코드 수정 (`input.cpp`)
4. [ ] 검증 메서드 추가 (해당 구조체에)
5. [ ] `Input::vehicle_ok_with_job()` 또는 유사 메서드에 체크 추가
6. [ ] 모든 operator의 `is_valid()` 수정
7. [ ] 초기 해 생성 로직 수정
8. [ ] Violation 추적 및 보고 코드 추가
9. [ ] JSON 출력 포맷에 violation 추가
10. [ ] 빌드 및 테스트
11. [ ] Docker 이미지 재빌드

### 수정해야 할 핵심 파일들

- `src/structures/typedefs.h` - 타입 정의
- `src/structures/vroom/job.h/cpp` - Job 구조체
- `src/structures/vroom/vehicle.h/cpp` - Vehicle 구조체
- `src/structures/vroom/input/input.h/cpp` - 입력 파싱 및 호환성
- `src/problems/*/operators/*.cpp` - 모든 operator들
- `src/structures/vroom/solution/route.cpp` - Violation 추적
- `src/structures/vroom/solution/solution.cpp` - JSON 출력

이 가이드를 따라하면 VROOM에 완전히 새로운 커스텀 제약 조건을 추가할 수 있습니다!

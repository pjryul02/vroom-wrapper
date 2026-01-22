# 커스텀 제약 조건의 Violation 보고 시스템 구현 가이드

## 핵심 목표

**새로운 제약을 추가했을 때, 그 제약이 위반되면 사용자에게 명확한 사유를 설명**

예시:
```json
{
  "unassigned": [
    {
      "id": 5,
      "location": [127.02, 37.53],
      "type": "job",
      "violation_reason": "zone_restriction",
      "details": {
        "job_zone": 3,
        "vehicle_allowed_zones": [1, 2],
        "message": "차량 1은 지역 3의 작업을 처리할 수 없습니다"
      }
    }
  ]
}
```

---

## Step-by-Step 구현: "지역 제약" 예시

### Step 1: Violation 타입 정의

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

  // 커스텀 제약 추가
  ZONE_RESTRICTION,      // 지역 제약 위반
  TIME_SLOT_CONFLICT,    // 시간대 충돌
  VEHICLE_TYPE_MISMATCH, // 차량 유형 불일치
  EQUIPMENT_MISSING      // 필요 장비 부족
};
```

---

### Step 2: Violation 상세 정보 구조체 추가

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/violations.h`

```cpp
#include <string>
#include <optional>
#include <vector>

// Violation 상세 정보
struct ViolationDetail {
  VIOLATION type;
  std::optional<std::string> message;         // 사람이 읽을 수 있는 메시지
  std::optional<std::string> job_info;        // 작업 관련 정보
  std::optional<std::string> vehicle_info;    // 차량 관련 정보

  // Zone 제약용
  std::optional<unsigned> job_zone;
  std::optional<std::vector<unsigned>> vehicle_allowed_zones;

  // Time slot 제약용
  std::optional<Duration> job_time_start;
  std::optional<Duration> job_time_end;
  std::optional<Duration> vehicle_available_from;
  std::optional<Duration> vehicle_available_to;

  ViolationDetail(VIOLATION type) : type(type) {}
};

struct Violations {
  UserDuration lead_time;
  UserDuration delay;
  std::unordered_set<VIOLATION> types;

  // 추가: 상세 정보 목록
  std::vector<ViolationDetail> details;

  Violations();
  Violations(const UserDuration lead_time,
             const UserDuration delay,
             std::unordered_set<VIOLATION>&& types);

  // 새 메서드: violation detail 추가
  void add_detail(const ViolationDetail& detail);

  Violations& operator+=(const Violations& rhs);
};
```

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/violations.cpp`

```cpp
void Violations::add_detail(const ViolationDetail& detail) {
  types.insert(detail.type);
  details.push_back(detail);
}

Violations& Violations::operator+=(const Violations& rhs) {
  this->lead_time += rhs.lead_time;
  this->delay += rhs.delay;
  for (const auto t : rhs.types) {
    this->types.insert(t);
  }
  // 상세 정보도 병합
  for (const auto& d : rhs.details) {
    this->details.push_back(d);
  }
  return *this;
}
```

---

### Step 3: Input 클래스에 제약 위반 사유 추적

**파일**: `/home/shawn/vroom/src/structures/vroom/input/input.h`

```cpp
class Input {
private:
  // 제약 위반 사유 추적 맵
  std::unordered_map<Index, std::vector<ViolationDetail>>
    job_violation_reasons;  // job_rank -> violations

public:
  // 기존 메서드
  bool vehicle_ok_with_job(Index v_rank, Index j_rank) const;

  // 새 메서드: 제약 위반 사유와 함께 체크
  bool vehicle_ok_with_job_detailed(Index v_rank,
                                     Index j_rank,
                                     ViolationDetail& out_violation) const {
    const auto& vehicle = vehicles[v_rank];
    const auto& job = jobs[j_rank];

    // 1. Skills 체크
    if (!vehicle.has_skills(job.skills)) {
      out_violation = ViolationDetail(VIOLATION::SKILLS);
      out_violation.message = "Vehicle " + std::to_string(vehicle.id) +
                             " lacks required skills for job " +
                             std::to_string(job.id);
      out_violation.job_info = "Required skills: " +
                              format_skills(job.skills);
      out_violation.vehicle_info = "Vehicle skills: " +
                                  format_skills(vehicle.skills);
      return false;
    }

    // 2. Zone 체크 (커스텀)
    if (!vehicle.can_serve_zone(job.zone)) {
      out_violation = ViolationDetail(VIOLATION::ZONE_RESTRICTION);
      out_violation.message = "Vehicle " + std::to_string(vehicle.id) +
                             " cannot serve zone " + std::to_string(job.zone);
      out_violation.job_zone = job.zone;
      out_violation.vehicle_allowed_zones =
        std::vector<unsigned>(vehicle.allowed_zones.begin(),
                            vehicle.allowed_zones.end());
      out_violation.job_info = "Job zone: " + std::to_string(job.zone);
      out_violation.vehicle_info = "Allowed zones: " +
                                  format_zones(vehicle.allowed_zones);
      return false;
    }

    return true;
  }

  // 특정 작업의 위반 사유 가져오기
  std::vector<ViolationDetail> get_job_violation_reasons(Index j_rank) const {
    auto it = job_violation_reasons.find(j_rank);
    if (it != job_violation_reasons.end()) {
      return it->second;
    }
    return {};
  }

  // 위반 사유 기록
  void record_job_violation(Index j_rank, const ViolationDetail& detail) {
    job_violation_reasons[j_rank].push_back(detail);
  }

private:
  std::string format_skills(const Skills& skills) const {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& s : skills) {
      if (!first) oss << ", ";
      oss << s;
      first = false;
    }
    oss << "]";
    return oss.str();
  }

  std::string format_zones(const std::unordered_set<unsigned>& zones) const {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& z : zones) {
      if (!first) oss << ", ";
      oss << z;
      first = false;
    }
    oss << "]";
    return oss.str();
  }
};
```

---

### Step 4: 초기 해 생성 시 위반 사유 수집

**파일**: `/home/shawn/vroom/src/structures/vroom/input/input.cpp`

```cpp
void Input::set_vehicle_to_job_compatibility() {
  vehicle_to_job_compatibility.resize(vehicles.size());
  job_violation_reasons.clear();

  for (Index v = 0; v < vehicles.size(); ++v) {
    vehicle_to_job_compatibility[v].resize(jobs.size());

    for (Index j = 0; j < jobs.size(); ++j) {
      ViolationDetail violation(VIOLATION::SKILLS);

      // 상세 정보와 함께 호환성 체크
      bool compatible = vehicle_ok_with_job_detailed(v, j, violation);
      vehicle_to_job_compatibility[v][j] = compatible;

      // 호환되지 않으면 사유 기록
      if (!compatible) {
        record_job_violation(j, violation);
      }
    }
  }
}
```

---

### Step 5: Unassigned Jobs에 Violation Reason 포함

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/solution.h`

```cpp
struct Solution {
  unsigned code;
  std::vector<Route> routes;
  std::vector<Job> unassigned;
  Summary summary;

  // 추가: unassigned job별 violation reasons
  std::unordered_map<Id, std::vector<ViolationDetail>>
    unassigned_reasons;
};
```

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/solution.cpp`

솔루션 생성 시 unassigned job의 사유 수집:

```cpp
Solution::Solution(const Input& input,
                   unsigned code,
                   std::vector<Route>&& routes)
  : code(code), routes(std::move(routes)) {

  // Unassigned jobs 수집
  std::unordered_set<Index> assigned_jobs;
  for (const auto& route : this->routes) {
    for (const auto& step : route.steps) {
      if (step.job_type == JOB_TYPE::SINGLE) {
        assigned_jobs.insert(step.rank);
      }
    }
  }

  // 할당되지 않은 작업 및 사유 수집
  for (Index j = 0; j < input.jobs.size(); ++j) {
    if (assigned_jobs.find(j) == assigned_jobs.end()) {
      unassigned.push_back(input.jobs[j]);

      // 위반 사유 가져오기
      auto reasons = input.get_job_violation_reasons(j);
      if (!reasons.empty()) {
        unassigned_reasons[input.jobs[j].id] = reasons;
      }
    }
  }
}
```

---

### Step 6: JSON 출력에 Violation Detail 포함

**파일**: `/home/shawn/vroom/src/structures/vroom/solution/solution.cpp`

```cpp
void Solution::write_to_json(rapidjson::Writer<rapidjson::StringBuffer>& writer,
                             bool geometry) const {
  writer.StartObject();

  // ... 기존 코드 ...

  // Unassigned jobs with reasons
  writer.Key("unassigned");
  writer.StartArray();

  for (const auto& job : unassigned) {
    writer.StartObject();

    writer.Key("id");
    writer.Uint(job.id);

    writer.Key("location");
    writer.StartArray();
    writer.Double(job.location.lon());
    writer.Double(job.location.lat());
    writer.EndArray();

    writer.Key("type");
    writer.String("job");

    // 추가: Violation reasons
    auto it = unassigned_reasons.find(job.id);
    if (it != unassigned_reasons.end() && !it->second.empty()) {
      writer.Key("violation_reasons");
      writer.StartArray();

      for (const auto& detail : it->second) {
        writer.StartObject();

        // Violation type
        writer.Key("type");
        writer.String(get_violation_type_string(detail.type).c_str());

        // Message
        if (detail.message.has_value()) {
          writer.Key("message");
          writer.String(detail.message.value().c_str());
        }

        // Job info
        if (detail.job_info.has_value()) {
          writer.Key("job_info");
          writer.String(detail.job_info.value().c_str());
        }

        // Vehicle info
        if (detail.vehicle_info.has_value()) {
          writer.Key("vehicle_info");
          writer.String(detail.vehicle_info.value().c_str());
        }

        // Zone-specific details
        if (detail.job_zone.has_value()) {
          writer.Key("job_zone");
          writer.Uint(detail.job_zone.value());
        }

        if (detail.vehicle_allowed_zones.has_value()) {
          writer.Key("vehicle_allowed_zones");
          writer.StartArray();
          for (const auto& zone : detail.vehicle_allowed_zones.value()) {
            writer.Uint(zone);
          }
          writer.EndArray();
        }

        // Time slot specific details
        if (detail.job_time_start.has_value()) {
          writer.Key("job_time_window");
          writer.StartArray();
          writer.Uint(detail.job_time_start.value());
          writer.Uint(detail.job_time_end.value());
          writer.EndArray();
        }

        if (detail.vehicle_available_from.has_value()) {
          writer.Key("vehicle_time_window");
          writer.StartArray();
          writer.Uint(detail.vehicle_available_from.value());
          writer.Uint(detail.vehicle_available_to.value());
          writer.EndArray();
        }

        writer.EndObject();
      }

      writer.EndArray();
    }

    writer.EndObject();
  }

  writer.EndArray();

  // ... 나머지 코드 ...

  writer.EndObject();
}

// Helper 함수
std::string Solution::get_violation_type_string(VIOLATION type) const {
  switch (type) {
    case VIOLATION::LEAD_TIME: return "lead_time";
    case VIOLATION::DELAY: return "delay";
    case VIOLATION::LOAD: return "load";
    case VIOLATION::MAX_TASKS: return "max_tasks";
    case VIOLATION::SKILLS: return "skills";
    case VIOLATION::PRECEDENCE: return "precedence";
    case VIOLATION::MISSING_BREAK: return "missing_break";
    case VIOLATION::MAX_TRAVEL_TIME: return "max_travel_time";
    case VIOLATION::MAX_LOAD: return "max_load";
    case VIOLATION::MAX_DISTANCE: return "max_distance";
    case VIOLATION::ZONE_RESTRICTION: return "zone_restriction";
    case VIOLATION::TIME_SLOT_CONFLICT: return "time_slot_conflict";
    case VIOLATION::VEHICLE_TYPE_MISMATCH: return "vehicle_type_mismatch";
    case VIOLATION::EQUIPMENT_MISSING: return "equipment_missing";
    default: return "unknown";
  }
}
```

---

## 결과 예시

### 입력

```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "end": [126.9780, 37.5665],
      "skills": [1, 2],
      "allowed_zones": [1, 2]
    },
    {
      "id": 2,
      "start": [127.0594, 37.5140],
      "end": [127.0594, 37.5140],
      "skills": [2, 3],
      "allowed_zones": [3, 4]
    }
  ],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "zone": 1,
      "skills": [1]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "zone": 3,
      "skills": [3]
    },
    {
      "id": 3,
      "location": [126.9910, 37.5512],
      "zone": 5,
      "skills": [1]
    }
  ]
}
```

### 출력 (개선된 버전)

```json
{
  "code": 0,
  "summary": {
    "cost": 450,
    "routes": 2,
    "unassigned": 1
  },
  "unassigned": [
    {
      "id": 3,
      "location": [126.991, 37.5512],
      "type": "job",
      "violation_reasons": [
        {
          "type": "zone_restriction",
          "message": "차량 1은 지역 5의 작업을 처리할 수 없습니다",
          "job_info": "Job zone: 5",
          "vehicle_info": "Allowed zones: [1, 2]",
          "job_zone": 5,
          "vehicle_allowed_zones": [1, 2]
        },
        {
          "type": "zone_restriction",
          "message": "차량 2는 지역 5의 작업을 처리할 수 없습니다",
          "job_info": "Job zone: 5",
          "vehicle_info": "Allowed zones: [3, 4]",
          "job_zone": 5,
          "vehicle_allowed_zones": [3, 4]
        }
      ]
    }
  ],
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start"},
        {"type": "job", "id": 1},
        {"type": "end"}
      ]
    },
    {
      "vehicle": 2,
      "steps": [
        {"type": "start"},
        {"type": "job", "id": 2},
        {"type": "end"}
      ]
    }
  ]
}
```

---

## 다른 커스텀 제약 예시

### 1. 시간대 충돌 (TIME_SLOT_CONFLICT)

```cpp
// Vehicle에 unavailable time slots 추가
struct Vehicle {
  std::vector<TimeWindow> unavailable_slots;

  bool is_available_at(Duration time) const {
    for (const auto& slot : unavailable_slots) {
      if (slot.contains(time)) {
        return false;
      }
    }
    return true;
  }
};

// 체크 로직
ViolationDetail detail(VIOLATION::TIME_SLOT_CONFLICT);
detail.message = "Vehicle " + std::to_string(vehicle.id) +
                " is unavailable during job time window";
detail.job_time_start = job.tws[0].start;
detail.job_time_end = job.tws[0].end;
detail.vehicle_available_from = vehicle.tw.start;
detail.vehicle_available_to = vehicle.tw.end;
```

**출력**:
```json
{
  "violation_reasons": [{
    "type": "time_slot_conflict",
    "message": "Vehicle 1 is unavailable during job time window",
    "job_time_window": [32400, 36000],
    "vehicle_time_window": [28800, 32400]
  }]
}
```

### 2. 차량 유형 불일치 (VEHICLE_TYPE_MISMATCH)

```cpp
enum class VehicleType {
  TRUCK,
  VAN,
  MOTORCYCLE,
  BICYCLE
};

struct Job {
  std::optional<VehicleType> required_vehicle_type;
};

struct Vehicle {
  VehicleType type;
};

// 체크 로직
if (job.required_vehicle_type.has_value() &&
    job.required_vehicle_type.value() != vehicle.type) {
  ViolationDetail detail(VIOLATION::VEHICLE_TYPE_MISMATCH);
  detail.message = "Job requires " +
                  get_vehicle_type_string(job.required_vehicle_type.value()) +
                  " but vehicle is " +
                  get_vehicle_type_string(vehicle.type);
  return false;
}
```

**출력**:
```json
{
  "violation_reasons": [{
    "type": "vehicle_type_mismatch",
    "message": "Job requires TRUCK but vehicle is VAN"
  }]
}
```

### 3. 장비 부족 (EQUIPMENT_MISSING)

```cpp
enum class Equipment {
  REFRIGERATION,
  LIFT_GATE,
  HAZMAT_CERTIFIED,
  OVERSIZED_CAPACITY
};

struct Job {
  std::unordered_set<Equipment> required_equipment;
};

struct Vehicle {
  std::unordered_set<Equipment> available_equipment;
};

// 체크 로직
std::vector<Equipment> missing;
for (const auto& req : job.required_equipment) {
  if (vehicle.available_equipment.find(req) ==
      vehicle.available_equipment.end()) {
    missing.push_back(req);
  }
}

if (!missing.empty()) {
  ViolationDetail detail(VIOLATION::EQUIPMENT_MISSING);
  detail.message = "Vehicle lacks required equipment: " +
                  format_equipment_list(missing);
  return false;
}
```

**출력**:
```json
{
  "violation_reasons": [{
    "type": "equipment_missing",
    "message": "Vehicle lacks required equipment: REFRIGERATION, LIFT_GATE"
  }]
}
```

---

## API 응답 처리 (클라이언트 측)

### Python 예시

```python
import requests

response = requests.post('http://localhost:3000/', json={
    "vehicles": [...],
    "jobs": [...]
})

result = response.json()

# Unassigned jobs와 사유 출력
if result['unassigned']:
    print("할당 실패한 작업:")
    for job in result['unassigned']:
        print(f"\n작업 ID {job['id']}:")

        if 'violation_reasons' in job:
            for reason in job['violation_reasons']:
                print(f"  ❌ {reason['type']}")
                print(f"     {reason['message']}")

                # Zone 관련 상세 정보
                if 'job_zone' in reason:
                    print(f"     작업 지역: {reason['job_zone']}")
                    print(f"     차량 허용 지역: {reason['vehicle_allowed_zones']}")

                # Time 관련 상세 정보
                if 'job_time_window' in reason:
                    print(f"     작업 시간: {reason['job_time_window']}")
                    print(f"     차량 운행 시간: {reason['vehicle_time_window']}")
```

### JavaScript 예시

```javascript
const result = await fetch('http://localhost:3000/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({vehicles: [...], jobs: [...]})
}).then(r => r.json());

// Unassigned jobs 처리
result.unassigned?.forEach(job => {
  console.log(`\n작업 ${job.id} 할당 실패:`);

  job.violation_reasons?.forEach(reason => {
    console.log(`  ❌ ${reason.type}: ${reason.message}`);

    // 추가 정보 출력
    if (reason.job_zone) {
      console.log(`     작업 지역: ${reason.job_zone}`);
      console.log(`     허용 지역: ${reason.vehicle_allowed_zones.join(', ')}`);
    }
  });
});
```

---

## 다국어 지원

```cpp
// 다국어 메시지 생성
std::string get_violation_message(VIOLATION type,
                                  const std::string& lang,
                                  const ViolationDetail& detail) {
  if (lang == "ko") {
    switch (type) {
      case VIOLATION::ZONE_RESTRICTION:
        return "차량이 해당 지역의 작업을 처리할 수 없습니다";
      case VIOLATION::SKILLS:
        return "차량에 필요한 기술이 없습니다";
      case VIOLATION::TIME_SLOT_CONFLICT:
        return "차량이 해당 시간대에 사용 불가능합니다";
      // ...
    }
  } else {  // English
    switch (type) {
      case VIOLATION::ZONE_RESTRICTION:
        return "Vehicle cannot serve jobs in this zone";
      case VIOLATION::SKILLS:
        return "Vehicle lacks required skills";
      case VIOLATION::TIME_SLOT_CONFLICT:
        return "Vehicle is unavailable during this time";
      // ...
    }
  }
}
```

---

## 요약

### 구현 체크리스트

- [x] **Step 1**: `typedefs.h`에 새 VIOLATION 타입 정의
- [x] **Step 2**: `ViolationDetail` 구조체 생성 (상세 정보 포함)
- [x] **Step 3**: `Input` 클래스에 `vehicle_ok_with_job_detailed()` 추가
- [x] **Step 4**: 초기 해 생성 시 위반 사유 수집 및 저장
- [x] **Step 5**: `Solution`에 `unassigned_reasons` 맵 추가
- [x] **Step 6**: JSON 출력에 `violation_reasons` 배열 포함

### 핵심 개념

1. **ViolationDetail**: 단순 enum이 아닌 **상세 정보 구조체**
2. **job_violation_reasons**: 작업별 위반 사유 추적 맵
3. **JSON 출력**: unassigned job마다 `violation_reasons` 배열 제공
4. **다국어**: 메시지를 언어별로 생성 가능

이제 사용자는 **왜 작업이 할당되지 않았는지** 명확하게 알 수 있습니다!

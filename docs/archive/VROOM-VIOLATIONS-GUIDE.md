# VROOM Violations (제약 위반) 완벽 가이드

> **레거시 문서 (v1.0~v2.0 기준)** — 최신 기술 문서는 [`docs/TECHNICAL-ARCHITECTURE.md`](TECHNICAL-ARCHITECTURE.md)를 참조하세요. 이 문서는 참고용으로만 보존됩니다.


## 개요

VROOM은 제약 조건을 처리하는 방식이 2가지입니다:

1. **Hard Constraints (하드 제약)**: 절대 위반 불가 → 작업을 `unassigned`로 남김
2. **Soft Constraints (소프트 제약)**: 위반 가능하지만 패널티 → `violations` 배열에 기록

---

## VROOM의 Violation 타입 10가지

코드 위치: `/home/shawn/vroom/src/structures/typedefs.h`

```cpp
enum class VIOLATION : std::uint8_t {
  LEAD_TIME,           // 시간 윈도우보다 일찍 도착
  DELAY,               // 시간 윈도우 늦게 도착
  LOAD,                // 용량 초과
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

## Hard vs Soft Constraints

### Hard Constraints (항상 준수)

VROOM이 **절대 위반하지 않는** 제약들:

1. **Skills**: 차량이 필요 기술이 없으면 할당 불가
2. **Capacity**: 용량 초과 불가
3. **Max Tasks**: 최대 작업 수 초과 불가
4. **Shipment Precedence**: 픽업 전에 배송 불가

이런 제약을 만족할 수 없으면 작업은 `unassigned`에 남습니다.

```json
{
  "unassigned": [
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "type": "job"
    }
  ]
}
```

### Soft Constraints (위반 가능, 패널티 있음)

특정 상황에서 **위반을 허용하되 기록하는** 제약들:

1. **Time Windows**: DELAY, LEAD_TIME
2. **Vehicle Range**: MAX_TRAVEL_TIME, MAX_DISTANCE
3. **Breaks**: MISSING_BREAK

이런 제약 위반 시 `violations` 배열에 기록됩니다.

---

## Violations 발생 케이스

### 케이스 1: 입력 데이터에 이미 경로가 지정된 경우

VROOM은 초기 경로(`vehicles[].steps`)가 주어지면 이를 검증하고 violation을 보고합니다.

```json
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "time_window": [28800, 36000],
    "steps": [
      {"type": "start"},
      {"type": "job", "id": 1},
      {"type": "job", "id": 2},
      {"type": "end"}
    ]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "time_windows": [[32400, 34200]]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "time_windows": [[64800, 72000]]
    }
  ]
}
```

**응답**: Job 2의 시간 윈도우를 만족할 수 없음 → `DELAY` violation

```json
{
  "routes": [{
    "vehicle": 1,
    "violations": [
      {
        "type": "delay",
        "duration": 28800
      }
    ],
    "steps": [...]
  }]
}
```

### 케이스 2: 모든 차량이 제약을 위반할 때

차량 2대가 모두 시간 제약을 위반하지만, 그나마 덜 위반하는 차량에 할당:

```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "time_window": [28800, 32400]
    },
    {
      "id": 2,
      "start": [127.0594, 37.5140],
      "time_window": [28800, 34200]
    }
  ],
  "jobs": [{
    "id": 1,
    "location": [127.0276, 37.4979],
    "time_windows": [[43200, 46800]]
  }]
}
```

### 케이스 3: `-c` 옵션 사용 (Plan Mode)

`-c` 옵션으로 실행하면 VROOM이 제약 확인만 하고 최적화하지 않습니다.

```bash
vroom -i input.json -c
```

---

## Violations 응답 구조

### Summary Level Violations

전체 솔루션의 violation 요약:

```json
{
  "summary": {
    "violations": [
      {
        "type": "delay",
        "duration": 3600
      }
    ]
  }
}
```

### Route Level Violations

각 경로별 violation:

```json
{
  "routes": [{
    "vehicle": 1,
    "violations": [
      {
        "type": "delay",
        "duration": 1800
      },
      {
        "type": "missing_break"
      }
    ]
  }]
}
```

### Step Level Violations

각 작업별 violation:

```json
{
  "steps": [{
    "type": "job",
    "id": 1,
    "arrival": 37000,
    "violations": [
      {
        "type": "delay",
        "duration": 800
      }
    ]
  }]
}
```

---

## Violation 타입별 상세 설명

### 1. DELAY (지연)

**의미**: 작업의 시간 윈도우 종료 후에 도착

```json
{
  "type": "delay",
  "duration": 3600  // 1시간 늦음
}
```

**예시**:
- 작업 시간 윈도우: 09:00 - 10:00
- 실제 도착: 11:00
- Delay: 3600초 (1시간)

### 2. LEAD_TIME (조기 도착)

**의미**: 작업의 시간 윈도우 시작 전에 도착 (대기 필요)

```json
{
  "type": "lead_time",
  "duration": 1800  // 30분 일찍 도착
}
```

**예시**:
- 작업 시간 윈도우: 10:00 - 11:00
- 실제 도착: 09:30
- Lead time: 1800초 (30분 대기)

### 3. LOAD (하중 초과)

**의미**: 용량 제약 위반

```json
{
  "type": "load"
}
```

**예시**:
- 차량 용량: [100]
- 특정 시점 하중: [120]

### 4. MAX_TASKS (최대 작업 수 초과)

```json
{
  "type": "max_tasks"
}
```

### 5. SKILLS (기술 부족)

```json
{
  "type": "skills"
}
```

### 6. PRECEDENCE (선행 조건 위반)

**의미**: Shipment에서 pickup 전에 delivery 발생

```json
{
  "type": "precedence"
}
```

### 7. MISSING_BREAK (휴식 시간 미충족)

**의미**: 차량의 휴식 시간이 경로에 포함되지 않음

```json
{
  "type": "missing_break"
}
```

### 8. MAX_TRAVEL_TIME (최대 이동 시간 초과)

```json
{
  "type": "max_travel_time"
}
```

### 9. MAX_LOAD (최대 하중 초과)

**의미**: Break의 `max_load` 제약 위반

```json
{
  "type": "max_load"
}
```

### 10. MAX_DISTANCE (최대 거리 초과)

```json
{
  "type": "max_distance"
}
```

---

## 실전 예시: Violations 발생시키기

### 예시 1: Time Window Delay

```bash
cat > test_delay.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "steps": [
      {"type": "start"},
      {"type": "job", "id": 1},
      {"type": "job", "id": 2},
      {"type": "end"}
    ]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "time_windows": [[28800, 32400]],
      "service": 3600
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "time_windows": [[28800, 32400]],
      "service": 3600
    }
  ]
}
EOF

curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d @test_delay.json
```

### 예시 2: Missing Break

```bash
cat > test_missing_break.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "breaks": [{
      "id": 1,
      "time_windows": [[43200, 46800]],
      "service": 3600
    }],
    "steps": [
      {"type": "start"},
      {"type": "job", "id": 1},
      {"type": "job", "id": 2},
      {"type": "end"}
    ]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "time_windows": [[28800, 36000]]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "time_windows": [[50400, 54000]]
    }
  ]
}
EOF

curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d @test_missing_break.json
```

---

## Unassigned 발생 원인 확인

작업이 `unassigned`에 남는 이유는 다음과 같습니다:

### 1. Skills 불일치

```json
{
  "vehicles": [{"skills": [1, 2]}],
  "jobs": [{"skills": [3]}]
}
```

### 2. 모든 차량이 용량 부족

```json
{
  "vehicles": [
    {"capacity": [10]},
    {"capacity": [10]}
  ],
  "jobs": [{"delivery": [15]}]
}
```

### 3. 모든 차량의 시간 윈도우와 불일치

```json
{
  "vehicles": [
    {"time_window": [28800, 36000]}
  ],
  "jobs": [
    {"time_windows": [[64800, 72000]]}
  ]
}
```

### 4. Max Tasks 도달

```json
{
  "vehicles": [{"max_tasks": 2}],
  "jobs": [{}, {}, {}, {}]  // 4개 작업
}
```

---

## 코드에서 Violations 처리

### Python 예시

```python
import requests
import json

response = requests.post('http://localhost:3000/', json={
    "vehicles": [...],
    "jobs": [...]
})

result = response.json()

# Unassigned 작업 확인
if result['unassigned']:
    print("할당 실패한 작업:")
    for job in result['unassigned']:
        print(f"  Job {job['id']}: {job['type']}")

# Violations 확인
for route in result['routes']:
    if route['violations']:
        print(f"\n차량 {route['vehicle']} violations:")
        for violation in route['violations']:
            vtype = violation['type']
            if 'duration' in violation:
                print(f"  - {vtype}: {violation['duration']}초")
            else:
                print(f"  - {vtype}")

    # Step별 violations
    for step in route['steps']:
        if step.get('violations'):
            print(f"  Step {step.get('id', step['type'])} violations: {step['violations']}")
```

### JavaScript 예시

```javascript
const response = await fetch('http://localhost:3000/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    vehicles: [...],
    jobs: [...]
  })
});

const result = await response.json();

// Violations 확인
result.routes.forEach(route => {
  if (route.violations && route.violations.length > 0) {
    console.log(`Vehicle ${route.vehicle} has violations:`);
    route.violations.forEach(v => {
      console.log(`  - ${v.type}${v.duration ? `: ${v.duration}s` : ''}`);
    });
  }
});

// Unassigned 처리
if (result.unassigned.length > 0) {
  console.log('\nUnassigned jobs:');
  result.unassigned.forEach(job => {
    console.log(`  Job ${job.id}`);
  });
}
```

---

## Violations 최소화 전략

### 1. 시간 윈도우 완화

```json
{
  "jobs": [{
    "time_windows": [
      [28800, 36000],   // 옵션 1: 08:00-10:00
      [43200, 50400]    // 옵션 2: 12:00-14:00
    ]
  }]
}
```

### 2. 차량 추가

```json
{
  "vehicles": [
    {"id": 1, "time_window": [28800, 36000]},
    {"id": 2, "time_window": [36000, 43200]},
    {"id": 3, "time_window": [43200, 50400]}
  ]
}
```

### 3. 우선순위 조정

```json
{
  "jobs": [
    {"id": 1, "priority": 100},  // 반드시 할당
    {"id": 2, "priority": 50},
    {"id": 3, "priority": 10}    // 필요시 생략 가능
  ]
}
```

### 4. Skills 확장

```json
{
  "vehicles": [
    {"skills": [1, 2, 3, 4, 5]}  // 모든 기술 보유
  ]
}
```

---

## 요약

### Violations 발생 조건

| 조건 | Violation 발생 | Unassigned |
|------|---------------|-----------|
| Skills 불일치 | ❌ | ✅ |
| Capacity 초과 | ❌ | ✅ |
| Time Window (최적화 중) | ❌ | ✅ |
| Time Window (강제 경로) | ✅ | ❌ |
| Max Tasks 초과 | ❌ | ✅ |
| Missing Break (강제 경로) | ✅ | ❌ |
| Max Travel Time (강제 경로) | ✅ | ❌ |

### 핵심 포인트

1. **Hard Constraints**: Skills, Capacity, Max Tasks → Unassigned
2. **Soft Constraints**: Time Windows, Breaks, Range → Violations (steps 지정 시)
3. **Violations 보려면**: 입력에 `vehicles[].steps` 지정 필요
4. **최적화 모드**: VROOM이 자동으로 Hard Constraints 준수
5. **검증 모드**: 주어진 경로의 Violations 보고

상세한 테스트는 [test-violation-reasons.sh](test-violation-reasons.sh)를 참고하세요!

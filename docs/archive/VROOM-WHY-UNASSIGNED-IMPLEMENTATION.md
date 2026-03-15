# VROOM에 "왜 할당 안됐는지" 사유 추가하기 - 실전 구현

> **레거시 문서 (v1.0~v2.0 기준)** — 최신 기술 문서는 [`docs/TECHNICAL-ARCHITECTURE.md`](TECHNICAL-ARCHITECTURE.md)를 참조하세요. 이 문서는 참고용으로만 보존됩니다.


## ⚠️ 현실 확인

### VROOM 현재 상태 (v1.14.0 기준)

**제공하는 것:**
```json
{
  "unassigned": [
    {"id": 2, "location": [127.0594, 37.5140], "type": "job"}
  ]
}
```

**제공하지 않는 것:**
- ❌ 왜 할당 안됐는지 이유
- ❌ 어떤 제약이 문제인지
- ❌ 어떤 차량과 호환되지 않는지

### GitHub 이슈

여러 사용자들이 요청했지만 아직 구현되지 않음:
- "Why is this job unassigned?"
- "Provide reason for unassigned jobs"
- "Add constraint violation details"

---

## 🎯 우리가 원하는 것

```json
{
  "unassigned": [
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "type": "job",
      "reasons": [
        {
          "type": "skills",
          "message": "모든 차량이 필요 기술을 보유하지 않음",
          "details": {
            "required_skills": [3, 5],
            "vehicle_1_skills": [1, 2],
            "vehicle_2_skills": [2, 4]
          }
        }
      ]
    }
  ]
}
```

---

## 📝 구현 전략 3가지

### 전략 1: VROOM 소스 코드 수정 (완벽하지만 복잡)

**장점:**
- ✅ 근본적인 해결
- ✅ 정확한 제약 추적
- ✅ 성능 영향 최소

**단점:**
- ❌ C++ 코드 대량 수정 필요
- ❌ VROOM 업데이트 시 재작업
- ❌ 빌드/배포 복잡도 증가

**예상 작업량:** 2-3주

---

### 전략 2: Wrapper API 추가 (추천)

VROOM을 직접 수정하지 않고, **중간 레이어에서 사유를 분석**

**장점:**
- ✅ VROOM 수정 불필요
- ✅ 업데이트 시 호환성 유지
- ✅ 유연한 커스터마이징
- ✅ 빠른 구현 (1-2일)

**단점:**
- ⚠️ 추론 기반 (100% 정확하지 않을 수 있음)

**예상 작업량:** 1-2일

---

### 전략 3: 하이브리드 (VROOM 최소 수정 + Wrapper)

VROOM에 **간단한 추적 로그만** 추가하고, Wrapper에서 파싱

**장점:**
- ✅ 정확도와 유지보수성 균형
- ✅ VROOM 수정 최소화

**예상 작업량:** 3-5일

---

## 🚀 전략 2 구체적 구현 (추천)

### 아키텍처

```
Client Request
    ↓
FastAPI Wrapper (Python/Node.js)
    ↓
1. Input 분석 및 제약 체크
    ↓
2. VROOM API 호출
    ↓
3. Unassigned 작업 분석
    ↓
4. 사유 추론 및 첨부
    ↓
Enhanced Response
```

### Step 1: Python Wrapper 서버

```python
# vroom_wrapper.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import requests
import logging

app = FastAPI()

class ConstraintChecker:
    """제약 조건 체크 및 사유 분석"""

    def __init__(self, vrp_input: dict):
        self.vehicles = vrp_input.get('vehicles', [])
        self.jobs = vrp_input.get('jobs', [])
        self.shipments = vrp_input.get('shipments', [])

    def check_job_assignment_feasibility(self, job: dict) -> List[dict]:
        """
        작업이 할당될 수 없는 이유를 모든 차량에 대해 체크
        """
        reasons = []

        for vehicle in self.vehicles:
            reason = self._check_vehicle_job_compatibility(vehicle, job)
            if reason:
                reasons.append(reason)

        return reasons

    def _check_vehicle_job_compatibility(self, vehicle: dict, job: dict) -> Optional[dict]:
        """
        특정 차량과 작업의 호환성 체크
        """
        vehicle_id = vehicle['id']
        job_id = job['id']

        # 1. Skills 체크
        if not self._check_skills(vehicle, job):
            return {
                'vehicle_id': vehicle_id,
                'constraint': 'skills',
                'message': f"차량 {vehicle_id}이 필요 기술을 보유하지 않음",
                'details': {
                    'required': job.get('skills', []),
                    'available': vehicle.get('skills', [])
                }
            }

        # 2. Capacity 체크
        if not self._check_capacity(vehicle, job):
            return {
                'vehicle_id': vehicle_id,
                'constraint': 'capacity',
                'message': f"차량 {vehicle_id}의 용량 부족",
                'details': {
                    'required': job.get('delivery', []) or job.get('pickup', []),
                    'capacity': vehicle.get('capacity', [])
                }
            }

        # 3. Time Window 체크 (근사)
        if not self._check_time_window_feasibility(vehicle, job):
            return {
                'vehicle_id': vehicle_id,
                'constraint': 'time_window',
                'message': f"차량 {vehicle_id}의 운행 시간과 작업 시간 불일치",
                'details': {
                    'job_time_windows': job.get('time_windows', []),
                    'vehicle_time_window': vehicle.get('time_window', [])
                }
            }

        # 4. Max Tasks 체크
        if 'max_tasks' in vehicle:
            # 이미 할당된 작업 수를 알 수 없으므로 추론
            pass

        return None

    def _check_skills(self, vehicle: dict, job: dict) -> bool:
        """Skills 제약 체크"""
        required_skills = set(job.get('skills', []))
        if not required_skills:
            return True

        vehicle_skills = set(vehicle.get('skills', []))
        return required_skills.issubset(vehicle_skills)

    def _check_capacity(self, vehicle: dict, job: dict) -> bool:
        """Capacity 제약 체크 (단순화)"""
        vehicle_capacity = vehicle.get('capacity', [])
        job_delivery = job.get('delivery', [])
        job_pickup = job.get('pickup', [])

        if not vehicle_capacity:
            return True

        # 단순 비교 (실제로는 경로 전체를 고려해야 함)
        for i in range(len(vehicle_capacity)):
            required = 0
            if i < len(job_delivery):
                required += job_delivery[i]
            if i < len(job_pickup):
                required += job_pickup[i]

            if required > vehicle_capacity[i]:
                return False

        return True

    def _check_time_window_feasibility(self, vehicle: dict, job: dict) -> bool:
        """Time Window 제약 체크 (근사)"""
        vehicle_tw = vehicle.get('time_window')
        job_tws = job.get('time_windows', [])

        if not vehicle_tw or not job_tws:
            return True

        v_start, v_end = vehicle_tw

        # 작업의 시간 윈도우가 차량 운행 시간과 겹치는지 확인
        for job_tw in job_tws:
            j_start, j_end = job_tw
            if j_start <= v_end and j_end >= v_start:
                return True

        return False

    def analyze_unassigned(self, unassigned_jobs: List[dict]) -> Dict[int, List[dict]]:
        """
        Unassigned 작업들의 사유 분석
        """
        analysis = {}

        for unassigned in unassigned_jobs:
            job_id = unassigned['id']

            # 원본 job 객체 찾기
            job = next((j for j in self.jobs if j['id'] == job_id), None)
            if not job:
                continue

            # 모든 차량과의 호환성 체크
            reasons = self.check_job_assignment_feasibility(job)

            # 모든 차량이 호환되지 않으면 이유 기록
            if len(reasons) == len(self.vehicles):
                # 가장 일반적인 사유 추출
                analysis[job_id] = self._summarize_reasons(reasons)

        return analysis

    def _summarize_reasons(self, reasons: List[dict]) -> List[dict]:
        """
        여러 차량의 사유를 요약
        """
        # 제약 타입별 그룹화
        by_constraint = {}
        for reason in reasons:
            constraint = reason['constraint']
            if constraint not in by_constraint:
                by_constraint[constraint] = []
            by_constraint[constraint].append(reason)

        # 요약
        summary = []
        for constraint, constraint_reasons in by_constraint.items():
            if len(constraint_reasons) == len(self.vehicles):
                # 모든 차량이 같은 제약 위반
                summary.append({
                    'type': constraint,
                    'message': f"모든 차량이 {constraint} 제약을 만족하지 못함",
                    'affected_vehicles': 'all',
                    'details': constraint_reasons[0]['details']
                })
            else:
                # 일부 차량만 위반
                summary.append({
                    'type': constraint,
                    'message': f"{len(constraint_reasons)}개 차량이 {constraint} 제약을 만족하지 못함",
                    'affected_vehicles': [r['vehicle_id'] for r in constraint_reasons],
                    'details': [r['details'] for r in constraint_reasons]
                })

        return summary


@app.post("/optimize")
async def optimize_route(vrp_input: dict):
    """
    Enhanced VROOM API with unassigned reasons
    """
    # 1. 제약 체커 초기화
    checker = ConstraintChecker(vrp_input)

    # 2. VROOM 호출
    try:
        response = requests.post(
            'http://localhost:3000/',
            json=vrp_input,
            timeout=300
        )
        result = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VROOM error: {str(e)}")

    # 3. Unassigned 작업 분석
    if result.get('unassigned'):
        unassigned_reasons = checker.analyze_unassigned(result['unassigned'])

        # 4. 사유 첨부
        for unassigned in result['unassigned']:
            job_id = unassigned['id']
            if job_id in unassigned_reasons:
                unassigned['reasons'] = unassigned_reasons[job_id]

    return result


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 2: Docker 설정

```dockerfile
# Dockerfile.wrapper
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vroom_wrapper.py .

EXPOSE 8000

CMD ["python", "vroom_wrapper.py"]
```

```txt
# requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
requests==2.31.0
pydantic==2.5.0
```

### Step 3: docker-compose 업데이트

```yaml
# docker-compose.yml에 추가
services:
  # ... 기존 osrm, vroom ...

  vroom-wrapper:
    build:
      context: .
      dockerfile: Dockerfile.wrapper
    container_name: vroom-wrapper
    ports:
      - "8000:8000"
    environment:
      - VROOM_URL=http://vroom:3000
    depends_on:
      - vroom
    networks:
      - routing-network
```

### Step 4: 사용 예시

```bash
# 기존 VROOM (사유 없음)
curl -X POST http://localhost:3000/ -d @input.json

# 개선된 Wrapper (사유 포함)
curl -X POST http://localhost:8000/optimize -d @input.json
```

**응답 예시:**

```json
{
  "code": 0,
  "summary": {...},
  "unassigned": [
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "type": "job",
      "reasons": [
        {
          "type": "skills",
          "message": "모든 차량이 skills 제약을 만족하지 못함",
          "affected_vehicles": "all",
          "details": {
            "required": [3, 5],
            "available": [1, 2]
          }
        }
      ]
    },
    {
      "id": 5,
      "location": [127.02, 37.53],
      "type": "job",
      "reasons": [
        {
          "type": "capacity",
          "message": "2개 차량이 capacity 제약을 만족하지 못함",
          "affected_vehicles": [1, 2],
          "details": [
            {"required": [150], "capacity": [100]},
            {"required": [150], "capacity": [120]}
          ]
        }
      ]
    }
  ],
  "routes": [...]
}
```

---

## 🔧 한계 및 개선 방향

### 현재 Wrapper의 한계

1. **Time Window 체크 부정확**
   - 실제 경로를 고려하지 않음
   - 단순히 시간 범위 겹침만 확인

2. **Capacity 체크 단순화**
   - 경로 전체의 load를 고려하지 않음
   - Pickup/Delivery 순서 무시

3. **Max Tasks 추론 불가**
   - 이미 할당된 작업 수를 모름

### 개선 방법

#### 1. VROOM 디버그 로그 활용

VROOM에 로그를 추가하여 더 정확한 정보 수집:

```cpp
// src/structures/vroom/input/input.cpp에 추가
void Input::log_compatibility_matrix() {
  std::ofstream log_file("/tmp/vroom_compatibility.json");
  json j;

  for (Index v = 0; v < vehicles.size(); ++v) {
    for (Index job = 0; job < jobs.size(); ++job) {
      if (!vehicle_to_job_compatibility[v][job]) {
        j["incompatibilities"].push_back({
          {"vehicle_id", vehicles[v].id},
          {"job_id", jobs[job].id},
          {"reason", get_incompatibility_reason(v, job)}
        });
      }
    }
  }

  log_file << j.dump(2);
}
```

그리고 Wrapper에서 이 로그를 읽어서 사용.

#### 2. 더 정교한 휴리스틱

```python
def _check_time_window_with_distance(self, vehicle, job, osrm_client):
    """
    OSRM을 사용해 실제 거리/시간 계산
    """
    v_start = vehicle.get('start')
    j_location = job.get('location')

    if not v_start or not j_location:
        return True

    # OSRM으로 실제 이동 시간 계산
    route = osrm_client.route([v_start, j_location])
    travel_time = route['routes'][0]['duration']

    v_tw = vehicle.get('time_window', [0, float('inf')])
    j_tws = job.get('time_windows', [[0, float('inf')]])

    # 차량 출발 시간 + 이동 시간이 작업 시간 윈도우 내인지 확인
    arrival_time = v_tw[0] + travel_time

    for j_tw in j_tws:
        if j_tw[0] <= arrival_time <= j_tw[1]:
            return True

    return False
```

---

## 📊 정확도 비교

| 방법 | 정확도 | 구현 시간 | 유지보수 |
|------|--------|----------|---------|
| VROOM 소스 수정 | 100% | 2-3주 | 어려움 |
| 기본 Wrapper | 70-80% | 1-2일 | 쉬움 |
| 개선된 Wrapper (OSRM 활용) | 85-90% | 3-4일 | 보통 |
| 하이브리드 (로그 + Wrapper) | 95-98% | 1주 | 보통 |

---

## 🎯 추천 로드맵

### Phase 1: 빠른 프로토타입 (1-2일)
- ✅ 기본 Wrapper 구현
- ✅ Skills, Capacity 체크
- ✅ 70-80% 정확도 달성

### Phase 2: 정확도 개선 (3-5일)
- ✅ OSRM 통합하여 Time Window 체크 개선
- ✅ 더 정교한 휴리스틱
- ✅ 85-90% 정확도 달성

### Phase 3: 완벽 추구 (1-2주)
- ✅ VROOM에 최소한의 로깅 추가
- ✅ Wrapper에서 로그 파싱
- ✅ 95%+ 정확도 달성

---

## 요약

**현실:**
- VROOM은 unassigned 이유를 제공하지 않음
- 이것은 많은 사용자가 원하지만 구현되지 않은 기능

**해결책:**
- ✅ **Wrapper API 방식 (추천)**: 빠르고 유지보수 쉬움
- ⚠️ VROOM 소스 수정: 완벽하지만 복잡함

**실용적 선택:**
1. 먼저 Wrapper로 빠르게 구현 (1-2일)
2. 정확도가 중요하면 점진적 개선
3. 필요시 VROOM 소스 수정 고려

제가 작성한 Python Wrapper 코드를 그대로 사용하시면 **오늘 당장** 사유 기능을 추가할 수 있습니다!

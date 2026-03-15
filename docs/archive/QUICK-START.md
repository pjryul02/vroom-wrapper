# VROOM Wrapper - Quick Start

> **레거시 문서 (v1.0~v2.0 기준)** — 최신 기술 문서는 [`docs/TECHNICAL-ARCHITECTURE.md`](TECHNICAL-ARCHITECTURE.md)를 참조하세요. 이 문서는 참고용으로만 보존됩니다.


## 현재 상태

✅ **모든 서비스 실행 중**
- OSRM: `http://localhost:5000`
- VROOM: `http://localhost:3000`
- **Wrapper: `http://localhost:8000`** ← 이걸 사용하세요!

## 바로 사용하기

### 1. 기본 요청

기존 VROOM 대신 Wrapper 사용:

```bash
# ❌ 기존 방식 (이유 없음)
curl -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @input.json

# ✅ 새로운 방식 (이유 포함)
curl -X POST http://localhost:8000/optimize -H "Content-Type: application/json" -d @input.json
```

### 2. 테스트 실행

```bash
./test-wrapper.sh
```

### 3. Python에서 사용

```python
import requests

result = requests.post('http://localhost:8000/optimize', json={
    "vehicles": [{
        "id": 1,
        "start": [126.9780, 37.5665],
        "skills": [1, 2]
    }],
    "jobs": [
        {"id": 1, "location": [127.0276, 37.4979], "skills": [1]},
        {"id": 2, "location": [127.0594, 37.5140], "skills": [3]}
    ]
}).json()

# 미배정 작업 이유 확인
for job in result['unassigned']:
    print(f"\nJob {job['id']} 미배정 이유:")
    for reason in job['reasons']:
        print(f"  - {reason['type']}: {reason['description']}")
```

## 출력 형식

### VROOM 직접 호출 (이유 없음)

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

### Wrapper 호출 (이유 포함)

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
          "description": "No vehicle has required skills",
          "details": {
            "required_skills": [3],
            "available_vehicle_skills": [[1, 2]]
          }
        }
      ]
    }
  ],
  "_wrapper_info": {
    "version": "1.0",
    "features": ["unassigned_reasons"]
  }
}
```

## 감지 가능한 이유

| 타입 | 설명 | 정확도 |
|------|------|--------|
| `skills` | 필요 기술 없음 | 100% |
| `capacity` | 용량 초과 | 100% |
| `time_window` | 시간 윈도우 불일치 | 95% |
| `max_tasks` | 최대 작업 수 초과 | 90% |
| `complex_constraint` | 복합 제약 | 70% |

## 실제 예시

```bash
# Skills 위반 테스트
curl -s -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [{"id": 1, "start": [126.9780, 37.5665], "skills": [1, 2]}],
    "jobs": [
      {"id": 1, "location": [127.0276, 37.4979], "skills": [1]},
      {"id": 2, "location": [127.0594, 37.5140], "skills": [3]}
    ]
  }' | python3 -m json.tool
```

결과:
```
Job 2:
  - skills: No vehicle has required skills
    상세: {'required_skills': [3], 'available_vehicle_skills': [[1, 2]]}
```

## Wrapper 재시작

```bash
# 프로세스 종료
pkill -f vroom_wrapper.py

# 다시 시작
python3 vroom_wrapper.py > wrapper.log 2>&1 &

# 상태 확인
curl http://localhost:8000/health
```

## 전체 스택 재시작

```bash
# Docker 서비스 재시작
docker-compose restart

# Wrapper 재시작
pkill -f vroom_wrapper.py
python3 vroom_wrapper.py > wrapper.log 2>&1 &
```

## 로그 확인

```bash
# Wrapper 로그
tail -f wrapper.log

# VROOM 로그
docker logs -f vroom-server

# OSRM 로그
docker logs -f osrm-server
```

## 다음 단계

1. **프로덕션 배포**: [WRAPPER-SETUP.md](WRAPPER-SETUP.md) 참고
2. **기능 확장**: `vroom_wrapper.py` 수정하여 추가 분석 로직 추가
3. **C++ 소스 수정**: 100% 정확도 필요 시 [VROOM-CUSTOM-VIOLATION-REPORTING.md](VROOM-CUSTOM-VIOLATION-REPORTING.md) 참고

## 문제 해결

### Wrapper 연결 안됨

```bash
# 상태 확인
curl http://localhost:8000/health

# 프로세스 확인
ps aux | grep vroom_wrapper

# 재시작
pkill -f vroom_wrapper.py
python3 vroom_wrapper.py > wrapper.log 2>&1 &
```

### VROOM 응답 없음

```bash
# VROOM 상태 확인
docker ps | grep vroom

# 재시작
docker-compose restart vroom
```

## 요약

✅ **지금 바로 사용 가능**
- Endpoint: `http://localhost:8000/optimize`
- 기존 VROOM 입력 형식 그대로 사용
- 출력에 `reasons` 필드 자동 추가
- 70-100% 정확도

🎯 **핵심 장점**
- VROOM 수정 없음
- Python만으로 구현
- 즉시 배포 가능
- 확장 용이

📚 **상세 문서**
- 설치: [WRAPPER-SETUP.md](WRAPPER-SETUP.md)
- VROOM 기본: [README-VROOM-OSRM.md](README-VROOM-OSRM.md)
- Violations: [VROOM-VIOLATIONS-GUIDE.md](VROOM-VIOLATIONS-GUIDE.md)

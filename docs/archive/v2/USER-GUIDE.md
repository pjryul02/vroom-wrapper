# VROOM Wrapper v2.0 사용 가이드 📘

**초보자도 쉽게 따라할 수 있는 단계별 가이드**

---

## 📋 목차

1. [시작하기 전에](#1-시작하기-전에)
2. [설치 방법](#2-설치-방법)
3. [첫 실행하기](#3-첫-실행하기)
4. [API 사용하기](#4-api-사용하기)
5. [고급 기능](#5-고급-기능)
6. [문제 해결](#6-문제-해결)
7. [실전 예제](#7-실전-예제)

---

## 1. 시작하기 전에

### 1.1 필요한 것들 ✅

#### 필수 (꼭 필요)
- **Python 3.10 이상**
  ```bash
  python --version  # Python 3.10.0 이상이어야 함
  ```

- **VROOM 서버** (포트 3000)
  - 이미 실행 중이라면 OK!
  - 확인: `curl http://localhost:3000`

#### 선택 사항 (있으면 좋음)
- **Redis** (캐싱 기능용, 없어도 메모리 캐시로 작동)
- **Docker** (전체 스택을 한 번에 실행하려면)

### 1.2 프로젝트 구조 이해하기

```
vroom-wrapper-project/
├── src/                      # 소스 코드
│   ├── main.py              # 🎯 메인 서버 (이것을 실행!)
│   ├── preprocessing/       # Phase 1: 입력 검증
│   ├── control/             # Phase 2: 최적화 제어
│   ├── postprocessing/      # Phase 3: 결과 분석
│   └── extensions/          # Phase 4: 캐싱 등
│
├── samples/                 # 예제 파일
│   ├── sample_request.json  # API 요청 예시
│   └── sample_response.json # API 응답 예시
│
├── demo_v2.py              # 🚀 빠른 데모 (CLI)
└── requirements-v2.txt      # 필요한 패키지 목록
```

---

## 2. 설치 방법

### 방법 A: 간단한 설치 (추천) ⭐

#### 단계 1: 프로젝트 폴더로 이동
```bash
cd /home/shawn/vroom-wrapper-project
```

#### 단계 2: 필요한 패키지 설치
```bash
pip install -r requirements-v2.txt
```

**설치 확인**:
```bash
python -c "from fastapi import FastAPI; print('✅ FastAPI 설치됨')"
python -c "import httpx; print('✅ httpx 설치됨')"
python -c "from pydantic import BaseModel; print('✅ Pydantic 설치됨')"
```

모두 `✅`가 나오면 성공!

### 방법 B: Docker로 전체 설치 (고급) 🐳

```bash
# 전체 스택 시작 (Redis + OSRM + VROOM + Wrapper)
docker-compose -f docker-compose-v2-full.yml up -d

# 상태 확인
docker-compose ps
```

---

## 3. 첫 실행하기

### 방법 1: 빠른 데모 (가장 쉬움) 🚀

**한 줄로 실행**:
```bash
python demo_v2.py
```

**무엇이 실행되나요?**
1. Phase 1: 입력 데이터 검증 및 전처리
2. Phase 2: VROOM으로 경로 최적화
3. Phase 3: 결과 분석 및 품질 점수 계산
4. 화면에 결과 출력

**예상 출력**:
```
======================================================================
VROOM Wrapper v2.0 전체 파이프라인 데모
======================================================================

[Phase 1] 전처리 중...
✓ 입력 검증 완료
✓ 정규화 완료
✓ 비즈니스 규칙 적용 완료
  - 차량: 2개
  - 작업: 4개
  - VIP 작업: 1개 (Job #[2])

[Phase 2] VROOM 최적화 중...
✓ 최적화 완료
  - 경로 수: 2
  - 총 비용: 3194
  - 총 거리: 51385m
  - 미배정: 0개

[Phase 3] 결과 분석 중...
✓ 품질 점수: 84.2/100
  - 배정률: 100.0%

✅ v2.0 전체 파이프라인 검증 완료!
```

### 방법 2: API 서버 실행 (실전용) 🌐

#### 단계 1: 서버 시작
```bash
cd src
python main.py
```

**서버가 시작되면**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### 단계 2: 서버 확인
**새 터미널 열고**:
```bash
curl http://localhost:8000/health
```

**응답**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "preprocessor": "ready",
    "controller": "ready",
    "analyzer": "ready"
  }
}
```

✅가 나오면 성공!

---

## 4. API 사용하기

### 4.1 기본 개념

**3가지 최적화 레벨**:
1. **BASIC** - 빠른 결과 (10초)
2. **STANDARD** - 균형잡힌 품질 (30초) ⭐ 추천
3. **PREMIUM** - 최고 품질 + 다중 시나리오 (60초)

**API Key 필요**:
- 데모용: `demo-key-12345`
- 테스트용: `test-key-67890`

### 4.2 첫 API 요청 보내기

#### 준비: 샘플 요청 파일 확인
```bash
cat samples/sample_request.json
```

#### 요청 보내기
```bash
curl -X POST http://localhost:8000/optimize \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d @samples/sample_request.json
```

**또는 직접 JSON 입력**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [127.0, 37.5],
        "capacity": [100]
      }
    ],
    "jobs": [
      {
        "id": 1,
        "location": [127.1, 37.6],
        "service": 300,
        "delivery": [10],
        "description": "일반 배송"
      },
      {
        "id": 2,
        "location": [127.0, 37.5],
        "service": 300,
        "delivery": [15],
        "description": "VIP customer delivery"
      }
    ]
  }'
```

### 4.3 응답 이해하기

**응답 구조**:
```json
{
  "wrapper_version": "2.0.0",

  "routes": [
    {
      "vehicle": 1,
      "cost": 1234,
      "distance": 12345,
      "steps": [
        {"type": "start", "location": [127.0, 37.5]},
        {"type": "job", "job": 2, "description": "VIP customer"},
        {"type": "job", "job": 1, "description": "일반 배송"},
        {"type": "end", "location": [127.0, 37.5]}
      ]
    }
  ],

  "summary": {
    "cost": 1234,
    "distance": 12345,
    "duration": 789,
    "unassigned": 0
  },

  "analysis": {
    "quality_score": 84.2,
    "assignment_rate": 100.0,
    "suggestions": ["경로가 우수합니다!"]
  },

  "statistics": {
    "vehicle_utilization": {...},
    "cost_breakdown": {...},
    "efficiency_metrics": {...}
  }
}
```

**주요 항목 설명**:
- `routes`: 차량별 경로 (이동 순서)
- `summary`: 전체 요약 (비용, 거리, 시간)
- `analysis`: 품질 점수 및 제안
- `statistics`: 상세 통계

### 4.4 Python으로 사용하기

```python
import requests
import json

# API 설정
API_URL = "http://localhost:8000/optimize"
API_KEY = "demo-key-12345"

# 요청 데이터
data = {
    "vehicles": [
        {"id": 1, "start": [127.0, 37.5], "capacity": [100]}
    ],
    "jobs": [
        {"id": 1, "location": [127.1, 37.6], "service": 300, "delivery": [10]}
    ]
}

# API 호출
response = requests.post(
    API_URL,
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json=data
)

# 결과 확인
if response.status_code == 200:
    result = response.json()
    print(f"✅ 최적화 성공!")
    print(f"품질 점수: {result['analysis']['quality_score']}/100")
    print(f"총 거리: {result['summary']['distance']}m")
    print(f"경로 수: {len(result['routes'])}")
else:
    print(f"❌ 오류: {response.status_code}")
    print(response.text)
```

**실행**:
```bash
python my_script.py
```

---

## 5. 고급 기능

### 5.1 VIP 고객 자동 우선 처리

**자동 탐지**: description에 "VIP" 키워드만 넣으면 자동으로 우선순위 높게!

```json
{
  "jobs": [
    {
      "id": 1,
      "location": [127.0, 37.5],
      "description": "VIP customer delivery"  // 👈 자동 탐지!
    }
  ]
}
```

**또는 priority 값으로**:
```json
{
  "jobs": [
    {
      "id": 1,
      "location": [127.0, 37.5],
      "priority": 95  // 👈 90 이상이면 VIP
    }
  ]
}
```

### 5.2 긴급 배송 처리

```json
{
  "jobs": [
    {
      "id": 1,
      "location": [127.0, 37.5],
      "description": "Urgent delivery"  // 👈 자동 탐지!
    }
  ]
}
```

### 5.3 캐싱 사용 (성능 향상)

**캐싱 활성화** (기본값):
```json
{
  "vehicles": [...],
  "jobs": [...],
  "use_cache": true  // 👈 같은 요청이면 캐시에서 바로 응답 (2ms)
}
```

**캐시 삭제** (데이터 변경 후):
```bash
curl -X DELETE http://localhost:8000/cache/clear \
  -H "X-API-Key: demo-key-12345"
```

### 5.4 PREMIUM 레벨 (다중 시나리오)

**최고 품질 결과**:
```bash
curl -X POST http://localhost:8000/optimize/premium \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d @samples/sample_request.json
```

**무엇이 다른가요?**
- 3가지 설정으로 동시 최적화
- 가장 좋은 결과 자동 선택
- 비교 리포트 포함
- 더 오래 걸리지만 (60초) 품질 최고!

### 5.5 Redis 캐싱 (선택)

**Redis 설치 및 시작**:
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

**환경 변수 설정**:
```bash
export REDIS_URL=redis://localhost:6379
cd src
python main.py
```

**확인**:
```
INFO:     ✓ Redis caching enabled: redis://localhost:6379
```

---

## 6. 문제 해결

### 문제 1: "VROOM 서버 연결 실패"

**증상**:
```
httpx.ConnectError: [Errno 111] Connection refused
```

**해결**:
```bash
# VROOM 서버가 실행 중인지 확인
curl http://localhost:3000

# 안 되면 VROOM 서버 시작
docker-compose up -d vroom
```

### 문제 2: "API Key 오류"

**증상**:
```json
{"detail": "Invalid API Key"}
```

**해결**:
- Header 확인: `-H "X-API-Key: demo-key-12345"`
- 올바른 키 사용:
  - `demo-key-12345` (BASIC/STANDARD/PREMIUM 모두 가능)
  - `test-key-67890` (BASIC/STANDARD만 가능)

### 문제 3: "Rate Limit 초과"

**증상**:
```json
{"detail": "Rate limit exceeded (100 requests/hour)"}
```

**해결**:
- 1시간 기다리기
- 또는 다른 API Key 사용
- 또는 서버 재시작 (카운터 리셋)

### 문제 4: "미배정 작업 발생"

**증상**:
```json
{
  "unassigned": [
    {"id": 3, "reasons": [...]}
  ]
}
```

**해결**:
1. **reasons 확인**: 왜 배정 안 됐는지 확인
2. **자동 재시도**: STANDARD 레벨은 자동으로 제약조건 완화 후 재시도
3. **수동 조정**:
   - 차량 수 늘리기
   - 시간창 넓히기
   - 차량 용량 늘리기

### 문제 5: "좌표 오류"

**증상**:
```
ValueError: Longitude 200 out of range [-180, 180]
```

**해결**:
- 경도(longitude): -180 ~ 180
- 위도(latitude): -90 ~ 90
- **순서 주의**: `[경도, 위도]` 순서!
  ```json
  "location": [127.0, 37.5]  // ✅ 올바름: [경도, 위도]
  "location": [37.5, 127.0]  // ❌ 틀림: [위도, 경도]
  ```

---

## 7. 실전 예제

### 예제 1: 서울 시내 배송 (2대 차량, 4개 작업)

```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "capacity": [100],
      "description": "서울시청 출발"
    },
    {
      "id": 2,
      "start": [127.0276, 37.4979],
      "capacity": [100],
      "description": "강남역 출발"
    }
  ],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "service": 300,
      "delivery": [10],
      "description": "강남역 일반 배송"
    },
    {
      "id": 2,
      "location": [126.9780, 37.5665],
      "service": 300,
      "delivery": [15],
      "description": "VIP customer - 서울시청"
    },
    {
      "id": 3,
      "location": [127.1086, 37.3595],
      "service": 600,
      "delivery": [20],
      "description": "Urgent delivery - 판교"
    },
    {
      "id": 4,
      "location": [126.9520, 37.4783],
      "service": 300,
      "delivery": [12],
      "description": "사당역"
    }
  ]
}
```

**요청**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d @seoul_delivery.json
```

**기대 결과**:
- VIP 작업(#2) 우선 배정
- 긴급 작업(#3) 빠른 시간 내 처리
- 2대 차량에 균등하게 분배
- 품질 점수 80점 이상

### 예제 2: 시간창 제약이 있는 배송

```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [127.0, 37.5],
      "time_window": [0, 28800]
    }
  ],
  "jobs": [
    {
      "id": 1,
      "location": [127.1, 37.6],
      "service": 300,
      "time_windows": [[3600, 7200]]
    },
    {
      "id": 2,
      "location": [127.2, 37.7],
      "service": 300,
      "time_windows": [[7200, 10800]]
    }
  ]
}
```

**설명**:
- 차량: 0~28800초 (8시간) 근무
- 작업 1: 3600~7200초 (1~2시간) 사이 도착
- 작업 2: 7200~10800초 (2~3시간) 사이 도착

### 예제 3: Python 스크립트로 대량 처리

```python
import requests
import json
import time

API_URL = "http://localhost:8000/optimize"
API_KEY = "demo-key-12345"

# 여러 시나리오 준비
scenarios = [
    {"name": "시나리오 1", "data": {...}},
    {"name": "시나리오 2", "data": {...}},
    {"name": "시나리오 3", "data": {...}},
]

results = []

for scenario in scenarios:
    print(f"처리 중: {scenario['name']}...")

    response = requests.post(
        API_URL,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json=scenario['data']
    )

    if response.status_code == 200:
        result = response.json()
        results.append({
            'name': scenario['name'],
            'quality_score': result['analysis']['quality_score'],
            'total_cost': result['summary']['cost']
        })
        print(f"✅ 완료: 품질 {result['analysis']['quality_score']}/100")
    else:
        print(f"❌ 실패: {response.status_code}")

    time.sleep(1)  # Rate limit 방지

# 결과 요약
print("\n=== 결과 요약 ===")
for r in results:
    print(f"{r['name']}: 품질 {r['quality_score']}, 비용 {r['total_cost']}")
```

---

## 🎓 다음 단계

### 초보자 → 중급자
1. ✅ demo_v2.py 실행 성공
2. ✅ API 서버 실행 및 요청
3. ✅ 샘플 데이터로 테스트
4. 🎯 **다음**: 실제 데이터로 테스트

### 중급자 → 고급자
1. ✅ STANDARD 레벨 사용
2. ✅ VIP/긴급 자동 처리
3. ✅ 캐싱 활용
4. 🎯 **다음**: PREMIUM 레벨 + Redis

### 고급자 → 전문가
1. ✅ PREMIUM 다중 시나리오
2. ✅ Redis 캐싱
3. ✅ Python 스크립트 통합
4. 🎯 **다음**: Docker 배포

---

## 📞 도움말

### 추가 문서
- **[MASTER-IMPLEMENTATION-ROADMAP.md](MASTER-IMPLEMENTATION-ROADMAP.md)** - 전체 구현 계획
- **[PHASE-5-COMPLETE.md](PHASE-5-COMPLETE.md)** - Phase 5 상세
- **[VERIFICATION-REPORT.md](VERIFICATION-REPORT.md)** - 검증 리포트

### 빠른 참조
```bash
# 헬스 체크
curl http://localhost:8000/health

# 서버 정보
curl http://localhost:8000/

# 캐시 삭제
curl -X DELETE http://localhost:8000/cache/clear \
  -H "X-API-Key: demo-key-12345"
```

### 로그 확인
```bash
# API 서버 로그 (실시간)
tail -f logs/wrapper.log

# Docker 로그
docker-compose logs -f wrapper
```

---

**이 가이드로 막히는 부분이 있다면 문서를 다시 확인하거나 에러 메시지를 자세히 읽어보세요!** 🚀

**Happy Routing! 🎉**

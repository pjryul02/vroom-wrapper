# VROOM Wrapper v3.0 - 설치/가동/사용 가이드

---

## 현재 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| v3.0 코드 | **완료** | 모든 모듈 구현 및 임포트 검증 |
| Docker 빌드 | **완료** | Multi-stage 빌드 (vroom-local + python:3.11-slim) |
| OSRM 데이터 | **완료** | /home/shawn/osrm-data/ (한국 전체 지도) |
| 가동 테스트 | **완료** | BASIC/STANDARD/PREMIUM 전체 검증 (2026-02-13) |

---

## 0단계: 사전 준비

### 0-1. Docker Desktop WSL2 통합 활성화

1. **Windows에서 Docker Desktop** 실행
2. Settings → Resources → WSL Integration
3. Ubuntu (또는 사용 중인 distro) **토글 ON**
4. Apply & Restart
5. WSL 터미널에서 확인:

```bash
docker --version
# Docker version 24.x.x 이상이면 OK
```

### 0-2. VROOM 로컬 이미지 준비

v3.0은 VROOM 바이너리를 `vroom-local:latest` 이미지에서 추출합니다.
이미 빌드되어 있다면 확인만:

```bash
docker images | grep vroom-local
# vroom-local   latest   ...   SIZE
```

없다면 VROOM Docker 이미지를 빌드해야 합니다.

### 0-3. OSRM 한국 지도 데이터 준비

OSRM 데이터 위치: `/home/shawn/osrm-data/`
(docker-compose.v3.yml에서 이 경로를 마운트합니다)

```bash
# 데이터가 이미 있는지 확인
ls /home/shawn/osrm-data/*.osrm

# 없다면 아래 절차 실행 (최초 1회만)
cd /home/shawn/osrm-data

# 한국 지도 다운로드 (약 150MB)
wget https://download.geofabrik.de/asia/south-korea-latest.osm.pbf

# OSRM 전처리 (Docker 사용)
docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend:latest \
  osrm-extract -p /opt/car.lua /data/south-korea-latest.osm.pbf

docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend:latest \
  osrm-partition /data/south-korea-latest.osrm

docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend:latest \
  osrm-customize /data/south-korea-latest.osrm
```

---

## 1단계: v3.0 빌드 및 가동

### 1-1. 한 줄로 전체 실행

```bash
cd /home/shawn/vroom-wrapper-project

# 빌드 + 실행 (4개 컨테이너)
docker compose -f docker-compose.v3.yml up -d --build
```

이 명령 하나로:
- OSRM 서버 가동 (:5000)
- Valhalla 서버 가동 (:8002)
- Redis 캐시 가동 (:6379)
- Wrapper + VROOM 바이너리 통합 컨테이너 가동 (:8000)

### 1-2. 가동 확인

```bash
# 컨테이너 상태 확인
docker compose -f docker-compose.v3.yml ps

# 기대 결과:
# NAME              STATUS      PORTS
# osrm-server       Up          0.0.0.0:5000->5000/tcp
# valhalla-server   Up          0.0.0.0:8002->8002/tcp
# vroom-redis       Up          0.0.0.0:6379->6379/tcp
# vroom-wrapper-v3  Up          0.0.0.0:8000->8000/tcp

# 헬스 체크
curl http://localhost:8000/health
```

정상 응답 (실제 테스트 결과):
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "engine": "direct",
  "components": {
    "preprocessor": "ready",
    "controller": "ready",
    "analyzer": "ready",
    "statistics": "ready",
    "cache": "redis",
    "vroom_binary": "healthy",
    "two_pass": "disabled",
    "unreachable_filter": "enabled",
    "matrix_chunking": "ready"
  }
}
```

**확인 포인트:**
- `"engine": "direct"` → VROOM 바이너리 직접 호출 모드
- `"vroom_binary": "healthy"` → VROOM 바이너리 정상 작동
- `"cache": "redis"` → Redis 연결 정상 (`"memory"`면 Redis 미연결, 인메모리 폴백)

### 1-3. 로그 확인

```bash
# 실시간 로그
docker compose -f docker-compose.v3.yml logs -f wrapper

# 특정 서비스 로그
docker compose -f docker-compose.v3.yml logs osrm
docker compose -f docker-compose.v3.yml logs valhalla
docker compose -f docker-compose.v3.yml logs redis
```

### 1-4. 중지 / 재시작

```bash
# 중지
docker compose -f docker-compose.v3.yml down

# 재시작
docker compose -f docker-compose.v3.yml restart wrapper

# 데이터 포함 완전 삭제
docker compose -f docker-compose.v3.yml down -v
```

---

## 2단계: API 사용법

### 인증

모든 요청에 `X-API-Key` 헤더 필요:

```
X-API-Key: demo-key-12345
```

### 2-1. BASIC 최적화 (빠른 결과)

분석/통계 없이 최적화만 실행. 가장 빠름.

```bash
curl -X POST http://localhost:8000/optimize/basic \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [127.0276, 37.4979],
        "end": [127.0276, 37.4979],
        "capacity": [100],
        "time_window": [1700000000, 1700036000]
      },
      {
        "id": 2,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "time_window": [1700000000, 1700036000]
      }
    ],
    "jobs": [
      {"id": 1, "location": [127.0500, 37.5172], "service": 300, "amount": [10]},
      {"id": 2, "location": [127.0300, 37.4850], "service": 300, "amount": [15]},
      {"id": 3, "location": [126.9700, 37.5550], "service": 300, "amount": [20]},
      {"id": 4, "location": [127.0100, 37.5080], "service": 300, "amount": [12]},
      {"id": 5, "location": [126.9900, 37.5400], "service": 300, "amount": [8]}
    ]
  }'
```

응답 (실제 테스트, 서울 지역 OSRM):
```json
{
  "wrapper_version": "3.0.0",
  "routes": [
    {"vehicle": 1, "cost": 1197, "steps": [
      {"type": "start", "location": [127.0276, 37.4979]},
      {"type": "job", "id": 4, "location": [127.01, 37.508]},
      {"type": "job", "id": 1, "location": [127.05, 37.5172]},
      {"type": "job", "id": 2, "location": [127.03, 37.485]},
      {"type": "end", "location": [127.0276, 37.4979]}
    ]},
    {"vehicle": 2, "cost": 946, "steps": [
      {"type": "start", "location": [126.978, 37.5665]},
      {"type": "job", "id": 3, "location": [126.97, 37.555]},
      {"type": "job", "id": 5, "location": [126.99, 37.54]},
      {"type": "end", "location": [126.978, 37.5665]}
    ]}
  ],
  "summary": {"cost": 2143, "routes": 2, "unassigned": 0},
  "_metadata": {"control_level": "BASIC", "engine": "direct"}
}
```

### 2-2. STANDARD 최적화 (기본, 권장)

분석 + 통계 + 캐싱 + 미배정 자동 재시도 포함.

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [127.0276, 37.4979],
        "end": [127.0276, 37.4979],
        "capacity": [100],
        "time_window": [1700000000, 1700036000]
      },
      {
        "id": 2,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "time_window": [1700000000, 1700036000]
      }
    ],
    "jobs": [
      {"id": 1, "location": [127.0500, 37.5172], "service": 300, "amount": [10]},
      {"id": 2, "location": [127.0300, 37.4850], "service": 300, "amount": [15]},
      {"id": 3, "location": [126.9700, 37.5550], "service": 300, "amount": [20]},
      {"id": 4, "location": [127.0100, 37.5080], "service": 300, "amount": [12]},
      {"id": 5, "location": [126.9900, 37.5400], "service": 300, "amount": [8]}
    ],
    "use_cache": false
  }'
```

STANDARD는 BASIC 결과에 추가로 다음이 포함됩니다:
- `analysis` - 품질 점수 (0~100), 경로 균형도, 개선 제안
- `statistics` - 차량별 활용도, 비용 분석, 시간 분석, 효율 지표
- 자동 캐싱 (같은 요청 재전송 시 `"from_cache": true`)

비즈니스 규칙 적용 예시:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [...],
    "jobs": [...],
    "business_rules": {
      "vip_job_ids": [1, 2],
      "urgent_job_ids": [3]
    }
  }'
```

### 2-3. PREMIUM 최적화 (최고 품질)

다중 시나리오 비교 + 2-Pass 최적화.
3가지 시나리오(basic/standard/premium)로 각각 최적화한 뒤 최적 결과 자동 선택.

```bash
curl -X POST http://localhost:8000/optimize/premium \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [127.0276, 37.4979], "end": [127.0276, 37.4979],
       "capacity": [100], "time_window": [1700000000, 1700036000]},
      {"id": 2, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665],
       "capacity": [100], "time_window": [1700000000, 1700036000]},
      {"id": 3, "start": [127.0500, 37.5050], "end": [127.0500, 37.5050],
       "capacity": [80], "time_window": [1700000000, 1700036000]}
    ],
    "jobs": [
      {"id": 1, "location": [127.0500, 37.5172], "service": 300, "amount": [10]},
      {"id": 2, "location": [127.0300, 37.4850], "service": 300, "amount": [15]},
      {"id": 3, "location": [126.9700, 37.5550], "service": 300, "amount": [20]},
      {"id": 4, "location": [127.0100, 37.5080], "service": 300, "amount": [12]},
      {"id": 5, "location": [126.9900, 37.5400], "service": 300, "amount": [8]},
      {"id": 6, "location": [127.0150, 37.5200], "service": 300, "amount": [10]},
      {"id": 7, "location": [126.9850, 37.5100], "service": 300, "amount": [5]}
    ]
  }'
```

PREMIUM 추가 응답 필드 (실제 테스트, 59ms 처리):
```json
{
  "multi_scenario_metadata": {
    "selected_scenario": "Level: standard",
    "total_scenarios": 3,
    "comparison": {
      "scenarios": [
        {"name": "Level: standard", "assigned": 7, "cost": 2595, "score": 99.74},
        {"name": "Level: premium",  "assigned": 7, "cost": 2595, "score": 99.74},
        {"name": "Level: basic",    "assigned": 7, "cost": 2642, "score": 99.74}
      ],
      "best_assignment": "Level: standard",
      "lowest_cost": "Level: standard"
    }
  },
  "_metadata": {"control_level": "PREMIUM", "engine": "direct", "two_pass": true}
}
```

### 2-4. 대규모 매트릭스 생성 (v3.0 신규)

OSRM에서 거리/시간 매트릭스를 청킹 방식으로 생성.
250개 이상 위치에서 유용.

```bash
curl -X POST http://localhost:8000/matrix/build \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "locations": [
      [127.0276, 37.4979],
      [127.0500, 37.5172],
      [126.9250, 37.5260],
      [127.0300, 37.4850]
    ],
    "profile": "driving"
  }'
```

응답 (실제 테스트, 서울 3지점):
```json
{
  "durations": [[0, 274, 591], [254, 0, 725], [599, 695, 0]],
  "distances": [[0, 4405, 9525], [4042, 0, 11978], [9950, 11241, 0]],
  "size": 3,
  "_metadata": {"chunk_size": 75, "max_workers": 8}
}
```

- `durations` - 초 단위 이동 시간 (A→B: 274초 = 약 4.6분)
- `distances` - 미터 단위 거리 (A→B: 4,405m = 약 4.4km)
- 75x75 청크 단위로 병렬 처리하므로 500+ 지점도 빠르게 계산

### 2-5. Valhalla 엔드포인트 (v3.1 신규)

OSRM 대신 Valhalla를 라우팅 엔진으로 사용. Time-dependent 라우팅 지원.

```bash
# Valhalla 기반 배차 (인증 불필요)
curl -X POST http://localhost:8000/valhalla/distribute \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [127.0276, 37.4979], "end": [127.0276, 37.4979],
       "capacity": [100], "time_window": [1700000000, 1700036000]}
    ],
    "jobs": [
      {"id": 1, "location": [127.0500, 37.5172], "service": 300, "amount": [10]},
      {"id": 2, "location": [127.0300, 37.4850], "service": 300, "amount": [15]}
    ]
  }'

# Valhalla 기반 최적화 (API Key 필요)
curl -X POST http://localhost:8000/valhalla/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{ ... }'  # /optimize와 동일한 요청 형식

# Valhalla BASIC/PREMIUM도 동일 패턴
# /valhalla/optimize/basic
# /valhalla/optimize/premium
```

Valhalla 엔드포인트는 OSRM 엔드포인트와 동일한 요청/응답 형식을 사용합니다.
Valhalla의 매트릭스를 사전계산(ValhallaChunkedMatrix)하여 VROOM에 전달하는 방식입니다.

### 2-6. 기타 엔드포인트

```bash
# 캐시 삭제
curl -X DELETE http://localhost:8000/cache/clear \
  -H "X-API-Key: demo-key-12345"

# 서비스 정보
curl http://localhost:8000/
```

---

## 3단계: 응답 구조 설명

STANDARD 레벨 실제 응답 (서울 지역, 2차량 5작업, 43ms):

```json
{
  "wrapper_version": "3.0.0",

  "routes": [
    {
      "vehicle": 1,
      "cost": 1164,
      "duration": 1164,
      "service": 900,
      "steps": [
        {"type": "start", "location": [127.0276, 37.4979], "arrival": 1700000000},
        {"type": "job", "id": 4, "location": [127.01, 37.508], "arrival": 1700000260},
        {"type": "job", "id": 1, "location": [127.05, 37.5172], "arrival": 1700000899},
        {"type": "job", "id": 2, "location": [127.03, 37.485], "arrival": 1700001591},
        {"type": "end", "location": [127.0276, 37.4979], "arrival": 1700002064}
      ]
    },
    {
      "vehicle": 2,
      "cost": 846,
      "duration": 846,
      "service": 600,
      "steps": [
        {"type": "start", "location": [126.978, 37.5665], "arrival": 1700000000},
        {"type": "job", "id": 3, "location": [126.97, 37.555], "arrival": 1700000256},
        {"type": "job", "id": 5, "location": [126.99, 37.54], "arrival": 1700000888},
        {"type": "end", "location": [126.978, 37.5665], "arrival": 1700001446}
      ]
    }
  ],

  "summary": {
    "cost": 2010,
    "routes": 2,
    "unassigned": 0,
    "duration": 2010,
    "service": 1500,
    "waiting_time": 0
  },

  "unassigned": [],

  "analysis": {
    "quality_score": 93.6,
    "assignment_rate": 100.0,
    "route_balance": {
      "balance_score": 80.0,
      "routes": [
        {"vehicle": 1, "num_jobs": 3, "duration": 1164},
        {"vehicle": 2, "num_jobs": 2, "duration": 846}
      ]
    },
    "suggestions": ["최적화 결과가 우수합니다!"]
  },

  "statistics": {
    "vehicle_utilization": {
      "vehicles": [
        {"vehicle": 1, "jobs": 3, "duration_min": 19.4, "capacity_used": 3},
        {"vehicle": 2, "jobs": 2, "duration_min": 14.1, "capacity_used": 2}
      ]
    },
    "cost_breakdown": {
      "total_cost": 2010,
      "total_duration_hours": 0.56,
      "service_time_hours": 0.42
    },
    "time_analysis": {
      "travel_time_sec": 510,
      "service_time_sec": 1500,
      "travel_percentage": 25.4
    },
    "efficiency_metrics": {
      "jobs_per_vehicle": 2.5,
      "minutes_per_job": 6.7
    }
  },

  "_metadata": {
    "api_key": "Demo Client",
    "control_level": "STANDARD",
    "engine": "direct",
    "processing_time_ms": 43,
    "from_cache": false
  }
}
```

**주요 필드 설명:**

| 필드 | 설명 |
|------|------|
| `routes[].steps` | 차량별 방문 순서 (type: start → job → end, arrival은 UNIX timestamp) |
| `routes[].cost` | 경로 비용 (초 단위 이동 시간) |
| `summary.unassigned` | 미배정 작업 수 (0이면 전체 배정 성공) |
| `unassigned[]` | 미배정된 작업 목록 + 사유 |
| `analysis.quality_score` | 0~100 품질 점수 (90+ 우수) |
| `analysis.route_balance.balance_score` | 경로 간 균형도 (100 = 완벽 균형) |
| `statistics.time_analysis.travel_percentage` | 이동시간 비율 (낮을수록 효율적) |
| `_metadata.engine` | `"direct"` = v3.0 직접 호출, `"http"` = v2.0 HTTP 폴백 |
| `_metadata.from_cache` | `true`면 캐시에서 반환 (동일 요청 재전송 시) |

---

## 4단계: 환경변수 튜닝

`docker-compose.v3.yml`의 `environment` 섹션에서 설정.
또는 `.env` 파일 생성.

### 성능 튜닝

```bash
# VROOM 스레드 (CPU 코어 수에 맞게)
VROOM_THREADS=8               # 기본 4

# 탐색 깊이 (0=최소, 5=최대)
VROOM_EXPLORATION=5           # 높을수록 좋지만 느림

# 타임아웃
VROOM_TIMEOUT=300             # 300초 (5분)
```

### 2-Pass 최적화 활성화

대규모 배차 (작업 50개 이상)에서 권장:

```bash
TWO_PASS_ENABLED=true
TWO_PASS_MAX_WORKERS=4        # 동시에 최적화하는 경로 수
TWO_PASS_INITIAL_THREADS=16   # Pass 1 (배정) 스레드
TWO_PASS_ROUTE_THREADS=4      # Pass 2 (경로 최적화) 스레드
```

### HTTP 폴백 모드

VROOM 바이너리 없이 기존 vroom-express 사용:

```bash
USE_DIRECT_CALL=false
VROOM_URL=http://vroom:3000
```

이 경우 별도의 vroom-express 컨테이너가 필요합니다.
(`docker-compose-v2-full.yml` 사용)

---

## 5단계: 문제 해결

### VROOM 바이너리 에러

```
헬스 체크에서 "vroom_binary": "error"
```

**원인**: Dockerfile.v3 빌드 시 VROOM 바이너리 복사 실패

**해결**:
```bash
# 컨테이너 안에서 확인
docker exec -it vroom-wrapper-v3 ls -la /usr/local/bin/vroom
docker exec -it vroom-wrapper-v3 vroom --version

# 라이브러리 의존성 확인
docker exec -it vroom-wrapper-v3 ldd /usr/local/bin/vroom
```

### OSRM 연결 실패

```
VROOM routing error: ...
```

**원인**: OSRM 서버 미가동 또는 데이터 미준비

**해결**:
```bash
# OSRM 상태 확인
curl http://localhost:5000/nearest/v1/driving/127.0,37.5

# OSRM 데이터 확인
ls -la /home/shawn/osrm-data/*.osrm

# OSRM 로그 확인
docker compose -f docker-compose.v3.yml logs osrm
```

### 도달 불가능 작업이 너무 많이 필터링됨

**원인**: 임계값이 너무 낮음

**해결**:
```bash
# 임계값 올리기 (기본: 43200초 = 12시간)
UNREACHABLE_THRESHOLD=86400   # 24시간으로 변경

# 또는 필터링 비활성화
UNREACHABLE_FILTER_ENABLED=false
```

### 메모리 부족

대규모 매트릭스 (500+ 위치) 처리 시:

```bash
# 청크 크기 줄이기
OSRM_CHUNK_SIZE=50            # 기본 75 → 50으로

# 동시 워커 줄이기
OSRM_MAX_WORKERS=4            # 기본 8 → 4로
```

---

## 아키텍처 요약

```
v3.0 = Roouty Engine(Go)의 성능 + Python Wrapper의 기능

Roouty에서 가져온 것 (성능):
├── VROOM 바이너리 직접 호출 (subprocess stdin/stdout)
├── 2-Pass 최적화 (배정 → 경로별 재최적화)
├── 도달 불가능 작업 사전 필터링
└── OSRM 매트릭스 병렬 청킹

Python에서 유지한 것 (기능):
├── 실시간 교통 API (TMap/Kakao/Naver)
├── 다중 시나리오 비교 최적화
├── 결과 품질 분석 + 개선 제안
├── 비즈니스 규칙 엔진 (VIP/긴급/지역)
├── 미배정 사유 분석
├── Redis 캐싱
├── API Key 인증 + Rate Limiting
└── 상세 통계 생성

컨테이너 구성: 4개
├── OSRM (:5000)      - 거리/시간 계산
├── Valhalla (:8002)  - Time-dependent 라우팅
├── Redis (:6379)     - 캐싱
└── Wrapper (:8000)   - Python + VROOM 바이너리 통합
```

---

## 빠른 시작 체크리스트

```
[ ] Docker Desktop WSL2 통합 활성화
[ ] vroom-local:latest 이미지 확인 (docker images | grep vroom-local)
[ ] OSRM 데이터 확인 (ls /home/shawn/osrm-data/*.osrm)
[ ] docker compose -f docker-compose.v3.yml up -d --build
[ ] curl http://localhost:8000/health → "vroom_binary": "healthy" 확인
[ ] BASIC 테스트 (2-1 예시 복사해서 실행)
[ ] STANDARD 테스트 → analysis + statistics 확인
[ ] PREMIUM 테스트 → multi_scenario_metadata 확인
```

---

## 참고: OSRM 데이터 경로

docker-compose.v3.yml은 OSRM 데이터를 다음 경로에서 마운트합니다:
```
/home/shawn/osrm-data → 컨테이너 /data
```
경로를 변경하려면 `docker-compose.v3.yml`의 `osrm.volumes`를 수정하세요.

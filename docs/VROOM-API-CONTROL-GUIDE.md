# VROOM API 통제 및 커스터마이징 가이드

## 개요

VROOM을 API로 통제하고 커스터마이징하는 방법은 크게 4가지 레벨로 나뉩니다:

1. **설정 파일 수정** (가장 간단) - 재시작만으로 적용
2. **vroom-express 미들웨어 추가** (중급) - Node.js 코드 수정
3. **VROOM 코어 수정** (고급) - C++ 코드 수정
4. **커스텀 API 래퍼 개발** (최고급) - 완전한 제어

---

## 1. 설정 파일 수정 (가장 간단)

### 현재 설정 위치
```
/home/shawn/vroom-conf/config.yml
```

### 수정 가능한 주요 파라미터

```yaml
cliArgs:
  geometry: true          # 경로 geometry 반환 여부
  planmode: false         # plan 모드 활성화
  threads: 4              # 병렬 처리 스레드 수
  explore: 5              # 탐색 레벨 (0-5)
  limit: '1mb'            # 최대 요청 크기
  maxlocations: 1000      # 최대 작업 위치 수
  maxvehicles: 200        # 최대 차량 수
  timeout: 300000         # 요청 타임아웃 (밀리초)
  baseurl: '/'            # API 베이스 URL
  port: 3000              # 서비스 포트
```

### 적용 방법

```bash
# 1. 설정 파일 수정
nano /home/shawn/vroom-conf/config.yml

# 2. VROOM 컨테이너 재시작
docker-compose restart vroom

# 3. 변경사항 확인
docker logs vroom-server
```

### 사용 예시: 대규모 작업 처리

```yaml
cliArgs:
  threads: 8              # CPU 코어에 맞게 증가
  explore: 3              # 속도 우선 (정확도는 약간 낮음)
  maxlocations: 5000      # 더 많은 위치 허용
  maxvehicles: 500        # 더 많은 차량 허용
  timeout: 600000         # 10분 타임아웃
```

---

## 2. vroom-express 미들웨어 커스터마이징

vroom-express는 Node.js 기반 HTTP 래퍼입니다. 다음과 같은 커스터마이징이 가능합니다.

### A. 인증/권한 추가

컨테이너 내부의 vroom-express 소스를 수정하거나, 커스텀 버전을 빌드:

```javascript
// /vroom-express/src/index.js에 추가

// API Key 인증 미들웨어
app.use((req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  const validKeys = ['your-secret-key-1', 'your-secret-key-2'];

  if (!validKeys.includes(apiKey)) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Invalid API key'
    });
  }
  next();
});

// Rate Limiting
const rateLimit = require('express-rate-limit');
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 100, // 최대 100 요청
  message: 'Too many requests, please try again later.'
});
app.use(limiter);
```

### B. 요청/응답 전처리

```javascript
// 요청 전처리 - 좌표 검증
app.use((req, res, next) => {
  if (req.body.jobs) {
    req.body.jobs = req.body.jobs.filter(job => {
      const [lon, lat] = job.location;
      // 한국 내 좌표만 허용
      return lon >= 124 && lon <= 132 && lat >= 33 && lat <= 43;
    });
  }
  next();
});

// 응답 후처리 - 메타데이터 추가
app.use((req, res, next) => {
  const originalSend = res.send;
  res.send = function(data) {
    if (typeof data === 'string') {
      const jsonData = JSON.parse(data);
      jsonData.metadata = {
        timestamp: new Date().toISOString(),
        server: 'custom-vroom-server',
        version: '1.0.0'
      };
      data = JSON.stringify(jsonData);
    }
    originalSend.call(this, data);
  };
  next();
});
```

### C. 커스텀 엔드포인트 추가

```javascript
// 통계 엔드포인트
let requestCount = 0;
let totalProcessingTime = 0;

app.get('/stats', (req, res) => {
  res.json({
    total_requests: requestCount,
    avg_processing_time: requestCount > 0 ? totalProcessingTime / requestCount : 0,
    uptime: process.uptime()
  });
});

// 배치 처리 엔드포인트
app.post('/batch', async (req, res) => {
  const requests = req.body.requests; // 여러 최적화 요청
  const results = [];

  for (const request of requests) {
    // 각 요청을 순차적으로 처리
    const result = await processVroomRequest(request);
    results.push(result);
  }

  res.json({ results });
});
```

### 커스텀 vroom-express 적용 방법

```bash
# 1. vroom-express를 로컬에 클론
git clone https://github.com/VROOM-Project/vroom-express.git custom-vroom-express
cd custom-vroom-express

# 2. src/index.js 수정
nano src/index.js

# 3. 커스텀 Dockerfile 생성
cat > Dockerfile.custom << 'EOF'
FROM node:20-bookworm-slim

# VROOM 바이너리 복사 (기존 이미지에서)
COPY --from=vroom-local:latest /usr/local/bin/vroom /usr/local/bin/

# 커스텀 vroom-express 복사
COPY . /vroom-express
WORKDIR /vroom-express

RUN npm install

EXPOSE 3000
CMD ["npm", "start"]
EOF

# 4. 빌드 및 실행
docker build -f Dockerfile.custom -t vroom-custom:latest .
```

---

## 3. VROOM 코어 알고리즘 수정 (고급)

VROOM 자체의 최적화 알고리즘을 수정하려면 C++ 소스를 수정해야 합니다.

### A. 커스텀 제약 조건 추가

```cpp
// vroom/src/problems/vrp.cpp

// 예: 특정 작업은 특정 시간대에만 방문 가능
bool VRP::is_valid_for_vehicle(Job& job, Vehicle& vehicle) {
  // 커스텀 로직
  if (job.priority > 100 && vehicle.id != 1) {
    return false; // 높은 우선순위 작업은 차량 1만 처리
  }
  return true;
}
```

### B. 커스텀 비용 함수

```cpp
// vroom/src/utils/helpers.cpp

// 거리 대신 시간+비용 혼합 메트릭 사용
Cost compute_custom_cost(const Location& from, const Location& to) {
  Cost distance_cost = compute_distance(from, to);
  Cost time_cost = compute_time(from, to);
  Cost toll_cost = get_toll_cost(from, to); // 통행료

  return distance_cost * 0.5 + time_cost * 0.3 + toll_cost * 0.2;
}
```

### 커스텀 VROOM 빌드

```bash
# 1. VROOM 소스 수정
cd /home/shawn/vroom
nano src/problems/vrp.cpp

# 2. Docker 빌드 (기존 Dockerfile 사용)
cd /home/shawn/vroom-docker
docker build -t vroom-custom:latest \
  --build-arg VROOM_RELEASE=master \
  --build-arg VROOM_EXPRESS_RELEASE=master .

# 3. docker-compose.yml에서 이미지 변경
# image: vroom-custom:latest

# 4. 재시작
docker-compose up -d vroom
```

---

## 4. 완전한 커스텀 API 래퍼 (최고급)

VROOM CLI를 직접 호출하는 Python/Go/Java API를 만들 수 있습니다.

### Python 예시: FastAPI 래퍼

```python
# custom_vroom_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import logging

app = FastAPI()

class VRPRequest(BaseModel):
    vehicles: list
    jobs: list
    shipments: list = []

class VRPResponse(BaseModel):
    code: int
    summary: dict
    routes: list

@app.post("/optimize", response_model=VRPResponse)
async def optimize_route(request: VRPRequest):
    # 전처리: 비즈니스 로직 적용
    request = preprocess_request(request)

    # VROOM 호출
    result = call_vroom(request)

    # 후처리: 결과 가공
    result = postprocess_result(result)

    return result

def preprocess_request(request: VRPRequest):
    """요청 전처리"""
    # 좌표 검증
    for job in request.jobs:
        if not is_valid_coordinate(job['location']):
            raise HTTPException(status_code=400, detail="Invalid coordinates")

    # 우선순위 자동 할당
    for i, job in enumerate(request.jobs):
        if 'priority' not in job:
            job['priority'] = calculate_priority(job)

    return request

def call_vroom(request: VRPRequest):
    """VROOM CLI 호출"""
    # JSON 파일로 저장
    with open('/tmp/vroom_input.json', 'w') as f:
        json.dump(request.dict(), f)

    # VROOM 실행
    cmd = [
        'vroom',
        '-i', '/tmp/vroom_input.json',
        '-g',  # geometry 포함
        '-t', '4',  # 4 스레드
        '-x', '5',  # explore 레벨 5
        '-r', 'osrm',
        '-a', 'http://localhost:5000'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="VROOM optimization failed")

    return json.loads(result.stdout)

def postprocess_result(result):
    """결과 후처리"""
    # 추가 메타데이터
    result['metadata'] = {
        'optimization_quality': calculate_quality_score(result),
        'estimated_fuel_cost': calculate_fuel_cost(result),
        'carbon_footprint': calculate_carbon(result)
    }

    # 경로 최적화 제안
    result['suggestions'] = generate_suggestions(result)

    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Docker로 커스텀 API 실행

```dockerfile
# Dockerfile.custom-api
FROM python:3.11-slim

# VROOM 바이너리 복사
COPY --from=vroom-local:latest /usr/local/bin/vroom /usr/local/bin/

# 런타임 의존성 설치
RUN apt-get update && apt-get install -y libglpk40 && rm -rf /var/lib/apt/lists/*

# API 코드 복사
COPY custom_vroom_api.py /app/
COPY requirements.txt /app/
WORKDIR /app

# Python 의존성 설치
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "custom_vroom_api.py"]
```

```yaml
# docker-compose.yml에 추가
services:
  custom-vroom-api:
    build:
      context: .
      dockerfile: Dockerfile.custom-api
    ports:
      - "8000:8000"
    environment:
      - OSRM_HOST=osrm
      - OSRM_PORT=5000
    depends_on:
      - osrm
    networks:
      - routing-network
```

---

## 5. 실전 사용 사례별 구현

### A. 배달 서비스 - 시간 제약 강화

```yaml
# config.yml
cliArgs:
  geometry: true
  threads: 8
  explore: 5      # 정확도 우선
  timeout: 600000 # 10분

# API 요청 예시
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "time_window": [28800, 64800],  # 08:00 ~ 18:00
    "capacity": [100],
    "breaks": [{
      "id": 1,
      "time_windows": [[43200, 46800]],  # 12:00 ~ 13:00 점심
      "service": 3600
    }]
  }],
  "jobs": [{
    "id": 1,
    "location": [127.0276, 37.4979],
    "time_windows": [[32400, 36000]],  # 09:00 ~ 10:00
    "service": 300  # 5분 서비스 시간
  }]
}
```

### B. 물류 최적화 - 용량 제약

```python
# 전처리: 작업을 차량 용량에 맞게 그룹핑
def preprocess_for_capacity(jobs, vehicle_capacity):
    """작업을 용량별로 그룹핑하여 여러 번의 최적화 실행"""
    groups = []
    current_group = []
    current_load = 0

    for job in sorted(jobs, key=lambda x: x['delivery'][0], reverse=True):
        job_load = job['delivery'][0]
        if current_load + job_load <= vehicle_capacity:
            current_group.append(job)
            current_load += job_load
        else:
            groups.append(current_group)
            current_group = [job]
            current_load = job_load

    if current_group:
        groups.append(current_group)

    return groups
```

### C. 동적 재최적화 - 실시간 주문 추가

```python
# WebSocket을 통한 실시간 재최적화
from fastapi import WebSocket

@app.websocket("/ws/optimize")
async def websocket_optimize(websocket: WebSocket):
    await websocket.accept()

    current_solution = None

    while True:
        # 새 주문 수신
        data = await websocket.receive_json()

        if data['type'] == 'new_order':
            # 기존 솔루션에 새 주문 추가
            updated_request = add_job_to_solution(current_solution, data['job'])

            # 재최적화
            new_solution = call_vroom(updated_request)

            # 변경사항만 전송
            changes = compute_changes(current_solution, new_solution)
            await websocket.send_json({
                'type': 'solution_update',
                'changes': changes
            })

            current_solution = new_solution
```

---

## 6. 모니터링 및 로깅 추가

### Prometheus 메트릭 추가

```javascript
// vroom-express에 메트릭 추가
const promClient = require('prom-client');

// 메트릭 정의
const httpRequestDuration = new promClient.Histogram({
  name: 'vroom_http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code']
});

const optimizationDuration = new promClient.Histogram({
  name: 'vroom_optimization_duration_seconds',
  help: 'Duration of VROOM optimization in seconds',
  labelNames: ['num_jobs', 'num_vehicles']
});

// 메트릭 엔드포인트
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.end(await promClient.register.metrics());
});
```

---

## 7. 요약 및 권장사항

### 상황별 추천 방법

| 요구사항 | 권장 방법 | 난이도 |
|---------|----------|--------|
| 기본 파라미터 조정 | config.yml 수정 | ⭐ |
| 인증/Rate Limiting | vroom-express 미들웨어 | ⭐⭐ |
| 비즈니스 로직 추가 | Python/Node.js 래퍼 | ⭐⭐⭐ |
| 최적화 알고리즘 수정 | VROOM 코어 수정 | ⭐⭐⭐⭐⭐ |

### 실전 구현 체크리스트

- [ ] 설정 파일로 기본 파라미터 조정
- [ ] 인증/권한 미들웨어 추가
- [ ] Rate Limiting 구현
- [ ] 요청 전처리 (좌표 검증, 우선순위 계산)
- [ ] 응답 후처리 (메타데이터, 비용 계산)
- [ ] 로깅 및 모니터링 추가
- [ ] 에러 처리 및 재시도 로직
- [ ] 배치 처리 기능
- [ ] 캐싱 전략 (동일 요청에 대한 결과 캐싱)
- [ ] 성능 최적화 (병렬 처리, 비동기)

자세한 구현이 필요하면 말씀해주세요!

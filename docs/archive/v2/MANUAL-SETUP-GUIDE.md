# VROOM Wrapper v2.0 수동 설치 가이드

**목표**: 자동화 스크립트 없이 모든 컴포넌트를 직접 설치하고 설정하며, 각 단계를 완전히 이해하고 제어합니다.

---

## 📋 목차

1. [시스템 아키텍처 이해](#1-시스템-아키텍처-이해)
2. [기본 환경 준비](#2-기본-환경-준비)
3. [VROOM 서버 설정](#3-vroom-서버-설정)
4. [Redis 설정 (선택)](#4-redis-설정-선택)
5. [Wrapper 의존성 설치](#5-wrapper-의존성-설치)
6. [설정 파일 구성](#6-설정-파일-구성)
7. [단계별 검증](#7-단계별-검증)
8. [실시간 교통 매트릭스 (Phase 1.5)](#8-실시간-교통-매트릭스-phase-15)
9. [프로덕션 설정](#9-프로덕션-설정)
10. [모니터링 및 로그](#10-모니터링-및-로그)
11. [문제 해결](#11-문제-해결)

---

## 1. 시스템 아키텍처 이해

### 1.1 전체 구조

```
[클라이언트]
    ↓ HTTP POST
[Wrapper v2.0:8000]  ← 이 프로젝트
    ↓ (Phase 1-3)
    ├─→ [Redis:6379]         (캐싱, 선택사항)
    ├─→ [TMap/Kakao/Naver]   (실시간 교통, 선택사항)
    └─→ [VROOM:3000]
            ↓
        [OSRM:5000]          (도로망 거리 계산)
```

### 1.2 각 컴포넌트 역할

| 컴포넌트 | 포트 | 필수? | 역할 |
|---------|------|-------|------|
| **Wrapper v2.0** | 8000 | ✅ 필수 | 입력 검증, 전처리, 통제, 분석 |
| **VROOM** | 3000 | ✅ 필수 | VRP 최적화 엔진 |
| **OSRM** | 5000 | ✅ 필수 | 도로망 기반 거리 계산 |
| **Redis** | 6379 | ⚠️ 선택 | 결과 캐싱 (없으면 메모리 사용) |
| **TMap/Kakao/Naver** | 외부 | ⚠️ 선택 | 실시간 교통 기반 소요시간 |

### 1.3 데이터 흐름

```
입력 JSON
  ↓
Phase 1: 검증 + 정규화 + 비즈니스 룰
  ↓
Phase 1.5: 실시간 교통 매트릭스 (선택)
  │  ├─ 거리: OSRM (도로망 기반, 정적)
  │  └─ 시간: TMap/Kakao/Naver (실시간 교통)
  ↓
Phase 2: VROOM 최적화 (BASIC/STANDARD/PREMIUM)
  │  └─ 매트릭스 있으면 → OSRM 호출 생략, 직접 사용
  ↓
Phase 3: 품질 분석 + 통계 생성
  ↓
응답 JSON (경로 + 분석 + 통계)
```

**✅ 체크포인트**: 위 구조를 이해했다면 다음 단계로 진행하세요.

---

## 2. 기본 환경 준비

### 2.1 Python 버전 확인

```bash
python --version
```

**필요**: Python 3.8 이상 (권장: 3.10)

**없다면**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# macOS
brew install python@3.10
```

**확인**:
```bash
python --version
# 출력: Python 3.10.x
```

### 2.2 가상 환경 생성 (권장)

**왜?**: 시스템 Python과 분리하여 의존성 충돌 방지

```bash
cd /home/shawn/vroom-wrapper-project

# 가상환경 생성
python -m venv venv

# 활성화
source venv/bin/activate  # Linux/macOS
# 또는
venv\Scripts\activate     # Windows

# 확인
which python
# 출력: /home/shawn/vroom-wrapper-project/venv/bin/python
```

**✅ 체크포인트**: `which python`이 venv 경로를 가리키는지 확인

### 2.3 pip 업그레이드

```bash
pip install --upgrade pip

# 확인
pip --version
# 출력: pip 24.x.x
```

---

## 3. VROOM 서버 설정

### 3.1 옵션 선택

**옵션 A**: Docker로 VROOM + OSRM 설치 (간단, 권장)
**옵션 B**: 직접 컴파일 설치 (고급, 커스터마이징 가능)

### 3.2 옵션 A: Docker 설치

#### 3.2.1 Docker 설치 확인

```bash
docker --version
docker-compose --version
```

**없다면**:
```bash
# Ubuntu
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER
# 로그아웃 후 재로그인

# macOS
brew install docker docker-compose
```

#### 3.2.2 OSRM 데이터 준비

```bash
# 데이터 디렉토리 생성
mkdir -p osrm-data
cd osrm-data

# 한국 지도 다운로드 (약 100MB)
wget http://download.geofabrik.de/asia/south-korea-latest.osm.pbf

# OSRM 형식으로 변환 (10분 소요)
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/south-korea-latest.osm.pbf

# 파티션 생성 (5분 소요)
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/south-korea-latest.osrm

# 커스터마이징 (2분 소요)
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/south-korea-latest.osrm

cd ..
```

**확인**:
```bash
ls -lh osrm-data/*.osrm
# 다음 파일들이 있어야 함:
# - south-korea-latest.osrm
# - south-korea-latest.osrm.cells
# - south-korea-latest.osrm.edges
# - south-korea-latest.osrm.icd
# - south-korea-latest.osrm.mldgr
```

#### 3.2.3 OSRM 서버 시작

```bash
docker run -d \
  --name osrm-server \
  -p 5000:5000 \
  -v "${PWD}/osrm-data:/data" \
  ghcr.io/project-osrm/osrm-backend:latest \
  osrm-routed --algorithm mld /data/south-korea-latest.osrm \
  --max-table-size 10000 --port 5000 --ip 0.0.0.0
```

**확인**:
```bash
# 1. 컨테이너 실행 중인지 확인
docker ps | grep osrm
# 출력: osrm-server ... Up ... 0.0.0.0:5000->5000/tcp

# 2. API 응답 테스트
curl "http://localhost:5000/route/v1/driving/126.9780,37.5665;127.0276,37.4979?overview=false"
# 출력: {"code":"Ok",...} (JSON 응답)
```

**로그 확인**:
```bash
docker logs osrm-server
# 출력: [info] starting up engines...
#       [info] loaded plugin: ...
```

#### 3.2.4 VROOM 서버 시작

```bash
docker run -d \
  --name vroom-server \
  -p 3000:3000 \
  --link osrm-server:osrm \
  -e VROOM_ROUTER=osrm \
  vroomvrp/vroom-docker:latest
```

**확인**:
```bash
# 1. 컨테이너 실행 확인
docker ps | grep vroom
# 출력: vroom-server ... Up ... 0.0.0.0:3000->3000/tcp

# 2. Health check
curl http://localhost:3000/health
# 출력: {"status":"ok"} 또는 유사한 응답

# 3. 실제 최적화 테스트
curl -X POST http://localhost:3000 \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [{"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665]}],
    "jobs": [
      {"id": 1, "location": [127.0276, 37.4979]},
      {"id": 2, "location": [127.0017, 37.5642]}
    ]
  }'

# 출력: {"code":0, "summary":{...}, "routes":[...]} (JSON 응답)
```

**✅ 체크포인트**:
- OSRM 서버가 5000 포트에서 응답
- VROOM 서버가 3000 포트에서 응답
- 테스트 최적화 요청이 성공

### 3.3 옵션 B: 직접 설치 (고급)

**OSRM 빌드** (고급 사용자):
```bash
git clone https://github.com/Project-OSRM/osrm-backend.git
cd osrm-backend
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
sudo make install
```

**VROOM 빌드**:
```bash
git clone https://github.com/VROOM-Project/vroom.git
cd vroom/src
make
sudo make install
```

---

## 4. Redis 설정 (선택)

### 4.1 Redis가 필요한가?

**필요한 경우**:
- 동일한 요청이 자주 반복됨
- 응답 시간을 최소화하고 싶음
- 여러 Wrapper 인스턴스를 실행 (로드밸런싱)

**불필요한 경우**:
- 모든 요청이 고유함
- 메모리 캐싱으로 충분
- 단일 서버 운영

### 4.2 Redis 설치 (선택한 경우)

```bash
# Ubuntu
sudo apt install redis-server

# macOS
brew install redis

# Docker
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine
```

**시작**:
```bash
# 시스템 서비스
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Docker (이미 시작됨)
```

**확인**:
```bash
# 연결 테스트
redis-cli ping
# 출력: PONG

# 버전 확인
redis-cli --version
# 출력: redis-cli 7.x.x

# 간단한 캐시 테스트
redis-cli set test_key "hello"
redis-cli get test_key
# 출력: "hello"

redis-cli del test_key
```

**✅ 체크포인트**: Redis가 6379 포트에서 응답 (또는 건너뛰기)

---

## 5. Wrapper 의존성 설치

### 5.1 requirements-v2.txt 확인

```bash
cat requirements-v2.txt
```

**내용**:
```
fastapi==0.109.0      # 웹 프레임워크
uvicorn[standard]==0.27.0  # ASGI 서버
pydantic==2.5.3       # 데이터 검증
httpx==0.26.0         # 비동기 HTTP 클라이언트
redis==5.0.1          # Redis 연결 (선택)
pytest==7.4.3         # 테스트 (개발용)
pytest-asyncio==0.21.1
```

### 5.2 의존성 설치 (하나씩)

```bash
# 1. 코어 프레임워크
pip install fastapi==0.109.0
pip show fastapi
# 확인: Version: 0.109.0

# 2. ASGI 서버
pip install uvicorn[standard]==0.27.0
pip show uvicorn
# 확인: Version: 0.27.0

# 3. 데이터 검증
pip install pydantic==2.5.3
python -c "import pydantic; print(pydantic.__version__)"
# 출력: 2.5.3

# 4. HTTP 클라이언트
pip install httpx==0.26.0
python -c "import httpx; print(httpx.__version__)"
# 출력: 0.26.0

# 5. Redis (Redis를 사용하는 경우만)
pip install redis==5.0.1
python -c "import redis; print(redis.__version__)"
# 출력: 5.0.1

# 6. 테스트 도구 (개발 시)
pip install pytest==7.4.3 pytest-asyncio==0.21.1
```

**또는 한번에**:
```bash
pip install -r requirements-v2.txt
```

**확인**:
```bash
pip list | grep -E "(fastapi|uvicorn|pydantic|httpx|redis|pytest)"

# 출력:
# fastapi          0.109.0
# uvicorn          0.27.0
# pydantic         2.5.3
# httpx            0.26.0
# redis            5.0.1
# pytest           7.4.3
# pytest-asyncio   0.21.1
```

**✅ 체크포인트**: 모든 패키지가 올바른 버전으로 설치됨

---

## 6. 설정 파일 구성

### 6.1 환경 변수 설정

**`.env` 파일 생성** (프로젝트 루트):
```bash
cat > .env << 'EOF'
# VROOM 서버 설정
VROOM_URL=http://localhost:3000

# Redis 설정 (선택, 주석 처리하면 메모리 캐싱 사용)
REDIS_URL=redis://localhost:6379

# API 서버 설정
HOST=0.0.0.0
PORT=8000

# 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600  # 초 단위
EOF
```

**확인**:
```bash
cat .env
```

### 6.2 API Key 설정

**`src/config.py` 생성**:
```bash
cat > src/config.py << 'EOF'
"""
설정 파일
이 파일을 수정하여 API Key, Rate Limit, 캐싱 등을 제어합니다.
"""

import os

# API Keys 정의
# 프로덕션에서는 환경 변수나 별도의 secrets 관리 시스템 사용
API_KEYS = {
    "demo-key-12345": {
        "name": "Demo Client",
        "rate_limit": "100/hour",
        "features": ["basic", "standard", "premium"]
    },
    "prod-key-67890": {
        "name": "Production Client",
        "rate_limit": "1000/hour",
        "features": ["basic", "standard", "premium"]
    },
    # 여기에 새로운 API Key 추가
}

# VROOM 서버
VROOM_URL = os.getenv("VROOM_URL", "http://localhost:3000")

# Redis
REDIS_URL = os.getenv("REDIS_URL", None)  # None이면 메모리 캐싱

# 서버
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 로그
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Rate Limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))
EOF
```

**확인**:
```bash
cat src/config.py
python -c "from src.config import API_KEYS; print(list(API_KEYS.keys()))"
# 출력: ['demo-key-12345', 'prod-key-67890']
```

### 6.3 main.py 수정 (config 사용)

**src/main.py에서 하드코딩된 설정 제거**:
```bash
# main.py 첫 부분에 추가
sed -i '1i from config import API_KEYS, VROOM_URL, REDIS_URL, HOST, PORT' src/main.py

# 또는 직접 편집
nano src/main.py
# import config 추가하고 API_KEYS = config.API_KEYS 사용
```

**✅ 체크포인트**:
- `.env` 파일 생성됨
- `src/config.py` 생성됨
- API Key 목록 확인됨

---

## 7. 단계별 검증

### 7.1 Phase 1 단독 테스트 (전처리)

```bash
python << 'EOF'
import asyncio
from src.preprocessing.preprocessor import PreProcessor

async def test_phase1():
    preprocessor = PreProcessor()

    # 테스트 입력
    raw_input = {
        "vehicles": [
            {"id": 1, "start": [126.9780, 37.5665]}  # 서울시청
        ],
        "jobs": [
            {"id": 1, "location": [127.0276, 37.4979], "description": "VIP 고객"}
        ]
    }

    # Phase 1 실행
    result = await preprocessor.process(raw_input)

    # 확인
    print("✅ Phase 1 성공!")
    print(f"Jobs: {len(result['jobs'])}")
    print(f"VIP 스킬 부여: {10000 in result['jobs'][0].get('skills', [])}")

    return result

result = asyncio.run(test_phase1())
EOF
```

**예상 출력**:
```
✅ Phase 1 성공!
Jobs: 1
VIP 스킬 부여: True
```

### 7.2 VROOM 연동 테스트 (Phase 2)

```bash
python << 'EOF'
import httpx
import asyncio

async def test_vroom():
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
            "jobs": [{"id": 1, "location": [127.0276, 37.4979]}]
        }

        response = await client.post("http://localhost:3000", json=payload)
        result = response.json()

        print("✅ VROOM 연동 성공!")
        print(f"Code: {result.get('code')}")
        print(f"Routes: {len(result.get('routes', []))}")

        return result

asyncio.run(test_vroom())
EOF
```

**예상 출력**:
```
✅ VROOM 연동 성공!
Code: 0
Routes: 1
```

### 7.3 캐싱 테스트 (Redis 사용 시)

```bash
python << 'EOF'
from src.extensions.cache_manager import CacheManager
import time

# Redis 연결
cache = CacheManager(redis_url="redis://localhost:6379")

# 테스트 데이터
test_data = {"test": "data"}

# 캐시 저장
key = cache.set(test_data, {"result": "cached"}, ttl=60)
print(f"✅ 캐시 저장: {key[:16]}...")

# 캐시 조회
cached = cache.get(test_data)
print(f"✅ 캐시 조회: {cached}")

# 통계
stats = cache.get_stats()
print(f"캐시 통계: {stats}")
EOF
```

**예상 출력**:
```
✅ 캐시 저장: a3f5e8b9c2d1...
✅ 캐시 조회: {'result': 'cached'}
캐시 통계: {'hits': 1, 'misses': 0, 'size': 1}
```

### 7.4 전체 파이프라인 테스트

```bash
python demo_v2.py
```

**예상 출력**:
```
========================================
VROOM Wrapper v2.0 데모
========================================

--- Phase 1: 전처리 ---
✅ 검증 완료
✅ 정규화 완료
✅ 비즈니스 룰 적용 완료

--- Phase 2: 최적화 (STANDARD) ---
✅ VROOM 최적화 완료 (10ms)

--- Phase 3: 분석 ---
품질 점수: 84.2/100
배정률: 100.0%
...
```

**✅ 체크포인트**:
- Phase 1 단독 테스트 성공
- VROOM 연동 성공
- 캐싱 동작 확인 (Redis 사용 시)
- 전체 파이프라인 성공

---

## 8. 실시간 교통 매트릭스 (Phase 1.5)

### 8.1 개념 이해

**문제**: OSRM은 도로망 기반 정적 소요시간만 계산 (실시간 교통 상황 미반영)

**해결**: 외부 API (TMap/Kakao/Naver)로 실시간 교통 기반 소요시간 계산

**하이브리드 접근**:
```
거리(distance): OSRM 사용 (도로망 기반, 정적, 무료)
시간(duration): TMap/Kakao/Naver (실시간 교통, 동적, 유료)
```

**VROOM에 매트릭스 주입**:
```json
{
  "vehicles": [...],
  "jobs": [...],
  "matrix": {
    "durations": [[0, 1800, 2400], [1800, 0, 1200], ...],
    "distances": [[0, 5000, 8000], [5000, 0, 4000], ...]
  }
}
```

→ VROOM은 OSRM을 호출하지 않고 제공된 매트릭스를 직접 사용

### 8.2 API 키 발급

#### TMap

1. https://openapi.sk.com 접속
2. 회원가입 및 로그인
3. "내 애플리케이션" → "앱 생성"
4. "Tmap 경로안내" API 사용 신청
5. 발급된 `appKey` 복사

#### Kakao

1. https://developers.kakao.com 접속
2. 회원가입 및 로그인
3. "내 애플리케이션" → "애플리케이션 추가"
4. "카카오 모빌리티" 사용 설정
5. "REST API 키" 복사

#### Naver

1. https://console.ncloud.com 접속
2. 회원가입 및 로그인
3. "AI·NAVER API" → "Maps" → "Directions 5"
4. "애플리케이션 등록"
5. `Client ID`와 `Client Secret` 복사

### 8.3 환경 변수 설정

```bash
# .env 파일 수정
nano .env
```

**TMap 사용**:
```bash
TRAFFIC_MATRIX_ENABLED=true
TRAFFIC_PROVIDER=tmap
TMAP_API_KEY=your_tmap_api_key_here
```

**Kakao 사용**:
```bash
TRAFFIC_MATRIX_ENABLED=true
TRAFFIC_PROVIDER=kakao
KAKAO_API_KEY=your_kakao_rest_api_key_here
```

**Naver 사용**:
```bash
TRAFFIC_MATRIX_ENABLED=true
TRAFFIC_PROVIDER=naver
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

**비활성화 (OSRM만 사용)**:
```bash
TRAFFIC_MATRIX_ENABLED=false
TRAFFIC_PROVIDER=osrm
```

### 8.4 테스트

#### 8.4.1 OSRM만으로 테스트 (API 키 없이)

```bash
python examples/traffic_matrix_example.py
```

**예상 출력**:
```
==================================================
예시 1: OSRM 매트릭스 (실시간 교통 없음)
==================================================

지점 수: 4
빌드 시간: 45ms
제공자: OSRMProvider

시간 매트릭스 (초):
  0: [0, 1200, 600, 900]
  1: [1200, 0, 800, 1500]
  ...
```

#### 8.4.2 TMap 실시간 교통 테스트

```bash
export TMAP_API_KEY=your_api_key
python << 'EOF'
import asyncio
from src.preprocessing.matrix_builder import create_matrix_builder, TrafficProvider
import os

async def test():
    builder = create_matrix_builder(
        provider=TrafficProvider.TMAP,
        api_key=os.getenv("TMAP_API_KEY"),
        osrm_url="http://localhost:5000"
    )

    vrp_input = {
        "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
        "jobs": [{"id": 1, "location": [127.0276, 37.4979]}]  # 서울시청→강남역
    }

    result = await builder.build(vrp_input)

    print(f"실시간 소요시간: {result.durations[0][1]}초")
    print(f"({result.durations[0][1]//60}분)")

asyncio.run(test())
EOF
```

**예상 출력** (교통 상황에 따라 다름):
```
실시간 소요시간: 2340초
(39분)
```

#### 8.4.3 OSRM vs TMap 비교

```bash
python << 'EOF'
import asyncio
from src.preprocessing.matrix_builder import create_matrix_builder, TrafficProvider
import os

async def compare():
    vrp = {
        "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
        "jobs": [{"id": 1, "location": [127.0276, 37.4979]}]
    }

    # OSRM (정적)
    osrm = create_matrix_builder(provider=TrafficProvider.OSRM)
    osrm_result = await osrm.build(vrp.copy())
    osrm_time = osrm_result.durations[0][1]

    # TMap (실시간)
    tmap = create_matrix_builder(
        provider=TrafficProvider.TMAP,
        api_key=os.getenv("TMAP_API_KEY")
    )
    tmap_result = await tmap.build(vrp.copy())
    tmap_time = tmap_result.durations[0][1]

    print(f"OSRM (정적): {osrm_time//60}분")
    print(f"TMap (실시간): {tmap_time//60}분")
    print(f"차이: {(tmap_time - osrm_time)//60:+d}분")

asyncio.run(compare())
EOF
```

### 8.5 PreProcessor에서 사용

```python
from src.preprocessing.preprocessor import PreProcessor
from src.preprocessing.matrix_builder import TrafficProvider

# 실시간 교통 활성화
preprocessor = PreProcessor(
    enable_validation=True,
    enable_normalization=True,
    enable_business_rules=True,
    enable_traffic_matrix=True,          # 활성화
    traffic_provider=TrafficProvider.TMAP,
    traffic_api_key="your_tmap_key",
    osrm_url="http://localhost:5000"
)

# 전처리 실행 (Phase 1 + 1.5)
result = await preprocessor.process(vrp_input)

# 결과에 매트릭스 포함됨
print("matrix" in result)  # True
```

### 8.6 비용 고려

**API 호출 수**: N개 지점 = N × N 조합

| 지점 수 | API 호출 | 월간 (1일 100회 요청) |
|--------|---------|---------------------|
| 5 | 25 | 75,000 |
| 10 | 100 | 300,000 |
| 20 | 400 | 1,200,000 |
| 50 | 2,500 | 7,500,000 |

**비용 절감 전략**:

1. **캐싱**: 동일 구간 5분 캐싱 (기본 설정)
   ```bash
   MATRIX_CACHE_TTL=300  # 5분
   ```

2. **병렬 제한**: API Rate Limit 고려
   ```bash
   MATRIX_PARALLEL_REQUESTS=5  # 동시 5개
   ```

3. **선택적 활성화**: 피크 시간대만 실시간 교통 사용
   ```python
   from datetime import datetime

   is_peak = 7 <= datetime.now().hour <= 9 or 17 <= datetime.now().hour <= 19
   preprocessor.enable_traffic_matrix = is_peak
   ```

### 8.7 문제 해결

**증상: TMap API 인증 실패**
```
httpx.HTTPStatusError: 401 Unauthorized
```
**해결**:
```bash
# API 키 확인
echo $TMAP_API_KEY

# 올바른 키인지 직접 테스트
curl -X POST "https://apis.openapi.sk.com/tmap/routes" \
  -H "appKey: $TMAP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"startX":"126.9780","startY":"37.5665","endX":"127.0276","endY":"37.4979"}'
```

**증상: API 호출이 너무 느림**
**해결**:
```bash
# 병렬 요청 수 증가 (Rate Limit 주의)
MATRIX_PARALLEL_REQUESTS=20

# 또는 캐시 TTL 증가
MATRIX_CACHE_TTL=600  # 10분
```

**증상: OSRM 거리와 TMap 거리가 다름**
```
use_osrm_distance=True 설정 시 거리는 OSRM, 시간은 TMap 사용
둘 다 TMap 사용하려면: use_osrm_distance=False
```

**✅ 체크포인트**:
- API 키 발급 완료
- 환경 변수 설정
- OSRM 테스트 성공
- 외부 API 테스트 성공 (키 있는 경우)
- OSRM vs 실시간 비교 확인

---

## 9. 프로덕션 설정

### 8.1 API 서버 시작 (수동)

```bash
cd src
python main.py
```

**예상 출력**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 8.2 API 테스트 (다른 터미널)

**Health Check**:
```bash
curl http://localhost:8000/health
# 출력: {"status":"healthy","version":"2.0","vroom_connected":true}
```

**인증 없이 요청 (실패해야 함)**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"vehicles":[],"jobs":[]}'

# 출력: {"detail":"API Key required"}
```

**올바른 인증으로 요청**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
    "jobs": [{"id": 1, "location": [127.0276, 37.4979]}]
  }'

# 출력: {"code":0, "routes":[...], "analysis":{...}, "statistics":{...}}
```

**Rate Limit 테스트**:
```bash
# 100번 연속 요청 (설정값 초과)
for i in {1..101}; do
  curl -X POST http://localhost:8000/optimize \
    -H "X-API-Key: demo-key-12345" \
    -H "Content-Type: application/json" \
    -d '{"vehicles":[{"id":1,"start":[126.9,37.5]}],"jobs":[]}' \
    -s -o /dev/null -w "Request $i: %{http_code}\n"
done

# 마지막 요청이 429 (Too Many Requests)를 반환해야 함
```

### 8.3 systemd 서비스 설정 (자동 시작)

**서비스 파일 생성**:
```bash
sudo nano /etc/systemd/system/vroom-wrapper.service
```

**내용**:
```ini
[Unit]
Description=VROOM Wrapper v2.0
After=network.target redis.service docker.service

[Service]
Type=simple
User=shawn
WorkingDirectory=/home/shawn/vroom-wrapper-project
Environment="PATH=/home/shawn/vroom-wrapper-project/venv/bin"
ExecStart=/home/shawn/vroom-wrapper-project/venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**활성화**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vroom-wrapper
sudo systemctl start vroom-wrapper

# 상태 확인
sudo systemctl status vroom-wrapper

# 로그 확인
sudo journalctl -u vroom-wrapper -f
```

**✅ 체크포인트**:
- API 서버가 8000 포트에서 응답
- 인증이 올바르게 동작
- Rate Limiting이 동작
- systemd 서비스로 자동 시작됨

---

## 10. 모니터링 및 로그

### 8.1 로그 디렉토리 설정

```bash
mkdir -p /home/shawn/vroom-wrapper-project/logs
chmod 755 logs
```

### 8.2 로그 설정 추가 (src/main.py)

```python
import logging
from logging.handlers import RotatingFileHandler

# 로그 설정
log_handler = RotatingFileHandler(
    '/home/shawn/vroom-wrapper-project/logs/wrapper.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger("vroom-wrapper")
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)
```

### 8.3 로그 모니터링

```bash
# 실시간 로그
tail -f logs/wrapper.log

# 에러만 필터링
grep ERROR logs/wrapper.log

# 특정 API Key 요청만 보기
grep "demo-key-12345" logs/wrapper.log

# 최근 100줄
tail -n 100 logs/wrapper.log
```

### 8.4 성능 모니터링

**간단한 모니터링 스크립트**:
```bash
cat > monitor.sh << 'EOF'
#!/bin/bash

echo "=== VROOM Wrapper 모니터링 ==="
echo ""

# 서버 상태
echo "1. 서버 프로세스:"
ps aux | grep "[p]ython.*main.py"
echo ""

# 포트 리스닝
echo "2. 포트 상태:"
netstat -tlnp 2>/dev/null | grep -E "(3000|5000|6379|8000)" || ss -tlnp | grep -E "(3000|5000|6379|8000)"
echo ""

# 메모리 사용
echo "3. 메모리 사용:"
ps aux | grep "[p]ython.*main.py" | awk '{print "  CPU: "$3"%, MEM: "$4"%, RSS: "$6/1024"MB"}'
echo ""

# API 응답 테스트
echo "4. API Health Check:"
curl -s http://localhost:8000/health | python -m json.tool
echo ""

# 최근 에러 로그
echo "5. 최근 에러 (최근 10줄):"
tail -n 10 logs/wrapper.log | grep ERROR || echo "  에러 없음"
echo ""

# Redis 상태 (사용 시)
echo "6. Redis 상태:"
redis-cli info stats 2>/dev/null | grep -E "(total_commands_processed|used_memory_human)" || echo "  Redis 미사용 또는 연결 안됨"
EOF

chmod +x monitor.sh
./monitor.sh
```

**Cron으로 정기 모니터링**:
```bash
# 5분마다 모니터링 로그 저장
crontab -e
# 추가:
*/5 * * * * /home/shawn/vroom-wrapper-project/monitor.sh >> /home/shawn/vroom-wrapper-project/logs/monitor.log 2>&1
```

**✅ 체크포인트**:
- 로그 파일이 생성되고 기록됨
- 모니터링 스크립트가 동작
- 서버 상태를 실시간으로 확인 가능

---

## 11. 문제 해결

### 10.1 VROOM 서버 연결 실패

**증상**:
```
httpx.ConnectError: [Errno 111] Connection refused
```

**원인 및 해결**:
```bash
# 1. VROOM 서버가 실행 중인가?
docker ps | grep vroom
# 없다면: docker start vroom-server

# 2. 포트가 올바른가?
curl http://localhost:3000/health
# 실패 시: docker logs vroom-server

# 3. 방화벽 확인
sudo ufw status
sudo ufw allow 3000/tcp

# 4. 네트워크 확인
docker inspect vroom-server | grep IPAddress
# Wrapper에서 접근 가능한지 확인
```

### 10.2 Redis 연결 실패

**증상**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**해결**:
```bash
# 1. Redis 서비스 확인
redis-cli ping
# 실패 시: sudo systemctl start redis-server

# 2. Redis 사용 안함으로 전환 (메모리 캐싱)
# .env 파일에서:
# REDIS_URL=redis://localhost:6379  <- 이 줄을 주석 처리
# 또는 삭제

# 3. Wrapper 재시작
sudo systemctl restart vroom-wrapper
```

### 10.3 API Key 인증 실패

**증상**:
```
{"detail":"Invalid API Key"}
```

**해결**:
```bash
# 1. 사용 중인 API Key 확인
python -c "from src.config import API_KEYS; print(list(API_KEYS.keys()))"

# 2. 새 API Key 추가
nano src/config.py
# API_KEYS에 추가:
#   "my-new-key": {
#       "name": "My Client",
#       "rate_limit": "100/hour",
#       "features": ["basic", "standard", "premium"]
#   }

# 3. 서버 재시작
sudo systemctl restart vroom-wrapper

# 4. 테스트
curl -H "X-API-Key: my-new-key" http://localhost:8000/health
```

### 10.4 Rate Limit 초과

**증상**:
```
{"detail":"Rate limit exceeded"}
```

**해결**:
```bash
# 1. 임시로 Rate Limit 비활성화
# .env 파일:
RATE_LIMIT_ENABLED=false

# 2. 또는 제한 완화
# .env 파일:
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# 3. 특정 API Key의 제한 변경
nano src/config.py
# "rate_limit": "1000/hour"  <- 변경

# 4. 재시작
sudo systemctl restart vroom-wrapper
```

### 10.5 최적화 결과가 이상함

**증상**: 미배정이 너무 많거나 경로가 비효율적

**해결**:
```bash
# 1. 입력 데이터 검증
python << 'EOF'
from src.preprocessing.validator import InputValidator

validator = InputValidator()
result = validator.validate({
    "vehicles": [...],
    "jobs": [...]
})
print(result.errors)  # 검증 에러 확인
EOF

# 2. 제어 레벨 변경
curl -X POST http://localhost:8000/optimize/premium \
  -H "X-API-Key: demo-key-12345" \
  -d @your_request.json

# 3. 제약 조건 확인
# 시간창이 너무 타이트한가?
# 차량 용량이 충분한가?
# 스킬 제약이 너무 엄격한가?

# 4. 디버그 모드로 실행
LOG_LEVEL=DEBUG python src/main.py
# 로그에서 자세한 정보 확인
```

### 10.6 메모리 부족

**증상**:
```
MemoryError: Unable to allocate...
```

**해결**:
```bash
# 1. 현재 메모리 사용 확인
free -h
ps aux | grep python | awk '{sum+=$6} END {print sum/1024 "MB"}'

# 2. 캐시 크기 제한 (메모리 캐싱 사용 시)
# src/extensions/cache_manager.py 수정:
MAX_CACHE_SIZE = 1000  # 최대 캐시 항목 수

# 3. Redis 사용으로 전환 (메모리 외부화)
REDIS_URL=redis://localhost:6379

# 4. Worker 수 제한
uvicorn src.main:app --workers 2 --host 0.0.0.0 --port 8000

# 5. 시스템 swap 확인
sudo swapon --show
```

### 10.7 성능이 느림

**해결**:
```bash
# 1. 캐싱 활성화
REDIS_URL=redis://localhost:6379

# 2. 요청에 캐시 사용 명시
curl -X POST http://localhost:8000/optimize \
  -H "X-API-Key: demo-key-12345" \
  -d '{"vehicles":[...],"jobs":[...],"use_cache":true}'

# 3. VROOM 타임아웃 늘리기
# src/control/optimization_controller.py:
timeout = 60  # 기본 30초

# 4. 병렬 처리 (PREMIUM 레벨)
curl -X POST http://localhost:8000/optimize/premium \
  -H "X-API-Key: demo-key-12345" \
  -d '{"vehicles":[...],"jobs":[...],"num_scenarios":3}'

# 5. OSRM 최적화
docker stop osrm-server
docker rm osrm-server
# 더 빠른 알고리즘으로 재시작 (MLD 대신 CH)
docker run -d --name osrm-server -p 5000:5000 \
  -v "${PWD}/osrm-data:/data" \
  ghcr.io/project-osrm/osrm-backend \
  osrm-routed --algorithm ch /data/south-korea-latest.osrm
```

---

## 11. 체크리스트

시스템을 완전히 제어하고 있는지 확인하세요:

### 기본 설정
- [ ] Python 3.8+ 설치 및 가상환경 생성
- [ ] 모든 의존성 설치 및 버전 확인
- [ ] OSRM 서버 실행 및 health check 통과
- [ ] VROOM 서버 실행 및 테스트 요청 성공

### 선택 사항
- [ ] Redis 설치 및 연결 테스트 (또는 메모리 캐싱 사용)

### Wrapper 설정
- [ ] `.env` 파일 생성 및 환경 변수 설정
- [ ] `src/config.py` 생성 및 API Key 설정
- [ ] Phase 1 단독 테스트 성공
- [ ] VROOM 연동 테스트 성공
- [ ] 전체 파이프라인 테스트 성공 (demo_v2.py)

### 프로덕션 배포
- [ ] API 서버 수동 시작 성공
- [ ] Health check API 응답 확인
- [ ] 인증 동작 확인 (401/403 에러)
- [ ] Rate Limiting 동작 확인 (429 에러)
- [ ] systemd 서비스 등록 및 자동 시작

### 모니터링
- [ ] 로그 디렉토리 생성 및 권한 설정
- [ ] 로그 파일 기록 확인
- [ ] 모니터링 스크립트 작성 및 테스트
- [ ] 실시간 로그 확인 가능

### 제어 능력
- [ ] API Key 추가/제거 방법 이해
- [ ] Rate Limit 조정 방법 이해
- [ ] 캐싱 on/off 전환 방법 이해
- [ ] 제어 레벨 (BASIC/STANDARD/PREMIUM) 이해
- [ ] 문제 발생 시 디버깅 방법 이해

---

## 12. 다음 단계

모든 체크리스트를 완료했다면, 이제 시스템을 완전히 제어하고 있습니다!

### 실전 사용
1. **실제 데이터 투입**:
   - `samples/sample_request.json`을 기반으로 실제 데이터 작성
   - `/optimize/standard` 엔드포인트로 테스트

2. **성능 튜닝**:
   - 캐싱 효과 측정 (히트율 확인)
   - 타임아웃 조정
   - Worker 수 조정

3. **모니터링 강화**:
   - Prometheus + Grafana 연동 (선택)
   - Alert 설정 (서버 다운, 응답 시간 초과)

4. **보안 강화**:
   - HTTPS 설정 (nginx + Let's Encrypt)
   - API Key를 환경 변수나 Secrets Manager로 이동
   - CORS 설정 조정

5. **스케일링**:
   - 여러 Wrapper 인스턴스 실행 (로드밸런서)
   - Redis Cluster 구성
   - VROOM 서버 다중화

---

## 📞 지원

문제가 발생하면:
1. 해당 섹션의 "문제 해결" 참조
2. 로그 파일 확인: `tail -f logs/wrapper.log`
3. 각 컴포넌트 개별 테스트
4. GitHub Issues 등록

**이제 당신은 VROOM Wrapper v2.0을 완전히 제어할 수 있습니다!** 🎯

# VROOM 소스코드 사용 가이드

## 🔍 현재 상태 분석

### Docker 이미지 사용 현황

| docker-compose 파일 | VROOM 이미지 | 소스코드 연결 |
|---------------------|-------------|--------------|
| `docker-compose.unified.yml` ✅ | `vroomvrp/vroom-docker:latest` | ❌ **Docker Hub 공식 이미지** |
| `docker-compose-v2-full.yml` | `vroomvrp/vroom-docker:latest` | ❌ **Docker Hub 공식 이미지** |
| `docker-compose.yml` | `vroom-local:latest` | ⚠️ 로컬 빌드 필요 |
| `docker-compose-secure.yml` | `vroom-local:latest` | ⚠️ 로컬 빌드 필요 |

**결론: 현재 운영 환경(`unified`)은 로컬 소스코드(`/home/shawn/vroom/`)를 사용하지 않습니다.**

---

## 📦 세 가지 VROOM 버전

### 1. `/home/shawn/vroom/` (Core Engine Only)
```
vroom/
├── src/                          # C++ 소스코드
│   ├── algorithms/              # 메타휴리스틱
│   ├── problems/vrptw/          # VRPTW 문제
│   │   └── operators/           # 🎯 최적화 오퍼레이터
│   └── structures/              # 데이터 구조
├── Dockerfile                   # CLI만 빌드
└── bin/vroom                    # 빌드 결과 (CLI)
```
- **용도**: VROOM 엔진만 (CLI 실행파일)
- **API 서버 없음** - HTTP 요청 불가

### 2. `/home/shawn/vroom-docker/` (Full Stack)
```
vroom-docker/
├── Dockerfile                   # 🎯 Full Stack
│   ├── vroom (GitHub clone)     # 엔진
│   └── vroom-express (GitHub)   # Node.js API 서버
└── docker-entrypoint.sh
```
- **용도**: VROOM + vroom-express API 서버
- HTTP API 지원 (`POST /`)
- Docker Hub 이미지의 기반

### 3. Docker Hub `vroomvrp/vroom-docker:latest`
- **공식 빌드**: GitHub Actions로 자동 빌드
- **현재 사용 중**: `docker-compose.unified.yml`에서 사용
- `/home/shawn/vroom/` 소스코드와 **무관**

---

## 🔬 연구 vs 적용

### 시나리오 A: 알고리즘 연구 (현재 가능)
```bash
# 소스코드 분석
cd /home/shawn/vroom/src/problems/vrptw/operators
vim cross_exchange.cpp

# 로컬 빌드 테스트
cd /home/shawn/vroom
make
./bin/vroom --input test.json
```
✅ **영향 없음**: 운영 환경(Docker)에는 영향 없음
✅ **안전함**: 로컬에서만 테스트

### 시나리오 B: 수정된 알고리즘 적용 (설정 필요)

#### Step 1: 로컬 소스 수정
```bash
cd /home/shawn/vroom/src/problems/vrptw/operators
# cross_exchange.cpp 수정
# 예: 오퍼레이터 가중치, 제약조건 등
```

#### Step 2: Docker 이미지 빌드
```bash
cd /home/shawn/vroom
docker build -t vroom-custom:v1.0 .
```
⚠️ **문제**: 이 이미지는 **CLI만** 있고 API 서버가 없음

#### Step 3: vroom-express 포함 이미지 빌드 (권장)
```bash
cd /home/shawn/vroom-docker

# Dockerfile 수정: GitHub clone → 로컬 소스 사용
# 기존: RUN git clone https://github.com/VROOM-Project/vroom.git
# 변경: COPY /home/shawn/vroom /vroom

docker build -t vroom-custom-full:v1.0 .
```

#### Step 4: docker-compose 수정
```yaml
# docker-compose.unified.yml
services:
  vroom:
    # image: vroomvrp/vroom-docker:latest  # 기존
    image: vroom-custom-full:v1.0          # 변경
    container_name: vroom-engine
    # ... 나머지 동일
```

#### Step 5: 재배포
```bash
cd /home/shawn/vroom-wrapper-project
docker-compose -f docker-compose.unified.yml down
docker-compose -f docker-compose.unified.yml up -d
```

---

## 🎯 추천 워크플로우

### 개발 단계
```
1. /home/shawn/vroom/ 소스 수정
2. 로컬 make 빌드로 검증
3. CLI로 테스트 케이스 실행
4. 결과 확인 ✅
```

### 적용 단계
```
5. vroom-docker/Dockerfile 수정 (로컬 소스 사용)
6. docker build -t vroom-custom-full:v1.0 .
7. docker-compose.unified.yml 이미지 변경
8. docker-compose up -d
9. API 테스트
10. 프로덕션 배포
```

---

## 📋 Quick Commands

### 로컬 빌드 (연구용)
```bash
cd ~/vroom
make clean && make -j$(nproc)
./bin/vroom --input ~/vroom-wrapper-project/examples/test.json
```

### Docker 이미지 빌드 (적용용)
```bash
# 옵션 1: vroom만 (CLI)
cd ~/vroom
docker build -t vroom-custom:v1.0 .

# 옵션 2: vroom + API (권장)
cd ~/vroom-docker
# Dockerfile 수정 필요 (아래 참조)
docker build -t vroom-custom-full:v1.0 .
```

### vroom-docker/Dockerfile 수정
```dockerfile
# 기존 (GitHub에서 clone)
RUN git clone --branch $VROOM_RELEASE --single-branch --recurse-submodules \
    https://github.com/VROOM-Project/vroom.git

# 변경 (로컬 소스 사용)
COPY /home/shawn/vroom /vroom
```

---

## 🚨 주의사항

### 현재 상태
- ✅ `/home/shawn/vroom/` 존재 - 연구/학습용
- ❌ 운영 환경 미연결 - Docker Hub 이미지 사용 중
- ⚠️ 수정사항 적용 위해서는 **추가 설정 필요**

### 수정 적용시
1. **테스트 필수**: 로컬에서 먼저 검증
2. **버전 관리**: 이미지 태그로 버전 구분 (`v1.0`, `v1.1` 등)
3. **롤백 준비**: 기존 이미지 보관
4. **문서화**: 수정 내용과 이유 기록

---

## 🔗 다음 단계

### 지금 당장 (연구만)
- 현재 구조 유지 - 문제 없음
- `/home/shawn/vroom/` 소스 자유롭게 분석
- 로컬 빌드로 실험

### 수정 적용 시
1. `vroom-docker/Dockerfile` 수정 가이드 필요하면 요청
2. 빌드 & 테스트 자동화 스크립트 제공 가능
3. CI/CD 파이프라인 구축 가능

**현재는 연구 목적이므로 추가 작업 불필요. 적용 단계에서 다시 논의.**

# VROOM Wrapper v3.1 - Synthesis Edition

VROOM 배차 최적화 엔진의 Python Wrapper 플랫폼.
VROOM 바이너리 직접 호출, 미배정 사유 분석, 비즈니스 규칙, 제약 완화 자동 재시도, 다중 시나리오 비교를 제공합니다.

## 핵심 기능

- **VROOM 바이너리 직접 호출** - vroom-express 제거, subprocess stdin/stdout 파이프
- **미배정 사유 분석** - skills/capacity/time_window/max_tasks/complex_constraint 역추적
- **비즈니스 규칙** - VIP 우선처리, 긴급 배차, 지역 제약 자동 적용
- **제약 완화 자동 재시도** - 미배정 발생 시 6단계 완화 전략
- **다중 시나리오 비교** - BASIC/STANDARD/PREMIUM 병렬 실행 후 최적 선택
- **2-Pass 최적화** - 초기 배정 + 경로별 병렬 최적화 (Roouty Engine 패턴)
- **도달 불가능 필터링** - 매트릭스 기반 사전 필터링
- **대규모 매트릭스 청킹** - OSRM 병렬 분할 처리
- **실시간 교통** - TMap/Kakao/Naver API 연동
- **운영 기능** - API Key 인증, Rate Limiting, Redis 캐싱

## 시스템 구성

```
Docker Compose (7 컨테이너)
  OSRM (:5000)            ─┐
  Valhalla (:8002)         ─┤── Wrapper (:8000)  FastAPI + VROOM 바이너리
  Redis (:6379)            ─┤── Celery Worker 1  비동기 dispatch (concurrency=3)
                            ├── Celery Worker 2  비동기 dispatch (concurrency=3)
                            └── Flower (:5555)   Celery 모니터링 웹 UI
```

- **Valhalla** — 한국 전체 데이터(south-korea-latest.osm.pbf), time-dependent routing 지원
- **Celery Workers** — Redis 큐 기반, 동시 최대 6건 비동기 dispatch 처리

## Quick Start

```bash
# 빌드 & 실행
docker-compose -f docker-compose.v3.yml up -d --build

# 상태 확인
curl http://localhost:8000/health

# 최적화 요청
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [{"id": 1, "start": [126.978, 37.566], "capacity": [20], "skills": [1]}],
    "jobs": [
      {"id": 1, "location": [127.0, 37.55], "delivery": [5], "skills": [1]},
      {"id": 2, "location": [127.01, 37.54], "delivery": [3], "skills": [3]}
    ]
  }'
```

## API 엔드포인트

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | `/distribute` | VROOM 호환 배차 | - |
| POST | `/optimize` | STANDARD 최적화 | API Key |
| POST | `/optimize/basic` | BASIC 최적화 (빠른 결과) | API Key |
| POST | `/optimize/premium` | PREMIUM 최적화 (다중 시나리오) | API Key |
| POST | `/dispatch` | HGLIS 가전 배송 배차 | API Key |
| GET | `/jobs/{job_id}` | 비동기 배차 작업 진행률/결과 조회 | - |
| POST | `/matrix/build` | OSRM 매트릭스 생성 | API Key |
| POST | `/map-matching/match` | GPS 궤적 맵 매칭 | API Key |
| GET | `/map-matching/health` | OSRM 맵 매칭 연결 확인 | - |
| POST | `/map-matching/validate` | GPS 궤적 유효성 검증 | API Key |
| POST | `/valhalla/distribute` | Valhalla 배차 (인증 불필요) | - |
| POST | `/valhalla/optimize` | Valhalla STANDARD 최적화 | API Key |
| POST | `/valhalla/optimize/basic` | Valhalla BASIC 최적화 | API Key |
| POST | `/valhalla/optimize/premium` | Valhalla PREMIUM 최적화 | API Key |
| DELETE | `/cache/clear` | 캐시 삭제 | API Key |
| GET | `/health` | 헬스 체크 | - |

## 프로젝트 구조

```
src/
  main_v3.py              # FastAPI 메인 앱
  config.py               # 환경 변수 설정
  api/                     # 라우터 (distribute, optimize, dispatch, jobs, valhalla, map_matching 등)
  core/                    # 인증, 의존성 주입
  preprocessing/           # 검증, 정규화, 비즈니스 규칙, 교통 매트릭스
  control/                 # VROOM 설정, 제약 완화, 다중 시나리오
  optimization/            # VROOM 직접 호출, 2-Pass 최적화
  postprocessing/          # 미배정 분석, 품질 점수, 통계
  hglis/                   # HGLIS 배차 (스킬 인코딩, 권역 분할, 요금 검증)
  map_matching/            # GPS 궤적 맵 매칭 엔진
  services/                # 비동기 Job 관리
  extensions/              # Redis/메모리 캐싱
```

## 문서

| 문서 | 언제 읽는가 |
|------|-----------|
| [docs/WRAPPER-QUICK-GUIDE.md](docs/WRAPPER-QUICK-GUIDE.md) | 처음 코드베이스 파악 — 전체 그림을 빠르게 |
| [docs/API-DOCUMENTATION.md](docs/API-DOCUMENTATION.md) | API 연동 개발, 요청/응답 형식, 환경변수 확인 |
| [docs/TECHNICAL-ARCHITECTURE.md](docs/TECHNICAL-ARCHITECTURE.md) | 특정 로직 수정/디버깅, 파이프라인 상세 이해 |
| [docs/HGLIS_배차엔진_통합명세서_v8.3.md](docs/HGLIS_배차엔진_통합명세서_v8.3.md) | /dispatch 개발, 시뮬레이터 팀과 제약 협의 |
| [docs/V3-GUIDE.md](docs/V3-GUIDE.md) | 서버 세팅, Docker 설치/가동 |
| [docs/PRD.md](docs/PRD.md) | 기능 범위 확인, 설계 의도 파악 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 변경 이력, Breaking change 확인 |
| [docs/archive/](docs/archive/) | 구버전 문서 (v1/v2, 참고용) |

## 사전 요구사항

- Docker 24+ & Docker Compose
- OSRM 한국 지도 데이터 (전처리 완료)
- VROOM Docker 이미지 (`vroom-local:latest`)

## 기술 스택

- **VROOM** v1.14+ (C++ 바이너리, 직접 호출)
- **OSRM** (OpenStreetMap 라우팅)
- **Valhalla** v3.5+ (time-dependent routing, 한국 전체 데이터)
- **FastAPI** + **uvicorn** (Python 웹 프레임워크)
- **Celery** 5.3+ (비동기 태스크 큐, 워커 2개)
- **Flower** 2.0+ (Celery 모니터링 웹 UI)
- **Redis** 7+ (캐시 + Celery broker/backend)
- **Docker** (멀티스테이지 빌드)

## 라이센스

MIT License

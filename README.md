# VROOM Wrapper v3.0 - Synthesis Edition

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
Docker Compose (3 컨테이너)
  OSRM (:5000)  ─┐
  Redis (:6379)  ─┤── Wrapper (:8000)
                  │   FastAPI + VROOM 바이너리
                  └── (vroom-express 제거!)
```

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
| POST | `/optimize` | STANDARD 최적화 | API Key |
| POST | `/optimize/basic` | BASIC 최적화 (빠른 결과) | API Key |
| POST | `/optimize/premium` | PREMIUM 최적화 (다중 시나리오) | API Key |
| POST | `/matrix/build` | OSRM 매트릭스 생성 | API Key |
| DELETE | `/cache/clear` | 캐시 삭제 | API Key |
| GET | `/health` | 헬스 체크 | - |

## 프로젝트 구조

```
src/
  main_v3.py              # FastAPI 메인 앱
  config.py               # 환경 변수 설정
  preprocessing/           # 검증, 정규화, 비즈니스 규칙, 교통 매트릭스
  control/                 # VROOM 설정, 제약 완화, 다중 시나리오
  optimization/            # VROOM 직접 호출, 2-Pass 최적화
  postprocessing/          # 미배정 분석, 품질 점수, 통계
  extensions/              # Redis/메모리 캐싱
```

## 문서

| 문서 | 내용 |
|------|------|
| [PRD.md](PRD.md) | 제품 요구사항 정의서 |
| [V3-GUIDE.md](V3-GUIDE.md) | 설치/가동 가이드 |
| [CHANGELOG.md](CHANGELOG.md) | 버전별 변경 이력 |
| [DOCUMENT-INDEX.md](DOCUMENT-INDEX.md) | 전체 문서 인덱스 |

## 사전 요구사항

- Docker 24+ & Docker Compose
- OSRM 한국 지도 데이터 (전처리 완료)
- VROOM Docker 이미지 (`vroom-local:latest`)

## 기술 스택

- **VROOM** v1.14+ (C++ 바이너리, 직접 호출)
- **OSRM** (OpenStreetMap 라우팅)
- **FastAPI** + **uvicorn** (Python 웹 프레임워크)
- **Redis** 7+ (캐싱, 선택)
- **Docker** (멀티스테이지 빌드)

## 라이센스

MIT License

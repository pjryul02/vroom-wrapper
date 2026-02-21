# Changelog

이 프로젝트의 모든 주요 변경사항을 기록합니다.

---

## [v3.0.0] - 2026-02-13 (정반합 Synthesis Edition)

Roouty Engine(Go) 성능 패턴 + Python Wrapper v2.0 기능의 통합.

### 아키텍처 변경
- **vroom-express(Node.js) 제거** - Docker 컨테이너 4개 → 3개
- **VROOM 바이너리 직접 호출** - subprocess stdin/stdout 파이프 (`vroom_executor.py`)
- **멀티스테이지 Docker 빌드** - vroom-local + python:3.11-slim (`Dockerfile.v3`)

### 신규 기능
- **2-Pass 최적화** - 초기 배정 + 경로별 병렬 최적화 (`two_pass.py`)
- **도달 불가능 필터링** - 매트릭스 기반 사전 필터링 (`unreachable_filter.py`)
- **OSRM 매트릭스 청킹** - 대규모 병렬 분할 처리 (`chunked_matrix.py`)
- **`/matrix/build` 엔드포인트** - 독립 매트릭스 생성 API
- **config.py** - 전체 설정 환경변수 기반 관리

### v2.0 기능 계승 (전부 유지)
- 입력 전처리 (검증/정규화/비즈니스 규칙)
- 3단계 제어 레벨 (BASIC/STANDARD/PREMIUM)
- 제약 완화 자동 재시도 (6단계 완화 전략)
- 다중 시나리오 비교 최적화
- 미배정 사유 분석 (ConstraintChecker)
- 품질 분석 + 통계 생성
- API Key 인증 + Rate Limiting
- Redis 캐싱 (메모리 폴백)

### 코드 통계
- 총 소스 코드: 6,243줄 / 27개 Python 파일
- 모듈: preprocessing(2,395줄), control(1,258줄), optimization(601줄), postprocessing(592줄), extensions(101줄)

---

## [v2.1.0] - 2026-02-03

### 추가
- **실시간 교통 매트릭스** - TMap, Kakao, Naver API 연동 (`matrix_builder.py`)
- `MANUAL-SETUP-GUIDE.md` 수동 설치 가이드
- `config.py` 설정 파일 도입
- `.env.example` 환경 변수 템플릿

---

## [v2.0.0] - 2026-01-28

5-Phase 모듈형 아키텍처로 전면 재설계.

### Phase 1: 전처리 계층
- `validator.py` - Pydantic 기반 입력 검증
- `normalizer.py` - 기본값 설정, 좌표/시간 정규화
- `business_rules.py` - VIP/긴급/지역 비즈니스 규칙

### Phase 2: 제어 계층
- `vroom_config.py` - BASIC/STANDARD/PREMIUM/CUSTOM 제어 레벨
- `constraint_tuner.py` - 6단계 제약 완화 전략
- `multi_scenario.py` - 다중 시나리오 병렬 실행
- `controller.py` - 최적화 오케스트레이션

### Phase 3: 후처리 계층
- `analyzer.py` - 품질 점수 (0-100), 개선 제안
- `statistics.py` - 차량/비용/시간/효율 통계

### Phase 4: 확장 계층
- `cache_manager.py` - Redis + 메모리 폴백 캐싱

### Phase 5: 통합
- `main.py` - FastAPI 앱 (인증, Rate Limiting, 캐싱 통합)
- Docker Compose 구성 (4 컨테이너)

---

## [v1.0.0] - 2026-01-23

### 최초 릴리스
- `vroom_wrapper.py` - 단일 파일 VROOM 래퍼
- **미배정 사유 분석** - skills/capacity/time_window/max_tasks/complex_constraint
- Docker Compose (OSRM + VROOM + Wrapper)
- VROOM 기술 문서 (`docs/`)

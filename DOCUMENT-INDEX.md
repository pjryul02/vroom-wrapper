# 문서 인덱스

현재 버전: **v3.1** (2026-03-02)

---

## 핵심 문서 (최신)

| 문서 | 목적 | 우선순위 |
|------|------|---------|
| [README.md](README.md) | 프로젝트 개요 + Quick Start | 필수 |
| [PRD.md](PRD.md) | 제품 요구사항 정의서 (기능/비기능/데이터흐름) | 필수 |
| [V3-GUIDE.md](V3-GUIDE.md) | 설치, 배포, 가동 가이드 | 필수 |
| [API-DOCUMENTATION.md](API-DOCUMENTATION.md) | API 엔드포인트 사용법 (13개) | 필수 |
| [docs/TECHNICAL-ARCHITECTURE.md](docs/TECHNICAL-ARCHITECTURE.md) | 기술 아키텍처, 파이프라인, 알고리즘 상세 | 필수 |
| [docs/DEVELOPMENT-REPORT.md](docs/DEVELOPMENT-REPORT.md) | PRD 충족 검증, 테스트 결과, 코드 통계 | 참고 |
| [CHANGELOG.md](CHANGELOG.md) | 버전별 변경 이력 (v1.0 ~ v3.1) | 참고 |
| [DOCUMENT-INDEX.md](DOCUMENT-INDEX.md) | 이 문서 (전체 문서 인덱스) | 참고 |
| [.env.example](.env.example) | 환경 변수 템플릿 | 설정 |

---

## 소스 코드 구조

상세 아키텍처: [docs/TECHNICAL-ARCHITECTURE.md](docs/TECHNICAL-ARCHITECTURE.md)

```
src/
├── main_v3.py                    # FastAPI 메인 앱
├── config.py                     # 환경 변수 설정 (30+)
├── api_models.py                 # Pydantic 요청 모델
│
├── api/                          # 엔드포인트 라우터 (13개)
│   ├── distribute.py             #   POST /distribute
│   ├── optimize.py               #   POST /optimize, /optimize/basic, /optimize/premium
│   ├── dispatch.py               #   POST /dispatch (HGLIS)
│   ├── jobs.py                   #   GET /jobs/{job_id} (비동기)
│   ├── matrix.py                 #   POST /matrix/build
│   ├── map_matching.py           #   POST /map-matching/match, /validate
│   └── health.py                 #   GET /, /health, DELETE /cache/clear
│
├── core/                         # 공통 인프라
│   ├── auth.py                   #   API Key 인증 + Rate Limiting
│   └── dependencies.py           #   싱글턴 컴포넌트 관리
│
├── preprocessing/                # Phase 1: 전처리
│   ├── preprocessor.py           #   통합 전처리 오케스트레이터
│   ├── validator.py              #   입력 검증
│   ├── normalizer.py             #   입력 정규화
│   ├── business_rules.py         #   비즈니스 규칙 (VIP/긴급/지역)
│   ├── unreachable_filter.py     #   도달불가 사전 필터링
│   ├── vroom_matrix_preparer.py  #   OSRM 매트릭스 사전계산
│   ├── chunked_matrix.py         #   OSRM 75×75 청킹
│   └── matrix_builder.py         #   실시간 교통 매트릭스
│
├── control/                      # Phase 2: 최적화 제어
│   ├── controller.py             #   OptimizationController
│   ├── vroom_executor.py         #   VROOM 바이너리 직접 호출
│   ├── vroom_config.py           #   BASIC/STANDARD/PREMIUM 설정
│   ├── constraint_tuner.py       #   제약 완화 6단계 자동 재시도
│   └── multi_scenario.py         #   다중 시나리오 병렬 실행
│
├── optimization/                 # 최적화 엔진
│   └── two_pass.py               #   2-Pass 최적화
│
├── postprocessing/               # Phase 3: 후처리
│   ├── constraint_checker.py     #   미배정 사유 역추적 분석
│   ├── analyzer.py               #   품질 분석 (0~100점)
│   └── statistics.py             #   통계 생성
│
├── hglis/                        # HGLIS 배차 전용
│   ├── models.py                 #   Pydantic 모델 (C1~C8 제약)
│   ├── dispatcher.py             #   HGLIS 배차 오케스트레이터
│   ├── skill_encoder.py          #   C4/C7/C8/소파 → VROOM skills
│   ├── vroom_assembler.py        #   HGLIS → VROOM JSON 변환
│   ├── fee_validator.py          #   C2 설치비 하한 검증
│   └── monthly_cap.py            #   C6 월상한 검증
│
├── map_matching/                 # GPS 궤적 도로 매칭
│   ├── engine.py                 #   OSRM 기반 Map Matcher
│   └── models.py                 #   맵 매칭 요청/응답 모델
│
├── services/                     # 공통 서비스
│   └── job_manager.py            #   비동기 작업 진행률 관리
│
└── extensions/                   # 확장 모듈
    └── cache_manager.py          #   Redis/인메모리 캐시
```

---

## 인프라 파일

| 파일 | 용도 |
|------|------|
| `Dockerfile.v3` | 멀티스테이지 빌드 (vroom-local → python:3.11-slim) |
| `docker-compose.v3.yml` | 3-서비스 구성 (OSRM + Redis + Wrapper) |
| `requirements-v3.txt` | Python 의존성 |

---

## HGLIS 명세

| 문서 | 내용 |
|------|------|
| `docs/HGLIS_배차엔진_통합명세서_v8.3.md` | HGLIS 원본 명세서 (C1~C8 제약 정의) |
| `docs/WRAPPER_PROCESSING_LOGIC_v1.md` | HGLIS 처리 로직 v1.0 (Step 1~6 상세) |

---

## 레거시 참고 자료 (docs/, v1.0~v2.0 기준)

VROOM 엔진 이해 및 역사적 참고용. **최신 내용은 `docs/TECHNICAL-ARCHITECTURE.md`에 통합됨.**

| 문서 | 내용 | 유니크 내용 |
|------|------|------------|
| `docs/VROOM-VIOLATIONS-GUIDE.md` | VROOM 10종 violation 타입 | Hard vs Soft 구분, Violations 3계층 |
| `docs/VROOM-CUSTOM-CONSTRAINTS-GUIDE.md` | VROOM C++ 커스텀 제약 추가 | 10-Step 절차, 수정 대상 파일 목록 |
| `docs/VROOM-CUSTOM-VIOLATION-REPORTING.md` | VROOM C++ violation 보고 추가 | ViolationDetail 구조체 설계 |
| `docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md` | 미배정 분석 3전략 비교 | 하이브리드 전략(디버그 로그+파싱) |
| `docs/VROOM-WRAPPER-COMPLETE-GUIDE.md` | v1.0 역추적 알고리즘 상세 | 필터 체이닝, 대규모 시나리오 |
| `docs/VROOM-API-CONTROL-GUIDE.md` | VROOM 설정 튜닝 | 동적 재최적화, 커스텀 비용함수 |
| `docs/README-VROOM-OSRM.md` | OSRM 연동 기초 | MLD vs CH 알고리즘 비교 |
| `docs/QUICK-START.md` | v1.0 빠른 시작 | (대체됨 → V3-GUIDE.md) |
| `docs/WRAPPER-SETUP.md` | v1.0 설치 가이드 | (대체됨 → V3-GUIDE.md) |

---

## 아카이브 (archive/)

이전 버전의 코드와 문서. 참고용으로만 사용.

| 디렉토리 | 내용 |
|----------|------|
| `archive/v1/` | v1.0 코드 (`vroom_wrapper.py`, `docker-compose.yml`, 테스트 스크립트) |
| `archive/v2/` | v2.0 코드 (`main.py`, `main_v2.py`), 구현 로드맵, 검증 보고서 |
| `archive/analysis/` | 기술 분석 문서 (VROOM 직접호출, Roouty 비교, vroom-express 분석) |

---

## 버전 히스토리

| 버전 | 날짜 | 핵심 변경 |
|------|------|----------|
| v1.0 | 2026-01-23 | 단일 파일 래퍼 + 미배정 사유 분석 |
| v2.0 | 2026-01-28 | 5-Phase 모듈형 아키텍처 |
| v2.1 | 2026-02-03 | 실시간 교통 매트릭스 (TMap/Kakao/Naver) |
| v3.0 | 2026-02-13 | Roouty Engine 패턴 통합 (정반합) |
| **v3.1** | **2026-03-02** | **2-Pass 활성화, OSRM 매트릭스 사전계산, HGLIS /dispatch, 비동기 모드, Swagger 보강** |

상세 변경 이력: [CHANGELOG.md](CHANGELOG.md)

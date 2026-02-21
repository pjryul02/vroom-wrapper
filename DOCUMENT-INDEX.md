# 문서 인덱스

현재 버전: **v3.0.0** (2026-02-13)

---

## 현재 문서 (v3.0)

| 문서 | 목적 | 우선순위 |
|------|------|---------|
| [README.md](README.md) | 프로젝트 개요 + Quick Start | 필수 |
| [PRD.md](PRD.md) | 제품 요구사항 정의서 (기능/비기능/데이터흐름) | 필수 |
| [V3-GUIDE.md](V3-GUIDE.md) | 설치, 배포, 가동 가이드 | 필수 |
| [CHANGELOG.md](CHANGELOG.md) | 버전별 변경 이력 (v1.0 ~ v3.0) | 참고 |
| [DOCUMENT-INDEX.md](DOCUMENT-INDEX.md) | 이 문서 (전체 문서 인덱스) | 참고 |
| [.env.example](.env.example) | 환경 변수 템플릿 (v3.0 전체 설정) | 설정 |

---

## 소스 코드 구조

```
src/                              # 6,243줄 / 27 파일
├── __init__.py                   # 패키지 선언
├── main_v3.py                    # FastAPI 메인 앱 (519줄)
├── config.py                     # 환경 변수 설정 (175줄)
│
├── preprocessing/                # 전처리 (2,395줄)
│   ├── validator.py              #   입력 검증 (Pydantic)
│   ├── normalizer.py             #   입력 정규화
│   ├── business_rules.py         #   비즈니스 규칙 (VIP/긴급/지역)
│   ├── preprocessor.py           #   전처리 파이프라인
│   ├── matrix_builder.py         #   교통 매트릭스 (TMap/Kakao/Naver)
│   ├── unreachable_filter.py     #   도달 불가능 필터
│   └── chunked_matrix.py         #   OSRM 병렬 청킹
│
├── control/                      # 최적화 제어 (1,258줄)
│   ├── vroom_config.py           #   제어 레벨 설정 (BASIC/STANDARD/PREMIUM)
│   ├── controller.py             #   최적화 오케스트레이션
│   ├── constraint_tuner.py       #   제약 완화 전략 (6단계)
│   └── multi_scenario.py         #   다중 시나리오 엔진
│
├── optimization/                 # VROOM 실행 (601줄)
│   ├── vroom_executor.py         #   바이너리 직접 호출 (stdin/stdout)
│   └── two_pass.py               #   2-Pass 최적화
│
├── postprocessing/               # 후처리 (592줄)
│   ├── constraint_checker.py     #   미배정 사유 역추적 분석
│   ├── analyzer.py               #   품질 분석 (0-100점)
│   └── statistics.py             #   통계 생성
│
└── extensions/                   # 확장 (101줄)
    └── cache_manager.py          #   Redis + 메모리 캐싱
```

---

## 인프라 파일

| 파일 | 용도 |
|------|------|
| `Dockerfile.v3` | 멀티스테이지 빌드 (vroom-local → python:3.11-slim) |
| `docker-compose.v3.yml` | 3-서비스 구성 (OSRM + Redis + Wrapper) |
| `requirements-v3.txt` | Python 의존성 |

---

## 참고 자료 (docs/)

VROOM 엔진 자체에 대한 기술 문서. Wrapper와 직접 관련 없으나 VROOM 이해에 유용.

| 문서 | 내용 |
|------|------|
| `docs/VROOM-WRAPPER-COMPLETE-GUIDE.md` | VROOM 전체 가이드 |
| `docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md` | 미배정 원인 분석 기법 |
| `docs/VROOM-VIOLATIONS-GUIDE.md` | 제약 위반 처리 |
| `docs/VROOM-CUSTOM-CONSTRAINTS-GUIDE.md` | 커스텀 제약 조건 |
| `docs/VROOM-API-CONTROL-GUIDE.md` | VROOM API 제어 |
| `docs/README-VROOM-OSRM.md` | VROOM + OSRM 연동 |

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
| **v3.0** | **2026-02-13** | **Roouty Engine 패턴 통합 (정반합)** |

상세 변경 이력: [CHANGELOG.md](CHANGELOG.md)

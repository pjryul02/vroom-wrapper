# 문서 인덱스 및 버전 히스토리

이 문서는 프로젝트의 모든 문서를 **버전별**, **단계별**로 정리합니다.

---

## 📊 버전 개요

| 버전 | 기간 | 주요 내용 | 상태 |
|-----|------|---------|------|
| **v1.0** | ~2025.01.23 | VROOM 기본 래퍼, 미배정 분석 | ✅ 완료 |
| **v2.0** | 2025.01.24~ | 모듈형 아키텍처, 5단계 구현 | ✅ 완료 |
| **v2.1** | 2025.02.03 | 실시간 교통 매트릭스 (Phase 1.5) | ✅ 완료 |

---

## 🗂️ 문서 분류

### 1. 현재 사용 문서 (v2.0+)

**반드시 읽어야 할 문서** (순서대로):

| 순서 | 문서 | 목적 | 비고 |
|-----|------|-----|------|
| 1 | [MANUAL-SETUP-GUIDE.md](MANUAL-SETUP-GUIDE.md) | **수동 설치 가이드** | 최신, 가장 중요 |
| 2 | [MASTER-IMPLEMENTATION-ROADMAP.md](MASTER-IMPLEMENTATION-ROADMAP.md) | 전체 구현 로드맵 | 설계 참조용 |
| 3 | [PHASE-5-COMPLETE.md](PHASE-5-COMPLETE.md) | Phase 5 완료 보고서 | 구현 현황 |
| 4 | [VERIFICATION-REPORT.md](VERIFICATION-REPORT.md) | 테스트 검증 결과 | 품질 확인 |

**참고 문서**:

| 문서 | 목적 |
|-----|------|
| [USER-GUIDE.md](USER-GUIDE.md) | 자동화 기반 빠른 시작 (간단 버전) |
| [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md) | 구현 진행 상태 |
| [README.md](README.md) | 프로젝트 개요 |

---

### 2. v1.0 참고 문서 (docs/)

VROOM 자체에 대한 기술 문서. **Wrapper와 무관하게 VROOM 이해에 유용**:

| 문서 | 내용 |
|-----|------|
| [docs/VROOM-WRAPPER-COMPLETE-GUIDE.md](docs/VROOM-WRAPPER-COMPLETE-GUIDE.md) | VROOM 전체 가이드 |
| [docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md](docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md) | 미배정 원인 분석 (v1.0 핵심) |
| [docs/VROOM-VIOLATIONS-GUIDE.md](docs/VROOM-VIOLATIONS-GUIDE.md) | 제약 위반 처리 |
| [docs/VROOM-CUSTOM-CONSTRAINTS-GUIDE.md](docs/VROOM-CUSTOM-CONSTRAINTS-GUIDE.md) | 커스텀 제약 조건 |
| [docs/VROOM-API-CONTROL-GUIDE.md](docs/VROOM-API-CONTROL-GUIDE.md) | VROOM API 제어 |
| [docs/README-VROOM-OSRM.md](docs/README-VROOM-OSRM.md) | VROOM + OSRM 연동 |
| [docs/WRAPPER-SETUP.md](docs/WRAPPER-SETUP.md) | 초기 래퍼 설정 |
| [docs/QUICK-START.md](docs/QUICK-START.md) | 초기 빠른 시작 |

---

### 3. 아카이브 (archive/)

**더 이상 사용하지 않음**. v2.0 설계 시 참조한 초기 문서들:

| 문서 | 당시 목적 | 현재 상태 |
|-----|---------|---------|
| [archive/WRAPPER-IMPLEMENTATION-PLAN.md](archive/WRAPPER-IMPLEMENTATION-PLAN.md) | v2.0 초기 구현 계획 | → MASTER-IMPLEMENTATION-ROADMAP.md로 대체 |
| [archive/WRAPPER-ARCHITECTURE.md](archive/WRAPPER-ARCHITECTURE.md) | 아키텍처 설계 | → MASTER-IMPLEMENTATION-ROADMAP.md에 통합 |
| [archive/MODULAR-WRAPPER-DESIGN.md](archive/MODULAR-WRAPPER-DESIGN.md) | 모듈 설계 | → 구현 완료 |
| [archive/OSRM-AND-REALTIME-ETA.md](archive/OSRM-AND-REALTIME-ETA.md) | 실시간 ETA 설계 | → Phase 1.5로 구현 |
| [archive/API-DOCUMENTATION.md](archive/API-DOCUMENTATION.md) | API 문서 초안 | → 코드에 반영 |
| [archive/QUICK-START-V2.md](archive/QUICK-START-V2.md) | v2.0 빠른 시작 초안 | → USER-GUIDE.md로 대체 |
| [archive/PROJECT-STATUS.md](archive/PROJECT-STATUS.md) | 프로젝트 상태 | → IMPLEMENTATION-STATUS.md로 대체 |
| [archive/EXTERNAL-ACCESS.md](archive/EXTERNAL-ACCESS.md) | 외부 접근 설정 | 참고용 |
| [archive/PUSH-TO-GITHUB.md](archive/PUSH-TO-GITHUB.md) | GitHub 푸시 가이드 | 참고용 |

---

## 📅 타임라인

```
2025.01.23 (v1.0)
├── docs/ 폴더 생성 (VROOM 기술 문서)
├── 기본 래퍼 구현
└── 미배정 원인 분석 완료

2025.01.24 (v2.0 시작)
├── archive/ 폴더로 초기 문서 이동
├── MASTER-IMPLEMENTATION-ROADMAP.md 생성 (95KB)
└── Phase 1-5 구현 시작

2025.01.28 (v2.0 완료)
├── Phase 1: 전처리 (validator, normalizer, business_rules)
├── Phase 2: 통제 (vroom_config, constraint_tuner, multi_scenario)
├── Phase 3: 후처리 (result_analyzer, statistics)
├── Phase 4: 확장 (cache_manager)
├── Phase 5: 통합 (main.py, Docker)
├── PHASE-5-COMPLETE.md
├── VERIFICATION-REPORT.md
└── USER-GUIDE.md

2025.02.03 (v2.1)
├── Phase 1.5: 실시간 교통 매트릭스 (matrix_builder.py)
├── MANUAL-SETUP-GUIDE.md (수동 제어형 가이드)
├── src/config.py (설정 파일)
└── .env.example (환경 변수 템플릿)
```

---

## 🎯 문서 사용 가이드

### 처음 시작하는 경우

1. **[MANUAL-SETUP-GUIDE.md](MANUAL-SETUP-GUIDE.md)** 읽기 (섹션 1-7)
2. 각 단계별로 직접 실행하며 확인
3. 필요시 [MASTER-IMPLEMENTATION-ROADMAP.md](MASTER-IMPLEMENTATION-ROADMAP.md) 참조

### 빠르게 테스트만 하고 싶은 경우

1. **[USER-GUIDE.md](USER-GUIDE.md)** 읽기
2. `quickstart.sh` 실행

### VROOM 자체를 이해하고 싶은 경우

1. **[docs/VROOM-WRAPPER-COMPLETE-GUIDE.md](docs/VROOM-WRAPPER-COMPLETE-GUIDE.md)**
2. [docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md](docs/VROOM-WHY-UNASSIGNED-IMPLEMENTATION.md)

### 실시간 교통 연동이 필요한 경우

1. **[MANUAL-SETUP-GUIDE.md](MANUAL-SETUP-GUIDE.md)** 섹션 8 읽기
2. TMap/Kakao/Naver API 키 발급
3. `examples/traffic_matrix_example.py` 실행

### 설계 배경을 알고 싶은 경우

1. [archive/WRAPPER-ARCHITECTURE.md](archive/WRAPPER-ARCHITECTURE.md)
2. [archive/MODULAR-WRAPPER-DESIGN.md](archive/MODULAR-WRAPPER-DESIGN.md)

---

## 📁 현재 프로젝트 구조

```
vroom-wrapper-project/
├── 📄 DOCUMENT-INDEX.md        ← 이 파일 (문서 인덱스)
├── 📄 MANUAL-SETUP-GUIDE.md    ← 최신 수동 설치 가이드 ⭐
├── 📄 MASTER-IMPLEMENTATION-ROADMAP.md  ← 전체 로드맵
├── 📄 USER-GUIDE.md            ← 빠른 시작 가이드
├── 📄 PHASE-5-COMPLETE.md      ← 완료 보고서
├── 📄 VERIFICATION-REPORT.md   ← 테스트 결과
├── 📄 IMPLEMENTATION-STATUS.md ← 구현 현황
├── 📄 README.md                ← 프로젝트 개요
├── 📄 .env.example             ← 환경 변수 템플릿
│
├── 📂 src/                     ← 소스 코드 (v2.0)
│   ├── main.py                 ← API 서버
│   ├── config.py               ← 설정 파일
│   ├── preprocessing/          ← Phase 1 + 1.5
│   ├── control/                ← Phase 2
│   ├── postprocessing/         ← Phase 3
│   └── extensions/             ← Phase 4
│
├── 📂 docs/                    ← VROOM 기술 문서 (v1.0)
│   └── (VROOM 관련 가이드들)
│
├── 📂 archive/                 ← 아카이브 (사용 안함)
│   └── (초기 설계 문서들)
│
├── 📂 examples/                ← 사용 예시
│   └── traffic_matrix_example.py
│
├── 📂 tests/                   ← 테스트
│   └── unit/
│
└── 📂 samples/                 ← 샘플 데이터
    ├── sample_request.json
    └── sample_response.json
```

---

## ⚠️ 주의사항

1. **archive/ 폴더 문서는 참고만** - 현재 코드와 맞지 않을 수 있음
2. **docs/ 폴더는 VROOM 자체 문서** - Wrapper v2.0과 직접 관련 없음
3. **MANUAL-SETUP-GUIDE.md가 최신** - 다른 가이드와 충돌 시 이 문서 우선

---

## 🔄 문서 업데이트 기록

| 날짜 | 문서 | 변경 내용 |
|-----|------|---------|
| 2025.02.03 | MANUAL-SETUP-GUIDE.md | Phase 1.5 (실시간 교통) 섹션 추가 |
| 2025.02.03 | DOCUMENT-INDEX.md | 신규 생성 |
| 2025.01.28 | USER-GUIDE.md | 초기 생성 |
| 2025.01.28 | PHASE-5-COMPLETE.md | Phase 5 완료 |
| 2025.01.24 | MASTER-IMPLEMENTATION-ROADMAP.md | v2.0 로드맵 |

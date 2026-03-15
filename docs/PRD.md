# PRD: VROOM Wrapper v3.0 - 제품 요구사항 정의서

> **이 문서는**: 래퍼 v3.0의 기능 범위, 비기능 요구사항, 설계 의도 정의서.
> **언제 읽는가**: 기능 추가 전 범위 확인, 시뮬레이터 팀과 인터페이스 계약 검토, 아키텍처 방향 재확인 시.
> **관련 문서**: 실제 구현 상태 → `TECHNICAL-ARCHITECTURE.md` / API 계약 → `API-DOCUMENTATION.md`

**Product Requirements Document**
**작성일**: 2026-02-13
**버전**: v3.0
**소유**: WEMEETPLACE 배차최적화팀

---

## 1. 제품 개요

### 1.1 배경

VROOM(Vehicle Routing Open-source Optimization Machine)은 C++ 기반 오픈소스 VRP(Vehicle Routing Problem) 최적화 엔진이다. 뛰어난 성능을 가지고 있으나, 실무 배차 시스템에 적용하기 위해서는 다음과 같은 한계가 있다:

- **미배정 사유 미제공**: 작업이 배정되지 않았을 때 그 이유를 알 수 없음
- **비즈니스 규칙 부재**: VIP 우선처리, 긴급 배차, 지역 제약 등 비즈니스 로직 미지원
- **제약 완화 불가**: 미배정 발생 시 자동 재시도 불가
- **운영 기능 부재**: 인증, 캐싱, Rate Limiting 등 프로덕션 필수 기능 없음
- **교통 정보 미반영**: OSRM 정적 데이터만 사용, 실시간 교통 반영 불가

### 1.2 제품 정의

VROOM Wrapper v3.0은 VROOM 엔진을 감싸는 Python 기반 최적화 플랫폼이다. 기존 v2.0의 모든 기능을 유지하면서, 사내 Go 기반 프로덕션 시스템(Roouty Engine)에서 검증된 성능 패턴을 통합한 **정반합(正反合)** 버전이다.

### 1.3 핵심 가치

| 가치 | 설명 |
|------|------|
| **완전한 미배정 사유** | 스킬/용량/시간대/복합 제약 등 미배정 이유를 상세 분석 |
| **비즈니스 최적화** | VIP/긴급/지역 규칙을 VROOM 제약으로 자동 변환 |
| **자동 복구** | 미배정 발생 시 제약 완화 후 자동 재시도 |
| **고성능 직접 호출** | VROOM 바이너리 직접 실행 (HTTP 오버헤드 제거) |
| **대규모 처리** | OSRM 매트릭스 병렬 청킹으로 대규모 문제 처리 |

---

## 2. 아키텍처 요구사항

### 2.1 시스템 구성

```
┌─────────────────────────────────────────────────┐
│              Docker Compose (3 컨테이너)          │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │   OSRM   │  │  Redis   │  │    Wrapper     │ │
│  │  :5000   │  │  :6379   │  │    :8000       │ │
│  │          │  │          │  │                │ │
│  │ 라우팅   │  │ 캐싱     │  │ FastAPI        │ │
│  │ 엔진     │  │ (선택)   │  │ + VROOM 바이너리│ │
│  └──────────┘  └──────────┘  └────────────────┘ │
└─────────────────────────────────────────────────┘
```

**v3.0 핵심 변경**: vroom-express(Node.js HTTP 서버) 제거. VROOM C++ 바이너리를 Wrapper 컨테이너에 내장하여 subprocess stdin/stdout으로 직접 호출.

### 2.2 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| 언어 | Python | 3.11+ |
| 프레임워크 | FastAPI | 0.109+ |
| VRP 엔진 | VROOM | 1.14+ (C++ 바이너리) |
| 라우팅 | OSRM | latest |
| 캐싱 | Redis | 7+ (선택, 메모리 폴백) |
| 컨테이너 | Docker + Compose | 24+ |
| HTTP 클라이언트 | httpx | 0.26+ |

---

## 3. 기능 요구사항

### FR-1: API 엔드포인트

| ID | 엔드포인트 | 메서드 | 설명 | 인증 |
|----|-----------|--------|------|------|
| FR-1.1 | `/optimize` | POST | STANDARD 최적화 | API Key |
| FR-1.2 | `/optimize/basic` | POST | BASIC 최적화 (빠른 결과) | API Key |
| FR-1.3 | `/optimize/premium` | POST | PREMIUM 최적화 (다중 시나리오) | API Key + premium |
| FR-1.4 | `/matrix/build` | POST | OSRM 매트릭스 생성 | API Key |
| FR-1.5 | `/cache/clear` | DELETE | 캐시 삭제 | API Key |
| FR-1.6 | `/health` | GET | 헬스 체크 | 없음 |
| FR-1.7 | `/` | GET | 서비스 정보 | 없음 |

### FR-2: 전처리 (Pre-processing)

| ID | 기능 | 설명 | 구현 모듈 |
|----|------|------|-----------|
| FR-2.1 | 입력 검증 | 좌표/시간/ID 유효성 검사 | `validator.py` |
| FR-2.2 | 입력 정규화 | 기본값 설정, 좌표 반올림, 시간 변환 | `normalizer.py` |
| FR-2.3 | 비즈니스 규칙 | VIP/긴급/지역 제약을 VROOM 스킬로 변환 | `business_rules.py` |
| FR-2.4 | 교통 매트릭스 | TMap/Kakao/Naver API 기반 실시간 교통 반영 | `matrix_builder.py` |
| FR-2.5 | 도달 불가능 필터 | 매트릭스 기반 도달 불가능 작업 사전 제거 | `unreachable_filter.py` |
| FR-2.6 | 매트릭스 청킹 | 대규모 OSRM 매트릭스 병렬 분할 생성 | `chunked_matrix.py` |

### FR-3: 최적화 제어 (Control)

| ID | 기능 | 설명 | 구현 모듈 |
|----|------|------|-----------|
| FR-3.1 | 제어 레벨 | BASIC/STANDARD/PREMIUM 3단계 설정 관리 | `vroom_config.py` |
| FR-3.2 | VROOM 직접 호출 | stdin/stdout 파이프로 바이너리 실행 | `vroom_executor.py` |
| FR-3.3 | 2-Pass 최적화 | 초기 배정 → 경로별 병렬 최적화 | `two_pass.py` |
| FR-3.4 | 제약 완화 재시도 | 미배정 시 6단계 완화 전략 자동 적용 | `constraint_tuner.py` |
| FR-3.5 | 다중 시나리오 | 여러 설정으로 병렬 실행 후 최적 선택 | `multi_scenario.py` |
| FR-3.6 | 우선순위 탐지 | VIP/긴급 작업 자동 감지 및 설정 강화 | `controller.py` |

### FR-4: 후처리 (Post-processing)

| ID | 기능 | 설명 | 구현 모듈 |
|----|------|------|-----------|
| FR-4.1 | 미배정 사유 분석 | skills/capacity/time_window/max_tasks/복합 제약 분석 | `constraint_checker.py` |
| FR-4.2 | 품질 분석 | 배정률/균형도/시간창 활용도/비용 효율성 (0-100점) | `analyzer.py` |
| FR-4.3 | 통계 생성 | 차량 활용률, 비용 분석, 시간 분석, 효율 지표 | `statistics.py` |
| FR-4.4 | 개선 제안 | 미배정률/균형도 기반 개선 방안 자동 생성 | `analyzer.py` |

### FR-5: 운영 기능 (Extensions)

| ID | 기능 | 설명 | 구현 모듈 |
|----|------|------|-----------|
| FR-5.1 | API Key 인증 | Header 기반 인증 + 기능 제한 | `main_v3.py` |
| FR-5.2 | Rate Limiting | 시간 윈도우 기반 요청 제한 | `main_v3.py` |
| FR-5.3 | Redis 캐싱 | 동일 요청 캐싱 (메모리 폴백) | `cache_manager.py` |
| FR-5.4 | 환경 변수 설정 | 모든 설정을 환경 변수로 관리 | `config.py` |

---

## 4. 비기능 요구사항

### NFR-1: 성능

| ID | 요구사항 | 목표값 |
|----|---------|--------|
| NFR-1.1 | Wrapper 오버헤드 | VROOM 실행 시간 대비 < 10% |
| NFR-1.2 | 소규모 응답 시간 (5 jobs) | < 100ms |
| NFR-1.3 | 중규모 응답 시간 (100 jobs) | < 5s |
| NFR-1.4 | 대규모 응답 시간 (1000+ jobs) | < 60s |
| NFR-1.5 | OSRM 매트릭스 병렬 처리 | 8 workers, 75x75 chunk |

### NFR-2: 안정성

| ID | 요구사항 |
|----|---------|
| NFR-2.1 | VROOM 바이너리 장애 시 HTTP 폴백 |
| NFR-2.2 | Redis 장애 시 메모리 캐시 폴백 |
| NFR-2.3 | OSRM 응답 실패 시 graceful error |
| NFR-2.4 | Docker healthcheck로 자동 복구 |

### NFR-3: 배포

| ID | 요구사항 |
|----|---------|
| NFR-3.1 | Docker Compose 원커맨드 배포 |
| NFR-3.2 | 멀티스테이지 빌드 (이미지 최소화) |
| NFR-3.3 | 환경 변수 기반 설정 (12-factor) |

---

## 5. 데이터 흐름

### 5.1 STANDARD 최적화 요청 흐름

```
Client → POST /optimize (API Key)
  │
  ├─ 1. 인증 + Rate Limit 확인
  ├─ 2. 캐시 조회 (hit → 즉시 반환)
  ├─ 3. 전처리
  │     ├─ 검증 (validator)
  │     ├─ 정규화 (normalizer)
  │     ├─ 비즈니스 규칙 (business_rules)
  │     └─ 교통 매트릭스 (선택)
  ├─ 4. 최적화
  │     ├─ VROOM 설정 생성 (vroom_config)
  │     ├─ 도달 불가능 필터링 (unreachable_filter)
  │     ├─ VROOM 바이너리 실행 (vroom_executor)
  │     └─ 미배정 시 제약 완화 재시도 (constraint_tuner)
  ├─ 5. 후처리
  │     ├─ 미배정 사유 분석 (constraint_checker)
  │     ├─ 품질 분석 (analyzer)
  │     └─ 통계 생성 (statistics)
  ├─ 6. 캐시 저장
  └─ 7. 응답 반환
```

### 5.2 PREMIUM 최적화 요청 흐름

```
Client → POST /optimize/premium (API Key + premium)
  │
  ├─ 1~3. (STANDARD와 동일)
  ├─ 4. 다중 시나리오 최적화
  │     ├─ 3개 시나리오 생성 (BASIC/STANDARD/PREMIUM 설정)
  │     ├─ 병렬 실행 + 2-Pass 최적화
  │     ├─ 점수 기반 최적 선택
  │     └─ 시나리오 비교 메타데이터
  ├─ 5~7. (STANDARD와 동일 + multi_scenario_metadata)
  └─ 응답 반환
```

---

## 6. 응답 구조

### 6.1 STANDARD/PREMIUM 응답

```json
{
  "wrapper_version": "3.0.0",
  "routes": [
    {
      "vehicle": 1,
      "cost": 1435,
      "steps": [
        {"type": "start", "location": [lon, lat], "arrival": 170000000},
        {"type": "job", "id": 101, "location": [lon, lat], "arrival": 170000320},
        {"type": "end", "location": [lon, lat], "arrival": 170002035}
      ]
    }
  ],
  "summary": {
    "cost": 1435,
    "routes": 1,
    "unassigned": 2,
    "duration": 1435
  },
  "unassigned": [
    {
      "id": 102,
      "type": "job",
      "reasons": [
        {
          "type": "skills",
          "description": "필요 스킬을 가진 차량 없음",
          "details": {
            "required_skills": [3],
            "available_vehicle_skills": [[1, 2]]
          }
        }
      ]
    }
  ],
  "analysis": {
    "quality_score": 93.6,
    "assignment_rate": 80.0,
    "suggestions": ["..."]
  },
  "statistics": {
    "vehicle_utilization": {...},
    "cost_breakdown": {...},
    "time_analysis": {...},
    "efficiency_metrics": {...}
  },
  "relaxation_metadata": {
    "applied": true,
    "initial_unassigned": 3,
    "final_unassigned": 1,
    "improvement": 2
  },
  "_metadata": {
    "api_key": "Demo Client",
    "control_level": "STANDARD",
    "engine": "direct",
    "processing_time_ms": 82,
    "from_cache": false
  }
}
```

### 6.2 미배정 사유 타입

| 타입 | 설명 | 정확도 |
|------|------|--------|
| `skills` | 필요 스킬을 가진 차량이 없음 | 100% |
| `capacity` | 모든 호환 차량의 용량 초과 | 100% |
| `time_window` | 작업 시간대와 호환되는 차량 없음 | 95% |
| `max_tasks` | 호환 차량들의 최대 작업수 한도 | 90% |
| `unreachable` | 도달 불가능한 위치 (매트릭스 기반) | 100% |
| `complex_constraint` | 복합 제약으로 단일 원인 특정 불가 | 70% |

---

## 7. 버전 히스토리 요약

| 버전 | 핵심 변경 | 아키텍처 |
|------|----------|---------|
| v1.0 | 미배정 사유 분석 기본 래퍼 | 단일 파일 (`vroom_wrapper.py`) |
| v2.0 | 5-Phase 모듈형 아키텍처 | `src/` 패키지 (preprocessing/control/postprocessing/extensions) |
| v2.1 | 실시간 교통 매트릭스 (TMap/Kakao/Naver) | Phase 1.5 추가 (`matrix_builder.py`) |
| **v3.0** | **Roouty Engine 패턴 통합 (정반합)** | **VROOM 직접호출, 2-Pass, 필터링, 청킹** |

### v3.0 신규 vs v2.0 계승

| 구분 | 기능 |
|------|------|
| **v3.0 신규** | VROOM 바이너리 직접 호출, 2-Pass 최적화, 도달 불가능 필터링, OSRM 매트릭스 청킹, `/matrix/build` 엔드포인트 |
| **v2.0 계승** | 입력 전처리, 비즈니스 규칙, 제어 레벨, 제약 완화 재시도, 다중 시나리오, 미배정 사유 분석, 품질 분석, 통계, 캐싱, 인증, Rate Limiting |
| **v1.0 계승** | ConstraintChecker 미배정 역추적 분석 (skills/capacity/time_window/max_tasks/complex_constraint) |

---

## 8. 프로젝트 구조

```
vroom-wrapper-project/
├── PRD.md                       ← 이 문서
├── README.md                    ← 프로젝트 개요
├── CHANGELOG.md                 ← 버전별 변경 이력
├── DOCUMENT-INDEX.md            ← 문서 인덱스
│
├── Dockerfile.v3                ← 멀티스테이지 빌드
├── docker-compose.v3.yml        ← 3-서비스 구성
├── requirements-v3.txt          ← Python 의존성
├── .env.example                 ← 환경 변수 템플릿
│
├── src/                         ← v3.0 소스 코드
│   ├── __init__.py
│   ├── main_v3.py              ← FastAPI 메인 앱 (519줄)
│   ├── config.py               ← 환경 변수 설정 (175줄)
│   │
│   ├── preprocessing/          ← 전처리 (2,395줄)
│   │   ├── validator.py        ← 입력 검증
│   │   ├── normalizer.py       ← 입력 정규화
│   │   ├── business_rules.py   ← 비즈니스 규칙
│   │   ├── preprocessor.py     ← 전처리 파이프라인
│   │   ├── matrix_builder.py   ← 교통 매트릭스
│   │   ├── unreachable_filter.py ← 도달 불가능 필터
│   │   └── chunked_matrix.py   ← OSRM 병렬 청킹
│   │
│   ├── control/                ← 최적화 제어 (1,258줄)
│   │   ├── vroom_config.py     ← 제어 레벨 설정
│   │   ├── controller.py       ← 최적화 오케스트레이션
│   │   ├── constraint_tuner.py ← 제약 완화 전략
│   │   └── multi_scenario.py   ← 다중 시나리오
│   │
│   ├── optimization/           ← VROOM 실행 (601줄)
│   │   ├── vroom_executor.py   ← 바이너리 직접 호출
│   │   └── two_pass.py         ← 2-Pass 최적화
│   │
│   ├── postprocessing/         ← 후처리 (592줄)
│   │   ├── constraint_checker.py ← 미배정 사유 분석
│   │   ├── analyzer.py         ← 품질 분석
│   │   └── statistics.py       ← 통계 생성
│   │
│   └── extensions/             ← 확장 (101줄)
│       └── cache_manager.py    ← Redis/메모리 캐싱
│
├── docs/                       ← VROOM 기술 참고 문서
├── archive/                    ← 레거시 문서/코드 (v1.0, v2.0)
├── tests/                      ← 테스트
├── examples/                   ← 사용 예시
└── samples/                    ← 샘플 데이터
```

**총 소스 코드**: 6,243줄 / 27개 Python 파일

---

## 9. 배포 요구사항

### 9.1 사전 조건

- Docker 24+ & Docker Compose
- OSRM 한국 지도 데이터 (전처리 완료)
- VROOM Docker 이미지 (`vroom-local:latest`)

### 9.2 배포 명령

```bash
# 빌드 및 실행
docker-compose -f docker-compose.v3.yml up -d --build

# 상태 확인
curl http://localhost:8000/health
```

### 9.3 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| OSRM | 5000 | 라우팅 엔진 |
| Redis | 6379 | 캐싱 (선택) |
| Wrapper | 8000 | VRP 최적화 API |

---

## 10. 검증 기준

### 10.1 기능 검증

| 테스트 | 합격 기준 |
|--------|----------|
| Health Check | 모든 컴포넌트 "ready", VROOM "healthy" |
| BASIC 최적화 | 유효한 routes + unassigned 반환 |
| STANDARD 최적화 | routes + analysis + statistics + unassigned reasons |
| PREMIUM 최적화 | multi_scenario_metadata (3개 시나리오 비교) |
| 미배정 사유 - skills | `type: "skills"` + required_skills + available 반환 |
| 미배정 사유 - capacity | `type: "capacity"` + job_delivery + vehicle_capacities |
| 미배정 사유 - time_window | `type: "time_window"` + 시간대 비교 |
| 제약 완화 재시도 | relaxation_metadata.improvement > 0 |
| 캐시 | 동일 요청 두 번째 응답에 from_cache: true |
| 매트릭스 빌드 | durations + distances 매트릭스 반환 |

### 10.2 검증 완료 (2026-02-13)

모든 검증 항목 통과 확인됨. 상세 결과는 `docs/DEVELOPMENT-REPORT.md` 참조.

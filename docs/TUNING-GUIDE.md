# VROOM Wrapper 성능·품질 튜닝 가이드

> **이 파일이 바이블이다.** 배차 품질이 나쁘거나, 너무 느리거나, 코어가 놀거나 터지면 여기서 조절한다.
> 모든 변수는 `docker-compose.v3.yml`에 있고, 수정 후 해당 컨테이너만 재시작하면 된다.

---

## 먼저 알아야 할 것: VROOM이 배차 푸는 순서

```
요청 들어옴
  │
  ├─ [전처리] 거리행렬 계산 (OSRM에 좌표 던져서 이동시간 행렬 받아옴)
  │
  ├─ [Pass 1] VROOM 실행 — "누가 어떤 건을 담당할지" 결정 (전체 배정)
  │     내부 동작:
  │       1. 초기해 생성 (빠르게 일단 배차 한번 만들어봄)
  │       2. Local Search — 조금씩 바꿔가며 더 나은 배차 탐색 (반복)
  │       3. 시간 or 탐색 횟수 다 쓰면 그 시점 최선안 반환
  │
  ├─ [Pass 2] 기사별 재최적화 — "그 기사 담당 건들의 방문 순서" 최적화
  │     각 기사 경로를 독립적으로 VROOM 다시 실행 (병렬로 동시에)
  │
  └─ [후처리] 미배정 사유 분석, 응답 포맷 변환
```

**핵심 이해:**
- **스레드(THREADS)** = VROOM이 Local Search를 몇 방향 동시에 탐색하느냐 → **넓게** 탐색
- **탐색깊이(EXPLORATION)** = 각 방향을 얼마나 깊이 파고드느냐 → **깊게** 탐색
- 둘 다 올리면 품질↑ 속도↓, 둘 다 내리면 품질↓ 속도↑

---

## 현재 서버 사양 (12코어)

```
물리 코어: 12개
Celery Worker: 2개 (vroom-celery-worker, vroom-celery-worker-2)
Worker당 concurrency: 2 (동시 처리 task 수)
→ 최대 동시 배차 처리: 2 × 2 = 4개
```

---

## 변수 전체 설명

### ① VROOM 단일 실행 (Pass 1과 무관한 단독 /distribute, /optimize 호출 시)

| 변수 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `VROOM_THREADS` | `4` | VROOM이 동시에 탐색하는 방향 수 = 사용 코어 수 | 코어 여유 있으면 올림. 12코어 기준 최대 8 추천 |
| `VROOM_EXPLORATION` | `5` | 탐색 깊이 (1~5) | 품질 중요하면 5 유지. 빠른 응답 필요하면 3으로 낮춤 |
| `VROOM_TIMEOUT` | `300` | VROOM 최대 실행 시간 (초) | 500건 이상이면 600으로 늘릴 것 |

> **예시:** 50건 빠르게 → `THREADS=2, EXPLORATION=3` / 300건 품질 중요 → `THREADS=8, EXPLORATION=5`

---

### ② Pass 1 — 전체 배정 단계

| 변수 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `TWO_PASS_ENABLED` | `true` | 2-Pass 최적화 켜기/끄기 | 끄면 단순 1회 실행. 켜놓는 게 항상 나음 |
| `TWO_PASS_INITIAL_THREADS` | `8` | Pass 1에서 VROOM이 쓰는 스레드 수 | 12코어에서 8이 적정. 단독 실행이라 여유 있게 씀 |
| `TWO_PASS_INITIAL_EXPLORATION` | `5` | Pass 1 탐색 깊이 | 배정 품질에 직결. 5 유지 추천 |

---

### ③ Pass 2 — 기사별 순서 최적화 단계

| 변수 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `TWO_PASS_MAX_WORKERS` | `4` | 동시에 최적화할 기사 경로 수 | 기사 10명이면 4개씩 병렬. 코어 상황 보고 조절 |
| `TWO_PASS_ROUTE_THREADS` | `4` | 경로 하나당 VROOM 스레드 수 | MAX_WORKERS × ROUTE_THREADS = 코어 사용량 |
| `TWO_PASS_ROUTE_EXPLORATION` | `5` | Pass 2 탐색 깊이 | 기사별 최적 순서에 영향. 5 유지 추천 |

> **코어 계산 예시 (현재 설정):**
> Pass 2 동시 코어 = `MAX_WORKERS(4) × ROUTE_THREADS(4)` = 16코어
> → 12코어 서버에서 살짝 오버. 여유 없으면 `MAX_WORKERS=2`로 낮출 것

---

### ④ Celery Worker — 동시 처리량

Celery는 `docker-compose.v3.yml`의 `command`에서 설정한다 (환경변수 아님).

```yaml
command: python -m celery ... worker --concurrency=2
```

| 설정 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `--concurrency` | `2` | worker 1개가 동시에 처리하는 dispatch 수 | 올리면 처리량↑ but 각 배차가 느려짐 |
| Worker 컨테이너 수 | `2개` | celery-worker + celery-worker-2 | 트래픽 적으면 worker-2 `docker stop`으로 끔 |

> **공식:** 총 동시 처리 = `worker 수 × concurrency` = 2 × 2 = **4개 동시 배차**

---

### ⑤ 거리행렬 계산 (OSRM)

배차 전에 모든 지점 간 이동시간을 OSRM에서 받아오는 단계. 건수 많을수록 오래 걸림.

| 변수 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `OSRM_CHUNK_SIZE` | `75` | 한 번에 OSRM에 보내는 지점 수 (75×75 행렬) | OSRM이 불안정하면 50으로 낮춤 |
| `OSRM_MAX_WORKERS` | `8` | 청크를 동시에 요청하는 수 | OSRM 서버 부하 보고 조절. 현재 8이면 충분 |
| `MATRIX_CACHE_TTL` | `300` | 거리행렬 캐시 유효시간 (초, 5분) | 같은 지점 반복 요청 많으면 늘림 |
| `MATRIX_PARALLEL_REQUESTS` | `10` | 거리행렬 병렬 요청 수 | 높을수록 빠름. OSRM 과부하 시 낮춤 |
| `MATRIX_PREP_ENABLED` | `true` | 사전 거리행렬 계산 켜기 | 끄면 느려짐. 항상 켜놓을 것 |

---

### ⑥ 도달 불가능 필터링

VROOM에 넘기기 전에 "이 기사가 이 시간 안에 절대 못 가는 건"을 미리 걸러냄.
걸러내면 VROOM 입력이 줄어서 더 빠르고 정확해짐.

| 변수 | 현재값 | 설명 | 조절 기준 |
|------|--------|------|----------|
| `UNREACHABLE_FILTER_ENABLED` | `true` | 필터링 켜기 | 항상 켜놓을 것 |
| `UNREACHABLE_THRESHOLD` | `43200` | 도달 불가 기준 이동시간 (초, 현재 12시간) | 너무 많이 걸러지면 늘림. 기본값으로 충분 |

---

## 12코어 기준 전체 코어 사용량 계산

```
동시 4 dispatch 실행 시:

Pass 1 (배정):
  4 dispatch × INITIAL_THREADS(8) = 32코어 ← 오버! 실제론 경쟁
  (Pass 1은 순차 실행이 아니라 겹칠 수 있음)

Pass 2 (순서):
  MAX_WORKERS(4) × ROUTE_THREADS(4) = 16코어 per dispatch

현실적으로 모든 dispatch가 동시에 Pass 1에 있진 않으므로 감당 가능.
하지만 트래픽 폭증 시 INITIAL_THREADS=4 로 낮추는 것 고려.
```

---

## 빠른 조절 레시피

### 배차 결과 품질이 나쁠 때
```
VROOM_EXPLORATION=5 (최대)
TWO_PASS_INITIAL_EXPLORATION=5
TWO_PASS_ROUTE_EXPLORATION=5
TWO_PASS_INITIAL_THREADS=8 이상
```

### 배차가 너무 느릴 때
```
VROOM_EXPLORATION=3
TWO_PASS_INITIAL_EXPLORATION=3
TWO_PASS_ROUTE_EXPLORATION=3
TWO_PASS_MAX_WORKERS=2
```

### 동시 요청 많이 처리하고 싶을 때
```
--concurrency=3 (command에서)
VROOM_THREADS=2
TWO_PASS_INITIAL_THREADS=4
TWO_PASS_MAX_WORKERS=2
→ 스레드 수 낮추고 동시 처리량 늘리는 트레이드오프
```

### 코어가 놀고 있을 때 (단일 요청 품질 극대화)
```
--concurrency=1
VROOM_THREADS=8
TWO_PASS_INITIAL_THREADS=12
TWO_PASS_MAX_WORKERS=4
TWO_PASS_ROUTE_THREADS=3
```

---

## 변경 후 적용 방법

```bash
# docker-compose.v3.yml 수정 후
docker compose -f ~/vroom-wrapper-project/docker-compose.v3.yml up -d --no-deps celery-worker celery-worker-2

# wrapper도 변경했다면
docker compose -f ~/vroom-wrapper-project/docker-compose.v3.yml up -d --no-deps wrapper

# 로그 확인
docker logs -f vroom-celery-worker
```

---

## 운영 전환 시 체크리스트

- [ ] `LOG_LEVEL=INFO` 로 변경 (DEBUG는 I/O 부담)
- [ ] `--loglevel=info` (celery command)
- [ ] VROOM_EXPLORATION, TWO_PASS_*_EXPLORATION 품질/속도 균형 재확인
- [ ] concurrency × INITIAL_THREADS ≤ 코어 수 확인

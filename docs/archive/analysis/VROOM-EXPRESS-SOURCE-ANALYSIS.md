# vroom-express 소스코드 완전 분석

## 📂 클론 위치
```
/home/shawn/vroom-express/
```

## 📋 목차
1. [프로젝트 구조](#프로젝트-구조)
2. [핵심 코드 분석](#핵심-코드-분석)
3. [실행 흐름](#실행-흐름)
4. [설정 시스템](#설정-시스템)
5. [라우팅 백엔드 연동](#라우팅-백엔드-연동)
6. [우리 Wrapper와의 차이점](#우리-wrapper와의-차이점)

---

## 프로젝트 구조

```
vroom-express/
├── src/
│   ├── index.js              # 🎯 메인 Express 서버 (338줄)
│   └── config.js             # ⚙️ 설정 로더 (80줄)
│
├── config.yml                # 🔧 기본 설정
├── package.json              # 📦 의존성
│
├── healthchecks/
│   └── vroom_custom_matrix.json  # 헬스체크용 테스트 데이터
│
└── README.md
```

**총 코드량**: 약 420줄 (매우 단순함!)

---

## 핵심 코드 분석

### 1. index.js - 메인 서버 (338줄)

#### 구조 개요
```javascript
// 1. 모듈 로딩 (1-9줄)
const {spawn} = require('child_process');
const express = require('express');
// ...

// 2. Express 앱 초기화 (12줄)
const app = express();

// 3. 미들웨어 설정 (20-58줄)
// - CORS
// - JSON 파싱
// - 로깅
// - 보안 (helmet)

// 4. 핵심 함수들 (60-295줄)
// - sizeCheckCallback(): 입력 크기 검증
// - execCallback(): VROOM 실행

// 5. 라우트 설정 (297-331줄)
// - POST / : 최적화 요청
// - GET /health : 헬스체크

// 6. 서버 시작 (333-337줄)
app.listen(3000);
```

#### 핵심 함수 1: execCallback() - VROOM 실행기

```javascript
function execCallback(req, res) {
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 1단계: 옵션 파싱 (164-207줄)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const options = defaultOptions.slice();

  // 기본값
  let planMode = args.planmode;      // false
  let geometry = args.geometry;      // false
  let nbThreads = args.threads;      // 4
  let explorationLevel = args.explore; // 5

  // 요청의 options 필드에서 오버라이드
  const reqOptions = req.body.options;
  if (reqOptions) {
    if ('g' in reqOptions) {
      geometry = Boolean(reqOptions.g);  // geometry 반환 여부
    }
    if ('c' in reqOptions) {
      planMode = Boolean(reqOptions.c);  // plan mode
    }
    if ('t' in reqOptions) {
      nbThreads = reqOptions.t;          // 스레드 수
    }
    if ('x' in reqOptions) {
      explorationLevel = reqOptions.x;   // 탐색 레벨 (0-5)
    }
  }

  // 옵션을 CLI 인자로 변환
  if (planMode) options.push('-c');
  if (geometry) options.push('-g');
  options.push('-t', nbThreads);
  options.push('-x', explorationLevel);

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 2단계: 입력을 파일로 저장 (218-234줄)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const timestamp = Math.floor(Date.now() / 1000);
  const fileName = path.join(
    args.logdir,
    timestamp + '_' + uuid.v1() + '.json'
  );

  try {
    fs.writeFileSync(fileName, JSON.stringify(req.body));
  } catch (err) {
    // 파일 쓰기 실패 시 500 에러
    res.status(500).send({
      code: 1,
      error: 'Internal error'
    });
    return;
  }

  options.push('-i', '"' + fileName + '"');

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 3단계: VROOM 프로세스 실행 (238줄)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const vroom = spawn(vroomCommand, options, {shell: true});
  // vroomCommand = '/usr/local/bin/vroom'

  // 예: vroom -r osrm -a car:0.0.0.0 -p car:5000
  //          -t 4 -x 5 -i "/tmp/1234567890_uuid.json"

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 4단계: 출력 수집 (240-262줄)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  vroom.on('error', err => {
    res.status(500).send({
      code: 1,
      error: 'Unknown internal error'
    });
  });

  vroom.stderr.on('data', data => {
    console.error(data.toString());
  });

  let solution = '';
  vroom.stdout.on('data', data => {
    solution += data.toString();  // JSON 문자열 누적
  });

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 5단계: 결과 반환 (264-294줄)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  vroom.on('close', (code, signal) => {
    // Exit code에 따른 HTTP 상태 코드 결정
    switch (code) {
      case 0:  // OK
        res.status(200);
        break;
      case 1:  // Internal error
        res.status(500);
        break;
      case 2:  // Input error
        res.status(400);
        break;
      case 3:  // Routing error
        res.status(500);
        break;
      default:
        res.status(500);
        solution = {
          code: 1,
          error: 'Internal error'
        };
    }

    res.send(solution);  // JSON 응답

    // 임시 파일 정리
    if (fileExists(fileName)) {
      fs.unlinkSync(fileName);
    }
  });
}
```

**핵심 포인트**:
1. **동기 방식 아님**: `spawn()`으로 비동기 프로세스 실행
2. **임시 파일 사용**: 입력을 파일로 저장 → VROOM `-i` 옵션
3. **stdout 스트리밍**: VROOM 출력을 문자열로 누적
4. **자동 정리**: 프로세스 종료 시 임시 파일 삭제

#### 핵심 함수 2: sizeCheckCallback() - 크기 검증

```javascript
function sizeCheckCallback(maxLocationNumber, maxVehicleNumber) {
  return function (req, res, next) {
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // 1. 필수 필드 확인
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    const hasJobs = 'jobs' in req.body;
    const hasShipments = 'shipments' in req.body;
    const correctInput = (hasJobs || hasShipments) && 'vehicles' in req.body;

    if (!correctInput) {
      res.status(400).send({
        code: 2,
        error: 'Invalid JSON object, need vehicles and jobs/shipments'
      });
      return;
    }

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // 2. 위치 수 계산
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    let nbLocations = 0;
    if (hasJobs) {
      nbLocations += req.body.jobs.length;
    }
    if (hasShipments) {
      nbLocations += 2 * req.body.shipments.length;  // pickup + delivery
    }

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // 3. 제한 검증
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if (nbLocations > maxLocationNumber) {  // 기본 1000
      res.status(413).send({  // 413 Payload Too Large
        code: 4,
        error: `Too many locations (${nbLocations}), max is ${maxLocationNumber}`
      });
      return;
    }

    if (req.body.vehicles.length > maxVehicleNumber) {  // 기본 200
      res.status(413).send({
        code: 4,
        error: `Too many vehicles (${vehicles}), max is ${maxVehicleNumber}`
      });
      return;
    }

    next();  // 검증 통과
  };
}
```

#### 라우트 설정

```javascript
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// POST / - 최적화 요청 (297-300줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app.post(args.baseurl, [
  sizeCheckCallback(args.maxlocations, args.maxvehicles),  // 미들웨어 1
  execCallback,                                            // 미들웨어 2
]);

// 예: POST http://localhost:3000/
// 1. sizeCheckCallback() 실행 → 크기 검증
// 2. execCallback() 실행 → VROOM 호출

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// GET /health - 헬스체크 (303-331줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app.get(args.baseurl + 'health', (req, res) => {
  const vroom = spawn(
    vroomCommand,
    ['-i', './healthchecks/vroom_custom_matrix.json'],
    {shell: true}
  );

  let msg = 'healthy';
  let status = 200;

  vroom.on('error', () => {
    msg = 'vroom is not in $PATH';
    status = 500;
  });

  vroom.stderr.on('data', err => {
    msg = err.toString();
    status = 500;
  });

  vroom.on('close', code => {
    res.status(status).send();
  });
});

// 예: GET http://localhost:3000/health
// → vroom 실행 테스트 → 200 또는 500
```

---

### 2. config.js - 설정 로더 (80줄)

```javascript
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 1. config.yml 로드 (6-15줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
let config_yml;
try {
  config_yml = yaml.load(fs.readFileSync('./config.yml'));
} catch (err) {
  console.log('Please provide a valid config.yml');
  process.exit(1);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 2. 환경변수 우선 (17-25줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const router = process.env.VROOM_ROUTER || config_yml.cliArgs.router;
const logdir = process.env.VROOM_LOG || config_yml.cliArgs.logdir;

// Docker 환경변수로 설정 가능:
// - VROOM_ROUTER=osrm
// - VROOM_LOG=/conf

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 3. CLI 인자 파싱 (27-52줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const cliArgs = minimist(process.argv.slice(2), {
  alias: {
    o: 'override',
    p: 'port',
    r: 'router',
  },
  default: {
    baseurl: '/',
    explore: 5,           // 탐색 레벨 (0-5)
    geometry: false,      // geometry 반환 여부
    limit: '1mb',         // 요청 크기 제한
    maxlocations: 1000,   // 최대 위치 수
    maxvehicles: 200,     // 최대 차량 수
    port: 3000,
    router: 'osrm',
    threads: 4,           // 스레드 수
    timeout: 300000,      // 5분
    // ... config.yml 값으로 초기화
  },
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 4. 에러 코드 정의 (58-73줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const vroomErrorCodes = {
  ok: 0,           // 성공
  internal: 1,     // 내부 에러
  input: 2,        // 입력 에러
  routing: 3,      // 라우팅 에러
  tooLarge: 4,     // 크기 초과
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 5. 내보내기 (75-79줄)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
module.exports = {
  cliArgs: cliArgs,
  routingServers: config_yml.routingServers,
  vroomErrorCodes: vroomErrorCodes,
};
```

---

### 3. config.yml - 설정 파일

```yaml
cliArgs:
  geometry: false          # -g: 경로 형상 반환 여부
  planmode: false          # -c: plan mode
  threads: 4               # -t: 스레드 수
  explore: 5               # -x: 탐색 레벨 (0=빠름, 5=정확)
  limit: '1mb'             # 요청 크기 제한
  logdir: '..'             # 로그 디렉토리
  logsize: '100M'          # 로그 파일 최대 크기
  maxlocations: 1000       # 최대 위치 수
  maxvehicles: 200         # 최대 차량 수
  override: ['c', 'g', 'l', 't', 'x']  # 오버라이드 허용 옵션
  path: ''                 # vroom 바이너리 경로
  port: 3000               # HTTP 포트
  router: 'osrm'           # 라우팅 백엔드
  timeout: 300000          # 타임아웃 (5분)
  baseurl: '/'             # API base URL

routingServers:
  osrm:
    car:
      host: '0.0.0.0'
      port: '5000'
    bike:
      host: '0.0.0.0'
      port: '5001'
    foot:
      host: '0.0.0.0'
      port: '5002'

  ors:  # OpenRouteService
    driving-car:
      host: '0.0.0.0/ors/v2'
      port: '8080'
    # ... 더 많은 프로필

  valhalla:  # Valhalla
    auto:
      host: '0.0.0.0'
      port: '8002'
    # ... 더 많은 프로필
```

**설정 우선순위**:
```
1순위: CLI 인자 (node src/index.js -p 3001)
2순위: 환경변수 (VROOM_ROUTER=osrm)
3순위: config.yml
```

---

## 실행 흐름

### 전체 플로우

```
┌─────────────────────────────────────────────────────────────┐
│  1. HTTP 요청 수신                                           │
│     POST http://localhost:3000/                             │
│     Content-Type: application/json                          │
│     { "vehicles": [...], "jobs": [...] }                    │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  2. Express 미들웨어 체인                                    │
│     ├─ CORS 헤더 추가                                       │
│     ├─ JSON 파싱 (express.json)                             │
│     ├─ 로깅 (morgan)                                        │
│     └─ 보안 (helmet)                                        │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  3. sizeCheckCallback() - 크기 검증                         │
│     ├─ vehicles 존재 확인                                   │
│     ├─ jobs 또는 shipments 존재 확인                        │
│     ├─ 위치 수 검증 (≤ 1000)                                │
│     └─ 차량 수 검증 (≤ 200)                                 │
│                                                             │
│     ✅ 통과 → next()                                        │
│     ❌ 실패 → 400/413 응답                                  │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  4. execCallback() - VROOM 실행                             │
│                                                             │
│     ① 옵션 파싱                                             │
│        - req.body.options에서 g, c, t, x 추출              │
│        - CLI 인자로 변환: ['-t', 4, '-x', 5, ...]          │
│                                                             │
│     ② 임시 파일 생성                                        │
│        - 파일명: /tmp/1234567890_uuid.json                  │
│        - 내용: JSON.stringify(req.body)                     │
│                                                             │
│     ③ VROOM 프로세스 실행                                   │
│        spawn('/usr/local/bin/vroom',                        │
│              ['-r', 'osrm',                                 │
│               '-a', 'car:0.0.0.0',                          │
│               '-p', 'car:5000',                             │
│               '-t', 4,                                      │
│               '-x', 5,                                      │
│               '-i', '/tmp/1234567890_uuid.json'])           │
│                                                             │
│     ④ 출력 수집                                             │
│        - stdout: solution += data (JSON 누적)               │
│        - stderr: console.error()                            │
│                                                             │
│     ⑤ 프로세스 종료 대기                                    │
│        - exit code 확인                                     │
│        - HTTP 상태 코드 결정                                │
│        - 임시 파일 삭제                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  5. VROOM C++ 엔진 실행 (별도 프로세스)                      │
│                                                             │
│     ① 입력 파일 읽기                                        │
│        - /tmp/1234567890_uuid.json 파싱                     │
│                                                             │
│     ② matrices 확인                                         │
│        - 있음 → 그대로 사용 ✅                              │
│        - 없음 → OSRM 호출                                   │
│           GET http://0.0.0.0:5000/table/v1/driving/...     │
│                                                             │
│     ③ 최적화 알고리즘 실행                                  │
│        - Local Search                                       │
│        - Cross-exchange, 2-opt, Relocate 등                 │
│                                                             │
│     ④ 결과 JSON 생성                                        │
│        - stdout으로 출력                                    │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  6. HTTP 응답                                               │
│     Status: 200 (성공) / 400 (입력 에러) / 500 (내부 에러)   │
│     Body: { "code": 0, "summary": {...}, "routes": [...] }  │
└─────────────────────────────────────────────────────────────┘
```

### 타이밍 분석

| 단계 | 소요시간 (예상) | 설명 |
|------|----------------|------|
| 1-4 | ~10ms | Express 처리 (매우 빠름) |
| 5 | 100ms ~ 수십초 | VROOM 최적화 (문제 크기에 따라) |
| 6 | ~5ms | 응답 전송 |

**총 소요시간 ≈ VROOM 실행시간**

---

## 설정 시스템

### 옵션 오버라이드 메커니즘

```javascript
// config.yml
override: ['c', 'g', 'l', 't', 'x']

// 허용된 옵션만 요청에서 오버라이드 가능
req.body.options = {
  g: true,     // ✅ geometry (허용)
  t: 8,        // ✅ threads (허용)
  x: 3,        // ✅ exploration level (허용)
  unknown: 1   // ❌ 무시됨
}
```

### 탐색 레벨 (exploration level)

| 레벨 | 설명 | 속도 | 품질 |
|------|------|------|------|
| 0 | 최소 탐색 | ⚡⚡⚡ | ⭐ |
| 1-2 | 빠른 휴리스틱 | ⚡⚡ | ⭐⭐ |
| 3-4 | 균형 | ⚡ | ⭐⭐⭐ |
| **5** | 최대 탐색 (기본) | 🐢 | ⭐⭐⭐⭐⭐ |

```javascript
// 요청에서 오버라이드
{
  "vehicles": [...],
  "jobs": [...],
  "options": {
    "x": 3  // 탐색 레벨을 3으로 낮춤 → 더 빠름
  }
}
```

---

## 라우팅 백엔드 연동

### OSRM 연동 방식

```javascript
// config.yml
routingServers:
  osrm:
    car:
      host: '0.0.0.0'
      port: '5000'

// ↓ CLI 인자로 변환

// vroom 실행 시:
spawn('vroom', [
  '-r', 'osrm',           // 라우터 타입
  '-a', 'car:0.0.0.0',    // 프로필:호스트
  '-p', 'car:5000',       // 프로필:포트
  '-i', 'input.json'
])
```

### VROOM이 OSRM 호출하는 방식

```cpp
// vroom C++ 내부 (추정)
if (!input.matrices) {
  // OSRM table 서비스 호출
  string url = "http://" + host + ":" + port +
               "/table/v1/driving/" + coordinates;

  json response = http_get(url);

  matrices.durations = response["durations"];
  matrices.distances = response["distances"];
}
```

### 우리가 matrices를 제공하면?

```json
{
  "vehicles": [...],
  "jobs": [...],
  "matrices": {
    "durations": [[...]],  // ← 이미 있음!
    "distances": [[...]]
  }
}
```

**결과**: vroom-express → VROOM → **OSRM 호출 스킵** ✅

---

## 우리 Wrapper와의 차이점

### 기능 비교

| 기능 | vroom-express | 우리 Wrapper |
|------|--------------|-------------|
| **HTTP API** | ✅ Express | ✅ FastAPI |
| **입력 검증** | ✅ 크기만 | ✅ 상세 검증 + 타입 체크 |
| **라우팅** | ✅ OSRM (정적) | ✅ TMap/Kakao (실시간) |
| **매트릭스** | ❌ OSRM만 | ✅ 하이브리드 (거리+시간) |
| **비즈니스 룰** | ❌ | ✅ Phase 2 (시간창, 우선순위 등) |
| **다중 시나리오** | ❌ | ✅ 자동 비교 |
| **결과 분석** | ❌ | ✅ Phase 5 (품질 분석) |
| **자동 재시도** | ❌ | ✅ 미배정 시 재시도 |
| **캐싱** | ❌ | ✅ Redis |
| **프로파일링** | ❌ | ✅ 성능 모니터링 |

### 코드량 비교

| 프로젝트 | 코드량 | 복잡도 |
|---------|-------|--------|
| **vroom-express** | ~420줄 | 낮음 (단순 브릿지) |
| **우리 Wrapper** | ~5000줄+ | 높음 (풀스택) |

### 아키텍처 차이

#### vroom-express (단순)
```
HTTP Request
    ↓
Express (파싱)
    ↓
Size Check
    ↓
spawn('vroom', ...)
    ↓
stdout → HTTP Response
```

#### 우리 Wrapper (정교)
```
HTTP Request
    ↓
FastAPI (검증)
    ↓
Phase 1: Validation
    ↓
Phase 2: Normalization
    ↓
Phase 3: Business Rules
    ↓
Phase 1.5: Traffic Matrix (TMap)
    ↓
Phase 4: vroom-express 호출
    │         ↓
    │      VROOM C++
    │         ↓
    ←─────┘
    ↓
Phase 5: Analysis
    ↓
HTTP Response (enriched)
```

### 우리가 vroom-express를 우회하는 방법

```python
# 우리 Wrapper에서
async def process(self, vrp_input):
    # ... Phase 1-3 ...

    # Phase 1.5: 실시간 교통 매트릭스
    matrices = await self.matrix_builder.build_matrix(
        locations=all_locations,
        provider='tmap'  # 🎯 TMap API
    )

    # VROOM 입력에 추가
    result['matrices'] = {
        'durations': matrices['durations'],  # TMap 실시간
        'distances': matrices['distances']   # OSRM 정적
    }

    return result

# → vroom-express로 전송
# → vroom-express는 matrices 발견
# → OSRM 호출 스킵 ✅
# → 우리가 제공한 실시간 매트릭스 사용 ✅
```

---

## 핵심 인사이트

### 1. vroom-express는 **얇은 래퍼**
- 역할: HTTP ↔ CLI 브릿지
- 로직: 거의 없음 (검증, 파일 I/O, 프로세스 관리만)
- 확장성: 낮음 (비즈니스 로직 추가 어려움)

### 2. **spawn()**으로 프로세스 분리
```javascript
const vroom = spawn('/usr/local/bin/vroom', ['-i', 'input.json']);
```
- Node.js ↔ C++ 완전 분리
- 통신: stdin/stdout (JSON)
- 장점: 언어 독립적
- 단점: 오버헤드 (프로세스 생성 + 파일 I/O)

### 3. **matrices 제공이 핵심**
```json
{
  "matrices": {
    "durations": [[...]]  // ← 이것만 제공하면
  }
}
```
→ OSRM 호출 스킵 가능!
→ 우리 Wrapper의 핵심 전략 ✅

### 4. **설정 유연성**
```
config.yml → 환경변수 → CLI 인자
```
→ Docker 환경에서 `VROOM_ROUTER` 등으로 제어 가능

### 5. **에러 처리 단순**
```javascript
vroom.on('close', code => {
  if (code === 0) res.status(200);
  else res.status(500);
});
```
→ VROOM의 exit code를 그대로 HTTP 상태로 변환

---

## 개선 아이디어

### vroom-express의 한계

1. **동기적 파일 I/O**
   ```javascript
   fs.writeFileSync(fileName, JSON.stringify(req.body));
   ```
   → 대용량 입력 시 블로킹

2. **임시 파일 의존**
   ```javascript
   const fileName = '/tmp/...' + uuid + '.json';
   ```
   → 디스크 I/O 오버헤드

3. **프로세스 오버헤드**
   ```javascript
   spawn('vroom', [...])  // 매 요청마다 프로세스 생성
   ```
   → 작은 문제에도 무거움

4. **매트릭스 캐싱 없음**
   → 같은 위치 조합도 매번 OSRM 호출

### 우리 Wrapper가 해결한 부분

✅ **비동기 I/O** (AsyncIO)
✅ **메모리 기반** 처리 (파일 없음)
✅ **Redis 캐싱** (매트릭스, 결과)
✅ **배치 최적화** (한 번에 여러 매트릭스)
✅ **실시간 교통** (TMap/Kakao)

---

## 다음 연구 단계

### 1. 로컬 실행 테스트
```bash
cd /home/shawn/vroom-express
npm install
node src/index.js
```

### 2. 직접 요청 테스트
```bash
curl -X POST http://localhost:3000 \
  -H "Content-Type: application/json" \
  -d @test-input.json
```

### 3. 커스터마이징 실험
- `config.yml` 수정 (threads, explore 등)
- `src/index.js` 수정 (로깅 추가, 검증 강화)
- 빌드 후 Docker 이미지 생성

### 4. 성능 프로파일링
- 각 단계별 소요시간 측정
- OSRM 호출 vs 커스텀 매트릭스 비교

---

## 참고 자료
- [vroom-express GitHub](https://github.com/VROOM-Project/vroom-express)
- [로컬 클론](/home/shawn/vroom-express/)
- [우리 Wrapper 연결 지점](../src/control/controller.py#L236)

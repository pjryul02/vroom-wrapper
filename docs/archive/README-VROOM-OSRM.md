# VROOM + OSRM Docker 설치 및 실행 가이드

> **레거시 문서 (v1.0~v2.0 기준)** — 최신 기술 문서는 [`docs/TECHNICAL-ARCHITECTURE.md`](TECHNICAL-ARCHITECTURE.md)를 참조하세요. 이 문서는 참고용으로만 보존됩니다.


## 개요
이 프로젝트는 OSRM (Open Source Routing Machine)과 VROOM (Vehicle Routing Optimization)을 Docker로 로컬에서 실행하는 설정입니다.

- **OSRM**: 차량 경로 탐색 엔진 (포트 5000)
- **VROOM**: 차량 경로 최적화 엔진 (포트 3000)

## 디렉토리 구조

```
/home/shawn/
├── osrm-backend/           # OSRM 소스 코드
├── osrm-data/             # OSM 맵 데이터 및 처리된 데이터
│   └── south-korea-latest.osm.pbf
├── vroom-docker/          # VROOM Docker 설정
├── vroom-conf/            # VROOM 설정 파일
│   └── config.yml
├── docker-compose.yml     # Docker Compose 설정
└── vroom-test-request.json # 샘플 테스트 요청
```

## 서비스 실행

### 모든 서비스 시작
```bash
cd /home/shawn
docker-compose up -d
```

### 서비스 상태 확인
```bash
docker-compose ps
# 또는
docker ps
```

### 서비스 중지
```bash
docker-compose down
```

### 로그 확인
```bash
# OSRM 로그
docker logs osrm-server

# VROOM 로그
docker logs vroom-server

# 실시간 로그
docker-compose logs -f
```

## API 사용 예제

### 1. OSRM - 경로 탐색 (Route)

서울에서 강남까지 경로 탐색:

```bash
curl "http://localhost:5000/route/v1/driving/126.9780,37.5665;127.0276,37.4979?overview=false"
```

geometry 포함:
```bash
curl "http://localhost:5000/route/v1/driving/126.9780,37.5665;127.0276,37.4979?overview=full&geometries=geojson"
```

### 2. OSRM - 거리/시간 매트릭스 (Table)

여러 지점 간의 거리/시간 계산:

```bash
curl "http://localhost:5000/table/v1/driving/126.9780,37.5665;127.0276,37.4979;127.0594,37.5140"
```

### 3. OSRM - 최근접 도로 찾기 (Nearest)

```bash
curl "http://localhost:5000/nearest/v1/driving/126.9780,37.5665?number=3"
```

### 4. VROOM - 차량 경로 최적화

샘플 요청 파일 사용:

```bash
curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d @vroom-test-request.json
```

직접 JSON 전송:

```bash
curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665]
      }
    ],
    "jobs": [
      {
        "id": 1,
        "location": [127.0276, 37.4979]
      },
      {
        "id": 2,
        "location": [127.0594, 37.5140]
      },
      {
        "id": 3,
        "location": [126.9910, 37.5512]
      }
    ]
  }'
```

### 5. VROOM - Health Check

```bash
curl http://localhost:3000/health
```

## 외부 접속 설정

다른 컴퓨터에서 접속하려면:

1. 방화벽에서 포트 5000, 3000 열기
2. 서버 IP 주소로 접속:
   ```bash
   # OSRM
   curl "http://서버IP:5000/route/v1/driving/126.9780,37.5665;127.0276,37.4979"

   # VROOM
   curl -X POST http://서버IP:3000/ -H "Content-Type: application/json" -d @request.json
   ```

## 맵 데이터 업데이트

새로운 지역의 OSM 데이터를 사용하려면:

1. [Geofabrik](http://download.geofabrik.de/)에서 OSM 데이터 다운로드:
   ```bash
   cd /home/shawn/osrm-data
   wget http://download.geofabrik.de/asia/south-korea-latest.osm.pbf
   ```

2. OSRM 데이터 전처리:
   ```bash
   # Extract
   docker run -t -v "${PWD}/osrm-data:/data" \
     ghcr.io/project-osrm/osrm-backend \
     osrm-extract -p /opt/car.lua /data/south-korea-latest.osm.pbf

   # Partition
   docker run -t -v "${PWD}/osrm-data:/data" \
     ghcr.io/project-osrm/osrm-backend \
     osrm-partition /data/south-korea-latest.osrm

   # Customize
   docker run -t -v "${PWD}/osrm-data:/data" \
     ghcr.io/project-osrm/osrm-backend \
     osrm-customize /data/south-korea-latest.osrm
   ```

3. 서비스 재시작:
   ```bash
   docker-compose restart
   ```

## 설정 커스터마이징

### VROOM 설정 수정

[vroom-conf/config.yml](vroom-conf/config.yml) 파일을 편집하고 재시작:

```bash
nano vroom-conf/config.yml
docker-compose restart vroom
```

주요 설정:
- `threads`: 사용할 스레드 수
- `maxlocations`: 최대 작업 위치 수
- `maxvehicles`: 최대 차량 수
- `timeout`: 요청 타임아웃 (밀리초)

### OSRM 프로파일 변경

차량 타입 변경 (car, bike, foot):
```bash
docker run -t -v "${PWD}/osrm-data:/data" \
  ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/bicycle.lua /data/south-korea-latest.osm.pbf
```

## 트러블슈팅

### 컨테이너가 시작되지 않는 경우

```bash
# 로그 확인
docker logs osrm-server
docker logs vroom-server

# 컨테이너 재시작
docker-compose restart

# 전체 재빌드
docker-compose down
docker-compose up -d --build
```

### 포트 충돌

다른 포트를 사용하려면 [docker-compose.yml](docker-compose.yml) 수정:
```yaml
ports:
  - "5001:5000"  # OSRM
  - "3001:3000"  # VROOM
```

## 유용한 링크

- [OSRM API 문서](http://project-osrm.org/docs/v5.24.0/api/)
- [VROOM API 문서](https://github.com/VROOM-Project/vroom/wiki/API)
- [VROOM 예제](https://github.com/VROOM-Project/vroom/wiki/Example)
- [Geofabrik OSM 데이터](http://download.geofabrik.de/)

## 성능 최적화

### OSRM
- `--max-table-size`: 테이블 서비스 최대 크기 증가
- `--algorithm mld`: MLD 알고리즘 사용 (기본값, 추천)
- `--algorithm ch`: CH 알고리즘 (대규모 거리 행렬에 유리)

### VROOM
- `threads`: CPU 코어 수에 맞게 조정
- `explore`: 탐색 레벨 (0-5, 높을수록 더 나은 결과지만 느림)

## 라이선스

- OSRM: BSD-2-Clause License
- VROOM: BSD-2-Clause License

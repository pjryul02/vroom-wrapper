#!/bin/bash

echo "============================================"
echo "VROOM Wrapper Setup Script"
echo "============================================"
echo ""

# 1. OSRM 데이터 다운로드
echo "[1/4] Downloading OSRM map data..."
if [ ! -f "osrm-data/south-korea-latest.osm.pbf" ]; then
    mkdir -p osrm-data
    wget -O osrm-data/south-korea-latest.osm.pbf \
        http://download.geofabrik.de/asia/south-korea-latest.osm.pbf
    echo "✓ Map data downloaded"
else
    echo "✓ Map data already exists"
fi

# 2. OSRM 데이터 전처리
echo ""
echo "[2/4] Preprocessing OSRM data..."
if [ ! -f "osrm-data/south-korea-latest.osrm" ]; then
    docker run -t -v "${PWD}/osrm-data:/data" \
        ghcr.io/project-osrm/osrm-backend:latest \
        osrm-extract -p /opt/car.lua /data/south-korea-latest.osm.pbf

    docker run -t -v "${PWD}/osrm-data:/data" \
        ghcr.io/project-osrm/osrm-backend:latest \
        osrm-partition /data/south-korea-latest.osrm

    docker run -t -v "${PWD}/osrm-data:/data" \
        ghcr.io/project-osrm/osrm-backend:latest \
        osrm-customize /data/south-korea-latest.osrm

    echo "✓ OSRM data preprocessed"
else
    echo "✓ OSRM data already preprocessed"
fi

# 3. VROOM Docker 이미지 빌드
echo ""
echo "[3/4] Building VROOM Docker image..."
if [ -z "$(docker images -q vroom-local:latest 2> /dev/null)" ]; then
    # VROOM 소스 클론
    if [ ! -d "vroom-docker" ]; then
        git clone https://github.com/VROOM-Project/vroom-docker.git
    fi

    cd vroom-docker
    docker build -t vroom-local:latest .
    cd ..

    echo "✓ VROOM image built"
else
    echo "✓ VROOM image already exists"
fi

# 4. Python 의존성 설치
echo ""
echo "[4/4] Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✓ Python dependencies installed"

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Start services:    docker-compose up -d"
echo "  2. Start wrapper:     python3 vroom_wrapper.py"
echo "  3. Test:              ./test-wrapper.sh"
echo ""

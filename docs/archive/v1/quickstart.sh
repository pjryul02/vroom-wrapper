#!/bin/bash

# VROOM Wrapper v2.0 빠른 시작 스크립트

echo "========================================"
echo "VROOM Wrapper v2.0 빠른 시작"
echo "========================================"
echo ""

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 단계 1: 환경 확인
echo "🔍 단계 1/5: 환경 확인 중..."
echo ""

# Python 버전 확인
echo -n "Python 버전: "
python_version=$(python --version 2>&1)
echo "$python_version"

if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python이 설치되지 않았습니다${NC}"
    echo "   설치: sudo apt install python3 (Ubuntu) 또는 brew install python (macOS)"
    exit 1
fi

# VROOM 서버 확인
echo -n "VROOM 서버: "
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 실행 중 (포트 3000)${NC}"
else
    echo -e "${YELLOW}⚠️  VROOM 서버가 실행되지 않음${NC}"
    echo "   docker-compose up -d vroom 으로 시작하세요"
fi

echo ""

# 단계 2: 의존성 설치
echo "📦 단계 2/5: 필요한 패키지 설치 중..."
echo ""

if [ ! -f "requirements-v2.txt" ]; then
    echo -e "${RED}❌ requirements-v2.txt 파일이 없습니다${NC}"
    exit 1
fi

pip install -q -r requirements-v2.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 패키지 설치 완료${NC}"
else
    echo -e "${RED}❌ 패키지 설치 실패${NC}"
    exit 1
fi

echo ""

# 단계 3: 빠른 테스트
echo "🚀 단계 3/5: 빠른 테스트 실행 중..."
echo ""

python demo_v2.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 빠른 테스트 성공!${NC}"
else
    echo ""
    echo -e "${RED}❌ 테스트 실패${NC}"
    echo "   VROOM 서버가 실행 중인지 확인하세요"
    exit 1
fi

echo ""

# 단계 4: 샘플 파일 확인
echo "📄 단계 4/5: 샘플 파일 확인..."
echo ""

if [ -f "samples/sample_request.json" ]; then
    echo -e "${GREEN}✅ 샘플 요청 파일 있음${NC}"
else
    echo -e "${YELLOW}⚠️  샘플 파일이 없습니다${NC}"
fi

if [ -f "samples/sample_response.json" ]; then
    echo -e "${GREEN}✅ 샘플 응답 파일 있음${NC}"
else
    echo -e "${YELLOW}⚠️  샘플 응답 파일이 없습니다${NC}"
fi

echo ""

# 단계 5: API 서버 시작 안내
echo "🌐 단계 5/5: 다음 단계"
echo ""
echo "API 서버를 시작하려면:"
echo -e "${YELLOW}  cd src && python main.py${NC}"
echo ""
echo "그 다음, 새 터미널에서 테스트:"
echo -e "${YELLOW}  curl -X POST http://localhost:8000/optimize \\
    -H \"X-API-Key: demo-key-12345\" \\
    -H \"Content-Type: application/json\" \\
    -d @samples/sample_request.json${NC}"
echo ""
echo "또는 Python으로:"
echo -e "${YELLOW}  python examples/basic_usage.py${NC}"
echo ""

# 완료
echo "========================================"
echo -e "${GREEN}✅ 빠른 시작 완료!${NC}"
echo "========================================"
echo ""
echo "📚 자세한 사용법: USER-GUIDE.md 참조"
echo "🚀 행복한 경로 최적화 되세요!"
echo ""

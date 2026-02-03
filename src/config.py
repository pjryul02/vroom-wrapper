"""
VROOM Wrapper v2.0 설정 파일

이 파일을 수정하여 API Key, 외부 서비스, 캐싱 등을 제어합니다.
"""

import os
from typing import Optional

# ============================================================
# API Keys
# ============================================================
# 프로덕션에서는 환경 변수나 Secrets Manager 사용 권장

API_KEYS = {
    "demo-key-12345": {
        "name": "Demo Client",
        "rate_limit": "100/hour",
        "features": ["basic", "standard", "premium"]
    },
    # 여기에 새로운 API Key 추가
    # "your-api-key": {
    #     "name": "Your Client Name",
    #     "rate_limit": "1000/hour",
    #     "features": ["basic", "standard", "premium"]
    # }
}


# ============================================================
# VROOM 서버
# ============================================================

VROOM_URL = os.getenv("VROOM_URL", "http://localhost:3000")


# ============================================================
# OSRM 서버 (거리 계산)
# ============================================================

OSRM_URL = os.getenv("OSRM_URL", "http://localhost:5000")


# ============================================================
# Redis 캐싱 (선택)
# ============================================================
# None이면 메모리 캐싱 사용

REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)


# ============================================================
# 실시간 교통 API (Phase 1.5)
# ============================================================

# 활성화 여부
TRAFFIC_MATRIX_ENABLED = os.getenv("TRAFFIC_MATRIX_ENABLED", "false").lower() == "true"

# 제공자: tmap, kakao, naver, osrm
TRAFFIC_PROVIDER = os.getenv("TRAFFIC_PROVIDER", "osrm")

# TMap API
TMAP_API_KEY: Optional[str] = os.getenv("TMAP_API_KEY", None)

# Kakao API
KAKAO_API_KEY: Optional[str] = os.getenv("KAKAO_API_KEY", None)

# Naver API
NAVER_CLIENT_ID: Optional[str] = os.getenv("NAVER_CLIENT_ID", None)
NAVER_CLIENT_SECRET: Optional[str] = os.getenv("NAVER_CLIENT_SECRET", None)

# 매트릭스 캐시 TTL (초)
MATRIX_CACHE_TTL = int(os.getenv("MATRIX_CACHE_TTL", "300"))  # 5분

# 병렬 API 요청 수
MATRIX_PARALLEL_REQUESTS = int(os.getenv("MATRIX_PARALLEL_REQUESTS", "10"))


# ============================================================
# API 서버
# ============================================================

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


# ============================================================
# 로그
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# ============================================================
# Rate Limiting
# ============================================================

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 초


# ============================================================
# Helper 함수
# ============================================================

def get_traffic_api_key() -> Optional[str]:
    """현재 설정된 교통 제공자의 API 키 반환"""
    if TRAFFIC_PROVIDER == "tmap":
        return TMAP_API_KEY
    elif TRAFFIC_PROVIDER == "kakao":
        return KAKAO_API_KEY
    elif TRAFFIC_PROVIDER == "naver":
        return NAVER_CLIENT_ID  # Naver는 별도 처리 필요
    return None


def print_config():
    """현재 설정 출력 (디버깅용)"""
    print("=== VROOM Wrapper Configuration ===")
    print(f"VROOM_URL: {VROOM_URL}")
    print(f"OSRM_URL: {OSRM_URL}")
    print(f"REDIS_URL: {REDIS_URL or '(disabled)'}")
    print(f"TRAFFIC_MATRIX_ENABLED: {TRAFFIC_MATRIX_ENABLED}")
    print(f"TRAFFIC_PROVIDER: {TRAFFIC_PROVIDER}")
    print(f"API_KEYS: {list(API_KEYS.keys())}")
    print(f"RATE_LIMIT: {RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}s")
    print("===================================")


if __name__ == "__main__":
    print_config()

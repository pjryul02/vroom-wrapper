"""API Key 인증 및 Rate Limiting"""

import time
from typing import Dict, Optional
from fastapi import HTTPException, Header
from .. import config

# Rate Limit 카운터 (인메모리)
_request_counts: Dict[str, int] = {}


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict:
    """API Key 검증"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key required (Header: X-API-Key)"
        )

    if x_api_key not in config.API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return config.API_KEYS[x_api_key]


def check_rate_limit(api_key: str, limit: Optional[int] = None):
    """Rate Limiting 확인"""
    if not config.RATE_LIMIT_ENABLED:
        return

    limit = limit or config.RATE_LIMIT_REQUESTS
    window = config.RATE_LIMIT_WINDOW
    current_window = int(time.time() // window)
    key = f"{api_key}:{current_window}"

    if key not in _request_counts:
        _request_counts[key] = 0

    _request_counts[key] += 1

    if _request_counts[key] > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests/{window}s)"
        )

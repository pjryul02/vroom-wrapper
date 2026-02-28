"""POST /matrix/build — 대규모 매트릭스 생성"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Header

from ..api_models import MatrixBuildRequest
from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/matrix/build")
async def build_matrix(
    request_body: MatrixBuildRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """v3.0: 대규모 매트릭스 생성 (OSRM 청킹)"""
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    locations = request_body.locations
    profile = request_body.profile or "driving"

    if not locations:
        raise HTTPException(status_code=400, detail="locations required")

    try:
        result = await c.matrix_builder.build_matrix(locations, profile)
        return {
            "durations": result["durations"],
            "distances": result["distances"],
            "size": len(locations),
            "_metadata": {
                "chunk_size": config.OSRM_CHUNK_SIZE,
                "max_workers": config.OSRM_MAX_WORKERS,
            }
        }
    except Exception as e:
        logger.error(f"Matrix build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

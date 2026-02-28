"""API 라우터 모듈"""

from .distribute import router as distribute_router
from .optimize import router as optimize_router
from .matrix import router as matrix_router
from .map_matching import router as map_matching_router
from .health import router as health_router
from .dispatch import router as dispatch_router

__all__ = [
    'distribute_router',
    'optimize_router',
    'matrix_router',
    'map_matching_router',
    'health_router',
    'dispatch_router',
]

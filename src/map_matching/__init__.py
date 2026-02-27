"""
Map Matching 모듈

Roouty Process Server에서 이식된 GPS 궤적 보정 엔진.
OSRM Match/Route/Nearest API를 활용하여 GPS 궤적을 도로 네트워크에 매칭.
"""

from .engine import OSRMMapMatcher, GPSOutlierDetector

__all__ = ['OSRMMapMatcher', 'GPSOutlierDetector']

"""
OSRM Map Matching Engine

Roouty Process Server에서 이식된 GPS 궤적 보정 엔진.
aiohttp → httpx, aiolimiter → asyncio.Semaphore, numpy → 순수 Python으로 변환.
"""

import asyncio
import time
import math
import os
import logging
from typing import List, Tuple, Dict, Any, Optional

import httpx

from .geometry import haversine_distance, calculate_bearing
from .config import MAX_OSRM_MATCH_COORDINATES

logger = logging.getLogger(__name__)


class GPSOutlierDetector:
    """GPS 이상값 감지 클래스"""

    def __init__(self):
        self.speed_threshold = 150       # 150m/s (540km/h)
        self.acceleration_threshold = 50  # 50m/s²
        self.distance_threshold = 200     # 200m
        self.bearing_change_threshold = 150  # 150 degrees

    def detect_outliers(self, gps_trajectory: List[List[float]]) -> List[Dict[str, Any]]:
        """GPS 튐 현상 감지"""
        outliers = []

        if len(gps_trajectory) < 3:
            return outliers

        for i in range(1, len(gps_trajectory) - 1):
            prev_point = gps_trajectory[i - 1]
            curr_point = gps_trajectory[i]
            next_point = gps_trajectory[i + 1]

            speed_outlier = self._detect_speed_outlier(prev_point, curr_point, next_point)
            accel_outlier = self._detect_acceleration_outlier(prev_point, curr_point, next_point)
            trajectory_outlier = self._detect_trajectory_outlier(prev_point, curr_point, next_point)

            if speed_outlier or accel_outlier or trajectory_outlier:
                outliers.append({
                    'index': i,
                    'point': curr_point,
                    'outlier_type': self._classify_outlier_type(speed_outlier, accel_outlier, trajectory_outlier),
                    'severity': self._calculate_outlier_severity(prev_point, curr_point, next_point)
                })

        return outliers

    def _calculate_speed(self, point1: List[float], point2: List[float]) -> float:
        if len(point1) < 3 or len(point2) < 3:
            return 0
        distance = haversine_distance((point1[1], point1[0]), (point2[1], point2[0]))
        time_diff = abs(point2[2] - point1[2])
        if time_diff > 0:
            return distance / time_diff
        return 0

    def _detect_speed_outlier(self, prev_point, curr_point, next_point) -> bool:
        speed1 = self._calculate_speed(prev_point, curr_point)
        speed2 = self._calculate_speed(curr_point, next_point)
        return speed1 > self.speed_threshold or speed2 > self.speed_threshold

    def _detect_acceleration_outlier(self, prev_point, curr_point, next_point) -> bool:
        speed1 = self._calculate_speed(prev_point, curr_point)
        speed2 = self._calculate_speed(curr_point, next_point)
        time_diff = abs(next_point[2] - prev_point[2]) / 2
        if time_diff > 0:
            acceleration = abs(speed2 - speed1) / time_diff
            return acceleration > self.acceleration_threshold
        return False

    def _detect_trajectory_outlier(self, prev_point, curr_point, next_point) -> bool:
        direct_distance = haversine_distance(
            (prev_point[1], prev_point[0]), (next_point[1], next_point[0])
        )
        detour_distance = (
            haversine_distance((prev_point[1], prev_point[0]), (curr_point[1], curr_point[0])) +
            haversine_distance((curr_point[1], curr_point[0]), (next_point[1], next_point[0]))
        )

        if detour_distance > direct_distance * 3:
            return True

        bearing1 = calculate_bearing((prev_point[1], prev_point[0]), (curr_point[1], curr_point[0]))
        bearing2 = calculate_bearing((curr_point[1], curr_point[0]), (next_point[1], next_point[0]))
        bearing_change = abs(bearing2 - bearing1)
        if bearing_change > self.bearing_change_threshold:
            return True

        return False

    def _classify_outlier_type(self, speed_outlier, accel_outlier, trajectory_outlier) -> str:
        if speed_outlier and accel_outlier:
            return "severe_jump"
        elif speed_outlier:
            return "speed_jump"
        elif trajectory_outlier:
            return "trajectory_jump"
        elif accel_outlier:
            return "acceleration_jump"
        return "unknown"

    def _calculate_outlier_severity(self, prev_point, curr_point, next_point) -> float:
        severity = 0.0

        speed1 = self._calculate_speed(prev_point, curr_point)
        speed2 = self._calculate_speed(curr_point, next_point)
        max_speed = max(speed1, speed2)

        if max_speed > self.speed_threshold:
            severity += min(1.0, max_speed / (self.speed_threshold * 2))

        distance1 = haversine_distance((prev_point[1], prev_point[0]), (curr_point[1], curr_point[0]))
        distance2 = haversine_distance((curr_point[1], curr_point[0]), (next_point[1], next_point[0]))
        max_distance = max(distance1, distance2)

        if max_distance > self.distance_threshold:
            severity += min(0.5, max_distance / (self.distance_threshold * 4))

        return min(1.0, severity)


class OSRMMapMatcher:
    """OSRM을 활용한 맵 매칭 엔진"""

    def __init__(self, osrm_url: str = None):
        if osrm_url is None:
            osrm_url = os.getenv('OSRM_URL', 'http://localhost:5000')

        self.osrm_url = osrm_url.rstrip('/')
        self.outlier_detector = GPSOutlierDetector()
        # asyncio.Semaphore for rate limiting (replaces aiolimiter)
        self._rate_semaphore = asyncio.Semaphore(50)

        self.shape_weight = 0.4
        self.continuity_weight = 0.3
        self.accuracy_weight = 0.3

        self.route_cache = {}

        logger.info(f"OSRM Map Matcher initialized: {self.osrm_url}")

    # ========== Main Entry Points ==========

    async def match_trajectory(self, trajectory_data: List[List[float]]) -> Dict[str, Any]:
        """GPS 궤적을 도로에 매칭"""
        if len(trajectory_data) < 2:
            return self._create_empty_result()

        logger.info(f"[Map Matching] 궤적 매칭 시작: {len(trajectory_data)}개 포인트")

        try:
            corrected_trajectory = await self._preprocess_trajectory(trajectory_data)
            osrm_result = await self._call_osrm_match(corrected_trajectory)

            if not osrm_result:
                logger.error("[Map Matching] OSRM 매칭 실패")
                return self._create_fallback_result(trajectory_data)

            enhanced_result = await self._enhance_matching_result(
                corrected_trajectory, osrm_result
            )
            final_result = self._finalize_result(trajectory_data, enhanced_result)

            logger.info(
                f"[Map Matching] 매칭 완료: "
                f"{final_result['summary']['matched_points']}/{final_result['summary']['total_points']}개 성공"
            )
            return final_result

        except Exception as e:
            logger.error(f"[Map Matching] 오류: {str(e)}")
            return self._create_fallback_result(trajectory_data)

    async def match_trajectory_selective(
        self,
        trajectory_data: List[List[float]],
        accuracy_threshold: float = 50.0,
        max_speed_kmh: float = 120.0,
        enable_debug: bool = False
    ) -> Dict[str, Any]:
        """
        선택적 GPS 보정 (정확도 기반)

        저정확도 구간만 감지하여 OSRM Route API로 도로 경로를 생성하고,
        해당 구간의 GPS 포인트를 경로에 투영하여 보정.
        """
        logger.info(f"[Selective Matching] 시작: {len(trajectory_data)}개 포인트")

        debug_info = {
            'enabled': enable_debug,
            'tunnel_detections': [],
            'route_selections': [],
            'gps_projections': [],
            'segment_details': []
        } if enable_debug else None

        # 1. 저정확도 구간 감지
        low_acc_segments = self._identify_low_accuracy_segments(
            trajectory_data, accuracy_threshold
        )

        logger.info(f"{len(low_acc_segments)}개 저정확도 구간 발견")

        points_to_correct = sum(len(seg['points']) for seg in low_acc_segments)
        logger.info(f"{points_to_correct}개 포인트 보정 예정 ({points_to_correct/len(trajectory_data)*100:.1f}%)")

        # 2. 결과 초기화 (원본 복사 + flag=1.0)
        corrected_trajectory = []
        for point in trajectory_data:
            corrected_trajectory.append(point[:] + [1.0])

        # 3. 각 저정확도 구간 처리
        all_intermediate_points = []
        total_corrected = 0

        for i, segment in enumerate(low_acc_segments):
            logger.info(f"구간 {i+1}/{len(low_acc_segments)} 처리 중... (Index {segment['start_idx']}-{segment['end_idx']})")

            expanded_start = max(0, segment['start_idx'] - 20)
            expanded_end = min(len(trajectory_data), segment['end_idx'] + 20)

            # 터널 감지
            tunnel_info = self._detect_tunnel_usage(trajectory_data, segment, expanded_start, expanded_end)

            if enable_debug and tunnel_info:
                debug_info['tunnel_detections'].append({
                    'segment_index': i,
                    'tunnel_name': tunnel_info['tunnel']['name'],
                    'start_idx': segment['start_idx'],
                    'end_idx': segment['end_idx']
                })

            # Waypoints 생성
            waypoints = []
            waypoint_radiuses = []
            waypoint_bearings = []

            # 시작 anchor 찾기
            start_anchor = None
            start_anchor_idx = None
            for j in range(segment['start_idx'] - 1, expanded_start - 1, -1):
                if j >= 0 and trajectory_data[j][3] <= accuracy_threshold:
                    start_anchor = trajectory_data[j][:2]
                    start_anchor_idx = j
                    waypoints.append(start_anchor)
                    waypoint_radiuses.append(150)
                    waypoint_bearings.append(None)
                    break

            # 터널 waypoints 추가
            if tunnel_info:
                tunnel = tunnel_info['tunnel']
                for idx, wp in enumerate(tunnel['waypoints']):
                    waypoints.append(wp)
                    waypoint_radiuses.append(100)
                    tunnel_bearings = tunnel.get('bearings', [])
                    if tunnel_bearings and idx < len(tunnel_bearings):
                        waypoint_bearings.append(tunnel_bearings[idx])
                    else:
                        waypoint_bearings.append(None)

            # 종료 anchor 찾기
            end_anchor = None
            end_anchor_idx = None
            for j in range(segment['end_idx'] + 1, expanded_end):
                if j < len(trajectory_data) and trajectory_data[j][3] <= accuracy_threshold:
                    end_anchor = trajectory_data[j][:2]
                    end_anchor_idx = j
                    waypoints.append(end_anchor)
                    waypoint_radiuses.append(150)
                    waypoint_bearings.append(None)
                    break

            if len(waypoints) < 2:
                logger.info(f"  앞뒤 anchor 포인트 부족, 원본 유지")
                continue

            # Route alternatives 생성
            routes = await self._get_route_alternatives_for_segment(
                waypoints, num_alternatives=3,
                waypoint_radiuses=waypoint_radiuses,
                waypoint_bearings=waypoint_bearings
            )

            if not routes:
                # Nearest API 폴백
                logger.info(f"  경로 생성 실패, Nearest API로 개별 보정 시도...")
                corrected_points = await self._correct_points_with_nearest(trajectory_data, segment)
                if corrected_points:
                    for cp in corrected_points:
                        if 0 <= cp['idx'] < len(corrected_trajectory):
                            corrected_trajectory[cp['idx']] = cp['corrected']
                            total_corrected += 1
                continue

            # 최적 경로 선택
            best_route = None
            best_similarity = 0

            if tunnel_info and routes:
                best_route = routes[0]
                best_similarity = 1.0
            else:
                all_high_acc_points = [
                    (j, trajectory_data[j][:2])
                    for j in range(expanded_start, expanded_end)
                    if trajectory_data[j][3] <= 50
                ]

                for route in routes:
                    route_geometry = route['geometry']
                    relevant_points = []

                    for idx, point in all_high_acc_points:
                        min_dist = float('inf')
                        for route_point in route_geometry:
                            dist = haversine_distance(
                                (point[1], point[0]),
                                (route_point[1], route_point[0])
                            )
                            min_dist = min(min_dist, dist)

                        if min_dist <= 500:
                            relevant_points.append(point)

                    if len(relevant_points) >= 2:
                        similarity = self._calculate_shape_similarity(relevant_points, route_geometry)
                    else:
                        similarity = 0.0

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_route = route

            # Anchor 신뢰도 확인
            anchor_trust = False
            if start_anchor_idx is not None and end_anchor_idx is not None:
                start_accuracy = trajectory_data[start_anchor_idx][3]
                end_accuracy = trajectory_data[end_anchor_idx][3]
                if start_accuracy <= 10 and end_accuracy <= 10:
                    anchor_trust = True

            if best_route:
                corrected_points = self._project_gps_to_route(
                    trajectory_data, best_route['geometry'], segment,
                    start_anchor_idx, end_anchor_idx, enable_debug, debug_info
                )

                for cp in corrected_points:
                    if cp['idx'] == -1:
                        all_intermediate_points.append(cp)
                    else:
                        if 0 <= cp['idx'] < len(corrected_trajectory):
                            corrected_trajectory[cp['idx']] = cp['corrected']
                            total_corrected += 1

            elif routes and anchor_trust:
                best_route = routes[0]
                corrected_points = self._project_gps_to_route(
                    trajectory_data, best_route['geometry'], segment,
                    start_anchor_idx, end_anchor_idx, enable_debug, debug_info
                )

                for cp in corrected_points:
                    if cp['idx'] == -1:
                        all_intermediate_points.append(cp)
                    else:
                        if 0 <= cp['idx'] < len(corrected_trajectory):
                            corrected_trajectory[cp['idx']] = cp['corrected']
                            total_corrected += 1
            else:
                corrected_points = await self._correct_points_with_nearest(trajectory_data, segment)
                if corrected_points:
                    for cp in corrected_points:
                        if 0 <= cp['idx'] < len(corrected_trajectory):
                            corrected_trajectory[cp['idx']] = cp['corrected']
                            total_corrected += 1

        # 4. 중간 포인트 타임스탬프 기반 병합
        if all_intermediate_points:
            logger.info(f"{len(all_intermediate_points)}개 중간 포인트 병합 중...")

            all_points = []
            for idx, pt in enumerate(corrected_trajectory):
                all_points.append({
                    'original_idx': idx,
                    'point': pt,
                    'timestamp': pt[2]
                })

            for cp in all_intermediate_points:
                all_points.append({
                    'original_idx': -1,
                    'point': cp['corrected'],
                    'timestamp': cp['corrected'][2]
                })

            all_points.sort(key=lambda x: x['timestamp'])

            # 타임스탬프 순서 보정
            for i in range(1, len(all_points)):
                if all_points[i]['timestamp'] <= all_points[i-1]['timestamp']:
                    all_points[i]['point'][2] = all_points[i-1]['timestamp'] + 1
                    all_points[i]['timestamp'] = all_points[i-1]['timestamp'] + 1

            # 속도 검증 (120km/h = 33.33m/s)
            MAX_SPEED_MPS = 33.33
            filtered_points = []
            for i in range(len(all_points)):
                current_point = all_points[i]
                current_flag = current_point['point'][3] if len(current_point['point']) > 3 else 0

                if current_flag in [0.5, 1.0] or i == 0:
                    filtered_points.append(current_point)
                    continue

                if current_flag == 2.0 and filtered_points:
                    last = filtered_points[-1]
                    prev_coords = (last['point'][1], last['point'][0])
                    curr_coords = (current_point['point'][1], current_point['point'][0])
                    distance = haversine_distance(prev_coords, curr_coords)
                    time_diff = (current_point['timestamp'] - last['timestamp'])

                    if time_diff > 0:
                        speed = distance / time_diff
                        if speed > MAX_SPEED_MPS:
                            continue

                filtered_points.append(current_point)

            corrected_trajectory = [p['point'] for p in filtered_points]

        # 엣지 연속성 검사
        corrected_trajectory = self._check_edge_continuity(corrected_trajectory)

        # 터널 내 제거된 포인트 필터링
        filtered_trajectory = [pt for pt in corrected_trajectory if len(pt) < 7 or pt[6] != -1.0]

        # 결과 구성
        result = {
            'matched_trace': filtered_trajectory,
            'summary': {
                'total_points': len(trajectory_data),
                'corrected_points': total_corrected,
                'kept_original': len(trajectory_data) - total_corrected,
                'low_accuracy_segments': len(low_acc_segments),
                'correction_rate': round(total_corrected / len(trajectory_data) * 100, 2) if trajectory_data else 0
            }
        }

        if enable_debug and debug_info:
            result['debug_info'] = debug_info

        logger.info(f"[Selective Matching] 완료: {total_corrected}/{len(trajectory_data)}개 보정")
        return result

    # ========== GPS Preprocessing ==========

    async def _preprocess_trajectory(self, trajectory_data: List[List[float]]) -> List[List[float]]:
        outliers = self.outlier_detector.detect_outliers(trajectory_data)
        if not outliers:
            return trajectory_data

        logger.info(f"[GPS 보정] {len(outliers)}개 이상값 감지")
        corrected_trajectory = trajectory_data.copy()

        for outlier in reversed(outliers):
            corrected_point = await self._correct_outlier(outlier, corrected_trajectory)
            if corrected_point:
                corrected_trajectory[outlier['index']] = corrected_point

        return corrected_trajectory

    async def _correct_outlier(self, outlier: Dict, trajectory: List[List[float]]) -> Optional[List[float]]:
        index = outlier['index']
        severity = outlier['severity']

        if index == 0 or index >= len(trajectory) - 1:
            return None

        prev_point = trajectory[index - 1]
        curr_point = trajectory[index]
        next_point = trajectory[index + 1]

        if severity >= 0.8:
            return await self._road_based_correction(prev_point, curr_point, next_point)
        else:
            return self._linear_interpolation_correction(prev_point, curr_point, next_point)

    def _linear_interpolation_correction(self, prev_point, curr_point, next_point) -> List[float]:
        prev_time = prev_point[2]
        curr_time = curr_point[2]
        next_time = next_point[2]

        if next_time - prev_time > 0:
            time_ratio = (curr_time - prev_time) / (next_time - prev_time)
        else:
            time_ratio = 0.5

        corrected_lon = prev_point[0] + (next_point[0] - prev_point[0]) * time_ratio
        corrected_lat = prev_point[1] + (next_point[1] - prev_point[1]) * time_ratio

        return [corrected_lon, corrected_lat, curr_time, curr_point[3], curr_point[4]]

    async def _road_based_correction(self, prev_point, curr_point, next_point) -> List[float]:
        try:
            route = await self._get_connecting_route(prev_point[:2], next_point[:2])
            if route:
                time_ratio = self._calculate_time_ratio(prev_point, curr_point, next_point)
                corrected_position = self._interpolate_on_route(route, time_ratio)
                return [corrected_position[0], corrected_position[1], curr_point[2], curr_point[3], curr_point[4]]
        except Exception:
            pass
        return self._linear_interpolation_correction(prev_point, curr_point, next_point)

    def _calculate_time_ratio(self, prev_point, curr_point, next_point) -> float:
        if next_point[2] - prev_point[2] > 0:
            return (curr_point[2] - prev_point[2]) / (next_point[2] - prev_point[2])
        return 0.5

    # ========== OSRM API Calls (httpx) ==========

    async def _get_connecting_route(self, start_coord: List[float], end_coord: List[float]) -> Optional[List[List[float]]]:
        cache_key = f"{start_coord[0]:.6f},{start_coord[1]:.6f}-{end_coord[0]:.6f},{end_coord[1]:.6f}"
        if cache_key in self.route_cache:
            return self.route_cache[cache_key]

        try:
            async with self._rate_semaphore:
                url = f"{self.osrm_url}/route/v1/driving/{start_coord[0]},{start_coord[1]};{end_coord[0]},{end_coord[1]}"
                params = {'steps': 'false', 'geometries': 'geojson'}

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes') and len(data['routes']) > 0:
                            geometry = data['routes'][0].get('geometry', {}).get('coordinates', [])
                            self.route_cache[cache_key] = geometry
                            return geometry
        except Exception as e:
            logger.error(f"[Route API] 경로 계산 실패: {e}")

        return None

    def _interpolate_on_route(self, route_geometry: List[List[float]], time_ratio: float) -> List[float]:
        if not route_geometry or len(route_geometry) < 2:
            return route_geometry[0] if route_geometry else [0, 0]

        total_length = 0
        segment_lengths = []
        for i in range(len(route_geometry) - 1):
            seg_len = haversine_distance(
                (route_geometry[i][1], route_geometry[i][0]),
                (route_geometry[i+1][1], route_geometry[i+1][0])
            )
            segment_lengths.append(seg_len)
            total_length += seg_len

        if total_length == 0:
            return route_geometry[0]

        target_distance = total_length * time_ratio
        accumulated = 0

        for i, seg_len in enumerate(segment_lengths):
            if accumulated + seg_len >= target_distance:
                remaining = target_distance - accumulated
                ratio = remaining / seg_len if seg_len > 0 else 0
                start = route_geometry[i]
                end = route_geometry[i + 1]
                return [
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio
                ]
            accumulated += seg_len

        return route_geometry[-1]

    async def _call_osrm_match(self, trajectory: List[List[float]]) -> Optional[Dict[str, Any]]:
        if len(trajectory) < 2:
            return None

        if len(trajectory) > MAX_OSRM_MATCH_COORDINATES:
            chunks = self._split_trajectory_into_chunks(trajectory)
            chunk_results = []
            for chunk, start_idx in chunks:
                result = await self._call_osrm_match_single_chunk(chunk)
                if result:
                    chunk_results.append((result, start_idx))
            if not chunk_results:
                return None
            return self._merge_chunk_results(chunk_results, len(trajectory))

        return await self._call_osrm_match_single_chunk(trajectory)

    async def _call_osrm_match_single_chunk(self, trajectory: List[List[float]]) -> Optional[Dict[str, Any]]:
        if len(trajectory) < 2:
            return None

        try:
            coordinates = []
            timestamps = []
            radiuses = []

            for point in trajectory:
                coordinates.append(f"{point[0]},{point[1]}")
                ts = point[2]
                ts_s = int(ts / 1000) if ts > 10000000000 else int(ts)
                timestamps.append(str(ts_s))
                accuracy = point[3] if len(point) > 3 else 10
                radius = max(accuracy * 1.5, 10)
                radiuses.append(str(int(radius)))

            coords_str = ";".join(coordinates)
            timestamps_str = ";".join(timestamps)
            radiuses_str = ";".join(radiuses)

            async with self._rate_semaphore:
                url = f"{self.osrm_url}/match/v1/driving/{coords_str}"
                params = {
                    'timestamps': timestamps_str,
                    'radiuses': radiuses_str,
                    'steps': 'false',
                    'geometries': 'geojson',
                    'annotations': 'true'
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('code') == 'Ok':
                            return data
                        else:
                            logger.error(f"[OSRM Match] API 오류: {data.get('message', 'Unknown')}")
                    else:
                        logger.error(f"[OSRM Match] HTTP 오류: {response.status_code}")

        except Exception as e:
            logger.error(f"[OSRM Match] 요청 실패: {e}")

        return None

    def _split_trajectory_into_chunks(self, trajectory: List[List[float]], max_size: int = MAX_OSRM_MATCH_COORDINATES) -> List[Tuple[List[List[float]], int]]:
        if len(trajectory) <= max_size:
            return [(trajectory, 0)]

        chunks = []
        overlap = 1
        start_idx = 0

        while start_idx < len(trajectory):
            end_idx = min(start_idx + max_size, len(trajectory))
            chunk = trajectory[start_idx:end_idx]
            chunks.append((chunk, start_idx))
            if end_idx >= len(trajectory):
                break
            start_idx = end_idx - overlap

        return chunks

    def _merge_chunk_results(self, chunk_results: List[Tuple[Dict, int]], total_length: int) -> Optional[Dict]:
        if not chunk_results:
            return None
        if len(chunk_results) == 1:
            return chunk_results[0][0]

        merged = {
            'code': 'Ok',
            'matchings': [],
            'tracepoints': [None] * total_length
        }

        for result, start_idx in chunk_results:
            if not result or result.get('code') != 'Ok':
                continue

            tracepoints = result.get('tracepoints', [])
            for i, tp in enumerate(tracepoints):
                global_idx = start_idx + i
                if global_idx >= total_length:
                    break
                if merged['tracepoints'][global_idx] is not None:
                    continue
                merged['tracepoints'][global_idx] = tp

            merged['matchings'].extend(result.get('matchings', []))

        return merged

    # ========== Result Enhancement ==========

    async def _enhance_matching_result(self, original_trajectory: List[List[float]], osrm_result: Dict) -> List[List[float]]:
        matchings = osrm_result.get('matchings', [])
        tracepoints = osrm_result.get('tracepoints', [])

        if not matchings or not tracepoints:
            return original_trajectory

        enhanced = []
        for i, (orig, tp) in enumerate(zip(original_trajectory, tracepoints)):
            if tp is None:
                corrected = await self._interpolate_unmatched_point(orig, original_trajectory, i, tracepoints)
                enhanced.append(corrected + [1])
            else:
                matched_coord = tp['location']
                gps_lon, gps_lat = orig[0], orig[1]
                osrm_lon, osrm_lat = matched_coord[0], matched_coord[1]
                distance = haversine_distance((gps_lat, gps_lon), (osrm_lat, osrm_lon))

                if distance > 50.0:
                    enhanced.append([gps_lon, gps_lat, orig[2], orig[3], orig[4], 4.0])
                else:
                    enhanced.append([matched_coord[0], matched_coord[1], orig[2], orig[3], orig[4], 0])

        return enhanced

    async def _interpolate_unmatched_point(self, unmatched, trajectory, index, tracepoints) -> List[float]:
        prev_matched = None
        next_matched = None

        for i in range(index - 1, -1, -1):
            if tracepoints[i] is not None:
                prev_matched = (i, tracepoints[i])
                break

        for i in range(index + 1, len(tracepoints)):
            if tracepoints[i] is not None:
                next_matched = (i, tracepoints[i])
                break

        if prev_matched and next_matched:
            prev_idx, prev_trace = prev_matched
            next_idx, next_trace = next_matched
            time_ratio = (index - prev_idx) / (next_idx - prev_idx)
            prev_coord = prev_trace['location']
            next_coord = next_trace['location']
            lon = prev_coord[0] + (next_coord[0] - prev_coord[0]) * time_ratio
            lat = prev_coord[1] + (next_coord[1] - prev_coord[1]) * time_ratio
            return [lon, lat, unmatched[2], unmatched[3], unmatched[4]]

        return unmatched[:5]

    def _finalize_result(self, original, enhanced) -> Dict[str, Any]:
        total = len(original)
        matched = sum(1 for p in enhanced if len(p) > 5 and p[5] == 0)
        confidence = matched / total if total > 0 else 0
        shape_score = self._calculate_shape_preservation_score(original, enhanced)

        return {
            "matched_trace": enhanced,
            "summary": {
                "total_points": total,
                "matched_points": matched,
                "confidence": round(confidence, 3),
                "shape_preservation_score": round(shape_score, 3)
            }
        }

    # ========== Low Accuracy Segment Detection ==========

    def _identify_low_accuracy_segments(self, trajectory: List[List[float]], accuracy_threshold: float = 50.0) -> List[Dict]:
        segments = []
        current_segment = None

        for i, point in enumerate(trajectory):
            acc = point[3]
            if acc > accuracy_threshold:
                if not current_segment:
                    current_segment = {'start_idx': i, 'points': [], 'accuracies': []}
                current_segment['points'].append(i)
                current_segment['accuracies'].append(acc)
            else:
                if current_segment:
                    current_segment['end_idx'] = current_segment['points'][-1]
                    current_segment['avg_accuracy'] = sum(current_segment['accuracies']) / len(current_segment['accuracies'])
                    current_segment['needs_correction'] = True
                    segments.append(current_segment)
                    current_segment = None

        if current_segment:
            current_segment['end_idx'] = current_segment['points'][-1]
            current_segment['avg_accuracy'] = sum(current_segment['accuracies']) / len(current_segment['accuracies'])
            current_segment['needs_correction'] = True
            segments.append(current_segment)

        return segments

    # ========== Route Alternatives ==========

    async def _get_route_alternatives_for_segment(
        self,
        waypoints: List[List[float]],
        num_alternatives: int = 3,
        waypoint_radiuses: Optional[List[float]] = None,
        waypoint_bearings: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        if len(waypoints) < 2:
            return []

        # 중복 waypoints 제거
        unique_waypoints = [waypoints[0]]
        unique_radiuses = [waypoint_radiuses[0]] if waypoint_radiuses else []
        unique_bearings = [waypoint_bearings[0]] if waypoint_bearings else []

        for i in range(1, len(waypoints)):
            dist = haversine_distance(
                (waypoints[i][1], waypoints[i][0]),
                (unique_waypoints[-1][1], unique_waypoints[-1][0])
            )
            if dist > 10:
                unique_waypoints.append(waypoints[i])
                if waypoint_radiuses and i < len(waypoint_radiuses):
                    unique_radiuses.append(waypoint_radiuses[i])
                if waypoint_bearings and i < len(waypoint_bearings):
                    unique_bearings.append(waypoint_bearings[i])

        if len(unique_waypoints) < 2:
            return []

        coords_str = ";".join([f"{lon},{lat}" for lon, lat in unique_waypoints])
        alternatives = min(num_alternatives, 3)

        try:
            async with self._rate_semaphore:
                url = f"{self.osrm_url}/route/v1/driving/{coords_str}"
                params = {
                    'alternatives': alternatives,
                    'steps': 'false',
                    'geometries': 'geojson',
                    'overview': 'full',
                    'continue_straight': 'false'
                }

                if unique_radiuses and len(unique_radiuses) == len(unique_waypoints):
                    params['radiuses'] = ";".join([str(int(r)) for r in unique_radiuses])

                if unique_bearings and len(unique_bearings) == len(unique_waypoints):
                    bearings_parts = []
                    for b in unique_bearings:
                        if b is not None:
                            bearings_parts.append(f"{int(b)},45")
                        else:
                            bearings_parts.append("")
                    params['bearings'] = ";".join(bearings_parts)

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('code') != 'Ok':
                            return []

                        routes = []
                        for route in data.get('routes', []):
                            geometry = route.get('geometry', {}).get('coordinates', [])
                            routes.append({
                                'geometry': geometry,
                                'distance': route.get('distance', 0),
                                'duration': route.get('duration', 0)
                            })
                        return routes

        except Exception as e:
            logger.error(f"[Route Alternatives] 경로 생성 실패: {e}")

        return []

    # ========== GPS to Route Projection ==========

    def _project_gps_to_route(
        self, gps_segment, route_geometry, segment_info,
        start_anchor_idx=None, end_anchor_idx=None,
        enable_debug=False, debug_info=None
    ) -> List[Dict]:
        corrected_points = []

        start_anchor_ts = None
        end_anchor_ts = None
        if start_anchor_idx is not None and start_anchor_idx < len(gps_segment):
            start_anchor_ts = gps_segment[start_anchor_idx][2]
        if end_anchor_idx is not None and end_anchor_idx < len(gps_segment):
            end_anchor_ts = gps_segment[end_anchor_idx][2]

        prev_corrected = None
        prev_gps_point = None

        for idx in segment_info['points']:
            if idx >= len(gps_segment):
                continue

            gps_point = gps_segment[idx]
            if len(gps_point) < 5:
                continue

            lon, lat, ts, acc, spd = gps_point[:5]

            # 경로에서 가장 가까운 점 찾기
            closest_point = None
            min_distance = float('inf')

            for i in range(len(route_geometry) - 1):
                p1 = route_geometry[i]
                p2 = route_geometry[i + 1]
                projected = self._project_point_to_segment([lon, lat], p1, p2)
                dist = haversine_distance((lat, lon), (projected[1], projected[0]))
                if dist < min_distance:
                    min_distance = dist
                    closest_point = projected

            # 경로에서 500m 이상 떨어진 경우 시간 기반 보간
            if min_distance > 500 and start_anchor_ts and end_anchor_ts:
                time_ratio = (ts - start_anchor_ts) / (end_anchor_ts - start_anchor_ts) if (end_anchor_ts - start_anchor_ts) > 0 else 0.5
                route_point = self._interpolate_on_route(route_geometry, time_ratio)
                current_corrected = {
                    'idx': idx,
                    'corrected': [route_point[0], route_point[1], ts, acc, spd, 0.5]
                }
            elif closest_point:
                current_corrected = {
                    'idx': idx,
                    'corrected': [closest_point[0], closest_point[1], ts, acc, spd, 0.5]
                }
            else:
                continue

            # 중간 포인트 삽입
            if prev_corrected is not None and prev_gps_point is not None:
                original_distance = haversine_distance(
                    (prev_gps_point[1], prev_gps_point[0]),
                    (lat, lon)
                )

                if original_distance >= 500:
                    is_tunnel = False
                    avg_accuracy = (prev_gps_point[3] + gps_point[3]) / 2
                    if avg_accuracy >= 150:
                        is_tunnel = True

                    if not is_tunnel and (not route_geometry or len(route_geometry) <= 200):
                        self._insert_intermediate_points(
                            corrected_points, prev_corrected, current_corrected, route_geometry
                        )

            corrected_points.append(current_corrected)
            prev_corrected = current_corrected
            prev_gps_point = gps_point

        return corrected_points

    def _project_point_to_segment(self, point, seg_start, seg_end) -> List[float]:
        px, py = point
        x1, y1 = seg_start
        x2, y2 = seg_end

        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            return seg_start

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))

        return [x1 + t * dx, y1 + t * dy]

    # ========== Intermediate Points ==========

    def _insert_intermediate_points(self, corrected_points, prev_point, curr_point, route_geometry=None):
        prev_coord = prev_point['corrected']
        curr_coord = curr_point['corrected']

        prev_ts = prev_coord[2]
        curr_ts = curr_coord[2]
        time_diff = curr_ts - prev_ts

        if time_diff <= 0:
            return

        distance = haversine_distance(
            (prev_coord[1], prev_coord[0]),
            (curr_coord[1], curr_coord[0])
        )

        use_route = route_geometry is not None and len(route_geometry) > 1

        if use_route:
            sub_geometry = self._extract_sub_geometry(
                route_geometry,
                (prev_coord[1], prev_coord[0]),
                (curr_coord[1], curr_coord[0])
            )
            route_geometry = sub_geometry
            use_route = len(route_geometry) > 1

        if use_route:
            prev_pos = self._find_position_on_route(route_geometry, (prev_coord[1], prev_coord[0]))
            curr_pos = self._find_position_on_route(route_geometry, (curr_coord[1], curr_coord[0]))

            turning_points = self._find_turning_points_on_route(route_geometry, prev_pos, curr_pos)

            num_distance_based = max(1, int(distance / 500))
            num_distance_based = min(num_distance_based, 10)

            target_positions = []
            for i in range(1, num_distance_based + 1):
                ratio = i / (num_distance_based + 1)
                pos = prev_pos + (curr_pos - prev_pos) * ratio
                target_positions.append(pos)

            for turn_pos in turning_points:
                too_close = any(abs(turn_pos - ep) < 50 for ep in target_positions)
                if not too_close:
                    target_positions.append(turn_pos)

            target_positions.sort()
            target_positions = target_positions[:15]

            for target_pos in target_positions:
                ratio = (target_pos - prev_pos) / (curr_pos - prev_pos) if (curr_pos - prev_pos) != 0 else 0.5
                ratio = max(0, min(1, ratio))

                route_point = self._get_point_at_position(route_geometry, target_pos)

                corrected_points.append({
                    'idx': -1,
                    'corrected': [
                        route_point[0], route_point[1],
                        int(prev_ts + time_diff * ratio),
                        (prev_coord[3] + curr_coord[3]) / 2,
                        (prev_coord[4] + curr_coord[4]) / 2,
                        2.0
                    ]
                })
        else:
            num_intermediate = max(1, int(distance / 500))
            num_intermediate = min(num_intermediate, 10)

            for i in range(1, num_intermediate + 1):
                ratio = i / (num_intermediate + 1)
                corrected_points.append({
                    'idx': -1,
                    'corrected': [
                        prev_coord[0] + (curr_coord[0] - prev_coord[0]) * ratio,
                        prev_coord[1] + (curr_coord[1] - prev_coord[1]) * ratio,
                        int(prev_ts + time_diff * ratio),
                        (prev_coord[3] + curr_coord[3]) / 2,
                        (prev_coord[4] + curr_coord[4]) / 2,
                        2.0
                    ]
                })

    # ========== Route Geometry Utilities ==========

    def _extract_sub_geometry(self, route_geometry, start_point, end_point) -> List[List[float]]:
        if not route_geometry or len(route_geometry) < 2:
            return route_geometry

        start_pos = self._find_position_on_route(route_geometry, start_point)
        end_pos = self._find_position_on_route(route_geometry, end_point)

        if start_pos > end_pos:
            start_pos, end_pos = end_pos, start_pos

        sub_geometry = []
        accumulated = 0.0
        started = False

        for i in range(len(route_geometry) - 1):
            p1 = route_geometry[i]
            p2 = route_geometry[i + 1]
            seg_len = haversine_distance((p1[1], p1[0]), (p2[1], p2[0]))
            next_dist = accumulated + seg_len

            if not started and next_dist >= start_pos:
                started = True
                if accumulated < start_pos and seg_len > 0:
                    ratio = (start_pos - accumulated) / seg_len
                    sub_geometry.append([
                        p1[0] + (p2[0] - p1[0]) * ratio,
                        p1[1] + (p2[1] - p1[1]) * ratio
                    ])
                else:
                    sub_geometry.append(p1)

            if started:
                sub_geometry.append(p2)
                if next_dist >= end_pos:
                    if accumulated < end_pos < next_dist and seg_len > 0:
                        ratio = (end_pos - accumulated) / seg_len
                        sub_geometry[-1] = [
                            p1[0] + (p2[0] - p1[0]) * ratio,
                            p1[1] + (p2[1] - p1[1]) * ratio
                        ]
                    break

            accumulated = next_dist

        if len(sub_geometry) < 2:
            return route_geometry
        return sub_geometry

    def _find_position_on_route(self, route_geometry, point) -> float:
        if not route_geometry or len(route_geometry) < 2:
            return 0.0

        min_distance = float('inf')
        best_position = 0.0
        accumulated = 0.0

        for i in range(len(route_geometry) - 1):
            p1 = route_geometry[i]
            p2 = route_geometry[i + 1]
            seg_len = haversine_distance((p1[1], p1[0]), (p2[1], p2[0]))

            projected = self._project_point_to_segment([point[1], point[0]], p1, p2)
            dist = haversine_distance(point, (projected[1], projected[0]))

            if dist < min_distance:
                min_distance = dist
                dist_in_seg = haversine_distance((p1[1], p1[0]), (projected[1], projected[0]))
                best_position = accumulated + dist_in_seg

            accumulated += seg_len

        return best_position

    def _get_point_at_position(self, route_geometry, position: float) -> List[float]:
        if not route_geometry or len(route_geometry) < 2:
            return route_geometry[0] if route_geometry else [0, 0]

        if position <= 0:
            return route_geometry[0]

        accumulated = 0.0
        for i in range(len(route_geometry) - 1):
            p1 = route_geometry[i]
            p2 = route_geometry[i + 1]
            seg_len = haversine_distance((p1[1], p1[0]), (p2[1], p2[0]))

            if accumulated + seg_len >= position:
                remaining = position - accumulated
                ratio = remaining / seg_len if seg_len > 0 else 0
                return [
                    p1[0] + (p2[0] - p1[0]) * ratio,
                    p1[1] + (p2[1] - p1[1]) * ratio
                ]
            accumulated += seg_len

        return route_geometry[-1]

    def _find_turning_points_on_route(self, route_geometry, start_pos, end_pos, min_angle_change=30.0) -> List[float]:
        if not route_geometry or len(route_geometry) < 3:
            return []

        if start_pos > end_pos:
            start_pos, end_pos = end_pos, start_pos

        turning_points = []
        accumulated = 0.0

        for i in range(len(route_geometry) - 2):
            p1 = route_geometry[i]
            p2 = route_geometry[i + 1]
            p3 = route_geometry[i + 2]

            seg_len = haversine_distance((p1[1], p1[0]), (p2[1], p2[0]))
            current_pos = accumulated + seg_len

            if start_pos <= current_pos <= end_pos:
                bearing1 = calculate_bearing((p1[1], p1[0]), (p2[1], p2[0]))
                bearing2 = calculate_bearing((p2[1], p2[0]), (p3[1], p3[0]))
                angle_change = abs(bearing2 - bearing1)
                angle_change = min(angle_change, 360 - angle_change)

                if angle_change >= min_angle_change:
                    turning_points.append(current_pos)

            accumulated += seg_len

        return turning_points

    # ========== Nearest API Fallback ==========

    async def _correct_points_with_nearest(self, trajectory_data, segment, batch_size=25) -> List[Dict]:
        corrected_points = []
        segment_points = segment['points']

        for batch_start in range(0, len(segment_points), batch_size):
            batch_end = min(batch_start + batch_size, len(segment_points))
            batch_indices = segment_points[batch_start:batch_end]

            tasks = []
            for idx in batch_indices:
                gps_point = trajectory_data[idx]
                lon, lat, ts, acc, spd = gps_point[:5]
                tasks.append({
                    'idx': idx,
                    'task': self._get_nearest_road(lon, lat),
                    'original': [lon, lat, ts, acc, spd]
                })

            results = await asyncio.gather(*[t['task'] for t in tasks], return_exceptions=True)

            for task_info, nearest_result in zip(tasks, results):
                if isinstance(nearest_result, Exception):
                    continue
                if nearest_result:
                    snapped_lon, snapped_lat = nearest_result['location']
                    original = task_info['original']
                    corrected_points.append({
                        'idx': task_info['idx'],
                        'corrected': [snapped_lon, snapped_lat, original[2], original[3], original[4], 0.5]
                    })

        return corrected_points

    async def _get_nearest_road(self, lon: float, lat: float, number: int = 1) -> Optional[Dict]:
        try:
            async with self._rate_semaphore:
                url = f"{self.osrm_url}/nearest/v1/driving/{lon},{lat}"
                params = {'number': number}

                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('code') == 'Ok' and data.get('waypoints'):
                            wp = data['waypoints'][0]
                            return {
                                'location': wp['location'],
                                'distance': wp.get('distance', 0),
                                'name': wp.get('name', '')
                            }
        except Exception as e:
            logger.error(f"[Nearest API] 오류: {e}")
        return None

    # ========== Tunnel Detection ==========

    def _detect_tunnel_usage(self, trajectory_data, segment, expanded_start, expanded_end) -> Optional[Dict]:
        TUNNELS = [
            {
                'name': '신월여의지하도로',
                'entry': {'lat': 37.526, 'lon': 126.835, 'radius': 600},
                'exit': {'lat': 37.522, 'lon': 126.920, 'radius': 600},
                'min_duration': 120,
                'min_distance': 2000,
                'waypoints': [
                    [126.8392, 37.5262], [126.860, 37.525],
                    [126.880, 37.524], [126.900, 37.523], [126.920, 37.522]
                ],
                'bearings': [90, 90, 90, 90, 90]
            },
            {
                'name': '강변북로 지하차도',
                'entry': {'lat': 37.538, 'lon': 127.003, 'radius': 400},
                'exit': {'lat': 37.540, 'lon': 127.020, 'radius': 400},
                'min_duration': 90,
                'min_distance': 1000,
                'waypoints': [
                    [127.003, 37.538], [127.010, 37.539], [127.020, 37.540]
                ],
                'bearings': [80, 80, 80]
            },
            {
                'name': '남한산성터널',
                'entry': {'lat': 37.442, 'lon': 127.142, 'radius': 800},
                'exit': {'lat': 37.541, 'lon': 127.211, 'radius': 800},
                'min_duration': 240,
                'min_distance': 7000,
                'waypoints': [
                    [127.142, 37.442], [127.152, 37.460],
                    [127.162, 37.478], [127.172, 37.496],
                    [127.182, 37.514], [127.192, 37.527], [127.211, 37.541]
                ],
                'bearings': [30, 30, 30, 30, 30, 30, 30]
            }
        ]

        segment_points = [trajectory_data[idx] for idx in segment['points']]
        if len(segment_points) < 2:
            return None

        start_point = segment_points[0]
        end_point = segment_points[-1]
        duration = end_point[2] - start_point[2]

        total_distance = 0
        for i in range(len(segment_points) - 1):
            total_distance += haversine_distance(
                (segment_points[i][1], segment_points[i][0]),
                (segment_points[i+1][1], segment_points[i+1][0])
            )

        very_low_acc_count = sum(1 for pt in segment_points if pt[3] > 100)
        very_low_acc_ratio = very_low_acc_count / len(segment_points)

        for tunnel in TUNNELS:
            has_entry = False
            has_exit = False

            for i in range(expanded_start, min(expanded_end, len(trajectory_data))):
                pt = trajectory_data[i]
                entry_dist = haversine_distance(
                    (pt[1], pt[0]), (tunnel['entry']['lat'], tunnel['entry']['lon'])
                )
                if entry_dist <= tunnel['entry']['radius']:
                    has_entry = True

                exit_dist = haversine_distance(
                    (pt[1], pt[0]), (tunnel['exit']['lat'], tunnel['exit']['lon'])
                )
                if exit_dist <= tunnel['exit']['radius']:
                    has_exit = True

            if (has_entry and has_exit and
                duration >= tunnel['min_duration'] and
                total_distance >= tunnel['min_distance'] and
                very_low_acc_ratio >= 0.4):

                logger.info(f"터널 감지: {tunnel['name']}")
                return {
                    'tunnel': tunnel,
                    'has_entry': has_entry,
                    'has_exit': has_exit,
                    'duration': duration,
                    'distance': total_distance
                }

        return None

    # ========== Edge Continuity Check ==========

    def _check_edge_continuity(self, trajectory: List[List]) -> List[List]:
        if len(trajectory) < 3:
            return trajectory

        angle_threshold = 90
        corrected = trajectory.copy()

        for i in range(1, len(trajectory) - 1):
            prev_point = trajectory[i - 1]
            curr_point = trajectory[i]
            next_point = trajectory[i + 1]

            curr_flag = curr_point[3] if len(curr_point) > 3 else 0
            if curr_flag not in [0.5, 1.0]:
                continue

            try:
                bearing1 = calculate_bearing((prev_point[1], prev_point[0]), (curr_point[1], curr_point[0]))
                bearing2 = calculate_bearing((curr_point[1], curr_point[0]), (next_point[1], next_point[0]))
                angle_change = abs(bearing2 - bearing1)
                angle_change = min(angle_change, 360 - angle_change)

                if angle_change > angle_threshold:
                    dist1 = haversine_distance((prev_point[1], prev_point[0]), (curr_point[1], curr_point[0]))
                    dist2 = haversine_distance((curr_point[1], curr_point[0]), (next_point[1], next_point[0]))

                    if dist1 < 200 or dist2 < 200:
                        avg_lon = (prev_point[0] + next_point[0]) / 2
                        avg_lat = (prev_point[1] + next_point[1]) / 2

                        corrected[i] = [
                            avg_lon, avg_lat,
                            curr_point[2] if len(curr_point) > 2 else 0,
                            0.5,
                            curr_point[4] if len(curr_point) > 4 else 0,
                            curr_point[5] if len(curr_point) > 5 else 0,
                            3.0
                        ]
            except Exception:
                continue

        return corrected

    # ========== Shape Preservation ==========

    def _calculate_shape_preservation_score(self, original, matched) -> float:
        if len(original) < 3 or len(matched) < 3:
            return 1.0

        try:
            bearing_similarities = []
            for i in range(min(len(original), len(matched)) - 1):
                orig_b = calculate_bearing((original[i][1], original[i][0]), (original[i+1][1], original[i+1][0]))
                match_b = calculate_bearing((matched[i][1], matched[i][0]), (matched[i+1][1], matched[i+1][0]))
                diff = abs(orig_b - match_b)
                diff = min(diff, 360 - diff)
                bearing_similarities.append(1.0 - (diff / 180.0))

            return sum(bearing_similarities) / len(bearing_similarities) if bearing_similarities else 1.0
        except Exception:
            return 1.0

    def _calculate_shape_similarity(self, gps_points, route_geometry) -> float:
        if not gps_points or not route_geometry:
            return 0.0

        total_distance = 0
        for gps_point in gps_points:
            min_dist = float('inf')
            for route_point in route_geometry:
                dist = haversine_distance(
                    (gps_point[1], gps_point[0]),
                    (route_point[1], route_point[0])
                )
                min_dist = min(min_dist, dist)
            total_distance += min_dist

        avg_distance = total_distance / len(gps_points)
        return max(0, 1 - (avg_distance / 500))

    # ========== Helpers ==========

    def _create_empty_result(self) -> Dict[str, Any]:
        return {
            "matched_trace": [],
            "summary": {
                "total_points": 0,
                "matched_points": 0,
                "confidence": 0.0,
                "shape_preservation_score": 0.0
            }
        }

    def _create_fallback_result(self, trajectory: List[List[float]]) -> Dict[str, Any]:
        fallback_trace = [point[:5] + [1] for point in trajectory]
        return {
            "matched_trace": fallback_trace,
            "summary": {
                "total_points": len(trajectory),
                "matched_points": 0,
                "confidence": 0.0,
                "shape_preservation_score": 1.0
            }
        }

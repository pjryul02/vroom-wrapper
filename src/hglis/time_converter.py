"""
HGLIS C3 시간윈도우 변환

희망배송시간 → VROOM time_windows (Unix timestamp)

시간대 매핑 (±60분 버퍼):
  오전1:    08:00~12:00 → 허용 07:00~13:00
  오후1:    12:00~16:00 → 허용 11:00~17:00
  오후2:    16:00~19:00 → 허용 15:00~20:00
  오후3:    19:00~23:59 → 허용 18:00~24:59
  하루종일: 08:00~23:59 (버퍼 없음)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
from zoneinfo import ZoneInfo
from .models import HglisJob, HglisVehicle

KST = ZoneInfo("Asia/Seoul")

logger = logging.getLogger(__name__)

BUFFER_MINUTES = 60

# 시간대 → (시작, 종료) 시:분
TIME_SLOTS: Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]] = {
    "오전1":    ((8, 0), (12, 0)),
    "오후1":    ((12, 0), (16, 0)),
    "오후2":    ((16, 0), (19, 0)),
    "오후3":    ((19, 0), (23, 59)),
    "하루종일": ((8, 0), (23, 59)),
}

# 기본 근무 시간
DEFAULT_WORK_START = (8, 0)
DEFAULT_WORK_END = (23, 59)

# 기본 체류 시간 (양중15 + 마무리10)
BASE_STAY_MINUTES = 25


def _to_unix(base_date: str, hour: int, minute: int) -> int:
    """날짜 + 시분 → Unix timestamp (KST 고정)"""
    dt = datetime.strptime(base_date, "%Y-%m-%d").replace(tzinfo=KST)
    dt = dt.replace(hour=min(hour, 23), minute=min(minute, 59))
    # 24:59 같은 경우 → 다음날 00:59
    if hour >= 24:
        dt = dt.replace(hour=0, minute=minute) + timedelta(days=1)
    return int(dt.timestamp())


def _parse_hhmm(time_str: str) -> Tuple[int, int]:
    """HH:MM 문자열 → (시, 분)"""
    parts = time_str.strip().split(":")
    return int(parts[0]), int(parts[1])


def convert_job_time_windows(
    job: HglisJob,
    base_date: str,
) -> List[List[int]]:
    """
    오더의 희망배송시간 → VROOM time_windows

    Returns: [[unix_start, unix_end]]
    """
    slot = job.scheduling.preferred_time_slot

    if slot not in TIME_SLOTS:
        raise ValueError(f"유효하지 않은 시간대: {slot}")

    (start_h, start_m), (end_h, end_m) = TIME_SLOTS[slot]

    if slot == "하루종일":
        # 버퍼 없음
        tw_start = _to_unix(base_date, start_h, start_m)
        tw_end = _to_unix(base_date, end_h, end_m)
    else:
        # ±60분 버퍼 (KST 고정)
        buf_start = datetime.strptime(base_date, "%Y-%m-%d").replace(
            hour=start_h, minute=start_m, tzinfo=KST
        ) - timedelta(minutes=BUFFER_MINUTES)
        buf_end = datetime.strptime(base_date, "%Y-%m-%d").replace(
            hour=min(end_h, 23), minute=end_m, tzinfo=KST
        ) + timedelta(minutes=BUFFER_MINUTES)

        tw_start = int(buf_start.timestamp())
        tw_end = int(buf_end.timestamp())

    return [[tw_start, tw_end]]


def convert_vehicle_time_window(
    vehicle: HglisVehicle,
    base_date: str,
) -> List[int]:
    """
    기사 근무시간 → VROOM time_window

    Returns: [unix_start, unix_end]
    """
    start_h, start_m = DEFAULT_WORK_START
    tw_start = _to_unix(base_date, start_h, start_m)

    # 종료 시간
    if vehicle.work_time and vehicle.work_time.end:
        end_h, end_m = _parse_hhmm(vehicle.work_time.end)
    else:
        end_h, end_m = DEFAULT_WORK_END

    tw_end = _to_unix(base_date, end_h, end_m)

    return [tw_start, tw_end]


def convert_vehicle_breaks(
    vehicle: HglisVehicle,
    base_date: str,
) -> Optional[List[Dict]]:
    """
    기사 휴게 시간 → VROOM breaks

    Returns: [{"time_windows": [[start, end]], "service": 0}]
    """
    if not vehicle.work_time or not vehicle.work_time.breaks:
        return None

    vroom_breaks = []
    for brk in vehicle.work_time.breaks:
        if "start" in brk and "end" in brk:
            bh1, bm1 = _parse_hhmm(brk["start"])
            bh2, bm2 = _parse_hhmm(brk["end"])
            b_start = _to_unix(base_date, bh1, bm1)
            b_end = _to_unix(base_date, bh2, bm2)
            duration = b_end - b_start
            vroom_breaks.append({
                "time_windows": [[b_start, b_end]],
                "service": max(duration, 0),
            })

    return vroom_breaks if vroom_breaks else None


def calc_service_seconds(job: HglisJob) -> int:
    """
    오더 서비스 시간 계산 (초 단위)

    service = (설치 소요 시간 + 기본 체류 25분) * 60
    """
    service_min = job.scheduling.service_minutes + BASE_STAY_MINUTES
    return service_min * 60


def calc_setup_seconds(job: HglisJob) -> Optional[int]:
    """setup 시간 (옵션, 초 단위)"""
    if job.scheduling.setup_minutes:
        return job.scheduling.setup_minutes * 60
    return None

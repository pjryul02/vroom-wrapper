"""
HGLIS /dispatch 건수별 처리시간 벤치마크
"""
import json
import time
import requests
from datetime import date

API_URL = "http://localhost:8000/dispatch"
API_KEY = "demo-key-12345"

TODAY = date.today().isoformat()

# 서울/수도권 좌표 풀
JOB_LOCS = [
    [127.0500, 37.5172], [126.9302, 37.4846], [127.0276, 37.4979],
    [127.0590, 37.5120], [127.0627, 37.4946], [127.0082, 37.4920],
    [127.0857, 37.5110], [126.9721, 37.6100], [127.0010, 37.5340],
    [126.8826, 37.4810], [127.0367, 37.5615], [126.8580, 37.5020],
    [127.1110, 37.3940], [127.0980, 37.3218], [126.7698, 37.6584],
    [126.8927, 37.6410], [126.7560, 37.7130], [126.7245, 37.6348],
    [127.2020, 37.3630], [127.1540, 37.5580], [126.6470, 37.5260],
    [127.0364, 37.5010], [127.0130, 37.5137], [127.0594, 37.6560],
    [126.8381, 37.5614], [127.0450, 37.5050], [126.9800, 37.5200],
    [127.0300, 37.4800], [126.9500, 37.5400], [127.1000, 37.5000],
]

CENTER = [127.0276, 37.4979]  # 강남 물류센터

HOME_LOCS = [
    [127.0500, 37.6000], [126.9000, 37.5500], [127.1000, 37.4500],
    [126.8500, 37.6500], [127.0800, 37.3800], [126.7500, 37.5000],
    [127.1500, 37.6000], [126.9500, 37.4000],
]

PRODUCTS = [
    {"model_code": "SF-001", "model_name": "소파 3인용",   "cbm": 3.0, "fee": 120000, "required_grade": "B", "quantity": 1, "is_new_product": False, "is_sofa": True},
    {"model_code": "BD-001", "model_name": "침대 퀸사이즈", "cbm": 3.0, "fee": 120000, "required_grade": "B", "quantity": 1, "is_new_product": False, "is_sofa": False},
    {"model_code": "WD-001", "model_name": "옷장 3도어",   "cbm": 3.5, "fee": 130000, "required_grade": "A", "quantity": 1, "is_new_product": False, "is_sofa": False},
    {"model_code": "DT-001", "model_name": "식탁 6인용",   "cbm": 2.0, "fee": 80000,  "required_grade": "B", "quantity": 1, "is_new_product": False, "is_sofa": False},
    {"model_code": "DS-001", "model_name": "서랍장 5단",   "cbm": 1.2, "fee": 50000,  "required_grade": "C", "quantity": 1, "is_new_product": False, "is_sofa": False},
]

SLOTS = ["오전1", "오전1", "오후1", "오후1", "오후2", "오후3", "하루종일"]
GRADES = ["A", "A", "B", "B", "B", "C", "C"]


def make_job(i: int) -> dict:
    loc = JOB_LOCS[i % len(JOB_LOCS)]
    prod = PRODUCTS[i % len(PRODUCTS)]
    slot = SLOTS[i % len(SLOTS)]
    crew = "2인" if i % 5 == 0 else "any"
    return {
        "id": i + 1,
        "order_id": f"ORD-{i+1:04d}",
        "location": loc,
        "region_code": "Y1",
        "products": [prod],
        "scheduling": {"preferred_time_slot": slot, "service_minutes": 45},
        "constraints": {"crew_type": crew},
        "priority": {"level": 0, "is_urgent": False, "is_vip": False},
    }


def make_vehicle(i: int, crew_size: int = 1) -> dict:
    home = HOME_LOCS[i % len(HOME_LOCS)]
    grade = GRADES[i % len(GRADES)]
    return {
        "id": i + 1,
        "driver_id": f"DRV-{i+1:03d}",
        "driver_name": f"기사{i+1}",
        "grade": grade,
        "service_grade": grade if grade != "C" else "B",
        "capacity_cbm": 12.0,
        "location": {
            "center": CENTER, "home": home,
            "start": CENTER, "end": home,
        },
        "region_code": "Y1",
        "crew": {"size": crew_size, "is_filler": False, "can_joint_dispatch": False},
        "new_product_restricted": False,
        "avoid_models": [],
        "fee_status": {"monthly_accumulated": 0},
    }


def build_payload(n_jobs: int, n_vehicles: int) -> dict:
    jobs = [make_job(i) for i in range(n_jobs)]
    # 2인팀 비율 20%
    vehicles = []
    for i in range(n_vehicles):
        size = 2 if i % 5 == 0 else 1
        vehicles.append(make_vehicle(i, size))
    return {
        "meta": {"date": TODAY, "region_mode": "strict"},
        "jobs": jobs,
        "vehicles": vehicles,
        "options": {
            "max_tasks_per_driver": 12,
            "geometry": False,
            "constraints": {"C1": True, "C2": False, "C3": True, "C4": True, "C5": True, "C6": False},
        },
    }


SCENARIOS = [
    (10,   4),
    (25,   8),
    (50,  15),
    (100, 25),
    (200, 45),
    (300, 60),
    (500, 100),
]

print(f"{'건수':>6} {'차량':>6} {'소요(s)':>10} {'배정':>8} {'미배정':>8} {'배정률':>8}")
print("-" * 55)

for n_jobs, n_vehicles in SCENARIOS:
    payload = build_payload(n_jobs, n_vehicles)
    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}

    t0 = time.time()
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=600)
        elapsed = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            assigned = data.get("statistics", {}).get("assigned_orders", "?")
            unassigned = data.get("statistics", {}).get("unassigned_orders", "?")
            rate = data.get("statistics", {}).get("assignment_rate", 0)
            print(f"{n_jobs:>6} {n_vehicles:>6} {elapsed:>10.1f} {assigned:>8} {unassigned:>8} {rate:>7.1f}%")
        else:
            print(f"{n_jobs:>6} {n_vehicles:>6} {elapsed:>10.1f}  ERROR {resp.status_code}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"{n_jobs:>6} {n_vehicles:>6} {elapsed:>10.1f}  EXCEPTION: {e}")

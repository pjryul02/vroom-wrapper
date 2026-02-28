#!/usr/bin/env python3
"""
HGLIS 배차 엣지케이스 테스트

각 제약조건별 독립 검증:
  Test 1: C3 시간대 — 오전1 vs 오후3 기사, 시간 미매칭 검증
  Test 2: C4 기능도 — S급 오더 + C급 기사만 → 미배정
  Test 3: C5 CBM — 과다 용량 오더 → 미배정
  Test 4: C7 신제품 — restricted 기사 → 미배정
  Test 5: C8 미결이력 — 회피 모델 → 미배정
  Test 6: 소파 — Y1 기사만(W1/지방 없음) → 미배정
  Test 7: 정상 기본 — 모든 제약 충족 → 100% 배정
"""

import httpx
import json
import sys

API = "http://localhost:8000"
HEADERS = {"X-API-Key": "demo-key-12345", "Content-Type": "application/json"}

# 기본 위치 (서울역 근처)
LOC_SEOUL = [126.972, 37.555]
LOC_WAREHOUSE = [127.05, 37.50]


def make_job(id, order_id, **kwargs):
    """기본 job 생성 헬퍼"""
    base = {
        "id": id,
        "order_id": order_id,
        "location": kwargs.pop("location", LOC_SEOUL),
        "region_code": kwargs.pop("region_code", "Y1"),
        "products": kwargs.pop("products", [{
            "model_code": "STD-001",
            "cbm": 1.0,
            "fee": 50000,
            "required_grade": "C",
        }]),
        "scheduling": kwargs.pop("scheduling", {
            "preferred_time_slot": "하루종일",
            "service_minutes": 30,
        }),
    }
    base.update(kwargs)
    return base


def make_vehicle(id, driver_id, **kwargs):
    """기본 vehicle 생성 헬퍼"""
    base = {
        "id": id,
        "driver_id": driver_id,
        "driver_name": kwargs.pop("driver_name", f"기사{id}"),
        "skill_grade": kwargs.pop("skill_grade", "A"),
        "service_grade": kwargs.pop("service_grade", "A"),
        "capacity_cbm": kwargs.pop("capacity_cbm", 15.0),
        "location": kwargs.pop("location", {"start": LOC_WAREHOUSE, "end": LOC_WAREHOUSE}),
        "region_code": kwargs.pop("region_code", "Y1"),
        "crew": kwargs.pop("crew", {"size": 1, "is_filler": False}),
    }
    base.update(kwargs)
    return base


def make_request(jobs, vehicles, **kwargs):
    """기본 request 생성"""
    return {
        "meta": kwargs.pop("meta", {"date": "2026-02-28", "region_mode": "ignore"}),
        "jobs": jobs,
        "vehicles": vehicles,
        "options": kwargs.pop("options", {"max_tasks_per_driver": 12, "geometry": False}),
    }


def dispatch(payload):
    """dispatch API 호출"""
    r = httpx.post(f"{API}/dispatch", json=payload, headers=HEADERS, timeout=60)
    return r.json()


def test_c4_grade_mismatch():
    """C4: S급 오더 + C급 기사만 → 미배정 (skill 4 요구, 기사는 skill 1만)"""
    print("\n=== Test C4: 기능도 미매칭 ===")
    jobs = [make_job(1, "ORD-C4-1", products=[{
        "model_code": "HIGH-001",
        "cbm": 1.0,
        "fee": 80000,
        "required_grade": "S",  # S급 필요
    }])]
    vehicles = [make_vehicle(1, "DRV-C4-1", skill_grade="C")]  # C급만 보유

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])

    print(f"  배정: {assigned}, 미배정: {len(unassigned)}")
    if unassigned:
        print(f"  미배정 사유: {unassigned[0].get('constraint', '?')}")

    assert assigned == 0, f"C4: S급 오더가 C급 기사에 배정됨!"
    assert len(unassigned) == 1
    assert unassigned[0]["constraint"] == "C4_기능도"
    print("  ✓ PASS")


def test_c5_cbm_overflow():
    """C5: 오더 CBM 합 > 기사 용량 → 미배정"""
    print("\n=== Test C5: CBM 초과 ===")
    jobs = [make_job(1, "ORD-C5-1", products=[{
        "model_code": "BIG-001",
        "cbm": 20.0,  # 20 CBM
        "fee": 100000,
        "required_grade": "C",
    }])]
    vehicles = [make_vehicle(1, "DRV-C5-1", capacity_cbm=5.0)]  # 5 CBM만 가능

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])

    print(f"  배정: {assigned}, 미배정: {len(unassigned)}")
    if unassigned:
        print(f"  미배정 사유: {unassigned[0].get('constraint', '?')}")

    assert assigned == 0, f"C5: 20CBM 오더가 5CBM 기사에 배정됨!"
    print("  ✓ PASS")


def test_c7_new_product_restricted():
    """C7: 신제품 오더 + restricted 기사 → 미배정"""
    print("\n=== Test C7: 신제품 제한 ===")
    jobs = [make_job(1, "ORD-C7-1", products=[{
        "model_code": "NEW-X1",
        "cbm": 1.0,
        "fee": 60000,
        "required_grade": "C",
        "is_new_product": True,  # 신제품
    }])]
    vehicles = [make_vehicle(1, "DRV-C7-1", new_product_restricted=True)]  # 신제품 제한

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])

    print(f"  배정: {assigned}, 미배정: {len(unassigned)}")
    if unassigned:
        print(f"  미배정 사유: {unassigned[0].get('constraint', '?')}")

    assert assigned == 0, f"C7: 신제품이 restricted 기사에 배정됨!"
    assert unassigned[0]["constraint"] == "C7_신제품"
    print("  ✓ PASS")


def test_c8_avoid_model():
    """C8: 회피 모델 오더 + 해당 모델 회피 기사 → 미배정"""
    print("\n=== Test C8: 미결이력 회피 ===")
    jobs = [make_job(1, "ORD-C8-1", products=[{
        "model_code": "AVOID-M1",
        "cbm": 1.0,
        "fee": 50000,
        "required_grade": "C",
    }])]
    vehicles = [make_vehicle(1, "DRV-C8-1", avoid_models=[{"model": "AVOID-M1"}])]

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])

    print(f"  배정: {assigned}, 미배정: {len(unassigned)}")
    if unassigned:
        print(f"  미배정 사유: {unassigned[0].get('constraint', '?')}")

    assert assigned == 0, f"C8: 회피 모델이 해당 기사에 배정됨!"
    assert unassigned[0]["constraint"] == "C8_미결이력"
    print("  ✓ PASS")


def test_sofa_no_w1():
    """소파: Y1 기사만 → 소파 오더 미배정"""
    print("\n=== Test 소파: W1/지방 기사 없음 ===")
    jobs = [make_job(1, "ORD-SOFA-1", products=[{
        "model_code": "SOFA-001",
        "cbm": 3.0,
        "fee": 70000,
        "required_grade": "C",
        "is_sofa": True,
    }])]
    vehicles = [make_vehicle(1, "DRV-SOFA-1", region_code="Y1")]  # Y1은 소파 불가

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])

    print(f"  배정: {assigned}, 미배정: {len(unassigned)}")
    if unassigned:
        print(f"  미배정 사유: {unassigned[0].get('constraint', '?')}")

    assert assigned == 0, f"소파: Y1 기사에 소파가 배정됨!"
    assert unassigned[0]["constraint"] == "소파_권역"
    print("  ✓ PASS")


def test_normal_all_assigned():
    """정상: 3개 오더 + 2명 기사 → 전체 배정"""
    print("\n=== Test 정상: 전체 배정 ===")
    jobs = [
        make_job(1, "ORD-N-1"),
        make_job(2, "ORD-N-2", location=[126.98, 37.56]),
        make_job(3, "ORD-N-3", location=[127.01, 37.54]),
    ]
    vehicles = [
        make_vehicle(1, "DRV-N-1"),
        make_vehicle(2, "DRV-N-2"),
    ]

    result = dispatch(make_request(jobs, vehicles))
    assigned = result.get("statistics", {}).get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])
    rate = result.get("statistics", {}).get("assignment_rate", 0)

    print(f"  배정: {assigned}/3, 미배정: {len(unassigned)}, 배정률: {rate}%")
    assert assigned == 3, f"정상: 3개 중 {assigned}개만 배정됨"
    assert rate == 100.0
    print("  ✓ PASS")


def test_c2_fee_warning():
    """C2: 낮은 설치비 → 하한 미달 경고"""
    print("\n=== Test C2: 설치비 하한 경고 ===")
    jobs = [make_job(1, "ORD-C2-1", products=[{
        "model_code": "CHEAP-001",
        "cbm": 1.0,
        "fee": 30000,  # 3만원 — B급 하한 22만보다 훨씬 낮음
        "required_grade": "C",
    }])]
    vehicles = [make_vehicle(1, "DRV-C2-1", skill_grade="B", service_grade="B")]

    result = dispatch(make_request(jobs, vehicles))
    warnings = result.get("warnings", [])
    c2_warnings = [w for w in warnings if w.get("type", "").startswith("C2_")]

    print(f"  전체 경고: {len(warnings)}건, C2: {len(c2_warnings)}건")
    if c2_warnings:
        print(f"  C2 메시지: {c2_warnings[0].get('message', '')[:60]}...")

    assert len(c2_warnings) >= 1, "C2: 하한 미달인데 경고 없음!"
    print("  ✓ PASS")


def test_c6_monthly_cap_warning():
    """C6: 월상한 근접 → 경고"""
    print("\n=== Test C6: 월상한 경고 ===")
    jobs = [make_job(1, "ORD-C6-1", products=[{
        "model_code": "STD-001",
        "cbm": 1.0,
        "fee": 500000,
        "required_grade": "C",
    }])]
    # B등급 월상한 9,000,000원, 이미 8,600,000 누적 → 9,100,000 > 9,000,000 (초과)
    vehicles = [make_vehicle(1, "DRV-C6-1", service_grade="B",
                             fee_status={"monthly_accumulated": 8_600_000})]

    result = dispatch(make_request(jobs, vehicles))
    warnings = result.get("warnings", [])
    c6_warnings = [w for w in warnings if w.get("type", "").startswith("C6_")]

    print(f"  전체 경고: {len(warnings)}건, C6: {len(c6_warnings)}건")
    if c6_warnings:
        print(f"  C6 타입: {c6_warnings[0].get('type', '')}")

    assert len(c6_warnings) >= 1, "C6: 월상한 초과인데 경고 없음!"
    print("  ✓ PASS")


if __name__ == "__main__":
    tests = [
        test_c4_grade_mismatch,
        test_c5_cbm_overflow,
        test_c7_new_product_restricted,
        test_c8_avoid_model,
        test_sofa_no_w1,
        test_normal_all_assigned,
        test_c2_fee_warning,
        test_c6_monthly_cap_warning,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  ✗ ERROR: {e}")

    print(f"\n{'='*50}")
    print(f"결과: {passed} PASS, {failed} FAIL (총 {len(tests)})")
    if errors:
        print("\n실패 목록:")
        for name, msg in errors:
            print(f"  - {name}: {msg}")

    sys.exit(0 if failed == 0 else 1)

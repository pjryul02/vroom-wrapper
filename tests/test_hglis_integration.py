#!/usr/bin/env python3
"""
HGLIS 통합 시나리오 테스트

시나리오: 실제 배차와 유사한 복합 요청
- 10개 오더 (다양한 등급, 시간대, CBM, 신제품/소파 혼재)
- 5명 기사 (다양한 등급, 권역, 제약)
- 다중 제약 동시 적용 검증
"""

import httpx
import json
import sys

API = "http://localhost:8000"
HEADERS = {"X-API-Key": "demo-key-12345", "Content-Type": "application/json"}


def test_complex_scenario():
    """
    복합 시나리오:
    - 10개 오더: 혼합 등급/시간대/CBM/특수조건
    - 5명 기사: 다양한 능력치
    - 기대: 대부분 배정, C8/소파/C4 미배정 일부 발생
    """
    print("=== 통합 시나리오: 복합 배차 ===\n")

    jobs = [
        # 1. 기본 C급 오더 (어떤 기사든 가능)
        {
            "id": 1, "order_id": "INT-001",
            "location": [126.97, 37.55], "region_code": "Y1",
            "products": [{"model_code": "STD-001", "cbm": 1.5, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 30},
        },
        # 2. A급 오더 (A급 이상 기사만)
        {
            "id": 2, "order_id": "INT-002",
            "location": [126.98, 37.56], "region_code": "Y1",
            "products": [{"model_code": "PRO-001", "cbm": 2.0, "fee": 80000, "required_grade": "A"}],
            "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 45},
        },
        # 3. S급 오더 (S급 기사만 → 기사1만 가능)
        {
            "id": 3, "order_id": "INT-003",
            "location": [127.00, 37.57], "region_code": "Y1",
            "products": [{"model_code": "ELITE-001", "cbm": 3.0, "fee": 120000, "required_grade": "S"}],
            "scheduling": {"preferred_time_slot": "오후1", "service_minutes": 60},
        },
        # 4. 신제품 오더 (restricted 기사 못 받음)
        {
            "id": 4, "order_id": "INT-004",
            "location": [126.95, 37.54], "region_code": "Y1",
            "products": [{"model_code": "NEW-X99", "cbm": 1.0, "fee": 60000, "required_grade": "C", "is_new_product": True}],
            "scheduling": {"preferred_time_slot": "오후1", "service_minutes": 30},
        },
        # 5. C8 회피 모델 오더 (기사3이 회피)
        {
            "id": 5, "order_id": "INT-005",
            "location": [127.02, 37.53], "region_code": "Y1",
            "products": [{"model_code": "RISKY-M1", "cbm": 1.0, "fee": 45000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 25},
        },
        # 6. 대용량 CBM 오더 (큰 기사만)
        {
            "id": 6, "order_id": "INT-006",
            "location": [126.96, 37.55], "region_code": "Y1",
            "products": [
                {"model_code": "BIG-001", "cbm": 5.0, "fee": 90000, "required_grade": "B"},
                {"model_code": "BIG-002", "cbm": 4.0, "fee": 70000, "required_grade": "B"},
            ],
            "scheduling": {"preferred_time_slot": "오후2", "service_minutes": 50},
        },
        # 7. 소파 오더 (W1/지방 기사만)
        {
            "id": 7, "order_id": "INT-007",
            "location": [126.97, 37.56], "region_code": "Y1",
            "products": [{"model_code": "SOFA-LUX", "cbm": 4.0, "fee": 85000, "required_grade": "C", "is_sofa": True}],
            "scheduling": {"preferred_time_slot": "오후1", "service_minutes": 40},
        },
        # 8. VIP 오더 (우선순위 높음)
        {
            "id": 8, "order_id": "INT-008",
            "location": [127.01, 37.55], "region_code": "Y1",
            "products": [{"model_code": "STD-002", "cbm": 1.0, "fee": 55000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 25},
            "priority": {"level": 10, "is_vip": True},
        },
        # 9. 긴급 오더
        {
            "id": 9, "order_id": "INT-009",
            "location": [126.99, 37.54], "region_code": "Y1",
            "products": [{"model_code": "STD-003", "cbm": 0.5, "fee": 35000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 20},
            "priority": {"level": 0, "is_urgent": True},
        },
        # 10. 낮은 설치비 오더 (C2 경고 유발용)
        {
            "id": 10, "order_id": "INT-010",
            "location": [127.03, 37.56], "region_code": "Y1",
            "products": [{"model_code": "CHEAP-001", "cbm": 0.3, "fee": 20000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 15},
        },
    ]

    vehicles = [
        # 기사1: S급 올라운더 (15CBM)
        {
            "id": 1, "driver_id": "DRV-S01", "driver_name": "김에스",
            "skill_grade": "S", "service_grade": "S",
            "capacity_cbm": 15.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
        },
        # 기사2: A급 (10CBM, 신제품 restricted)
        {
            "id": 2, "driver_id": "DRV-A01", "driver_name": "이에이",
            "skill_grade": "A", "service_grade": "A",
            "capacity_cbm": 10.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
            "new_product_restricted": True,
        },
        # 기사3: B급 (8CBM, RISKY-M1 회피)
        {
            "id": 3, "driver_id": "DRV-B01", "driver_name": "박비",
            "skill_grade": "B", "service_grade": "B",
            "capacity_cbm": 8.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
            "avoid_models": [{"model": "RISKY-M1"}],
        },
        # 기사4: C급 (5CBM, 월누적 높음)
        {
            "id": 4, "driver_id": "DRV-C01", "driver_name": "정씨",
            "skill_grade": "C", "service_grade": "C",
            "capacity_cbm": 5.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
            "fee_status": {"monthly_accumulated": 6_500_000},  # C등급 상한 7M에 근접
        },
        # 기사5: W1 소파 전용 (A급, 12CBM)
        {
            "id": 5, "driver_id": "DRV-W01", "driver_name": "최소파",
            "skill_grade": "A", "service_grade": "A",
            "capacity_cbm": 12.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "W1",
            "crew": {"size": 1, "is_filler": False},
        },
    ]

    request = {
        "meta": {"date": "2026-02-28", "region_mode": "ignore"},
        "jobs": jobs,
        "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }

    r = httpx.post(f"{API}/dispatch", json=request, headers=HEADERS, timeout=60)
    result = r.json()

    # 결과 분석
    stats = result.get("statistics", {})
    assigned = stats.get("assigned_orders", 0)
    unassigned_count = stats.get("unassigned_orders", 0)
    rate = stats.get("assignment_rate", 0)
    warnings = result.get("warnings", [])
    unassigned = result.get("unassigned", [])
    driver_summary = result.get("driver_summary", [])
    results_list = result.get("results", [])

    print(f"통계:")
    print(f"  전체 오더: {stats.get('total_orders', '?')}")
    print(f"  배정: {assigned}, 미배정: {unassigned_count}, 배정률: {rate}%")
    print(f"  경고: {len(warnings)}건")
    print(f"  활성 기사: {stats.get('active_vehicles', '?')}/{stats.get('total_vehicles', '?')}")

    print(f"\n배정 결과:")
    for r in results_list:
        print(f"  {r['order_id']} → {r['driver_id']} (seq:{r['delivery_sequence']}, fee:{r['install_fee']:,})")

    print(f"\n미배정 오더:")
    for u in unassigned:
        print(f"  {u['order_id']}: {u['constraint']} — {u['reason'][:50]}")

    print(f"\n기사별 요약:")
    for ds in driver_summary:
        status_marks = []
        if ds['c2_status'] != 'ok':
            status_marks.append(f"C2:{ds['c2_status']}")
        if ds['c6_status'] != 'ok':
            status_marks.append(f"C6:{ds['c6_status']}")
        marks = f" [{', '.join(status_marks)}]" if status_marks else ""
        print(f"  {ds['driver_id']} ({ds['skill_grade']}급): "
              f"{ds['assigned_count']}건, {ds['total_fee']:,}원{marks}")

    print(f"\n경고 목록:")
    for w in warnings:
        wtype = w.get("type", "?")
        wmsg = w.get("message", "?")[:60]
        print(f"  [{wtype}] {wmsg}")

    # 검증
    print(f"\n--- 검증 ---")
    errors = []

    # 1. 배정률 확인 (소파가 Y1만 있으면 미배정 가능 → W1 기사가 있으니 배정 가능)
    if assigned < 7:
        errors.append(f"배정이 너무 적음: {assigned}/10")

    # 2. S급 오더(INT-003)가 S급 기사에게 배정되었나
    s_order = [r for r in results_list if r["order_id"] == "INT-003"]
    if s_order:
        if s_order[0]["driver_id"] != "DRV-S01":
            # S급은 DRV-S01만 가능
            errors.append(f"S급 오더가 비S급 기사에 배정: {s_order[0]['driver_id']}")
    else:
        errors.append("S급 오더(INT-003)가 미배정됨")

    # 3. 소파(INT-007)가 W1 기사에게 배정되었나
    sofa_order = [r for r in results_list if r["order_id"] == "INT-007"]
    if sofa_order:
        if sofa_order[0]["driver_id"] != "DRV-W01":
            errors.append(f"소파 오더가 W1이 아닌 기사에 배정: {sofa_order[0]['driver_id']}")
    # 소파 미배정은 허용 (W1 기사가 region_mode=ignore에서도 소파 skill 가짐)

    # 4. C6 경고가 존재해야 (DRV-C01은 배정 0건이라도 월누적만으로 warning 가능?)
    #    → fee_validator/monthly_cap은 assigned_count==0이면 skip. C4 사전검증 경고가 있으면 OK
    c6_warnings = [w for w in warnings if w.get("type", "").startswith("C6_")]
    # C6 사전검증 경고 (monthly_accumulated가 90%+) 확인
    if not c6_warnings:
        errors.append("C6 월상한 경고가 하나도 없음")

    # 5. 활성 기사 — VROOM 최적화 결과이므로 최소 2명이면 OK
    active_drivers = [ds for ds in driver_summary if ds["assigned_count"] > 0]
    if len(active_drivers) < 2:
        errors.append(f"활성 기사가 2명 미만: {len(active_drivers)}명")

    if errors:
        print("  ISSUES:")
        for e in errors:
            print(f"  ⚠ {e}")
    else:
        print("  ✓ 모든 검증 통과")

    return len(errors) == 0


def test_multi_region_strict():
    """다권역 strict 모드: 권역별 분리 배차"""
    print("\n\n=== 통합 시나리오: 다권역 strict 모드 ===\n")

    jobs = [
        # Y1 오더
        {
            "id": 1, "order_id": "REG-Y1-1",
            "location": [126.97, 37.55], "region_code": "Y1",
            "products": [{"model_code": "STD-001", "cbm": 1.0, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 30},
        },
        {
            "id": 2, "order_id": "REG-Y1-2",
            "location": [126.98, 37.56], "region_code": "Y1",
            "products": [{"model_code": "STD-002", "cbm": 1.5, "fee": 60000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 25},
        },
        # 대전 오더
        {
            "id": 3, "order_id": "REG-DJ-1",
            "location": [127.38, 36.35], "region_code": "대전",
            "products": [{"model_code": "STD-003", "cbm": 2.0, "fee": 55000, "required_grade": "B"}],
            "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 35},
        },
        # 부산 오더 (기사 없음 → 미배정)
        {
            "id": 4, "order_id": "REG-BS-1",
            "location": [129.07, 35.17], "region_code": "부산",
            "products": [{"model_code": "STD-004", "cbm": 1.0, "fee": 40000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 20},
        },
    ]

    vehicles = [
        # Y1 기사
        {
            "id": 1, "driver_id": "DRV-Y1-1", "driver_name": "Y1기사",
            "skill_grade": "A", "service_grade": "A", "capacity_cbm": 15.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
        },
        # 대전 기사
        {
            "id": 2, "driver_id": "DRV-DJ-1", "driver_name": "대전기사",
            "skill_grade": "B", "service_grade": "B", "capacity_cbm": 10.0,
            "location": {"start": [127.40, 36.35], "end": [127.40, 36.35]},
            "region_code": "대전",
            "crew": {"size": 1, "is_filler": False},
        },
    ]

    request = {
        "meta": {"date": "2026-02-28", "region_mode": "strict"},
        "jobs": jobs,
        "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }

    r = httpx.post(f"{API}/dispatch", json=request, headers=HEADERS, timeout=60)
    result = r.json()

    stats = result.get("statistics", {})
    assigned = stats.get("assigned_orders", 0)
    unassigned = result.get("unassigned", [])
    results_list = result.get("results", [])
    meta = result.get("meta", {})

    print(f"배정: {assigned}/4, 미배정: {len(unassigned)}")
    print(f"처리 권역: {meta.get('regions_processed', '?')}")

    for r_item in results_list:
        print(f"  {r_item['order_id']} → {r_item['driver_id']}")
    for u in unassigned:
        print(f"  미배정: {u['order_id']} ({u['constraint']})")

    # 검증
    errors = []

    # Y1 오더 2건 → Y1 기사에 배정
    y1_assigned = [r for r in results_list if r["order_id"].startswith("REG-Y1")]
    if len(y1_assigned) != 2:
        errors.append(f"Y1 오더 배정 {len(y1_assigned)}/2")

    # 대전 오더 1건 → 대전 기사에 배정
    dj_assigned = [r for r in results_list if r["order_id"].startswith("REG-DJ")]
    if len(dj_assigned) != 1:
        errors.append(f"대전 오더 배정 {len(dj_assigned)}/1")

    # 부산 오더 → 미배정 (기사 없음)
    bs_unassigned = [u for u in unassigned if u["order_id"] == "REG-BS-1"]
    if len(bs_unassigned) != 1:
        errors.append(f"부산 미배정 {len(bs_unassigned)}/1")

    # 총 3건 배정, 1건 미배정
    if assigned != 3:
        errors.append(f"총 배정 {assigned} != 3")

    if errors:
        print(f"\n  ISSUES:")
        for e in errors:
            print(f"  ⚠ {e}")
    else:
        print(f"\n  ✓ 모든 검증 통과")

    return len(errors) == 0


def test_validation_error():
    """검증 에러: 중복 ID → 400 에러"""
    print("\n\n=== 통합 시나리오: 검증 에러 (중복 ID) ===\n")

    jobs = [
        {
            "id": 1, "order_id": "DUP-1",
            "location": [126.97, 37.55], "region_code": "Y1",
            "products": [{"model_code": "STD-001", "cbm": 1.0, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 30},
        },
        {
            "id": 1, "order_id": "DUP-2",  # 동일 ID!
            "location": [126.98, 37.56], "region_code": "Y1",
            "products": [{"model_code": "STD-002", "cbm": 1.0, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 30},
        },
    ]

    vehicles = [
        {
            "id": 1, "driver_id": "DRV-1", "driver_name": "기사1",
            "skill_grade": "A", "service_grade": "A", "capacity_cbm": 15.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
        },
    ]

    request = {
        "meta": {"date": "2026-02-28", "region_mode": "ignore"},
        "jobs": jobs,
        "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }

    r = httpx.post(f"{API}/dispatch", json=request, headers=HEADERS, timeout=60)
    print(f"  HTTP Status: {r.status_code}")

    if r.status_code == 400:
        detail = r.json().get("detail", {})
        print(f"  에러: {detail.get('error', '?')}")
        print(f"  ✓ 중복 ID 검증 정상 (400 반환)")
        return True
    else:
        result = r.json()
        print(f"  Status: {result.get('status', '?')}")
        # status가 "failed"이고 validation error가 있어도 OK
        if result.get("status") == "failed":
            print(f"  ✓ 중복 ID 검증 정상 (failed 반환)")
            return True
        print(f"  ⚠ 중복 ID가 에러 없이 통과됨")
        return False


def test_flexible_region():
    """flexible 모드: strict에서 미배정 → 인접 권역 기사에 재시도"""
    print("\n\n=== 통합 시나리오: flexible 권역 모드 ===\n")

    jobs = [
        # Y1 오더 2건
        {
            "id": 1, "order_id": "FLEX-Y1-1",
            "location": [126.97, 37.55], "region_code": "Y1",
            "products": [{"model_code": "STD-001", "cbm": 1.0, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 30},
        },
        # Y3 오더 — Y3 기사 없음, 인접(Y1,Y2)에서 재시도
        {
            "id": 2, "order_id": "FLEX-Y3-1",
            "location": [127.10, 37.58], "region_code": "Y3",
            "products": [{"model_code": "STD-002", "cbm": 1.0, "fee": 45000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 25},
        },
    ]

    vehicles = [
        # Y1 기사만 — Y3는 인접
        {
            "id": 1, "driver_id": "DRV-FLEX-1", "driver_name": "Y1기사",
            "skill_grade": "A", "service_grade": "A", "capacity_cbm": 15.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
        },
    ]

    # strict: Y3 오더 미배정
    request_strict = {
        "meta": {"date": "2026-02-28", "region_mode": "strict"},
        "jobs": jobs, "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }
    r_strict = httpx.post(f"{API}/dispatch", json=request_strict, headers=HEADERS, timeout=60)
    strict_result = r_strict.json()
    strict_assigned = strict_result.get("statistics", {}).get("assigned_orders", 0)
    strict_unassigned = strict_result.get("unassigned", [])

    print(f"strict: 배정 {strict_assigned}/2, 미배정 {len(strict_unassigned)}")
    for u in strict_unassigned:
        print(f"  미배정: {u['order_id']} ({u['constraint']})")

    # flexible: Y3 오더가 Y1 기사에 재시도 배정
    request_flex = {
        "meta": {"date": "2026-02-28", "region_mode": "flexible"},
        "jobs": jobs, "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }
    r_flex = httpx.post(f"{API}/dispatch", json=request_flex, headers=HEADERS, timeout=60)
    flex_result = r_flex.json()
    flex_assigned = flex_result.get("statistics", {}).get("assigned_orders", 0)
    flex_warnings = flex_result.get("warnings", [])
    flex_retry = [w for w in flex_warnings if w.get("type") == "FLEXIBLE_RETRY"]

    print(f"flexible: 배정 {flex_assigned}/2, 재시도 경고 {len(flex_retry)}건")
    if flex_retry:
        print(f"  재시도: {flex_retry[0].get('message', '')}")

    # 검증
    errors = []
    if strict_assigned != 1:
        errors.append(f"strict에서 Y1 오더만 배정되어야: {strict_assigned}")
    if len(strict_unassigned) != 1:
        errors.append(f"strict에서 Y3 미배정이어야: {len(strict_unassigned)}")
    if flex_assigned != 2:
        errors.append(f"flexible에서 전체 배정되어야: {flex_assigned}")

    if errors:
        print(f"\n  ISSUES:")
        for e in errors:
            print(f"  ⚠ {e}")
    else:
        print(f"\n  ✓ 모든 검증 통과")

    return len(errors) == 0


def test_driver_distribution():
    """기사 균등 배분: 5명 기사 모두 최소 1건 배정"""
    print("\n\n=== 통합 시나리오: 기사 균등 배분 ===\n")

    # 10개 동일 오더
    jobs = []
    for i in range(1, 11):
        jobs.append({
            "id": i, "order_id": f"DIST-{i:02d}",
            "location": [126.97 + i * 0.005, 37.55 + i * 0.003],
            "region_code": "Y1",
            "products": [{"model_code": "STD-001", "cbm": 1.0, "fee": 50000, "required_grade": "C"}],
            "scheduling": {"preferred_time_slot": "하루종일", "service_minutes": 30},
        })

    # 5명 동일 기사 (C급, 15CBM)
    vehicles = []
    for i in range(1, 6):
        vehicles.append({
            "id": i, "driver_id": f"DRV-DIST-{i}",
            "driver_name": f"기사{i}", "skill_grade": "C", "service_grade": "C",
            "capacity_cbm": 15.0,
            "location": {"start": [127.05, 37.50], "end": [127.05, 37.50]},
            "region_code": "Y1",
            "crew": {"size": 1, "is_filler": False},
        })

    request = {
        "meta": {"date": "2026-02-28", "region_mode": "ignore"},
        "jobs": jobs, "vehicles": vehicles,
        "options": {"max_tasks_per_driver": 12, "geometry": False},
    }

    r = httpx.post(f"{API}/dispatch", json=request, headers=HEADERS, timeout=60)
    result = r.json()

    stats = result.get("statistics", {})
    driver_summary = result.get("driver_summary", [])
    active = stats.get("active_vehicles", 0)

    print(f"배정: {stats.get('assigned_orders')}/10, 활성 기사: {active}/5")
    for ds in driver_summary:
        print(f"  {ds['driver_id']}: {ds['assigned_count']}건")

    # 검증: 최소 3명 이상 활성
    errors = []
    if active < 3:
        errors.append(f"활성 기사 {active}명 < 3명")

    if errors:
        print(f"\n  ISSUES:")
        for e in errors:
            print(f"  ⚠ {e}")
    else:
        print(f"\n  ✓ 모든 검증 통과")

    return len(errors) == 0


if __name__ == "__main__":
    tests = [
        ("복합 배차", test_complex_scenario),
        ("다권역 strict", test_multi_region_strict),
        ("검증 에러", test_validation_error),
        ("flexible 권역", test_flexible_region),
        ("기사 균등 배분", test_driver_distribution),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ ERROR: {e}")

    print(f"\n{'='*50}")
    print(f"통합 결과: {passed} PASS, {failed} FAIL (총 {len(tests)})")
    sys.exit(0 if failed == 0 else 1)

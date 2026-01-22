#!/bin/bash

echo "================================"
echo "VROOM Violation 테스트"
echo "================================"
echo ""

# 1. Skills 위반 테스트
echo "[1] Skills Constraint Violation 테스트"
echo "차량: skills [1, 2]"
echo "작업 2: skills [3] 필요 -> SKILLS violation 예상"
echo "--------------------------------"

cat > /tmp/test_skills.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "skills": [1, 2]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "skills": [1]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "skills": [3]
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @/tmp/test_skills.json)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len(data['routes'][0]['steps']) - 2 if data['routes'] else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"  - Job {job['id']}: {job.get('type', 'unknown')}\")
"
echo ""

# 2. Capacity 위반 테스트
echo "[2] Capacity Constraint Violation 테스트"
echo "차량 용량: [10]"
echo "작업들 합계: [20] -> LOAD violation 예상"
echo "--------------------------------"

cat > /tmp/test_capacity.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "capacity": [10]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "delivery": [8]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "delivery": [7]
    },
    {
      "id": 3,
      "location": [126.9910, 37.5512],
      "delivery": [5]
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @/tmp/test_capacity.json)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len(data['routes'][0]['steps']) - 2 if data['routes'] else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
total_delivery = sum([job.get('delivery', [0])[0] for job in data.get('unassigned', [])])
print(f\"미할당 작업 배송량 합계: {total_delivery}\")
"
echo ""

# 3. Time Window 위반 테스트
echo "[3] Time Window Violation 테스트"
echo "차량 운행: 08:00-10:00 (28800-36000초)"
echo "작업 시간: 18:00-20:00 (64800-72000초) -> DELAY violation 예상"
echo "--------------------------------"

cat > /tmp/test_timewindow.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "time_window": [28800, 36000]
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "time_windows": [[32400, 34200]]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "time_windows": [[64800, 72000]]
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @/tmp/test_timewindow.json)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len(data['routes'][0]['steps']) - 2 if data['routes'] else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"  - Job {job['id']}\")
"
echo ""

# 4. Max Tasks 위반 테스트
echo "[4] Max Tasks Violation 테스트"
echo "차량 max_tasks: 2"
echo "작업 개수: 4개 -> MAX_TASKS violation 예상"
echo "--------------------------------"

cat > /tmp/test_maxtasks.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "max_tasks": 2
  }],
  "jobs": [
    {"id": 1, "location": [127.0276, 37.4979]},
    {"id": 2, "location": [127.0594, 37.5140]},
    {"id": 3, "location": [126.9910, 37.5512]},
    {"id": 4, "location": [127.0100, 37.5400]}
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @/tmp/test_maxtasks.json)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assigned = len(data['routes'][0]['steps']) - 2 if data['routes'] else 0
unassigned = len(data['unassigned'])
print(f\"할당된 작업: {assigned}개 (max_tasks=2 제약 준수)\")
print(f\"미할당 작업: {unassigned}개\")
"
echo ""

# 5. 모든 제약 만족하는 케이스
echo "[5] 모든 제약 만족 케이스 (Violations 없음)"
echo "--------------------------------"

cat > /tmp/test_valid.json << 'EOF'
{
  "vehicles": [{
    "id": 1,
    "start": [126.9780, 37.5665],
    "end": [126.9780, 37.5665],
    "capacity": [100],
    "skills": [1, 2, 3],
    "time_window": [28800, 64800],
    "max_tasks": 10
  }],
  "jobs": [
    {
      "id": 1,
      "location": [127.0276, 37.4979],
      "delivery": [10],
      "skills": [1],
      "time_windows": [[32400, 36000]]
    },
    {
      "id": 2,
      "location": [127.0594, 37.5140],
      "delivery": [15],
      "skills": [2],
      "time_windows": [[36000, 43200]]
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:3000/ -H "Content-Type: application/json" -d @/tmp/test_valid.json)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assigned = len(data['routes'][0]['steps']) - 2 if data['routes'] else 0
print(f\"할당된 작업: {assigned}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
print(f\"Violations: {data['summary']['violations']}\")
if data['routes']:
    print(f\"Route violations: {data['routes'][0]['violations']}\")
"
echo ""

echo "================================"
echo "테스트 완료"
echo "================================"

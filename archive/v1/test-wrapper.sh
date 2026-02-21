#!/bin/bash

echo "========================================"
echo "VROOM Wrapper Test - Unassigned Reasons"
echo "========================================"
echo ""

echo "[1] Testing Skills Violation"
echo "Job requires skill [3], vehicle only has [1, 2]"
echo "----------------------------------------"

cat > /tmp/wrapper_test_skills.json << 'EOF'
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

RESPONSE=$(curl -s -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @/tmp/wrapper_test_skills.json)

echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len([s for s in data['routes'][0]['steps'] if s['type'] == 'job']) if data.get('routes') else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"\\n  Job {job['id']}:\")
        if 'reasons' in job:
            for reason in job['reasons']:
                print(f\"    - {reason['type']}: {reason['description']}\")
                if reason.get('details'):
                    print(f\"      상세: {reason['details']}\")
"
echo ""

echo "[2] Testing Capacity Violation"
echo "Vehicle capacity [10], jobs need [8] + [7] + [5] = 20 total"
echo "----------------------------------------"

cat > /tmp/wrapper_test_capacity.json << 'EOF'
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

RESPONSE=$(curl -s -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @/tmp/wrapper_test_capacity.json)

echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len([s for s in data['routes'][0]['steps'] if s['type'] == 'job']) if data.get('routes') else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"\\n  Job {job['id']}:\")
        if 'reasons' in job:
            for reason in job['reasons']:
                print(f\"    - {reason['type']}: {reason['description']}\")
                if reason.get('details'):
                    print(f\"      상세: {reason['details']}\")
"
echo ""

echo "[3] Testing Time Window Violation"
echo "Vehicle: 08:00-10:00, Job needs 18:00-20:00"
echo "----------------------------------------"

cat > /tmp/wrapper_test_timewindow.json << 'EOF'
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

RESPONSE=$(curl -s -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @/tmp/wrapper_test_timewindow.json)

echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len([s for s in data['routes'][0]['steps'] if s['type'] == 'job']) if data.get('routes') else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"\\n  Job {job['id']}:\")
        if 'reasons' in job:
            for reason in job['reasons']:
                print(f\"    - {reason['type']}: {reason['description']}\")
                if reason.get('details'):
                    print(f\"      상세: {reason['details']}\")
"
echo ""

echo "[4] Testing Complex Test Case"
echo "Multiple constraints: skills [3], capacity [8], max_tasks 3"
echo "----------------------------------------"

curl -s -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @/home/shawn/test-violations.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"할당된 작업: {len([s for s in data['routes'][0]['steps'] if s['type'] == 'job']) if data.get('routes') else 0}개\")
print(f\"미할당 작업: {len(data['unassigned'])}개\")
if data['unassigned']:
    for job in data['unassigned']:
        print(f\"\\n  Job {job['id']}:\")
        if 'reasons' in job:
            for reason in job['reasons']:
                print(f\"    - {reason['type']}: {reason['description']}\")
                if reason.get('details'):
                    details_str = str(reason['details'])[:100]
                    print(f\"      상세: {details_str}...\")
"

echo ""
echo "========================================"
echo "테스트 완료"
echo "========================================"

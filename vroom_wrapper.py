#!/usr/bin/env python3
"""
VROOM Wrapper with Unassigned Reason Reporting

This wrapper adds the capability to explain WHY jobs are unassigned,
which VROOM doesn't provide by default.

Usage:
    python3 vroom_wrapper.py

Then send requests to http://localhost:8000/optimize instead of VROOM directly.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import requests
import uvicorn
from dataclasses import dataclass
from enum import Enum

app = FastAPI(title="VROOM Wrapper with Violation Reasons")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VROOM_URL = "http://localhost:3000"

class ViolationType(str, Enum):
    SKILLS = "skills"
    CAPACITY = "capacity"
    TIME_WINDOW = "time_window"
    MAX_TASKS = "max_tasks"
    VEHICLE_TIME_WINDOW = "vehicle_time_window"
    PRECEDENCE = "precedence"
    NO_VEHICLES = "no_vehicles"


@dataclass
class ViolationReason:
    type: str
    description: str
    details: Dict[str, Any]


class ConstraintChecker:
    """Analyzes why jobs are unassigned by comparing with original input"""

    def __init__(self, vrp_input: Dict[str, Any]):
        self.vehicles = vrp_input.get('vehicles', [])
        self.jobs = vrp_input.get('jobs', [])
        self.shipments = vrp_input.get('shipments', [])
        self.jobs_by_id = {job['id']: job for job in self.jobs}
        self.shipments_by_id = {shipment['id']: shipment for shipment in self.shipments}

    def analyze_unassigned(self, unassigned_list: List[Dict]) -> Dict[int, List[Dict]]:
        """
        For each unassigned job/shipment, determine why it couldn't be assigned

        Returns:
            Dict mapping job/shipment ID to list of violation reasons
        """
        reasons_map = {}

        for unassigned in unassigned_list:
            job_id = unassigned['id']
            job_type = unassigned.get('type', 'job')

            if job_type == 'job':
                job = self.jobs_by_id.get(job_id)
                if job:
                    reasons = self._check_job_violations(job)
                else:
                    reasons = [{"type": "unknown", "description": "Job not found in input"}]
            else:  # shipment
                shipment = self.shipments_by_id.get(job_id)
                if shipment:
                    reasons = self._check_shipment_violations(shipment)
                else:
                    reasons = [{"type": "unknown", "description": "Shipment not found in input"}]

            reasons_map[job_id] = reasons

        return reasons_map

    def _check_job_violations(self, job: Dict) -> List[Dict]:
        """Check why a job couldn't be assigned to any vehicle"""
        violations = []

        if not self.vehicles:
            violations.append({
                "type": ViolationType.NO_VEHICLES,
                "description": "No vehicles available",
                "details": {}
            })
            return violations

        job_skills = set(job.get('skills', []))
        job_delivery = job.get('delivery', [0])
        job_pickup = job.get('pickup', [0])
        job_time_windows = job.get('time_windows', [])

        # Check skills compatibility
        skills_compatible_vehicles = []
        for vehicle in self.vehicles:
            vehicle_skills = set(vehicle.get('skills', []))
            if not job_skills or job_skills.issubset(vehicle_skills):
                skills_compatible_vehicles.append(vehicle)

        if not skills_compatible_vehicles:
            violations.append({
                "type": ViolationType.SKILLS,
                "description": "No vehicle has required skills",
                "details": {
                    "required_skills": list(job_skills),
                    "available_vehicle_skills": [v.get('skills', []) for v in self.vehicles]
                }
            })
            # If skills don't match, it's a hard constraint - other checks don't matter
            return violations

        # Check capacity (only for vehicles with matching skills)
        capacity_compatible_vehicles = []
        for vehicle in skills_compatible_vehicles:
            vehicle_capacity = vehicle.get('capacity', [])
            if not vehicle_capacity:
                capacity_compatible_vehicles.append(vehicle)
                continue

            # Check if this vehicle can handle the load
            can_handle = True
            for i, (delivery, pickup) in enumerate(zip(
                job_delivery if job_delivery else [0] * len(vehicle_capacity),
                job_pickup if job_pickup else [0] * len(vehicle_capacity)
            )):
                if i < len(vehicle_capacity):
                    if delivery > vehicle_capacity[i] or pickup > vehicle_capacity[i]:
                        can_handle = False
                        break

            if can_handle:
                capacity_compatible_vehicles.append(vehicle)

        if not capacity_compatible_vehicles:
            violations.append({
                "type": ViolationType.CAPACITY,
                "description": "Job load exceeds all vehicle capacities",
                "details": {
                    "job_delivery": job_delivery,
                    "job_pickup": job_pickup,
                    "vehicle_capacities": [v.get('capacity', []) for v in skills_compatible_vehicles]
                }
            })
            return violations

        # Check time windows
        time_window_compatible = False
        if job_time_windows:
            for vehicle in capacity_compatible_vehicles:
                vehicle_tw = vehicle.get('time_window')
                if not vehicle_tw:
                    time_window_compatible = True
                    break

                # Check if any job time window overlaps with vehicle time window
                for job_tw in job_time_windows:
                    if len(job_tw) >= 2:
                        # Check for any overlap
                        if job_tw[0] <= vehicle_tw[1] and job_tw[1] >= vehicle_tw[0]:
                            time_window_compatible = True
                            break

                if time_window_compatible:
                    break
        else:
            time_window_compatible = True

        if not time_window_compatible and job_time_windows:
            violations.append({
                "type": ViolationType.TIME_WINDOW,
                "description": "Job time windows incompatible with all vehicle time windows",
                "details": {
                    "job_time_windows": job_time_windows,
                    "vehicle_time_windows": [v.get('time_window') for v in capacity_compatible_vehicles if v.get('time_window')]
                }
            })

        # Check max_tasks
        max_tasks_issue = []
        for vehicle in capacity_compatible_vehicles:
            max_tasks = vehicle.get('max_tasks')
            if max_tasks is not None:
                max_tasks_issue.append({
                    "vehicle_id": vehicle['id'],
                    "max_tasks": max_tasks
                })

        if max_tasks_issue and not violations:
            violations.append({
                "type": ViolationType.MAX_TASKS,
                "description": "All compatible vehicles may have reached max_tasks limit",
                "details": {
                    "vehicles_with_limits": max_tasks_issue
                }
            })

        # If no specific violation found, return general incompatibility
        if not violations:
            violations.append({
                "type": "complex_constraint",
                "description": "Could not be assigned due to combination of constraints (time windows, vehicle routes, optimization conflicts)",
                "details": {
                    "compatible_vehicles_count": len(capacity_compatible_vehicles),
                    "note": "Job is theoretically compatible but couldn't fit in optimal routes"
                }
            })

        return violations

    def _check_shipment_violations(self, shipment: Dict) -> List[Dict]:
        """Check why a shipment couldn't be assigned"""
        # Similar logic to jobs but for shipments
        violations = []

        pickup = shipment.get('pickup', {})
        delivery = shipment.get('delivery', {})

        # Check if pickup and delivery have compatible skills/capacity
        pickup_skills = set(pickup.get('skills', []))
        delivery_skills = set(delivery.get('skills', []))

        if pickup_skills != delivery_skills:
            violations.append({
                "type": ViolationType.SKILLS,
                "description": "Pickup and delivery have different skill requirements",
                "details": {
                    "pickup_skills": list(pickup_skills),
                    "delivery_skills": list(delivery_skills)
                }
            })

        # Similar capacity and time window checks as jobs
        # (Simplified for now - can be expanded)

        return violations if violations else [{"type": "unknown", "description": "Shipment could not be assigned"}]


@app.post("/optimize")
async def optimize_with_reasons(vrp_input: Dict[str, Any]):
    """
    Optimize VRP and attach reasons for unassigned jobs

    Args:
        vrp_input: Standard VROOM input format

    Returns:
        VROOM output with added 'reasons' field for each unassigned job
    """
    try:
        # Create constraint checker with original input
        checker = ConstraintChecker(vrp_input)

        # Call VROOM
        response = requests.post(VROOM_URL, json=vrp_input, timeout=300)
        response.raise_for_status()
        result = response.json()

        # Analyze unassigned jobs
        if result.get('unassigned'):
            reasons_map = checker.analyze_unassigned(result['unassigned'])

            # Attach reasons to each unassigned job
            for unassigned in result['unassigned']:
                job_id = unassigned['id']
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        # Add metadata
        result['_wrapper_info'] = {
            "version": "1.0",
            "features": ["unassigned_reasons"],
            "vroom_url": VROOM_URL
        }

        return result

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"VROOM service error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/health")
async def health_check():
    """Check if wrapper and VROOM are healthy"""
    try:
        # Check VROOM connectivity
        vroom_response = requests.get(VROOM_URL, timeout=5)
        vroom_status = "ok" if vroom_response.status_code == 200 else "error"
    except:
        vroom_status = "unreachable"

    return {
        "wrapper": "ok",
        "vroom": vroom_status,
        "vroom_url": VROOM_URL
    }


@app.get("/")
async def root():
    return {
        "service": "VROOM Wrapper with Unassigned Reasons",
        "version": "1.0",
        "endpoints": {
            "/optimize": "POST - Optimize VRP with unassigned reasons",
            "/health": "GET - Health check",
        },
        "usage": "Send VROOM input to /optimize endpoint"
    }


if __name__ == "__main__":
    print("=" * 60)
    print("VROOM Wrapper with Unassigned Reason Reporting")
    print("=" * 60)
    print(f"Wrapper: http://localhost:8000")
    print(f"VROOM: {VROOM_URL}")
    print("")
    print("Send requests to http://localhost:8000/optimize")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)

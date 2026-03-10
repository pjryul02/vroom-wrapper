"""
비동기 Job 관리자

인메모리 Job 저장소 — 비동기 dispatch/optimize 요청의 진행률 추적.
"""

import uuid
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class JobStage(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PREPROCESSING = "preprocessing"
    OPTIMIZING = "optimizing"
    OPTIMIZING_PASS2 = "optimizing_pass2"
    RETRY_RELAXATION = "retry_relaxation"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    FAILED = "failed"


# 단계별 진행률(%) 및 라벨
STAGE_CONFIG = {
    JobStage.QUEUED:            (0,   "대기 중"),
    JobStage.VALIDATING:        (10,  "검증 중"),
    JobStage.PREPROCESSING:     (20,  "전처리 중"),
    JobStage.OPTIMIZING:        (40,  "최적화 중"),
    JobStage.OPTIMIZING_PASS2:  (60,  "2차 최적화 중"),
    JobStage.RETRY_RELAXATION:  (75,  "재시도 중"),
    JobStage.POSTPROCESSING:    (90,  "후처리 중"),
    JobStage.COMPLETED:         (100, "완료"),
    JobStage.FAILED:            (100, "실패"),
}

# TTL: 2시간
JOB_TTL_SECONDS = 7200


class Job:
    __slots__ = [
        "id", "stage", "percentage", "stage_label",
        "result", "error", "created_at", "updated_at",
        "metadata",
    ]

    def __init__(self, job_id: str):
        self.id = job_id
        self.stage = JobStage.QUEUED
        self.percentage = 0
        self.stage_label = "대기 중"
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.updated_at = time.time()
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        elapsed_ms = int((time.time() - self.created_at) * 1000)
        d = {
            "job_id": self.id,
            "status": "completed" if self.stage == JobStage.COMPLETED
                      else "failed" if self.stage == JobStage.FAILED
                      else "processing",
            "progress": {
                "stage": self.stage.value,
                "stage_label": self.stage_label,
                "percentage": self.percentage,
            },
            "elapsed_ms": elapsed_ms,
        }
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class JobManager:
    """인메모리 Job 저장소"""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())[:8]
        self._jobs[job_id] = Job(job_id)
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_progress(self, job_id: str, stage: JobStage, **metadata):
        job = self._jobs.get(job_id)
        if not job:
            return
        pct, label = STAGE_CONFIG.get(stage, (0, stage.value))
        job.stage = stage
        job.percentage = pct
        job.stage_label = label
        job.updated_at = time.time()
        if metadata:
            job.metadata.update(metadata)

    def set_result(self, job_id: str, result: Dict[str, Any]):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.stage = JobStage.COMPLETED
        job.percentage = 100
        job.stage_label = "완료"
        job.result = result
        job.updated_at = time.time()

    def set_failed(self, job_id: str, error: str):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.stage = JobStage.FAILED
        job.percentage = 100
        job.stage_label = "실패"
        job.error = error
        job.updated_at = time.time()

    def cleanup_expired(self):
        """TTL 초과 Job 정리"""
        now = time.time()
        expired = [
            jid for jid, job in self._jobs.items()
            if now - job.created_at > JOB_TTL_SECONDS
        ]
        for jid in expired:
            del self._jobs[jid]
        if expired:
            logger.info(f"Job 정리: {len(expired)}건 TTL 만료 삭제")


# 싱글톤
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager

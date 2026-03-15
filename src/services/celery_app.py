"""Celery 애플리케이션 설정"""

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

celery_app = Celery(
    "vroom_wrapper",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.services.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=7200,  # 2시간
    worker_concurrency=3,  # MAX_CONCURRENT_DISPATCH와 동일
    task_acks_late=True,  # 완료 후 ack
    worker_prefetch_multiplier=1,  # 한 번에 하나씩
)


@celery_app.on_after_configure.connect
def setup_components(sender, **kwargs):
    """worker 시작 시 컴포넌트 lazy init"""
    from ..core.dependencies import get_components
    import logging
    logger = logging.getLogger(__name__)
    try:
        get_components()
        logger.info("Celery worker: 컴포넌트 초기화 완료")
    except Exception as e:
        logger.warning(f"Celery worker: 컴포넌트 초기화 실패 (task 호출 시 재시도): {e}")

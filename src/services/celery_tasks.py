"""Celery 태스크 정의"""

import asyncio
import logging
from celery import shared_task

from ..hglis.models import HglisDispatchRequest
from ..hglis.dispatcher import HglisDispatcher
from ..core.dependencies import get_components

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="dispatch_task", max_retries=0)
def dispatch_task(self, request_data: dict) -> dict:
    """비동기 dispatch Celery 태스크"""
    logger.info(f"Celery dispatch 시작: task_id={self.request.id}")
    try:
        request_body = HglisDispatchRequest.model_validate(request_data)
        c = get_components()
        dispatcher = HglisDispatcher(
            controller=c.controller,
            valhalla_eta_updater=c.valhalla_eta_updater,
        )
        response = asyncio.run(dispatcher.dispatch(request_body))
        logger.info(f"Celery dispatch 완료: task_id={self.request.id}")
        return response.model_dump()
    except Exception as e:
        logger.error(f"Celery dispatch 실패: task_id={self.request.id}, error={e}")
        raise

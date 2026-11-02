"""Celery application for background work.

The production Compose worker runs `celery -A app.tasks:celery_app`.
Task modules can be registered on `celery_app` as they are added. With no
tasks registered, the worker still connects to Redis and stays up.
"""

from celery import Celery

from app.config import Settings

settings = Settings()

celery_app = Celery(
    "core_accounting",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    worker_hijack_root_logger=False,
)

# `celery -A app.tasks` looks up an attribute named app.
app = celery_app

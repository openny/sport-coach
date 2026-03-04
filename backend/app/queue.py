# backend/app/queue.py
from celery import Celery
from .config import settings

celery_app = Celery(
    "coach",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_routes={"app.tasks.*": {"queue": "default"}},
    broker_connection_retry_on_startup=True,
)
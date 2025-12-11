from celery import Celery
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "pdf_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.autodiscover_tasks(["worker"])

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

)

from worker import tasks


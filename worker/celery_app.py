from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "gigbid",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker.tasks"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="gigbid",
    task_soft_time_limit=120,
    task_time_limit=150,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_track_started=True,
    result_expires=60 * 60,
    broker_transport_options={"visibility_timeout": 60 * 60},
    timezone="Asia/Karachi",
    beat_schedule={
        "scout-saved-searches": {
            "task": "gigbid.scout_saved_searches",
            "schedule": 4 * 60 * 60,
        }
    },
)

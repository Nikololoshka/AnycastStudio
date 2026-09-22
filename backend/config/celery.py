"""The worker that keeps publishing after the browser tab is closed.

Uploads run for minutes and must survive both the tab closing and the worker
restarting. acks_late means a task killed mid-flight is handed out again;
claiming the target with a conditional UPDATE is what stops that becoming a
second upload, and resume_state is what stops it becoming a second transfer.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("anycaststudio")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

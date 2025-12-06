import os
from pathlib import Path

from .settings import *  # noqa: F403

CELERY_RESULTS_DIR = Path(os.getenv("CELERY_RESULTS_DIR", Path.home() / "celery_results"))

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = f"file://{CELERY_RESULTS_DIR}"

CELERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "sqlite3.db",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

LANGUAGE_CODE = "en"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}
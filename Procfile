web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: celery -A workers.tasks worker --loglevel=info --concurrency=${CELERY_CONCURRENCY:-1}

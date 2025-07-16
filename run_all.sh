#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Start Redis server in background (if not already running)
redis-server --daemonize yes

# Start Django ASGI server using Daphne
daphne -p 8000 bitWar_backend.asgi:application &

# Start Celery worker
celery -A bitWar_backend worker --loglevel=info &

# Start Celery beat
celery -A bitWar_backend beat --loglevel=info &


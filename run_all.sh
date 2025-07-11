#!/bin/bash

# Start Redis server in background
redis-server --daemonize yes

# Start Django ASGI server using Daphne
daphne -p 8000 bitWar_backend.asgi:application &

# Start Celery worker
celery -A bitWar_backend worker --loglevel=info &

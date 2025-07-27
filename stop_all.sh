

echo "🛑 Stopping Daphne..."
pkill -f "daphne -p 8000"

echo "🛑 Stopping Celery worker..."
pkill -f "celery -A bitWar_backend worker"

echo "🛑 Stopping Celery beat..."
pkill -f "celery -A bitWar_backend beat"

echo "🛑 (Optional) Stopping Redis server..."
pkill redis-server

echo "✅ All services stopped."

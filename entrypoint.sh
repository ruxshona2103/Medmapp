#!/bin/bash

# Exit on error
set -e

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if doesn't exist (optional)
# echo "Creating superuser..."
# python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"

# Start Daphne (ASGI server for HTTP + WebSocket)
echo "Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 \
    --access-log - \
    --proxy-headers \
    config.asgi:application

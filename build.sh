#!/usr/bin/env bash
# Render uchun avtomatik migration script

echo "📦 Installing requirements..."
pip install -r requirements.txt

echo "🚀 Forcing patient migrations..."
python force_migrate.py

echo "🧱 Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build process complete!"

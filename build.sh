#!/usr/bin/env bash
# ===============================================================
# 🚀 Render Build Script (Django)
# ===============================================================

set -o errexit  # Xatolik chiqsa, jarayonni to‘xtatadi

echo "📦 Installing requirements..."
pip install -r requirements.txt

# ===============================================================
# 🧱 Run Migrations (safe mode)
# ===============================================================
echo "🧱 Running migrations..."

# 1️⃣ Avval oddiy migrate
if ! python manage.py migrate --noinput; then
    echo "⚠️ Normal migration failed, trying fake migration..."
    python manage.py migrate --fake --noinput
fi

# ===============================================================
# 🧾 Collect Static Files
# ===============================================================
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# ===============================================================
# 👑 CREATE SUPERUSER (automatic from Environment Variables)
# ===============================================================
echo "👑 Checking for existing superuser..."

python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()

phone = "${DJANGO_SUPERUSER_PHONE}"
if not phone:
    print("⚠️  Environment variable DJANGO_SUPERUSER_PHONE is missing — skipping superuser creation.")
else:
    if not User.objects.filter(phone_number=phone).exists():
        print(f"🆕 Creating superuser: {phone}")
        User.objects.create_superuser(
            phone_number=phone,
            password="${DJANGO_SUPERUSER_PASSWORD}",
        )
        print("✅ Superuser created successfully.")
    else:
        print("⚡ Superuser already exists.")
EOF

echo "✅ Build process complete!"

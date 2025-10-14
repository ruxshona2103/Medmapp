# force_migrate.py
import os
os.system("python manage.py showmigrations patients")
os.system("python manage.py migrate patients --plan")
os.system("python manage.py migrate patients --noinput")

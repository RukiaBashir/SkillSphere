import os
import sys
import django
from django.contrib.auth import get_user_model

# Ensure the project root is in the Python path.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django environment.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SkillSphere.settings')
django.setup()

User = get_user_model()

SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_EMAIL = os.getenv("SUPERUSER_EMAIL", "admin@example.com")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "123456l7")

if not User.objects.filter(username=SUPERUSER_USERNAME).exists():
    User.objects.create_superuser(
        username=SUPERUSER_USERNAME,
        email=SUPERUSER_EMAIL,
        password=SUPERUSER_PASSWORD
    )
    print("Superuser created successfully!")
else:
    print("Superuser already exists.")

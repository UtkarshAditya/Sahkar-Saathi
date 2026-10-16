"""Create the team superuser once, from environment variables. Safe to run on every start.

    DJANGO_SUPERUSER_USERNAME          (default: admin)
    DJANGO_SUPERUSER_EMAIL             (optional)
    DJANGO_SUPERUSER_PASSWORD or DJANGO_SUPERUSER_PASSWORD_FILE

Does nothing if no password is configured or the user already exists. It never changes
an existing user's password, so a password changed in the admin site stays changed.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from config.settings import env_secret


class Command(BaseCommand):
    help = "Create the team superuser from DJANGO_SUPERUSER_* settings if it does not exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = env_secret("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            self.stdout.write("ensure_superuser: no password configured, skipping.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"ensure_superuser: '{username}' already exists.")
            return

        User.objects.create_superuser(
            username=username,
            email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"ensure_superuser: created '{username}'."))

import os

from django.core.asgi import get_asgi_application

# ASGI entry point kept here in case the project needs async support later.

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pompom_house.settings')
application = get_asgi_application()

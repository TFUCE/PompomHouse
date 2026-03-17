import os

from django.core.wsgi import get_wsgi_application

# WSGI entry point used by the current deployment setup.

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pompom_house.settings')
application = get_wsgi_application()

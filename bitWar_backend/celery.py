import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bitWar_backend.settings')


app = Celery('bitwar_backend')


app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

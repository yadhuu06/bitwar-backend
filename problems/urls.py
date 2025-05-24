from django.urls import path
from . import views

urlpatterns = [
    path('', views.problems, name='problems'),
  
]
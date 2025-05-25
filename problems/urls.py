from django.urls import path
from .views import QuestionCreateAPIView,QuestionsAPIView

urlpatterns = [
    path('create/', QuestionCreateAPIView.as_view(), name='create_question'),
    path('', QuestionsAPIView.as_view(), name='questions'),


]

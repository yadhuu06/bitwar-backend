from django.urls import path
from .views import QuestionCreateAPIView, QuestionsAPIView

urlpatterns = [
    path('questions/', QuestionsAPIView.as_view(), name='questions-list'),
    path('questions/create/', QuestionCreateAPIView.as_view(), name='question-create'),
    path('questions/edit/<uuid:question_id>/', QuestionCreateAPIView.as_view(), name='question-edit'),
]
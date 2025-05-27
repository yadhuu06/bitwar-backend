from django.urls import path
from .views import QuestionCreateAPIView, QuestionsAPIView, TestCaseListCreateAPIView, TestCaseRetrieveUpdateDestroyAPIView, QuestionDetailAPIView

urlpatterns = [
    path('', QuestionsAPIView.as_view(), name='questions-list'),
    path('<uuid:question_id>/', QuestionDetailAPIView.as_view(), name='question-detail'),
    path('create/', QuestionCreateAPIView.as_view(), name='question-create'),
    path('edit/<uuid:question_id>/', QuestionCreateAPIView.as_view(), name='question-edit'),
    path('<uuid:question_id>/test-cases/', TestCaseListCreateAPIView.as_view(), name='test-case-list-create'),
    path('<uuid:question_id>/test-cases/<int:test_case_id>/', TestCaseRetrieveUpdateDestroyAPIView.as_view(), name='test-case-detail'),
]
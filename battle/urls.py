from django.urls import path
from .views import QuestionDetailAPIView

urlpatterns = [
    
    path('<int:id>/', QuestionDetailAPIView.as_view(), name='get-problem-details'),
    
]
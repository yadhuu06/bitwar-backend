from django.urls import path
from .views import BattleQuestionAPIView, QuestionVerifyAPIView,GlobalRankingAPIView

urlpatterns = [
    path('<int:question_id>/', BattleQuestionAPIView.as_view(), name='get-problem-details'),
    path('<int:question_id>/verify/', QuestionVerifyAPIView.as_view(), name='get-problem-verify'),
     path('global-rankings/', GlobalRankingAPIView.as_view(), name='global-rankings'),
   




]


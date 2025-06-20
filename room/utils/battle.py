from room.models import Room, RoomParticipant
from problems.models import Question
from django.db.models import Q
import random



def select_random_question(room):
    print("call came for question selection")
    print("topic=",room.topic)
    question_options = Question.objects.filter(
        difficulty=room.difficulty,
        tags=room.topic
    ).filter(
        Q(is_contributed=False) | Q(is_contributed=True, contribution_status="Accepted")
    ).exclude(is_validate=False)

    print("Available questions: ", question_options)

    if not question_options.exists():
        return None
    selected_question=random.choice(list(question_options))
    print("selected one is >>>",selected_question)

    return selected_question


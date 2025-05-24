
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('EASY', 'Easy'),
        ('MEDIUM', 'Medium'),
        ('HARD', 'Hard'),
    ]
    TAGS_CHOICES=[
        ('Array','Array'),
        ('STRING','String'),
        ('DSA','Dsa'),
    ]

    title = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField()  
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, db_index=True)
    tags = models.CharField(choices=TAGS_CHOICES)  
    is_validate=models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_questions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['difficulty']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Example(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="examples")
    input_example = models.TextField()
    output_example = models.TextField()
    explanation = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('question', 'order')
        ordering = ['order']
        indexes = [
            models.Index(fields=['question', 'order']),
        ]

    def __str__(self):
        return f"Example {self.order + 1} for {self.question.title}"
class SolvedCode(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='solved_codes')
    language = models.CharField(max_length=50) 
    solution_code = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class TestCase(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)  
    order = models.PositiveIntegerField(default=0)

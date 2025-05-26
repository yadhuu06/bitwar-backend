from rest_framework import serializers
from django.utils.text import slugify
from .models import Question, Example, SolvedCode, TestCase

class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ['id', 'input_example', 'output_example', 'explanation', 'order']

class SolvedCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolvedCode
        fields = ['id', 'language', 'solution_code', 'created_at']

class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ['id', 'input_data', 'expected_output', 'is_sample', 'order']

class QuestionInitialCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['title', 'description', 'difficulty', 'tags', 'question_id']
        read_only_fields = ['question_id']

    def validate_tags(self, value):
        valid_tags = [tag[0] for tag in Question.TAGS_CHOICES]  # ['ARRAY', 'STRING', 'DSA']
        if value not in valid_tags:
            raise serializers.ValidationError(
                f"Invalid tag. Must be one of {valid_tags}"
            )
        return value

    def validate_difficulty(self, value):
        valid_difficulties = [choice[0] for choice in Question.DIFFICULTY_CHOICES]
        if value not in valid_difficulties:
            raise serializers.ValidationError(
                f"Invalid difficulty. Must be one of {valid_difficulties}"
            )
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        if not user:
            raise serializers.ValidationError("User must be authenticated to create a question")
        
        base_slug = slugify(validated_data['title'])
        slug = base_slug
        counter = 1
        while Question.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        validated_data['slug'] = slug
        validated_data['created_by'] = user
        return super().create(validated_data)

class QuestionListSerializer(serializers.ModelSerializer):
    created_by = serializers.SlugRelatedField(slug_field='username', read_only=True)
    question_id = serializers.UUIDField(read_only=True)
    examples = ExampleSerializer(many=True, read_only=True)
    solved_codes = SolvedCodeSerializer(many=True, read_only=True)
    test_cases = TestCaseSerializer(many=True, read_only=True)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Map tag values to display names for frontend
        tag_display = dict(Question.TAGS_CHOICES).get(representation['tags'], representation['tags'])
        representation['tags'] = tag_display
        return representation

    class Meta:
        model = Question
        fields = [
            'question_id',
            'title',
            'slug',
            'description',
            'difficulty',
            'tags',
            'is_validate',
            'created_by',
            'created_at',
            'updated_at',
            'examples',
            'solved_codes',
            'test_cases',
        ]
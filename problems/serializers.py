from rest_framework import serializers
from django.utils.text import slugify
from .models import Question, Example, SolvedCode, TestCase
import ast
import re

class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ['id', 'input_example', 'output_example', 'explanation']

class SolvedCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolvedCode
        fields = ['id', 'language', 'solution_code', 'created_at']

class TestCaseSerializer(serializers.ModelSerializer):
    formatted_input = serializers.SerializerMethodField()

    class Meta:
        model = TestCase
        fields = ['id', 'input_data', 'expected_output', 'is_sample', 'formatted_input']

    def validate_input_data(self, value):
        # Custom parser to handle input formats: "a,b", "[1,2,3]", "[1,2,3],4"
        try:
            parsed_data = self._parse_input(value)
            if not parsed_data:
                raise ValueError("Invalid input format")
            # Validate the parsed result as a Python literal
            if isinstance(parsed_data, (list, tuple, dict)):
                ast.literal_eval(str(parsed_data))
            # Ensure comma-separated inputs have exactly two values
            if isinstance(parsed_data, tuple) and len(parsed_data) != 2:
                raise ValueError("Input must be two comma-separated values (e.g., '15,5')")
            return value
        except (ValueError, SyntaxError):
            raise serializers.ValidationError("input_data must be a valid format (e.g., '12,34', '[1,2,3]', or '[1,2,3],4')")

    def _parse_input(self, value):
        # Remove leading/trailing whitespace
        value = value.strip()
        # Case 1: Comma-separated values (e.g., "12,34" -> (12, 34))
        if "," in value and not value.startswith("["):
            try:
                return tuple(ast.literal_eval(f"({value})"))
            except (ValueError, SyntaxError):
                raise serializers.ValidationError("Invalid input format for comma-separated values")
        # Case 2: Array with optional addend (e.g., "[1,2,3],4" -> ([1,2,3], 4))
        match = re.match(r"\[(.*?)\](?:,(\d+))?", value)
        if match:
            array_str = match.group(1)
            addend_str = match.group(2)
            array = ast.literal_eval(f"[{array_str}]") if array_str else []
            addend = ast.literal_eval(addend_str) if addend_str else None
            return (array, addend) if addend is not None else array
        # Fallback: Treat as raw string and attempt literal eval
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            raise serializers.ValidationError("Invalid input format")

    def get_formatted_input(self, obj):
        # Format input_data for user-friendly display
        try:
            parsed = self._parse_input(obj.input_data)
            if isinstance(parsed, dict):
                return ", ".join(f"{key} = {value}" for key, value in parsed.items())
            elif isinstance(parsed, tuple) and len(parsed) == 2 and isinstance(parsed[1], (int, float)):
                return f"a = {parsed[0]}, b = {parsed[1]}"
            elif isinstance(parsed, (list, tuple)):
                if obj.input_data.replace(" ", "").count(",") > 0 and not obj.input_data.startswith("["):
                    return ", ".join(str(x) for x in parsed)
                return f"arr = {parsed}"
            elif isinstance(parsed, (int, float, str, bool)):
                return str(parsed)
            else:
                return obj.input_data
        except (ValueError, SyntaxError):
            return obj.input_data

class QuestionInitialCreateSerializer(serializers.ModelSerializer):
    examples = ExampleSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = ['title', 'description', 'difficulty', 'tags', 'question_id', 'examples']
        read_only_fields = ['question_id']

    def validate_tags(self, value):
        valid_tags = [tag[0] for tag in Question.TAGS_CHOICES]
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
        
        examples_data = validated_data.pop('examples', [])
        base_slug = slugify(validated_data['title'])
        slug = base_slug
        counter = 1
        while Question.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        validated_data['slug'] = slug
        validated_data['created_by'] = user
        question = super().create(validated_data)
        
        for example_data in examples_data:
            Example.objects.create(question=question, **example_data)
        return question

    def update(self, instance, validated_data):
        examples_data = validated_data.pop('examples', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        base_slug = slugify(validated_data.get('title', instance.title))
        slug = base_slug
        counter = 1
        while Question.objects.filter(slug=slug).exclude(id=instance.id).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        instance.slug = slug
        instance.save()
        
        if examples_data is not None:
            instance.examples.all().delete()
            for example_data in examples_data:
                Example.objects.create(question=instance, **example_data)
        return instance

class QuestionListSerializer(serializers.ModelSerializer):
    created_by = serializers.SlugRelatedField(slug_field='username', read_only=True)
    question_id = serializers.UUIDField(read_only=True)
    examples = ExampleSerializer(many=True, read_only=True)
    solved_codes = SolvedCodeSerializer(many=True, read_only=True)
    test_cases = TestCaseSerializer(many=True, read_only=True)
    contribution_status = serializers.CharField(read_only=True, allow_null=True)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        tag_display = dict(Question.TAGS_CHOICES).get(representation['tags'], representation['tags'])
        representation['tags'] = tag_display
        contribution_status_display = dict(Question.CONTRIBUTION_STATUS_CHOICES).get(
            representation['contribution_status'], representation['contribution_status']
        )
        representation['contribution_status'] = contribution_status_display
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
            'is_contributed',
            'contribution_status',
            'created_at',
            'updated_at',
            'examples',
            'solved_codes',
            'test_cases',
        ]
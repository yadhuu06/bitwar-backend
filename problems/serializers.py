from rest_framework import serializers
from .models import Question
from django.utils.text import slugify

class QuestionInitialCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['title', 'description', 'difficulty', 'tags','question_id']  
        read_only_fields = ['question_id']

    def create(self, validated_data):
        print("the data:",validated_data)
        request = self.context.get('request')
        user = request.user if request else None
        validated_data['slug'] = slugify(validated_data['title'])
        validated_data['created_by'] = user
        return super().create(validated_data)

class QuestionListSerializer(serializers.ModelSerializer):
    created_by = serializers.SlugRelatedField(slug_field='username', read_only=True)
    question_id = serializers.UUIDField(read_only=True)

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
        ]
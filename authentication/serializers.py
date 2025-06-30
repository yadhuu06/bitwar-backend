from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.conf import settings
from .models import OTP, CustomUser

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=CustomUser.objects.all())]
    )
    username = serializers.CharField(
        required=True,
        validators=[UniqueValidator(queryset=CustomUser.objects.all())]
    )
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password']
        )

        OTP.objects.filter(email=validated_data['email']).delete()
        return user
class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        print("call came")
        model = OTP
        fields = ('email','otp_type')
        print ("fields",fields)

class UserSerializer(serializers.ModelSerializer):
    profile_picture = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'created_at',
            'profile_picture',
            'is_staff',
            'total_battles',
            'battles_won',
            'user_id'
        ]

    def validate_username(self, value):
        user = self.instance
        if user and user.username != value and CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username has already been taken")
        return value

    def validate_profile_picture(self, value):
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError("Profile picture must be a valid URL")
        return value

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        if 'profile_picture' in validated_data:
            instance.profile_picture = validated_data['profile_picture']
        instance.save()
        return instance
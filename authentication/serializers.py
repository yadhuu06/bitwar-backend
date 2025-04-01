from rest_framework import serializers
from rest_framework.validators import UniqueValidator
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
        # Clear OTP after successful registration
        OTP.objects.filter(email=validated_data['email']).delete()
        return user




class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ('email',)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('user_id', 'username', 'email', 'created_at', 'updated_at', 'auth_type')
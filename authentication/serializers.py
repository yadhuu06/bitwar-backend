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




from rest_framework import serializers
from .models import CustomUser  

from django.conf import settings
from rest_framework import serializers
from .models import CustomUser

from rest_framework import serializers
from django.conf import settings

class UserSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'created_at', 'profile_picture', 'is_staff']

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            path = str(obj.profile_picture)
            if path.startswith("http://") or path.startswith("https://"):
                return path  
            return f"{settings.MEDIA_URL}{path}"  
        return f"{settings.MEDIA_URL}profile_pics/default/coding_hacker.png"


    def validate_username(self, value):
        user = self.instance
        if user and user.username != value and CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username has already been taken")
        return value

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        if 'profile_picture' in validated_data:
            instance.profile_picture = validated_data['profile_picture']
        instance.save()
        return instance
from django.shortcuts import render

# Create your views here.
def room_view(request):
    print("hai")


from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Room
from .serializers import RoomCreateSerializer

class RoomCreateAPIView(generics.CreateAPIView):
    queryset = Room.objects.all()
    serializer_class = RoomCreateSerializer
    permission_classes = [IsAuthenticated]
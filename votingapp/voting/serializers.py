from rest_framework import serializers
from .models import VotingUser, Restaurant


class VotingUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = VotingUser
        fields = ["id", "username", "limit"]


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name"]


class VoteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

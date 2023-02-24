from datetime import date

from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from voting.models import Restaurant, VotingUser
from .serializers import RestaurantSerializer, VoteSerializer, VotingUserSerializer


@extend_schema_view()
class VotingUserViewSet(viewsets.ModelViewSet):
    queryset = VotingUser.objects.order_by("-pk").all()
    serializer_class = VotingUserSerializer


@extend_schema_view()
class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.order_by("-pk").all()
    serializer_class = RestaurantSerializer

    @extend_schema(
        description="Returns 3 restaurants with highest number of votes for a provided date",
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter by voting date; must be in ISO format",
                examples=[
                    OpenApiExample(
                        'Retrieve winners for January 1, 2023',
                        value="2023-01-31"
                    )
                ]
            )
        ],
        examples=[
            OpenApiExample(
                'Response example',
                value={
                    "count": 2,
                    "winners": [
                        {
                            "id": 58,
                            "name": "Test restaurant 1",
                            "total_votes": 12.50,
                            "num_voters": 10
                        },
                        {
                            "id": 341,
                            "name": "Test restaurant 2",
                            "total_votes": 5,
                            "num_voters": 5
                        }
                    ]
                },
                response_only=True,
            )
        ]
    )
    @action(methods=["get"], detail=False, url_path="winners")
    def get_winners(self, request):
        try:
            date_param = date.fromisoformat(
                request.query_params.get("date", date.today().isoformat())
            )
        except (ValueError, TypeError) as e:
            raise APIException(
                detail="Date query parameter is required and must be in ISO format, i.e. yyyy-mm-dd",
                code="422",
            )
        winners = (
            Restaurant.objects.filter(votes__date=date_param)
            .annotate(
                total_votes=Sum("votes__weight", filter=Q(votes__date=date_param)),
                num_voters=Count(
                    "votes__voting_user",
                    distinct=True,
                    filter=Q(votes__date=date_param),
                ),
            )
            .order_by("-total_votes", "-num_voters")
            .values()[:3]
        )
        winners_list = list(winners)
        return Response({'count': len(winners_list), 'winners': winners_list}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Vote for a restaurant",
        parameters=[
            OpenApiParameter(
                name="restaurant_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Restaurant id to vote for",
                examples=[
                    OpenApiExample(
                        'Restaurant id parameter example',
                        value=21
                    )
                ]
            )
        ],
        examples=[
            OpenApiExample(
                'Request example',
                value={"user_id": 120},
                request_only=True
            ),
            OpenApiExample(
                'Response example',
                value={"restaurant_id": 21, "user_id": 120, "remaining_limit": 3},
                response_only=True
            )
        ],
    )
    @action(methods=["post"], detail=True)
    def vote(self, request, pk=None):
        serializer = VoteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user_id = serializer.validated_data["user_id"]

        if not user_id or int(user_id) <= 0:
            raise APIException(
                detail="User_id is required and must be a positive integer.",
                code="422",
            )

        if not VotingUser.objects.filter(id=user_id).exists():
            raise APIException(
                detail="User corresponding to user_id not found.",
                code="422",
            )

        restaurant = get_object_or_404(Restaurant, id=pk)
        voting_user = VotingUser.objects.get(id=user_id)
        voting_date = date.today()
        total_votes = voting_user.total_votes(voting_user, voting_date)

        if total_votes >= voting_user.limit:
            return Response(
                {"detail": "You have exceeded your voting limit for today."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        restaurant.add_vote(total_votes, voting_user, voting_date)
        return Response(
            {
                "restaurant_id": restaurant.pk,
                "user_id": voting_user.pk,
                "remaining_limit": voting_user.limit - total_votes - 1,
            },
            status=status.HTTP_202_ACCEPTED,
        )

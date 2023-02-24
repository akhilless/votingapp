from datetime import date, timedelta
import json
from random import randrange

import pytest
import time_machine
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient

from voting.viewsets import RestaurantViewSet


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def api_user(db):
    return User.objects.create_superuser(
        "votingapp", "votingapp@votingapp.com", password="12345678"
    )


@pytest.mark.django_db
def test_create_and_retrieve_restaurant(api_user):
    factory = APIRequestFactory()
    restaurant_endpoint = reverse("restaurant-list")
    restaurant_names = ["Test restaurant 1", "Test restaurant 2", "Test restaurant 3"]

    for name in restaurant_names:
        create_request = factory.post(
            restaurant_endpoint, {"name": name}, format="json"
        )
        force_authenticate(create_request, user=api_user)
        view = RestaurantViewSet.as_view({"post": "create"})
        response = view(create_request)
        assert status.is_success(response.status_code)

    list_request = factory.get(restaurant_endpoint)
    force_authenticate(list_request, user=api_user)
    view = RestaurantViewSet.as_view({"get": "list"})
    response = view(list_request)
    response.render()
    content = json.loads(response.content)
    assert status.is_success(response.status_code)
    assert content["count"] == len(restaurant_names)

    assert set(map(lambda r: r["name"], content["results"])) == set(restaurant_names)

    random_number = randrange(0, len(restaurant_names))
    random_restaurant = content["results"][random_number]
    retrieve_request = factory.get(restaurant_endpoint)
    force_authenticate(retrieve_request, user=api_user)
    view = RestaurantViewSet.as_view({"get": "retrieve"})
    response = view(retrieve_request, pk=random_restaurant["id"])
    response.render()
    assert status.is_success(response.status_code)
    assert json.loads(response.content) == {
        "id": random_restaurant["id"],
        "name": random_restaurant["name"],
    }


@pytest.fixture
def setup_vote_tests(db, client, api_user):
    client.force_authenticate(user=api_user)
    voting_user_ids = []
    for i in range(0, 3):
        voting_user_response = client.post(
            reverse("votinguser-list"),
            {"username": f"test_username {i}", "limit": 5},
            format="json",
        )
        assert status.is_success(voting_user_response.status_code)
        voting_user_id = voting_user_response.data["id"]
        voting_user_limit = voting_user_response.data["limit"]
        assert voting_user_limit == 5
        voting_user_ids.append(voting_user_id)

    restaurant_ids = []
    for i in range(0, 5):
        restaurant_response = client.post(
            reverse("restaurant-list"), {"name": f"Test restaurant {i}"}
        )
        assert status.is_success(restaurant_response.status_code)
        restaurant_ids.append(restaurant_response.data["id"])

    return voting_user_ids, restaurant_ids, voting_user_limit


@pytest.mark.django_db
def test_voting_limit(client, setup_vote_tests):
    user_ids, restaurant_ids, limit = setup_vote_tests
    num_of_restaurants = len(restaurant_ids) - 1
    user_id = user_ids[0]

    with time_machine.travel(date.today() - timedelta(days=1)):
        for i in range(0, limit):
            random_restaurant = randrange(0, num_of_restaurants)
            response = client.post(
                reverse(
                    "restaurant-vote", kwargs={"pk": restaurant_ids[random_restaurant]}
                ),
                data={"user_id": user_id},
                format="json",
            )
            assert status.is_success(response.status_code)
            assert response.data["remaining_limit"] == limit - i - 1

        random_restaurant = randrange(0, num_of_restaurants)
        response = client.post(
            reverse(
                "restaurant-vote", kwargs={"pk": restaurant_ids[random_restaurant]}
            ),
            data={"user_id": user_id},
            format="json",
        )
        assert status.HTTP_429_TOO_MANY_REQUESTS == response.status_code
        assert (
            response.data["detail"] == "You have exceeded your voting limit for today."
        )

    # next day the limits should be reset, so the user should be able to vote again
    random_restaurant = randrange(0, num_of_restaurants)
    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_ids[random_restaurant]}),
        data={"user_id": user_id},
        format="json",
    )
    assert status.is_success(response.status_code)
    assert response.data["remaining_limit"] == limit - 1


@pytest.mark.django_db
def test_winners_counts_only_votes_on_the_same_day(client, setup_vote_tests):
    user_ids, restaurant_ids, limit = setup_vote_tests
    restaurant_id = restaurant_ids[0]

    with time_machine.travel(date.today() - timedelta(days=1)):
        for i in range(0, 4):
            response = client.post(
                reverse("restaurant-vote", kwargs={"pk": restaurant_id}),
                data={"user_id": user_ids[0]},
                format="json",
            )
            assert status.is_success(response.status_code)

    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_id}),
        data={"user_id": user_ids[0]},
        format="json",
    )
    assert status.is_success(response.status_code)

    response = client.get(
        reverse("restaurant-get-winners"),
        data={"date": (date.today() - timedelta(days=1)).isoformat()},
    )
    assert status.is_success(response.status_code)
    winners = response.data["winners"]
    assert response.data["count"] == 1
    assert len(winners) == 1
    assert winners[0]["id"] == restaurant_id
    assert winners[0]["total_votes"] == 2.0
    assert winners[0]["num_voters"] == 1

    response = client.get(
        reverse("restaurant-get-winners"), data={"date": date.today().isoformat()}
    )
    winners = response.data["winners"]
    assert response.data["count"] == 1
    assert len(winners) == 1
    assert winners[0]["id"] == restaurant_id
    assert winners[0]["total_votes"] == 1.0
    assert winners[0]["num_voters"] == 1


@pytest.mark.django_db
def test_winners_restaurant_with_more_votes_wins(client, setup_vote_tests):
    user_ids, restaurant_ids, limit = setup_vote_tests

    for i in range(0, 4):
        response = client.post(
            reverse("restaurant-vote", kwargs={"pk": restaurant_ids[1]}),
            data={"user_id": user_ids[0]},
            format="json",
        )
        assert status.is_success(response.status_code)

    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_ids[0]}),
        data={"user_id": user_ids[0]},
        format="json",
    )
    assert status.is_success(response.status_code)

    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_ids[0]}),
        data={"user_id": user_ids[1]},
        format="json",
    )
    assert status.is_success(response.status_code)

    response = client.get(
        reverse("restaurant-get-winners"), data={"date": date.today().isoformat()}
    )
    assert status.is_success(response.status_code)
    winners = response.data["winners"]
    assert response.data["count"] == 2
    assert len(winners) == 2
    assert winners[0]["id"] == restaurant_ids[1]
    assert winners[0]["total_votes"] == 2.0
    assert winners[0]["num_voters"] == 1

    assert winners[1]["id"] == restaurant_ids[0]
    assert winners[1]["total_votes"] == 1.25
    assert winners[1]["num_voters"] == 2


@pytest.mark.django_db
def test_winners_when_votes_are_equal_restaurant_with_more_voters_wins(
    client, setup_vote_tests
):
    user_ids, restaurant_ids, limit = setup_vote_tests

    for i in range(0, 4):
        response = client.post(
            reverse("restaurant-vote", kwargs={"pk": restaurant_ids[0]}),
            data={"user_id": user_ids[0]},
            format="json",
        )
        assert status.is_success(response.status_code)

    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_ids[1]}),
        data={"user_id": user_ids[1]},
        format="json",
    )
    assert status.is_success(response.status_code)

    response = client.post(
        reverse("restaurant-vote", kwargs={"pk": restaurant_ids[1]}),
        data={"user_id": user_ids[2]},
        format="json",
    )
    assert status.is_success(response.status_code)

    response = client.get(
        reverse("restaurant-get-winners"), data={"date": date.today().isoformat()}
    )
    assert status.is_success(response.status_code)
    winners = response.data["winners"]
    assert response.data["count"] == 2
    assert len(winners) == 2
    assert winners[0]["id"] == restaurant_ids[1]
    assert winners[0]["total_votes"] == 2.0
    assert winners[0]["num_voters"] == 2

    assert winners[1]["id"] == restaurant_ids[0]
    assert winners[1]["total_votes"] == 2.0
    assert winners[1]["num_voters"] == 1

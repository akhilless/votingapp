from django.db import models


class VotingUser(models.Model):
    username = models.CharField(max_length=120, unique=True)
    limit = models.PositiveIntegerField()

    def total_votes(self, voting_user, voting_date):
        return self.votes.filter(voting_user=voting_user, date=voting_date).count()


class Restaurant(models.Model):
    name = models.CharField(max_length=200)

    def add_vote(self, total_votes, voting_user, voting_date):
        def calculate_vote_weight(total_count):
            if not total_count:
                return 1
            elif total_count == 1:
                return 0.5
            else:
                return 0.25

        self.votes.create(
            voting_user=voting_user,
            weight=calculate_vote_weight(total_votes),
            date=voting_date,
        )


class Vote(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="votes"
    )
    voting_user = models.ForeignKey(
        VotingUser, on_delete=models.CASCADE, related_name="votes"
    )
    weight = models.FloatField()
    date = models.DateField()

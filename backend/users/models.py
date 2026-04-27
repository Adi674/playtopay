from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_MERCHANT = "merchant"
    ROLE_REVIEWER = "reviewer"
    ROLE_CHOICES = [
        (ROLE_MERCHANT, "Merchant"),
        (ROLE_REVIEWER, "Reviewer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MERCHANT)
    phone = models.CharField(max_length=20, blank=True)

    def is_merchant(self):
        return self.role == self.ROLE_MERCHANT

    def is_reviewer(self):
        return self.role == self.ROLE_REVIEWER

    def __str__(self):
        return f"{self.username} ({self.role})"

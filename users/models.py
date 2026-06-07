from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    def block(self):
        self.is_blocked = True
        self.is_active = False
        self.save()

    def __str__(self):
        return self.username

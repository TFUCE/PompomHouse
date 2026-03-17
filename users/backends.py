from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailRoleBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, role=None, email=None, **kwargs):
        email = email if email is not None else username

        if email is None or password is None or role is None:
            return None

        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


# Two account roles are enough for this project, so the choices stay simple.
class UserRole(models.TextChoices):
    TENANT = 'tenant', 'Tenant'
    LANDLORD = 'landlord', 'Landlord'


# We keep email visible to users, but store a role-based username internally.
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email=None, password=None, username=None, **extra_fields):
        if not email:
            email = username
        if not email:
            raise ValueError('An email address is required.')

        role = extra_fields.get('role')
        if not role:
            raise ValueError('A role is required.')

        email = email.strip()
        user = self.model(
            email=email,
            username=self.model.build_username(email, role),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        username = extra_fields.pop('username', None)
        return self._create_user(email=email, password=password, username=username, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.LANDLORD)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email=email, password=password, username=username, **extra_fields)


# Hobbies are reused in sign-up, account editing, and match scoring.
class Hobby(models.Model):
    category = models.CharField(max_length=50)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(fields=['category', 'name'], name='unique_hobby_category_name'),
        ]

    def __str__(self):
        return f'{self.category}: {self.name}'


# One email can exist once per role, so tenant + landlord can share an address.
class User(AbstractUser):
    username = models.CharField(max_length=320, unique=True, editable=False)
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=UserRole.choices)
    joined_at = models.DateTimeField(default=timezone.now)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    hobbies = models.ManyToManyField(Hobby, related_name='users', blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['email', 'role'], name='unique_email_per_role'),
        ]

    @staticmethod
    def build_username(email, role):
        return f'{role}__{email}'

    @property
    def is_tenant(self):
        return self.role == UserRole.TENANT

    @property
    def is_landlord(self):
        return self.role == UserRole.LANDLORD

    @property
    def sidebar_hobbies(self):
        return self.hobbies.all()[:6]

    def __str__(self):
        return f'{self.email} ({self.role})'


# Extra tenant-only data lives outside the main user model to keep it lighter.
class SeekerProfile(models.Model):
    GENDER_CHOICES = [
        ('', 'Prefer not to say'),
        ('female', 'Female'),
        ('male', 'Male'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seeker_profile')
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    budget_min = models.PositiveIntegerField(blank=True, null=True)
    budget_max = models.PositiveIntegerField(blank=True, null=True)
    move_in_date = models.DateField(blank=True, null=True)
    is_smoker = models.BooleanField(default=False)
    has_pet = models.BooleanField(default=False)
    about = models.TextField(blank=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f'SeekerProfile({self.user.email})'

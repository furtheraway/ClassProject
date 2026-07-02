from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

PRIVATE_FIELD_HELP = "Private: visible only to you and the instructor."


class UserManager(BaseUserManager):
    """Creates users keyed by email instead of username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Email-login user with the class profile fields (SPEC §3.1).

    Personal fields are blank-able at the database level so the instructor
    account can exist without them; the registration form makes them required
    for students. The public/private split is enforced in the profile template
    and admin, per SPEC §3.1.
    """

    class StudyYear(models.IntegerChoices):
        YEAR_1 = 1, "Year 1"
        YEAR_2 = 2, "Year 2"
        YEAR_3 = 3, "Year 3"
        YEAR_4 = 4, "Year 4"
        YEAR_5_PLUS = 5, "Year 5+"

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        UNDISCLOSED = "N", "Prefer not to say"

    # Remove AbstractUser's username/first/last — email is the identifier.
    username = None
    first_name = None
    last_name = None

    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=100)

    # Public profile fields
    department = models.CharField(max_length=100, blank=True)
    major = models.CharField(max_length=100, blank=True)
    languages = models.CharField(
        "languages spoken",
        max_length=200,
        blank=True,
        help_text="Comma-separated, e.g. “Chinese, English”.",
    )
    interests = models.TextField(blank=True)
    skills = models.TextField(blank=True)

    # Private fields — self + instructor only (SPEC §3.1)
    birth_year = models.PositiveIntegerField(
        "year of birth",
        null=True,
        blank=True,
        validators=[MinValueValidator(1950), MaxValueValidator(2015)],
        help_text=PRIVATE_FIELD_HELP,
    )
    study_year = models.PositiveSmallIntegerField(
        choices=StudyYear.choices,
        null=True,
        blank=True,
        help_text=PRIVATE_FIELD_HELP,
    )
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        help_text=PRIVATE_FIELD_HELP,
    )
    height_cm = models.PositiveIntegerField(
        "height (cm)",
        null=True,
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(250)],
        help_text=PRIVATE_FIELD_HELP,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]  # prompted by createsuperuser

    objects = UserManager()

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    # AbstractUser's implementations use first_name/last_name, which we removed.
    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name

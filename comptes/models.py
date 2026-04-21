from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator

class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        phone_number = str(phone_number).strip()

        extra_fields.setdefault("is_active", True)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        # superuser peut ne pas avoir d’organisation
        return self.create_user(phone_number, password, **extra_fields)


class Utilisateur(AbstractUser):
    username = None  # on enlève username

    phone_number = models.CharField(
        max_length=9,
        unique=True,
        validators=[RegexValidator(r"^\d{9}$", "Le téléphone doit contenir exactement 9 chiffres.")],
        verbose_name="Téléphone"
    )

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.PROTECT,
        null=True, blank=True,  # ✅ superuser autorisé
        related_name="utilisateurs"
    )

    ROLE_CHOICES = (
        ("superadmin", "Super Administrateur"),
        ("admin_org", "Admin Organisation"),
        ("manager", "Manager"),
        ("agent", "Agent"),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="agent")

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    def save(self, *args, **kwargs):
        # Si superuser → role superadmin
        if self.is_superuser:
            self.role = "superadmin"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone_number

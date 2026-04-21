from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur

    # Si tu n'as pas username (phone_number en identifiant)
    ordering = ("phone_number",)
    list_display = ("phone_number", "role", "organisation", "is_active", "is_staff", "is_superuser")
    list_filter = ("role", "organisation", "is_active", "is_staff", "is_superuser")
    search_fields = ("phone_number", "email", "first_name", "last_name")
    list_select_related = ("organisation",)

    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        (_("Informations"), {"fields": ("first_name", "last_name", "email", "organisation", "role")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone_number", "password1", "password2", "organisation", "role", "is_active", "is_staff", "is_superuser"),
        }),
    )

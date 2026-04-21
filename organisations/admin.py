from django.contrib import admin
from .models import Organisation


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)
    ordering = ("nom",)

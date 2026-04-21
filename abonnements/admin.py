from django.contrib import admin
from django.utils import timezone

from .models import Plan, Abonnement


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "prix", "max_sites", "max_utilisateurs", "actif")
    list_filter = ("actif",)
    search_fields = ("nom",)
    ordering = ("nom",)
    list_per_page = 25


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ("id", "organisation", "plan", "date_debut", "date_fin", "est_actif", "statut")
    list_filter = ("est_actif", "plan", "plan__actif")
    search_fields = ("organisation__nom", "plan__nom")
    list_select_related = ("organisation", "plan")
    ordering = ("-date_fin",)
    list_per_page = 25

    @admin.display(description="Statut")
    def statut(self, obj: Abonnement):
        today = timezone.now().date()

        if not obj.est_actif:
            return "Inactif"
        if obj.date_fin < today:
            return "Expiré"
        if obj.date_debut > today:
            return "À venir"
        return "Actif"

from django.contrib import admin
from django.utils.html import format_html

from .models import Site, Zone, AffectationPrestataire


# =========================
# SITE
# =========================
@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "organisation", "adresse", "actif")
    list_filter = ("organisation", "actif")
    search_fields = ("nom", "adresse", "organisation__nom")
    list_select_related = ("organisation",)
    ordering = ("organisation__nom", "nom")
    list_per_page = 25


# =========================
# ZONE
# =========================
@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "site", "organisation", "actif")
    list_filter = ("actif", "site__organisation", "site")
    search_fields = ("nom", "site__nom", "site__organisation__nom")
    list_select_related = ("site", "site__organisation")
    ordering = ("site__organisation__nom", "site__nom", "nom")
    list_per_page = 25

    @admin.display(description="Organisation")
    def organisation(self, obj):
        return obj.site.organisation


# =========================
# AFFECTATION PRESTATAIRE
# =========================
@admin.register(AffectationPrestataire)
class AffectationPrestataireAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "prestataire",
        "site",
        "organisation",
        "zones_affichees",
        "actif",
        "cree_le",
    )
    list_filter = ("actif", "site__organisation", "site", "prestataire")
    search_fields = (
        "prestataire__nom",
        "site__nom",
        "site__organisation__nom",
        "zones__nom",
    )
    list_select_related = ("site", "site__organisation", "prestataire")
    ordering = ("-cree_le",)
    list_per_page = 25

    filter_horizontal = ("zones",)  # Interface propre pour M2M

    @admin.display(description="Organisation")
    def organisation(self, obj):
        return obj.site.organisation

    @admin.display(description="Zones concernées")
    def zones_affichees(self, obj):
        """
        Si aucune zone => agit sur tout le site
        Sinon => affiche la liste des zones
        """
        zones = list(obj.zones.all().values_list("nom", flat=True))
        if not zones:
            return format_html(
                "<span style='color:#0b3a6a;font-weight:700'>Tout le site</span>"
            )
        return ", ".join(zones)

from django.contrib import admin
from .models import DomaineIntervention, Prestataire, DocumentPrestataire, AgentPrestataire



# =============================
# Inline Documents Prestataire
# =============================
class DocumentPrestataireInline(admin.TabularInline):
    model = DocumentPrestataire
    extra = 1
    fields = (
        "type_document",
        "titre",
        "fichier",
        "date_emission",
        "date_expiration",
        "actif",
    )
    readonly_fields = ("date_upload",)
    show_change_link = True


# =============================
# Domaine Intervention Admin
# =============================
@admin.register(DomaineIntervention)
class DomaineInterventionAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "organisation",
        "actif",
    )

    list_filter = (
        "organisation",
        "actif",
    )

    search_fields = (
        "nom",
        "organisation__nom",
    )

    ordering = ("nom",)

    list_per_page = 25


# =============================
# Prestataire Admin
# =============================
@admin.register(Prestataire)
class PrestataireAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "organisation",
        "domaine",
        "telephone",
        "email",
        "actif",
        "date_creation",
    )

    list_filter = (
        "organisation",
        "domaine",
        "actif",
        "date_creation",
    )

    search_fields = (
        "nom",
        "telephone",
        "email",
        "organisation__nom",
        "domaine__nom",
    )

    ordering = ("nom",)

    readonly_fields = ("date_creation",)

    list_per_page = 25

    inlines = [DocumentPrestataireInline]


# =============================
# Document Prestataire Admin
# =============================
@admin.register(DocumentPrestataire)
class DocumentPrestataireAdmin(admin.ModelAdmin):

    list_display = (
        "prestataire",
        "type_document",
        "titre",
        "date_emission",
        "date_expiration",
        "actif",
        "date_upload",
    )

    list_filter = (
        "type_document",
        "actif",
        "date_emission",
        "date_expiration",
        "date_upload",
    )

    search_fields = (
        "prestataire__nom",
        "titre",
        "description",
    )

    readonly_fields = (
        "date_upload",
    )

    ordering = ("-date_upload",)

    list_per_page = 25


# =============================
# Agent Prestataire Admin
# =============================
@admin.register(AgentPrestataire)
class AgentPrestataireAdmin(admin.ModelAdmin):
    # ✅ obligatoire pour autocomplete_fields dans l'app permis
    search_fields = (
        "nom",
        "prenom",
        "telephone",
        "prestataire__nom",
    )

    list_display = (
        "nom",
        "prenom",
        "telephone",
        "prestataire",
        "actif",
    )

    list_filter = (
        "prestataire",
        "actif",
    )

    ordering = ("nom", "prenom")
    list_per_page = 25

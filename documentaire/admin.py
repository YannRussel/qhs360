from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Document,
    DocumentType,
    Processus,
    DocumentVersion,
    DocumentAccessLog,
    DocumentNotification,
)


# ============================================================
# TYPES DE DOCUMENTS
# ============================================================
@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "actif")
    list_filter = ("organisation", "actif")
    search_fields = ("nom",)
    ordering = ("nom",)


# ============================================================
# PROCESSUS
# ============================================================
@admin.register(Processus)
class ProcessusAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "actif")
    list_filter = ("organisation", "actif")
    search_fields = ("nom",)
    ordering = ("nom",)


# ============================================================
# INLINE VERSIONS (dans Document)
# ============================================================
class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    fields = ("version", "fichier", "commentaire", "cree_par", "cree_le", "statut_snapshot")
    readonly_fields = ("cree_par", "cree_le", "statut_snapshot")
    ordering = ("-cree_le",)


# ============================================================
# DOCUMENTS
# ============================================================
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "titre",
        "type_document",
        "processus",
        "site",
        "statut_badge",
        "version_actuelle",
        "confidentialite",
        "proprietaire",
        "cree_le",
        "modifie_le",
    )

    list_filter = (
        "organisation",
        "type_document",
        "processus",
        "site",
        "statut",
        "confidentialite",
        "cree_le",
    )

    search_fields = (
        "code",
        "titre",
        "mots_cles",
        "type_document__nom",
        "processus__nom",
        "site__nom",
    )

    readonly_fields = ("cree_le", "modifie_le", "version_courante")
    autocomplete_fields = ("proprietaire",)
    ordering = ("-modifie_le", "-cree_le")

    inlines = [DocumentVersionInline]

    fieldsets = (
        ("Informations générales", {
            "fields": (
                "organisation",
                "code",
                "titre",
                "type_document",
                "processus",
                "site",
                "mots_cles",
            )
        }),
        ("Statut & Sécurité", {
            "fields": (
                "statut",
                "confidentialite",
                "proprietaire",
            )
        }),
        ("Révision & Audit", {
            "fields": (
                "date_prochaine_revision",
                "cree_le",
                "modifie_le",
            )
        }),
        ("Version courante", {
            "fields": ("version_courante",)
        }),
    )

    # ---- Affichages ----
    def statut_badge(self, obj):
        colors = {
            "brouillon": "#f59e0b",
            "validation": "#0ea5e9",
            "approuve": "#16a34a",
            "obsolete": "#64748b",
        }
        color = colors.get(obj.statut, "#999999")
        return format_html(
            '<span style="background:{};color:#fff;padding:4px 10px;border-radius:12px;font-weight:900;">{}</span>',
            color,
            obj.get_statut_display(),
        )
    statut_badge.short_description = "Statut"

    def version_actuelle(self, obj):
        return obj.version_courante.version if obj.version_courante else "-"
    version_actuelle.short_description = "Version"


# ============================================================
# VERSIONS (vue séparée)
# ============================================================
@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("document", "version", "cree_par", "cree_le", "statut_snapshot")
    list_filter = ("cree_le", "statut_snapshot")
    search_fields = ("document__code", "document__titre", "version")
    ordering = ("-cree_le",)


# ============================================================
# LOGS (DocumentAccessLog)  ✅ cree_le au lieu de created_at
# ============================================================
@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "action", "ip", "cree_le")
    list_filter = ("action", "cree_le")
    search_fields = ("document__code", "document__titre", "details", "user__username", "user__phone_number")
    ordering = ("-cree_le",)
    readonly_fields = [f.name for f in DocumentAccessLog._meta.fields]


# ============================================================
# NOTIFICATIONS
# ============================================================
@admin.register(DocumentNotification)
class DocumentNotificationAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "lu", "cree_le")
    list_filter = ("lu", "cree_le")
    search_fields = ("document__code", "document__titre", "user__username", "user__phone_number")
    ordering = ("-cree_le",)
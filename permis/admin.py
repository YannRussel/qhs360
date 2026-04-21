from django.contrib import admin
from django.utils import timezone
from django.db.models import Count

from .models import (
    Formation,
    TypeHabilitation,
    AgentHabilitation,
    SessionFormation,
    ParticipantSession,
)

# =========================
# Inlines
# =========================
class ParticipantSessionInline(admin.TabularInline):
    model = ParticipantSession
    extra = 0
    autocomplete_fields = ["agent"]  # nécessite AgentPrestataire enregistré dans prestataire/admin.py
    fields = ("agent", "present", "valide", "note")


# =========================
# Formation
# =========================
@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "actif")
    list_filter = ("actif", "organisation")
    search_fields = ("nom", "description", "organisation__nom")
    list_select_related = ("organisation",)
    ordering = ("nom",)


# =========================
# TypeHabilitation
# =========================
@admin.register(TypeHabilitation)
class TypeHabilitationAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "actif", "nb_formations")
    list_filter = ("actif", "organisation")
    search_fields = ("nom", "description", "organisation__nom", "formations_requises__nom")
    filter_horizontal = ("formations_requises",)
    list_select_related = ("organisation",)
    ordering = ("nom",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_nb_formations=Count("formations_requises", distinct=True))

    @admin.display(description="Formations", ordering="_nb_formations")
    def nb_formations(self, obj):
        return getattr(obj, "_nb_formations", 0)


# =========================
# AgentHabilitation
# =========================
@admin.register(AgentHabilitation)
class AgentHabilitationAdmin(admin.ModelAdmin):
    list_display = (
        "agent",
        "type_habilitation",
        "date_obtention",
        "date_expiration",
        "actif",
        "valide_aujourdhui",
    )
    list_filter = ("actif", "type_habilitation__organisation", "type_habilitation")
    search_fields = (
        "agent__nom", "agent__prenom", "agent__telephone",
        "type_habilitation__nom",
        "type_habilitation__organisation__nom",
    )
    autocomplete_fields = ["agent", "type_habilitation"]
    date_hierarchy = "date_obtention"
    ordering = ("-date_obtention",)

    @admin.display(boolean=True, description="Valide aujourd'hui")
    def valide_aujourdhui(self, obj):
        return obj.est_valide_le(timezone.now().date())


# =========================
# SessionFormation
# =========================
@admin.action(description="✅ Terminer la session (générer habilitations)")
def terminer_sessions(modeladmin, request, queryset):
    for s in queryset:
        s.terminer()

@admin.register(SessionFormation)
class SessionFormationAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "organisation",
        "formation",
        "date_debut",
        "duree_minutes",
        "statut",
        "nb_intervenants",
        "nb_participants",
    )
    list_filter = ("statut", "organisation", "formation")
    search_fields = ("formation__nom", "titre", "lieu", "organisation__nom", "notes")
    autocomplete_fields = ("organisation", "formation")
    filter_horizontal = ("intervenants",)
    date_hierarchy = "date_debut"
    ordering = ("-date_debut",)
    actions = [terminer_sessions]
    inlines = [ParticipantSessionInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _nb_intervenants=Count("intervenants", distinct=True),
            _nb_participants=Count("participants", distinct=True),
        )

    @admin.display(description="Intervenants", ordering="_nb_intervenants")
    def nb_intervenants(self, obj):
        return getattr(obj, "_nb_intervenants", 0)

    @admin.display(description="Participants", ordering="_nb_participants")
    def nb_participants(self, obj):
        return getattr(obj, "_nb_participants", 0)


# =========================
# ParticipantSession
# =========================
@admin.register(ParticipantSession)
class ParticipantSessionAdmin(admin.ModelAdmin):
    list_display = ("session", "agent", "present", "valide", "note")
    list_filter = ("present", "valide", "session__organisation", "session__formation")
    search_fields = ("agent__nom", "agent__prenom", "session__formation__nom", "session__titre")
    autocomplete_fields = ("session", "agent")
    ordering = ("-session__date_debut",)


# permis/admin.py

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    TypePermis,
    Intervention,
    PermisDelivre,
    QuestionPermis,
    ReponsePermis,
)


# -----------------------------
# Inlines
# -----------------------------

class QuestionPermisInline(admin.TabularInline):
    model = QuestionPermis
    extra = 1
    fields = ("ordre", "texte", "type_reponse", "choix", "obligatoire", "actif")
    ordering = ("ordre", "id")
    show_change_link = True


class ReponsePermisInline(admin.TabularInline):
    model = ReponsePermis
    extra = 0
    fields = ("question", "valeur_bool", "valeur_choice", "valeur_number", "valeur_text", "remarque", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("question__ordre", "id")
    show_change_link = True


class PermisDelivreInline(admin.TabularInline):
    model = PermisDelivre
    extra = 0
    fields = ("agent", "type_permis", "statut", "actif", "date_delivrance", "valide_le")
    readonly_fields = ("date_delivrance", "valide_le")
    show_change_link = True


# -----------------------------
# Admin: TypePermis
# -----------------------------

@admin.register(TypePermis)
class TypePermisAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "actif", "habilitations_count")
    list_filter = ("organisation", "actif")
    search_fields = ("nom", "description", "organisation__nom")
    filter_horizontal = ("habilitations_requises",)
    inlines = [QuestionPermisInline]
    ordering = ("organisation", "nom")

    def habilitations_count(self, obj):
        return obj.habilitations_requises.count()
    habilitations_count.short_description = "Habilitations requises"


# -----------------------------
# Admin: Intervention
# -----------------------------

@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("titre", "organisation", "statut", "date_debut", "date_fin", "permis_requis_count", "agents_count")
    list_filter = ("organisation", "statut")
    search_fields = ("titre", "description", "lieu", "organisation__nom")
    filter_horizontal = ("permis_requis", "agents")
    date_hierarchy = "date_debut"
    inlines = [PermisDelivreInline]
    ordering = ("-date_debut",)

    def permis_requis_count(self, obj):
        return obj.permis_requis.count()
    permis_requis_count.short_description = "Permis requis"

    def agents_count(self, obj):
        return obj.agents.count()
    agents_count.short_description = "Agents"


# -----------------------------
# Admin: PermisDelivre
# -----------------------------

@admin.register(PermisDelivre)
class PermisDelivreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organisation",
        "intervention",
        "agent_display",
        "type_permis",
        "statut_badge",
        "actif",
        "date_delivrance",
        "valide_le",
    )
    list_filter = ("organisation", "statut", "actif", "type_permis")
    search_fields = (
        "intervention__titre",
        "type_permis__nom",
        "agent__nom",
        "agent__prenom",
        "agent__prestataire__nom",
        "organisation__nom",
    )
    date_hierarchy = "date_delivrance"
    readonly_fields = ("date_delivrance",)
    inlines = [ReponsePermisInline]
    ordering = ("-date_delivrance",)

    def agent_display(self, obj):
        # évite crash si prenom absent
        prenom = getattr(obj.agent, "prenom", "")
        return f"{obj.agent.nom} {prenom}".strip()
    agent_display.short_description = "Agent"

    def statut_badge(self, obj):
        if obj.statut == "valide":
            return format_html('<span style="padding:2px 8px;border-radius:10px;background:#dcfce7;color:#166534;font-weight:700;">VALIDÉ</span>')
        if obj.statut == "refuse":
            return format_html('<span style="padding:2px 8px;border-radius:10px;background:#fee2e2;color:#991b1b;font-weight:700;">REFUSÉ</span>')
        return format_html('<span style="padding:2px 8px;border-radius:10px;background:#fef3c7;color:#92400e;font-weight:700;">EN ATTENTE</span>')
    statut_badge.short_description = "Statut"


# -----------------------------
# Admin: QuestionPermis (optionnel en dehors de TypePermis)
# -----------------------------

@admin.register(QuestionPermis)
class QuestionPermisAdmin(admin.ModelAdmin):
    list_display = ("type_permis", "ordre", "texte", "type_reponse", "obligatoire", "actif")
    list_filter = ("type_permis", "type_reponse", "obligatoire", "actif")
    search_fields = ("texte", "type_permis__nom")
    ordering = ("type_permis", "ordre", "id")


# -----------------------------
# Admin: ReponsePermis (optionnel)
# -----------------------------

@admin.register(ReponsePermis)
class ReponsePermisAdmin(admin.ModelAdmin):
    list_display = ("permis", "question", "valeur_bool", "valeur_choice", "valeur_number", "created_at")
    list_filter = ("question__type_reponse", "question__type_permis")
    search_fields = ("permis__intervention__titre", "question__texte")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

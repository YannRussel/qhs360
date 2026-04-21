from django.urls import path
from . import views

app_name = "permis"

urlpatterns = [
    # ====== FORMATIONS ======
    path("formations-habilitations", views.formation_habilitation, name="form-hab"),
    path("formations/dashboard/", views.formation_dashboard, name="formation_dashboard"),

    path("formations/", views.formation_liste, name="formation_liste"),
    path("formations/nouvelle/", views.formation_creer, name="formation_creer"),
    path("formations/<int:pk>/modifier/", views.formation_modifier, name="formation_modifier"),
    path("formations/<int:pk>/supprimer/", views.formation_supprimer, name="formation_supprimer"),
    # ====================== Seesion des Formations =========================
    path("formations/sessions/nouvelle/", views.session_creer, name="session_creer"),
    path("formations/sessions/", views.session_liste, name="session_liste"),
    path("formations/sessions/nouvelle/", views.session_creer, name="session_creer"),
    path("formations/sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("formations/sessions/<int:pk>/participants/", views.session_participants, name="session_participants"),
    path("formations/sessions/<int:pk>/terminer/", views.session_terminer, name="session_terminer"),

    # ====== TYPES D’HABILITATIONS ======
    path("habilitations/dashboard/", views.habilitation_dashboard, name="habilitation_dashboard"),
    path("habilitations/", views.habilitation_type_liste, name="habilitation_liste"),
    path("habilitations/nouvelle/", views.habilitation_type_creer, name="habilitation_creer"),
    path("habilitations/<int:pk>/modifier/", views.habilitation_type_modifier, name="habilitation_modifier"),
    path("habilitations/<int:pk>/supprimer/", views.habilitation_type_supprimer, name="habilitation_supprimer"),
    # REGISTRES
    path("registres/formations/", views.registre_formations, name="registre_formations"),
    path("registres/habilitations/", views.registre_habilitations, name="registre_habilitations"),

    # ================================== Gestion des permis et Interventions
    path("dashboard/permis-interventions/", views.dashboard_permis_interventions, name="dashboard_permis_interventions"),

      # types permis
    path("permis/types/", views.type_permis_liste, name="type_permis_liste"),
    path("permis/types/nouveau/", views.type_permis_creer, name="type_permis_creer"),

    # interventions
    path("interventions/nouvelle/", views.intervention_creer, name="intervention_creer"),
    path("interventions/<int:pk>/", views.intervention_detail, name="intervention_detail"),

    # délivrer permis
    path("interventions/<int:pk>/delivrer/", views.permis_delivrer, name="permis_delivrer"),
    # permis detail (questionnaire)
    path("permis/<int:pk>/", views.permis_detail, name="permis_detail"),
    path("permis/<int:pk>/valider/", views.permis_valider, name="permis_valider"),
    # PDF permis
    path("permis/<int:pk>/pdf/", views.permis_pdf, name="permis_pdf"),
    # liste permis
    path("permis/", views.permis_liste, name="permis_liste"),

    # registre par permis
    path("permis/<int:pk>/registre/", views.registre_par_permis, name="registre_par_permis"),
    path("registres/permis/", views.registre_permis_travail, name="registre_permis_travail"),
    path("permis/<int:pk>/reevaluer/", views.permis_reevaluer, name="permis_reevaluer"),


]

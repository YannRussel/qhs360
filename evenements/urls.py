# evenements/urls.py
from django.urls import path
from . import views

app_name = "evenements"

urlpatterns = [
    path("", views.evenements_dashboard, name="dashboard_evenement"),

    path("evenement/nouveau/", views.evenement_create, name="evenement_create"),
    path("evenement/<int:pk>/", views.evenement_detail, name="evenement_detail"),
    path("evenement/<int:pk>/edit/", views.evenement_edit, name="evenement_edit"),

    path("evenement/<int:pk>/personne/add/", views.personne_add, name="personne_add"),
    path("evenement/<int:pk>/temoin/add/", views.temoin_add, name="temoin_add"),
    path("evenement/<int:pk>/piece/add/", views.piece_add, name="piece_add"),

    path("evenement/<int:pk>/enquete/", views.enquete_edit, name="enquete_edit"),

    path("evenement/<int:pk>/action/add/", views.action_add, name="action_add"),
    path("action/<int:action_id>/edit/", views.action_edit, name="action_edit"),

    path("stats/", views.stats_list, name="stats_list"),
    path("stats/nouveau/", views.stats_create, name="stats_create"),
    path("stats/<int:pk>/", views.stats_detail, name="stats_detail"),
    path("stats/<int:pk>/edit/", views.stats_edit, name="stats_edit"),

    # API: zones d’un site (pour select dynamique)
    path("api/zones/", views.api_zones_by_site, name="api_zones_by_site"),
    path("evenements/<int:pk>/api/chrono/add/", views.api_chrono_add, name="api_chrono_add"),
    path("api/chrono/<int:chrono_id>/edit/", views.api_chrono_edit, name="api_chrono_edit"),
    path("api/chrono/<int:chrono_id>/delete/", views.api_chrono_delete, name="api_chrono_delete"),

    path("evenements/<int:pk>/api/arbre/add/", views.api_arbre_add, name="api_arbre_add"),
    path("api/arbre/<int:node_id>/edit/", views.api_arbre_edit, name="api_arbre_edit"),
    path("api/arbre/<int:node_id>/delete/", views.api_arbre_delete, name="api_arbre_delete"),
         path("actions/suivi/", views.actions_suivi, name="actions_suivi"),
    path("dossier/<int:pk>/suivi-cloture/", views.suivi_cloture, name="suivi_cloture"),

    path("actions/nouvelle/", views.action_create_global, name="action_create_global"),
    path("stats/auto/", views.stats_auto, name="stats_auto"),
]
from django.urls import path
from . import views

app_name = "incendie"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("registre/", views.registre_controles, name="registre_controles"),

    # Extincteurs
    path("extincteurs/", views.extincteurs_list, name="extincteurs_list"),
    path("extincteurs/create/", views.extincteur_create, name="extincteur_create"),
    path("extincteurs/<int:pk>/", views.extincteur_detail, name="extincteur_detail"),
    path("extincteurs/<int:pk>/verifier/", views.extincteur_verifier, name="extincteur_verifier"),

    # RIA
    path("ria/", views.ria_list, name="ria_list"),
    path("ria/create/", views.ria_create, name="ria_create"),
    path("ria/<int:pk>/", views.ria_detail, name="ria_detail"),
    path("ria/<int:pk>/verifier/", views.ria_verifier, name="ria_verifier"),

    # Systèmes
    path("systemes/", views.systemes_list, name="systemes_list"),
    path("systemes/controle/create/", views.systeme_controle_create, name="systeme_controle_create"),
    path("systemes/controle/<int:pk>/", views.systeme_controle_detail, name="systeme_controle_detail"),
    path("systemes/controle/<int:pk>/dm/add/", views.systeme_dm_add, name="systeme_dm_add"),
    path("systemes/controle/<int:pk>/detecteur/add/", views.systeme_detecteur_add, name="systeme_detecteur_add"),

    # Exercices
    path("exercices/", views.exercices_list, name="exercices_list"),
    path("exercices/create/", views.exercice_create, name="exercice_create"),
    path("exercices/<int:pk>/", views.exercice_detail, name="exercice_detail"),
    path("exercices/<int:pk>/chrono/add/", views.exercice_chrono_add, name="exercice_chrono_add"),
    path("exercices/<int:pk>/participation/add/", views.exercice_participation_add, name="exercice_participation_add"),
    path("exercices/<int:pk>/controle/save/", views.exercice_controle_save, name="exercice_controle_save"),

    # Rapports
    path("rapports/", views.rapports_list, name="rapports_list"),
    path("rapports/create/", views.rapport_create, name="rapport_create"),
    path("zones/", views.zones_by_site, name="zones_by_site"),

]

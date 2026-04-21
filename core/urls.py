# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_router, name="home"),
    path("index", views.accueil, name="accueil"),

    # Code Gestion des Organisations
    path("plateforme/", views.plateforme_dashboard, name="plateforme_dashboard"),
    path("plateforme/organisations/nouvelle/", views.organisation_creer, name="organisation_creer"),
    path("plateforme/abonnements/nouveau/", views.abonnement_creer, name="abonnement_creer"),
    path("plateforme/admin-org/nouveau/", views.admin_org_creer, name="admin_org_creer"),

]

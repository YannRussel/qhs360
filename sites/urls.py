from django.urls import path
from . import views

app_name = "sites"

urlpatterns = [
    path("", views.site_liste, name="liste"),
    path("nouveau-site/", views.site_creer, name="creer_site"),
    path("<int:pk>/", views.site_detail, name="detail"),

    # Zones
    path("<int:site_pk>/zones/", views.zone_liste, name="zone_liste"),
    path("<int:site_pk>/zones/nouvelle/", views.zone_creer, name="zone_creer"),

    # ✅ Page gestion affectations
    path("<int:site_pk>/affectations/", views.affectations_page, name="affectations"),

    # ✅ Créer affectation
    path("<int:site_pk>/affectations/nouvelle/", views.affectation_creer, name="affectation_creer"),

    # ✅ Modifier / supprimer
    path("affectations/<int:pk>/modifier/", views.affectation_modifier, name="affectation_modifier"),
    path("affectations/<int:pk>/supprimer/", views.affectation_supprimer, name="affectation_supprimer"),
]

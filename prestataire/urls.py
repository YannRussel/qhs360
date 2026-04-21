from django.urls import path
from . import views

app_name = "prestataire"

urlpatterns = [
    path("", views.prestataire_liste, name="liste"),
    path("nouveau/", views.prestataire_creer, name="creer"),
    path("<int:pk>/modifier/", views.prestataire_modifier, name="modifier"),
    path("<int:pk>/supprimer/", views.prestataire_supprimer, name="supprimer"),
    path("<int:pk>/", views.prestataire_detail, name="detail"), 
]

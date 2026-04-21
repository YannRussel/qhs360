from django.urls import path
from . import views

app_name = "rapport"

urlpatterns = [
    path("rapport", views.dashboard_kpi, name="dashboard_kpi"),
]
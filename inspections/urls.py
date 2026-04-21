from django.urls import path
from . import views

app_name = "inspections"

urlpatterns = [
    path("", views.dashboard, name="dashboard_inspections"),

    path("list/", views.inspection_list, name="inspection_list"),
    path("create/", views.inspection_create, name="inspection_create"),

    path("template/<int:pk>/inspections/", views.inspections_by_template, name="inspections_by_template"),

    path("<int:pk>/fill/", views.inspection_fill, name="inspection_fill"),
    path("<int:pk>/", views.inspection_detail, name="inspection_detail"),

    path("<int:pk>/nc/create/", views.nc_create, name="nc_create"),
    path("nc/<int:nc_id>/resolve/", views.nc_resolve, name="nc_resolve"),

    path("nc/<int:nc_id>/action/add/", views.action_add, name="action_add"),
    path("action/<int:action_id>/toggle/", views.action_toggle, name="action_toggle"),
    path("registre/", views.registre_inspections, name="registre_inspections"),
    path("<int:pk>/close/", views.inspection_close, name="inspection_close"),

]

from django.urls import path
from . import views

app_name = "documentaire"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("nouveau/", views.document_create, name="create"),

    # ✅ API: génération/preview du code automatique
    path("api/generate-code/", views.document_generate_code, name="generate_code"),

    path("<int:pk>/", views.document_detail, name="detail"),
    path("<int:pk>/modifier/", views.document_edit_meta, name="edit_meta"),
    path("<int:pk>/versions/", views.document_versions, name="versions"),
    path("<int:pk>/versions/ajouter/", views.document_add_version, name="add_version"),
    path("<int:pk>/statut/", views.document_change_status, name="change_status"),
    path("<int:pk>/archiver/", views.document_archive, name="archive"),
    path("telecharger/version/<int:version_id>/", views.document_download_version, name="download_version"),
    path("notifications/", views.document_notifications, name="notifications"),
    path("notifications/<int:notif_id>/lue/", views.notification_mark_read, name="notif_read"),
]
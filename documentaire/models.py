from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from organisations.models import Organisation
from sites.models import Site


class DocumentType(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="doc_types")
    nom = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Processus(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="processus_docs")
    nom = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Document(models.Model):
    # Statuts ISO
    BROUILLON = "brouillon"
    VALIDATION = "validation"
    APPROUVE = "approuve"
    OBSOLETE = "obsolete"
    STATUT_CHOICES = [
        (BROUILLON, "Brouillon"),
        (VALIDATION, "En validation"),
        (APPROUVE, "Approuvé"),
        (OBSOLETE, "Obsolète"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="documents_qhs")

    code = models.CharField(max_length=60)  # ex: PR-01, INSTR-002
    titre = models.CharField(max_length=255)

    type_document = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="documents")
    processus = models.ForeignKey(Processus, on_delete=models.PROTECT, related_name="documents", null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="documents", null=True, blank=True)

    mots_cles = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=BROUILLON)

    # Gouvernance
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_possedes"
    )
    confidentialite = models.BooleanField(default=False)  # ancien confidentiel

    # Révision
    date_prochaine_revision = models.DateField(null=True, blank=True)  # ancien prochaine_revision

    # Audit (ancien derniere_mise_a_jour)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    # Version courante (peut être null si doc migré depuis ancien système)
    version_courante = models.ForeignKey(
        "DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        unique_together = ("organisation", "code")
        ordering = ["-modifie_le", "-cree_le"]

    def __str__(self):
        return f"{self.code} — {self.titre}"

    @property
    def version_label(self):
        if self.version_courante:
            return self.version_courante.version or "—"
        return "—"

    @property
    def est_en_retard_revision(self):
        if self.date_prochaine_revision:
            return self.date_prochaine_revision < timezone.localdate()
        return False

    def can_download(self, user):
        # Téléchargement autorisé uniquement si approuvé, sauf staff/superuser
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        return self.statut == self.APPROUVE and not self.confidentialite

    @staticmethod
    def search_queryset(qs, q):
        if not q:
            return qs
        q = q.strip()
        return qs.filter(
            Q(code__icontains=q)
            | Q(titre__icontains=q)
            | Q(mots_cles__icontains=q)
            | Q(type_document__nom__icontains=q)
            | Q(processus__nom__icontains=q)
            | Q(site__nom__icontains=q)
        )


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")

    # ✅ temporairement nullable pour ne pas bloquer les migrations si tu as déjà des lignes
    version = models.CharField(max_length=20, null=True, blank=True)  # ex: 1.0, 1.1, 2.0

    fichier = models.FileField(upload_to="documentaire/documents/%Y/%m/")
    commentaire = models.TextField(blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="doc_versions_creees"
    )

    # ✅ temporairement nullable pour ne pas bloquer les migrations
    statut_snapshot = models.CharField(
        max_length=20,
        choices=Document.STATUT_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("document", "version")
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.document.code} v{self.version or '—'}"


class DocumentAccessLog(models.Model):
    ACTION_VIEW = "view"
    ACTION_DOWNLOAD = "download"
    ACTION_CREATE = "create"
    ACTION_UPDATE_META = "update_meta"
    ACTION_NEW_VERSION = "new_version"
    ACTION_STATUS = "status"
    ACTION_ARCHIVE = "archive"
    ACTION_CHOICES = [
        (ACTION_VIEW, "Consultation"),
        (ACTION_DOWNLOAD, "Téléchargement"),
        (ACTION_CREATE, "Création"),
        (ACTION_UPDATE_META, "Mise à jour fiche"),
        (ACTION_NEW_VERSION, "Nouvelle version"),
        (ACTION_STATUS, "Changement statut"),
        (ACTION_ARCHIVE, "Archivage"),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]


class DocumentNotification(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="doc_notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doc_notifications")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    lu = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]
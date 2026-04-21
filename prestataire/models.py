from django.db import models
from organisations.models import Organisation
from django.utils import timezone

class DomaineIntervention(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="domaines_prestataires"
    )
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Prestataire(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="prestataires"
    )

    domaine = models.ForeignKey(
        DomaineIntervention,
        on_delete=models.PROTECT,
        related_name="prestataires",
        null=True,
        blank=True
    )


    nom = models.CharField(max_length=255)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.domaine.nom})"


class DocumentPrestataire(models.Model):
    TYPE_DOCUMENT = [
        ("immatriculation", "Immatriculation société"),
        ("niu", "NIU"),
        ("autre", "Autre"),
    ]

    prestataire = models.ForeignKey(
        Prestataire,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    type_document = models.CharField(
        max_length=30,
        choices=TYPE_DOCUMENT
    )

    titre = models.CharField(
        max_length=255,
        blank=True,
        help_text="Obligatoire si type = Autre (ex: Assurance RC, Contrat, Agrément...)"
    )

    fichier = models.FileField(upload_to="prestataires/documents/")

    date_emission = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)

    description = models.CharField(max_length=255, blank=True)

    date_upload = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date_upload"]

    def __str__(self):
        label = self.get_type_document_display()
        if self.type_document == "autre" and self.titre:
            label = self.titre
        return f"{self.prestataire.nom} - {label}"


#################" Gestion des agents prestataire"

from django.core.validators import RegexValidator

class AgentPrestataire(models.Model):
    prestataire = models.ForeignKey(
        Prestataire,
        on_delete=models.CASCADE,
        related_name="agents"
    )

    nom = models.CharField(max_length=120)
    prenom = models.CharField(max_length=120, blank=True)

    telephone = models.CharField(
        max_length=50,
        blank=True
    )
    email = models.EmailField(blank=True)

    matricule = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optionnel (matricule interne du prestataire)"
    )

    fonction = models.CharField(max_length=120, blank=True)  # ex: Chef d'équipe, Technicien
    piece_identite = models.CharField(max_length=120, blank=True)  # ex: CNI, Passeport
    numero_piece = models.CharField(max_length=120, blank=True)

    date_embauche = models.DateField(null=True, blank=True)

    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenom"]
        unique_together = ("prestataire", "nom", "prenom", "telephone")

    def __str__(self):
        full = f"{self.nom} {self.prenom}".strip()
        return f"{full} — {self.prestataire.nom}"

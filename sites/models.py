from django.db import models
from organisations.models import Organisation
from prestataire.models import Prestataire

class Site(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="sites")
    nom = models.CharField(max_length=255)
    adresse = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")

    def __str__(self):
        return self.nom

class Zone(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="zones")
    nom = models.CharField(max_length=255)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("site", "nom")

    def __str__(self):
        return f"{self.site} - {self.nom}"

class AffectationPrestataire(models.Model):
    """
    zones vide => prestataire agit sur tout le site
    zones non vide => agit uniquement sur ces zones
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="affectations")
    prestataire = models.ForeignKey(Prestataire, on_delete=models.PROTECT, related_name="affectations")
    zones = models.ManyToManyField(Zone, blank=True, related_name="affectations")
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("site", "prestataire")

    def __str__(self):
        return f"{self.prestataire} -> {self.site}"

from django.db import models
from django.utils import timezone
from organisations.models import Organisation

class Plan(models.Model):
    nom = models.CharField(max_length=80)  # Basique, Pro, Entreprise
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_sites = models.PositiveIntegerField(default=1)
    max_utilisateurs = models.PositiveIntegerField(default=5)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom

class Abonnement(models.Model):
    organisation = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name="abonnement")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_actif = models.BooleanField(default=True)

    def est_valide(self) -> bool:
        today = timezone.now().date()
        return self.est_actif and self.date_debut <= today <= self.date_fin

    def __str__(self):
        return f"{self.organisation} - {self.plan}"

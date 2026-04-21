# qhse/models_habilitations.py (ou dans ton app permis/interventions)

from django.db import models
from django.utils import timezone
from organisations.models import Organisation
from prestataire.models import Prestataire  # tu l'as
# from prestataire.models import AgentPrestataire  # à créer si pas déjà
from django.conf import settings

class Formation(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="formations")
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class TypeHabilitation(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="types_habilitations")
    nom = models.CharField(max_length=255)  # ex: "Habilitation Feu"
    description = models.TextField(blank=True)
    formations_requises = models.ManyToManyField(Formation, blank=True, related_name="habilitations_delivrees")
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class AgentHabilitation(models.Model):
    agent = models.ForeignKey("prestataire.AgentPrestataire", on_delete=models.CASCADE, related_name="habilitations")
    type_habilitation = models.ForeignKey(TypeHabilitation, on_delete=models.PROTECT, related_name="agents")
    date_obtention = models.DateField(default=timezone.now)
    date_expiration = models.DateField(null=True, blank=True)
    preuve = models.FileField(upload_to="habilitations/preuves/", null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("agent", "type_habilitation")
        ordering = ["-date_obtention"]

    def est_valide_le(self, date_ref=None):
        if not self.actif:
            return False
        date_ref = date_ref or timezone.now().date()
        if self.date_expiration and self.date_expiration < date_ref:
            return False
        return True

    def __str__(self):
        return f"{self.agent} - {self.type_habilitation}"


from django.db import models, transaction
from django.utils import timezone

class SessionFormation(models.Model):
    STATUT_CHOICES = (
        ("planifiee", "Planifiée"),
        ("encours", "En cours"),
        ("terminee", "Terminée"),
        ("annulee", "Annulée"),
    )

    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="sessions_formations")
    formation = models.ForeignKey("permis.Formation", on_delete=models.PROTECT, related_name="sessions")

    titre = models.CharField(max_length=255, blank=True)  # optionnel
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)

    # ✅ Durée : simple et fiable (minutes)
    duree_minutes = models.PositiveIntegerField(default=0)

    lieu = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifiee")

    # ✅ Intervenants = agents prestataires
    intervenants = models.ManyToManyField(
        "prestataire.AgentPrestataire",
        blank=True,
        related_name="sessions_animees"
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.formation} — {self.date_debut:%d/%m/%Y}"

    def terminer(self, date_obtention=None):
        """
        Marque la session terminée et génère les habilitations pour tous les participants validés.
        (Idempotent grâce aux unique_together de AgentHabilitation)
        """
        from .models import TypeHabilitation, AgentHabilitation

        if self.statut == "terminee":
            return

        date_obtention = date_obtention or timezone.now().date()

        with transaction.atomic():
            self.statut = "terminee"
            if not self.date_fin:
                self.date_fin = timezone.now()
            self.save()

            # ✅ toutes les habilitations liées à cette formation (via formations_requises)
            types = TypeHabilitation.objects.filter(
                organisation=self.organisation,
                actif=True,
                formations_requises=self.formation
            )

            # ✅ participants validés
            participants = self.participants.filter(valide=True).select_related("agent")

            for p in participants:
                for t in types:
                    AgentHabilitation.objects.get_or_create(
                        agent=p.agent,
                        type_habilitation=t,
                        defaults={
                            "date_obtention": date_obtention,
                            "actif": True
                        }
                    )


class ParticipantSession(models.Model):
    session = models.ForeignKey(SessionFormation, on_delete=models.CASCADE, related_name="participants")
    agent = models.ForeignKey("prestataire.AgentPrestataire", on_delete=models.CASCADE, related_name="sessions_suivies")

    # présence / validation
    present = models.BooleanField(default=True)
    valide = models.BooleanField(default=True)  # si l’agent a réussi/est éligible
    note = models.CharField(max_length=30, blank=True)  # ex: "Admis", "Recalé", "80/100"

    class Meta:
        unique_together = ("session", "agent")

    def __str__(self):
        return f"{self.agent} — {self.session}"


####### =========================== Gestion des Interventions, permis


# ===========================
# Gestion des Interventions & Permis (Option A)
# ===========================

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

from organisations.models import Organisation


class TypePermis(models.Model):
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="types_permis"
    )
    nom = models.CharField(max_length=255)  # ex: "Permis Feu", "Permis Hauteur"
    description = models.TextField(blank=True)

    # ✅ Les habilitations nécessaires pour avoir droit à ce permis
    habilitations_requises = models.ManyToManyField(
        "permis.TypeHabilitation",
        blank=True,
        related_name="permis_eligibles",
    )

    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "nom")
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Intervention(models.Model):
    STATUT_CHOICES = (
        ("planifiee", "Planifiée"),
        ("encours", "En cours"),
        ("terminee", "Terminée"),
        ("annulee", "Annulée"),
    )

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="interventions"
    )

    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    lieu = models.CharField(max_length=255, blank=True)

    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifiee")

    # ✅ Permis requis pour cette intervention
    permis_requis = models.ManyToManyField(
        TypePermis, blank=True, related_name="interventions"
    )

    # ✅ Participants possibles (agents prestataire)
    agents = models.ManyToManyField(
        "prestataire.AgentPrestataire", blank=True, related_name="interventions"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.titre} ({self.date_debut:%d/%m/%Y})"


class PermisDelivre(models.Model):
    """
    Un permis concret délivré à un agent dans le cadre d'une intervention.
    Option A: généré automatiquement en 'en_attente', questionnaire rempli ensuite, puis validation.
    """
    STATUT_CHOICES = (
        ("en_attente", "En attente"),
        ("valide", "Validé"),
        ("refuse", "Refusé"),
    )

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="permis_delivres"
    )
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name="permis_delivres"
    )
    agent = models.ForeignKey(
        "prestataire.AgentPrestataire", on_delete=models.CASCADE, related_name="permis_delivres"
    )
    type_permis = models.ForeignKey(
        TypePermis, on_delete=models.PROTECT, related_name="delivrances"
    )

    date_delivrance = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(null=True, blank=True)

    actif = models.BooleanField(default=True)

    # ✅ workflow
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")
    motif_refus = models.TextField(blank=True)

    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="permis_valides",
    )
    valide_le = models.DateTimeField(null=True, blank=True)

    remarque = models.TextField(blank=True)

    class Meta:
        unique_together = ("intervention", "agent", "type_permis")
        ordering = ["-date_delivrance"]

    def __str__(self):
        return f"{self.type_permis} — {self.agent} — {self.intervention}"

    def agent_est_eligible(self, date_ref=None) -> bool:
        """
        ✅ Règle métier:
        L'agent est éligible si toutes les habilitations requises par le type de permis
        sont détenues par l'agent (et valides).
        """
        date_ref = date_ref or timezone.now().date()

        required_ids = list(self.type_permis.habilitations_requises.values_list("id", flat=True))
        if not required_ids:
            return True

        from permis.models import AgentHabilitation  # ton modèle existant

        agent_habs = AgentHabilitation.objects.filter(
            agent=self.agent,
            type_habilitation_id__in=required_ids,
            actif=True,
            # ✅ IMPORTANT: on filtre par org via le type d'habilitation (AgentHabilitation n'a pas organisation)
            type_habilitation__organisation=self.organisation,
        )

        valid_ids = set()
        for h in agent_habs:
            if h.est_valide_le(date_ref):
                valid_ids.add(h.type_habilitation_id)

        return set(required_ids).issubset(valid_ids)

    def clean(self):
        """
        Validation Django (si tu utilises full_clean()).
        """
        # 1) même org
        if self.intervention_id and self.intervention.organisation_id != self.organisation_id:
            raise ValidationError("Organisation incohérente (intervention).")

        if self.type_permis_id and self.type_permis.organisation_id != self.organisation_id:
            raise ValidationError("Organisation incohérente (type permis).")

        # 2) le permis doit être requis par l'intervention (si tu veux garder cette règle)
        if self.intervention_id and self.type_permis_id:
            if not self.intervention.permis_requis.filter(id=self.type_permis_id).exists():
                raise ValidationError("Ce permis n'est pas requis pour cette intervention.")

        # 3) éligibilité seulement si le permis n'est pas "refuse"
        if self.statut != "refuse" and not self.agent_est_eligible():
            raise ValidationError("Agent non éligible : habilitations requises manquantes/expirées.")


class QuestionPermis(models.Model):
    TYPE_REPONSE = (
        ("bool", "Oui / Non"),
        ("text", "Texte"),
        ("choice", "Choix"),
        ("number", "Nombre"),
    )

    type_permis = models.ForeignKey(
        TypePermis, on_delete=models.CASCADE, related_name="questions"
    )

    texte = models.CharField(max_length=500)
    type_reponse = models.CharField(max_length=20, choices=TYPE_REPONSE, default="bool")
    choix = models.TextField(blank=True, help_text="Ex: OK; KO; N/A")

    obligatoire = models.BooleanField(default=True)
    ordre = models.PositiveIntegerField(default=1)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordre", "id"]

    def __str__(self):
        return f"{self.type_permis.nom} — {self.texte[:40]}"


class ReponsePermis(models.Model):
    permis = models.ForeignKey(
        PermisDelivre, on_delete=models.CASCADE, related_name="reponses"
    )
    question = models.ForeignKey(
        QuestionPermis, on_delete=models.PROTECT, related_name="reponses"
    )

    valeur_bool = models.BooleanField(null=True, blank=True)
    valeur_text = models.TextField(blank=True)
    valeur_choice = models.CharField(max_length=255, blank=True)
    valeur_number = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    remarque = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("permis", "question")
        ordering = ["question__ordre", "id"]

    def __str__(self):
        return f"Réponse — Permis#{self.permis_id} — Q#{self.question_id}"
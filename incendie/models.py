from django.db import models
from django.conf import settings
from django.utils import timezone
from sites.models import Site, Zone

User = settings.AUTH_USER_MODEL


STATUS_CHOICES = (
    ("conforme", "Conforme"),
    ("nc", "Non conforme"),
    ("na", "Non applicable"),
)

SYSTEME_CHOICES = (
    ("alarme", "Système d'alarme"),
    ("desenfumage", "Système de désenfumage"),
    ("alarme_desenfumage", "Alarme + Désenfumage"),
)

EXERCICE_TYPE_CHOICES = (
    ("planifie", "Planifié"),
    ("inopine", "Inopiné"),
)

INTERVENTION_TYPE_CHOICES = (
    ("incident", "Incident réel"),
    ("exercice", "Exercice"),
)


class TimeStamped(models.Model):
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =========================
# EXTINCTEURS
# =========================

class Extincteur(TimeStamped):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="extincteurs")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="extincteurs")

    numero = models.CharField(max_length=120)  # identifiant unique terrain
    type_extincteur = models.CharField(max_length=80)  # Eau/CO2/Poudre/Mousse/...
    capacite = models.CharField(max_length=40, blank=True)  # "6kg" / "9L"
    emplacement = models.CharField(max_length=255)

    marque = models.CharField(max_length=120, blank=True)
    numero_serie = models.CharField(max_length=120, blank=True)
    annee_fabrication = models.CharField(max_length=10, blank=True)

    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("site", "numero")

    def __str__(self):
        return f"{self.numero} — {self.site.nom}"


class VerificationExtincteur(TimeStamped):
    extincteur = models.ForeignKey(Extincteur, on_delete=models.CASCADE, related_name="verifications")
    date_verification = models.DateField(default=timezone.now)

    # checklist (alignée registre client)
    checklist = models.JSONField(default=dict, blank=True)  # {pression_ok:true, scelle_ok:true, ...}
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="conforme")

    observation = models.TextField(blank=True)
    verifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verifs_extincteurs")

    def __str__(self):
        return f"Vérif {self.extincteur.numero} ({self.date_verification})"


# =========================
# RIA
# =========================

class RIA(TimeStamped):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="rias")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="rias")

    numero = models.CharField(max_length=120)
    localisation = models.CharField(max_length=255)

    type_ria = models.CharField(max_length=40, blank=True)  # Enrouleur / Poste fixe
    diametre_tuyau = models.CharField(max_length=40, blank=True)  # 19/25mm
    longueur_tuyau = models.CharField(max_length=40, blank=True)
    pression_nominale = models.CharField(max_length=40, blank=True)
    marque = models.CharField(max_length=120, blank=True)
    annee_installation = models.CharField(max_length=10, blank=True)

    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ("site", "numero")

    def __str__(self):
        return f"RIA {self.numero} — {self.site.nom}"


class VerificationRIA(TimeStamped):
    ria = models.ForeignKey(RIA, on_delete=models.CASCADE, related_name="verifications")
    date_verification = models.DateField(default=timezone.now)

    checklist_visuelle = models.JSONField(default=dict, blank=True)      # booleans
    checklist_fonctionnelle = models.JSONField(default=dict, blank=True) # booleans

    pression_mesuree = models.CharField(max_length=40, blank=True)
    etancheite_ok = models.BooleanField(default=True)

    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="conforme")
    commentaire = models.TextField(blank=True)

    verifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verifs_ria")

    def __str__(self):
        return f"Vérif RIA {self.ria.numero} ({self.date_verification})"


# =========================
# CONTROLE ALARME / DESENFUMAGE
# =========================

class ControleSystemeIncendie(TimeStamped):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="controles_systemes_incendie")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="controles_systemes_incendie")

    type_systeme = models.CharField(max_length=30, choices=SYSTEME_CHOICES, default="alarme_desenfumage")
    date_controle = models.DateField(default=timezone.now)

    presence_responsable_securite = models.BooleanField(default=False)
    controle_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="controles_systeme_incendie")

    checklist_alarme = models.JSONField(default=dict, blank=True)
    checklist_desenfumage = models.JSONField(default=dict, blank=True)

    observation = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="conforme")

    def __str__(self):
        return f"Contrôle {self.get_type_systeme_display()} — {self.site.nom} ({self.date_controle})"


class ControleDM(TimeStamped):
    controle = models.ForeignKey(ControleSystemeIncendie, on_delete=models.CASCADE, related_name="dms")
    identifiant = models.CharField(max_length=120)
    localisation = models.CharField(max_length=255, blank=True)
    acces_ok = models.BooleanField(default=True)
    etat_ok = models.BooleanField(default=True)
    test_ok = models.BooleanField(default=True)
    remarque = models.TextField(blank=True)


class ControleDetecteur(TimeStamped):
    controle = models.ForeignKey(ControleSystemeIncendie, on_delete=models.CASCADE, related_name="detecteurs")
    identifiant = models.CharField(max_length=120)
    type_detecteur = models.CharField(max_length=120, blank=True)
    localisation = models.CharField(max_length=255, blank=True)
    proprete_ok = models.BooleanField(default=True)
    test_ok = models.BooleanField(default=True)
    remarque = models.TextField(blank=True)


# =========================
# EXERCICES D'EVACUATION (suivi + controle)
# =========================

class ExerciceEvacuation(TimeStamped):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="exercices_evacuation")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="exercices_evacuation")

    type_exercice = models.CharField(max_length=20, choices=EXERCICE_TYPE_CHOICES, default="planifie")
    date_exercice = models.DateField(default=timezone.now)
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)

    objectifs = models.TextField(blank=True)
    scenario = models.TextField(blank=True)
    deroulement = models.TextField(blank=True)

    organise_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="exercices_organises")

    def __str__(self):
        return f"Exercice {self.site.nom} ({self.date_exercice})"


class ChronometrageEvacuation(TimeStamped):
    exercice = models.ForeignKey(ExerciceEvacuation, on_delete=models.CASCADE, related_name="chronometrages")
    libelle_zone = models.CharField(max_length=255)
    heure_debut_zone = models.TimeField(null=True, blank=True)
    heure_arrivee_point = models.TimeField(null=True, blank=True)
    temps_minutes = models.IntegerField(null=True, blank=True)
    remarque = models.TextField(blank=True)


class ParticipationEvacuation(TimeStamped):
    exercice = models.ForeignKey(ExerciceEvacuation, on_delete=models.CASCADE, related_name="participations")
    service = models.CharField(max_length=255)
    effectif_theorique = models.IntegerField(default=0)
    presents = models.IntegerField(default=0)
    absents = models.IntegerField(default=0)
    remarque = models.TextField(blank=True)


class ControleExerciceEvacuation(TimeStamped):
    exercice = models.OneToOneField(ExerciceEvacuation, on_delete=models.CASCADE, related_name="controle")

    checklist_declenchement = models.JSONField(default=dict, blank=True)
    checklist_comportement = models.JSONField(default=dict, blank=True)
    checklist_guides = models.JSONField(default=dict, blank=True)
    checklist_issues = models.JSONField(default=dict, blank=True)
    checklist_rassemblement = models.JSONField(default=dict, blank=True)

    temps_total_minutes = models.IntegerField(null=True, blank=True)
    observation = models.TextField(blank=True)

    controle_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="controles_exercices")
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="conforme")


# =========================
# RAPPORT INTERVENTION INCENDIE
# =========================

class RapportInterventionIncendie(TimeStamped):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="rapports_incendie")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="rapports_incendie")

    type_intervention = models.CharField(max_length=20, choices=INTERVENTION_TYPE_CHOICES, default="incident")
    date = models.DateField(default=timezone.now)
    heure = models.TimeField(null=True, blank=True)

    titre = models.CharField(max_length=255)
    description = models.TextField()
    actions_menees = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)

    redige_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="rapports_incendie")

    pieces_jointes = models.FileField(upload_to="incendie/rapports/", blank=True, null=True)

    def __str__(self):
        return f"Rapport {self.type_intervention} — {self.site.nom} ({self.date})"

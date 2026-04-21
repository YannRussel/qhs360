from django.db import models
from django.utils import timezone

from organisations.models import Organisation
from sites.models import Site, Zone
from prestataire.models import Prestataire, AgentPrestataire


class Evenement(models.Model):
    TYPE_EVENT = [
        ("accident", "Accident du travail"),
        ("incident", "Incident"),
        ("presquaccident", "Presqu’accident"),
        ("audit", "Audit"),
        ("inspection", "Inspection"),
        ("autre", "Autre"),
    ]

    GRAVITE_EVENT = [
        ("benin", "Bénin"),
        ("sans_arret", "Sans arrêt"),
        ("avec_arret", "Avec arrêt"),
        ("grave", "Grave"),
        ("mortel", "Mortel"),
    ]

    NIVEAU_DOSSIER = [
        ("faible", "Faible"),
        ("moyen", "Moyen"),
        ("eleve", "Élevé"),
        ("critique", "Critique"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="evenements")

    reference = models.CharField(max_length=120, blank=True)  # Référence accident/dossier/audit
    type_evenement = models.CharField(max_length=20, choices=TYPE_EVENT)

    # Identification (fiche déclaration)
    date_evenement = models.DateField()
    heure = models.TimeField(null=True, blank=True)
    lieu_precis = models.CharField(max_length=255, blank=True)
    service_departement = models.CharField(max_length=255, blank=True)
    declarant_nom_fonction = models.CharField(max_length=255, blank=True)

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="evenements")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="evenements", null=True, blank=True)

    prestataire = models.ForeignKey(Prestataire, on_delete=models.PROTECT, related_name="evenements", null=True, blank=True)

    # Description & gravité
    description = models.TextField(blank=True)

    nature_accident = models.CharField(max_length=80, blank=True)  # Chute/Coupure/...
    partie_corps = models.CharField(max_length=120, blank=True)

    gravite_apparente = models.CharField(max_length=20, choices=GRAVITE_EVENT, blank=True)
    niveau_gravite_dossier = models.CharField(max_length=10, choices=NIVEAU_DOSSIER, blank=True)

    dommages_materiels = models.BooleanField(default=False)
    impact_environnemental = models.BooleanField(default=False)

    # Mesures immédiates (cases)
    mesures_premiers_secours = models.BooleanField(default=False)
    mesures_mise_en_securite = models.BooleanField(default=False)
    mesures_arret_activite = models.BooleanField(default=False)
    mesures_balisage = models.BooleanField(default=False)
    mesures_alerte_hse = models.BooleanField(default=False)
    mesures_autres = models.CharField(max_length=255, blank=True)

    # Analyse préliminaire HSE (cases)
    analyse_humaine = models.BooleanField(default=False)
    analyse_technique = models.BooleanField(default=False)
    analyse_organisationnelle = models.BooleanField(default=False)
    analyse_environnementale = models.BooleanField(default=False)

    # Workflow dossier (fiche suivi & clôture)
    date_ouverture = models.DateField(default=timezone.now)
    date_cloture_prevue = models.DateField(null=True, blank=True)
    date_cloture = models.DateField(null=True, blank=True)
    dossier_cloture_validee = models.BooleanField(null=True, blank=True)  # None = pas décidé

    # Signatures / validations (déclaration & suivi)
    validation_declarant = models.CharField(max_length=255, blank=True)
    validation_hierarchique = models.CharField(max_length=255, blank=True)
    validation_hse = models.CharField(max_length=255, blank=True)

    validation_qhs = models.CharField(max_length=255, blank=True)     # suivi/clôture
    validation_direction = models.CharField(max_length=255, blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_evenement", "-cree_le"]

    def __str__(self):
        ref = self.reference or f"EVT-{self.id}"
        return f"{ref} — {self.get_type_evenement_display()} — {self.site}"


class PersonneImpliquee(models.Model):
    STATUT = [
        ("salarie", "Salarié"),
        ("prestataire", "Prestataire"),
    ]

    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="personnes_impliquees")

    # soit lien agent prestataire, soit saisie libre
    agent_prestataire = models.ForeignKey(AgentPrestataire, on_delete=models.PROTECT, null=True, blank=True)

    nom_prenom = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT, blank=True)

    entreprise_prestataire = models.CharField(max_length=255, blank=True)
    poste_fonction = models.CharField(max_length=255, blank=True)
    anciennete = models.CharField(max_length=80, blank=True)

    formation_habilitation_valide = models.CharField(
        max_length=20,
        choices=[("oui", "Oui"), ("non", "Non"), ("averifier", "À vérifier")],
        blank=True
    )

    def __str__(self):
        return self.nom_prenom or (str(self.agent_prestataire) if self.agent_prestataire else f"Impliqué #{self.id}")


class Temoin(models.Model):
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="temoins")
    nom = models.CharField(max_length=255)
    fonction = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.nom


class PieceJointe(models.Model):
    TYPE = [
        ("photo", "Photo"),
        ("video", "Vidéo"),
        ("certificat", "Certificat médical"),
        ("rapport", "Rapport secours"),
        ("autre", "Autre"),
    ]

    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="pieces_jointes")
    type_piece = models.CharField(max_length=20, choices=TYPE)
    fichier = models.FileField(upload_to="evenements/pieces/")
    titre = models.CharField(max_length=255, blank=True)
    ajoute_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_piece_display()} — {self.evenement}"


class EnqueteAccident(models.Model):
    """
    Fiche d’enquête : déroulement, causes, facteurs contributifs, lien modules, conclusion, validation.
    + Méthode structurée : 5P ou Arbre des causes
    + Chronologie dynamique (arbre de faits)
    """
    METHODE_ANALYSE = [
        ("", "—"),
        ("5p", "Méthode des 5P (Personnel, Procédures, Produits, Procédé, Place)"),
        ("arbre", "Arbre des causes"),
    ]

    evenement = models.OneToOneField(Evenement, on_delete=models.CASCADE, related_name="enquete")

    # équipe d’enquête (simple texte multiline)
    equipe_enquete = models.TextField(blank=True)

    # Conserve un champ texte si tu veux un résumé global (optionnel)
    deroulement_faits = models.TextField(blank=True)

    methode_analyse = models.CharField(
        max_length=20,
        choices=METHODE_ANALYSE,
        blank=True,
        default=""
    )

    # causes (texte)
    causes_humaines = models.TextField(blank=True)
    causes_techniques = models.TextField(blank=True)
    causes_organisationnelles = models.TextField(blank=True)
    causes_environnementales = models.TextField(blank=True)

    # facteurs contributifs (cases)
    fc_formation_non_valide = models.BooleanField(default=False)
    fc_habilitation_expiree = models.BooleanField(default=False)
    fc_permis_non_conforme = models.BooleanField(default=False)
    fc_epi_non_porte = models.BooleanField(default=False)
    fc_procedure_non_appliquee = models.BooleanField(default=False)
    fc_supervision_insuffisante = models.BooleanField(default=False)

    # lien modules
    lien_formation = models.BooleanField(default=False)
    lien_habilitation = models.BooleanField(default=False)
    lien_permis = models.BooleanField(default=False)
    lien_procedure = models.BooleanField(default=False)

    conclusion = models.TextField(blank=True)

    # validation enquête
    validation_responsable_hse = models.CharField(max_length=255, blank=True)
    validation_chef_site_direction = models.CharField(max_length=255, blank=True)
    cloture_enquete = models.BooleanField(default=False)

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)
    
    # ===== Suivi & clôture (efficacité + décision) =====
    date_verification_efficacite = models.DateField(null=True, blank=True)
    efficace_globale = models.BooleanField(null=True, blank=True)  # Oui/Non/Non défini
    commentaires_efficacite = models.TextField(blank=True)

    decision_cloture = models.TextField(blank=True)  # texte décision
    decision_finale = models.BooleanField(default=False)  # case "Décision finale de clôture"

    def __str__(self):
        return f"Enquête — {self.evenement}"


class ChronologieFait(models.Model):
    """
    Chronologie structurée (arborescente) :
    - Un fait peut avoir des sous-faits (parent -> enfants)
    """
    enquete = models.ForeignKey(EnqueteAccident, on_delete=models.CASCADE, related_name="chronologie")

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sous_faits"
    )

    date_fait = models.DateField()
    heure_fait = models.TimeField(null=True, blank=True)
    description = models.TextField()

    ordre = models.PositiveIntegerField(default=1)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_fait", "heure_fait", "ordre", "id"]

    def __str__(self):
        return f"{self.date_fait} — {self.description[:50]}"


class Analyse5Pourquoi(models.Model):
    """
    Méthode des 5 Pourquoi :
    5 questions + 5 réponses obligatoires + cause racine
    """
    enquete = models.OneToOneField(EnqueteAccident, on_delete=models.CASCADE, related_name="analyse_5p")

    pourquoi1 = models.TextField()
    reponse1 = models.TextField()

    pourquoi2 = models.TextField()
    reponse2 = models.TextField()

    pourquoi3 = models.TextField()
    reponse3 = models.TextField()

    pourquoi4 = models.TextField()
    reponse4 = models.TextField()

    pourquoi5 = models.TextField()
    reponse5 = models.TextField()

    cause_racine_finale = models.TextField()

    maj_le = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"5P — {self.enquete}"


class Analyse5PIndustrie(models.Model):
    """
    Méthode des 5P en industrie :
    Personnel / Procédures / Produits / Procédé / Place
    """
    enquete = models.OneToOneField(
        EnqueteAccident,
        on_delete=models.CASCADE,
        related_name="analyse_5p_industrie"
    )

    personnel = models.TextField()
    procedures = models.TextField()
    produits = models.TextField()
    procede = models.TextField()
    place = models.TextField()

    cause_racine_finale = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)

    maj_le = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"5P Industrie — {self.enquete}"

class ArbreCauseNoeud(models.Model):
    """
    Arbre des causes détaillé :
    - un nœud peut représenter un fait, une cause, une barrière absente ou une cause racine
    - chaque nœud peut avoir une question "Pourquoi ?"
    - chaque nœud peut avoir une réponse
    - la réponse peut ensuite devenir la cause du nœud enfant
    """

    TYPE_NOEUD = [
        ("fait", "Fait"),
        ("cause", "Cause"),
        ("barriere", "Barrière absente"),
        ("cause_racine", "Cause racine"),
    ]

    LOGIQUE = [
        ("et", "ET"),
        ("ou", "OU"),
    ]

    enquete = models.ForeignKey(
        EnqueteAccident,
        on_delete=models.CASCADE,
        related_name="arbre_causes"
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="enfants"
    )

    type_noeud = models.CharField(max_length=20, choices=TYPE_NOEUD, default="cause")

    # Nouveau format détaillé
    cause = models.TextField()
    pourquoi = models.TextField(blank=True)
    reponse = models.TextField(blank=True)

    logique = models.CharField(max_length=5, choices=LOGIQUE, null=True, blank=True)

    ordre = models.PositiveIntegerField(default=1)

    # profondeur visuelle dans l'arbre
    niveau = models.PositiveIntegerField(default=0)

    # permet de marquer explicitement la fin d'analyse
    est_cause_racine = models.BooleanField(default=False)

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["niveau", "ordre", "id"]

    def __str__(self):
        return f"{self.get_type_noeud_display()} — {self.cause[:60]}"


class ActionCAPA(models.Model):
    """
    Actions Correctives & Préventives (CAPA) + statut + preuve + efficacité.
    """
    TYPE_ACTION = [("corrective", "Corrective"), ("preventive", "Préventive")]
    STATUT = [
        ("a_faire", "À faire"),
        ("en_cours", "En cours"),
        ("realisee", "Réalisée"),
        ("retard", "Retard"),
        ("annulee", "Annulée"),
    ]
    PRIORITE = [("basse", "Basse"), ("moyenne", "Moyenne"), ("haute", "Haute"), ("critique", "Critique")]

    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="actions")

    numero = models.PositiveIntegerField(default=1)
    type_action = models.CharField(max_length=20, choices=TYPE_ACTION)
    description_action = models.TextField()
    cause_racine = models.CharField(max_length=255, blank=True)

    responsable = models.CharField(max_length=255, blank=True)
    service_societe = models.CharField(max_length=255, blank=True)

    delai = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT, default="a_faire")
    priorite = models.CharField(max_length=20, choices=PRIORITE, blank=True)

    date_realisation = models.DateField(null=True, blank=True)
    preuve = models.FileField(upload_to="evenements/preuves/", null=True, blank=True)
    commentaires = models.CharField(max_length=255, blank=True)

    # efficacité (fiche actions + fiche suivi)
    date_verification_efficacite = models.DateField(null=True, blank=True)
    efficace = models.BooleanField(null=True, blank=True)
    commentaires_efficacite = models.TextField(blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["numero", "id"]

    def __str__(self):
        return f"Action {self.numero} — {self.evenement}"


class StatistiquesHSE(models.Model):
    """
    Fiche Statistiques & Indicateurs HSE (période, TF/TG, répartition, lien formations/habilitations/permis, etc.)
    """
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="stats_hse")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="stats_hse", null=True, blank=True)

    periode_label = models.CharField(max_length=120)  # ex: "Janvier 2026", "T1 2026"
    responsable_qhs = models.CharField(max_length=255, blank=True)

    # 1) Accidents
    nb_accidents_total = models.PositiveIntegerField(default=0)
    nb_accidents_avec_arret = models.PositiveIntegerField(default=0)
    nb_accidents_sans_arret = models.PositiveIntegerField(default=0)
    nb_jours_perdus = models.PositiveIntegerField(default=0)
    tf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tg = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # 2) Répartition (texte libre)
    repartition_par_site = models.TextField(blank=True)
    repartition_par_service = models.TextField(blank=True)
    repartition_par_prestataire = models.TextField(blank=True)
    repartition_par_activite = models.TextField(blank=True)
    repartition_par_gravite = models.TextField(blank=True)

    # 3) Incidents & presqu’accidents
    nb_incidents = models.PositiveIntegerField(default=0)
    nb_presquaccidents = models.PositiveIntegerField(default=0)
    taux_declaration = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tendance_vs_periode_precedente = models.CharField(max_length=255, blank=True)

    # 4) CAPA
    nb_actions_ouvertes = models.PositiveIntegerField(default=0)
    nb_actions_cloturees = models.PositiveIntegerField(default=0)
    nb_actions_en_retard = models.PositiveIntegerField(default=0)
    taux_cloture_actions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # 5) lien avec formations/habilitations/permis (champs numériques)
    accidents_formation_expiree = models.PositiveIntegerField(default=0)
    accidents_habilitation_manquante = models.PositiveIntegerField(default=0)
    accidents_permis_non_conforme = models.PositiveIntegerField(default=0)
    actions_formation_habilitation_declenchees = models.PositiveIntegerField(default=0)

    # 6) analyse commentaires
    analyse_commentaires = models.TextField(blank=True)

    # 7) validation & diffusion
    etabli_par = models.CharField(max_length=255, blank=True)
    valide_par = models.CharField(max_length=255, blank=True)
    diffusion_direction = models.BooleanField(default=False)
    diffusion_hse = models.BooleanField(default=False)
    diffusion_sites = models.BooleanField(default=False)
    diffusion_autres = models.CharField(max_length=255, blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"Stats HSE — {self.periode_label}"
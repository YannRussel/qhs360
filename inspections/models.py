from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from organisations.models import Organisation
from prestataire.models import Prestataire

# ✅ adapte "sites" si ton app s'appelle autrement
from sites.models import Site, Zone, AffectationPrestataire


INSPECTION_STATUS = [
    ('draft', 'Brouillon'),
    ('open', 'Ouvert'),
    ('closed', 'Clos'),
    ('cancelled', 'Annulé'),
]

SEVERITY = [
    ('low', 'Faible'),
    ('medium', 'Moyen'),
    ('high', 'Élevé'),
    ('critical', 'Critique'),
]

QUESTION_FIELD_TYPES = [
    ('checkbox', 'Checkbox (oui/non)'),
    ('radio', 'Radio (choix unique)'),
    ('select', 'Select (liste)'),
    ('text', 'Texte court'),
    ('textarea', 'Texte long'),
    ('number', 'Nombre'),
    ('photo', 'Photo requise'),
]


class InspectionTemplate(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="inspection_templates")

    nom = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)

    actif = models.BooleanField(default=True)
    required_for_deployment = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_inspection_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        unique_together = ("organisation", "nom")

    def __str__(self):
        return f"{self.nom} (v{self.version})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)[:250]
        super().save(*args, **kwargs)


class InspectionSection(models.Model):
    template = models.ForeignKey(InspectionTemplate, on_delete=models.CASCADE, related_name="sections")
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    ordre = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ["ordre"]
        unique_together = ("template", "ordre")

    def __str__(self):
        return f"{self.template.nom} — {self.titre}"


class InspectionQuestion(models.Model):
    section = models.ForeignKey(InspectionSection, on_delete=models.CASCADE, related_name="questions")
    ordre = models.PositiveSmallIntegerField(default=10)

    label = models.CharField(max_length=1000)
    aide = models.CharField(max_length=500, blank=True, null=True)

    field_type = models.CharField(max_length=20, choices=QUESTION_FIELD_TYPES, default="checkbox")
    obligatoire = models.BooleanField(default=False)

    select_options = models.TextField(
        blank=True, null=True,
        help_text="Sépare par '|' pour les choix (radio/select) ex: Bon|Mauvais|N/A"
    )
    points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.section.titre} — {self.label[:60]}"

    def options_list(self):
        if not self.select_options:
            return []
        return [x.strip() for x in self.select_options.split("|") if x.strip()]


class Inspection(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="inspections")

    template = models.ForeignKey(
        InspectionTemplate, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="inspections"
    )
    type_libre = models.CharField(max_length=255, blank=True, null=True)

    reference = models.CharField(max_length=120, unique=True, blank=True, null=True)

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="inspections")
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.PROTECT, related_name="inspections")
    prestataire = models.ForeignKey(Prestataire, null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections")

    date = models.DateTimeField(default=timezone.now, db_index=True)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="inspections_done"
    )

    status = models.CharField(max_length=30, choices=INSPECTION_STATUS, default="open", db_index=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(
    settings.AUTH_USER_MODEL, null=True, blank=True,
    on_delete=models.SET_NULL, related_name="inspections_closed"
)


    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["organisation", "date"]),
            models.Index(fields=["site", "date"]),
            models.Index(fields=["status", "template"]),
        ]

    def __str__(self):
        label = self.template.nom if self.template else (self.type_libre or "Inspection")
        ref = self.reference or f"INS-{self.pk}"
        return f"{ref} - {label} - {self.site}"

    def clean(self):
        if self.site_id and self.organisation_id and self.site.organisation_id != self.organisation_id:
            raise ValidationError("Organisation incohérente : le site n'appartient pas à cette organisation.")

        if self.zone_id and self.site_id and self.zone.site_id != self.site_id:
            raise ValidationError("La zone sélectionnée n'appartient pas au site.")

        if self.prestataire_id and self.site_id:
            aff_qs = AffectationPrestataire.objects.filter(site_id=self.site_id, prestataire_id=self.prestataire_id, actif=True)
            if not aff_qs.exists():
                raise ValidationError("Ce prestataire n'est pas affecté à ce site.")
            if self.zone_id:
                aff = aff_qs.first()
                if aff.zones.exists() and not aff.zones.filter(id=self.zone_id).exists():
                    raise ValidationError("Ce prestataire n'est pas affecté à cette zone.")

    def save(self, *args, **kwargs):
        creating = self.pk is None

        if self.site_id and not self.organisation_id:
            self.organisation = self.site.organisation

        super().save(*args, **kwargs)

        if creating and not self.reference:
            self.reference = f"INS-{self.pk:06d}"
            super().save(update_fields=["reference"])

    def calculate_score(self, save=True):
        total = 0.0
        possible = 0.0

        for resp in self.responses.select_related("question").all():
            q = resp.question
            if q and q.points:
                possible += float(q.points)
                if q.field_type == "checkbox":
                    if resp.valeur_bool:
                        total += float(q.points)
                else:
                    if resp.has_answer():
                        total += float(q.points)

        score_pct = (total / possible * 100.0) if possible else None
        if save:
            self.score = score_pct
            self.save(update_fields=["score"])
        return score_pct, possible

    def has_open_nc(self):
        return self.non_conformities.filter(resolved=False).exists()


class InspectionResponse(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(InspectionQuestion, null=True, blank=True, on_delete=models.SET_NULL, related_name="responses")

    valeur_bool = models.BooleanField(null=True, blank=True)
    valeur_texte = models.TextField(blank=True, null=True)
    valeur_num = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)

    photo = models.ImageField(upload_to="inspections/responses/photos/", blank=True, null=True)
    remarque = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("inspection", "question")

    def has_answer(self):
        return any([
            self.valeur_bool is not None,
            bool(self.valeur_texte and self.valeur_texte.strip()),
            self.valeur_num is not None,
            bool(self.photo),
        ])


class InspectionPhoto(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="inspections/photos/")
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class NonConformity(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="non_conformities")

    section = models.ForeignKey(InspectionSection, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    question = models.ForeignKey(InspectionQuestion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    titre = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=20, choices=SEVERITY, default="medium", db_index=True)

    reported_at = models.DateTimeField(auto_now_add=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="nc_assigned"
    )
    prestataire_responsible = models.ForeignKey(
        Prestataire, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="nc_presta"
    )

    due_date = models.DateField(blank=True, null=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-reported_at"]


class CorrectiveAction(models.Model):
    nc = models.ForeignKey(NonConformity, on_delete=models.CASCADE, related_name="actions")

    titre = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="actions_assigned"
    )

    date_target = models.DateField(blank=True, null=True)
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

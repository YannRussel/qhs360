from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.shortcuts import render
from django.utils import timezone


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _pct(part, total):
    if not total:
        return 0
    return round((part / total) * 100)


@login_required
def dashboard_kpi(request):
    org = _get_org(request)

    if not org:
        return render(request, "rapport/dashboard.html", {
            "organisation": None,
            "titre_page": "Rapports & KPI",
            "no_org": True,
        })

    # -----------------------------
    # Filtres globaux
    # -----------------------------
    site_id = (request.GET.get("site") or "").strip()
    prestataire_id = (request.GET.get("prestataire") or "").strip()
    period = (request.GET.get("period") or "30").strip()

    period_map = {
        "7": 7,
        "30": 30,
        "90": 90,
        "180": 180,
        "365": 365,
    }
    nb_days = period_map.get(period, 30)

    today = timezone.localdate()
    now_dt = timezone.now()
    date_from = now_dt - timedelta(days=nb_days)

    # -----------------------------
    # Imports métiers
    # -----------------------------
    from sites.models import Site, Zone, AffectationPrestataire
    from prestataire.models import Prestataire, AgentPrestataire, DocumentPrestataire
    from inspections.models import Inspection, NonConformity, CorrectiveAction
    from evenements.models import Evenement, ActionCAPA
    from incendie.models import (
        Extincteur, VerificationExtincteur,
        RIA, VerificationRIA,
        ControleSystemeIncendie,
        ExerciceEvacuation,
        ControleExerciceEvacuation,
        RapportInterventionIncendie,
    )
    from permis.models import (
        Formation, TypeHabilitation, AgentHabilitation,
        SessionFormation, ParticipantSession,
        Intervention, TypePermis, PermisDelivre,
    )
    from documentaire.models import Document, DocumentVersion, DocumentNotification

    # -----------------------------
    # Base querysets
    # -----------------------------
    sites_qs = Site.objects.filter(organisation=org)
    zones_qs = Zone.objects.filter(site__organisation=org)
    affectations_qs = AffectationPrestataire.objects.filter(site__organisation=org)

    prestataires_qs = Prestataire.objects.filter(organisation=org)
    agents_qs = AgentPrestataire.objects.filter(prestataire__organisation=org)
    docs_presta_qs = DocumentPrestataire.objects.filter(prestataire__organisation=org)

    inspections_qs = Inspection.objects.filter(organisation=org)
    nc_qs = NonConformity.objects.filter(inspection__organisation=org)
    corrective_qs = CorrectiveAction.objects.filter(nc__inspection__organisation=org)

    evenements_qs = Evenement.objects.filter(organisation=org)
    capa_qs = ActionCAPA.objects.filter(evenement__organisation=org)

    extincteurs_qs = Extincteur.objects.filter(site__organisation=org)
    verif_ext_qs = VerificationExtincteur.objects.filter(extincteur__site__organisation=org)
    ria_qs = RIA.objects.filter(site__organisation=org)
    verif_ria_qs = VerificationRIA.objects.filter(ria__site__organisation=org)
    systemes_qs = ControleSystemeIncendie.objects.filter(site__organisation=org)
    exercices_qs = ExerciceEvacuation.objects.filter(site__organisation=org)
    controle_ex_qs = ControleExerciceEvacuation.objects.filter(exercice__site__organisation=org)
    rapports_incendie_qs = RapportInterventionIncendie.objects.filter(site__organisation=org)

    formations_qs = Formation.objects.filter(organisation=org)
    types_hab_qs = TypeHabilitation.objects.filter(organisation=org)
    hab_qs = AgentHabilitation.objects.filter(type_habilitation__organisation=org)
    sessions_qs = SessionFormation.objects.filter(organisation=org)
    participants_qs = ParticipantSession.objects.filter(session__organisation=org)
    interventions_qs = Intervention.objects.filter(organisation=org)
    types_permis_qs = TypePermis.objects.filter(organisation=org)
    permis_qs = PermisDelivre.objects.filter(organisation=org)

    docs_qs = Document.objects.filter(organisation=org)
    doc_versions_qs = DocumentVersion.objects.filter(document__organisation=org)
    doc_notifs_qs = DocumentNotification.objects.filter(document__organisation=org)

    # -----------------------------
    # Filtre site
    # -----------------------------
    selected_site = None
    if site_id.isdigit():
        selected_site = sites_qs.filter(pk=int(site_id)).first()
        if selected_site:
            zones_qs = zones_qs.filter(site=selected_site)
            affectations_qs = affectations_qs.filter(site=selected_site)

            prestataires_qs = prestataires_qs.filter(affectations__site=selected_site).distinct()
            agents_qs = agents_qs.filter(prestataire__affectations__site=selected_site).distinct()
            docs_presta_qs = docs_presta_qs.filter(prestataire__affectations__site=selected_site).distinct()

            inspections_qs = inspections_qs.filter(site=selected_site)
            nc_qs = nc_qs.filter(inspection__site=selected_site)
            corrective_qs = corrective_qs.filter(nc__inspection__site=selected_site)

            evenements_qs = evenements_qs.filter(site=selected_site)
            capa_qs = capa_qs.filter(evenement__site=selected_site)

            extincteurs_qs = extincteurs_qs.filter(site=selected_site)
            verif_ext_qs = verif_ext_qs.filter(extincteur__site=selected_site)

            ria_qs = ria_qs.filter(site=selected_site)
            verif_ria_qs = verif_ria_qs.filter(ria__site=selected_site)

            systemes_qs = systemes_qs.filter(site=selected_site)
            exercices_qs = exercices_qs.filter(site=selected_site)
            controle_ex_qs = controle_ex_qs.filter(exercice__site=selected_site)
            rapports_incendie_qs = rapports_incendie_qs.filter(site=selected_site)

            docs_qs = docs_qs.filter(site=selected_site)
            doc_versions_qs = doc_versions_qs.filter(document__site=selected_site)
            doc_notifs_qs = doc_notifs_qs.filter(document__site=selected_site)

    # -----------------------------
    # Filtre prestataire
    # -----------------------------
    selected_prestataire = None
    if prestataire_id.isdigit():
        selected_prestataire = prestataires_qs.filter(pk=int(prestataire_id)).first()
        if selected_prestataire:
            agents_qs = agents_qs.filter(prestataire=selected_prestataire)
            docs_presta_qs = docs_presta_qs.filter(prestataire=selected_prestataire)

            inspections_qs = inspections_qs.filter(prestataire=selected_prestataire)
            nc_qs = nc_qs.filter(
                Q(inspection__prestataire=selected_prestataire) |
                Q(prestataire_responsible=selected_prestataire)
            ).distinct()
            corrective_qs = corrective_qs.filter(
                Q(nc__inspection__prestataire=selected_prestataire) |
                Q(nc__prestataire_responsible=selected_prestataire)
            ).distinct()

            evenements_qs = evenements_qs.filter(prestataire=selected_prestataire)
            capa_qs = capa_qs.filter(evenement__prestataire=selected_prestataire)

    # -----------------------------
    # Activité récente
    # -----------------------------
    inspections_recent_qs = inspections_qs.filter(date__gte=date_from)
    evenements_recent_qs = evenements_qs.filter(date_evenement__gte=date_from.date())
    sessions_recent_qs = sessions_qs.filter(date_debut__gte=date_from)
    interventions_recent_qs = interventions_qs.filter(date_debut__gte=date_from)
    doc_versions_recent_qs = doc_versions_qs.filter(cree_le__gte=date_from)
    rapports_incendie_recent_qs = rapports_incendie_qs.filter(date__gte=date_from.date())

    # -----------------------------
    # KPI globaux
    # -----------------------------
    total_sites = sites_qs.count()
    total_zones = zones_qs.count()
    total_affectations = affectations_qs.count()

    total_prestataires = prestataires_qs.count()
    total_agents = agents_qs.count()
    total_docs_presta = docs_presta_qs.count()

    total_inspections = inspections_qs.count()
    inspections_open = inspections_qs.filter(status="open").count()
    inspections_closed = inspections_qs.filter(status="closed").count()
    inspections_draft = inspections_qs.filter(status="draft").count()
    inspections_cancelled = inspections_qs.filter(status="cancelled").count()
    inspections_avg_score = inspections_qs.exclude(score__isnull=True).aggregate(avg=Avg("score"))["avg"] or 0

    total_nc = nc_qs.count()
    nc_open = nc_qs.filter(resolved=False).count()
    nc_closed = nc_qs.filter(resolved=True).count()

    total_corrective = corrective_qs.count()
    corrective_open = corrective_qs.filter(done=False).count()
    corrective_done = corrective_qs.filter(done=True).count()
    corrective_overdue = corrective_qs.filter(
        done=False,
        date_target__isnull=False,
        date_target__lt=today
    ).count()

    total_evenements = evenements_qs.count()
    evenements_open = evenements_qs.filter(date_cloture__isnull=True).count()
    accidents_count = evenements_qs.filter(type_evenement="accident").count()
    incidents_count = evenements_qs.filter(type_evenement="incident").count()
    presquaccidents_count = evenements_qs.filter(type_evenement="presquaccident").count()

    total_capa = capa_qs.count()
    capa_done = capa_qs.filter(statut="realisee").count()
    capa_retard = capa_qs.filter(statut="retard").count()
    capa_open = capa_qs.exclude(statut="realisee").count()

    total_extincteurs = extincteurs_qs.count()
    total_ria = ria_qs.count()
    total_systemes = systemes_qs.count()
    total_exercices = exercices_qs.count()
    total_rapports_incendie = rapports_incendie_qs.count()

    incendie_total = (
        verif_ext_qs.count()
        + verif_ria_qs.count()
        + systemes_qs.count()
        + controle_ex_qs.count()
    )
    incendie_conformes = (
        verif_ext_qs.filter(statut="conforme").count()
        + verif_ria_qs.filter(statut="conforme").count()
        + systemes_qs.filter(statut="conforme").count()
        + controle_ex_qs.filter(statut="conforme").count()
    )
    incendie_nc = (
        verif_ext_qs.filter(statut="nc").count()
        + verif_ria_qs.filter(statut="nc").count()
        + systemes_qs.filter(statut="nc").count()
        + controle_ex_qs.filter(statut="nc").count()
    )
    incendie_pct = _pct(incendie_conformes, incendie_total)

    total_formations = formations_qs.count()
    total_types_hab = types_hab_qs.count()
    total_habs = hab_qs.count()
    total_sessions = sessions_qs.count()
    total_participants = participants_qs.count()
    total_interventions = interventions_qs.count()
    total_types_permis = types_permis_qs.count()
    total_permis = permis_qs.count()

    permis_attente = permis_qs.filter(statut="en_attente").count()
    permis_valides = permis_qs.filter(statut="valide").count()
    permis_refuses = permis_qs.filter(statut="refuse").count()
    permis_actifs = permis_qs.filter(actif=True).count()

    hab_valides = hab_qs.filter(actif=True).filter(
        Q(date_expiration__isnull=True) | Q(date_expiration__gte=today)
    ).count()
    hab_expirees = hab_qs.filter(actif=True, date_expiration__lt=today).count()
    hab_bientot = hab_qs.filter(
        actif=True,
        date_expiration__isnull=False,
        date_expiration__gte=today,
        date_expiration__lte=today + timedelta(days=30)
    ).count()

    total_docs = docs_qs.count()
    docs_brouillon = docs_qs.filter(statut="brouillon").count()
    docs_validation = docs_qs.filter(statut="validation").count()
    docs_approuves = docs_qs.filter(statut="approuve").count()
    docs_obsoletes = docs_qs.filter(statut="obsolete").count()
    docs_retard = docs_qs.filter(date_prochaine_revision__lt=today).count()
    docs_confidentiels = docs_qs.filter(confidentialite=True).count()
    total_doc_versions = doc_versions_qs.count()
    unread_notifs = doc_notifs_qs.filter(user=request.user, lu=False).count()

    # -----------------------------
    # Pourcentages
    # -----------------------------
    inspections_close_pct = _pct(inspections_closed, total_inspections)
    nc_close_pct = _pct(nc_closed, total_nc)
    corrective_done_pct = _pct(corrective_done, total_corrective)
    capa_done_pct = _pct(capa_done, total_capa)
    permis_valid_pct = _pct(permis_valides, total_permis)
    hab_valid_pct = _pct(hab_valides, total_habs)
    docs_approved_pct = _pct(docs_approuves, total_docs)

    # -----------------------------
    # Cartes principales
    # -----------------------------
    overview_cards = [
        {
            "title": "Sites",
            "value": total_sites,
            "icon": "🏢",
            "sub": f"{total_zones} zones",
            "url": "sites:liste",
        },
        {
            "title": "Prestataires",
            "value": total_prestataires,
            "icon": "👷",
            "sub": f"{total_agents} agents",
            "url": "prestataire:liste",
        },
        {
            "title": "Inspections ouvertes",
            "value": inspections_open,
            "icon": "✅",
            "sub": f"{round(inspections_avg_score, 1)}% score moyen",
            "url": "inspections:dashboard_inspections",
        },
        {
            "title": "NC ouvertes",
            "value": nc_open,
            "icon": "🚨",
            "sub": f"{corrective_overdue} en retard",
            "url": "inspections:registre_inspections",
        },
        {
            "title": "Événements ouverts",
            "value": evenements_open,
            "icon": "⚠️",
            "sub": f"{total_evenements} dossiers",
            "url": "evenements:dashboard_evenement",
        },
        {
            "title": "Permis actifs",
            "value": permis_actifs,
            "icon": "📝",
            "sub": f"{permis_attente} en attente",
            "url": "permis:dashboard_permis_interventions",
        },
        {
            "title": "Habilitations bientôt expirées",
            "value": hab_bientot,
            "icon": "🎓",
            "sub": f"{hab_expirees} expirées",
            "url": "permis:habilitation_dashboard",
        },
        {
            "title": "Documents à réviser",
            "value": docs_retard,
            "icon": "📂",
            "sub": f"{unread_notifs} notifications",
            "url": "documentaire:list",
        },
    ]

    # -----------------------------
    # Cartes performance
    # -----------------------------
    performance_cards = [
        {
            "label": "Conformité incendie",
            "value": incendie_pct,
            "hint": f"{incendie_conformes} conformes / {incendie_total}",
        },
        {
            "label": "Clôture inspections",
            "value": inspections_close_pct,
            "hint": f"{inspections_closed} clôturées / {total_inspections}",
        },
        {
            "label": "Résolution NC",
            "value": nc_close_pct,
            "hint": f"{nc_closed} résolues / {total_nc}",
        },
        {
            "label": "Actions correctives terminées",
            "value": corrective_done_pct,
            "hint": f"{corrective_done} réalisées / {total_corrective}",
        },
        {
            "label": "CAPA terminées",
            "value": capa_done_pct,
            "hint": f"{capa_done} réalisées / {total_capa}",
        },
        {
            "label": "Permis validés",
            "value": permis_valid_pct,
            "hint": f"{permis_valides} validés / {total_permis}",
        },
        {
            "label": "Habilitations valides",
            "value": hab_valid_pct,
            "hint": f"{hab_valides} valides / {total_habs}",
        },
        {
            "label": "Documents approuvés",
            "value": docs_approved_pct,
            "hint": f"{docs_approuves} approuvés / {total_docs}",
        },
    ]

    # -----------------------------
    # Alertes
    # -----------------------------
    alerts = []

    if corrective_overdue:
        alerts.append({
            "level": "danger",
            "title": "Actions correctives en retard",
            "value": corrective_overdue,
            "desc": "Des actions liées aux inspections dépassent leur date cible.",
            "url": "inspections:registre_inspections",
        })

    if capa_retard:
        alerts.append({
            "level": "warning",
            "title": "CAPA en retard",
            "value": capa_retard,
            "desc": "Certaines actions des événements HSE sont en retard.",
            "url": "evenements:actions_suivi",
        })

    if hab_bientot:
        alerts.append({
            "level": "warning",
            "title": "Habilitations à renouveler",
            "value": hab_bientot,
            "desc": "Des habilitations approchent de leur expiration.",
            "url": "permis:habilitation_dashboard",
        })

    if docs_retard:
        alerts.append({
            "level": "danger",
            "title": "Documents en retard de révision",
            "value": docs_retard,
            "desc": "Des documents dépassent leur date de révision prévue.",
            "url": "documentaire:list",
        })

    if permis_attente:
        alerts.append({
            "level": "info",
            "title": "Permis en attente",
            "value": permis_attente,
            "desc": "Des permis doivent encore être évalués ou validés.",
            "url": "permis:permis_liste",
        })

    if evenements_open:
        alerts.append({
            "level": "info",
            "title": "Événements non clôturés",
            "value": evenements_open,
            "desc": "Des dossiers restent encore ouverts.",
            "url": "evenements:dashboard_evenement",
        })

    # -----------------------------
    # Liens rapides
    # -----------------------------
    quick_links = [
        {"label": "Accueil", "url": "core:accueil", "icon": "🏠"},
        {"label": "Sites", "url": "sites:liste", "icon": "📍"},
        {"label": "Prestataires", "url": "prestataire:liste", "icon": "👷"},
        {"label": "Formations", "url": "permis:formation_dashboard", "icon": "🎓"},
        {"label": "Permis", "url": "permis:dashboard_permis_interventions", "icon": "📝"},
        {"label": "Inspections", "url": "inspections:dashboard_inspections", "icon": "✅"},
        {"label": "Événements", "url": "evenements:dashboard_evenement", "icon": "⚠️"},
        {"label": "Incendie", "url": "incendie:dashboard", "icon": "🔥"},
        {"label": "Documents", "url": "documentaire:list", "icon": "📂"},
    ]

    # -----------------------------
    # Récent
    # -----------------------------
    recent_inspections = inspections_qs.select_related("site", "prestataire", "template").order_by("-date")[:6]
    recent_evenements = evenements_qs.select_related("site", "prestataire").order_by("-date_evenement", "-cree_le")[:6]
    recent_permis = permis_qs.select_related("agent", "agent__prestataire", "type_permis", "intervention").order_by("-date_delivrance")[:6]
    recent_documents = docs_qs.select_related("site", "type_document", "version_courante").order_by("-modifie_le", "-cree_le")[:6]

    # -----------------------------
    # Charts
    # -----------------------------
    charts = {
        "inspections": {
            "labels": ["Ouvertes", "Clôturées", "Brouillons", "Annulées"],
            "data": [inspections_open, inspections_closed, inspections_draft, inspections_cancelled],
        },
        "evenements": {
            "labels": ["Accidents", "Incidents", "Presqu'accidents"],
            "data": [accidents_count, incidents_count, presquaccidents_count],
        },
        "permis": {
            "labels": ["Validés", "En attente", "Refusés"],
            "data": [permis_valides, permis_attente, permis_refuses],
        },
        "documents": {
            "labels": ["Brouillon", "Validation", "Approuvé", "Obsolète"],
            "data": [docs_brouillon, docs_validation, docs_approuves, docs_obsoletes],
        },
        "incendie": {
            "labels": ["Conformes", "Non conformes"],
            "data": [incendie_conformes, incendie_nc],
        },
    }

    context = {
        "organisation": org,
        "titre_page": "Rapports & KPI",
        "no_org": False,
        "today": today,

        "sites": Site.objects.filter(organisation=org).order_by("nom"),
        "prestataires": Prestataire.objects.filter(organisation=org).order_by("nom"),

        "filters": {
            "site": site_id,
            "prestataire": prestataire_id,
            "period": period,
        },

        "overview_cards": overview_cards,
        "performance_cards": performance_cards,
        "alerts": alerts,
        "quick_links": quick_links,
        "charts": charts,

        "recent_inspections": recent_inspections,
        "recent_evenements": recent_evenements,
        "recent_permis": recent_permis,
        "recent_documents": recent_documents,

        "stats": {
            "sites": total_sites,
            "zones": total_zones,
            "affectations": total_affectations,

            "prestataires": total_prestataires,
            "agents": total_agents,
            "docs_prestataires": total_docs_presta,

            "inspections_total": total_inspections,
            "inspections_open": inspections_open,
            "inspections_closed": inspections_closed,
            "inspections_avg_score": round(inspections_avg_score, 1),

            "nc_total": total_nc,
            "nc_open": nc_open,
            "nc_closed": nc_closed,
            "corrective_total": total_corrective,
            "corrective_open": corrective_open,
            "corrective_done": corrective_done,
            "corrective_overdue": corrective_overdue,

            "evenements_total": total_evenements,
            "evenements_open": evenements_open,
            "accidents": accidents_count,
            "incidents": incidents_count,
            "presquaccidents": presquaccidents_count,
            "capa_total": total_capa,
            "capa_open": capa_open,
            "capa_done": capa_done,
            "capa_retard": capa_retard,

            "extincteurs": total_extincteurs,
            "ria": total_ria,
            "systemes": total_systemes,
            "exercices": total_exercices,
            "rapports_incendie": total_rapports_incendie,
            "incendie_total": incendie_total,
            "incendie_conformes": incendie_conformes,
            "incendie_nc": incendie_nc,
            "incendie_pct": incendie_pct,

            "formations": total_formations,
            "types_hab": total_types_hab,
            "habilitations": total_habs,
            "hab_valides": hab_valides,
            "hab_expirees": hab_expirees,
            "hab_bientot": hab_bientot,
            "sessions": total_sessions,
            "participants": total_participants,
            "interventions": total_interventions,
            "types_permis": total_types_permis,
            "permis_total": total_permis,
            "permis_actifs": permis_actifs,
            "permis_valides": permis_valides,
            "permis_attente": permis_attente,
            "permis_refuses": permis_refuses,

            "docs_total": total_docs,
            "docs_brouillon": docs_brouillon,
            "docs_validation": docs_validation,
            "docs_approuves": docs_approuves,
            "docs_obsoletes": docs_obsoletes,
            "docs_retard": docs_retard,
            "docs_confidentiels": docs_confidentiels,
            "doc_versions": total_doc_versions,
            "doc_notifs": unread_notifs,

            "activity_inspections": inspections_recent_qs.count(),
            "activity_evenements": evenements_recent_qs.count(),
            "activity_sessions": sessions_recent_qs.count(),
            "activity_interventions": interventions_recent_qs.count(),
            "activity_versions": doc_versions_recent_qs.count(),
            "activity_rapports_incendie": rapports_incendie_recent_qs.count(),
        }
    }

    return render(request, "rapport/dashboard.html", context)
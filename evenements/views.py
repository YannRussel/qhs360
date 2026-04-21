from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from organisations.models import Organisation
from sites.models import Site, Zone
from prestataire.models import Prestataire, AgentPrestataire

from .models import (
    Evenement, PersonneImpliquee, Temoin, PieceJointe,
    EnqueteAccident, ActionCAPA, StatistiquesHSE,
    ChronologieFait, Analyse5Pourquoi, ArbreCauseNoeud
)


def _get_org(request) -> Organisation:
    if request.user.is_superuser and request.GET.get("org"):
        return get_object_or_404(Organisation, pk=request.GET["org"])
    if not getattr(request.user, "organisation", None):
        raise Http404("Aucune organisation liée à ce compte.")
    return request.user.organisation


def _bool(v):
    return v in ("1", "true", "True", "on", "yes", "oui")


def _int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default


@login_required
def evenements_dashboard(request):
    org = _get_org(request)

    q = (request.GET.get("q") or "").strip()
    type_evt = (request.GET.get("type") or "").strip()
    site_id = request.GET.get("site") or ""
    statut = (request.GET.get("statut") or "").strip()

    qs = Evenement.objects.filter(organisation=org).select_related("site", "zone", "prestataire")

    if q:
        qs = qs.filter(
            Q(reference__icontains=q) |
            Q(lieu_precis__icontains=q) |
            Q(service_departement__icontains=q) |
            Q(description__icontains=q)
        )
    if type_evt:
        qs = qs.filter(type_evenement=type_evt)
    if site_id.isdigit():
        qs = qs.filter(site_id=int(site_id))
    if statut == "ouvert":
        qs = qs.filter(date_cloture__isnull=True)
    elif statut == "cloture":
        qs = qs.filter(date_cloture__isnull=False)

    # KPI rapides
    kpi_total = qs.count()
    kpi_accidents = qs.filter(type_evenement="accident").count()
    kpi_incidents = qs.filter(type_evenement="incident").count()
    kpi_actions = ActionCAPA.objects.filter(evenement__organisation=org).count()

    ctx = {
        "org": org,
        "items": qs[:200],
        "sites": Site.objects.filter(organisation=org, actif=True).order_by("nom"),
        "prestataires": Prestataire.objects.filter(organisation=org, actif=True).order_by("nom"),
        "kpi_total": kpi_total,
        "kpi_accidents": kpi_accidents,
        "kpi_incidents": kpi_incidents,
        "kpi_actions": kpi_actions,
        "filters": {"q": q, "type": type_evt, "site": site_id, "statut": statut},
    }
    return render(request, "evenements/dashboard.html", ctx)


@login_required
def evenement_create(request):
    org = _get_org(request)
    sites = Site.objects.filter(organisation=org, actif=True).order_by("nom")
    prestataires = Prestataire.objects.filter(organisation=org, actif=True).order_by("nom")

    if request.method == "POST":
        site_id = request.POST.get("site") or ""
        zone_id = request.POST.get("zone") or ""
        prest_id = request.POST.get("prestataire") or ""

        ev = Evenement.objects.create(
            organisation=org,
            reference=(request.POST.get("reference") or "").strip(),
            type_evenement=request.POST.get("type_evenement"),
            date_evenement=request.POST.get("date_evenement") or date.today(),
            heure=request.POST.get("heure") or None,
            lieu_precis=(request.POST.get("lieu_precis") or "").strip(),
            service_departement=(request.POST.get("service_departement") or "").strip(),
            declarant_nom_fonction=(request.POST.get("declarant_nom_fonction") or "").strip(),
            site_id=int(site_id) if site_id.isdigit() else None,
            zone_id=int(zone_id) if zone_id.isdigit() else None,
            prestataire_id=int(prest_id) if prest_id.isdigit() else None,

            description=request.POST.get("description") or "",
            nature_accident=(request.POST.get("nature_accident") or "").strip(),
            partie_corps=(request.POST.get("partie_corps") or "").strip(),
            gravite_apparente=(request.POST.get("gravite_apparente") or "").strip(),
            niveau_gravite_dossier=(request.POST.get("niveau_gravite_dossier") or "").strip(),

            dommages_materiels=_bool(request.POST.get("dommages_materiels")),
            impact_environnemental=_bool(request.POST.get("impact_environnemental")),

            mesures_premiers_secours=_bool(request.POST.get("mesures_premiers_secours")),
            mesures_mise_en_securite=_bool(request.POST.get("mesures_mise_en_securite")),
            mesures_arret_activite=_bool(request.POST.get("mesures_arret_activite")),
            mesures_balisage=_bool(request.POST.get("mesures_balisage")),
            mesures_alerte_hse=_bool(request.POST.get("mesures_alerte_hse")),
            mesures_autres=(request.POST.get("mesures_autres") or "").strip(),

            analyse_humaine=_bool(request.POST.get("analyse_humaine")),
            analyse_technique=_bool(request.POST.get("analyse_technique")),
            analyse_organisationnelle=_bool(request.POST.get("analyse_organisationnelle")),
            analyse_environnementale=_bool(request.POST.get("analyse_environnementale")),

            date_ouverture=request.POST.get("date_ouverture") or date.today(),
            date_cloture_prevue=request.POST.get("date_cloture_prevue") or None,

            validation_declarant=(request.POST.get("validation_declarant") or "").strip(),
            validation_hierarchique=(request.POST.get("validation_hierarchique") or "").strip(),
            validation_hse=(request.POST.get("validation_hse") or "").strip(),
        )

        messages.success(request, "Événement créé.")
        return redirect("evenements:evenement_detail", pk=ev.pk)

    return render(request, "evenements/evenement_form.html", {
        "org": org, "sites": sites, "prestataires": prestataires, "zones": [],
        "mode": "create",
        "today": date.today().isoformat(),
    })


@login_required
def evenement_edit(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    sites = Site.objects.filter(organisation=org, actif=True).order_by("nom")
    prestataires = Prestataire.objects.filter(organisation=org, actif=True).order_by("nom")
    zones = Zone.objects.filter(site=ev.site, actif=True).order_by("nom") if ev.site_id else Zone.objects.none()

    if request.method == "POST":
        site_id = request.POST.get("site") or ""
        zone_id = request.POST.get("zone") or ""
        prest_id = request.POST.get("prestataire") or ""

        ev.reference = (request.POST.get("reference") or "").strip()
        ev.type_evenement = request.POST.get("type_evenement")
        ev.date_evenement = request.POST.get("date_evenement") or ev.date_evenement
        ev.heure = request.POST.get("heure") or None
        ev.lieu_precis = (request.POST.get("lieu_precis") or "").strip()
        ev.service_departement = (request.POST.get("service_departement") or "").strip()
        ev.declarant_nom_fonction = (request.POST.get("declarant_nom_fonction") or "").strip()

        ev.site_id = int(site_id) if site_id.isdigit() else None
        ev.zone_id = int(zone_id) if zone_id.isdigit() else None
        ev.prestataire_id = int(prest_id) if prest_id.isdigit() else None

        ev.description = request.POST.get("description") or ""
        ev.nature_accident = (request.POST.get("nature_accident") or "").strip()
        ev.partie_corps = (request.POST.get("partie_corps") or "").strip()
        ev.gravite_apparente = (request.POST.get("gravite_apparente") or "").strip()
        ev.niveau_gravite_dossier = (request.POST.get("niveau_gravite_dossier") or "").strip()

        ev.dommages_materiels = _bool(request.POST.get("dommages_materiels"))
        ev.impact_environnemental = _bool(request.POST.get("impact_environnemental"))

        ev.mesures_premiers_secours = _bool(request.POST.get("mesures_premiers_secours"))
        ev.mesures_mise_en_securite = _bool(request.POST.get("mesures_mise_en_securite"))
        ev.mesures_arret_activite = _bool(request.POST.get("mesures_arret_activite"))
        ev.mesures_balisage = _bool(request.POST.get("mesures_balisage"))
        ev.mesures_alerte_hse = _bool(request.POST.get("mesures_alerte_hse"))
        ev.mesures_autres = (request.POST.get("mesures_autres") or "").strip()

        ev.analyse_humaine = _bool(request.POST.get("analyse_humaine"))
        ev.analyse_technique = _bool(request.POST.get("analyse_technique"))
        ev.analyse_organisationnelle = _bool(request.POST.get("analyse_organisationnelle"))
        ev.analyse_environnementale = _bool(request.POST.get("analyse_environnementale"))

        ev.date_ouverture = request.POST.get("date_ouverture") or ev.date_ouverture
        ev.date_cloture_prevue = request.POST.get("date_cloture_prevue") or None
        ev.date_cloture = request.POST.get("date_cloture") or None

        dcv = request.POST.get("dossier_cloture_validee")
        if dcv == "1":
            ev.dossier_cloture_validee = True
        elif dcv == "0":
            ev.dossier_cloture_validee = False
        else:
            ev.dossier_cloture_validee = None

        ev.validation_declarant = (request.POST.get("validation_declarant") or "").strip()
        ev.validation_hierarchique = (request.POST.get("validation_hierarchique") or "").strip()
        ev.validation_hse = (request.POST.get("validation_hse") or "").strip()

        ev.validation_qhs = (request.POST.get("validation_qhs") or "").strip()
        ev.validation_direction = (request.POST.get("validation_direction") or "").strip()

        ev.save()
        messages.success(request, "Événement mis à jour.")
        return redirect("evenements:evenement_detail", pk=ev.pk)

    return render(request, "evenements/evenement_form.html", {
        "org": org, "sites": sites, "prestataires": prestataires, "zones": zones,
        "ev": ev, "mode": "edit",
        "today": date.today().isoformat(),
    })


@login_required
def evenement_detail(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    enquete = getattr(ev, "enquete", None)

    return render(request, "evenements/evenement_detail.html", {
        "org": org,
        "ev": ev,
        "enquete": enquete,
        "agents_prestataire": AgentPrestataire.objects.filter(prestataire=ev.prestataire, actif=True).order_by("nom") if ev.prestataire_id else [],
    })


@login_required
def personne_add(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    if request.method == "POST":
        agent_id = request.POST.get("agent_prestataire") or ""
        PersonneImpliquee.objects.create(
            evenement=ev,
            agent_prestataire_id=int(agent_id) if agent_id.isdigit() else None,
            nom_prenom=(request.POST.get("nom_prenom") or "").strip(),
            statut=(request.POST.get("statut") or "").strip(),
            entreprise_prestataire=(request.POST.get("entreprise_prestataire") or "").strip(),
            poste_fonction=(request.POST.get("poste_fonction") or "").strip(),
            anciennete=(request.POST.get("anciennete") or "").strip(),
            formation_habilitation_valide=(request.POST.get("formation_habilitation_valide") or "").strip(),
        )
        messages.success(request, "Personne impliquée ajoutée.")
    return redirect("evenements:evenement_detail", pk=pk)


@login_required
def temoin_add(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    if request.method == "POST":
        Temoin.objects.create(
            evenement=ev,
            nom=(request.POST.get("nom") or "").strip(),
            fonction=(request.POST.get("fonction") or "").strip(),
            contact=(request.POST.get("contact") or "").strip(),
        )
        messages.success(request, "Témoin ajouté.")
    return redirect("evenements:evenement_detail", pk=pk)


@login_required
def piece_add(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    if request.method == "POST":
        f = request.FILES.get("fichier")
        if not f:
            messages.error(request, "Fichier manquant.")
            return redirect("evenements:evenement_detail", pk=pk)

        PieceJointe.objects.create(
            evenement=ev,
            type_piece=request.POST.get("type_piece"),
            fichier=f,
            titre=(request.POST.get("titre") or "").strip(),
        )
        messages.success(request, "Pièce jointe ajoutée.")
    return redirect("evenements:evenement_detail", pk=pk)


# ============================
# ENQUÊTE (MAJ) : méthode + 5P
# ============================

@login_required
def enquete_edit(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)
    enquete, _ = EnqueteAccident.objects.get_or_create(evenement=ev)

    chrono = ChronologieFait.objects.filter(enquete=enquete).select_related("parent")
    arbre = ArbreCauseNoeud.objects.filter(enquete=enquete).select_related("parent")
    analyse_5p = getattr(enquete, "analyse_5p", None)

    if request.method == "POST":
        enquete.equipe_enquete = request.POST.get("equipe_enquete") or ""
        enquete.deroulement_faits = request.POST.get("deroulement_faits") or ""
        enquete.methode_analyse = (request.POST.get("methode_analyse") or "").strip()

        # Causes générales en cases à cocher
        causes_humaines_list = request.POST.getlist("causes_humaines[]")
        causes_techniques_list = request.POST.getlist("causes_techniques[]")
        causes_organisationnelles_list = request.POST.getlist("causes_organisationnelles[]")
        causes_environnementales_list = request.POST.getlist("causes_environnementales[]")

        enquete.causes_humaines = "\n".join([f"- {x}" for x in causes_humaines_list]) if causes_humaines_list else ""
        enquete.causes_techniques = "\n".join([f"- {x}" for x in causes_techniques_list]) if causes_techniques_list else ""
        enquete.causes_organisationnelles = "\n".join([f"- {x}" for x in causes_organisationnelles_list]) if causes_organisationnelles_list else ""
        enquete.causes_environnementales = "\n".join([f"- {x}" for x in causes_environnementales_list]) if causes_environnementales_list else ""

        enquete.fc_formation_non_valide = _bool(request.POST.get("fc_formation_non_valide"))
        enquete.fc_habilitation_expiree = _bool(request.POST.get("fc_habilitation_expiree"))
        enquete.fc_permis_non_conforme = _bool(request.POST.get("fc_permis_non_conforme"))
        enquete.fc_epi_non_porte = _bool(request.POST.get("fc_epi_non_porte"))
        enquete.fc_procedure_non_appliquee = _bool(request.POST.get("fc_procedure_non_appliquee"))
        enquete.fc_supervision_insuffisante = _bool(request.POST.get("fc_supervision_insuffisante"))

        enquete.lien_formation = _bool(request.POST.get("lien_formation"))
        enquete.lien_habilitation = _bool(request.POST.get("lien_habilitation"))
        enquete.lien_permis = _bool(request.POST.get("lien_permis"))
        enquete.lien_procedure = _bool(request.POST.get("lien_procedure"))

        enquete.conclusion = request.POST.get("conclusion") or ""
        enquete.validation_responsable_hse = (request.POST.get("validation_responsable_hse") or "").strip()
        enquete.validation_chef_site_direction = (request.POST.get("validation_chef_site_direction") or "").strip()

        demande_cloture = _bool(request.POST.get("cloture_enquete"))

        chrono_count = ChronologieFait.objects.filter(enquete=enquete).count()
        arbre_count = ArbreCauseNoeud.objects.filter(enquete=enquete).count()

        if enquete.methode_analyse == "5p":
            personnel_list = request.POST.getlist("personnel[]")
            procedures_list = request.POST.getlist("procedures[]")
            produits_list = request.POST.getlist("produits[]")
            procede_list = request.POST.getlist("procede[]")
            place_list = request.POST.getlist("place[]")

            personnel_txt = (request.POST.get("p_personnel") or "").strip()
            procedures_txt = (request.POST.get("p_procedures") or "").strip()
            produits_txt = (request.POST.get("p_produits") or "").strip()
            procede_txt = (request.POST.get("p_procede") or "").strip()
            place_txt = (request.POST.get("p_place") or "").strip()

            personnel = "\n".join([f"- {x}" for x in personnel_list]) if personnel_list else personnel_txt
            procedures = "\n".join([f"- {x}" for x in procedures_list]) if procedures_list else procedures_txt
            produits = "\n".join([f"- {x}" for x in produits_list]) if produits_list else produits_txt
            procede = "\n".join([f"- {x}" for x in procede_list]) if procede_list else procede_txt
            place = "\n".join([f"- {x}" for x in place_list]) if place_list else place_txt

            cause_finale = (
                (request.POST.get("cause_racine_finale") or "").strip()
                or (request.POST.get("p_cause_racine_finale") or "").strip()
            )

            missing = []
            for label, value in [
                ("Personnel", personnel),
                ("Procédures", procedures),
                ("Produits", produits),
                ("Procédé", procede),
                ("Place / Environnement", place),
            ]:
                if not value:
                    missing.append(label)

            if not cause_finale:
                missing.append("Cause racine finale")

            if missing:
                messages.error(request, "Analyse 5P incomplète : " + ", ".join(missing))
                return redirect("evenements:enquete_edit", pk=pk)

            Analyse5Pourquoi.objects.update_or_create(
                enquete=enquete,
                defaults={
                    "pourquoi1": "Personnel",
                    "reponse1": personnel,

                    "pourquoi2": "Procédures",
                    "reponse2": procedures,

                    "pourquoi3": "Produits",
                    "reponse3": produits,

                    "pourquoi4": "Procédé",
                    "reponse4": procede,

                    "pourquoi5": "Place / Environnement",
                    "reponse5": place,

                    "cause_racine_finale": cause_finale,
                }
            )

        elif enquete.methode_analyse == "arbre":
            pass
        else:
            Analyse5Pourquoi.objects.filter(enquete=enquete).delete()

        if demande_cloture:
            if chrono_count == 0:
                messages.error(request, "Impossible de clôturer : ajoute au moins un fait dans la chronologie.")
                return redirect("evenements:enquete_edit", pk=pk)

            if enquete.methode_analyse == "5p":
                analyse_existante = Analyse5Pourquoi.objects.filter(enquete=enquete).exists()
                if not analyse_existante:
                    messages.error(request, "Impossible de clôturer : l’analyse 5P est vide.")
                    return redirect("evenements:enquete_edit", pk=pk)

            if enquete.methode_analyse == "arbre" and arbre_count == 0:
                messages.error(request, "Impossible de clôturer : l’arbre des causes est vide.")
                return redirect("evenements:enquete_edit", pk=pk)

        enquete.cloture_enquete = demande_cloture
        enquete.save()

        messages.success(request, "Enquête enregistrée.")
        return redirect("evenements:evenement_detail", pk=pk)

    return render(request, "evenements/enquete_form.html", {
        "org": org,
        "ev": ev,
        "enquete": enquete,
        "chronologie": chrono,
        "arbre_causes": arbre,
        "analyse_5p": analyse_5p,
    })
# ====================================
# CHRONOLOGIE : API JSON + actions POST
# ====================================

@login_required
def api_chrono_add(request, pk):
    """
    POST:
      - date_fait (YYYY-MM-DD)
      - heure_fait (HH:MM) optionnel
      - description
      - parent_id optionnel
      - ordre optionnel
    """
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)
    enquete, _ = EnqueteAccident.objects.get_or_create(evenement=ev)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    parent_id = request.POST.get("parent_id") or ""
    parent = None
    if parent_id.isdigit():
        parent = get_object_or_404(ChronologieFait, pk=int(parent_id), enquete=enquete)

    item = ChronologieFait.objects.create(
        enquete=enquete,
        parent=parent,
        date_fait=request.POST.get("date_fait"),
        heure_fait=request.POST.get("heure_fait") or None,
        description=(request.POST.get("description") or "").strip(),
        ordre=_int(request.POST.get("ordre"), 1) or 1
    )
    return JsonResponse({"ok": True, "id": item.id})


@login_required
def api_chrono_edit(request, chrono_id):
    """
    POST:
      - date_fait, heure_fait, description, ordre
    """
    org = _get_org(request)
    item = get_object_or_404(ChronologieFait, pk=chrono_id, enquete__evenement__organisation=org)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    if request.POST.get("date_fait"):
        item.date_fait = request.POST.get("date_fait")
    item.heure_fait = request.POST.get("heure_fait") or None
    if request.POST.get("description") is not None:
        item.description = (request.POST.get("description") or "").strip()
    if request.POST.get("ordre"):
        item.ordre = _int(request.POST.get("ordre"), item.ordre) or item.ordre

    item.save()
    return JsonResponse({"ok": True})


@login_required
def api_chrono_delete(request, chrono_id):
    """
    POST : supprime un fait (et ses sous-faits via CASCADE)
    """
    org = _get_org(request)
    item = get_object_or_404(ChronologieFait, pk=chrono_id, enquete__evenement__organisation=org)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    item.delete()
    return JsonResponse({"ok": True})


# ====================================
# ARBRE DES CAUSES : API JSON + actions
# ====================================

@login_required
def api_arbre_add(request, pk):
    """
    POST:
      - type_noeud: fait/cause/barriere/cause_racine
      - cause (obligatoire)
      - pourquoi (optionnel)
      - reponse (optionnel)
      - parent_id optionnel
      - logique optionnel (et/ou)
      - ordre optionnel
      - est_cause_racine optionnel
    """
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)
    enquete, _ = EnqueteAccident.objects.get_or_create(evenement=ev)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    parent_id = request.POST.get("parent_id") or ""
    parent = None
    niveau = 0

    if parent_id.isdigit():
        parent = get_object_or_404(ArbreCauseNoeud, pk=int(parent_id), enquete=enquete)
        niveau = (parent.niveau or 0) + 1

    cause = (request.POST.get("cause") or "").strip()
    pourquoi = (request.POST.get("pourquoi") or "").strip()
    reponse = (request.POST.get("reponse") or "").strip()

    if not cause:
        return JsonResponse({"ok": False, "error": "La cause est obligatoire."}, status=400)

    type_noeud = (request.POST.get("type_noeud") or "cause").strip()
    est_cause_racine = _bool(request.POST.get("est_cause_racine"))

    if type_noeud == "cause_racine":
        est_cause_racine = True

    node = ArbreCauseNoeud.objects.create(
        enquete=enquete,
        parent=parent,
        type_noeud=type_noeud,
        cause=cause,
        pourquoi=pourquoi,
        reponse=reponse,
        logique=(request.POST.get("logique") or "").strip() or None,
        ordre=_int(request.POST.get("ordre"), 1) or 1,
        niveau=niveau,
        est_cause_racine=est_cause_racine,
    )

    return JsonResponse({
        "ok": True,
        "id": node.id,
        "niveau": node.niveau,
    })


@login_required
def api_arbre_edit(request, node_id):
    """
    POST:
      - type_noeud
      - cause
      - pourquoi
      - reponse
      - logique
      - ordre
      - est_cause_racine
    """
    org = _get_org(request)
    node = get_object_or_404(ArbreCauseNoeud, pk=node_id, enquete__evenement__organisation=org)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    if request.POST.get("type_noeud"):
        node.type_noeud = request.POST.get("type_noeud")

    if request.POST.get("cause") is not None:
        node.cause = (request.POST.get("cause") or "").strip()

    if request.POST.get("pourquoi") is not None:
        node.pourquoi = (request.POST.get("pourquoi") or "").strip()

    if request.POST.get("reponse") is not None:
        node.reponse = (request.POST.get("reponse") or "").strip()

    lg = (request.POST.get("logique") or "").strip()
    node.logique = lg or None

    if request.POST.get("ordre"):
        node.ordre = _int(request.POST.get("ordre"), node.ordre) or node.ordre

    if request.POST.get("est_cause_racine") is not None:
        node.est_cause_racine = _bool(request.POST.get("est_cause_racine"))

    if node.type_noeud == "cause_racine":
        node.est_cause_racine = True

    node.save()
    return JsonResponse({"ok": True})


@login_required
def api_arbre_delete(request, node_id):
    """
    POST : supprime un noeud (et ses enfants via CASCADE)
    """
    org = _get_org(request)
    node = get_object_or_404(ArbreCauseNoeud, pk=node_id, enquete__evenement__organisation=org)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST requis"}, status=405)

    node.delete()
    return JsonResponse({"ok": True})
# ============================
# ACTIONS CAPA / STATS (inchangé)
# ============================

@login_required
def action_add(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    if request.method == "POST":
        preuve = request.FILES.get("preuve")

        # auto-numéro
        next_num = (ev.actions.aggregate(m=Count("id")).get("m") or 0) + 1

        ActionCAPA.objects.create(
            evenement=ev,
            numero=int(request.POST.get("numero") or next_num),
            type_action=request.POST.get("type_action"),
            description_action=request.POST.get("description_action") or "",
            cause_racine=(request.POST.get("cause_racine") or "").strip(),
            responsable=(request.POST.get("responsable") or "").strip(),
            service_societe=(request.POST.get("service_societe") or "").strip(),
            delai=request.POST.get("delai") or None,
            statut=request.POST.get("statut") or "a_faire",
            priorite=(request.POST.get("priorite") or "").strip(),
            date_realisation=request.POST.get("date_realisation") or None,
            preuve=preuve,
            commentaires=(request.POST.get("commentaires") or "").strip(),
        )
        messages.success(request, "Action ajoutée.")
    return redirect("evenements:evenement_detail", pk=pk)


@login_required
def action_edit(request, action_id):
    org = _get_org(request)
    action = get_object_or_404(ActionCAPA, pk=action_id, evenement__organisation=org)

    if request.method == "POST":
        action.numero = int(request.POST.get("numero") or action.numero)
        action.type_action = request.POST.get("type_action")
        action.description_action = request.POST.get("description_action") or ""
        action.cause_racine = (request.POST.get("cause_racine") or "").strip()
        action.responsable = (request.POST.get("responsable") or "").strip()
        action.service_societe = (request.POST.get("service_societe") or "").strip()
        action.delai = request.POST.get("delai") or None
        action.statut = request.POST.get("statut") or action.statut
        action.priorite = (request.POST.get("priorite") or "").strip()
        action.date_realisation = request.POST.get("date_realisation") or None
        if request.FILES.get("preuve"):
            action.preuve = request.FILES["preuve"]
        action.commentaires = (request.POST.get("commentaires") or "").strip()

        action.date_verification_efficacite = request.POST.get("date_verification_efficacite") or None
        eff = request.POST.get("efficace")
        action.efficace = True if eff == "1" else False if eff == "0" else None
        action.commentaires_efficacite = request.POST.get("commentaires_efficacite") or ""

        action.save()
        messages.success(request, "Action mise à jour.")
        return redirect("evenements:evenement_detail", pk=action.evenement_id)

    return render(request, "evenements/action_form.html", {"org": org, "action": action})


@login_required
def stats_list(request):
    org = _get_org(request)
    items = StatistiquesHSE.objects.filter(organisation=org).select_related("site")[:200]
    return render(request, "evenements/stats_list.html", {"org": org, "items": items})


@login_required
def stats_create(request):
    org = _get_org(request)
    sites = Site.objects.filter(organisation=org, actif=True).order_by("nom")

    if request.method == "POST":
        site_id = request.POST.get("site") or ""
        st = StatistiquesHSE.objects.create(
            organisation=org,
            site_id=int(site_id) if site_id.isdigit() else None,
            periode_label=(request.POST.get("periode_label") or "").strip(),
            responsable_qhs=(request.POST.get("responsable_qhs") or "").strip(),

            nb_accidents_total=int(request.POST.get("nb_accidents_total") or 0),
            nb_accidents_avec_arret=int(request.POST.get("nb_accidents_avec_arret") or 0),
            nb_accidents_sans_arret=int(request.POST.get("nb_accidents_sans_arret") or 0),
            nb_jours_perdus=int(request.POST.get("nb_jours_perdus") or 0),
            tf=request.POST.get("tf") or 0,
            tg=request.POST.get("tg") or 0,

            repartition_par_site=request.POST.get("repartition_par_site") or "",
            repartition_par_service=request.POST.get("repartition_par_service") or "",
            repartition_par_prestataire=request.POST.get("repartition_par_prestataire") or "",
            repartition_par_activite=request.POST.get("repartition_par_activite") or "",
            repartition_par_gravite=request.POST.get("repartition_par_gravite") or "",

            nb_incidents=int(request.POST.get("nb_incidents") or 0),
            nb_presquaccidents=int(request.POST.get("nb_presquaccidents") or 0),
            taux_declaration=request.POST.get("taux_declaration") or 0,
            tendance_vs_periode_precedente=(request.POST.get("tendance_vs_periode_precedente") or "").strip(),

            nb_actions_ouvertes=int(request.POST.get("nb_actions_ouvertes") or 0),
            nb_actions_cloturees=int(request.POST.get("nb_actions_cloturees") or 0),
            nb_actions_en_retard=int(request.POST.get("nb_actions_en_retard") or 0),
            taux_cloture_actions=request.POST.get("taux_cloture_actions") or 0,

            accidents_formation_expiree=int(request.POST.get("accidents_formation_expiree") or 0),
            accidents_habilitation_manquante=int(request.POST.get("accidents_habilitation_manquante") or 0),
            accidents_permis_non_conforme=int(request.POST.get("accidents_permis_non_conforme") or 0),
            actions_formation_habilitation_declenchees=int(request.POST.get("actions_formation_habilitation_declenchees") or 0),

            analyse_commentaires=request.POST.get("analyse_commentaires") or "",

            etabli_par=(request.POST.get("etabli_par") or "").strip(),
            valide_par=(request.POST.get("valide_par") or "").strip(),
            diffusion_direction=_bool(request.POST.get("diffusion_direction")),
            diffusion_hse=_bool(request.POST.get("diffusion_hse")),
            diffusion_sites=_bool(request.POST.get("diffusion_sites")),
            diffusion_autres=(request.POST.get("diffusion_autres") or "").strip(),
        )
        messages.success(request, "Statistiques enregistrées.")
        return redirect("evenements:stats_detail", pk=st.pk)

    return render(request, "evenements/stats_form.html", {"org": org, "sites": sites, "mode": "create"})


@login_required
def stats_detail(request, pk):
    org = _get_org(request)
    st = get_object_or_404(StatistiquesHSE, pk=pk, organisation=org)
    return render(request, "evenements/stats_detail.html", {"org": org, "st": st})


@login_required
def stats_edit(request, pk):
    org = _get_org(request)
    st = get_object_or_404(StatistiquesHSE, pk=pk, organisation=org)
    sites = Site.objects.filter(organisation=org, actif=True).order_by("nom")

    if request.method == "POST":
        site_id = request.POST.get("site") or ""
        st.site_id = int(site_id) if site_id.isdigit() else None
        st.periode_label = (request.POST.get("periode_label") or "").strip()
        st.responsable_qhs = (request.POST.get("responsable_qhs") or "").strip()

        st.nb_accidents_total = int(request.POST.get("nb_accidents_total") or 0)
        st.nb_accidents_avec_arret = int(request.POST.get("nb_accidents_avec_arret") or 0)
        st.nb_accidents_sans_arret = int(request.POST.get("nb_accidents_sans_arret") or 0)
        st.nb_jours_perdus = int(request.POST.get("nb_jours_perdus") or 0)
        st.tf = request.POST.get("tf") or 0
        st.tg = request.POST.get("tg") or 0

        st.repartition_par_site = request.POST.get("repartition_par_site") or ""
        st.repartition_par_service = request.POST.get("repartition_par_service") or ""
        st.repartition_par_prestataire = request.POST.get("repartition_par_prestataire") or ""
        st.repartition_par_activite = request.POST.get("repartition_par_activite") or ""
        st.repartition_par_gravite = request.POST.get("repartition_par_gravite") or ""

        st.nb_incidents = int(request.POST.get("nb_incidents") or 0)
        st.nb_presquaccidents = int(request.POST.get("nb_presquaccidents") or 0)
        st.taux_declaration = request.POST.get("taux_declaration") or 0
        st.tendance_vs_periode_precedente = (request.POST.get("tendance_vs_periode_precedente") or "").strip()

        st.nb_actions_ouvertes = int(request.POST.get("nb_actions_ouvertes") or 0)
        st.nb_actions_cloturees = int(request.POST.get("nb_actions_cloturees") or 0)
        st.nb_actions_en_retard = int(request.POST.get("nb_actions_en_retard") or 0)
        st.taux_cloture_actions = request.POST.get("taux_cloture_actions") or 0

        st.accidents_formation_expiree = int(request.POST.get("accidents_formation_expiree") or 0)
        st.accidents_habilitation_manquante = int(request.POST.get("accidents_habilitation_manquante") or 0)
        st.accidents_permis_non_conforme = int(request.POST.get("accidents_permis_non_conforme") or 0)
        st.actions_formation_habilitation_declenchees = int(request.POST.get("actions_formation_habilitation_declenchees") or 0)

        st.analyse_commentaires = request.POST.get("analyse_commentaires") or ""

        st.etabli_par = (request.POST.get("etabli_par") or "").strip()
        st.valide_par = (request.POST.get("valide_par") or "").strip()
        st.diffusion_direction = _bool(request.POST.get("diffusion_direction"))
        st.diffusion_hse = _bool(request.POST.get("diffusion_hse"))
        st.diffusion_sites = _bool(request.POST.get("diffusion_sites"))
        st.diffusion_autres = (request.POST.get("diffusion_autres") or "").strip()

        st.save()
        messages.success(request, "Statistiques mises à jour.")
        return redirect("evenements:stats_detail", pk=st.pk)

    return render(request, "evenements/stats_form.html", {"org": org, "sites": sites, "mode": "edit", "st": st})


@login_required
def api_zones_by_site(request):
    org = _get_org(request)
    site_id = request.GET.get("site_id") or ""
    if not site_id.isdigit():
        return JsonResponse({"ok": True, "zones": []})

    site = get_object_or_404(Site, pk=int(site_id), organisation=org)
    zones = list(site.zones.filter(actif=True).order_by("nom").values("id", "nom"))
    return JsonResponse({"ok": True, "zones": zones})


from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Evenement, ActionCAPA, EnqueteAccident

# (tu as déjà _get_org, _bool, _int dans ton fichier views.py)
# je réutilise ces helpers


@login_required
def actions_suivi(request):
    org = _get_org(request)

    # Onglet type dossier
    active_tab = (request.GET.get("tab") or "ai").strip()

    # Filtres
    origine = (request.GET.get("origine") or "").strip()
    type_action = (request.GET.get("type_action") or "").strip()
    responsable = (request.GET.get("responsable") or "").strip()
    statut = (request.GET.get("statut") or "").strip()
    delai = (request.GET.get("delai") or "").strip()
    retard_only = (request.GET.get("retard") or "").strip() == "1"

    qs = ActionCAPA.objects.filter(evenement__organisation=org).select_related("evenement", "evenement__site")

    # Filtre onglet => basé sur Evenement.type_evenement
    # adapte si tu veux d’autres correspondances
    if active_tab == "ai":
        qs = qs.filter(evenement__type_evenement__in=["accident", "incident", "presquaccident"])
    elif active_tab == "audit":
        qs = qs.filter(evenement__type_evenement="audit")
    elif active_tab == "inspection":
        qs = qs.filter(evenement__type_evenement="inspection")
    elif active_tab == "autre":
        qs = qs.filter(evenement__type_evenement="autre")
    # "tb" => pas de filtre

    # Origine (affichage simple : référence dossier / type)
    # si tu veux l'origine comme une vraie colonne => on peut la calculer côté template avec event
    if origine:
        qs = qs.filter(
            Q(evenement__reference__icontains=origine) |
            Q(evenement__type_evenement__icontains=origine)
        )

    if type_action:
        qs = qs.filter(type_action=type_action)

    if responsable:
        qs = qs.filter(responsable=responsable)

    if statut:
        qs = qs.filter(statut=statut)

    if delai.isdigit():
        max_date = date.today() + timedelta(days=int(delai))
        qs = qs.filter(delai__isnull=False, delai__lte=max_date)

    if retard_only:
        qs = qs.filter(statut="retard")

    # listes dropdowns
    responsables = list(
        ActionCAPA.objects.filter(evenement__organisation=org)
        .exclude(responsable="")
        .values_list("responsable", flat=True)
        .distinct()
        .order_by("responsable")
    )
    origines = list(
        Evenement.objects.filter(organisation=org)
        .exclude(reference="")
        .values_list("reference", flat=True)
        .distinct()
        .order_by("reference")
    )

    # pagination légère (simple)
    page_size = int(request.GET.get("page_size") or 25)
    page = int(request.GET.get("page") or 1)
    if page < 1:
        page = 1

    total_actions = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    actions = qs.order_by("-id")[start:end]

    page_info = f"{start+1}-{min(end, total_actions)} sur {total_actions} lignes" if total_actions else "0 ligne"
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if end < total_actions else page

    ctx = {
        "org": org,
        "active_tab": active_tab,
        "actions": actions,
        "total_actions": total_actions,
        "page_info": page_info,
        "prev_page": prev_page,
        "next_page": next_page,
        "page_sizes": [10, 25, 50, 100],
        "page_size": page_size,
        "filters": {
            "origine": origine,
            "type_action": type_action,
            "responsable": responsable,
            "statut": statut,
            "delai": delai,
        },
        "responsables": responsables,
        "origines": origines,
    }
    return render(request, "evenements/actions_suivi.html", ctx)


@login_required
def suivi_cloture(request, pk):
    org = _get_org(request)
    ev = get_object_or_404(Evenement, pk=pk, organisation=org)

    actions = ev.actions.all().order_by("numero", "id")
    actions_count = actions.count()
    actions_done = actions.filter(statut="realisee").count()

    # Enquête (pour stocker efficacité / décision si tu choisis)
    enquete, _ = EnqueteAccident.objects.get_or_create(evenement=ev)

    # Valeurs UI (si tu n’as pas encore les champs, ça reste juste visuel)
    efficacite_date = getattr(enquete, "date_verification_efficacite", None)
    efficace_globale = getattr(enquete, "efficace_globale", None)
    commentaires_efficacite = getattr(enquete, "commentaires_efficacite", "") if hasattr(enquete, "commentaires_efficacite") else ""
    decision_cloture = getattr(enquete, "decision_cloture", "") if hasattr(enquete, "decision_cloture") else ""
    decision_finale = getattr(enquete, "decision_finale", False) if hasattr(enquete, "decision_finale") else False

    if request.method == "POST":
        act = request.POST.get("action") or ""

        if act == "toggle_cloture":
            # clôture simple du dossier : date_cloture
            if ev.date_cloture:
                ev.date_cloture = None
                messages.success(request, "Dossier réouvert.")
            else:
                ev.date_cloture = date.today()
                messages.success(request, "Dossier clôturé.")
            ev.save()
            return redirect("evenements:suivi_cloture", pk=ev.pk)

        if act == "save_efficacite":
            # si tu ajoutes les champs dans EnqueteAccident, ça se sauvegarde
            d = request.POST.get("date_verification_efficacite") or None
            eff = request.POST.get("efficace_globale")
            com = request.POST.get("commentaires_efficacite") or ""

            if hasattr(enquete, "date_verification_efficacite"):
                enquete.date_verification_efficacite = d
            if hasattr(enquete, "efficace_globale"):
                enquete.efficace_globale = True if eff == "1" else False if eff == "0" else None
            if hasattr(enquete, "commentaires_efficacite"):
                enquete.commentaires_efficacite = com
            enquete.save()

            messages.success(request, "Vérification d’efficacité enregistrée.")
            return redirect("evenements:suivi_cloture", pk=ev.pk)

        if act == "save_decision":
            dec = request.POST.get("decision_cloture") or ""
            if hasattr(enquete, "decision_cloture"):
                enquete.decision_cloture = dec
                enquete.save()
            messages.success(request, "Décision enregistrée.")
            return redirect("evenements:suivi_cloture", pk=ev.pk)

        if act == "save_signatures":
            ev.validation_qhs = (request.POST.get("validation_qhs") or "").strip()
            ev.validation_direction = (request.POST.get("validation_direction") or "").strip()
            ev.save()

            if hasattr(enquete, "decision_finale"):
                enquete.decision_finale = _bool(request.POST.get("decision_finale"))
                enquete.save()

            # si decision finale cochée => clôture dossier (option)
            if _bool(request.POST.get("decision_finale")) and not ev.date_cloture:
                ev.date_cloture = date.today()
                ev.save()

            messages.success(request, "Signatures enregistrées.")
            return redirect("evenements:suivi_cloture", pk=ev.pk)

    ctx = {
        "org": org,
        "ev": ev,
        "actions": actions,
        "actions_count": actions_count,
        "actions_done": actions_done,

        "efficacite_date": efficacite_date.isoformat() if efficacite_date else "",
        "efficace_globale": efficace_globale,
        "commentaires_efficacite": commentaires_efficacite,
        "decision_cloture": decision_cloture,
        "decision_finale": decision_finale,
    }
    return render(request, "evenements/suivi_cloture.html", ctx)


@login_required
def action_create_global(request):
    """
    Page (optionnelle) pour créer une action sans ouvrir un événement d’abord.
    Tu peux la relier à un select des événements.
    """
    org = _get_org(request)
    events = Evenement.objects.filter(organisation=org).order_by("-date_evenement")[:200]

    if request.method == "POST":
        ev_id = request.POST.get("evenement") or ""
        if not ev_id.isdigit():
            messages.error(request, "Choisis un dossier (événement).")
            return redirect("evenements:action_create_global")

        ev = get_object_or_404(Evenement, pk=int(ev_id), organisation=org)
        next_num = (ev.actions.count() or 0) + 1

        ActionCAPA.objects.create(
            evenement=ev,
            numero=int(request.POST.get("numero") or next_num),
            type_action=request.POST.get("type_action"),
            description_action=request.POST.get("description_action") or "",
            cause_racine=(request.POST.get("cause_racine") or "").strip(),
            responsable=(request.POST.get("responsable") or "").strip(),
            service_societe=(request.POST.get("service_societe") or "").strip(),
            delai=request.POST.get("delai") or None,
            statut=request.POST.get("statut") or "a_faire",
            priorite=(request.POST.get("priorite") or "").strip(),
            date_realisation=request.POST.get("date_realisation") or None,
            preuve=request.FILES.get("preuve"),
            commentaires=(request.POST.get("commentaires") or "").strip(),
        )
        messages.success(request, "Action créée.")
        return redirect("evenements:actions_suivi")

    return render(request, "evenements/action_create_global.html", {"org": org, "events": events})


@login_required
def stats_auto(request):
    org = _get_org(request)
    site_id = request.GET.get("site") or ""

    ev_qs = Evenement.objects.filter(organisation=org)
    if site_id.isdigit():
        ev_qs = ev_qs.filter(site_id=int(site_id))

    total = ev_qs.count()
    clotures = ev_qs.filter(date_cloture__isnull=False).count()
    ouverts = ev_qs.filter(date_cloture__isnull=True).count()

    accidents = ev_qs.filter(type_evenement="accident").count()
    incidents = ev_qs.filter(type_evenement="incident").count()
    presqu = ev_qs.filter(type_evenement="presquaccident").count()

    actions = ActionCAPA.objects.filter(evenement__organisation=org)
    if site_id.isdigit():
        actions = actions.filter(evenement__site_id=int(site_id))

    actions_ouvertes = actions.exclude(statut="realisee").count()
    actions_cloturees = actions.filter(statut="realisee").count()
    actions_retard = actions.filter(statut="retard").count()

    ctx = {
        "org": org,
        "sites": Site.objects.filter(organisation=org, actif=True).order_by("nom"),
        "site_id": site_id,

        "total": total,
        "clotures": clotures,
        "ouverts": ouverts,

        "accidents": accidents,
        "incidents": incidents,
        "presqu": presqu,

        "actions_ouvertes": actions_ouvertes,
        "actions_cloturees": actions_cloturees,
        "actions_retard": actions_retard,
    }
    return render(request, "evenements/stats_auto.html", ctx)
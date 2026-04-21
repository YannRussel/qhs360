from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from sites.models import Site, Zone
from .models import (
    Extincteur, VerificationExtincteur,
    RIA, VerificationRIA,
    ControleSystemeIncendie, ControleDM, ControleDetecteur,
    ExerciceEvacuation, ChronometrageEvacuation, ParticipationEvacuation, ControleExerciceEvacuation,
    RapportInterventionIncendie
)


def _user_org(request):
    return getattr(request.user, "organisation", None)


def _sites_org(request):
    org = _user_org(request)
    if request.user.is_superuser:
        return Site.objects.all()
    if not org:
        return Site.objects.none()
    return Site.objects.filter(organisation=org)


def _zones_site(site_id):
    return Zone.objects.filter(site_id=site_id, actif=True)


def _bool(post, name):
    return post.get(name) in ("on", "1", "true", "True", "yes")


@login_required
def dashboard(request):
    sites = _sites_org(request)

    context = {
        "kpi_extincteurs": Extincteur.objects.filter(site__in=sites).count(),
        "kpi_ria": RIA.objects.filter(site__in=sites).count(),
        "kpi_systemes": ControleSystemeIncendie.objects.filter(site__in=sites).count(),
        "kpi_exercices": ExerciceEvacuation.objects.filter(site__in=sites).count(),
        "kpi_rapports": RapportInterventionIncendie.objects.filter(site__in=sites).count(),
    }
    return render(request, "incendie/dashboard.html", context)


# =========================
# EXTINCTEURS
# =========================

@login_required
def extincteurs_list(request):
    sites = _sites_org(request)
    qs = Extincteur.objects.filter(site__in=sites).select_related("site", "zone").order_by("-actif", "site__nom", "numero")

    site_id = request.GET.get("site")
    if site_id:
        qs = qs.filter(site_id=site_id)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(numero__icontains=q) | qs.filter(emplacement__icontains=q)

    context = {"extincteurs": qs, "sites": sites, "site_id": site_id or "", "q": q}
    return render(request, "incendie/extincteurs_list.html", context)


@login_required
def extincteur_create(request):
    sites = _sites_org(request)

    if request.method == "POST":
        site_id = request.POST.get("site")
        zone_id = request.POST.get("zone") or None

        numero = (request.POST.get("numero") or "").strip()
        type_extincteur = (request.POST.get("type_extincteur") or "").strip()
        capacite = (request.POST.get("capacite") or "").strip()
        emplacement = (request.POST.get("emplacement") or "").strip()
        marque = (request.POST.get("marque") or "").strip()
        numero_serie = (request.POST.get("numero_serie") or "").strip()
        annee_fabrication = (request.POST.get("annee_fabrication") or "").strip()

        if not site_id or not numero or not emplacement:
            messages.error(request, "Site, numéro et emplacement sont obligatoires.")
            return redirect("incendie:extincteur_create")

        ext = Extincteur.objects.create(
            site_id=site_id,
            zone_id=zone_id,
            numero=numero,
            type_extincteur=type_extincteur,
            capacite=capacite,
            emplacement=emplacement,
            marque=marque,
            numero_serie=numero_serie,
            annee_fabrication=annee_fabrication,
        )
        messages.success(request, "Extincteur ajouté.")
        return redirect("incendie:extincteur_detail", pk=ext.pk)

    return render(request, "incendie/extincteur_create.html", {"sites": sites})


@login_required
def extincteur_detail(request, pk):
    sites = _sites_org(request)
    ext = get_object_or_404(Extincteur, pk=pk, site__in=sites)
    verifs = ext.verifications.all().order_by("-date_verification", "-cree_le")

    return render(request, "incendie/extincteur_detail.html", {"ext": ext, "verifs": verifs})


@login_required
def extincteur_verifier(request, pk):
    sites = _sites_org(request)
    ext = get_object_or_404(Extincteur, pk=pk, site__in=sites)

    if request.method != "POST":
        return redirect("incendie:extincteur_detail", pk=pk)

    date_str = request.POST.get("date_verification") or ""
    date_verif = date_str or timezone.now().date()

    # checklist alignée registre client (exemples)
    checklist = {
        "pression_ok": _bool(request.POST, "pression_ok"),
        "scelle_ok": _bool(request.POST, "scelle_ok"),
        "tuyau_ok": _bool(request.POST, "tuyau_ok"),
        "goupille_ok": _bool(request.POST, "goupille_ok"),
        "accessibilite_ok": _bool(request.POST, "accessibilite_ok"),
        "signalisation_ok": _bool(request.POST, "signalisation_ok"),
        "corps_ok": _bool(request.POST, "corps_ok"),
    }

    statut = request.POST.get("statut") or "conforme"
    observation = (request.POST.get("observation") or "").strip()

    VerificationExtincteur.objects.create(
        extincteur=ext,
        date_verification=date_verif,
        checklist=checklist,
        statut=statut,
        observation=observation,
        verifie_par=request.user,
    )

    messages.success(request, "Vérification enregistrée.")
    return redirect("incendie:extincteur_detail", pk=pk)


# =========================
# RIA
# =========================

@login_required
def ria_list(request):
    sites = _sites_org(request)
    qs = RIA.objects.filter(site__in=sites).select_related("site", "zone").order_by("-actif", "site__nom", "numero")

    site_id = request.GET.get("site")
    if site_id:
        qs = qs.filter(site_id=site_id)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(numero__icontains=q) | qs.filter(localisation__icontains=q)

    context = {"rias": qs, "sites": sites, "site_id": site_id or "", "q": q}
    return render(request, "incendie/ria_list.html", context)


@login_required
def ria_create(request):
    sites = _sites_org(request)

    if request.method == "POST":
        site_id = request.POST.get("site")
        zone_id = request.POST.get("zone") or None
        numero = (request.POST.get("numero") or "").strip()
        localisation = (request.POST.get("localisation") or "").strip()

        if not site_id or not numero or not localisation:
            messages.error(request, "Site, numéro et localisation sont obligatoires.")
            return redirect("incendie:ria_create")

        obj = RIA.objects.create(
            site_id=site_id,
            zone_id=zone_id,
            numero=numero,
            localisation=localisation,
            type_ria=(request.POST.get("type_ria") or "").strip(),
            diametre_tuyau=(request.POST.get("diametre_tuyau") or "").strip(),
            longueur_tuyau=(request.POST.get("longueur_tuyau") or "").strip(),
            pression_nominale=(request.POST.get("pression_nominale") or "").strip(),
            marque=(request.POST.get("marque") or "").strip(),
            annee_installation=(request.POST.get("annee_installation") or "").strip(),
        )
        messages.success(request, "RIA ajouté.")
        return redirect("incendie:ria_detail", pk=obj.pk)

    return render(request, "incendie/ria_create.html", {"sites": sites})


@login_required
def ria_detail(request, pk):
    sites = _sites_org(request)
    ria = get_object_or_404(RIA, pk=pk, site__in=sites)
    verifs = ria.verifications.all().order_by("-date_verification", "-cree_le")
    return render(request, "incendie/ria_detail.html", {"ria": ria, "verifs": verifs})


@login_required
def ria_verifier(request, pk):
    sites = _sites_org(request)
    ria = get_object_or_404(RIA, pk=pk, site__in=sites)

    if request.method != "POST":
        return redirect("incendie:ria_detail", pk=pk)

    date_verif = request.POST.get("date_verification") or timezone.now().date()

    # Checklist visuelle & fonctionnelle (exemples)
    checklist_visuelle = {
        "accessibilite_ok": _bool(request.POST, "v_accessibilite_ok"),
        "signalisation_ok": _bool(request.POST, "v_signalisation_ok"),
        "etat_coffret_ok": _bool(request.POST, "v_etat_coffret_ok"),
        "tuyau_ok": _bool(request.POST, "v_tuyau_ok"),
    }
    checklist_fonctionnelle = {
        "ouverture_vanne_ok": _bool(request.POST, "f_ouverture_vanne_ok"),
        "debit_ok": _bool(request.POST, "f_debit_ok"),
        "lance_ok": _bool(request.POST, "f_lance_ok"),
    }

    pression_mesuree = (request.POST.get("pression_mesuree") or "").strip()
    etancheite_ok = _bool(request.POST, "etancheite_ok")
    statut = request.POST.get("statut") or "conforme"
    commentaire = (request.POST.get("commentaire") or "").strip()

    VerificationRIA.objects.create(
        ria=ria,
        date_verification=date_verif,
        checklist_visuelle=checklist_visuelle,
        checklist_fonctionnelle=checklist_fonctionnelle,
        pression_mesuree=pression_mesuree,
        etancheite_ok=etancheite_ok,
        statut=statut,
        commentaire=commentaire,
        verifie_par=request.user,
    )

    messages.success(request, "Vérification RIA enregistrée.")
    return redirect("incendie:ria_detail", pk=pk)


# =========================
# SYSTEMES (alarme / desenfumage)
# =========================

@login_required
def systemes_list(request):
    sites = _sites_org(request)
    qs = ControleSystemeIncendie.objects.filter(site__in=sites).select_related("site", "zone").order_by("-date_controle", "-cree_le")

    site_id = request.GET.get("site")
    if site_id:
        qs = qs.filter(site_id=site_id)

    t = request.GET.get("type")
    if t:
        qs = qs.filter(type_systeme=t)

    return render(request, "incendie/systemes_list.html", {"controles": qs, "sites": sites, "site_id": site_id or "", "type": t or ""})


@login_required
def systeme_controle_create(request):
    sites = _sites_org(request)

    if request.method == "POST":
        site_id = request.POST.get("site")
        zone_id = request.POST.get("zone") or None
        type_systeme = request.POST.get("type_systeme") or "alarme_desenfumage"
        date_controle = request.POST.get("date_controle") or timezone.now().date()

        # checklists (exemples)
        checklist_alarme = {
            "sirenes_ok": _bool(request.POST, "a_sirenes_ok"),
            "dm_accessibles_ok": _bool(request.POST, "a_dm_accessibles_ok"),
            "voyants_ok": _bool(request.POST, "a_voyants_ok"),
            "detection_auto_ok": _bool(request.POST, "a_detection_auto_ok"),
            "tableau_ok": _bool(request.POST, "a_tableau_ok"),
            "aucun_defaut": _bool(request.POST, "a_aucun_defaut"),
        }
        checklist_desenfumage = {
            "ouvrants_ok": _bool(request.POST, "d_ouvrants_ok"),
            "commandes_ok": _bool(request.POST, "d_commandes_ok"),
            "alimentation_ok": _bool(request.POST, "d_alimentation_ok"),
            "test_ok": _bool(request.POST, "d_test_ok"),
        }

        statut = request.POST.get("statut") or "conforme"
        observation = (request.POST.get("observation") or "").strip()

        obj = ControleSystemeIncendie.objects.create(
            site_id=site_id,
            zone_id=zone_id,
            type_systeme=type_systeme,
            date_controle=date_controle,
            presence_responsable_securite=_bool(request.POST, "presence_responsable_securite"),
            controle_par=request.user,
            checklist_alarme=checklist_alarme,
            checklist_desenfumage=checklist_desenfumage,
            observation=observation,
            statut=statut,
        )

        messages.success(request, "Contrôle système enregistré.")
        return redirect("incendie:systeme_controle_detail", pk=obj.pk)

    return render(request, "incendie/systeme_controle_create.html", {"sites": sites})


@login_required
def systeme_controle_detail(request, pk):
    sites = _sites_org(request)
    controle = get_object_or_404(ControleSystemeIncendie, pk=pk, site__in=sites)
    return render(request, "incendie/systeme_controle_detail.html", {"controle": controle})


@login_required
def systeme_dm_add(request, pk):
    sites = _sites_org(request)
    controle = get_object_or_404(ControleSystemeIncendie, pk=pk, site__in=sites)

    if request.method == "POST":
        identifiant = (request.POST.get("identifiant") or "").strip()
        if identifiant:
            ControleDM.objects.create(
                controle=controle,
                identifiant=identifiant,
                localisation=(request.POST.get("localisation") or "").strip(),
                acces_ok=_bool(request.POST, "acces_ok"),
                etat_ok=_bool(request.POST, "etat_ok"),
                test_ok=_bool(request.POST, "test_ok"),
                remarque=(request.POST.get("remarque") or "").strip(),
            )
            messages.success(request, "DM ajouté.")
    return redirect("incendie:systeme_controle_detail", pk=pk)


@login_required
def systeme_detecteur_add(request, pk):
    sites = _sites_org(request)
    controle = get_object_or_404(ControleSystemeIncendie, pk=pk, site__in=sites)

    if request.method == "POST":
        identifiant = (request.POST.get("identifiant") or "").strip()
        if identifiant:
            ControleDetecteur.objects.create(
                controle=controle,
                identifiant=identifiant,
                type_detecteur=(request.POST.get("type_detecteur") or "").strip(),
                localisation=(request.POST.get("localisation") or "").strip(),
                proprete_ok=_bool(request.POST, "proprete_ok"),
                test_ok=_bool(request.POST, "test_ok"),
                remarque=(request.POST.get("remarque") or "").strip(),
            )
            messages.success(request, "Détecteur ajouté.")
    return redirect("incendie:systeme_controle_detail", pk=pk)


# =========================
# EXERCICES
# =========================

@login_required
def exercices_list(request):
    sites = _sites_org(request)
    qs = ExerciceEvacuation.objects.filter(site__in=sites).select_related("site", "zone").order_by("-date_exercice", "-cree_le")
    return render(request, "incendie/exercices_list.html", {"exercices": qs, "sites": sites})


@login_required
def exercice_create(request):
    sites = _sites_org(request)

    if request.method == "POST":
        site_id = request.POST.get("site")
        if not site_id:
            messages.error(request, "Choisis un site.")
            return redirect("incendie:exercice_create")

        obj = ExerciceEvacuation.objects.create(
            site_id=site_id,
            zone_id=request.POST.get("zone") or None,
            type_exercice=request.POST.get("type_exercice") or "planifie",
            date_exercice=request.POST.get("date_exercice") or timezone.now().date(),
            heure_debut=request.POST.get("heure_debut") or None,
            heure_fin=request.POST.get("heure_fin") or None,
            objectifs=(request.POST.get("objectifs") or "").strip(),
            scenario=(request.POST.get("scenario") or "").strip(),
            deroulement=(request.POST.get("deroulement") or "").strip(),
            organise_par=request.user,
        )
        messages.success(request, "Exercice créé.")
        return redirect("incendie:exercice_detail", pk=obj.pk)

    return render(request, "incendie/exercice_create.html", {"sites": sites})


@login_required
def exercice_detail(request, pk):
    sites = _sites_org(request)
    ex = get_object_or_404(ExerciceEvacuation, pk=pk, site__in=sites)

    # contrôle (one-to-one) si absent, on le prépare
    ctrl = getattr(ex, "controle", None)
    if ctrl is None:
        ctrl = ControleExerciceEvacuation.objects.create(exercice=ex, controle_par=request.user)

    return render(request, "incendie/exercice_detail.html", {"ex": ex, "ctrl": ctrl})


@login_required
def exercice_chrono_add(request, pk):
    sites = _sites_org(request)
    ex = get_object_or_404(ExerciceEvacuation, pk=pk, site__in=sites)

    if request.method == "POST":
        ChronometrageEvacuation.objects.create(
            exercice=ex,
            libelle_zone=(request.POST.get("libelle_zone") or "").strip(),
            heure_debut_zone=request.POST.get("heure_debut_zone") or None,
            heure_arrivee_point=request.POST.get("heure_arrivee_point") or None,
            temps_minutes=int(request.POST.get("temps_minutes") or 0) or None,
            remarque=(request.POST.get("remarque") or "").strip(),
        )
        messages.success(request, "Chronométrage ajouté.")
    return redirect("incendie:exercice_detail", pk=pk)


@login_required
def exercice_participation_add(request, pk):
    sites = _sites_org(request)
    ex = get_object_or_404(ExerciceEvacuation, pk=pk, site__in=sites)

    if request.method == "POST":
        ParticipationEvacuation.objects.create(
            exercice=ex,
            service=(request.POST.get("service") or "").strip(),
            effectif_theorique=int(request.POST.get("effectif_theorique") or 0),
            presents=int(request.POST.get("presents") or 0),
            absents=int(request.POST.get("absents") or 0),
            remarque=(request.POST.get("remarque") or "").strip(),
        )
        messages.success(request, "Participation ajoutée.")
    return redirect("incendie:exercice_detail", pk=pk)


@login_required
def exercice_controle_save(request, pk):
    sites = _sites_org(request)
    ex = get_object_or_404(ExerciceEvacuation, pk=pk, site__in=sites)
    ctrl = getattr(ex, "controle", None) or ControleExerciceEvacuation.objects.create(exercice=ex, controle_par=request.user)

    if request.method != "POST":
        return redirect("incendie:exercice_detail", pk=pk)

    # ⚠️ Exemples de cases (tu peux en ajouter autant que tu veux côté template)
    ctrl.checklist_declenchement = {
        "alarme_declenchee": _bool(request.POST, "c_alarme_declenchee"),
        "message_clair": _bool(request.POST, "c_message_clair"),
        "pas_de_confusion": _bool(request.POST, "c_pas_de_confusion"),
        "reaction_immediate": _bool(request.POST, "c_reaction_immediate"),
    }
    ctrl.checklist_comportement = {
        "respect_consigne": _bool(request.POST, "b_respect_consigne"),
        "pas_de_panique": _bool(request.POST, "b_pas_de_panique"),
        "evacuation_ordre": _bool(request.POST, "b_evacuation_ordre"),
    }
    ctrl.checklist_guides = {
        "guides_present": _bool(request.POST, "g_guides_present"),
        "serre_files_present": _bool(request.POST, "g_serre_files_present"),
    }
    ctrl.checklist_issues = {
        "issues_accessibles": _bool(request.POST, "i_issues_accessibles"),
        "portes_ok": _bool(request.POST, "i_portes_ok"),
    }
    ctrl.checklist_rassemblement = {
        "point_rassemblement_ok": _bool(request.POST, "r_point_ok"),
        "comptage_ok": _bool(request.POST, "r_comptage_ok"),
    }

    ctrl.temps_total_minutes = int(request.POST.get("temps_total_minutes") or 0) or None
    ctrl.observation = (request.POST.get("observation") or "").strip()
    ctrl.statut = request.POST.get("statut") or "conforme"
    ctrl.controle_par = request.user
    ctrl.save()

    messages.success(request, "Contrôle d'exercice enregistré.")
    return redirect("incendie:exercice_detail", pk=pk)


# =========================
# RAPPORTS
# =========================

@login_required
def rapports_list(request):
    sites = _sites_org(request)
    qs = RapportInterventionIncendie.objects.filter(site__in=sites).select_related("site", "zone").order_by("-date", "-cree_le")
    return render(request, "incendie/rapports_list.html", {"rapports": qs, "sites": sites})


@login_required
def rapport_create(request):
    sites = _sites_org(request)

    if request.method == "POST":
        site_id = request.POST.get("site")
        if not site_id:
            messages.error(request, "Choisis un site.")
            return redirect("incendie:rapport_create")

        obj = RapportInterventionIncendie.objects.create(
            site_id=site_id,
            zone_id=request.POST.get("zone") or None,
            type_intervention=request.POST.get("type_intervention") or "incident",
            date=request.POST.get("date") or timezone.now().date(),
            heure=request.POST.get("heure") or None,
            titre=(request.POST.get("titre") or "").strip(),
            description=(request.POST.get("description") or "").strip(),
            actions_menees=(request.POST.get("actions_menees") or "").strip(),
            conclusion=(request.POST.get("conclusion") or "").strip(),
            redige_par=request.user,
            pieces_jointes=request.FILES.get("pieces_jointes"),
        )
        messages.success(request, "Rapport enregistré.")
        return redirect("incendie:rapports_list")

    return render(request, "incendie/rapport_create.html", {"sites": sites})

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sites.models import Zone

@require_GET
def zones_by_site(request):
    """
    Retourne les zones actives d'un site sous forme JSON.
    GET /incendie/zones/?site=<id>
    """
    site_id = request.GET.get("site")
    if not site_id:
        return JsonResponse({"zones": []})

    zones = Zone.objects.filter(site_id=site_id, actif=True).order_by("nom").values("id", "nom")
    return JsonResponse({"zones": list(zones)})

from datetime import datetime
from django.db.models import Q

@login_required
def registre_controles(request):
    sites = _sites_org(request)

    site_id = request.GET.get("site") or ""
    zone_id = request.GET.get("zone") or ""
    date_debut = request.GET.get("date_debut") or ""
    date_fin = request.GET.get("date_fin") or ""

    # helpers dates (tolérant)
    def _parse(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None

    d1 = _parse(date_debut)
    d2 = _parse(date_fin)

    # ---------- Querysets base ----------
    verif_ext = VerificationExtincteur.objects.filter(extincteur__site__in=sites).select_related(
        "extincteur", "extincteur__site", "extincteur__zone", "verifie_par"
    )
    verif_ria = VerificationRIA.objects.filter(ria__site__in=sites).select_related(
        "ria", "ria__site", "ria__zone", "verifie_par"
    )
    controles_sys = ControleSystemeIncendie.objects.filter(site__in=sites).select_related(
        "site", "zone", "controle_par"
    )
    controles_ex = ControleExerciceEvacuation.objects.filter(exercice__site__in=sites).select_related(
        "exercice", "exercice__site", "exercice__zone", "controle_par"
    )

    # ---------- Filtres ----------
    if site_id:
        verif_ext = verif_ext.filter(extincteur__site_id=site_id)
        verif_ria = verif_ria.filter(ria__site_id=site_id)
        controles_sys = controles_sys.filter(site_id=site_id)
        controles_ex = controles_ex.filter(exercice__site_id=site_id)

    if zone_id:
        verif_ext = verif_ext.filter(extincteur__zone_id=zone_id)
        verif_ria = verif_ria.filter(ria__zone_id=zone_id)
        controles_sys = controles_sys.filter(zone_id=zone_id)
        controles_ex = controles_ex.filter(exercice__zone_id=zone_id)

    if d1:
        verif_ext = verif_ext.filter(date_verification__gte=d1)
        verif_ria = verif_ria.filter(date_verification__gte=d1)
        controles_sys = controles_sys.filter(date_controle__gte=d1)
        controles_ex = controles_ex.filter(exercice__date_exercice__gte=d1)

    if d2:
        verif_ext = verif_ext.filter(date_verification__lte=d2)
        verif_ria = verif_ria.filter(date_verification__lte=d2)
        controles_sys = controles_sys.filter(date_controle__lte=d2)
        controles_ex = controles_ex.filter(exercice__date_exercice__lte=d2)

    # ---------- KPI ----------
    total = (
        verif_ext.count()
        + verif_ria.count()
        + controles_sys.count()
        + controles_ex.count()
    )
    conformes = (
        verif_ext.filter(statut="conforme").count()
        + verif_ria.filter(statut="conforme").count()
        + controles_sys.filter(statut="conforme").count()
        + controles_ex.filter(statut="conforme").count()
    )
    pct_conformite = int(round((conformes / total) * 100)) if total else 0

    kpi_ria_nc = verif_ria.filter(statut="nc").count()
    kpi_ext_nc = verif_ext.filter(statut="nc").count()
    kpi_alarm_nc = controles_sys.filter(statut="nc").count()

    # ---------- Table unifiée ----------
    rows = []

    for v in verif_ext.order_by("-date_verification", "-cree_le")[:250]:
        rows.append({
            "numero": f"EXT-{v.extincteur.numero}",
            "type": "Extincteur",
            "equipement": v.extincteur.numero,
            "site": v.extincteur.site.nom,
            "zone": (v.extincteur.zone.nom if v.extincteur.zone else "—"),
            "date": v.date_verification,
            "controleur": (getattr(v.verifie_par, "get_full_name", lambda: str(v.verifie_par))() if v.verifie_par else "—"),
            "resultat": ("Conforme" if v.statut == "conforme" else ("Non conforme" if v.statut == "nc" else "NA")),
            "statut": v.statut,
            "url": None,  # optionnel: tu peux pointer vers le détail extincteur
        })

    for v in verif_ria.order_by("-date_verification", "-cree_le")[:250]:
        rows.append({
            "numero": f"RIA-{v.ria.numero}",
            "type": "RIA",
            "equipement": v.ria.numero,
            "site": v.ria.site.nom,
            "zone": (v.ria.zone.nom if v.ria.zone else "—"),
            "date": v.date_verification,
            "controleur": (getattr(v.verifie_par, "get_full_name", lambda: str(v.verifie_par))() if v.verifie_par else "—"),
            "resultat": ("Conforme" if v.statut == "conforme" else ("Non conforme" if v.statut == "nc" else "NA")),
            "statut": v.statut,
            "url": None,
        })

    for c in controles_sys.order_by("-date_controle", "-cree_le")[:250]:
        rows.append({
            "numero": f"SYS-{c.id}",
            "type": "Système",
            "equipement": c.get_type_systeme_display(),
            "site": c.site.nom,
            "zone": (c.zone.nom if c.zone else "—"),
            "date": c.date_controle,
            "controleur": (getattr(c.controle_par, "get_full_name", lambda: str(c.controle_par))() if c.controle_par else "—"),
            "resultat": ("Conforme" if c.statut == "conforme" else ("Non conforme" if c.statut == "nc" else "NA")),
            "statut": c.statut,
            "url": None,
        })

    for c in controles_ex.order_by("-exercice__date_exercice", "-cree_le")[:250]:
        rows.append({
            "numero": f"EX-{c.exercice.id}",
            "type": "Exercice",
            "equipement": c.exercice.get_type_exercice_display(),
            "site": c.exercice.site.nom,
            "zone": (c.exercice.zone.nom if c.exercice.zone else "—"),
            "date": c.exercice.date_exercice,
            "controleur": (getattr(c.controle_par, "get_full_name", lambda: str(c.controle_par))() if c.controle_par else "—"),
            "resultat": ("Conforme" if c.statut == "conforme" else ("Non conforme" if c.statut == "nc" else "NA")),
            "statut": c.statut,
            "url": None,
        })

    # tri global par date desc
    rows.sort(key=lambda r: (r["date"] or timezone.now().date()), reverse=True)
    rows = rows[:400]

    zones = Zone.objects.filter(site__in=sites, actif=True).order_by("site__nom", "nom")

    ctx = {
        "sites": sites,
        "zones": zones,
        "site_id": site_id,
        "zone_id": zone_id,
        "date_debut": date_debut,
        "date_fin": date_fin,

        "pct_conformite": pct_conformite,
        "kpi_ria_nc": kpi_ria_nc,
        "kpi_ext_nc": kpi_ext_nc,
        "kpi_alarm_nc": kpi_alarm_nc,

        "rows": rows,
        "total": total,
        "conformes": conformes,
    }
    return render(request, "incendie/registre_controles.html", ctx)
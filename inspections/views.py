from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Inspection,
    InspectionTemplate,
    InspectionQuestion,
    InspectionResponse,
    NonConformity,
    CorrectiveAction,
)


def _user_org(request):
    return getattr(request.user, "organisation", None)


def _parse_dt_local(value: str):
    # "2026-02-18T12:30" -> aware datetime
    if not value:
        return None
    try:
        return timezone.make_aware(timezone.datetime.fromisoformat(value))
    except Exception:
        return None


@login_required
def dashboard(request):
    org = _user_org(request)
    if not org:
        return render(request, "inspections/dashboard.html", {"no_org": True})

    now = timezone.now()
    last_30 = now - timedelta(days=30)

    qs = Inspection.objects.filter(organisation=org)

    kpi = {
        "total": qs.count(),
        "open": qs.filter(status="open").count(),
        "closed": qs.filter(status="closed").count(),
        "last30": qs.filter(date__gte=last_30).count(),
        "open_nc": NonConformity.objects.filter(inspection__organisation=org, resolved=False).count(),
    }

    # ✅ Templates de l'orga + nb d'utilisations (inspections)
    top_templates = (
        InspectionTemplate.objects.filter(organisation=org)
        .annotate(nb=Count("inspections"))
        .order_by("-nb", "-created_at")[:12]
    )

    return render(request, "inspections/dashboard.html", {
        "kpi": kpi,
        "top_templates": top_templates,
    })


@login_required
def inspections_by_template(request, pk):
    """
    Liste toutes les inspections utilisant un template donné
    """
    org = _user_org(request)
    if not org:
        return render(request, "inspections/inspections_by_template.html", {"no_org": True})

    template = get_object_or_404(InspectionTemplate, pk=pk, organisation=org)

    inspections = (
        Inspection.objects.filter(organisation=org, template=template)
        .select_related("site", "zone", "prestataire", "template")
        .order_by("-date")
    )

    return render(request, "inspections/inspections_by_template.html", {
        "template": template,
        "inspections": inspections,
    })


@login_required
def inspection_list(request):
    org = _user_org(request)
    if not org:
        return render(request, "inspections/inspection_list.html", {"no_org": True})

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = (
        Inspection.objects.filter(organisation=org)
        .select_related("site", "zone", "prestataire", "template")
        .order_by("-date")
    )

    if q:
        qs = qs.filter(
            Q(reference__icontains=q) |
            Q(site__nom__icontains=q) |
            Q(prestataire__nom__icontains=q) |
            Q(template__nom__icontains=q) |
            Q(type_libre__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    return render(request, "inspections/inspection_list.html", {
        "inspections": qs[:250],
        "q": q,
        "status": status,
    })


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

# Assure-toi que ces imports correspondent à TON projet
from .models import Inspection, InspectionTemplate
from sites.models import Site, Zone, AffectationPrestataire
from prestataire.models import Prestataire

# Si tu as déjà ces helpers, garde-les, sinon tu peux les adapter :
# - _user_org(request) -> renvoie l'organisation de l'utilisateur
# - _parse_dt_local(str) -> convertit "datetime-local" en datetime aware



@login_required
def inspection_create(request):
    org = _user_org(request)
    if not org:
        return render(request, "inspections/inspection_create.html", {"no_org": True})

    templates = InspectionTemplate.objects.filter(organisation=org, actif=True).order_by("nom")

    # Sites de l'organisation
    # (adapte selon ton modèle : ici on suppose Site a un champ organisation)
    sites = Site.objects.filter(organisation=org).order_by("nom")

    def load_zones(site_id=None):
        if site_id:
            return Zone.objects.filter(site_id=site_id).order_by("nom")
        return Zone.objects.filter(site__organisation=org).order_by("nom")

    def load_prestataires(site_id=None, zone_id=None):
        """
        Prestataires autorisés selon AffectationPrestataire:
        - site obligatoire pour filtrer correctement
        - si zone choisie: affectation "site entier" (zones vide) OU affectation incluant la zone
        """
        if not site_id:
            return Prestataire.objects.filter(organisation=org).order_by("nom")

        aff = AffectationPrestataire.objects.filter(site_id=site_id, actif=True)

        if zone_id:
            aff = aff.filter(Q(zones__isnull=True) | Q(zones__id=zone_id))

        prest_ids = aff.values_list("prestataire_id", flat=True).distinct()
        return Prestataire.objects.filter(id__in=prest_ids).order_by("nom")

    # GET: pour recharger la page après sélection site/zone
    selected_site = (request.GET.get("site") or "").strip() or None
    selected_zone = (request.GET.get("zone") or "").strip() or None

    zones = load_zones(selected_site)
    prestataires = load_prestataires(selected_site, selected_zone)

    # Données sticky (pré-remplissage)
    data = {
        "template": "",
        "type_libre": "",
        "status": "open",
        "site": selected_site or "",
        "zone": selected_zone or "",
        "prestataire": "",
        "date": "",
        "notes": "",
    }

    if request.method == "POST":
        data["template"] = request.POST.get("template") or ""
        data["type_libre"] = (request.POST.get("type_libre") or "").strip()
        data["status"] = request.POST.get("status") or "open"
        data["site"] = request.POST.get("site") or ""
        data["zone"] = request.POST.get("zone") or ""
        data["prestataire"] = request.POST.get("prestataire") or ""
        data["date"] = request.POST.get("date") or ""
        data["notes"] = (request.POST.get("notes") or "").strip()

        template_id = data["template"] or None
        type_libre = data["type_libre"] or None
        site_id = data["site"] or None
        zone_id = data["zone"] or None
        prestataire_id = data["prestataire"] or None

        # Recharger listes selon POST (au cas où il y a une erreur)
        zones = load_zones(site_id)
        prestataires = load_prestataires(site_id, zone_id)

        # Validations de base
        if not template_id and not type_libre:
            messages.error(request, "Choisis un template OU renseigne un type libre.")
            return render(request, "inspections/inspection_create.html", {
                "no_org": False,
                "templates": templates,
                "sites": sites,
                "zones": zones,
                "prestataires": prestataires,
                "data": data,
            })

        if not site_id:
            messages.error(request, "Le site est obligatoire.")
            return render(request, "inspections/inspection_create.html", {
                "no_org": False,
                "templates": templates,
                "sites": sites,
                "zones": zones,
                "prestataires": prestataires,
                "data": data,
            })

        # Date
        date = _parse_dt_local(data["date"])
        if not date:
            date = timezone.now()

        ins = Inspection(
            organisation=org,
            template_id=template_id,
            type_libre=type_libre,
            site_id=site_id,
            zone_id=zone_id or None,
            prestataire_id=prestataire_id or None,
            status=data["status"],
            notes=data["notes"] or None,
            date=date,
            inspector=request.user,
        )

        try:
            ins.full_clean()
            ins.save()
        except ValidationError as e:
            # Affiche les erreurs proprement
            for m in getattr(e, "messages", [str(e)]):
                messages.error(request, m)
            return render(request, "inspections/inspection_create.html", {
                "no_org": False,
                "templates": templates,
                "sites": sites,
                "zones": zones,
                "prestataires": prestataires,
                "data": data,
            })
        except Exception as e:
            messages.error(request, f"Erreur serveur: {e}")
            return render(request, "inspections/inspection_create.html", {
                "no_org": False,
                "templates": templates,
                "sites": sites,
                "zones": zones,
                "prestataires": prestataires,
                "data": data,
            })

        return redirect("inspections:inspection_fill", pk=ins.pk)

    return render(request, "inspections/inspection_create.html", {
        "no_org": False,
        "templates": templates,
        "sites": sites,
        "zones": zones,
        "prestataires": prestataires,
        "data": data,
    })

@login_required
def inspection_fill(request, pk):
    org = _user_org(request)
    ins = get_object_or_404(Inspection.objects.select_related("template"), pk=pk)

    if org and ins.organisation_id != org.id:
        return redirect("inspections:inspection_list")

    if not ins.template_id:
        if request.method == "POST":
            ins.notes = (request.POST.get("notes_generales") or "").strip() or None
            ins.save(update_fields=["notes"])
            messages.success(request, "Inspection enregistrée.")
            return redirect("inspections:inspection_detail", pk=ins.pk)

        return render(request, "inspections/inspection_fill.html", {
            "inspection": ins,
            "sections": [],
            "no_template": True,
        })

    sections = list(ins.template.sections.order_by("ordre").prefetch_related("questions"))
    questions = list(
        InspectionQuestion.objects.filter(section__template=ins.template)
        .select_related("section")
        .order_by("section__ordre", "ordre")
    )

    resp_map = {r.question_id: r for r in ins.responses.select_related("question").all()}

    if request.method == "POST":
        ins.notes = (request.POST.get("notes_generales") or "").strip() or None
        ins.save(update_fields=["notes"])

        for q in questions:
            key = f"q_{q.id}"
            rkey = f"r_{q.id}"
            pkey = f"p_{q.id}"

            resp = resp_map.get(q.id) or InspectionResponse(inspection=ins, question=q)

            resp.valeur_bool = None
            resp.valeur_num = None
            resp.valeur_texte = None

            if q.field_type == "checkbox":
                resp.valeur_bool = True if request.POST.get(key) == "on" else False
            elif q.field_type == "number":
                raw = (request.POST.get(key) or "").strip()
                resp.valeur_num = raw if raw != "" else None
            else:
                raw = (request.POST.get(key) or "").strip()
                resp.valeur_texte = raw if raw != "" else None

            resp.remarque = (request.POST.get(rkey) or "").strip() or None

            photo = request.FILES.get(pkey)
            if photo:
                resp.photo = photo

            if q.obligatoire and (not resp.has_answer()):
                messages.error(request, f"Champ obligatoire manquant : {q.label}")
                return redirect("inspections:inspection_fill", pk=ins.pk)

            resp.save()

        ins.calculate_score(save=True)
        messages.success(request, "Inspection enregistrée.")
        return redirect("inspections:inspection_detail", pk=ins.pk)

    return render(request, "inspections/inspection_fill.html", {
        "inspection": ins,
        "sections": sections,
        "questions": questions,
        "resp_map": resp_map,
        "no_template": False,
    })


@login_required
def inspection_detail(request, pk):
    org = _user_org(request)
    ins = get_object_or_404(
        Inspection.objects.select_related("site", "zone", "prestataire", "template"),
        pk=pk
    )

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    sections = []
    questions = []
    if ins.template_id:
        sections = list(ins.template.sections.order_by("ordre").prefetch_related("questions"))
        questions = list(
            InspectionQuestion.objects.filter(section__template=ins.template)
            .select_related("section")
            .order_by("section__ordre", "ordre")
        )

    resp_map = {r.question_id: r for r in ins.responses.select_related("question").all()}

    if request.method == "POST":
        ins.notes = (request.POST.get("notes_generales") or "").strip() or None

        status = (request.POST.get("status") or "").strip()
        if status in ("draft", "open", "closed", "cancelled"):
            ins.status = status

        ins.save(update_fields=["notes", "status"])

        if ins.template_id:
            for q in questions:
                key = f"q_{q.id}"
                rkey = f"r_{q.id}"
                pkey = f"p_{q.id}"

                resp = resp_map.get(q.id) or InspectionResponse(inspection=ins, question=q)

                resp.valeur_bool = None
                resp.valeur_num = None
                resp.valeur_texte = None

                if q.field_type == "checkbox":
                    resp.valeur_bool = True if request.POST.get(key) == "on" else False
                elif q.field_type == "number":
                    raw = (request.POST.get(key) or "").strip()
                    resp.valeur_num = raw if raw != "" else None
                else:
                    raw = (request.POST.get(key) or "").strip()
                    resp.valeur_texte = raw if raw != "" else None

                resp.remarque = (request.POST.get(rkey) or "").strip() or None

                photo = request.FILES.get(pkey)
                if photo:
                    resp.photo = photo

                if q.obligatoire and (not resp.has_answer()):
                    messages.error(request, f"Champ obligatoire manquant : {q.label}")
                    return redirect("inspections:inspection_detail", pk=ins.pk)

                resp.save()

        ins.calculate_score(save=True)
        messages.success(request, "Inspection enregistrée.")
        return redirect("inspections:inspection_detail", pk=ins.pk)

    ncs = ins.non_conformities.prefetch_related("actions").select_related("question").order_by("-reported_at")

    return render(request, "inspections/inspection_detail.html", {
        "inspection": ins,
        "sections": sections,
        "questions": questions,
        "resp_map": resp_map,
        "ncs": ncs,
    })


@login_required
def nc_create(request, pk):
    if request.method != "POST":
        return redirect("inspections:inspection_detail", pk=pk)

    org = _user_org(request)
    ins = get_object_or_404(Inspection, pk=pk)

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    question_id = request.POST.get("question_id") or None
    titre = (request.POST.get("titre") or "").strip()
    description = (request.POST.get("description") or "").strip() or None
    severity = request.POST.get("severity") or "medium"
    due_date = request.POST.get("due_date") or None
    assigned_to_id = request.POST.get("assigned_to_id") or None
    prestataire_id = request.POST.get("prestataire_id") or None

    if not titre:
        messages.error(request, "Le titre de la non-conformité est obligatoire.")
        return redirect("inspections:inspection_fill", pk=ins.pk)

    section_id = None
    if question_id:
        q_obj = InspectionQuestion.objects.select_related("section").filter(id=question_id).first()
        if q_obj:
            section_id = q_obj.section_id

    NonConformity.objects.create(
        inspection=ins,
        section_id=section_id,
        question_id=question_id,
        titre=titre,
        description=description,
        severity=severity,
        due_date=due_date or None,
        assigned_to_id=assigned_to_id or None,
        prestataire_responsible_id=prestataire_id or None,
        resolved=False,
    )

    messages.success(request, "Non-conformité déclarée.")
    return redirect("inspections:inspection_fill", pk=ins.pk)


@login_required
def nc_resolve(request, nc_id):
    if request.method != "POST":
        return redirect("inspections:inspection_list")

    org = _user_org(request)
    nc = get_object_or_404(NonConformity.objects.select_related("inspection"), pk=nc_id)
    ins = nc.inspection

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    notes = (request.POST.get("resolution_notes") or "").strip() or None
    nc.resolved = True
    nc.resolved_at = timezone.now()
    if notes:
        prefix = f"[{timezone.now().isoformat()}]"
        nc.resolution_notes = (nc.resolution_notes or "") + f"\n{prefix} {notes}"
    nc.save()

    messages.success(request, "Non-conformité clôturée.")
    return redirect("inspections:inspection_detail", pk=ins.pk)


@login_required
def action_add(request, nc_id):
    if request.method != "POST":
        return redirect("inspections:inspection_list")

    org = _user_org(request)
    nc = get_object_or_404(NonConformity.objects.select_related("inspection"), pk=nc_id)
    ins = nc.inspection

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    titre = (request.POST.get("titre") or "").strip()
    description = (request.POST.get("description") or "").strip() or None
    assigned_to_id = request.POST.get("assigned_to_id") or None
    date_target = request.POST.get("date_target") or None

    if not titre:
        messages.error(request, "Le titre de l'action est obligatoire.")
        return redirect("inspections:inspection_detail", pk=ins.pk)

    CorrectiveAction.objects.create(
        nc=nc,
        titre=titre,
        description=description,
        assigned_to_id=assigned_to_id or None,
        date_target=date_target or None,
        done=False,
    )

    messages.success(request, "Action corrective ajoutée.")
    return redirect("inspections:inspection_detail", pk=ins.pk)


@login_required
def action_toggle(request, action_id):
    if request.method != "POST":
        return redirect("inspections:inspection_list")

    org = _user_org(request)
    act = get_object_or_404(CorrectiveAction.objects.select_related("nc__inspection"), pk=action_id)
    ins = act.nc.inspection

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    act.done = not act.done
    act.done_at = timezone.now() if act.done else None
    act.save()

    if act.done and not act.nc.actions.filter(done=False).exists():
        act.nc.resolved = True
        act.nc.resolved_at = timezone.now()
        act.nc.resolution_notes = (act.nc.resolution_notes or "") + "\n[Auto] Toutes les actions correctives clôturées."
        act.nc.save()

    messages.success(request, "Action mise à jour.")
    return redirect("inspections:inspection_detail", pk=ins.pk)


from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg
from django.shortcuts import render
from django.utils import timezone

from .models import Inspection, InspectionTemplate, NonConformity, CorrectiveAction


def _user_org(request):
    return getattr(request.user, "organisation", None)


@login_required
def registre_inspections(request):
    org = _user_org(request)
    if not org:
        return render(request, "inspections/registre_inspections.html", {"no_org": True})

    # -----------------------------
    # GET Filters
    # -----------------------------
    f_type = (request.GET.get("type") or "").strip()       # "tpl:<id>" ou "free:<val>" ou ""
    f_site = (request.GET.get("site") or "").strip()
    f_zone = (request.GET.get("zone") or "").strip()
    f_insp = (request.GET.get("inspecteur") or "").strip()
    f_status = (request.GET.get("status") or "").strip()
    f_start = (request.GET.get("start") or "").strip()     # "YYYY-MM-DD"
    f_end = (request.GET.get("end") or "").strip()         # "YYYY-MM-DD"

    qs = (
        Inspection.objects
        .filter(organisation=org)
        .select_related("site", "zone", "prestataire", "template", "inspector")
    )

    # Type : template ou type_libre
    if f_type.startswith("tpl:"):
        try:
            tpl_id = int(f_type.split(":", 1)[1])
            qs = qs.filter(template_id=tpl_id)
        except ValueError:
            pass
    elif f_type.startswith("free:"):
        val = f_type.split(":", 1)[1]
        if val:
            qs = qs.filter(template__isnull=True, type_libre=val)

    if f_site:
        qs = qs.filter(site_id=f_site)

    if f_zone:
        qs = qs.filter(zone_id=f_zone)

    if f_insp:
        qs = qs.filter(inspector_id=f_insp)

    if f_status:
        qs = qs.filter(status=f_status)

    # Dates (filtre par date uniquement)
    if f_start:
        qs = qs.filter(date__date__gte=f_start)
    if f_end:
        qs = qs.filter(date__date__lte=f_end)

    # -----------------------------
    # Annotations pour le tableau
    # -----------------------------
    qs = qs.annotate(
        actions_count=Count("non_conformities__actions", distinct=True),
        open_nc_count=Count("non_conformities", filter=Q(non_conformities__resolved=False), distinct=True),
    ).order_by("-date")

    inspections = list(qs[:1500])  # limite sécurité

    # -----------------------------
    # KPI / Stats (sur le périmètre filtré)
    # -----------------------------
    total = qs.count()

    nc_total = NonConformity.objects.filter(inspection__in=qs).count()

    actions_open = CorrectiveAction.objects.filter(
        nc__inspection__in=qs,
        done=False
    ).count()

    today = timezone.localdate()
    overdue_actions = CorrectiveAction.objects.filter(
        nc__inspection__in=qs,
        done=False,
        date_target__isnull=False,
        date_target__lt=today
    )
    overdue = overdue_actions.values("nc__inspection_id").distinct().count()

    avg_score = qs.exclude(score__isnull=True).aggregate(a=Avg("score"))["a"] or 0
    compliance = int(round(avg_score))

    stats = {
        "total": total,
        "nc": nc_total,
        "actions_open": actions_open,
        "overdue": overdue,
        "compliance": compliance,
    }

    # -----------------------------
    # Données pour dropdown filtres
    # -----------------------------
    # Sites / zones : on tente via models sites
    filter_sites = []
    filter_zones = []
    try:
        from sites.models import Site, Zone
        filter_sites = Site.objects.filter(organisation=org).order_by("nom")
        filter_zones = Zone.objects.filter(site__organisation=org).order_by("nom")
    except Exception:
        filter_sites = []
        filter_zones = []

    # Inspecteurs : on prend ceux présents dans inspections (dictionnaires)
    filter_inspecteurs = (
        Inspection.objects.filter(organisation=org, inspector__isnull=False)
        .values(
            "inspector_id",
            "inspector__first_name",
            "inspector__last_name",
            "inspector__phone_number",
            "inspector__email",
        )
        .distinct()
        .order_by("inspector__first_name", "inspector__last_name")
    )

    # Types : templates + types libres
    tpl_opts = list(
        InspectionTemplate.objects.filter(organisation=org).order_by("nom")
        .values("id", "nom")
    )
    free_opts = list(
        Inspection.objects.filter(organisation=org, template__isnull=True)
        .exclude(type_libre__isnull=True).exclude(type_libre__exact="")
        .values_list("type_libre", flat=True)
        .distinct()
        .order_by("type_libre")
    )

    filter_types = []
    for t in tpl_opts:
        filter_types.append({"value": f"tpl:{t['id']}", "label": f"🧩 {t['nom']}"})
    for v in free_opts:
        filter_types.append({"value": f"free:{v}", "label": f"✍️ {v}"})

    filters = {
        "type": f_type,
        "site": f_site,
        "zone": f_zone,
        "inspecteur": f_insp,
        "status": f_status,
        "start": f_start,
        "end": f_end,
    }

    return render(request, "inspections/registre_inspections.html", {
        "inspections": inspections,
        "stats": stats,
        "filters": filters,
        "filter_sites": filter_sites,
        "filter_zones": filter_zones,
        "filter_inspecteurs": filter_inspecteurs,
        "filter_types": filter_types,
    })

from django.views.decorators.http import require_POST

@require_POST
@login_required
def inspection_close(request, pk):
    org = _user_org(request)
    ins = get_object_or_404(Inspection, pk=pk)

    if org and ins.organisation_id != org.id:
        messages.error(request, "Accès refusé.")
        return redirect("inspections:inspection_list")

    # Déjà close ? On évite de “re-clôturer”
    if ins.status == "closed":
        messages.info(request, "Inspection déjà clôturée.")
        return redirect("inspections:inspection_detail", pk=ins.pk)

    ins.status = "closed"
    ins.closed_at = timezone.now()
    ins.closed_by = request.user
    ins.save(update_fields=["status", "closed_at", "closed_by"])

    messages.success(request, "Inspection clôturée.")
    return redirect("inspections:inspection_detail", pk=ins.pk)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q

from .models import Formation, TypeHabilitation


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Count

from .models import Formation

def formation_habilitation(request) :
    return render(request, 'permis/formations_habilitations.html')

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .models import Formation, TypeHabilitation

from .models import (
    Intervention,
    TypePermis,
    PermisDelivre,
    QuestionPermis,
    ReponsePermis,
    AgentHabilitation,
)


def _get_org(request):
    return getattr(request.user, "organisation", None)


from django.core.paginator import Paginator
from django.utils import timezone

@login_required
def formation_dashboard(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    # =========================
    # KPIs Formations
    # =========================
    total_formations = Formation.objects.filter(organisation=org).count()
    actifs_formations = Formation.objects.filter(organisation=org, actif=True).count()
    inactifs_formations = Formation.objects.filter(organisation=org, actif=False).count()

    # =========================
    # ✅ Pagination (au lieu de [:8])
    # =========================
    per_page = int(request.GET.get("per_page") or 20)
    per_page = 20 if per_page not in (10, 20, 50, 100) else per_page

    qs_formations = (
        Formation.objects
        .filter(organisation=org)
        .order_by("-id")
    )

    paginator = Paginator(qs_formations, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ✅ la page courante
    last_formations = list(page_obj.object_list)

    # =========================
    # ✅ Habilitations obtenues après formation
    # =========================
    formation_ids = [f.id for f in last_formations]
    hab_map = {fid: [] for fid in formation_ids}

    if formation_ids:
        habs = (
            TypeHabilitation.objects
            .filter(
                organisation=org,
                actif=True,
                formations_requises__id__in=formation_ids
            )
            .distinct()
            .prefetch_related("formations_requises")
            .order_by("nom")
        )

        for h in habs:
            for f in h.formations_requises.all():
                if f.id in hab_map:
                    hab_map[f.id].append(h)

    for f in last_formations:
        f.habilitations_obtenues = hab_map.get(f.id, [])

    # =========================
    # Sessions / participants
    # =========================
    sessions_upcoming = []
    sessions_total = 0
    participants_total = 0

    try:
        from .models import SessionFormation, ParticipantSession

        sessions_total = SessionFormation.objects.filter(organisation=org).count()
        sessions_upcoming = (
            SessionFormation.objects
            .filter(organisation=org)
            .order_by("date_debut")[:8]
        )
        participants_total = ParticipantSession.objects.filter(
            session__organisation=org
        ).count()
    except Exception:
        sessions_total = 0
        participants_total = 0
        sessions_upcoming = []

    context = {
        "organisation": org,
        "titre": "Dashboard Formations",
        "kpi": {
            "formations_total": total_formations,
            "formations_actifs": actifs_formations,
            "formations_inactifs": inactifs_formations,
            "sessions_total": sessions_total,
            "participants_total": participants_total,
        },

        # ✅ pagination
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,

        # ✅ compat (si tu utilises encore last_formations ailleurs)
        "last_formations": last_formations,

        "sessions_upcoming": sessions_upcoming,
        "today": timezone.now().date(),
    }

    return render(request, "permis/formations/dashboard.html", context)


def _get_org(request):
    return getattr(request.user, "organisation", None)


# =========================
# FORMATIONS
# =========================
@login_required
def formation_liste(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    q = (request.GET.get("q") or "").strip()
    actif = (request.GET.get("actif") or "").strip()  # "", "1", "0"

    qs = Formation.objects.filter(organisation=org)

    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(description__icontains=q))

    if actif == "1":
        qs = qs.filter(actif=True)
    elif actif == "0":
        qs = qs.filter(actif=False)

    qs = qs.order_by("nom")

    kpi = {
        "total": Formation.objects.filter(organisation=org).count(),
        "actifs": Formation.objects.filter(organisation=org, actif=True).count(),
        "inactifs": Formation.objects.filter(organisation=org, actif=False).count(),
    }

    return render(request, "permis/formations/liste.html", {
        "organisation": org,
        "formations": qs,
        "q": q,
        "actif": actif if actif else None,
        "kpi": kpi,
        "titre": "Formations",
    })


@login_required
def formation_creer(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    data = {"nom": "", "description": "", "actif": True}

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["description"] = (request.POST.get("description") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")

        if not data["nom"]:
            messages.error(request, "Le nom de la formation est obligatoire.")
            return render(request, "permis/formations/form.html", {
                "titre": "Nouvelle formation",
                "organisation": org,
                "data": data,
            })

        if Formation.objects.filter(organisation=org, nom__iexact=data["nom"]).exists():
            messages.error(request, "Une formation avec ce nom existe déjà.")
            return render(request, "permis/formations/form.html", {
                "titre": "Nouvelle formation",
                "organisation": org,
                "data": data,
            })

        try:
            Formation.objects.create(
                organisation=org,
                nom=data["nom"],
                description=data["description"],
                actif=data["actif"],
            )
        except IntegrityError:
            messages.error(request, "Erreur : doublon détecté.")
            return render(request, "permis/formations/form.html", {
                "titre": "Nouvelle formation",
                "organisation": org,
                "data": data,
            })

        messages.success(request, "Formation créée.")
        return redirect("permis:formation_liste")

    return render(request, "permis/formations/form.html", {
        "titre": "Nouvelle formation",
        "organisation": org,
        "data": data,
    })


@login_required
def formation_modifier(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    obj = get_object_or_404(Formation, pk=pk, organisation=org)
    data = {"nom": obj.nom, "description": obj.description or "", "actif": obj.actif}

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["description"] = (request.POST.get("description") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")

        if not data["nom"]:
            messages.error(request, "Le nom de la formation est obligatoire.")
            return render(request, "permis/formations/form.html", {
                "titre": "Modifier formation",
                "organisation": org,
                "data": data,
                "formation": obj,
            })
        if Formation.objects.filter(organisation=org, nom__iexact=data["nom"]).exclude(pk=obj.pk).exists():
            messages.error(request, "Une autre formation avec ce nom existe déjà.")
            return render(request, "permis/formations/form.html", {
                "titre": "Modifier formation",
                "organisation": org,
                "data": data,
                "formation": obj,
            })

        obj.nom = data["nom"]
        obj.description = data["description"]
        obj.actif = data["actif"]
        obj.save()

        messages.success(request, "Formation mise à jour.")
        return redirect("permis:formation_liste")

    return render(request, "permis/formations/form.html", {
        "titre": "Modifier formation",
        "organisation": org,
        "data": data,
        "formation": obj,
    })


@login_required
def formation_supprimer(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    obj = get_object_or_404(Formation, pk=pk, organisation=org)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Formation supprimée.")
        return redirect("permis:formation_liste")

    return render(request, "permis/formations/supprimer.html", {
        "organisation": org,
        "objet": obj,
        "titre": "Supprimer formation",
    })


# =========================
# TYPES D’HABILITATIONS
# (c’est la formation qui donne droit)
# =========================
@login_required
def habilitation_type_liste(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    q = (request.GET.get("q") or "").strip()
    actif = (request.GET.get("actif") or "").strip()

    qs = TypeHabilitation.objects.filter(organisation=org).prefetch_related("formations_requises")

    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(description__icontains=q))

    if actif == "1":
        qs = qs.filter(actif=True)
    elif actif == "0":
        qs = qs.filter(actif=False)

    qs = qs.order_by("nom")

    kpi = {
        "total": TypeHabilitation.objects.filter(organisation=org).count(),
        "actifs": TypeHabilitation.objects.filter(organisation=org, actif=True).count(),
        "inactifs": TypeHabilitation.objects.filter(organisation=org, actif=False).count(),
    }

    return render(request, "permis/habilitations/liste.html", {
        "organisation": org,
        "types": qs,
        "q": q,
        "actif": actif if actif else None,
        "kpi": kpi,
        "titre": "Habilitations",
    })


@login_required
def habilitation_type_creer(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    formations = Formation.objects.filter(organisation=org, actif=True).order_by("nom")
    data = {"nom": "", "description": "", "actif": True, "formation_ids": []}

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["description"] = (request.POST.get("description") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")
        data["formation_ids"] = request.POST.getlist("formations_ids")

        if not data["nom"]:
            messages.error(request, "Le nom de l’habilitation est obligatoire.")
            return render(request, "permis/habilitations/form.html", {
                "titre": "Nouvelle habilitation",
                "organisation": org,
                "formations": formations,
                "data": data,
            })

        if TypeHabilitation.objects.filter(organisation=org, nom__iexact=data["nom"]).exists():
            messages.error(request, "Cette habilitation existe déjà.")
            return render(request, "permis/habilitations/form.html", {
                "titre": "Nouvelle habilitation",
                "organisation": org,
                "formations": formations,
                "data": data,
            })

        try:
            obj = TypeHabilitation.objects.create(
                organisation=org,
                nom=data["nom"],
                description=data["description"],
                actif=data["actif"],
            )
            # ✅ formations -> donne droit
            if data["formation_ids"]:
                valid = formations.filter(id__in=data["formation_ids"])
                obj.formations_requises.set(valid)
        except IntegrityError:
            messages.error(request, "Erreur : doublon détecté.")
            return render(request, "permis/habilitations/form.html", {
                "titre": "Nouvelle habilitation",
                "organisation": org,
                "formations": formations,
                "data": data,
            })

        messages.success(request, "Habilitation créée.")
        return redirect("permis:habilitation_liste")

    return render(request, "permis/habilitations/form.html", {
        "titre": "Nouvelle habilitation",
        "organisation": org,
        "formations": formations,
        "data": data,
    })


@login_required
def habilitation_type_modifier(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    obj = get_object_or_404(TypeHabilitation, pk=pk, organisation=org)
    formations = Formation.objects.filter(organisation=org, actif=True).order_by("nom")

    data = {
        "nom": obj.nom,
        "description": obj.description or "",
        "actif": obj.actif,
        "formation_ids": [str(x) for x in obj.formations_requises.values_list("id", flat=True)],
    }

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["description"] = (request.POST.get("description") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")
        data["formation_ids"] = request.POST.getlist("formations_ids")

        if not data["nom"]:
            messages.error(request, "Le nom de l’habilitation est obligatoire.")
            return render(request, "permis/habilitations/form.html", {
                "titre": "Modifier habilitation",
                "organisation": org,
                "formations": formations,
                "data": data,
                "obj": obj,
            })

        if TypeHabilitation.objects.filter(organisation=org, nom__iexact=data["nom"]).exclude(pk=obj.pk).exists():
            messages.error(request, "Une autre habilitation avec ce nom existe déjà.")
            return render(request, "permis/habilitations/form.html", {
                "titre": "Modifier habilitation",
                "organisation": org,
                "formations": formations,
                "data": data,
                "obj": obj,
            })

        obj.nom = data["nom"]
        obj.description = data["description"]
        obj.actif = data["actif"]
        obj.save()

        valid = formations.filter(id__in=data["formation_ids"]) if data["formation_ids"] else formations.none()
        obj.formations_requises.set(valid)

        messages.success(request, "Habilitation mise à jour.")
        return redirect("permis:habilitation_liste")

    return render(request, "permis/habilitations/form.html", {
        "titre": "Modifier habilitation",
        "organisation": org,
        "formations": formations,
        "data": data,
        "obj": obj,
    })


@login_required
def habilitation_type_supprimer(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    obj = get_object_or_404(TypeHabilitation, pk=pk, organisation=org)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Habilitation supprimée.")
        return redirect("permis:habilitation_liste")

    return render(request, "permis/habilitations/supprimer.html", {
        "organisation": org,
        "objet": obj,
        "titre": "Supprimer habilitation",
    })

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db import transaction
from django.utils.dateparse import parse_datetime

from .models import Formation, SessionFormation
from prestataire.models import AgentPrestataire


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _to_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


@login_required
def session_creer(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    # ✅ listes pour les selects
    formations = Formation.objects.filter(organisation=org).order_by("nom")

    # ✅ AgentPrestataire n'a pas organisation -> on passe par prestataire__organisation
    agents = AgentPrestataire.objects.filter(
        prestataire__organisation=org
    ).select_related("prestataire").order_by("nom", "prenom")

    defaults = {
        "formation_id": "",
        "titre": "",
        "date_debut": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "date_fin": "",
        "duree_minutes": "",
        "lieu": "",
        "statut": "planifiee",
        "notes": "",
        "intervenants_ids": [],
    }

    if request.method == "POST":
        formation_id = request.POST.get("formation_id", "").strip()
        titre = request.POST.get("titre", "").strip()
        date_debut_raw = request.POST.get("date_debut", "").strip()
        date_fin_raw = request.POST.get("date_fin", "").strip()
        duree_minutes_raw = request.POST.get("duree_minutes", "").strip()
        lieu = request.POST.get("lieu", "").strip()
        statut = request.POST.get("statut", "planifiee").strip()
        notes = request.POST.get("notes", "").strip()
        intervenants_ids = request.POST.getlist("intervenants_ids")

        defaults.update({
            "formation_id": formation_id,
            "titre": titre,
            "date_debut": date_debut_raw,
            "date_fin": date_fin_raw,
            "duree_minutes": duree_minutes_raw,
            "lieu": lieu,
            "statut": statut,
            "notes": notes,
            "intervenants_ids": intervenants_ids,
        })

        errors = []

        # validations
        if not formation_id:
            errors.append("Choisis une formation.")
        elif not formations.filter(id=formation_id).exists():
            errors.append("Formation invalide pour cette organisation.")

        if not date_debut_raw:
            errors.append("La date de début est obligatoire.")

        date_debut = parse_datetime(date_debut_raw)
        date_fin = parse_datetime(date_fin_raw) if date_fin_raw else None

        if date_debut_raw and date_debut is None:
            errors.append("Date début invalide.")
        if date_fin_raw and date_fin is None:
            errors.append("Date fin invalide.")

        duree_minutes = _to_int(duree_minutes_raw, default=0)
        if duree_minutes < 0:
            errors.append("La durée ne peut pas être négative.")

        # calc auto durée
        if date_debut and date_fin and date_fin > date_debut and duree_minutes == 0:
            duree_minutes = int((date_fin - date_debut).total_seconds() // 60)

        allowed_status = {c[0] for c in SessionFormation.STATUT_CHOICES}
        if statut not in allowed_status:
            statut = "planifiee"

        # ✅ intervenants validés (dans la même organisation via prestataire)
        valid_intervenants = list(
            agents.filter(id__in=intervenants_ids).values_list("id", flat=True)
        )

        if errors:
            for e in errors:
                messages.error(request, f"❌ {e}")
        else:
            with transaction.atomic():
                session = SessionFormation.objects.create(
                    organisation=org,
                    formation_id=int(formation_id),
                    titre=titre,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    duree_minutes=duree_minutes,
                    lieu=lieu,
                    statut=statut,
                    notes=notes,
                )
                session.intervenants.set(valid_intervenants)

            messages.success(request, "✅ Session créée avec succès.")
            return redirect("permis:formation_dashboard")

    return render(request, "permis/sessions/session_form.html", {
        "titre": "Créer une session de formation",
        "organisation": org,
        "formations": formations,
        "agents": agents,
        "values": defaults,
        "statuts": SessionFormation.STATUT_CHOICES,
    })


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.utils.dateparse import parse_datetime

from .models import Formation, SessionFormation, ParticipantSession
from prestataire.models import AgentPrestataire


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _to_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default

@login_required
def session_liste(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    q = (request.GET.get("q") or "").strip()
    statut = (request.GET.get("statut") or "").strip()

    qs = SessionFormation.objects.filter(organisation=org).select_related("formation").order_by("-date_debut")

    if statut:
        qs = qs.filter(statut=statut)

    if q:
        qs = qs.filter(
            formation__nom__icontains=q
        ) | qs.filter(
            titre__icontains=q
        ) | qs.filter(
            lieu__icontains=q
        )

    sessions = list(qs[:80])  # simple limite dashboard

    # enrich: nb participants + nb intervenants
    for s in sessions:
        s.nb_participants = s.participants.count()
        s.nb_intervenants = s.intervenants.count()

    return render(request, "permis/sessions/session_liste.html", {
        "titre": "Registre des sessions",
        "organisation": org,
        "sessions": sessions,
        "q": q,
        "statut": statut,
        "statuts": SessionFormation.STATUT_CHOICES,
    })


@login_required
def session_creer(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    formations = Formation.objects.filter(organisation=org).order_by("nom")
    agents = AgentPrestataire.objects.filter(
        prestataire__organisation=org
    ).select_related("prestataire").order_by("nom", "prenom")

    defaults = {
        "formation_id": "",
        "titre": "",
        "date_debut": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "date_fin": "",
        "duree_minutes": "",
        "lieu": "",
        "statut": "planifiee",
        "notes": "",
        "intervenants_ids": [],
    }

    if request.method == "POST":
        formation_id = request.POST.get("formation_id", "").strip()
        titre = request.POST.get("titre", "").strip()
        date_debut_raw = request.POST.get("date_debut", "").strip()
        date_fin_raw = request.POST.get("date_fin", "").strip()
        duree_minutes_raw = request.POST.get("duree_minutes", "").strip()
        lieu = request.POST.get("lieu", "").strip()
        statut = request.POST.get("statut", "planifiee").strip()
        notes = request.POST.get("notes", "").strip()
        intervenants_ids = request.POST.getlist("intervenants_ids")

        defaults.update({
            "formation_id": formation_id,
            "titre": titre,
            "date_debut": date_debut_raw,
            "date_fin": date_fin_raw,
            "duree_minutes": duree_minutes_raw,
            "lieu": lieu,
            "statut": statut,
            "notes": notes,
            "intervenants_ids": intervenants_ids,
        })

        errors = []

        if not formation_id:
            errors.append("Choisis une formation.")
        elif not formations.filter(id=formation_id).exists():
            errors.append("Formation invalide pour cette organisation.")

        if not date_debut_raw:
            errors.append("La date de début est obligatoire.")

        date_debut = parse_datetime(date_debut_raw)
        date_fin = parse_datetime(date_fin_raw) if date_fin_raw else None

        if date_debut_raw and date_debut is None:
            errors.append("Date début invalide.")
        if date_fin_raw and date_fin is None:
            errors.append("Date fin invalide.")

        duree_minutes = _to_int(duree_minutes_raw, default=0)
        if duree_minutes < 0:
            errors.append("La durée ne peut pas être négative.")

        if date_debut and date_fin and date_fin > date_debut and duree_minutes == 0:
            duree_minutes = int((date_fin - date_debut).total_seconds() // 60)

        allowed_status = {c[0] for c in SessionFormation.STATUT_CHOICES}
        if statut not in allowed_status:
            statut = "planifiee"

        valid_intervenants = list(
            agents.filter(id__in=intervenants_ids).values_list("id", flat=True)
        )

        if errors:
            for e in errors:
                messages.error(request, f"❌ {e}")
        else:
            with transaction.atomic():
                session = SessionFormation.objects.create(
                    organisation=org,
                    formation_id=int(formation_id),
                    titre=titre,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    duree_minutes=duree_minutes,
                    lieu=lieu,
                    statut=statut,
                    notes=notes,
                )
                session.intervenants.set(valid_intervenants)

            messages.success(request, "✅ Session créée. Ajoute maintenant les participants.")
            return redirect("permis:session_participants", pk=session.pk)

    return render(request, "permis/sessions/session_form.html", {
        "titre": "Créer une session de formation",
        "organisation": org,
        "formations": formations,
        "agents": agents,
        "values": defaults,
        "statuts": SessionFormation.STATUT_CHOICES,
    })


@login_required
def session_detail(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    session = get_object_or_404(
        SessionFormation.objects.select_related("formation"),
        pk=pk, organisation=org
    )

    participants = session.participants.select_related("agent").order_by("agent__nom", "agent__prenom")

    return render(request, "permis/sessions/session_detail.html", {
        "titre": "Détail session",
        "organisation": org,
        "session": session,
        "participants": participants,
    })


@login_required
def session_participants(request, pk):
    """
    Ajout/enlèvement + édition présence/validation/note.
    Sans DjangoForm, tout en POST direct.
    """
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    session = get_object_or_404(SessionFormation, pk=pk, organisation=org)

    agents = AgentPrestataire.objects.filter(
        prestataire__organisation=org
    ).select_related("prestataire").order_by("nom", "prenom")

    # participants existants
    existing = list(
        ParticipantSession.objects.filter(session=session).select_related("agent")
    )
    existing_by_agent = {p.agent_id: p for p in existing}

    if request.method == "POST":
        selected_ids = request.POST.getlist("participants_ids")  # qui sont participants
        selected_ids_int = [int(x) for x in selected_ids if str(x).isdigit()]

        # sécurité: garde seulement agents de l'org
        valid_ids = set(agents.filter(id__in=selected_ids_int).values_list("id", flat=True))

        with transaction.atomic():
            # 1) supprimer ceux non sélectionnés
            ParticipantSession.objects.filter(session=session).exclude(agent_id__in=valid_ids).delete()

            # 2) créer ceux nouveaux
            already = set(ParticipantSession.objects.filter(session=session, agent_id__in=valid_ids)
                          .values_list("agent_id", flat=True))
            to_create = list(valid_ids - already)

            ParticipantSession.objects.bulk_create(
                [ParticipantSession(session=session, agent_id=aid) for aid in to_create],
                ignore_conflicts=True
            )

            # 3) update presence/valide/note pour ceux sélectionnés
            for aid in valid_ids:
                present = request.POST.get(f"present_{aid}") == "on"
                valide = request.POST.get(f"valide_{aid}") == "on"
                note = (request.POST.get(f"note_{aid}") or "").strip()

                ParticipantSession.objects.filter(session=session, agent_id=aid).update(
                    present=present,
                    valide=valide,
                    note=note
                )

        messages.success(request, "✅ Participants mis à jour.")
        return redirect("permis:session_detail", pk=session.pk)

    # GET : pré-cocher participants existants
    current_ids = set(existing_by_agent.keys())

    return render(request, "permis/sessions/session_participants.html", {
        "titre": "Gérer les participants",
        "organisation": org,
        "session": session,
        "agents": agents,
        "current_ids": current_ids,
        "existing_by_agent": existing_by_agent,
    })


@login_required
def session_terminer(request, pk):
    """
    Boucler la session = terminee + générer habilitations via session.terminer()
    """
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    session = get_object_or_404(SessionFormation, pk=pk, organisation=org)

    if request.method != "POST":
        messages.error(request, "Action non autorisée.")
        return redirect("permis:session_detail", pk=session.pk)

    # ✅ sécurité : si déjà terminée, on ne refait pas
    if session.statut == "terminee":
        messages.info(request, "ℹ️ Cette session est déjà terminée.")
        return redirect("permis:session_detail", pk=session.pk)

    # termine + génère habilitations (selon tes modèles)
    session.terminer()

    messages.success(request, "✅ Session terminée. Habilitations générées pour les participants validés.")
    return redirect("permis:session_detail", pk=session.pk)

##################################" Dash habilitations"

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Count, Q

from .models import AgentHabilitation, TypeHabilitation


def _get_org(request):
    return getattr(request.user, "organisation", None)


@login_required
def habilitation_dashboard(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    today = timezone.now().date()

    # -------- filtres ----------
    q = (request.GET.get("q") or "").strip()
    hab_id = (request.GET.get("hab") or "").strip()
    statut = (request.GET.get("statut") or "").strip()  # valide / expire / bientot / inactive

    qs = AgentHabilitation.objects.select_related(
        "agent",
        "agent__prestataire",
        "type_habilitation",
    ).filter(
        type_habilitation__organisation=org,
        agent__prestataire__organisation=org,
    )

    if hab_id.isdigit():
        qs = qs.filter(type_habilitation_id=int(hab_id))

    if q:
        qs = qs.filter(
            Q(agent__nom__icontains=q) |
            Q(agent__prenom__icontains=q) |
            Q(agent__matricule__icontains=q) |
            Q(agent__prestataire__nom__icontains=q) |
            Q(type_habilitation__nom__icontains=q)
        )

    # statut côté DB
    if statut == "valide":
        qs = qs.filter(actif=True).filter(Q(date_expiration__isnull=True) | Q(date_expiration__gte=today))
    elif statut == "expire":
        qs = qs.filter(actif=True, date_expiration__lt=today)
    elif statut == "bientot":
        qs = qs.filter(
            actif=True,
            date_expiration__isnull=False,
            date_expiration__gte=today,
            date_expiration__lte=today + timezone.timedelta(days=30)
        )
    elif statut == "inactive":
        qs = qs.filter(actif=False)

    qs = qs.order_by("-date_obtention")[:300]
    items = list(qs)

    # -------- enrich template : days_left + badge (sans underscore) ----------
    for it in items:
        it.badge = "valide"
        it.days_left = None

        if not it.actif:
            it.badge = "inactive"
            it.days_left = None
            continue

        if it.date_expiration is None:
            it.badge = "illimitee"
            it.days_left = None
            continue

        delta = (it.date_expiration - today).days
        it.days_left = delta

        if delta < 0:
            it.badge = "expire"
        elif delta <= 30:
            it.badge = "bientot"
        else:
            it.badge = "valide"

    # -------- KPI ----------
    base_all = AgentHabilitation.objects.filter(
        type_habilitation__organisation=org,
        agent__prestataire__organisation=org
    )

    total = base_all.count()
    actifs = base_all.filter(actif=True).count()

    valides = base_all.filter(actif=True).filter(
        Q(date_expiration__isnull=True) | Q(date_expiration__gte=today)
    ).count()

    bientot = base_all.filter(
        actif=True,
        date_expiration__isnull=False,
        date_expiration__gte=today,
        date_expiration__lte=today + timezone.timedelta(days=30)
    ).count()

    expires = base_all.filter(actif=True, date_expiration__lt=today).count()
    agents_uniques = base_all.values("agent_id").distinct().count()

    # types pour dropdown
    types = TypeHabilitation.objects.filter(organisation=org).order_by("nom").annotate(nb=Count("agents"))

    return render(request, "permis/habilitations/dashboard.html", {
        "titre": "Registre des Habilitations",
        "organisation": org,
        "kpi": {
            "total": total,
            "actifs": actifs,
            "valides": valides,
            "bientot": bientot,
            "expires": expires,
            "agents": agents_uniques,
        },
        "items": items,
        "types": types,
        "filters": {"q": q, "hab": hab_id, "statut": statut},
        "today": today,
    })

###########################"" Les deux registres

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q, Count

from .models import Formation, TypeHabilitation, AgentHabilitation


def _get_org(request):
    return getattr(request.user, "organisation", None)


from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Formation, SessionFormation, ParticipantSession, TypeHabilitation


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _parse_date(s):
    # attend "YYYY-MM-DD"
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


@login_required
def registre_formations(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    today = timezone.now().date()

    # -----------------------------
    # Filtres (GET)
    # -----------------------------
    q = (request.GET.get("q") or "").strip()
    formation_id = (request.GET.get("formation") or "").strip()
    statut = (request.GET.get("statut") or "").strip()  # planifiee / encours / terminee / annulee
    agent = (request.GET.get("agent") or "").strip()
    start = _parse_date(request.GET.get("start") or "")
    end = _parse_date(request.GET.get("end") or "")

    # par défaut : 30 derniers jours -> 30 prochains jours (style registre)
    if not start and not end:
        start = today - timedelta(days=30)
        end = today + timedelta(days=30)

    # -----------------------------
    # Query principale : sessions
    # -----------------------------
    sessions_qs = SessionFormation.objects.select_related(
        "formation",
        "organisation",
    ).prefetch_related(
        "intervenants",
        "participants__agent",
        "participants__agent__prestataire",
    ).filter(
        organisation=org
    )

    if formation_id.isdigit():
        sessions_qs = sessions_qs.filter(formation_id=int(formation_id))

    if statut in {"planifiee", "encours", "terminee", "annulee"}:
        sessions_qs = sessions_qs.filter(statut=statut)

    if start:
        sessions_qs = sessions_qs.filter(date_debut__date__gte=start)
    if end:
        sessions_qs = sessions_qs.filter(date_debut__date__lte=end)

    if q:
        sessions_qs = sessions_qs.filter(
            Q(formation__nom__icontains=q) |
            Q(titre__icontains=q) |
            Q(lieu__icontains=q)
        )

    # filtre agent : soit participant, soit intervenant
    if agent:
        sessions_qs = sessions_qs.filter(
            Q(participants__agent__nom__icontains=agent) |
            Q(participants__agent__prenom__icontains=agent) |
            Q(participants__agent__matricule__icontains=agent) |
            Q(intervenants__nom__icontains=agent) |
            Q(intervenants__prenom__icontains=agent) |
            Q(intervenants__matricule__icontains=agent)
        ).distinct()

    sessions_qs = sessions_qs.annotate(
        nb_participants=Count("participants", distinct=True),
        nb_intervenants=Count("intervenants", distinct=True),
        nb_valides=Count("participants", filter=Q(participants__valide=True), distinct=True),
    ).order_by("-date_debut")

    # -----------------------------
    # Pagination (Pages 20 style)
    # -----------------------------
    per_page = int(request.GET.get("per_page") or 20)
    per_page = 20 if per_page not in (10, 20, 50, 100) else per_page

    paginator = Paginator(sessions_qs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    sessions = list(page_obj.object_list)

    # -----------------------------
    # Habilitations délivrées par formation
    # (pour afficher dans le tableau)
    # -----------------------------
    # map: formation_id -> [TypeHabilitation...]
    types = TypeHabilitation.objects.filter(organisation=org, actif=True).prefetch_related("formations_requises")
    hab_by_formation = {}
    for s in sessions:
        f = s.formation
        habs = [t for t in types if f in t.formations_requises.all()]
        hab_by_formation[f.id] = habs
        # attach direct pour simplifier template
        s.habilitations_delivrees = habs

    # -----------------------------
    # KPI / Widgets
    # -----------------------------
    base_sessions = SessionFormation.objects.filter(organisation=org)
    base_participants = ParticipantSession.objects.filter(session__organisation=org)

    kpi = {
        "formations_total": Formation.objects.filter(organisation=org).count(),
        "formations_actives": Formation.objects.filter(organisation=org, actif=True).count(),
        "sessions_total": base_sessions.count(),
        "sessions_prevues": base_sessions.filter(statut="planifiee").count(),
        "sessions_terminees": base_sessions.filter(statut="terminee").count(),
        "participants_total": base_participants.count(),
        "participants_valides": base_participants.filter(valide=True).count(),
    }

    # Widgets droite (top formations / top agents)
    top_formations = (
        base_sessions.values("formation__id", "formation__nom")
        .annotate(nb=Count("id"))
        .order_by("-nb")[:6]
    )

    top_agents = (
        base_participants.filter(valide=True)
        .values("agent__id", "agent__nom", "agent__prenom")
        .annotate(nb=Count("id"))
        .order_by("-nb")[:6]
    )

    sessions_upcoming = base_sessions.filter(date_debut__gte=timezone.now()).order_by("date_debut")[:5]
    sessions_recent = base_sessions.filter(statut="terminee").order_by("-date_debut")[:5]

    # dropdown formations
    formations = Formation.objects.filter(organisation=org).order_by("nom")

    return render(request, "permis/registres/registre_formations.html", {
        "titre": "Registre des Formations",
        "organisation": org,
        "kpi": kpi,

        "formations": formations,
        "page_obj": page_obj,
        "paginator": paginator,

        "top_formations": top_formations,
        "top_agents": top_agents,
        "sessions_upcoming": sessions_upcoming,
        "sessions_recent": sessions_recent,

        "filters": {
            "q": q,
            "formation": formation_id,
            "statut": statut,
            "agent": agent,
            "start": start,
            "end": end,
            "per_page": per_page,
        },
        "today": today,
    })

from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import AgentHabilitation, TypeHabilitation


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


@login_required
def registre_habilitations(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    today = timezone.now().date()

    # -----------------------------
    # Filtres GET
    # -----------------------------
    q = (request.GET.get("q") or "").strip()                  # recherche globale
    type_id = (request.GET.get("type") or "").strip()         # type habilitation
    validite = (request.GET.get("validite") or "").strip()    # valide / expire / bientot / inactif
    prestataire = (request.GET.get("prestataire") or "").strip()
    start = _parse_date(request.GET.get("start") or "")
    end = _parse_date(request.GET.get("end") or "")

    if not start and not end:
        start = today - timedelta(days=365)  # registre sur 1 an par défaut
        end = today + timedelta(days=365)

    per_page = int(request.GET.get("per_page") or 20)
    per_page = 20 if per_page not in (10, 20, 50, 100) else per_page

    # -----------------------------
    # Base queryset
    # AgentPrestataire n'a pas organisation => filtre via prestataire__organisation
    # -----------------------------
    qs = AgentHabilitation.objects.select_related(
        "agent",
        "agent__prestataire",
        "type_habilitation",
    ).filter(
        type_habilitation__organisation=org
    )

    # période sur date_obtention
    if start:
        qs = qs.filter(date_obtention__gte=start)
    if end:
        qs = qs.filter(date_obtention__lte=end)

    if type_id.isdigit():
        qs = qs.filter(type_habilitation_id=int(type_id))

    if prestataire:
        qs = qs.filter(
            Q(agent__prestataire__nom__icontains=prestataire) |
            Q(agent__prestataire__telephone__icontains=prestataire)
        )

    if q:
        qs = qs.filter(
            Q(agent__nom__icontains=q) |
            Q(agent__prenom__icontains=q) |
            Q(agent__matricule__icontains=q) |
            Q(type_habilitation__nom__icontains=q) |
            Q(type_habilitation__description__icontains=q)
        )

    # filtres validité (calcul en Python via dates)
    items = list(qs.order_by("-date_obtention"))

    # enrichissement : jours restants + statut de validité
    def _validity_badge(it):
        if not it.actif:
            return ("inactif", None)

        if it.date_expiration:
            days_left = (it.date_expiration - today).days
            if days_left < 0:
                return ("expire", days_left)
            if days_left <= 30:
                return ("bientot", days_left)
            return ("valide", days_left)

        return ("valide", None)  # pas d'expiration => valide

    enriched = []
    for it in items:
        status, days_left = _validity_badge(it)
        it.validite_statut = status          # "valide" / "expire" / "bientot" / "inactif"
        it.days_left = days_left             # int ou None
        enriched.append(it)

    if validite in {"valide", "expire", "bientot", "inactif"}:
        enriched = [x for x in enriched if x.validite_statut == validite]

    # -----------------------------
    # Pagination sur liste Python
    # -----------------------------
    paginator = Paginator(enriched, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # -----------------------------
    # KPI
    # -----------------------------
    base = AgentHabilitation.objects.filter(type_habilitation__organisation=org)
    total = base.count()
    actifs = base.filter(actif=True).count()

    # calcul valides/expirées/bientot
    valides = 0
    bientot = 0
    expires_ = 0
    inactifs = base.filter(actif=False).count()

    for it in base.select_related("type_habilitation"):
        st, days = _validity_badge(it)
        if st == "valide":
            valides += 1
        elif st == "bientot":
            bientot += 1
        elif st == "expire":
            expires_ += 1

    kpi = {
        "total": total,
        "actifs": actifs,
        "valides": valides,
        "bientot": bientot,
        "expires": expires_,
        "inactifs": inactifs,
    }

    # dropdown types
    types = TypeHabilitation.objects.filter(organisation=org).order_by("nom")

    return render(request, "permis/registres/registre_habilitations.html", {
        "titre": "Registre des Habilitations",
        "organisation": org,
        "today": today,

        "kpi": kpi,
        "types": types,

        "page_obj": page_obj,
        "paginator": paginator,

        "filters": {
            "q": q,
            "type": type_id,
            "validite": validite,
            "prestataire": prestataire,
            "start": start,
            "end": end,
            "per_page": per_page,
        },
    })

######## ============================ Gestion des permis & Intervention ================================

# permis/views.py


# permis/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Q

from .models import Intervention, PermisDelivre, TypePermis, AgentHabilitation


def _get_org(request):
    """
    Même logique que tes autres vues: l'utilisateur doit appartenir à une organisation.
    """
    return getattr(request.user, "organisation", None)


@login_required
def dashboard_permis_interventions(request):
    org = _get_org(request)

    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    # -----------------------
    # KPI
    # -----------------------
    total_interventions = Intervention.objects.filter(organisation=org).count()

    interventions_actives = Intervention.objects.filter(
        organisation=org,
        statut__in=["planifiee", "encours"]
    ).count()

    total_permis_delivres = PermisDelivre.objects.filter(organisation=org).count()

    permis_actifs = PermisDelivre.objects.filter(
        organisation=org,
        actif=True
    ).count()

    # ✅ FIX: AgentHabilitation n'a pas "organisation"
    agents_habilites = AgentHabilitation.objects.filter(
        actif=True,
        type_habilitation__organisation=org  # ✅ on filtre via TypeHabilitation
    ).values("agent_id").distinct().count()

    types_permis = TypePermis.objects.filter(
        organisation=org,
        actif=True
    ).count()

    # -----------------------
    # Listes "récents"
    # -----------------------
    interventions = (
        Intervention.objects
        .filter(organisation=org)
        .order_by("-date_debut")[:8]
    )

    permis_recents = (
        PermisDelivre.objects
        .select_related("agent", "agent__prestataire", "type_permis", "intervention")
        .filter(organisation=org)
        .order_by("-date_delivrance")[:8]
    )

    context = {
        "organisation": org,
        "kpi": {
            "total_interventions": total_interventions,
            "interventions_actives": interventions_actives,
            "total_permis": total_permis_delivres,
            "permis_actifs": permis_actifs,
            "agents_habilites": agents_habilites,
            "types_permis": types_permis,
        },
        "interventions": interventions,
        "permis_recents": permis_recents,
    }

    return render(request, "permis/dashboard.html", context)


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.db.models import Q

from .models import (
    TypePermis, Intervention, PermisDelivre,
    TypeHabilitation, AgentHabilitation
)
from prestataire.models import AgentPrestataire


def _get_org(request):
    return getattr(request.user, "organisation", None)


# -------------------------
# TYPES PERMIS
# -------------------------
@login_required
def type_permis_liste(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    q = (request.GET.get("q") or "").strip()
    qs = TypePermis.objects.filter(organisation=org)

    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(description__icontains=q))

    qs = qs.order_by("nom")

    return render(request, "permis/permis/types_liste.html", {
        "titre": "Types de permis",
        "organisation": org,
        "items": qs,
        "q": q,
    })


@login_required
def type_permis_creer(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    habilitations = TypeHabilitation.objects.filter(organisation=org, actif=True).order_by("nom")

    data = {"nom": "", "description": "", "actif": True, "habilitations_ids": []}

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["description"] = (request.POST.get("description") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")
        data["habilitations_ids"] = request.POST.getlist("habilitations_ids")

        if not data["nom"]:
            messages.error(request, "Le nom est obligatoire.")
        elif TypePermis.objects.filter(organisation=org, nom__iexact=data["nom"]).exists():
            messages.error(request, "Ce type de permis existe déjà.")
        else:
            with transaction.atomic():
                obj = TypePermis.objects.create(
                    organisation=org,
                    nom=data["nom"],
                    description=data["description"],
                    actif=data["actif"],
                )
                valid = habilitations.filter(id__in=data["habilitations_ids"])
                obj.habilitations_requises.set(valid)

            messages.success(request, "✅ Type de permis créé.")
            return redirect("permis:type_permis_liste")

    return render(request, "permis/permis/type_form.html", {
        "titre": "Nouveau type de permis",
        "organisation": org,
        "habilitations": habilitations,
        "data": data,
    })


# -------------------------
# INTERVENTIONS
# -------------------------
def _get_org(request):
    return getattr(request.user, "organisation", None)


def _agent_est_eligible(agent, type_permis, org):
    """
    Vérifie si l'agent possède toutes les habilitations requises et valides.
    """
    required_ids = list(
        type_permis.habilitations_requises.values_list("id", flat=True)
    )

    if not required_ids:
        return True, []

    today = timezone.now().date()

    habs = AgentHabilitation.objects.filter(
        agent=agent,
        type_habilitation_id__in=required_ids,
        actif=True,
        type_habilitation__organisation=org,
    ).select_related("type_habilitation")

    valid_ids = set()
    for h in habs:
        if h.est_valide_le(today):
            valid_ids.add(h.type_habilitation_id)

    missing_ids = [hid for hid in required_ids if hid not in valid_ids]

    return len(missing_ids) == 0, missing_ids


@login_required
def intervention_creer(request):

    org = _get_org(request)

    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    types_permis = (
        TypePermis.objects
        .filter(organisation=org, actif=True)
        .order_by("nom")
    )

    agents = (
        AgentPrestataire.objects
        .filter(prestataire__organisation=org)
        .select_related("prestataire")
        .order_by("nom", "prenom")
    )

    values = {
        "titre": "",
        "description": "",
        "lieu": "",
        "date_debut": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "date_fin": "",
        "statut": "planifiee",
        "permis_ids": [],
        "agents_ids": [],
    }

    if request.method == "POST":

        values["titre"] = request.POST.get("titre", "").strip()
        values["description"] = request.POST.get("description", "").strip()
        values["lieu"] = request.POST.get("lieu", "").strip()
        values["date_debut"] = request.POST.get("date_debut", "").strip()
        values["date_fin"] = request.POST.get("date_fin", "").strip()
        values["statut"] = request.POST.get("statut", "planifiee").strip()

        values["permis_ids"] = request.POST.getlist("permis_ids")
        values["agents_ids"] = request.POST.getlist("agents_ids")

        errors = []

        if not values["titre"]:
            errors.append("Titre obligatoire.")

        date_debut = parse_datetime(values["date_debut"]) if values["date_debut"] else None
        date_fin = parse_datetime(values["date_fin"]) if values["date_fin"] else None

        if not date_debut:
            errors.append("Date début invalide.")

        permis_valid = list(
            types_permis.filter(id__in=values["permis_ids"])
        )

        agents_valid = list(
            agents.filter(id__in=values["agents_ids"])
        )

        if errors:
            for e in errors:
                messages.error(request, e)

        else:

            with transaction.atomic():

                # 1) créer intervention
                inter = Intervention.objects.create(
                    organisation=org,
                    titre=values["titre"],
                    description=values["description"],
                    lieu=values["lieu"],
                    date_debut=date_debut,
                    date_fin=date_fin,
                    statut=values["statut"],
                )

                inter.permis_requis.set(permis_valid)
                inter.agents.set(agents_valid)

                # 2) générer permis délivrés
                permis_bulk = []

                for agent in agents_valid:

                    for type_permis in permis_valid:

                        eligible, missing_ids = _agent_est_eligible(
                            agent, type_permis, org
                        )

                        if eligible:

                            permis_bulk.append(
                                PermisDelivre(
                                    organisation=org,
                                    intervention=inter,
                                    agent=agent,
                                    type_permis=type_permis,
                                    statut="en_attente",
                                    actif=True,
                                )
                            )

                        else:

                            missing_names = list(
                                type_permis.habilitations_requises
                                .filter(id__in=missing_ids)
                                .values_list("nom", flat=True)
                            )

                            permis_bulk.append(
                                PermisDelivre(
                                    organisation=org,
                                    intervention=inter,
                                    agent=agent,
                                    type_permis=type_permis,
                                    statut="refuse",
                                    actif=False,
                                    motif_refus="Habilitations manquantes: " + ", ".join(missing_names),
                                )
                            )

                PermisDelivre.objects.bulk_create(permis_bulk)

                # 3) créer réponses questionnaire vides
                permis_crees = (
                    PermisDelivre.objects
                    .filter(
                        organisation=org,
                        intervention=inter,
                        statut="en_attente"
                    )
                    .select_related("type_permis")
                )

                questions = (
                    QuestionPermis.objects
                    .filter(
                        type_permis__in=[p.type_permis for p in permis_crees],
                        actif=True
                    )
                    .order_by("type_permis_id", "ordre")
                )

                questions_by_type = {}

                for q in questions:
                    questions_by_type.setdefault(q.type_permis_id, []).append(q)

                reponses_bulk = []

                for permis in permis_crees:

                    for question in questions_by_type.get(permis.type_permis_id, []):

                        reponses_bulk.append(
                            ReponsePermis(
                                permis=permis,
                                question=question
                            )
                        )

                ReponsePermis.objects.bulk_create(reponses_bulk)

            messages.success(
                request,
                "Intervention créée avec succès. Permis générés automatiquement."
            )

            return redirect(
                "permis:intervention_detail",
                pk=inter.pk
            )

    context = {
        "organisation": org,
        "types_permis": types_permis,
        "agents": agents,
        "values": values,
        "statuts": Intervention.STATUT_CHOICES,
    }

    return render(
        request,
        "permis/interventions/intervention_form.html",
        context,
    )

@login_required
def intervention_detail(request, pk):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    inter = get_object_or_404(
        Intervention.objects.prefetch_related("permis_requis", "agents"),
        pk=pk, organisation=org
    )

    delivrances = (
        PermisDelivre.objects.select_related("agent", "agent__prestataire", "type_permis")
        .filter(intervention=inter, organisation=org)
        .order_by("-date_delivrance")
    )

    # ✅ pour le formulaire "délivrer"
    agents = inter.agents.all().select_related("prestataire").order_by("nom", "prenom")
    permis_requis = inter.permis_requis.all().order_by("nom")

    return render(request, "permis/interventions/intervention_detail.html", {
        "titre": "Détail intervention",
        "organisation": org,
        "inter": inter,
        "delivrances": delivrances,
        "agents": agents,
        "permis_requis": permis_requis,
    })


# -------------------------
# DELIVRER PERMIS
# -------------------------
@login_required
def permis_delivrer(request, pk):
    """
    pk = intervention_id
    POST: agent_id, type_permis_id
    """
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    inter = get_object_or_404(Intervention, pk=pk, organisation=org)

    if request.method != "POST":
        messages.error(request, "Action non autorisée.")
        return redirect("permis:intervention_detail", pk=inter.pk)

    agent_id = (request.POST.get("agent_id") or "").strip()
    type_permis_id = (request.POST.get("type_permis_id") or "").strip()

    if not (agent_id.isdigit() and type_permis_id.isdigit()):
        messages.error(request, "Paramètres invalides.")
        return redirect("permis:intervention_detail", pk=inter.pk)

    # sécurité org agent
    agent = get_object_or_404(
        AgentPrestataire.objects.select_related("prestataire"),
        pk=int(agent_id),
        prestataire__organisation=org
    )

    type_permis = get_object_or_404(TypePermis, pk=int(type_permis_id), organisation=org, actif=True)

    # ✅ règle: le permis doit être requis par cette intervention
    if not inter.permis_requis.filter(id=type_permis.id).exists():
        messages.error(request, "Ce permis n'est pas requis pour cette intervention.")
        return redirect("permis:intervention_detail", pk=inter.pk)

    # ✅ règle: l'agent doit faire partie des agents de l'intervention
    if not inter.agents.filter(id=agent.id).exists():
        messages.error(request, "Cet agent n'est pas inscrit à l'intervention.")
        return redirect("permis:intervention_detail", pk=inter.pk)

    # ✅ check habilitations requises
    required_ids = list(type_permis.habilitations_requises.values_list("id", flat=True))

    today = timezone.now().date()
    if required_ids:
        habs = AgentHabilitation.objects.filter(
            agent=agent, type_habilitation_id__in=required_ids, actif=True
        ).select_related("type_habilitation")

        valid_ids = set()
        for h in habs:
            if h.est_valide_le(today):
                valid_ids.add(h.type_habilitation_id)

        missing = [hid for hid in required_ids if hid not in valid_ids]
        if missing:
            missing_names = list(
                type_permis.habilitations_requises.filter(id__in=missing).values_list("nom", flat=True)
            )
            messages.error(
                request,
                "❌ Permis refusé : habilitations manquantes/expirées : " + ", ".join(missing_names)
            )
            return redirect("permis:intervention_detail", pk=inter.pk)

    # ✅ délivrance (idempotent)
    PermisDelivre.objects.get_or_create(
        organisation=org,
        intervention=inter,
        agent=agent,
        type_permis=type_permis,
        defaults={"actif": True}
    )

    messages.success(request, "✅ Permis délivré.")
    return redirect("permis:intervention_detail", pk=inter.pk)


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import Intervention, PermisDelivre


def _get_org(request):
    return getattr(request.user, "organisation", None)


@login_required
def intervention_detail(request, pk):
    org = _get_org(request)

    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    inter = get_object_or_404(
        Intervention.objects.prefetch_related("permis_requis", "agents"),
        pk=pk,
        organisation=org
    )

    # Permis générés pour cette intervention
    delivrances = (
        PermisDelivre.objects
        .select_related("agent", "agent__prestataire", "type_permis", "intervention")
        .filter(organisation=org, intervention=inter)
        .order_by("-date_delivrance")
    )

    agents = (
        inter.agents.all()
        .select_related("prestataire")
        .order_by("nom", "prenom")
    )

    permis_requis = inter.permis_requis.all().order_by("nom")

    return render(request, "permis/interventions/intervention_detail.html", {
        "organisation": org,
        "inter": inter,
        "delivrances": delivrances,
        "agents": agents,
        "permis_requis": permis_requis,
    })


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import PermisDelivre, ReponsePermis


from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import PermisDelivre, ReponsePermis, AgentHabilitation


from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import PermisDelivre, ReponsePermis, AgentHabilitation


@login_required
def permis_detail(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    permis = get_object_or_404(
        PermisDelivre.objects.select_related(
            "agent", "agent__prestataire", "type_permis", "intervention"
        ),
        pk=pk,
        organisation=org
    )

    reponses = list(
        ReponsePermis.objects
        .select_related("question")
        .filter(permis=permis)
        .order_by("question__ordre", "id")
    )

    # ✅ Préparer les choix pour les questions type "choice"
    for r in reponses:
        if r.question.type_reponse == "choice":
            raw = r.question.choix or ""
            r.choices_list = [x.strip() for x in raw.split(";") if x.strip()]
        else:
            r.choices_list = []

    # =========================================================
    # ✅ HABILITATIONS : requises vs détenues par l’agent
    # =========================================================
    today = timezone.localdate()

    required_habs = list(
        permis.type_permis.habilitations_requises.all().order_by("nom")
    )

    # ⚠️ AgentHabilitation n'a PAS organisation => filtre via type_habilitation__organisation
    agent_habs = list(
        AgentHabilitation.objects
        .select_related("type_habilitation")
        .filter(
            agent=permis.agent,
            type_habilitation__organisation=org
        )
    )

    # map: hab_id -> AgentHabilitation (dernier en date si doublons)
    agent_map = {}
    for ah in agent_habs:
        hid = ah.type_habilitation_id
        if hid not in agent_map:
            agent_map[hid] = ah
        else:
            old = agent_map[hid]
            if (ah.date_obtention or date.min) > (old.date_obtention or date.min):
                agent_map[hid] = ah

    hab_rows = []
    missing_names = []

    for hab in required_habs:
        ah = agent_map.get(hab.id)

        if not ah:
            hab_rows.append({
                "hab": hab,
                "status": "missing",
                "label": "Manquante",
                "days_left": None,
            })
            missing_names.append(hab.nom)
            continue

        if not getattr(ah, "actif", True):
            hab_rows.append({
                "hab": hab,
                "status": "inactive",
                "label": "Inactive",
                "days_left": None,
            })
            missing_names.append(hab.nom)
            continue

        # expiration : None => illimitée
        exp = getattr(ah, "date_expiration", None)
        if exp:
            exp_date = exp.date() if hasattr(exp, "date") else exp
            days_left = (exp_date - today).days

            if days_left < 0:
                hab_rows.append({
                    "hab": hab,
                    "status": "expired",
                    "label": "Expirée",
                    "days_left": days_left,  # négatif
                })
                missing_names.append(hab.nom)

            elif days_left <= 15:
                hab_rows.append({
                    "hab": hab,
                    "status": "soon",
                    "label": "Bientôt expirée",
                    "days_left": days_left,
                })

            else:
                hab_rows.append({
                    "hab": hab,
                    "status": "ok",
                    "label": "OK",
                    "days_left": days_left,
                })
        else:
            hab_rows.append({
                "hab": hab,
                "status": "ok",
                "label": "OK",
                "days_left": None,  # illimitée
            })

    # =========================================================
    # ✅ Sauvegarde des réponses (si permis en attente)
    # =========================================================
    if request.method == "POST" and permis.statut == "en_attente":
        with transaction.atomic():
            for r in reponses:
                key = f"q_{r.id}"
                t = r.question.type_reponse

                if t == "bool":
                    raw = (request.POST.get(key) or "").strip().lower()
                    if raw == "true":
                        r.valeur_bool = True
                    elif raw == "false":
                        r.valeur_bool = False
                    else:
                        r.valeur_bool = None

                elif t == "text":
                    r.valeur_text = (request.POST.get(key) or "").strip()

                elif t == "choice":
                    r.valeur_choice = (request.POST.get(key) or "").strip()

                elif t == "number":
                    raw = (request.POST.get(key) or "").strip()
                    try:
                        r.valeur_number = float(raw) if raw else None
                    except ValueError:
                        r.valeur_number = None

                r.remarque = (request.POST.get(f"rem_{r.id}") or "").strip()
                r.save()

        messages.success(request, "✅ Réponses enregistrées.")
        return redirect("permis:permis_detail", pk=permis.pk)

    # (Optionnel) si permis refusé et motif vide, on propose un motif auto
    if permis.statut == "refuse" and (not permis.motif_refus) and missing_names:
        permis.motif_refus = "Habilitations manquantes: " + ", ".join(missing_names)
        permis.save(update_fields=["motif_refus"])

    return render(request, "permis/permis/permis_detail.html", {
        "organisation": org,
        "permis": permis,
        "reponses": reponses,

        # ✅ nouveau pour le template
        "hab_rows": hab_rows,
        "missing_names": missing_names,
        "required_count": len(required_habs),
    })

@login_required
def permis_valider(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    permis = get_object_or_404(PermisDelivre, pk=pk, organisation=org)

    if request.method != "POST":
        return redirect("permis:permis_detail", pk=permis.pk)

    if permis.statut != "en_attente":
        messages.error(request, "Ce permis n'est pas en attente.")
        return redirect("permis:permis_detail", pk=permis.pk)

    reponses = ReponsePermis.objects.select_related("question").filter(permis=permis)

    # ✅ vérification des questions obligatoires
    missing = []
    for r in reponses:
        if not r.question.obligatoire:
            continue

        t = r.question.type_reponse
        if t == "bool" and r.valeur_bool is None:
            missing.append(r.question.texte)
        elif t == "text" and not (r.valeur_text or "").strip():
            missing.append(r.question.texte)
        elif t == "choice" and not (r.valeur_choice or "").strip():
            missing.append(r.question.texte)
        elif t == "number" and r.valeur_number is None:
            missing.append(r.question.texte)

    if missing:
        messages.error(
            request,
            "❌ Questions obligatoires non renseignées : " +
            " | ".join(missing[:6]) +
            (" ..." if len(missing) > 6 else "")
        )
        return redirect("permis:permis_detail", pk=permis.pk)

    # ✅ valider
    permis.statut = "valide"
    permis.valide_par = request.user
    permis.valide_le = timezone.now()
    permis.save(update_fields=["statut", "valide_par", "valide_le"])

    messages.success(request, "✅ Permis validé. PDF final possible.")
    return redirect("permis:permis_detail", pk=permis.pk)


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import PermisDelivre, ReponsePermis


@login_required
def permis_pdf(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    permis = get_object_or_404(
        PermisDelivre.objects.select_related(
            "intervention", "type_permis", "agent", "agent__prestataire"
        ),
        pk=pk,
        organisation=org
    )

    # ✅ Option A : PDF final seulement si validé
    if permis.statut != "valide":
        messages.error(request, "Le PDF final est disponible uniquement pour un permis validé.")
        return redirect("permis:permis_detail", pk=permis.pk)

    reponses = list(
        ReponsePermis.objects.select_related("question")
        .filter(permis=permis)
        .order_by("question__ordre", "id")
    )

    # Préparer choices_list (utile si tu veux afficher proprement les choix)
    for r in reponses:
        if r.question.type_reponse == "choice":
            raw = r.question.choix or ""
            r.choices_list = [x.strip() for x in raw.split(";") if x.strip()]
        else:
            r.choices_list = []

    return render(request, "permis/permis/permis_pdf.html", {
        "organisation": org,
        "permis": permis,
        "reponses": reponses,
    })


# =========================
# PERMIS DISPONIBLES
# =========================
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Q, Count

from .models import TypePermis


def _get_org(request):
    return getattr(request.user, "organisation", None)


@login_required
def permis_liste(request):
    org = _get_org(request)

    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    # ------------------------
    # Filtres GET
    # ------------------------
    q = (request.GET.get("q") or "").strip()

    qs = (
        TypePermis.objects
        .filter(
            organisation=org,
            actif=True
        )
        .prefetch_related("habilitations_requises")
        .annotate(
            nb_habilitations=Count("habilitations_requises", distinct=True)
        )
        .order_by("nom")
    )

    if q:
        qs = qs.filter(
            Q(nom__icontains=q) |
            Q(description__icontains=q) |
            Q(habilitations_requises__nom__icontains=q)
        ).distinct()

    items = list(qs)

    # ------------------------
    # KPI
    # ------------------------
    total = len(items)
    avec_hab = len([p for p in items if p.nb_habilitations > 0])
    sans_hab = len([p for p in items if p.nb_habilitations == 0])

    context = {
        "titre": "Permis disponibles",
        "organisation": org,
        "items": items,
        "kpi": {
            "total": total,
            "avec_habilitations": avec_hab,
            "sans_habilitations": sans_hab,
        },
        "filters": {
            "q": q,
        }
    }

    return render(request, "permis/permis/permis_liste.html", context)
# =========================
# REGISTRE PAR TYPE DE PERMIS
# =========================
@login_required
def registre_par_permis(request, pk):
    org = _get_org(request)

    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    type_permis = get_object_or_404(
        TypePermis,
        pk=pk,
        organisation=org
    )

    permis_qs = (
        PermisDelivre.objects
        .select_related("agent", "agent__prestataire", "intervention")
        .filter(
            organisation=org,
            type_permis=type_permis
        )
        .order_by("-date_delivrance")
    )

    return render(request, "permis/permis/registre_par_permis.html", {
        "titre": f"Registre - {type_permis.nom}",
        "organisation": org,
        "type_permis": type_permis,
        "items": permis_qs,
    })


from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q, Count

from .models import PermisDelivre, TypePermis


def _get_org(request):
    return getattr(request.user, "organisation", None)


def _parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


@login_required
def registre_permis_travail(request):
    org = _get_org(request)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    today = timezone.now()
    today_date = today.date()

    # -----------------------------
    # Filtres GET
    # -----------------------------
    q = (request.GET.get("q") or "").strip()
    type_id = (request.GET.get("type") or "").strip()          # TypePermis id
    statut = (request.GET.get("statut") or "").strip()         # en_attente / valide / refuse
    start = _parse_date(request.GET.get("start") or "")
    end = _parse_date(request.GET.get("end") or "")

    # défaut : 60 jours autour (comme un registre)
    if not start and not end:
        start = (today_date - timedelta(days=60))
        end = (today_date + timedelta(days=60))

    # -----------------------------
    # Base queryset
    # -----------------------------
    qs = (
        PermisDelivre.objects
        .select_related("type_permis", "intervention", "agent", "agent__prestataire")
        .filter(organisation=org)
        .order_by("-date_delivrance")
    )

    # période (date_delivrance)
    if start:
        qs = qs.filter(date_delivrance__date__gte=start)
    if end:
        qs = qs.filter(date_delivrance__date__lte=end)

    if type_id.isdigit():
        qs = qs.filter(type_permis_id=int(type_id))

    if statut in {"en_attente", "valide", "refuse"}:
        qs = qs.filter(statut=statut)

    if q:
        qs = qs.filter(
            Q(agent__nom__icontains=q) |
            Q(agent__prenom__icontains=q) |
            Q(agent__prestataire__nom__icontains=q) |
            Q(intervention__titre__icontains=q) |
            Q(type_permis__nom__icontains=q)
        )

    items = list(qs[:300])  # limite simple (tu peux paginer après)

    # -----------------------------
    # KPI
    # -----------------------------
    base = PermisDelivre.objects.filter(organisation=org)

    total_delivres = base.count()
    total_actifs = base.filter(actif=True).count()
    total_bloques = base.filter(statut="refuse").count()

    # "Expirés" : actif=True ET date_expiration < now
    total_expires = base.filter(actif=True, date_expiration__lt=today).count()

    kpi = {
        "delivres": total_delivres,
        "actifs": total_actifs,
        "bloques": total_bloques,
        "expires": total_expires,
    }

    # -----------------------------
    # Répartition par type (donut)
    # -----------------------------
    repartition = (
        base.values("type_permis__id", "type_permis__nom")
        .annotate(nb=Count("id"))
        .order_by("-nb")[:8]
    )

    chart_labels = [x["type_permis__nom"] for x in repartition]
    chart_values = [x["nb"] for x in repartition]

    # dropdown types
    types = TypePermis.objects.filter(organisation=org, actif=True).order_by("nom")

    return render(request, "permis/permis/registre_permis_travail.html", {
        "titre": "Registre des Permis de Travail",
        "organisation": org,
        "items": items,
        "types": types,
        "kpi": kpi,
        "filters": {
            "q": q,
            "type": type_id,
            "statut": statut,
            "start": start,
            "end": end,
        },
        "chart": {
            "labels": chart_labels,
            "values": chart_values,
        },
        "now": today,
    })

# views.py
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from permis.models import PermisDelivre

@login_required
def permis_reevaluer(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    permis = get_object_or_404(PermisDelivre, pk=pk, organisation=org)

    if permis.agent_est_eligible(date_ref=timezone.now().date()):
        permis.statut = "en_attente"
        permis.actif = True
        permis.motif_refus = ""
        permis.save(update_fields=["statut", "actif", "motif_refus"])
        messages.success(request, "✅ Permis réactivé : l’agent est maintenant éligible.")
    else:
        messages.error(request, "❌ Toujours non éligible : habilitations manquantes/expirées.")

    return redirect("permis:permis_detail", pk=permis.pk)
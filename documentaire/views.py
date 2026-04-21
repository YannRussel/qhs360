import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    Document, DocumentAccessLog, DocumentNotification,
    DocumentType, Processus, DocumentVersion
)
from organisations.models import Organisation


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _get_user_organisation(request):
    """
    Adaptation rapide :
    - si ton User a un champ organisation => return request.user.organisation
    - sinon tu peux stocker organisation_id en session
    - fallback : première organisation
    """
    if hasattr(request.user, "organisation") and request.user.organisation_id:
        return request.user.organisation
    org_id = request.session.get("organisation_id")
    if org_id:
        return Organisation.objects.filter(id=org_id).first()
    return Organisation.objects.first()


def _log(request, document, action, details=""):
    DocumentAccessLog.objects.create(
        document=document,
        user=request.user if request.user.is_authenticated else None,
        action=action,
        details=details[:255],
        ip=_get_ip(request),
    )


# ============================================================
# ✅ GÉNÉRATION DU CODE DOCUMENT (Type / Processus / Site)
# ============================================================

def _abbr(value: str, max_len: int = 3) -> str:
    """Abréviation simple (ex: 'Ressources Humaines' -> 'RH')."""
    if not value:
        return ""
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", value.upper())
    if not words:
        return ""
    ab = "".join(w[0] for w in words[:max_len])
    return ab[:max_len]


def _next_sequence_for_prefix(org, prefix: str) -> int:
    """
    Recherche le dernier code du type PREFIX-0001 et retourne le numéro suivant.
    Lock SELECT FOR UPDATE pour éviter les doublons en concurrence.
    """
    last = (
        Document.objects.select_for_update()
        .filter(organisation=org, code__startswith=prefix + "-")
        .order_by("-code")
        .first()
    )
    if not last:
        return 1

    m = re.search(r"-(\d+)$", last.code or "")
    if not m:
        return 1
    return int(m.group(1)) + 1


def generate_document_code(org, type_id: int, proc_id=None, site_id=None) -> str:
    """
    Format :
      {TYPE}-{PROC}-{SITE}-{NNNN}
    PROC et SITE sont optionnels.
    Exemple : PR-AC-S3-0001
    """
    t = DocumentType.objects.get(pk=type_id, organisation=org)
    type_part = _abbr(t.nom, 3) or "DOC"

    proc_part = ""
    if proc_id:
        p = Processus.objects.filter(pk=proc_id, organisation=org).first()
        proc_part = _abbr(p.nom, 3) if p else ""

    site_part = ""
    if site_id:
        s = org.sites.filter(pk=site_id).first() if hasattr(org, "sites") else None
        site_part = _abbr(getattr(s, "nom", ""), 3) if s else ""

    parts = [type_part]
    if proc_part:
        parts.append(proc_part)
    if site_part:
        parts.append(site_part)

    prefix = "-".join(parts)

    seq = _next_sequence_for_prefix(org, prefix)
    return f"{prefix}-{seq:04d}"


@login_required
def document_generate_code(request):
    """Endpoint AJAX: renvoie un code prévisionnel."""
    org = _get_user_organisation(request)

    type_id = (request.GET.get("type_document") or "").strip()
    proc_id = (request.GET.get("processus") or "").strip()
    site_id = (request.GET.get("site") or "").strip()

    if not type_id:
        return JsonResponse({"ok": False, "error": "type_document requis"}, status=400)

    with transaction.atomic():
        code = generate_document_code(
            org,
            type_id=int(type_id),
            proc_id=int(proc_id) if proc_id else None,
            site_id=int(site_id) if site_id else None,
        )

    return JsonResponse({"ok": True, "code": code})


# ============================================================
# LISTE
# ============================================================

from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

@login_required
def document_list(request):
    org = _get_user_organisation(request)
    if not org:
        raise Http404("Organisation introuvable. Configure organisation sur l'utilisateur ou en session.")

    # -----------------------------
    # GET params (alignés avec le template)
    # -----------------------------
    q = (request.GET.get("q") or "").strip()
    type_id = (request.GET.get("type") or "").strip()
    proc_id = (request.GET.get("processus") or "").strip()
    site_id = (request.GET.get("site") or "").strip()
    statut = (request.GET.get("statut") or "").strip()
    owner = (request.GET.get("owner") or "").strip()

    # ✅ ton template envoie date_filter/date_from/date_to
    date_filter = (request.GET.get("date_filter") or "").strip()  # cree | modifie | revision | ""
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()

    # ✅ ton template envoie per_page
    try:
        per_page = int(request.GET.get("per_page") or 10)
    except ValueError:
        per_page = 10
    per_page = per_page if per_page in (10, 20, 50, 100) else 10

    # -----------------------------
    # Queryset
    # -----------------------------
    qs = Document.objects.filter(organisation=org).select_related(
        "type_document", "processus", "site", "proprietaire", "version_courante"
    )

    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(titre__icontains=q)
            | Q(mots_cles__icontains=q)
            | Q(type_document__nom__icontains=q)
            | Q(processus__nom__icontains=q)
            | Q(site__nom__icontains=q)
        )

    if type_id:
        qs = qs.filter(type_document_id=type_id)
    if proc_id:
        qs = qs.filter(processus_id=proc_id)
    if site_id:
        qs = qs.filter(site_id=site_id)
    if statut:
        qs = qs.filter(statut=statut)
    if owner == "me":
        qs = qs.filter(proprietaire=request.user)

    # -----------------------------
    # Filtre date (range)
    # -----------------------------
    # On filtre par intervalle seulement si les 2 dates sont valides
    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    d_from = parse_date(date_from) if date_from else None
    d_to = parse_date(date_to) if date_to else None

    if date_filter and (d_from or d_to):
        # champs disponibles dans ton modèle : cree_le, modifie_le, date_prochaine_revision :contentReference[oaicite:3]{index=3}
        if date_filter == "cree":
            field = "cree_le__date"
        elif date_filter == "modifie":
            field = "modifie_le__date"
        elif date_filter == "revision":
            field = "date_prochaine_revision"
        else:
            field = None

        if field:
            if d_from and d_to:
                qs = qs.filter(**{f"{field}__range": (d_from, d_to)})
            elif d_from:
                qs = qs.filter(**{f"{field}__gte": d_from})
            elif d_to:
                qs = qs.filter(**{f"{field}__lte": d_to})

    qs = qs.order_by("-modifie_le", "-cree_le")

    # -----------------------------
    # Pagination
    # -----------------------------
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page)

    # -----------------------------
    # Data pour filtres
    # -----------------------------
    types = DocumentType.objects.filter(organisation=org, actif=True).order_by("nom")
    processus = Processus.objects.filter(organisation=org, actif=True).order_by("nom")
    sites = org.sites.filter(actif=True).order_by("nom") if hasattr(org, "sites") else []

    # -----------------------------
    # KPIs (optionnel mais ton template les affiche)
    # -----------------------------
    total = qs.count()
    a_jour = qs.filter(statut=Document.APPROUVE).count()
    retard = qs.filter(date_prochaine_revision__lt=timezone.localdate()).count()
    obsolete = qs.filter(statut=Document.OBSOLETE).count()

    context = {
        "titre": "Bibliothèque documentaire",
        "page_obj": page_obj,     # ✅ ton template boucle sur page_obj
        "docs": page_obj,         # ✅ bonus : si ailleurs tu utilises docs ça marche aussi
        "q": q,

        "types": types,
        "processus": processus,
        "sites": sites,
        "statuts": Document.STATUT_CHOICES,

        "filters": {
            "type": type_id,
            "processus": proc_id,
            "site": site_id,
            "statut": statut,
            "date_filter": date_filter,
            "date_from": date_from,
            "date_to": date_to,
            "per_page": per_page,
        },

        "kpis": {
            "total": total,
            "a_jour": a_jour,
            "retard": retard,
            "obsolete": obsolete,
        },
        # notif_count si tu l’utilises ailleurs (sinon retire)
        "notif_count": DocumentNotification.objects.filter(organisation=org, user=request.user, lu=False).count(),
    }
    return render(request, "documentaire/document_list.html", context)


# ============================================================
# CREATE (✅ code auto)
# ============================================================

@login_required
def document_create(request):
    org = _get_user_organisation(request)
    if request.method == "POST":
        # ✅ on ne saisit plus le code à la main : génération serveur
        titre = (request.POST.get("titre") or "").strip()
        type_id = (request.POST.get("type_document") or "").strip()
        proc_id = (request.POST.get("processus") or "").strip()
        site_id = (request.POST.get("site") or "").strip()
        mots_cles = (request.POST.get("mots_cles") or "").strip()
        confidentialite = True if request.POST.get("confidentialite") == "on" else False
        date_prochaine_revision = (request.POST.get("date_prochaine_revision") or "").strip()

        fichier = request.FILES.get("fichier")
        version = (request.POST.get("version") or "1.0").strip()
        commentaire = (request.POST.get("commentaire") or "").strip()

        # validations simples
        if not (titre and type_id and fichier):
            messages.error(request, "Titre, type de document et fichier sont obligatoires.")
            return redirect("documentaire:create")

        with transaction.atomic():
            code = generate_document_code(
                org,
                type_id=int(type_id),
                proc_id=int(proc_id) if proc_id else None,
                site_id=int(site_id) if site_id else None,
            )

            doc = Document.objects.create(
                organisation=org,
                code=code,
                titre=titre,
                type_document_id=type_id,
                processus_id=proc_id or None,
                site_id=site_id or None,
                mots_cles=mots_cles,
                statut=Document.BROUILLON,
                proprietaire=request.user,
                confidentialite=confidentialite,
                date_prochaine_revision=date_prochaine_revision or None
            )

            v = DocumentVersion.objects.create(
                document=doc,
                version=version,
                fichier=fichier,
                commentaire=commentaire,
                cree_par=request.user,
                statut_snapshot=doc.statut
            )
            doc.version_courante = v
            doc.save(update_fields=["version_courante"])

        _log(request, doc, DocumentAccessLog.ACTION_CREATE, details=f"Création + v{version}")
        messages.success(request, f"Document créé : {doc.code} (brouillon) + première version.")
        return redirect("documentaire:detail", pk=doc.pk)

    types = DocumentType.objects.filter(organisation=org, actif=True)
    processus = Processus.objects.filter(organisation=org, actif=True)
    sites = org.sites.filter(actif=True) if org and hasattr(org, "sites") else []
    context = {
        "titre": "Nouveau document",
        "types": types,
        "processus": processus,
        "sites": sites,
    }
    return render(request, "documentaire/document_create.html", context)


# ============================================================
# DETAIL & AUTRES VUES (inchangées)
# ============================================================

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

@login_required
def document_detail(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(
        Document.objects.select_related(
            "type_document", "processus", "site", "proprietaire", "version_courante"
        ),
        pk=pk,
        organisation=org,
    )

    versions = doc.versions.select_related("cree_par").all().order_by("-cree_le")

    # ✅ logs (10 derniers) + user
    logs = doc.logs.select_related("user").all()[:10]

    _log(request, doc, DocumentAccessLog.ACTION_VIEW, details="Consultation")

    context = {
        "titre": f"Document — {doc.code}",
        "doc": doc,
        "versions": versions,

        # ✅ AJOUTE ÇA (sinon ton select est vide)
        "statuts": Document.STATUT_CHOICES,

        # ✅ AJOUTE ÇA (sinon le journal est vide)
        "logs": logs,
    }
    return render(request, "documentaire/document_detail.html", context)

@login_required
def document_edit_meta(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(Document, pk=pk, organisation=org)

    if request.method == "POST":
        doc.titre = (request.POST.get("titre") or "").strip()
        doc.mots_cles = (request.POST.get("mots_cles") or "").strip()
        doc.confidentialite = True if request.POST.get("confidentialite") == "on" else False
        doc.date_prochaine_revision = (request.POST.get("date_prochaine_revision") or "").strip() or None

        type_id = (request.POST.get("type_document") or "").strip()
        proc_id = (request.POST.get("processus") or "").strip()
        site_id = (request.POST.get("site") or "").strip()

        if type_id:
            doc.type_document_id = type_id
        doc.processus_id = proc_id or None
        doc.site_id = site_id or None

        doc.save()
        _log(request, doc, DocumentAccessLog.ACTION_EDIT, details="Modification meta")
        messages.success(request, "Informations du document mises à jour.")
        return redirect("documentaire:detail", pk=doc.pk)

    types = DocumentType.objects.filter(organisation=org, actif=True)
    processus = Processus.objects.filter(organisation=org, actif=True)
    sites = org.sites.filter(actif=True) if org and hasattr(org, "sites") else []

    context = {
        "titre": f"Modifier — {doc.code}",
        "doc": doc,
        "types": types,
        "processus": processus,
        "sites": sites,
    }
    return render(request, "documentaire/document_edit_meta.html", context)


@login_required
def document_versions(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(Document, pk=pk, organisation=org)
    versions = doc.versions.select_related("cree_par").all().order_by("-cree_le")

    context = {
        "titre": f"Versions — {doc.code}",
        "doc": doc,
        "versions": versions,
    }
    return render(request, "documentaire/document_versions.html", context)


@login_required
def document_add_version(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(Document, pk=pk, organisation=org)

    if request.method == "POST":
        fichier = request.FILES.get("fichier")
        version = (request.POST.get("version") or "").strip()
        commentaire = (request.POST.get("commentaire") or "").strip()

        if not (fichier and version):
            messages.error(request, "Version et fichier sont obligatoires.")
            return redirect("documentaire:add_version", pk=doc.pk)

        v = DocumentVersion.objects.create(
            document=doc,
            version=version,
            fichier=fichier,
            commentaire=commentaire,
            cree_par=request.user,
            statut_snapshot=doc.statut
        )
        doc.version_courante = v
        doc.modifie_le = timezone.now()
        doc.save(update_fields=["version_courante", "modifie_le"])

        _log(request, doc, DocumentAccessLog.ACTION_NEW_VERSION, details=f"Ajout v{version}")
        messages.success(request, f"Nouvelle version {version} ajoutée.")
        return redirect("documentaire:detail", pk=doc.pk)

    context = {"titre": f"Ajouter une version — {doc.code}", "doc": doc}
    return render(request, "documentaire/document_add_version.html", context)


@login_required
def document_change_status(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(Document, pk=pk, organisation=org)

    if request.method == "POST":
        statut = (request.POST.get("statut") or "").strip()
        if statut not in dict(Document.STATUT_CHOICES):
            messages.error(request, "Statut invalide.")
            return redirect("documentaire:detail", pk=doc.pk)

        doc.statut = statut
        doc.modifie_le = timezone.now()
        doc.save(update_fields=["statut", "modifie_le"])
        _log(request, doc, DocumentAccessLog.ACTION_STATUS, details=f"Statut -> {statut}")

        messages.success(request, "Statut mis à jour.")
        return redirect("documentaire:detail", pk=doc.pk)

    return redirect("documentaire:detail", pk=doc.pk)


@login_required
def document_archive(request, pk):
    org = _get_user_organisation(request)
    doc = get_object_or_404(Document, pk=pk, organisation=org)

    doc.archive = True
    doc.modifie_le = timezone.now()
    doc.save(update_fields=["archive", "modifie_le"])
    _log(request, doc, DocumentAccessLog.ACTION_ARCHIVE, details="Archivage")
    messages.success(request, "Document archivé.")
    return redirect("documentaire:list")


@login_required
def document_download_version(request, version_id):
    org = _get_user_organisation(request)
    v = get_object_or_404(
        DocumentVersion.objects.select_related("document"),
        pk=version_id,
        document__organisation=org
    )

    doc = v.document
    _log(request, doc, DocumentAccessLog.ACTION_DOWNLOAD, details=f"Téléchargement v{v.version}")

    if not v.fichier:
        raise Http404("Fichier introuvable.")

    return FileResponse(v.fichier.open("rb"), as_attachment=True, filename=v.fichier.name)


@login_required
def document_notifications(request):
    org = _get_user_organisation(request)
    qs = DocumentNotification.objects.filter(organisation=org, user=request.user).select_related("document").order_by("-cree_le")
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {"titre": "Notifications", "page": page}
    return render(request, "documentaire/document_notifications.html", context)


@login_required
def notification_mark_read(request, notif_id):
    org = _get_user_organisation(request)
    notif = get_object_or_404(DocumentNotification, pk=notif_id, organisation=org, user=request.user)
    notif.lu = True
    notif.save(update_fields=["lu"])
    return redirect("documentaire:notifications")
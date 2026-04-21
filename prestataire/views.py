from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Prestataire, DomaineIntervention

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Count, Q

from .models import Prestataire

@login_required
def prestataire_liste(request):
    org = request.user.organisation

    q = (request.GET.get("q") or "").strip()
    statut = (request.GET.get("statut") or "").strip()  # "", "actif", "inactif"

    qs = Prestataire.objects.filter(organisation=org)

    if q:
        qs = qs.filter(
            Q(nom__icontains=q) |
            Q(telephone__icontains=q) |
            Q(email__icontains=q)
        )

    if statut == "actif":
        qs = qs.filter(actif=True)
    elif statut == "inactif":
        qs = qs.filter(actif=False)

    qs = qs.order_by("nom")

    # ====== KPI ======
    total = Prestataire.objects.filter(organisation=org).count()
    total_actifs = Prestataire.objects.filter(organisation=org, actif=True).count()
    total_inactifs = Prestataire.objects.filter(organisation=org, actif=False).count()

    # ====== Affectations (sites/zones) ======
    # On suppose que ton app sites contient AffectationPrestataire + Zone comme tu l’as défini.
    # Si jamais l’app n’est pas installée, on affiche juste "Non affecté".
    mapping = {}  # prestataire_id -> list of {site_nom, zones_noms or []}
    try:
        from sites.models import AffectationPrestataire  # <-- adapte si ton app s'appelle autrement

        affectations = (
            AffectationPrestataire.objects
            .filter(site__organisation=org, actif=True)
            .select_related("site", "prestataire")
            .prefetch_related("zones")
        )

        for a in affectations:
            zones = [z.nom for z in a.zones.all()]
            mapping.setdefault(a.prestataire_id, []).append({
                "site": a.site.nom,
                "zones": zones,   # vide => "Tout le site"
            })

    except Exception:
        mapping = {}

    return render(request, "prestataire/liste.html", {
        "organisation": org,
        "prestataire": qs,
        "q": q,
        "statut": statut,
        "kpi": {
            "total": total,
            "actifs": total_actifs,
            "inactifs": total_inactifs,
        },
        "interventions": mapping,
    })


from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect

from .models import (
    Prestataire,
    DomaineIntervention,
    DocumentPrestataire,
    AgentPrestataire,   # ✅ important
)


def _parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@login_required
def prestataire_creer(request):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    domaines = DomaineIntervention.objects.filter(organisation=org, actif=True).order_by("nom")

    # valeurs par défaut (pour garder les champs en cas d'erreur)
    data = {
        "nom": "",
        "telephone": "",
        "email": "",
        "adresse": "",
        "actif": True,
        "domaine_id": "",

        # docs (dates/textes seulement)
        "immatriculation_date_emission": "",
        "immatriculation_date_expiration": "",
        "immatriculation_description": "",

        "niu_date_emission": "",
        "niu_date_expiration": "",
        "niu_description": "",
    }

    if request.method == "POST":
        # ============ Prestataire ============
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["telephone"] = (request.POST.get("telephone") or "").strip()
        data["email"] = (request.POST.get("email") or "").strip()
        data["adresse"] = (request.POST.get("adresse") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")
        data["domaine_id"] = (request.POST.get("domaine") or "").strip()

        # ============ Docs : valeurs texte/date ============
        data["immatriculation_date_emission"] = request.POST.get("immatriculation_date_emission") or ""
        data["immatriculation_date_expiration"] = request.POST.get("immatriculation_date_expiration") or ""
        data["immatriculation_description"] = (request.POST.get("immatriculation_description") or "").strip()

        data["niu_date_emission"] = request.POST.get("niu_date_emission") or ""
        data["niu_date_expiration"] = request.POST.get("niu_date_expiration") or ""
        data["niu_description"] = (request.POST.get("niu_description") or "").strip()

        # ============ VALIDATIONS ============
        if not data["nom"]:
            messages.error(request, "Le nom du prestataire est obligatoire.")
            return render(request, "prestataire/form_prestataire.html", {
                "titre": "Nouveau prestataire",
                "domaines": domaines,
                "data": data,
            })

        if not data["domaine_id"]:
            messages.error(request, "Veuillez sélectionner un domaine d’intervention.")
            return render(request, "prestataire/form_prestataire.html", {
                "titre": "Nouveau prestataire",
                "domaines": domaines,
                "data": data,
            })

        domaine = domaines.filter(id=data["domaine_id"]).first()
        if not domaine:
            messages.error(request, "Domaine invalide.")
            return render(request, "prestataire/form_prestataire.html", {
                "titre": "Nouveau prestataire",
                "domaines": domaines,
                "data": data,
            })

        # unicité par organisation
        if Prestataire.objects.filter(organisation=org, nom__iexact=data["nom"]).exists():
            messages.error(request, "Ce prestataire existe déjà dans votre organisation.")
            return render(request, "prestataire/form_prestataire.html", {
                "titre": "Nouveau prestataire",
                "domaines": domaines,
                "data": data,
            })

        try:
            with transaction.atomic():
                # ✅ 1) Prestataire
                p = Prestataire.objects.create(
                    organisation=org,
                    domaine=domaine,
                    nom=data["nom"],
                    telephone=data["telephone"],
                    email=data["email"],
                    adresse=data["adresse"],
                    actif=data["actif"],
                )

                # ✅ 2) Documents

                # IMMATRICULATION
                imm_file = request.FILES.get("immatriculation_fichier")
                if imm_file:
                    DocumentPrestataire.objects.create(
                        prestataire=p,
                        type_document="immatriculation",
                        fichier=imm_file,
                        date_emission=_parse_date(request.POST.get("immatriculation_date_emission") or ""),
                        date_expiration=_parse_date(request.POST.get("immatriculation_date_expiration") or ""),
                        description=(request.POST.get("immatriculation_description") or "").strip(),
                        actif=(request.POST.get("immatriculation_actif") == "on"),
                    )

                # NIU
                niu_file = request.FILES.get("niu_fichier")
                if niu_file:
                    DocumentPrestataire.objects.create(
                        prestataire=p,
                        type_document="niu",
                        fichier=niu_file,
                        date_emission=_parse_date(request.POST.get("niu_date_emission") or ""),
                        date_expiration=_parse_date(request.POST.get("niu_date_expiration") or ""),
                        description=(request.POST.get("niu_description") or "").strip(),
                        actif=(request.POST.get("niu_actif") == "on"),
                    )

                # AUTRES (illimité) — fichier obligatoire (car FileField non-null)
                autres_titres = request.POST.getlist("autre_titre[]")
                autres_desc = request.POST.getlist("autre_description[]")
                autres_emis = request.POST.getlist("autre_date_emission[]")
                autres_exp = request.POST.getlist("autre_date_expiration[]")
                autres_files = request.FILES.getlist("autre_fichier[]")

                for idx, titre in enumerate(autres_titres):
                    titre = (titre or "").strip()
                    file_obj = autres_files[idx] if idx < len(autres_files) else None

                    # ignore lignes totalement vides
                    if not titre and not file_obj:
                        continue

                    if not titre:
                        raise ValueError("Chaque document 'Autre' doit avoir un titre.")

                    if not file_obj:
                        raise ValueError(f"Le document 'Autre' « {titre} » doit avoir un fichier.")

                    DocumentPrestataire.objects.create(
                        prestataire=p,
                        type_document="autre",
                        titre=titre,
                        fichier=file_obj,
                        date_emission=_parse_date(autres_emis[idx] if idx < len(autres_emis) else ""),
                        date_expiration=_parse_date(autres_exp[idx] if idx < len(autres_exp) else ""),
                        description=(autres_desc[idx] if idx < len(autres_desc) else "").strip(),
                        actif=True,
                    )

                # ✅ 3) Agents (illimité)
                agent_noms = request.POST.getlist("agent_nom[]")
                agent_prenoms = request.POST.getlist("agent_prenom[]")
                agent_tels = request.POST.getlist("agent_telephone[]")
                agent_emails = request.POST.getlist("agent_email[]")
                agent_fonctions = request.POST.getlist("agent_fonction[]")
                agent_matricules = request.POST.getlist("agent_matricule[]")

                # ✅ checkbox fiable par ligne (hidden + checkbox)
                agent_actifs = request.POST.getlist("agent_actif_val[]")  # "0" ou "1"

                for i, nom_agent in enumerate(agent_noms):
                    nom_agent = (nom_agent or "").strip()
                    prenom = (agent_prenoms[i] if i < len(agent_prenoms) else "").strip()
                    tel = (agent_tels[i] if i < len(agent_tels) else "").strip()
                    email = (agent_emails[i] if i < len(agent_emails) else "").strip()
                    fonction = (agent_fonctions[i] if i < len(agent_fonctions) else "").strip()
                    matricule = (agent_matricules[i] if i < len(agent_matricules) else "").strip()
                    actif_val = agent_actifs[i] if i < len(agent_actifs) else "1"
                    actif_agent = (actif_val == "1")

                    # ignore lignes totalement vides
                    if not nom_agent and not tel and not email and not fonction and not matricule:
                        continue

                    if not nom_agent:
                        raise ValueError("Chaque agent doit avoir au moins un nom.")

                    AgentPrestataire.objects.create(
                        prestataire=p,
                        nom=nom_agent,
                        prenom=prenom,
                        telephone=tel,
                        email=email,
                        fonction=fonction,
                        matricule=matricule,
                        actif=actif_agent,
                    )

        except (IntegrityError, ValueError) as e:
            messages.error(request, str(e) if isinstance(e, ValueError) else "Erreur : doublon ou contrainte DB.")
            return render(request, "prestataire/form_prestataire.html", {
                "titre": "Nouveau prestataire",
                "domaines": domaines,
                "data": data,
            })

        messages.success(request, "Prestataire créé (documents + agents enregistrés si fournis).")
        return redirect("prestataire:liste")

    return render(request, "prestataire/form_prestataire.html", {
        "titre": "Nouveau prestataire",
        "domaines": domaines,
        "data": data,
    })

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from datetime import datetime

from .models import (
    Prestataire, DomaineIntervention, DocumentPrestataire,
    AgentPrestataire,  # ✅ ajoute ceci
)

def _parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@login_required
def prestataire_modifier(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    prestataire = get_object_or_404(Prestataire, pk=pk, organisation=org)
    domaines = DomaineIntervention.objects.filter(organisation=org, actif=True).order_by("nom")

    documents = DocumentPrestataire.objects.filter(prestataire=prestataire).order_by("-date_upload")
    agents = AgentPrestataire.objects.filter(prestataire=prestataire).order_by("nom", "prenom")

    data = {
        "nom": prestataire.nom or "",
        "telephone": prestataire.telephone or "",
        "email": prestataire.email or "",
        "adresse": prestataire.adresse or "",
        "actif": prestataire.actif,
        "domaine_id": str(prestataire.domaine_id or ""),
    }

    if request.method == "POST":
        # -------- Prestataire fields --------
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["telephone"] = (request.POST.get("telephone") or "").strip()
        data["email"] = (request.POST.get("email") or "").strip()
        data["adresse"] = (request.POST.get("adresse") or "").strip()
        data["actif"] = (request.POST.get("actif") == "on")
        data["domaine_id"] = (request.POST.get("domaine") or "").strip()

        if not data["nom"]:
            messages.error(request, "Le nom du prestataire est obligatoire.")
            return render(request, "prestataire/modifier_prestataire.html", {
                "titre": "Modifier prestataire",
                "prestataire": prestataire,
                "domaines": domaines,
                "documents": documents,
                "agents": agents,
                "data": data,
            })

        # Domaine (optionnel car null=True)
        domaine = None
        if data["domaine_id"]:
            domaine = domaines.filter(id=data["domaine_id"]).first()
            if not domaine:
                messages.error(request, "Domaine invalide.")
                return render(request, "prestataire/modifier_prestataire.html", {
                    "titre": "Modifier prestataire",
                    "prestataire": prestataire,
                    "domaines": domaines,
                    "documents": documents,
                    "agents": agents,
                    "data": data,
                })

        # Unicité par organisation (exclure l'objet courant)
        if Prestataire.objects.filter(organisation=org, nom__iexact=data["nom"]).exclude(pk=prestataire.pk).exists():
            messages.error(request, "Un autre prestataire avec ce nom existe déjà.")
            return render(request, "prestataire/modifier_prestataire.html", {
                "titre": "Modifier prestataire",
                "prestataire": prestataire,
                "domaines": domaines,
                "documents": documents,
                "agents": agents,
                "data": data,
            })

        try:
            with transaction.atomic():
                # =============== Update prestataire ===============
                prestataire.nom = data["nom"]
                prestataire.telephone = data["telephone"]
                prestataire.email = data["email"]
                prestataire.adresse = data["adresse"]
                prestataire.actif = data["actif"]
                prestataire.domaine = domaine
                prestataire.save()

                # =============== DOCS (ton code inchangé) ===============
                delete_ids = request.POST.getlist("doc_delete_ids[]")
                if delete_ids:
                    DocumentPrestataire.objects.filter(prestataire=prestataire, id__in=delete_ids).delete()

                doc_ids = request.POST.getlist("doc_id[]")
                for doc_id in doc_ids:
                    doc = DocumentPrestataire.objects.filter(prestataire=prestataire, id=doc_id).first()
                    if not doc:
                        continue

                    type_doc = (request.POST.get(f"doc_type_{doc_id}") or "").strip()
                    titre = (request.POST.get(f"doc_titre_{doc_id}") or "").strip()
                    desc = (request.POST.get(f"doc_desc_{doc_id}") or "").strip()
                    date_em = _parse_date(request.POST.get(f"doc_date_em_{doc_id}") or "")
                    date_ex = _parse_date(request.POST.get(f"doc_date_ex_{doc_id}") or "")
                    actif_doc = (request.POST.get(f"doc_actif_{doc_id}") == "on")

                    if type_doc not in ("immatriculation", "niu", "autre"):
                        type_doc = doc.type_document

                    doc.type_document = type_doc
                    if type_doc == "autre":
                        doc.titre = titre
                    doc.description = desc
                    doc.date_emission = date_em
                    doc.date_expiration = date_ex
                    doc.actif = actif_doc

                    new_file = request.FILES.get(f"doc_file_{doc_id}")
                    if new_file:
                        doc.fichier = new_file

                    doc.save()

                imm_new = request.FILES.get("imm_new_file")
                if imm_new:
                    DocumentPrestataire.objects.create(
                        prestataire=prestataire,
                        type_document="immatriculation",
                        fichier=imm_new,
                        date_emission=_parse_date(request.POST.get("imm_new_date_em") or ""),
                        date_expiration=_parse_date(request.POST.get("imm_new_date_ex") or ""),
                        description=(request.POST.get("imm_new_desc") or "").strip(),
                        actif=(request.POST.get("imm_new_actif") == "on"),
                    )

                niu_new = request.FILES.get("niu_new_file")
                if niu_new:
                    DocumentPrestataire.objects.create(
                        prestataire=prestataire,
                        type_document="niu",
                        fichier=niu_new,
                        date_emission=_parse_date(request.POST.get("niu_new_date_em") or ""),
                        date_expiration=_parse_date(request.POST.get("niu_new_date_ex") or ""),
                        description=(request.POST.get("niu_new_desc") or "").strip(),
                        actif=(request.POST.get("niu_new_actif") == "on"),
                    )

                autres_titres = request.POST.getlist("autre_new_titre[]")
                autres_desc = request.POST.getlist("autre_new_desc[]")
                autres_em = request.POST.getlist("autre_new_date_em[]")
                autres_ex = request.POST.getlist("autre_new_date_ex[]")
                autres_files = request.FILES.getlist("autre_new_file[]")

                for idx, titre in enumerate(autres_titres):
                    titre = (titre or "").strip()
                    file_obj = autres_files[idx] if idx < len(autres_files) else None
                    if not titre and not file_obj:
                        continue
                    if not file_obj:
                        raise ValueError("Un document 'Autre' doit avoir un fichier.")
                    DocumentPrestataire.objects.create(
                        prestataire=prestataire,
                        type_document="autre",
                        titre=titre,
                        fichier=file_obj,
                        date_emission=_parse_date(autres_em[idx] if idx < len(autres_em) else ""),
                        date_expiration=_parse_date(autres_ex[idx] if idx < len(autres_ex) else ""),
                        description=(autres_desc[idx] if idx < len(autres_desc) else "").strip(),
                        actif=True,
                    )

                # =============== ✅ AGENTS : delete / update / add ===============

                # 1) Supprimer des agents
                agent_delete_ids = request.POST.getlist("agent_delete_ids[]")
                if agent_delete_ids:
                    AgentPrestataire.objects.filter(prestataire=prestataire, id__in=agent_delete_ids).delete()

                # 2) Mettre à jour agents existants
                agent_ids = request.POST.getlist("agent_id[]")
                for agent_id in agent_ids:
                    a = AgentPrestataire.objects.filter(prestataire=prestataire, id=agent_id).first()
                    if not a:
                        continue

                    nom = (request.POST.get(f"agent_nom_{agent_id}") or "").strip()
                    prenom = (request.POST.get(f"agent_prenom_{agent_id}") or "").strip()
                    tel = (request.POST.get(f"agent_tel_{agent_id}") or "").strip()
                    email = (request.POST.get(f"agent_email_{agent_id}") or "").strip()
                    fonction = (request.POST.get(f"agent_fonction_{agent_id}") or "").strip()
                    matricule = (request.POST.get(f"agent_matricule_{agent_id}") or "").strip()
                    actif_val = (request.POST.get(f"agent_actif_{agent_id}") or "0")
                    actif = (actif_val == "1")

                    if not nom:
                        raise ValueError("Un agent existant ne peut pas avoir un nom vide (supprime-le si nécessaire).")

                    a.nom = nom
                    a.prenom = prenom
                    a.telephone = tel
                    a.email = email
                    a.fonction = fonction
                    a.matricule = matricule
                    a.actif = actif
                    a.save()

                # 3) Ajouter nouveaux agents (illimité)
                new_noms = request.POST.getlist("agent_new_nom[]")
                new_prenoms = request.POST.getlist("agent_new_prenom[]")
                new_tels = request.POST.getlist("agent_new_telephone[]")
                new_emails = request.POST.getlist("agent_new_email[]")
                new_fonctions = request.POST.getlist("agent_new_fonction[]")
                new_matricules = request.POST.getlist("agent_new_matricule[]")
                new_actifs = request.POST.getlist("agent_new_actif_val[]")  # "0" / "1"

                for i, nom in enumerate(new_noms):
                    nom = (nom or "").strip()
                    prenom = (new_prenoms[i] if i < len(new_prenoms) else "").strip()
                    tel = (new_tels[i] if i < len(new_tels) else "").strip()
                    email = (new_emails[i] if i < len(new_emails) else "").strip()
                    fonction = (new_fonctions[i] if i < len(new_fonctions) else "").strip()
                    matricule = (new_matricules[i] if i < len(new_matricules) else "").strip()
                    actif_val = new_actifs[i] if i < len(new_actifs) else "1"
                    actif = (actif_val == "1")

                    # ignore lignes vides
                    if not nom and not tel and not email and not fonction and not matricule:
                        continue
                    if not nom:
                        raise ValueError("Chaque nouvel agent doit avoir un nom.")

                    AgentPrestataire.objects.create(
                        prestataire=prestataire,
                        nom=nom,
                        prenom=prenom,
                        telephone=tel,
                        email=email,
                        fonction=fonction,
                        matricule=matricule,
                        actif=actif,
                    )

        except ValueError as e:
            messages.error(request, str(e))
            documents = DocumentPrestataire.objects.filter(prestataire=prestataire).order_by("-date_upload")
            agents = AgentPrestataire.objects.filter(prestataire=prestataire).order_by("nom", "prenom")
            return render(request, "prestataire/modifier_prestataire.html", {
                "titre": "Modifier prestataire",
                "prestataire": prestataire,
                "domaines": domaines,
                "documents": documents,
                "agents": agents,
                "data": data,
            })

        messages.success(request, "Prestataire, documents et agents mis à jour.")
        return redirect("prestataire:liste")

    return render(request, "prestataire/modifier_prestataire.html", {
        "titre": "Modifier prestataire",
        "prestataire": prestataire,
        "domaines": domaines,
        "documents": documents,
        "agents": agents,
        "data": data,
    })


@login_required
def prestataire_supprimer(request, pk):
    obj = get_object_or_404(Prestataire, pk=pk, organisation=request.user.organisation)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Prestataire supprimé.")
        return redirect("prestataire:liste")

    return render(request, "prestataire/supprimer.html", {"objet": obj})


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Prestataire, DocumentPrestataire, AgentPrestataire  # ✅ AgentPrestataire
# Affectations viennent de l'app sites
from sites.models import AffectationPrestataire


@login_required
def prestataire_detail(request, pk):
    org = getattr(request.user, "organisation", None)
    if not org:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("core:accueil")

    prestataire = get_object_or_404(
        Prestataire.objects.select_related("domaine"),
        pk=pk,
        organisation=org
    )

    # Documents
    documents = (
        DocumentPrestataire.objects
        .filter(prestataire=prestataire)
        .order_by("-date_upload")
    )

    # Agents
    agents = (
        AgentPrestataire.objects
        .filter(prestataire=prestataire)
        .order_by("nom", "prenom")
    )

    # Affectations (Sites + Zones)
    affectations = (
        AffectationPrestataire.objects
        .filter(prestataire=prestataire)
        .select_related("site")
        .prefetch_related("zones")
        .order_by("-cree_le")
    )

    # KPI rapides
    kpi_docs = documents.count()
    kpi_agents = agents.count()
    kpi_affect = affectations.count()

    return render(request, "prestataire/detail.html", {
        "organisation": org,
        "prestataire": prestataire,
        "documents": documents,
        "agents": agents,
        "affectations": affectations,
        "kpi": {
            "docs": kpi_docs,
            "agents": kpi_agents,
            "affectations": kpi_affect,
        }
    })


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages


@login_required
def home_router(request):
    # ✅ superadmin => admin Django
    if request.user.is_superuser:
        return redirect("/admin/")

    # ✅ tout le reste => dashboard core
    return redirect("core:accueil")

@login_required
def accueil(request):
    # superuser : accès plateforme
    if request.user.is_superuser:
        return render(request, "core/accueil_superadmin.html")

    # users normaux : organisation obligatoire
    if not request.user.organisation:
        messages.error(request, "Votre compte n'est lié à aucune organisation.")
        return redirect("/accounts/logout/")

    org = request.user.organisation

    modules = [
        {"titre": "Gestion des prestataires externes", 
         "desc": "Suivi, contrats, interventions, conformité.", 
         "icone": "👷", 
         "url": "prestataire:liste" },

        {"titre": "Formations & Habilitations", 
         "desc": "Échéances, rappels, documents, validations.", 
         "icone": "🎓", 
         "url": "permis:form-hab"},

        {"titre": "Permis et autorisations de travail", 
         "desc": "PTW, validations, workflow, archivage.", 
         "icone": "📝", 
         "url": "permis:dashboard_permis_interventions" },

        {"titre": "Contrôles et inspections de sécurité", 
         "desc": "Checklists, scores, historique, preuves.", 
         "icone": "✅", 
         "url": "inspections:dashboard_inspections"},

        {"titre": "Suivi incendie et prévention des risques", 
         "desc": "Rondes, matériels incendie, plans, audits.", 
         "icone": "🔥", 
         "url": "incendie:dashboard"},
       
        {"titre": "Déclaration d’incidents, accidents et plans d’action", 
         "desc": "Signalement, analyse, actions, délais.", 
         "icone": "⚠️", 
         "url": "evenements:dashboard_evenement"},

        # ✅ NOUVEAU MODULE AJOUTÉ ICI
        {"titre": "Gestion des documents & maîtrise documentaire", 
         "desc": "Versions, validations, diffusion contrôlée, traçabilité ISO.", 
         "icone": "📂", 
         "url": "documentaire:list"},

        {"titre": "Rapports automatiques & tableaux de bord QHSSE", 
        "desc": "KPIs, exports PDF, synthèses, tendances.", 
        "icone": "📊", 
        "url": "rapport:dashboard_kpi"},

        {"titre": "Paramètres & Administration", 
         "desc": "Organisation, sites, zones, utilisateurs.", 
         "icone": "⚙️", 
         "url": ""},
    ]

    return render(request, "core/accueil.html", {
        "organisation": org,
        "modules": modules,
    })

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

from organisations.models import Organisation
from abonnements.models import Abonnement

User = get_user_model()

def superadmin_requis(view_func):
    def _wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/accounts/login/")
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé au super administrateur.")
            return redirect("core:accueil")
        return view_func(request, *args, **kwargs)
    return _wrap


@superadmin_requis
def plateforme_dashboard(request):
    organisations = Organisation.objects.all().order_by("-id")
    abonnements = Abonnement.objects.select_related("organisation").all().order_by("-id")[:30]
    return render(request, "core/plateforme_dashboard.html", {
        "organisations": organisations,
        "abonnements": abonnements,
    })


@superadmin_requis
def organisation_creer(request):
    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        if not nom:
            messages.error(request, "Nom obligatoire.")
            return redirect("core:organisation_creer")

        Organisation.objects.create(nom=nom)
        messages.success(request, "Organisation créée.")
        return redirect("core:plateforme_dashboard")

    return render(request, "core/organisation_form.html")


@superadmin_requis
def abonnement_creer(request):
    if request.method == "POST":
        org_id = request.POST.get("organisation_id")
        plan = (request.POST.get("plan") or "basic").strip()
        actif = (request.POST.get("actif") == "on")

        org = get_object_or_404(Organisation, id=org_id)
        Abonnement.objects.create(organisation=org, plan=plan, actif=actif)
        messages.success(request, "Abonnement créé.")
        return redirect("core:plateforme_dashboard")

    organisations = Organisation.objects.all().order_by("nom")
    return render(request, "core/abonnement_form.html", {"organisations": organisations})

############################ Mis en place d'une plateforme pour gerer les Organisation et autres

@superadmin_requis
def admin_org_creer(request):
    if request.method == "POST":
        org_id = request.POST.get("organisation_id")
        phone = (request.POST.get("phone_number") or "").strip()
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""

        if not phone.isdigit() or len(phone) != 9:
            messages.error(request, "Téléphone invalide : 9 chiffres.")
            return redirect("core:admin_org_creer")

        if password1 != password2 or len(password1) < 6:
            messages.error(request, "Mot de passe invalide (min 6) ou non identique.")
            return redirect("core:admin_org_creer")

        org = get_object_or_404(Organisation, id=org_id)

        if User.objects.filter(phone_number=phone).exists():
            messages.error(request, "Ce numéro existe déjà.")
            return redirect("core:admin_org_creer")

        User.objects.create(
            phone_number=phone,
            organisation=org,
            role="admin_org",
            password=make_password(password1),
            is_active=True,
        )
        messages.success(request, "Admin organisation créé.")
        return redirect("core:plateforme_dashboard")

    organisations = Organisation.objects.all().order_by("nom")
    return render(request, "core/admin_org_form.html", {"organisations": organisations})



from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404

from abonnements.decorators import abonnement_requis
from prestataire.models import Prestataire
from .models import Site, Zone, AffectationPrestataire

@login_required
def site_liste(request):
    sites = Site.objects.filter(organisation=request.user.organisation).order_by("nom")
    return render(request, "sites/site_list.html", {"sites": sites})



@login_required
@abonnement_requis
def site_creer(request):

    org = request.user.organisation
    abo = org.abonnement

    nb_sites = Site.objects.filter(organisation=org).count()

    # Vérifier la limite du plan
    if nb_sites >= abo.plan.max_sites:
        messages.error(
            request,
            f"Limite atteinte : votre plan autorise {abo.plan.max_sites} site(s)."
        )
        return redirect("sites:liste")


    # Valeurs par défaut
    data = {
        "nom": "",
        "adresse": "",
        "actif": True,
    }


    # Si POST → récupérer les valeurs
    if request.method == "POST":

        data["nom"] = (request.POST.get("nom") or "").strip()
        data["adresse"] = (request.POST.get("adresse") or "").strip()
        data["actif"] = True if request.POST.get("actif") == "on" else False


        # Validation
        if not data["nom"]:
            messages.error(request, "Le nom du site est obligatoire.")
            return render(
                request,
                "sites/site_form.html",
                {
                    "titre": "Créer un site",
                    "organisation": org,
                    "data": data,
                }
            )


        # Création
        try:

            site = Site.objects.create(
                organisation=org,
                nom=data["nom"],
                adresse=data["adresse"],
                actif=data["actif"],
            )

            messages.success(request, "Site créé avec succès.")

            return redirect("sites:liste")


        except IntegrityError:

            messages.error(
                request,
                "Un site avec ce nom existe déjà dans cette organisation."
            )

            return render(
                request,
                "sites/site_form.html",
                {
                    "titre": "Créer un site",
                    "organisation": org,
                    "data": data,
                }
            )


    # GET → afficher formulaire vide
    return render(
        request,
        "sites/site_form.html",
        {
            "titre": "Créer un site",
            "organisation": org,
            "data": data,
        }
    )


@login_required
def site_detail(request, pk):
    site = get_object_or_404(Site, pk=pk, organisation=request.user.organisation)
    zones = site.zones.order_by("nom")
    affectations = site.affectations.select_related("prestataire").order_by("prestataire__nom")
    return render(request, "sites/detail.html", {"site": site, "zones": zones, "affectations": affectations})

@login_required
@abonnement_requis
def zone_creer(request, site_pk):
    org = request.user.organisation

    site = get_object_or_404(Site, pk=site_pk, organisation=org)

    data = {"nom": "", "actif": True}

    if request.method == "POST":
        data["nom"] = (request.POST.get("nom") or "").strip()
        data["actif"] = True if request.POST.get("actif") == "on" else False

        if not data["nom"]:
            messages.error(request, "Le nom de la zone est obligatoire.")
            return render(request, "sites/zone_form.html", {
                "titre": "Nouvelle zone",
                "organisation": org,
                "site": site,
                "data": data,
            })

        try:
            Zone.objects.create(site=site, nom=data["nom"], actif=data["actif"])
            messages.success(request, "Zone créée.")
            return redirect("sites:zone_liste", site_pk=site.pk)  # adapte au name de ta route
        except IntegrityError:
            messages.error(request, "Une zone avec ce nom existe déjà pour ce site.")
            return render(request, "sites/zone_form.html", {
                "titre": "Nouvelle zone",
                "organisation": org,
                "site": site,
                "data": data,
            })

    return render(request, "sites/zone_form.html", {
        "titre": "Nouvelle zone",
        "organisation": org,
        "site": site,
        "data": data,
    })


@login_required
@abonnement_requis
def zone_liste(request, site_pk):

    org = request.user.organisation

    site = get_object_or_404(
        Site,
        pk=site_pk,
        organisation=org
    )

    zones = Zone.objects.filter(site=site).order_by("nom")

    return render(request,
                  "sites/zone_list.html",
                  {
                      "organisation": org,
                      "site": site,
                      "zones": zones
                  })


@login_required
def affectation_creer(request, site_pk):
    site = get_object_or_404(Site, pk=site_pk, organisation=request.user.organisation)

    prestataires = Prestataire.objects.filter(
        organisation=request.user.organisation, actif=True
    ).order_by("nom")
    zones = site.zones.filter(actif=True).order_by("nom")

    if request.method == "POST":
        prestataire_id = request.POST.get("prestataire_id")
        zones_ids = request.POST.getlist("zones_ids")  # peut être vide
        actif = True if request.POST.get("actif") == "on" else False

        if not prestataire_id:
            messages.error(request, "Choisis un prestataire.")
            return redirect("sites:affectation_creer", site_pk=site.pk)

        prestataire = get_object_or_404(
            Prestataire, pk=prestataire_id, organisation=request.user.organisation
        )

        try:
            with transaction.atomic():
                aff, created = AffectationPrestataire.objects.get_or_create(
                    site=site,
                    prestataire=prestataire,
                    defaults={"actif": actif},
                )
                if not created:
                    # si déjà existante, on met à jour
                    aff.actif = actif
                    aff.zones.clear()

                # Validation : zones doivent appartenir au site
                if zones_ids:
                    zones_ok = Zone.objects.filter(site=site, id__in=zones_ids)
                    if zones_ok.count() != len(zones_ids):
                        messages.error(request, "Certaines zones sont invalides.")
                        return redirect("sites:affectation_creer", site_pk=site.pk)
                    aff.save()
                    aff.zones.add(*zones_ok)
                else:
                    # vide => tout le site
                    aff.save()

            messages.success(request, "Affectation enregistrée.")
            return redirect("sites:detail", pk=site.pk)

        except IntegrityError:
            messages.error(request, "Erreur lors de l'enregistrement.")
            return redirect("sites:affectation_creer", site_pk=site.pk)

    return render(
        request,
        "sites/form_affectation.html",
        {"titre": f"Affecter un prestataire — {site.nom}", "site": site, "prestataires": prestataires, "zones": zones},
    )

@login_required
def affectation_supprimer(request, pk):
    aff = get_object_or_404(AffectationPrestataire, pk=pk, site__organisation=request.user.organisation)
    site_id = aff.site_id

    if request.method == "POST":
        aff.delete()
        messages.success(request, "Affectation supprimée.")
        return redirect("sites:detail", pk=site_id)

    return render(request, "sites/supprimer.html", {"objet": aff})

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from .models import Site, Zone, AffectationPrestataire


@login_required
def affectation_modifier(request, pk):
    aff = get_object_or_404(
        AffectationPrestataire,
        pk=pk,
        site__organisation=request.user.organisation
    )
    site = aff.site

    if request.method != "POST":
        return redirect("sites:affectations", site_pk=site.pk)

    zones_ids = request.POST.getlist("zones_ids")  # peut être vide => tout le site
    actif = True if request.POST.get("actif") == "on" else False

    try:
        with transaction.atomic():
            aff.actif = actif
            aff.zones.clear()

            if zones_ids:
                zones_ok = Zone.objects.filter(site=site, id__in=zones_ids)
                if zones_ok.count() != len(zones_ids):
                    messages.error(request, "Certaines zones sont invalides.")
                    return redirect("sites:affectations", site_pk=site.pk)
                aff.save()
                aff.zones.add(*zones_ok)
            else:
                # vide => tout le site
                aff.save()

        messages.success(request, "Affectation mise à jour.")
    except Exception:
        messages.error(request, "Erreur lors de la mise à jour.")

    return redirect("sites:affectations", site_pk=site.pk)


@login_required
def affectations_page(request, site_pk):
    site = get_object_or_404(Site, pk=site_pk, organisation=request.user.organisation)

    prestataires = Prestataire.objects.filter(
        organisation=request.user.organisation, actif=True
    ).order_by("nom")

    zones = site.zones.filter(actif=True).order_by("nom")

    affectations = (
        site.affectations
        .select_related("prestataire")
        .prefetch_related("zones")
        .order_by("prestataire__nom")
    )

    return render(request, "sites/affectations.html", {
        "titre": f"Affectations — {site.nom}",
        "site": site,
        "prestataires": prestataires,
        "zones": zones,
        "affectations": affectations,
    })

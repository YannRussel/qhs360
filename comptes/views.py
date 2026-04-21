from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect

User = get_user_model()

def admin_org_only(request):
    return request.user.is_authenticated and (request.user.role == "admin_org") and (request.user.organisation is not None)

def utilisateur_creer(request):
    if not admin_org_only(request):
        return redirect("core:accueil")

    org = request.user.organisation

    if request.method == "POST":
        phone = (request.POST.get("phone_number") or "").strip()
        role = request.POST.get("role") or "agent"
        pwd1 = request.POST.get("password1") or ""
        pwd2 = request.POST.get("password2") or ""

        if not phone.isdigit() or len(phone) != 9:
            messages.error(request, "Téléphone invalide : 9 chiffres obligatoires.")
            return redirect("comptes:creer")

        if pwd1 != pwd2 or len(pwd1) < 6:
            messages.error(request, "Mot de passe invalide (min 6) ou non identique.")
            return redirect("comptes:creer")

        if User.objects.filter(phone_number=phone).exists():
            messages.error(request, "Ce numéro existe déjà.")
            return redirect("comptes:creer")

        User.objects.create(
            phone_number=phone,
            role=role,
            organisation=org,               # ✅ auto
            password=make_password(pwd1),
            is_active=True,
        )
        messages.success(request, "Utilisateur créé et lié à l'organisation.")
        return redirect("comptes:liste")

    return render(request, "comptes/utilisateur_form.html", {"organisation": org})

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def abonnement_detail(request):
    org = request.user.organisation
    abo = getattr(org, "abonnement", None)
    return render(request, "abonnements/detail.html", {"abonnement": abo})

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def organisation_detail(request):
    org = getattr(request.user, "organisation", None)
    return render(request, "organisations/detail.html", {"organisation": org})

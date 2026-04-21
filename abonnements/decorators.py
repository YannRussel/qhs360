from django.contrib import messages
from django.shortcuts import redirect

def abonnement_requis(view_func):
    def _wrapped(request, *args, **kwargs):
        org = getattr(request.user, "organisation", None)
        if not org:
            messages.error(request, "Votre compte n'est lié à aucune organisation.")
            return redirect("organisations:detail")

        abo = getattr(org, "abonnement", None)
        if not abo or not abo.est_valide():
            messages.error(request, "Abonnement inactif ou expiré.")
            return redirect("abonnements:detail")

        return view_func(request, *args, **kwargs)
    return _wrapped

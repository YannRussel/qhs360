from django.db import models

class Organisation(models.Model):
    nom = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom

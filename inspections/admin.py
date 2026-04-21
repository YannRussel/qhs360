from django.contrib import admin
from .models import (
    InspectionTemplate, InspectionSection, InspectionQuestion,
    Inspection, InspectionResponse, InspectionPhoto,
    NonConformity, CorrectiveAction
)

class InspectionQuestionInline(admin.TabularInline):
    model = InspectionQuestion
    extra = 0

class InspectionSectionInline(admin.TabularInline):
    model = InspectionSection
    extra = 0

@admin.register(InspectionTemplate)
class InspectionTemplateAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisation", "version", "actif", "required_for_deployment", "created_at")
    search_fields = ("nom",)
    prepopulated_fields = {"slug": ("nom",)}
    inlines = [InspectionSectionInline]

@admin.register(InspectionSection)
class InspectionSectionAdmin(admin.ModelAdmin):
    list_display = ("template", "ordre", "titre")
    inlines = [InspectionQuestionInline]

@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("reference", "organisation", "site", "zone", "date", "status", "score")
    list_filter = ("status", "organisation", "site")
    search_fields = ("reference", "notes")

admin.site.register(InspectionResponse)
admin.site.register(InspectionPhoto)
admin.site.register(NonConformity)
admin.site.register(CorrectiveAction)

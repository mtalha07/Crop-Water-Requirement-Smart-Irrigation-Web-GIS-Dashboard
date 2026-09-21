from django.contrib import admin
from .models import Pole


@admin.register(Pole)
class PoleAdmin(admin.ModelAdmin):
    list_display = ("pole_survey_number", "latitude", "longitude")
    search_fields = ("pole_survey_number",)


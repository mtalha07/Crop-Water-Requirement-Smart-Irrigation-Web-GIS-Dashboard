from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Pole(models.Model):
    """Synthetic demonstration point stored in ordinary SQLite columns."""
    pole_id = models.BigAutoField(primary_key=True)
    pole_survey_number = models.CharField(max_length=30, unique=True)
    latitude = models.FloatField(validators=[
        MinValueValidator(-90), MaxValueValidator(90),
    ])
    longitude = models.FloatField(validators=[
        MinValueValidator(-180), MaxValueValidator(180),
    ])
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["pole_id"]

    def __str__(self):
        return self.pole_survey_number


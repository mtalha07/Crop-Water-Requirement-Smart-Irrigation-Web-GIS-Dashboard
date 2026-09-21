from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Pole",
            fields=[
                ("pole_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("pole_survey_number", models.CharField(max_length=30, unique=True)),
                ("latitude", models.FloatField(validators=[
                    django.core.validators.MinValueValidator(-90),
                    django.core.validators.MaxValueValidator(90),
                ])),
                ("longitude", models.FloatField(validators=[
                    django.core.validators.MinValueValidator(-180),
                    django.core.validators.MaxValueValidator(180),
                ])),
                ("description", models.CharField(blank=True, max_length=200)),
            ],
            options={"ordering": ["pole_id"]},
        ),
    ]


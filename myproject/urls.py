from django.contrib import admin
from django.urls import path
from backend import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("required_water/", views.calculate_water, name="required_water"),
    path("api/spatial-data/", views.fetch_spatial_data, name="fetch_spatial_data"),
]


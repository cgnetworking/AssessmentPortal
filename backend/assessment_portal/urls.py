from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("social_django.urls", namespace="social")),
    path("api/", include("assessments.urls")),
]

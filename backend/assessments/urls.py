from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/session/", views.auth_session, name="auth-session"),
    path("auth/logout/", views.auth_logout, name="auth-logout"),
    path("summary/", views.dashboard_summary, name="dashboard-summary"),
    path("tenants/", views.tenant_collection, name="tenant-collection"),
    path("tenants/<uuid:tenant_id>/", views.tenant_detail, name="tenant-detail"),
    path("tenants/<uuid:tenant_id>/certificate/", views.tenant_certificate, name="tenant-certificate"),
    path("tenants/<uuid:tenant_id>/certificate/download/", views.tenant_certificate_download, name="tenant-certificate-download"),
    path("runs/", views.run_collection, name="run-collection"),
    path("runs/<uuid:run_id>/", views.run_detail, name="run-detail"),
    path("audit-log/", views.audit_log, name="audit-log"),
]

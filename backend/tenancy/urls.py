from django.urls import path

from .views import (
    BrandingView,
    DomainListCreateView,
    MemberListCreateView,
    PlanListCreateView,
    TenantDetailView,
    TenantListCreateView,
    TenantSubscriptionView,
)

urlpatterns = [
    path("branding", BrandingView.as_view()),
    path("plans", PlanListCreateView.as_view()),
    path("tenants", TenantListCreateView.as_view()),
    path("tenants/<uuid:pk>", TenantDetailView.as_view()),
    path("tenants/<uuid:tenant_id>/subscription", TenantSubscriptionView.as_view()),
    path("members", MemberListCreateView.as_view()),
    path("domains", DomainListCreateView.as_view()),
]

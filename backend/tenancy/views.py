from django.db import transaction
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsPlatformAdmin, IsTenantAdmin

from .models import SubscriptionPlan, Tenant, TenantDomain, TenantSubscription
from .serializers import (
    CompanyProvisionSerializer,
    DomainSerializer,
    MemberSerializer,
    PlanSerializer,
    SubscriptionSerializer,
    TenantSerializer,
)


class BrandingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"name": "FX", "branding": {}, "features": {}})
        return Response(
            {
                "name": tenant.name,
                "slug": tenant.slug,
                "support_email": tenant.support_email,
                "branding": tenant.branding,
                "features": tenant.features,
            }
        )


def request_tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class PlanListCreateView(generics.ListCreateAPIView):
    serializer_class = PlanSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = SubscriptionPlan.objects.all().order_by("monthly_price")


class TenantListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = (
        Tenant.objects.select_related("subscription__plan").prefetch_related("domains").order_by("name")
    )


class TenantDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Tenant.objects.select_related("subscription__plan").prefetch_related("domains")


class CompanyProvisionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        serializer = CompanyProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        return Response(TenantSerializer(tenant).data, status=201)


class TenantSubscriptionView(APIView):
    permission_classes = [IsPlatformAdmin]

    @transaction.atomic
    def put(self, request, tenant_id):
        tenant = Tenant.objects.select_for_update().filter(pk=tenant_id).first()
        if not tenant:
            return Response({"detail": "Tenant not found"}, status=404)
        instance = TenantSubscription.objects.filter(tenant=tenant).first()
        serializer = SubscriptionSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=tenant)
        return Response(serializer.data)


class MemberListCreateView(generics.ListCreateAPIView):
    serializer_class = MemberSerializer
    permission_classes = [IsTenantAdmin]

    def get_tenant(self):
        tenant = request_tenant(self.request)
        if not tenant:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("No tenant context")
        return tenant

    def get_queryset(self):
        return (
            self.get_tenant()
            .memberships.select_related("user")
            .filter(is_active=True)
            .values_list("user_id", flat=True)
        )

    def list(self, request, *args, **kwargs):
        from core.models import User

        users = User.objects.filter(id__in=self.get_queryset()).order_by("first_name", "email")
        return Response(self.get_serializer(users, many=True).data)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self.get_tenant()
        return context

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        subscription = getattr(tenant, "subscription", None)
        active_members = tenant.memberships.filter(is_active=True).count()
        if subscription and active_members >= subscription.plan.client_limit:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("This company's client limit has been reached")
        serializer.save()


class DomainListCreateView(generics.ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = [IsTenantAdmin]

    def get_queryset(self):
        tenant = request_tenant(self.request)
        return TenantDomain.objects.filter(tenant=tenant).order_by("-is_primary", "hostname")

    def perform_create(self, serializer):
        serializer.save(tenant=request_tenant(self.request))

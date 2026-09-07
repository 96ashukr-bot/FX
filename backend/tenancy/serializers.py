from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import SubscriptionPlan, Tenant, TenantDomain, TenantMembership, TenantSubscription

User = get_user_model()


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    permits_trading = serializers.BooleanField(read_only=True)

    class Meta:
        model = TenantSubscription
        fields = ("id", "plan", "plan_code", "status", "starts_at", "ends_at", "metadata", "permits_trading")


class TenantSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(read_only=True)
    primary_domain = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = (
            "id",
            "name",
            "slug",
            "legal_name",
            "support_email",
            "timezone",
            "is_active",
            "features",
            "branding",
            "primary_domain",
            "subscription",
            "created_at",
        )

    def get_primary_domain(self, instance):
        domain = instance.domains.filter(is_primary=True).first()
        return domain.hostname if domain else None


class MemberSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10, required=False)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "tenant",
            "tenant_name",
            "password",
        )
        read_only_fields = ("id", "tenant", "tenant_name")

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        tenant = self.context["tenant"]
        user = User(**validated_data, tenant=tenant)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        TenantMembership.objects.create(tenant=tenant, user=user, role=user.role)
        return user

    def validate_role(self, value):
        if value not in {User.Role.CLIENT, User.Role.DEALER, User.Role.TENANT_ADMIN}:
            raise serializers.ValidationError("Only client, dealer, or tenant-admin members may be created")
        return value


class CompanyProvisionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    slug = serializers.SlugField()
    legal_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    support_email = serializers.EmailField(required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=64, default="UTC")
    admin_email = serializers.EmailField()
    admin_first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    admin_last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    admin_password = serializers.CharField(write_only=True, min_length=10)
    plan = serializers.PrimaryKeyRelatedField(queryset=SubscriptionPlan.objects.filter(is_active=True))
    subscription_days = serializers.IntegerField(min_value=1, max_value=3660, default=30)

    def validate(self, attrs):
        if Tenant.objects.filter(slug=attrs["slug"]).exists():
            raise serializers.ValidationError({"slug": "This company slug is already in use"})
        if User.objects.filter(email__iexact=attrs["admin_email"]).exists():
            raise serializers.ValidationError({"admin_email": "This email is already registered"})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from datetime import timedelta

        password = validated_data.pop("admin_password")
        admin_email = validated_data.pop("admin_email").lower()
        first_name = validated_data.pop("admin_first_name", "")
        last_name = validated_data.pop("admin_last_name", "")
        plan = validated_data.pop("plan")
        days = validated_data.pop("subscription_days")
        tenant = Tenant.objects.create(**validated_data)
        admin = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.TENANT_ADMIN,
            tenant=tenant,
        )
        TenantMembership.objects.create(tenant=tenant, user=admin, role=admin.role)
        now = timezone.now()
        TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.Status.ACTIVE,
            starts_at=now,
            ends_at=now + timedelta(days=days),
        )
        return tenant


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = ("id", "hostname", "is_primary", "is_verified", "certificate_status", "created_at")
        read_only_fields = ("is_verified", "certificate_status", "created_at")

from django.contrib.auth import get_user_model
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
            "password",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

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


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = ("id", "hostname", "is_primary", "is_verified", "certificate_status", "created_at")
        read_only_fields = ("is_verified", "certificate_status", "created_at")

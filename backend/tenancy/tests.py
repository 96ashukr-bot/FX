from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User

from .models import SubscriptionPlan, Tenant, TenantSubscription


class SaaSIsolationTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="platform",
            email="platform@example.com",
            password="secret-test-password",
            role=User.Role.PLATFORM_ADMIN,
        )
        self.tenant = Tenant.objects.create(name="Alpha FX", slug="alpha-fx")
        self.tenant_admin = User.objects.create_user(
            username="alpha-admin",
            email="admin@alpha.test",
            password="secret-test-password",
            role=User.Role.TENANT_ADMIN,
            tenant=self.tenant,
        )
        self.plan = SubscriptionPlan.objects.create(name="Starter", code="starter")
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.Status.ACTIVE,
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=30),
        )

    def test_tenant_admin_cannot_list_platform_tenants(self):
        client = APIClient()
        client.force_authenticate(self.tenant_admin)
        self.assertEqual(client.get("/api/v1/tenants").status_code, 403)

    def test_platform_admin_can_list_tenants(self):
        client = APIClient()
        client.force_authenticate(self.platform_admin)
        response = client.get("/api/v1/tenants")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["slug"], "alpha-fx")

    def test_current_user_reports_subscription(self):
        client = APIClient()
        client.force_authenticate(self.tenant_admin)
        response = client.get("/api/v1/me")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["subscription"]["permits_trading"])

    def test_platform_admin_provisions_complete_company(self):
        client = APIClient()
        client.force_authenticate(self.platform_admin)
        response = client.post(
            "/api/v1/companies/provision",
            {
                "name": "Bravo FX",
                "slug": "bravo-fx",
                "admin_email": "admin@bravo.test",
                "admin_password": "long-test-password",
                "plan": str(self.plan.id),
                "subscription_days": 45,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        tenant = Tenant.objects.get(slug="bravo-fx")
        self.assertTrue(tenant.subscription.permits_trading)
        admin = User.objects.get(email="admin@bravo.test")
        self.assertEqual(admin.tenant, tenant)
        self.assertEqual(admin.role, User.Role.TENANT_ADMIN)

from django.contrib import admin

from .models import Tenant, TenantDomain, TenantMembership

admin.site.register((Tenant, TenantDomain, TenantMembership))

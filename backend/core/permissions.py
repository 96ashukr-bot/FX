from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == request.user.Role.PLATFORM_ADMIN)


class IsTenantOperator(BasePermission):
    roles = {"PLATFORM_ADMIN", "TENANT_ADMIN", "DEALER"}

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role in self.roles)


class IsTenantAdmin(BasePermission):
    roles = {"PLATFORM_ADMIN", "TENANT_ADMIN"}

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role in self.roles)

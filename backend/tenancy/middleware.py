from .models import TenantDomain


class TenantResolutionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = request.get_host().split(":", 1)[0].lower()
        domain = (
            TenantDomain.objects.select_related("tenant")
            .filter(
                hostname=hostname,
                is_verified=True,
                tenant__is_active=True,
            )
            .first()
        )
        request.tenant = domain.tenant if domain else None
        return self.get_response(request)

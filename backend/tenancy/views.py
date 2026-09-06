from rest_framework.response import Response
from rest_framework.views import APIView


class BrandingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"name": "FX", "branding": {}, "features": {}})
        return Response({
            "name": tenant.name,
            "slug": tenant.slug,
            "support_email": tenant.support_email,
            "branding": tenant.branding,
            "features": tenant.features,
        })

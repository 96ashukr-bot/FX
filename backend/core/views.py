from django.db import connection
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok"})


class CurrentUserView(APIView):
    def get(self, request):
        tenant = getattr(request, "tenant", None) or request.user.tenant
        subscription = getattr(tenant, "subscription", None) if tenant else None
        return Response(
            {
                "id": request.user.id,
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "role": request.user.role,
                "tenant": ({"id": tenant.id, "name": tenant.name, "slug": tenant.slug} if tenant else None),
                "subscription": (
                    {
                        "status": subscription.status,
                        "plan": subscription.plan.code,
                        "starts_at": subscription.starts_at,
                        "ends_at": subscription.ends_at,
                        "permits_trading": subscription.permits_trading,
                    }
                    if subscription
                    else None
                ),
            }
        )

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/token", TokenObtainPairView.as_view()),
    path("api/v1/auth/refresh", TokenRefreshView.as_view()),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("tenancy.urls")),
    path("api/v1/", include("trading.urls")),
    path("api/v1/terminal/", include("terminal.urls")),
]

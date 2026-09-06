from django.urls import path

from .views import BrandingView

urlpatterns = [path("branding", BrandingView.as_view())]

from django.urls import path

from .views import CurrentUserView, health

urlpatterns = [path("health", health), path("me", CurrentUserView.as_view())]

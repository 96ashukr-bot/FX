from django.urls import path

from .views import CommandClaimView, EventIngestView, HeartbeatView, SnapshotView

urlpatterns = [
    path("commands/claim", CommandClaimView.as_view()),
    path("events", EventIngestView.as_view()),
    path("heartbeat", HeartbeatView.as_view()),
    path("snapshots", SnapshotView.as_view()),
]

from django.urls import path

from .views import (
    AgentDownloadView,
    CommandClaimView,
    EventIngestView,
    HeartbeatView,
    NodeProvisionView,
    SnapshotView,
)

urlpatterns = [
    path("nodes/provision", NodeProvisionView.as_view()),
    path("agents/<str:platform>/download", AgentDownloadView.as_view()),
    path("commands/claim", CommandClaimView.as_view()),
    path("events", EventIngestView.as_view()),
    path("heartbeat", HeartbeatView.as_view()),
    path("snapshots", SnapshotView.as_view()),
]

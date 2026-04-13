from django.urls import path
from django.views.generic import RedirectView

from apps.panel.views import monitor_view

from .views import panel

urlpatterns = [
    path("", RedirectView.as_view(url="/panel/timetable_update/", permanent=False)),
    path("login/", panel.admin_login, name="admin_login"),
    # API и страница мониторинга — под /panel/timetable_update/ (см. обсуждение в PR)
    path("timetable_update/stats/", monitor_view.monitoring_stats, name="monitoring_stats"),
    path(
        "timetable_update/download/<int:resource_id>/",
        monitor_view.download_resource,
        name="download_resource",
    ),
    path("timetable_update/settings/", panel.set_system_params, name="set_system_params"),
    path("timetable_update/manage_storage/", panel.manage_storage, name="manage_storage"),
    path("timetable_update/update_timetable/", panel.run_update_timetable, name="update_timetable"),
    path("timetable_update/", monitor_view.monitoring_panel, name="monitoring_panel"),
]

from django.urls import path

from apps.client import views
from apps.panel.views import monitor_view
from .views import panel

urlpatterns = [
    path("", panel.admin_panel, name="admin_panel"),
    path("login/", panel.admin_login, name="admin_login"),
    path("settings", panel.set_system_params, name="set_system_params"),
    path("manage_storage", panel.manage_storage, name="manage_storage"),
    path("update_timetable", panel.run_update_timetable, name="update_timetable"),
    path("monitor/", monitor_view.monitoring_panel, name="monitoring_panel"),
    path("monitor/stats", monitor_view.monitoring_stats, name="monitoring_stats"),
    path("monitor/download/<int:resource_id>/", monitor_view.download_resource, name="download_resource"),

]
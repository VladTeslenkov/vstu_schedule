from django.urls import path
from . import views

urlpatterns = [
    path("", views.admin_panel, name="admin_panel"),
    path("login/", views.admin_login, name="admin_login"),
    path("settings", views.set_system_params, name="set_system_params"),
    path("manage_storage", views.manage_storage, name="manage_storage"),
    path("update_timetable", views.run_update_timetable, name="update_timetable"),
]
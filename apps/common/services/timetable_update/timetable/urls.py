from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "timetable_choose_degree",
        views.timetable_choose_degree,
        name="timetable_choose_degree",
    ),
    path("exams_choose_degree", views.exams_choose_degree, name="exams_choose_degree"),
    path("timetable", views.timetable_list, name="timetable"),
    path("exams", views.timetable_list, name="exams"),
    path("timetable_params", views.timetable_params, name="timetable_params"),
    path("bells_timetable", views.bells_timetable, name="bells_timetable"),
    path("sports_timetable", views.sports_timetable, name="sports_timetable"),
    path("admin/", views.admin_panel, name="admin_panel"),
    path("login/", views.admin_login, name="admin_login"),
    path("admin/auth", views.put_google_auth_file, name="put_google_auth_file"),
    path("admin/settings", views.set_system_params, name="set_system_params"),
    path("admin/snapshot", views.snapshot, name="snapshot"),
    path("admin/manage_storage", views.manage_storage, name="manage_storage"),
    path("admin/update_timetable", views.update_timetable, name="update_timetable"),
]

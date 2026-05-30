"""
URL configuration for vstu_schedule project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.views.generic import RedirectView
from dmr.routing import path

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="schedule:index", permanent=True)),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("api/", include(("apps.api.urls", "api"), namespace="api")),
    path("schedule/", include(("apps.client.urls", "client"), namespace="schedule")),
    path("timetable/", RedirectView.as_view(pattern_name="schedule:index", permanent=False)),
    path("visualization/", RedirectView.as_view(pattern_name="schedule:index", permanent=False)),
    path("panel/", include("apps.panel.urls")),
    # Освободить корень проекта для включения остальных подсистем.
    # path('', include('apps.client.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "vstu_schedule.error_handlers.handler404"
handler500 = "vstu_schedule.error_handlers.handler500"

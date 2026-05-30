from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

PWA_STATIC_FILES = {
    "manifest.en.webmanifest": ("pwa/manifest.en.webmanifest", "application/manifest+json"),
    "manifest.ru.webmanifest": ("pwa/manifest.ru.webmanifest", "application/manifest+json"),
    "sw.js": ("pwa/sw.js", "application/javascript"),
}


@require_GET
def pwa_static_file(request, filename: str) -> FileResponse:
    static_path, content_type = PWA_STATIC_FILES.get(filename, (None, None))
    if static_path is None or content_type is None:
        raise Http404("PWA file not found")

    resolved_path = finders.find(static_path)
    if not resolved_path:
        raise Http404("PWA file not found")

    response = FileResponse(open(resolved_path, "rb"), content_type=content_type)  # noqa: SIM115
    if filename == "sw.js":
        response["Service-Worker-Allowed"] = "/"

    return response

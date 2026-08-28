from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class NonStrictManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """
    Some vendored minified files (lucide.min.js, dmr's redoc.standalone.js)
    reference a sourcemap that isn't shipped alongside them. The default
    storage tries to hash that referenced .map file too and fails
    collectstatic, so sourceMappingURL rewriting is disabled here; url()/
    @import rewriting for real static assets in CSS is kept as-is.
    """

    patterns = (
        (
            "*.css",
            (
                (
                    r"""(?P<matched>url\((?P<quote>['"]{0,1})"""
                    r"""\s*(?P<url>.*?)(?P=quote)\))"""
                ),
                (
                    r"""(?P<matched>@import\s*["']\s*(?P<url>.*?)["'])""",
                    """@import url("%(url)s")""",
                ),
            ),
        ),
    )

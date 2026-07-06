from types import MappingProxyType

from starlette.responses import Response

SECURITY_HEADERS = MappingProxyType(
    {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        # Reinforces X-Frame-Options and locks the document base URI. Kept narrow
        # so the API's own Swagger docs page (served from a CDN) still renders;
        # the browser-facing SPA sets a full resource CSP at the nginx layer.
        "Content-Security-Policy": "frame-ancestors 'none'; base-uri 'none'",
    }
)

HSTS_HEADER = "Strict-Transport-Security"
HSTS_VALUE = "max-age=63072000; includeSubDomains"


def apply_security_headers(response: Response, *, secure_transport: bool = False) -> None:
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    # Only assert HSTS when the deployment actually serves over TLS, so local
    # HTTP development is not pinned to HTTPS by a cached browser policy.
    if secure_transport:
        response.headers.setdefault(HSTS_HEADER, HSTS_VALUE)

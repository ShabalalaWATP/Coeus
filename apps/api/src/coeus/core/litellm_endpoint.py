"""Validation and endpoint construction for the deployment-managed LiteLLM Proxy."""

from urllib.parse import unquote, urlsplit, urlunsplit


def litellm_base_url_errors(base_url: str, *, hosted: bool) -> tuple[str, ...]:
    """Return structural configuration errors without performing network resolution."""
    if any(ord(character) < 32 or ord(character) == 127 for character in base_url):
        return ("COEUS_LITELLM_BASE_URL cannot contain control characters.",)
    try:
        parsed = urlsplit(base_url)
        _ = parsed.port
    except ValueError:
        return ("COEUS_LITELLM_BASE_URL must be a valid absolute HTTP(S) URL.",)
    errors: list[str] = []
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        errors.append("COEUS_LITELLM_BASE_URL must be a valid absolute HTTP(S) URL.")
    if hosted and parsed.scheme != "https":
        errors.append("COEUS_LITELLM_BASE_URL must use HTTPS in hosted environments.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        errors.append("COEUS_LITELLM_BASE_URL cannot contain credentials, a query or a fragment.")
    segments = tuple(part for part in unquote(parsed.path).split("/") if part)
    if any(part in {".", ".."} for part in segments):
        errors.append("COEUS_LITELLM_BASE_URL cannot contain dot path segments.")
    encoded = base_url.casefold()
    if any(token in encoded for token in ("%00", "%2f", "%3f", "%23", "%40", "%5c")):
        errors.append("COEUS_LITELLM_BASE_URL contains an unsafe encoded delimiter.")
    return tuple(dict.fromkeys(errors))


def litellm_endpoint(base_url: str, resource: str, *, hosted: bool = False) -> str:
    """Append one fixed v1 resource to an already validated proxy base URL."""
    if litellm_base_url_errors(base_url, hosted=hosted):
        raise ValueError("The LiteLLM Proxy base URL is invalid.")
    if resource not in {"chat/completions", "models"}:
        raise ValueError("The LiteLLM Proxy resource is invalid.")
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    versioned_path = path if path.endswith("/v1") else f"{path}/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, f"{versioned_path}/{resource}", "", ""))

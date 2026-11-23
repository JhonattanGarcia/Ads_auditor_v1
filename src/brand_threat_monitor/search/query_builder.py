"""Adaptacion de URL y rango temporal, compartida por validacion y ejecucion."""

from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

def prepare(profile, original_url=None, now=None):
    """Adapt a validated Meta Library URL to profile criteria and inclusive local date boundaries."""
    zone = ZoneInfo(profile.get("timezone", "America/Bogota"))
    today = (now or datetime.now(zone)).astimezone(zone).date()
    search = profile.get("search", {})
    original = original_url or search["template_url"]
    parts = urlsplit(original)
    if (parts.scheme != "https" or parts.hostname not in {"facebook.com", "www.facebook.com"}
            or parts.path != "/ads/library/" or parts.username or parts.password
            or parts.port not in (None, 443) or parts.fragment):
        raise ValueError("URL de Biblioteca no valida")
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if len({k for k, _ in pairs}) != len(pairs):
        raise ValueError("La URL contiene parametros duplicados")
    params = dict(pairs)
    overrides = search.get("parameters", {})
    managed = {"q", "country", "start_date[min]", "start_date[max]"}
    if managed.intersection(overrides):
        raise ValueError("Pais, criterio y fechas deben configurarse en sus campos propios")
    params.update(overrides)
    allowed = managed | {"active_status", "ad_type", "is_targeted_country", "media_type",
                         "search_type", "sort_data[direction]", "sort_data[mode]"}
    if set(params) - allowed:
        raise ValueError(f"Parametros no soportados: {sorted(set(params) - allowed)}")
    defaults = {"active_status": "active", "ad_type": "all", "is_targeted_country": "false",
                "media_type": "all", "search_type": "keyword_unordered",
                "sort_data[direction]": "desc", "sort_data[mode]": "total_impressions"}
    for key, expected in defaults.items():
        if params.get(key, expected) != expected:
            raise ValueError(f"Este adaptador inicial solo admite {key}={expected}")
        params[key] = expected
    if not profile.get("enabled", True):
        raise ValueError("El perfil esta deshabilitado")
    criteria = [c["query"] for c in profile.get("criteria", []) if c.get("enabled", True)]
    if len(criteria) != 1 or not isinstance(criteria[0], str) or not criteria[0].strip():
        raise ValueError("Este ejecutor inicial requiere exactamente un criterio habilitado")
    country = profile.get("country", "").upper()
    if len(country) != 2 or not country.isascii() or not country.isalpha():
        raise ValueError("country debe ser un codigo de pais de dos letras")
    temporal = search.get("date_range", {})
    mode = temporal.get("mode", "rolling_days" if "days_to_review" in profile else "today")
    days = profile.get("days_to_review", 1)
    if mode in {"today", "rolling_days"}:
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise ValueError("days_to_review debe ser entero positivo")
        if mode == "today" and days != 1:
            raise ValueError("today requiere days_to_review=1")
        low, high = today - timedelta(days=days - 1), today
    elif mode == "fixed":
        if "days_to_review" in profile:
            raise ValueError("fixed no admite days_to_review")
        low, high = date.fromisoformat(temporal["min"]), date.fromisoformat(temporal["max"])
        if low > high or high > today:
            raise ValueError("Rango fijo invertido o futuro")
    else:
        raise ValueError("Modo temporal no soportado")
    params.update({"q": criteria[0], "country": country,
                   "start_date[min]": low.isoformat(), "start_date[max]": high.isoformat()})
    effective = urlunsplit(("https", "www.facebook.com", "/ads/library/", urlencode(params), ""))
    return original, effective, params, zone, low, high

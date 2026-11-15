"""Carga estricta de perfiles y manifiestos antes de consultar fuentes."""

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..search.query_builder import prepare

# ISO 3166-1 alfa-2; no se aceptan paises inventados de dos letras.
COUNTRIES = set("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())


class ProfileError(ValueError):
    pass


def require(condition, field, message):
    if not condition:
        raise ProfileError(f"{field}: {message}")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, key, "clave JSON duplicada")
            result[key] = value
        return result
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)
    except (OSError, ValueError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
    require(isinstance(value, dict), str(path), "se requiere objeto JSON")
    return value


def validate_profile(value):
    profile = copy.deepcopy(value)
    require(isinstance(profile, dict), "profile", "se requiere objeto")
    require(profile.get("schema_version") == "1.0", "schema_version", "version admitida: 1.0")
    for field in ("client_id", "client_name", "country"):
        require(isinstance(profile.get(field), str) and bool(profile[field].strip()), field, "cadena obligatoria")
    country = profile["country"].upper()
    require(country in COUNTRIES, "country", "codigo ISO alfa-2 no valido")
    profile["country"] = country.lower()
    profile.setdefault("enabled", True)
    require(type(profile["enabled"]) is bool, "enabled", "se requiere booleano")
    profile.setdefault("timezone", "America/Bogota")
    try:
        ZoneInfo(profile["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ProfileError("timezone: zona horaria no valida") from exc
    criteria = profile.get("criteria")
    require(isinstance(criteria, list) and bool(criteria), "criteria", "lista no vacia obligatoria")
    seen = set()
    for index, criterion in enumerate(criteria):
        field = f"criteria[{index}]"
        require(isinstance(criterion, dict), field, "se requiere objeto")
        query = criterion.get("query")
        require(isinstance(query, str) and bool(query.strip()), field+".query", "cadena no vacia")
        criterion.setdefault("enabled", True)
        require(type(criterion["enabled"]) is bool, field+".enabled", "se requiere booleano")
        require(query not in seen, field+".query", "criterio duplicado")
        seen.add(query)
    search = profile.get("search")
    require(isinstance(search, dict), "search", "objeto obligatorio")
    require(isinstance(search.get("template_url"), str), "search.template_url", "URL obligatoria")
    require(isinstance(search.get("parameters", {}), dict), "search.parameters", "se requiere objeto")
    require(isinstance(search.get("date_range", {}), dict), "search.date_range", "se requiere objeto")
    for field in ("approved_advertiser_ids", "approved_domains"):
        values = profile.get(field, [])
        require(isinstance(values, list) and all(isinstance(v, str) and v.strip() for v in values), field, "lista de cadenas")
    # Valida incluso criterios desactivados; aun no se consulta ninguna fuente.
    for criterion in criteria:
        single = copy.deepcopy(profile)
        single["enabled"] = True
        single["criteria"] = [{"query": criterion["query"], "enabled": True}]
        try:
            prepare(single)
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            raise ProfileError(f"search/date_range: {exc}") from exc
    return profile


def load_profile(path):
    try:
        return validate_profile(read_json(path))
    except ProfileError as exc:
        raise ProfileError(f"{path}: {exc}") from exc


@dataclass(frozen=True)
class SearchPlan:
    profiles: list[dict]
    output_directory: Path

    def queries(self):
        for profile in self.profiles:
            if not profile["enabled"]:
                continue
            for criterion in profile["criteria"]:
                if criterion["enabled"]:
                    single = copy.deepcopy(profile)
                    single["criteria"] = [criterion.copy()]
                    yield single


def load_manifest(path):
    path = Path(path).resolve()
    data = read_json(path)
    require(data.get("schema_version") == "1.0", "schema_version", "version admitida: 1.0")
    entries = data.get("profiles")
    require(isinstance(entries, list) and bool(entries), "profiles", "lista no vacia obligatoria")
    output = data.get("output", {})
    require(isinstance(output, dict), "output", "se requiere objeto")
    require(output.get("format", "json") == "json", "output.format", "solo json soportado")
    directory = output.get("directory", "../data/results")
    require(isinstance(directory, str) and bool(directory.strip()), "output.directory", "ruta no vacia")
    profiles, paths, ids = [], set(), set()
    for index, entry in enumerate(entries):
        field = f"profiles[{index}]"
        require(isinstance(entry, dict), field, "se requiere objeto")
        require(type(entry.get("enabled", True)) is bool, field+".enabled", "se requiere booleano")
        require(isinstance(entry.get("path"), str) and bool(entry["path"].strip()), field+".path", "ruta obligatoria")
        candidate = (path.parent / entry["path"]).resolve()
        require(candidate not in paths, field+".path", "ruta duplicada")
        paths.add(candidate)
        if not entry.get("enabled", True):
            continue
        profile = load_profile(candidate)
        require(profile["client_id"] not in ids, field, "client_id duplicado")
        ids.add(profile["client_id"])
        profiles.append(profile)
    return SearchPlan(profiles, (path.parent / directory).resolve())

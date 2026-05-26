import json
import os
import urllib.parse
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_headers = {"Content-Type": "application/json"}


def configured():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _api(method: str, path: str, data=None, params: dict = None):
    import traceback
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url += "?" + qs
    hdrs = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if method in ("POST", "PATCH") and data is not None:
        prefers = ["return=representation"]
        if params and "on_conflict" in params:
            prefers.append("resolution=merge-duplicates")
        hdrs["Prefer"] = ", ".join(prefers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8")
            if not raw.strip():
                return []
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            print(f"Supabase HTTP {e.code} on {method} {path}: {err_body}", flush=True)
        except Exception:
            print(f"Supabase HTTP {e.code} on {method} {path}", flush=True)
        return None
    except Exception as ex:
        print(f"Supabase error on {method} {path}: {ex}", flush=True)
        return None


# ── FAQ ──

def get_faq_items():
    return _api("GET", "faq_items?order=id") or []


def upsert_faq_items(items: list[dict]):
    for item in items:
        clean = {"id": item["id"], "question": item.get("question", ""), "answer": item.get("answer", ""), "tags": item.get("tags", [])}
        _api("POST", "faq_items", clean, params={"on_conflict": "id"})


def get_system_messages():
    rows = _api("GET", "system_messages") or []
    return {r["key"]: r["value"] for r in rows}


def upsert_system_message(key: str, value: str):
    _api("POST", "system_messages", {"key": key, "value": value},
         params={"on_conflict": "key"})


# ── PRICING ──

def get_pricing_config() -> dict:
    rows = _api("GET", "pricing_config?id=eq.1") or []
    if rows:
        r = rows[0]
        return {
            "weekend_surcharge": {
                "friday": float(r.get("weekend_friday", 1.20)),
                "saturday": float(r.get("weekend_saturday", 1.25)),
                "sunday": float(r.get("weekend_sunday", 1.20)),
            },
            "high_season_multiplier": float(r.get("high_season_multiplier", 2.0)),
            "high_season_months": r.get("high_season_months", [1, 2, 7]),
            "min_nights_default": r.get("min_nights_default", 1),
            "min_nights_high_season": r.get("min_nights_high_season", 2),
        }
    return {}


def upsert_pricing_config(cfg: dict):
    row = {
        "id": 1,
        "weekend_friday": cfg.get("weekend_surcharge", {}).get("friday", 1.20),
        "weekend_saturday": cfg.get("weekend_surcharge", {}).get("saturday", 1.25),
        "weekend_sunday": cfg.get("weekend_surcharge", {}).get("sunday", 1.20),
        "high_season_multiplier": cfg.get("high_season_multiplier", 2.0),
        "high_season_months": cfg.get("high_season_months", [1, 2, 7]),
        "min_nights_default": cfg.get("min_nights_default", 1),
        "min_nights_high_season": cfg.get("min_nights_high_season", 2),
    }
    _api("POST", "pricing_config", row, params={"on_conflict": "id"})


def get_property_overrides() -> dict:
    rows = _api("GET", "property_overrides") or []
    return {r["property_key"]: r for r in rows}


def upsert_property_override(key: str, data: dict):
    row = {"property_key": key, **data}
    _api("POST", "property_overrides", row, params={"on_conflict": "property_key"})


def get_date_overrides() -> list:
    return _api("GET", "date_overrides?order=start_date") or []


def upsert_date_overrides(items: list[dict]):
    _api("DELETE", "date_overrides", params={"id": "neq.0"})
    for item in items:
        _api("POST", "date_overrides", item)


# ── CALENDAR ──

def get_calendar_dates(property_key: str, status: str = None) -> dict[str, set]:
    path = f"calendar_dates?property_key=eq.{property_key}"
    if status:
        path += f"&status=eq.{status}"
    rows = _api("GET", path) or []
    result = {"blocked": set(), "available": set()}
    for r in rows:
        result[r["status"]].add(r["date"])
    return result


def clear_all_calendar_dates():
    _api("DELETE", "calendar_dates", params={"property_key": "neq."})


def set_calendar_dates(property_key: str, dates: list[str], status: str):
    for d in dates:
        row = {"property_key": property_key, "date": d, "status": status}
        _api("POST", "calendar_dates", row)


def delete_calendar_dates(property_key: str, dates: list[str], status: str = None):
    for d in dates:
        params = {"property_key": f"eq.{property_key}", "date": f"eq.{d}"}
        if status:
            params["status"] = f"eq.{status}"
        _api("DELETE", "calendar_dates", params=params)


# ── PHOTOS ──

def get_photo_overrides() -> dict:
    rows = _api("GET", "photo_overrides") or []
    return {r["property_key"]: r.get("categories", {}) for r in rows}


def upsert_photo_override(property_key: str, categories: dict):
    row = {"property_key": property_key, "categories": categories}
    _api("POST", "photo_overrides", row, params={"on_conflict": "property_key"})

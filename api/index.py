import sys
import json
import re
import os
import traceback
import urllib.request
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

_api_dir = str(Path(__file__).parent)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from agent import Agent
from storage import ConversationStore
from blob_store import blob_get_key, blob_set_key, blob_read, blob_write
from supabase_db import configured as supabase_configured
from supabase_db import (_api,
                          get_faq_items, get_system_messages, upsert_faq_items, upsert_system_message,
                          get_pricing_config, get_property_overrides, get_date_overrides,
                          upsert_pricing_config, upsert_property_override, upsert_date_overrides,
                          get_calendar_dates, set_calendar_dates, clear_all_calendar_dates,
                           get_photo_overrides, upsert_photo_override)
from pix import gerar_pix_payload

app = FastAPI(title="PremiumHost Roberto - API", version="1.0.0")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "phadmin2026"

rate_limits = {}

def check_rate_limit(ip: str) -> bool:
    now = datetime.now()
    window = 60
    max_reqs = 30
    key = f"{ip}:{now.strftime('%Y%m%d%H%M')}"
    count = rate_limits.get(key, 0)
    if count >= max_reqs:
        return False
    rate_limits[key] = count + 1
    for k in list(rate_limits.keys()):
        if k.split(":")[1] != now.strftime("%Y%m%d%H%M"):
            del rate_limits[k]
    return True

def get_client_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def verify_admin(password: str = "", request=None):
    if password and password == ADMIN_PASSWORD:
        return True
    if request:
        header_key = request.headers.get("x-admin-key", "")
        if header_key == ADMIN_PASSWORD:
            return True
    return False

# ── BACKUP HELPERS ──

def _collect_snapshot():
    """Collect all current data into a dict for backup."""
    snap = {}
    if supabase_configured():
        try:
            faq = get_faq_items()
            if faq: snap["faq_items"] = faq
            sys_msgs = get_system_messages()
            if sys_msgs: snap["system_messages"] = {k: v for k, v in sys_msgs.items() if not k.startswith("_backup_")}
            pc = get_pricing_config()
            if pc: snap["pricing_config"] = pc
            po = get_property_overrides()
            if po: snap["property_overrides"] = {k: dict(v) for k, v in po.items()}
            do = get_date_overrides()
            if do: snap["date_overrides"] = do
            cal = []
            for pk in agent.pm.list_properties():
                for st in ("blocked", "available"):
                    cd = get_calendar_dates(pk, st)
                    for d in cd.get(st, set()):
                        cal.append({"property_key": pk, "date": d, "status": st})
            if cal: snap["calendar_dates"] = cal
            ph = get_photo_overrides()
            if ph: snap["photo_overrides"] = ph
        except Exception as e:
            print(f"Backup snapshot warn: {e}", flush=True)
    return snap


def _create_backup(label: str):
    """Save a snapshot to system_messages table. Returns the backup key, or None if failed."""
    snap = _collect_snapshot()
    key = "_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + (label.strip() or "manual")
    if supabase_configured():
        try:
            upsert_system_message(key, json.dumps(snap, ensure_ascii=False))
            # Verify the upsert took effect
            verify = _api("GET", f"system_messages?key=eq.{key}&select=key") or []
            if verify:
                print(f"Backup saved: {key}", flush=True)
                return key
            else:
                print(f"Backup NOT found after upsert: {key}", flush=True)
        except Exception as e:
            print(f"Backup error: {e}", flush=True)
    print("Backup: Supabase not configured", flush=True)
    return None


def _list_backups() -> list[dict]:
    """List all backups from system_messages table, newest first."""
    if not supabase_configured():
        return []
    try:
        rows = _api("GET", "system_messages?order=key.desc") or []
        result = []
        for r in rows:
            k = r["key"]
            if not k.startswith("_backup_"):
                continue
            rest = k[len("_backup_"):]
            parts = rest.split("_", 2)
            ts = parts[0] + "_" + parts[1] if len(parts) >= 2 else ""
            label = parts[2] if len(parts) >= 3 else ""
            result.append({"key": k, "created_at": ts, "label": label})
        return result
    except Exception as e:
        print(f"Backup list error: {e}", flush=True)
        return []


def _get_backup(key: str) -> dict:
    """Get a backup snapshot by key from system_messages."""
    if supabase_configured():
        try:
            rows = _api("GET", f"system_messages?key=eq.{key}") or []
            if rows:
                val = rows[0]["value"]
                if val:
                    return json.loads(val)
        except Exception as e:
            print(f"Get backup error: {e}", flush=True)
    return None


def _restore_backup(key: str) -> str:
    """Restore a backup snapshot into Supabase tables. Returns the label."""
    snap = _get_backup(key)
    if not snap:
        raise ValueError("Backup not found")
    rest = key[len("_backup_"):] if key.startswith("_backup_") else key
    parts = rest.split("_", 2)
    label = parts[2] if len(parts) >= 3 else parts[0] if parts else "unknown"
    if supabase_configured():
        try:
            from supabase_db import upsert_faq_items, upsert_system_message, upsert_pricing_config, upsert_property_override, upsert_date_overrides, upsert_photo_override, set_calendar_dates, clear_all_calendar_dates
            if "faq_items" in snap:
                upsert_faq_items(snap["faq_items"])
            if "system_messages" in snap:
                for k, v in snap["system_messages"].items():
                    upsert_system_message(k, v)
            if "pricing_config" in snap:
                upsert_pricing_config(snap["pricing_config"])
            if "property_overrides" in snap:
                for pk, data in snap["property_overrides"].items():
                    upsert_property_override(pk, data)
            if "date_overrides" in snap:
                upsert_date_overrides(snap["date_overrides"])
            if "photo_overrides" in snap:
                for pk, cats in snap["photo_overrides"].items():
                    upsert_photo_override(pk, cats)
            if "calendar_dates" in snap:
                clear_all_calendar_dates()
                for entry in snap["calendar_dates"]:
                    set_calendar_dates(entry["property_key"], [entry["date"]], entry["status"])
        except Exception as e:
            print(f"Restore error: {e}", flush=True)
            raise ValueError(f"Erro ao restaurar: {e}")
    return label

    if supabase_configured():
        if snap.get("faq_items"):
            upsert_faq_items(snap["faq_items"])
        if snap.get("system_messages"):
            for msg_key, val in snap["system_messages"].items():
                upsert_system_message(msg_key, val)
        if snap.get("pricing_config"):
            upsert_pricing_config(snap["pricing_config"])
        if snap.get("property_overrides"):
            for pk, data in snap["property_overrides"].items():
                upsert_property_override(pk, data)
        if snap.get("date_overrides"):
            items = [{"start_date": d["start_date"], "end_date": d["end_date"], "multiplier": d.get("multiplier", 1.0)} for d in snap["date_overrides"]]
            upsert_date_overrides(items)
        if snap.get("calendar_dates"):
            clear_all_calendar_dates()
            for row in snap["calendar_dates"]:
                set_calendar_dates(row["property_key"], [row["date"]], row["status"])
        if snap.get("photo_overrides"):
            _api("DELETE", "photo_overrides", params={"property_key": "neq."})
            for pk, cats in snap["photo_overrides"].items():
                upsert_photo_override(pk, cats)

    return label


def _cleanup_old_backups():
    """Delete backups older than 90 days from system_messages."""
    if not supabase_configured():
        return
    cutoff = (datetime.now() - timedelta(days=90))
    try:
        rows = _api("GET", "system_messages") or []
        for r in rows:
            k = r["key"]
            if not k.startswith("_backup_"):
                continue
            # key format: _backup_YYYYMMDD_HHMMSS_label
            date_str = k[len("_backup_"):].split("_", 2)[0]
            if len(date_str) == 8 and date_str.isdigit():
                dt = datetime.strptime(date_str, "%Y%m%d")
                if dt < cutoff:
                    _api("DELETE", "system_messages", params={"key": f"eq.{k}"})
    except Exception:
        pass

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config_path = str(Path(__file__).parent / "config.json")
agent = Agent(config_path)
store = ConversationStore()

# In-memory blocked dates (synced to /tmp for cross-instance resilience)
_admin_blocked = {}  # {property_key: set("YYYY-MM-DD", ...)}
# In-memory force-available dates (override blocked/ical)
_admin_available = {}  # {property_key: set("YYYY-MM-DD", ...)}

# In-memory photo overrides (synced to /tmp for cross-instance resilience)
_admin_photos = {}  # {property_key: {category: [url, ...]}}

CALENDAR_TMP = "/tmp/calendario_premiumhost.json"
PHOTOS_TMP = "/tmp/photos_premiumhost.json"

BLOCKED_TMP = "/tmp/blocked_premiumhost.json"


def _load_calendar_state():
    if os.path.exists(CALENDAR_TMP):
        try:
            with open(CALENDAR_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_calendar_state(data: dict):
    try:
        with open(CALENDAR_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _sync_calendar_state():
    # Try Supabase first (cross-instance persistence)
    if supabase_configured():
        try:
            has_data = False
            for prop_key in agent.pm.list_properties():
                cal = get_calendar_dates(prop_key)
                if cal["blocked"]:
                    has_data = True
                    _admin_blocked.setdefault(prop_key, set()).update(cal["blocked"])
                if cal["available"]:
                    has_data = True
                    _admin_available.setdefault(prop_key, set()).update(cal["available"])
            if has_data:
                return
        except Exception:
            pass
    # Try blob next
    try:
        blob = blob_get_key("calendar")
        if isinstance(blob, dict):
            for key, dates in blob.get("blocked", {}).items():
                _admin_blocked.setdefault(key, set()).update(dates)
            for key, dates in blob.get("available", {}).items():
                _admin_available.setdefault(key, set()).update(dates)
            _save_calendar_state(blob)
            return
    except Exception:
        pass
    # Fallback to /tmp
    data = _load_calendar_state()
    for key, dates in data.get("blocked", {}).items():
        _admin_blocked.setdefault(key, set()).update(dates)
    for key, dates in data.get("available", {}).items():
        _admin_available.setdefault(key, set()).update(dates)


_sync_calendar_state()


def _load_photos_override():
    if os.path.exists(PHOTOS_TMP):
        try:
            with open(PHOTOS_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_photos_override(data: dict):
    try:
        with open(PHOTOS_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_photos_for(property_key: str) -> dict:
    """Return merged photo data: memory > Supabase > /tmp > config seed."""
    if property_key in _admin_photos:
        return _admin_photos[property_key]
    if supabase_configured():
        try:
            all_overrides = get_photo_overrides()
            if property_key in all_overrides:
                _admin_photos[property_key] = all_overrides[property_key]
                return _admin_photos[property_key]
        except Exception:
            pass
    overrides = _load_photos_override()
    if property_key in overrides:
        _admin_photos[property_key] = overrides[property_key]
        return _admin_photos[property_key]
    cfg = agent.pm.config
    return cfg.get("photos", {}).get(property_key, {})


class MessageRequest(BaseModel):
    message: str
    guest_name: Optional[str] = None
    guest_id: Optional[str] = None
    platform: Optional[str] = "web"


class QuoteRequest(BaseModel):
    property_key: str
    checkin: str
    checkout: str
    guests: int = 2


class BlockRequest(BaseModel):
    property_key: str
    dates: list[str]
    password: str = ""

    class Config:
        # Allow population by field name for compatibility
        protected_namespaces = ()


@app.get("/api/health")
def health():
    return {"status": "online", "projeto": "PremiumHost Roberto"}


# ── BACKUP ENDPOINTS ──

@app.get("/api/admin/backups")
def admin_list_backups(password: str = "", request: Request = None):
    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Muitas requisicoes. Aguarde um minuto.")
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    _cleanup_old_backups()
    return JSONResponse(content=_list_backups())


@app.post("/api/admin/backups/create")
def admin_create_backup(label: str = "", password: str = "", request: Request = None):
    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Muitas requisicoes. Aguarde um minuto.")
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    lbl = label.strip() or "manual"
    result = _create_backup(lbl)
    if not result:
        raise HTTPException(status_code=500, detail="Erro ao criar backup")
    return JSONResponse(content={"key": result, "label": lbl})


@app.get("/api/admin/backups/cron")
def cron_backup(request: Request = None):
    if not verify_admin("", request):
        return JSONResponse(content={"error": "no password configured"}, status_code=500)
    result = _create_backup("automatico_10dias")
    if not result:
        return JSONResponse(content={"error": "backup failed"}, status_code=500)
    return JSONResponse(content={"key": result, "label": "automatico_10dias"})


@app.post("/api/admin/backups/restore/{backup_key}")
def admin_restore_backup(backup_key: str, password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha invalida")
    try:
        label = _restore_backup(backup_key)
        return JSONResponse(content={"ok": True, "label": label})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao restaurar: {e}")


@app.post("/api/admin/backups/delete/{backup_key}")
def admin_delete_backup(backup_key: str, password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    try:
        if supabase_configured():
            rows = _api("GET", f"system_messages?key=eq.{backup_key}&select=key") or []
            if rows:
                _api("DELETE", "system_messages", params={"key": f"eq.{backup_key}"})
    except Exception as e:
        print(f"Delete backup error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Erro ao excluir backup")
    return JSONResponse(content={"status": "ok"})


@app.get("/api/calendar/{property_key}")
def get_calendar(property_key: str):
    config = agent.pm.config
    prop = config.get("properties", {}).get(property_key)
    if not prop:
        return JSONResponse(content=[])
    booked = set(prop.get("blocked_dates", []))
    # merge admin-blocked dates
    extra = _admin_blocked.get(property_key, set())
    booked.update(extra)
    ical_url = prop.get("ical_url")
    if ical_url:
        try:
            req = urllib.request.Request(ical_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                ical_text = resp.read().decode("utf-8")
            dates = re.findall(r"DTSTART;VALUE=DATE:(\d{4})(\d{2})(\d{2})", ical_text)
            for y, m, d in dates:
                booked.add(f"{y}-{m}-{d}")
        except Exception:
            pass
    # Remove force-available dates
    available = _admin_available.get(property_key, set())
    booked -= available
    return JSONResponse(content=sorted(booked))


def _save_blocked_state():
    data = {"blocked": {k: sorted(v) for k, v in _admin_blocked.items()},
            "available": {k: sorted(v) for k, v in _admin_available.items()}}
    _create_backup("calendario_automatico")
    # Save to Supabase (clear all then re-insert to handle removals)
    if supabase_configured():
        try:
            clear_all_calendar_dates()
            for prop_key, dates in _admin_blocked.items():
                set_calendar_dates(prop_key, list(dates), "blocked")
            for prop_key, dates in _admin_available.items():
                set_calendar_dates(prop_key, list(dates), "available")
        except Exception:
            pass
    # Also save to /tmp and blob as fallback
    _save_calendar_state(data)
    try:
        blob_set_key("calendar", data)
    except Exception:
        pass


@app.post("/api/admin/block")
def admin_block(req: BlockRequest, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    if req.property_key not in _admin_blocked:
        _admin_blocked[req.property_key] = set()
    for d in req.dates:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            _admin_blocked[req.property_key].add(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(_admin_blocked[req.property_key]))


@app.post("/api/admin/unblock")
def admin_unblock(req: BlockRequest, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    existing = _admin_blocked.get(req.property_key, set())
    for d in req.dates:
        existing.discard(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(existing))


@app.post("/api/admin/available")
def admin_available(req: BlockRequest, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    if req.property_key not in _admin_available:
        _admin_available[req.property_key] = set()
    for d in req.dates:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            _admin_available[req.property_key].add(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(_admin_available[req.property_key]))


@app.post("/api/admin/unavailable")
def admin_unavailable(req: BlockRequest, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    existing = _admin_available.get(req.property_key, set())
    for d in req.dates:
        existing.discard(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(existing))


@app.get("/api/admin/blocked")
def admin_list_blocked(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    result = {}
    for key, dates in _admin_blocked.items():
        result[key] = sorted(dates)
    return JSONResponse(content=result)


@app.get("/api/admin/state")
def admin_get_state(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    return JSONResponse(content={
        "blocked": {k: sorted(v) for k, v in _admin_blocked.items()},
        "available": {k: sorted(v) for k, v in _admin_available.items()},
    })


@app.get("/api/photos/{property_key}")
def get_photos(property_key: str):
    merged = _get_photos_for(property_key)
    return JSONResponse(content={"key": property_key, "categories": merged})


@app.get("/api/photos-debug")
def photos_debug(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    # test write
    test_ok = False
    try:
        with open("/tmp/photos_premiumhost_test.txt", "w") as f:
            f.write("ok")
        test_ok = True
    except Exception as e:
        test_ok = str(e)
    return JSONResponse(content={
        "in_memory": {k: list(v.keys()) for k, v in _admin_photos.items()},
        "tmp_file_exists": os.path.exists(PHOTOS_TMP),
        "tmp_content": _load_photos_override(),
        "tmp_write_test": test_ok,
    })


class PhotosUpdate(BaseModel):
    categories: dict[str, list[str]]


@app.put("/api/admin/photos/{property_key}")
def admin_update_photos(property_key: str, req: PhotosUpdate, password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    _admin_photos[property_key] = req.categories
    _create_backup("fotos_automatico")
    # Save to Supabase
    if supabase_configured():
        try:
            upsert_photo_override(property_key, req.categories)
        except Exception:
            pass
    # Also save to /tmp
    overrides = _load_photos_override()
    overrides[property_key] = req.categories
    _save_photos_override(overrides)
    return JSONResponse(content={"key": property_key, "categories": req.categories})


PRECOS_TMP = "/tmp/precos_premiumhost.json"

PRECOS_DEFAULTS = {
    "general": {
        "weekend_surcharge": {"friday": 1.20, "saturday": 1.25, "sunday": 1.20},
        "high_season_months": [1, 2, 7],
        "high_season_multiplier": 2.0,
        "min_nights_default": 1,
        "min_nights_high_season": 2,
    },
    "properties": {},
    "date_overrides": [],
}


def _load_precos_override():
    # Try Supabase first
    if supabase_configured():
        try:
            cfg = get_pricing_config()
            if cfg:  # only if seed row exists
                props = get_property_overrides()
                date_ovr = get_date_overrides()
                properties = {}
                for pk, pv in props.items():
                    p = dict(pv)
                    p.pop("property_key", None)
                    p.pop("updated_at", None)
                    properties[pk] = {k: v for k, v in p.items() if v is not None}
                date_overrides = [{"start": d["start_date"], "end": d["end_date"], "multiplier": float(d["multiplier"])} for d in date_ovr]
                return {"general": cfg, "properties": properties, "date_overrides": date_overrides}
        except Exception:
            pass
    # Try /tmp next
    if os.path.exists(PRECOS_TMP):
        try:
            with open(PRECOS_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Try Blob last
    blob = blob_get_key("pricing")
    if blob is not None:
        return blob
    return {}


def _save_precos_override(data: dict):
    # Save to Supabase
    if supabase_configured():
        try:
            upsert_pricing_config(data.get("general", {}))
            valid_prop_keys = {"base_price", "base_guests", "extra_guest_fee", "cleaning_fee"}
            for key, props in data.get("properties", {}).items():
                filtered = {k: v for k, v in props.items() if k in valid_prop_keys and v is not None}
                upsert_property_override(key, filtered)
            date_ovr = [{"start_date": d["start"], "end_date": d["end"], "multiplier": d.get("multiplier", 1.0)} for d in data.get("date_overrides", [])]
            upsert_date_overrides(date_ovr)
        except Exception:
            pass
    # Also save to /tmp and blob as fallback
    try:
        with open(PRECOS_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    blob_set_key("pricing", data)


class PrecosUpdate(BaseModel):
    general: dict
    properties: dict[str, dict]
    date_overrides: list[dict]
    password: str = ""


@app.get("/api/admin/precos")
def admin_get_precos(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")

    override = _load_precos_override()
    general = override.get("general", PRECOS_DEFAULTS["general"])
    date_overrides = override.get("date_overrides", [])
    prop_overrides = override.get("properties", {})

    properties_data = {}
    for key in cfg.get("properties", {}):
        prop = cfg["properties"][key]
        base = {
            "nome": prop.get("name", key),
            "base_price": prop.get("base_price", 0),
            "extra_guest_fee": prop.get("extra_guest_fee", 75),
            "base_guests": prop.get("base_guests", 2),
            "cleaning_fee": prop.get("cleaning_fee", 0),
        }
        if key in prop_overrides:
            base.update(prop_overrides[key])
        properties_data[key] = base

    return JSONResponse(content={
        "general": general,
        "properties": properties_data,
        "date_overrides": date_overrides,
    })


@app.put("/api/admin/precos")
def admin_update_precos(req: PrecosUpdate, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")

    _create_backup("precos_automatico")
    override = _load_precos_override()
    override["general"] = req.general
    override["properties"] = req.properties
    override["date_overrides"] = req.date_overrides
    _save_precos_override(override)
    return JSONResponse(content={"status": "ok"})


@app.get("/api/imoveis")
def list_properties():
    result = {}
    for key in agent.pm.list_properties():
        p = agent.pm.get_property(key)
        result[key] = {
            "nome": p.name,
            "localizacao": p.location,
            "capacidade": p.capacity,
            "preco_base": p.base_price,
            "comodidades": p.amenities,
        }
    return result


def _static_pix_brcode() -> str:
    """Generate static PIX BR Code (without amount) for QR display."""
    try:
        from pix import PIX_TEMPLATE_BEFORE, PIX_TEMPLATE_AFTER, _crc16_ccitt
        payload = PIX_TEMPLATE_BEFORE + PIX_TEMPLATE_AFTER
        crc = _crc16_ccitt(payload.encode("utf-8") + b"6304")
        return payload + f"6304{crc:04X}"
    except Exception:
        return ""


def _enrich_qr_codes(text: str) -> str:
    """Append QR code images to text when WhatsApp number or PIX key is mentioned."""
    if not text:
        return text or ""
    import urllib.parse
    has_whatsapp = "99290-0979" in text or "(71) 99290-0979" in text or "992900979" in text
    has_pix = "b1b74e94-2687-4ea1-831b-6351b97e7929" in text

    if not has_whatsapp and not has_pix:
        return text

    # Avoid re-enriching if QR already present
    if '<img' in text and 'qrserver' in text:
        return text

    enriched = text
    if has_pix:
        brcode = _static_pix_brcode()
        if brcode:
            pix_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(brcode)}"
            enriched += f'\n\n<p style="font-weight:bold;margin:8px 0 4px">QR Code PIX — escaneie para pagar</p>'
            enriched += f'\n<img src="{pix_qr}" alt="QR Code PIX" style="max-width:200px;border-radius:8px;display:block">'

    if has_whatsapp:
        wa_url = "https://wa.me/5571992900979"
        wa_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(wa_url)}"
        enriched += f'\n\n<p style="font-weight:bold;margin:8px 0 4px">QR Code WhatsApp — fale conosco</p>'
        enriched += f'\n<a href="{wa_url}" target="_blank"><img src="{wa_qr}" alt="WhatsApp" style="max-width:200px;border-radius:8px;display:block"></a>'

    return enriched


@app.post("/api/chat")
def chat(req: MessageRequest, request: Request = None):
    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Muitas requisicoes. Aguarde um minuto.")
    guest_id = req.guest_id or req.guest_name or "anon"
    response = agent.respond(req.message, req.guest_name, guest_id)
    # Enrich response with QR codes
    response = _enrich_qr_codes(response)
    return {"response": response, "guest_id": guest_id}


@app.post("/api/cotacao")
def quote(req: QuoteRequest):
    from pricing import PricingEngine, _load_overrides
    from datetime import datetime

    prop = agent.pm.get_property(req.property_key)
    if not prop:
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")

    try:
        checkin = datetime.strptime(req.checkin, "%d/%m/%Y").date()
        checkout = datetime.strptime(req.checkout, "%d/%m/%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato invalido. Use DD/MM/AAAA")

    overrides = _load_overrides()
    engine = PricingEngine(prop, agent.calendar, overrides)
    avail, msg = engine.check_availability(checkin, checkout)
    if not avail:
        return {"disponivel": False, "motivo": msg}

    breakdown = engine.calculate_total(checkin, checkout, req.guests)
    return {
        "disponivel": True,
        "imovel": prop.name,
        "checkin": checkin.strftime("%d/%m/%Y"),
        "checkout": checkout.strftime("%d/%m/%Y"),
        "noites": breakdown["nights"],
        "hospedes": req.guests,
        "total": breakdown["total"],
        "media_noite": breakdown["nightly_avg"],
        "temporada": agent.calendar.get_season_label(checkin, checkout),
    }


FAQ_TMP = "/tmp/faq_premiumhost.json"


@app.get("/api/admin/faq")
def admin_get_faq(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    # Try Supabase first
    if supabase_configured():
        try:
            faq_items = get_faq_items()
            sys_msgs = get_system_messages()
            if faq_items:
                # Load defaults from local faq.json so blank keys show their defaults
                defaults = {}
                faq_defaults_path = str(Path(__file__).parent / "faq.json")
                if os.path.exists(faq_defaults_path):
                    try:
                        with open(faq_defaults_path, "r", encoding="utf-8") as f:
                            defaults = json.load(f)
                    except Exception:
                        pass
                result = {
                    "faq": [{"id": it["id"], "resposta": it.get("resposta") or it.get("answer", ""), "tags": it.get("tags", []), "variacoes": it.get("variacoes", [])} for it in faq_items],
                }
                template_keys = ["saudacoes", "saudacoes_nome", "apresentacoes", "precos_disponivel",
                    "precos_calculado", "precos_cta", "indisponivel", "indisponivel_alternativas",
                    "despedidas", "agradecimento", "pergunta_imovel", "need_info_intro", "need_info_outro",
                    "confirmar_reserva", "pix_pagamento", "pix_info", "alternativas_datas_intro",
                    "alternativas_datas_outro", "alternativas_imoveis_intro", "alternativas_imoveis_outro",
                    "excesso_capacidade", "datas_invalidas", "menu_faq", "fallback",
                    "card_ask_cpf", "card_ask_details", "card_ask_postal", "card_processing",
                    "card_approved", "card_failed"]
                for key in template_keys:
                    val = sys_msgs.get(key, "")
                    if val:
                        result[key] = [val]
                    elif key in defaults and isinstance(defaults[key], list) and defaults[key]:
                        result[key] = defaults[key]
                    else:
                        result[key] = [""]
                return result
        except Exception:
            pass
    # Fallback: blob
    _bd = blob_read()
    if isinstance(_bd, dict):
        _faq = _bd.get("faq")
        if isinstance(_faq, dict):
            return _faq
        if _faq is None and "saudacoes" in _bd:
            return _bd
    # Fallback: /tmp
    if os.path.exists(FAQ_TMP):
        try:
            with open(FAQ_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback: local faq.json
    faq_path = str(Path(__file__).parent / "faq.json")
    if os.path.exists(faq_path):
        with open(faq_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return JSONResponse(content={"faq": []})


class FaqUpdateRequest(BaseModel):
    password: str = ""
    data: dict


@app.put("/api/admin/faq")
def admin_update_faq(req: FaqUpdateRequest, request: Request = None):
    if not verify_admin(req.password, request):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    data = req.data
    _create_backup("faq_automatico")
    # Save to Supabase
    if supabase_configured():
        try:
            raw_items = data.get("faq", [])
            faq_items = []
            for item in raw_items:
                converted = {"id": item["id"], "tags": item.get("tags", [])}
                if "resposta" in item:
                    converted["resposta"] = item["resposta"]
                    converted["question"] = item["resposta"]
                    converted["answer"] = item["resposta"]
                elif "question" in item:
                    converted["question"] = item["question"]
                    converted["answer"] = item.get("answer", item["question"])
                if item.get("variacoes"):
                    converted["variacoes"] = item["variacoes"]
                faq_items.append(converted)
            upsert_faq_items(faq_items)
            for key in ["saudacoes", "saudacoes_nome", "apresentacoes", "precos_disponivel", "precos_calculado", "precos_cta", "indisponivel", "indisponivel_alternativas", "despedidas", "agradecimento", "pergunta_imovel", "need_info_intro", "need_info_outro", "confirmar_reserva", "pix_pagamento", "pix_info", "alternativas_datas_intro", "alternativas_datas_outro", "alternativas_imoveis_intro", "alternativas_imoveis_outro", "excesso_capacidade", "datas_invalidas", "menu_faq", "fallback", "card_ask_cpf", "card_ask_details", "card_ask_postal", "card_processing", "card_approved", "card_failed"]:
                values = data.get(key, [])
                val = values[0] if isinstance(values, list) and values else values
                if val:
                    upsert_system_message(key, val)
        except Exception:
            pass
    # Also save to blob/tmp/file as fallback
    blob_set_key("faq", data)
    try:
        with open(FAQ_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    faq_path = str(Path(__file__).parent / "faq.json")
    try:
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return JSONResponse(content={"status": "ok"})


class PixPayloadRequest(BaseModel):
    total: float
    property_name: str = "Apartamento"
    checkin: str = ""
    checkout: str = ""


@app.post("/api/pix/payload")
def gerar_pix(req: PixPayloadRequest):
    entrada = req.total / 2
    payload = gerar_pix_payload(valor=entrada)
    return JSONResponse(content={
        "payload": payload,
        "valor_entrada": round(entrada, 2),
        "valor_total": round(req.total, 2),
        "propriedade": req.property_name,
        "checkin": req.checkin,
        "checkout": req.checkout,
    })


# ── LANDING PAGE TRACKING ──

class LandingClickRequest(BaseModel):
    button: str
    guest_id: str
    timestamp: Optional[str] = ""


@app.post("/api/landing-click")
def landing_click(req: LandingClickRequest):
    if supabase_configured():
        try:
            from supabase_db import log_landing_click
            log_landing_click(req.button, req.guest_id)
        except Exception as e:
            print(f"landing-click error: {e}", flush=True)
    return JSONResponse(content={"status": "ok"})


@app.get("/api/admin/landing-stats")
def admin_landing_stats(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        return JSONResponse(content={"error": "Senha invalida"}, status_code=403)
    stats = {"today": {"btn_chat": 0, "btn_site": 0}}
    if supabase_configured():
        try:
            from supabase_db import get_landing_clicks_today
            stats["today"] = get_landing_clicks_today()
        except Exception as e:
            print(f"landing-stats error: {e}", flush=True)
    return JSONResponse(content={"stats": stats})


@app.get("/api/admin/leads")
def admin_leads(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        return JSONResponse(content={"error": "Senha invalida"}, status_code=403)
    leads = []
    if supabase_configured():
        try:
            rows = _api("GET", "system_messages?order=key.desc") or []
            for r in rows:
                if not r["key"].startswith("_lead_"):
                    continue
                try:
                    data = json.loads(r["value"])
                    data["id"] = r["key"]
                    leads.append(data)
                except Exception:
                    pass
        except Exception:
            pass
    return JSONResponse(content={"leads": leads})


@app.get("/api/admin/check-email")
def admin_check_email(password: str = "", request: Request = None):
    if not verify_admin(password, request):
        return JSONResponse(content={"error": "Senha invalida"}, status_code=403)
    try:
        import email_notify
        return JSONResponse(content={
            "configured": email_notify.configured(),
            "from_email": email_notify.FROM_EMAIL,
            "notify_email": email_notify.NOTIFY_EMAIL,
            "last_error": email_notify.LAST_ERROR,
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


import sys
import json
import re
import os
import traceback
import urllib.request
from pathlib import Path
from fastapi import FastAPI, HTTPException
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
                          get_photo_overrides, upsert_photo_override,
                          save_backup)
from pix import gerar_pix_payload

app = FastAPI(title="PremiumHost Roberto - API", version="1.0.0")

# ── BACKUP HELPERS ──

def _collect_snapshot():
    """Collect all current data into a dict for backup."""
    snap = {}
    if supabase_configured():
        try:
            faq = get_faq_items()
            if faq: snap["faq_items"] = faq
            sys_msgs = get_system_messages()
            if sys_msgs: snap["system_messages"] = sys_msgs
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
    """Save a snapshot to the backups table. Returns the backup label, or None if failed."""
    snap = _collect_snapshot()
    lbl = label.strip() or "manual"
    ok = False
    if supabase_configured():
        try:
            result = save_backup(lbl, snap)
            print(f"Backup save_backup result: {result}", flush=True)
            if result:
                ok = True
            else:
                print("Backup: save_backup returned None/False", flush=True)
        except Exception as e:
            print(f"Backup Supabase error: {e}", flush=True)
    if not ok:
        print("Backup: nenhum storage disponivel!", flush=True)
        return None
    return lbl


def _list_backups() -> list[dict]:
    """List all backups from the backups table, newest first."""
    if not supabase_configured():
        return []
    try:
        rows = _api("GET", "backups?order=created_at.desc") or []
        result = []
        for r in rows:
            result.append({
                "id": r.get("id", 0),
                "key": str(r.get("id", 0)),
                "created_at": r.get("created_at", ""),
                "label": r.get("label", ""),
            })
        return result
    except Exception as e:
        print(f"Backup list error: {e}", flush=True)
        return []


def _get_backup(backup_id: int) -> dict:
    """Get a backup snapshot by ID from the backups table."""
    if supabase_configured():
        try:
            from supabase_db import get_backup
            return get_backup(backup_id)
        except Exception as e:
            print(f"Get backup error: {e}", flush=True)
    return None


def _restore_backup(backup_id: int) -> str:
    """Restore a backup. Returns the label."""
    if supabase_configured():
        try:
            from supabase_db import restore_backup
            return restore_backup(backup_id)
        except Exception:
            pass
    raise ValueError("Backup not found or Supabase not configured")


def _restore_backup(backup_id: int) -> str:
    """Restore a backup snapshot into Supabase tables. Returns the label."""
    if supabase_configured():
        try:
            from supabase_db import restore_backup
            return restore_backup(backup_id)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Erro ao restaurar: {e}")
    raise ValueError("Supabase not configured")

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
    """Delete backups older than 90 days from backups table."""
    cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    if supabase_configured():
        try:
            _api("DELETE", "backups", params={"created_at": f"lt.{cutoff}"})
        except Exception:
            pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    password: str


@app.get("/api/health")
def health():
    return {"status": "online", "projeto": "PremiumHost Roberto"}


# ── BACKUP ENDPOINTS ──

@app.get("/api/admin/backups")
def admin_list_backups(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    _cleanup_old_backups()
    return JSONResponse(content=_list_backups())


@app.post("/api/admin/backups/create")
def admin_create_backup(label: str = "", password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    lbl = label.strip() or "manual"
    result = _create_backup(lbl)
    if not result:
        raise HTTPException(status_code=500, detail="Erro ao criar backup")
    return JSONResponse(content={"key": result, "label": lbl})


@app.post("/api/admin/backups/restore/{backup_id}")
def admin_restore_backup(backup_id: int, password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    try:
        label = _restore_backup(backup_id)
        return JSONResponse(content={"status": "ok", "label": label})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao restaurar: {e}")


@app.post("/api/admin/backups/delete/{backup_id}")
def admin_delete_backup(backup_id: int, password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    deleted = False
    if supabase_configured():
        try:
            from supabase_db import delete_backup
            delete_backup(backup_id)
            deleted = True
            rows = _api("GET", f"system_messages?key=eq.{backup_key}&select=key") or []
            if rows:
                _api("DELETE", "system_messages", params={"key": f"eq.{backup_key}"})
                deleted = True
        except Exception:
            pass
    if not deleted:
        try:
            data = blob_read()
            if isinstance(data, dict) and backup_key in data:
                del data[backup_key]
                blob_write(data)
                deleted = True
        except Exception:
            pass
    if not deleted:
        raise HTTPException(status_code=404, detail="Backup nao encontrado")
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
def admin_block(req: BlockRequest):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
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
def admin_unblock(req: BlockRequest):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    existing = _admin_blocked.get(req.property_key, set())
    for d in req.dates:
        existing.discard(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(existing))


@app.post("/api/admin/available")
def admin_available(req: BlockRequest):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
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
def admin_unavailable(req: BlockRequest):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    if req.property_key not in cfg.get("properties", {}):
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")
    existing = _admin_available.get(req.property_key, set())
    for d in req.dates:
        existing.discard(d)
    _save_blocked_state()
    return JSONResponse(content=sorted(existing))


@app.get("/api/admin/blocked")
def admin_list_blocked(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    result = {}
    for key, dates in _admin_blocked.items():
        result[key] = sorted(dates)
    return JSONResponse(content=result)


@app.get("/api/admin/state")
def admin_get_state(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
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
def photos_debug(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
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
def admin_update_photos(property_key: str, req: PhotosUpdate, password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
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
    password: str


@app.get("/api/admin/precos")
def admin_get_precos(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
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
def admin_update_precos(req: PrecosUpdate):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
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


@app.post("/api/chat")
def chat(req: MessageRequest):
    guest_id = req.guest_id or req.guest_name or "anon"
    response = agent.respond(req.message, req.guest_name, guest_id)
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
def admin_get_faq(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        raise HTTPException(status_code=403, detail="Senha incorreta")
    # Try Supabase first
    if supabase_configured():
        try:
            faq_items = get_faq_items()
            sys_msgs = get_system_messages()
            if faq_items:
                return {
                    "faq": [{"id": it["id"], "resposta": it.get("resposta") or it.get("answer", ""), "tags": it.get("tags", []), "variacoes": it.get("variacoes", [])} for it in faq_items],
                    "saudacoes": [sys_msgs.get("saudacoes", "")],
                    "apresentacoes": [sys_msgs.get("apresentacoes", "")],
                    "precos_disponivel": [sys_msgs.get("precos_disponivel", "")],
                    "precos_calculado": [sys_msgs.get("precos_calculado", "")],
                    "indisponivel": [sys_msgs.get("indisponivel", "")],
                    "despedidas": [sys_msgs.get("despedidas", "")],
                    "agradecimento": [sys_msgs.get("agradecimento", "")],
                }
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
    password: str
    data: dict


@app.put("/api/admin/faq")
def admin_update_faq(req: FaqUpdateRequest):
    cfg = agent.pm.config
    if req.password != cfg.get("admin_password", ""):
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
            for key in ["saudacoes", "apresentacoes", "precos_disponivel", "precos_calculado", "indisponivel", "despedidas", "agradecimento"]:
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
def admin_landing_stats(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
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
def admin_leads(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        return JSONResponse(content={"error": "Senha invalida"}, status_code=403)
    # Return empty leads list for now (conversation leads not persisted)
    return JSONResponse(content={"leads": []})


# ── DEBUG ──

@app.get("/api/debug/backups")
def debug_backups(password: str = ""):
    cfg = agent.pm.config
    if password != cfg.get("admin_password", ""):
        return JSONResponse(content={"error": "Senha invalida"}, status_code=403)
    result = {"backup_keys": [], "supabase_rows": None, "blob_keys": None}
    if supabase_configured():
        try:
            rows = _api("GET", "system_messages") or []
            result["supabase_rows"] = [{"key": r["key"], "len_value": len(r.get("value", ""))} for r in rows if r["key"].startswith("_backup_")]
        except Exception as e:
            result["supabase_error"] = str(e)
    try:
        data = blob_read()
        if isinstance(data, dict):
            result["blob_keys"] = [k for k in data if k.startswith("_backup_")]
    except Exception as e:
        result["blob_error"] = str(e)
    total = []
    if result["supabase_rows"]:
        total.extend([r["key"] for r in result["supabase_rows"]])
    if result["blob_keys"]:
        total.extend(result["blob_keys"])
    result["merged"] = list(set(total))
    return JSONResponse(content=result)

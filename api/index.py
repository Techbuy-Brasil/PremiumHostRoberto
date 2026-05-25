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

_api_dir = str(Path(__file__).parent)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from agent import Agent
from storage import ConversationStore
from blob_store import blob_get_key, blob_set_key, blob_read, blob_write
from pix import gerar_pix_payload

app = FastAPI(title="PremiumHost Roberto - API", version="1.0.0")

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
    # Try blob first (cross-instance)
    try:
        blob = blob_get_key("calendar")
        if isinstance(blob, dict):
            for key, dates in blob.get("blocked", {}).items():
                _admin_blocked.setdefault(key, set()).update(dates)
            for key, dates in blob.get("available", {}).items():
                _admin_available.setdefault(key, set()).update(dates)
            # Sync back to /tmp
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
    """Return merged photo data: memory override > /tmp override > config seed."""
    if property_key in _admin_photos:
        return _admin_photos[property_key]
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
    # Try Blob first (cross-instance persistence)
    blob = blob_get_key("pricing")
    if blob is not None:
        return blob
    # Try /tmp next (same instance fallback)
    if os.path.exists(PRECOS_TMP):
        try:
            with open(PRECOS_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_precos_override(data: dict):
    # Save to /tmp first (guaranteed on this instance)
    try:
        with open(PRECOS_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    # Also save to Blob (cross-instance)
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
    # Load from Vercel Blob first (persists across all instances)
    _bd = blob_read()
    if isinstance(_bd, dict):
        _faq = _bd.get("faq")
        if isinstance(_faq, dict):
            return _faq
        if _faq is None and "saudacoes" in _bd:
            return _bd
    # Load from /tmp next (admin edits persist here on Vercel)
    if os.path.exists(FAQ_TMP):
        try:
            with open(FAQ_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fall back to local faq.json
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
    # Save to Vercel Blob first (persists across all instances)
    blob_set_key("faq", data)
    # Save to /tmp so it persists between cold starts on Vercel
    try:
        with open(FAQ_TMP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    # Also save to the actual faq.json if possible (for Git persistence)
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

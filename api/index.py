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

# In-memory blocked dates (survives warm instances)
_admin_blocked = {}  # {property_key: set("YYYY-MM-DD", ...)}

# In-memory photo overrides (synced to /tmp for cross-instance resilience)
_admin_photos = {}  # {property_key: {category: [url, ...]}}

PHOTOS_TMP = "/tmp/photos_premiumhost.json"


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
    return JSONResponse(content=sorted(booked))


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
    _admin_blocked[req.property_key] = existing
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


@app.get("/api/photos/{property_key}")
def get_photos(property_key: str):
    merged = _get_photos_for(property_key)
    return JSONResponse(content={"key": property_key, "categories": merged})


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
    from pricing import PricingEngine
    from datetime import datetime

    prop = agent.pm.get_property(req.property_key)
    if not prop:
        raise HTTPException(status_code=404, detail="Imovel nao encontrado")

    try:
        checkin = datetime.strptime(req.checkin, "%d/%m/%Y").date()
        checkout = datetime.strptime(req.checkout, "%d/%m/%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato invalido. Use DD/MM/AAAA")

    engine = PricingEngine(prop, agent.calendar)
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

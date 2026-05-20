from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
from datetime import datetime

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

BASE_DIR = Path(__file__).parent
CONFIG_PATH = str(BASE_DIR / "config.json")

agent = Agent(CONFIG_PATH)
store = ConversationStore()


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


@app.get("/api/health")
def health():
    return {"status": "online", "projeto": "PremiumHost Roberto"}


@app.get("/api/imoveis")
def list_properties():
    result = {}
    for key in agent.pm.list_properties():
        p = agent.pm.get_property(key)
        result[key] = {
            "nome": p.name,
            "localizacao": p.location,
            "capacidade": p.capacity,
            "quartos": p.bedrooms,
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

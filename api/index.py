import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import os
from pathlib import Path
from datetime import datetime
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

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
CONFIG_PATH = BASE_DIR / "config.json"

agent = Agent(str(CONFIG_PATH))
store = ConversationStore()


class MessageRequest(BaseModel):
    message: str = Field(..., description="Mensagem do hospede")
    guest_name: Optional[str] = Field(None)
    guest_id: Optional[str] = Field(None)
    platform: Optional[str] = Field("web")


class QuoteRequest(BaseModel):
    property_key: str = Field(..., description="Chave do imovel")
    checkin: str = Field(..., description="Data check-in (DD/MM/AAAA)")
    checkout: str = Field(..., description="Data check-out (DD/MM/AAAA)")
    guests: int = Field(2, ge=1, le=6)


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
            "short_name": p.short_name,
            "localizacao": p.location,
            "capacidade": p.capacity,
            "quartos": p.bedrooms,
            "camas": p.beds,
            "banheiros": p.bathrooms,
            "preco_base": p.base_price,
            "taxa_limpeza": p.cleaning_fee,
            "comodidades": p.amenities,
        }
    return result


@app.post("/api/chat")
def chat(req: MessageRequest):
    try:
        guest_id = req.guest_id or req.guest_name or "anon"
        response = agent.respond(req.message, req.guest_name, guest_id)
        return {"response": response, "guest_id": guest_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cotacao")
def quote(req: QuoteRequest):
    from pricing import PricingEngine

    prop = agent.pm.get_property(req.property_key)
    if not prop:
        raise HTTPException(status_code=404, detail=f"Imovel '{req.property_key}' nao encontrado")

    try:
        checkin = datetime.strptime(req.checkin, "%d/%m/%Y").date()
        checkout = datetime.strptime(req.checkout, "%d/%m/%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data invalido. Use DD/MM/AAAA")

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
        "taxa_hospedes_extras": breakdown.get("extra_guests_fee", 0),
        "taxa_limpeza": breakdown.get("cleaning_fee", 0),
        "temporada": agent.calendar.get_season_label(checkin, checkout),
    }

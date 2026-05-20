import sys
import json
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

try:
    from agent import Agent
    from storage import ConversationStore
    AGENT_OK = True
except Exception as e:
    AGENT_OK = False
    AGENT_ERR = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

app = FastAPI(title="PremiumHost Roberto - API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if AGENT_OK:
    try:
        config_path = str(Path(__file__).parent / "config.json")
        agent = Agent(config_path)
        store = ConversationStore()
        AGENT_READY = True
    except Exception as e:
        AGENT_READY = False
        AGENT_ERR = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
else:
    AGENT_READY = False


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
    status = {"status": "online", "projeto": "PremiumHost Roberto", "agent_ready": AGENT_READY}
    if not AGENT_READY:
        status["error"] = AGENT_ERR
    return status

import json
import os
import random
from pathlib import Path

from blob_store import blob_get_key, blob_read, blob_available
from supabase_db import configured as supabase_configured
from supabase_db import get_faq_items, get_system_messages


class KnowledgeBase:
    def __init__(self, faq_path=None):
        if faq_path is None:
            faq_path = str(Path(__file__).parent / "faq.json")
        self.path = faq_path
        self._data, self._mtime = self._load()

    def _load(self):
        # Try Supabase first (cross-instance persistence)
        if supabase_configured():
            try:
                result = self._build_from_supabase()
                if result is not None:
                    return result, "supabase"
            except Exception:
                pass
        # Try Vercel Blob next
        if blob_available():
            try:
                all_data = blob_read()
                if isinstance(all_data, dict):
                    faq_data = all_data.get("faq")
                    if isinstance(faq_data, dict):
                        return faq_data, "blob"
                    if faq_data is None and "saudacoes" in all_data:
                        return all_data, "blob"
            except Exception:
                pass
        # Try /tmp next
        tmp_path = "/tmp/faq_premiumhost.json"
        if os.path.exists(tmp_path):
            try:
                with open(tmp_path, "r", encoding="utf-8") as f:
                    return json.load(f), os.path.getmtime(tmp_path)
            except Exception:
                pass
        # Fall back to local faq.json
        if not os.path.exists(self.path):
            return {"faq": [], "saudacoes": [], "saudacoes_nome": [], "apresentacoes": [],
                    "precos_disponivel": [], "precos_calculado": [], "precos_cta": [],
                    "indisponivel": [], "indisponivel_alternativas": [], "despedidas": [],
                    "agradecimento": [], "need_info_intro": [], "need_info_outro": [],
                    "confirmar_reserva": [], "pix_pagamento": [], "pix_info": [],
                    "card_ask_cpf": [], "card_ask_details": [], "card_ask_postal": [],
                    "card_processing": [], "card_approved": [], "card_failed": [],
                    "alternativas_datas_intro": [], "alternativas_datas_outro": [],
                    "alternativas_imoveis_intro": [], "alternativas_imoveis_outro": [],
                    "excesso_capacidade": [], "datas_invalidas": [], "menu_faq": [],
                    "pergunta_imovel": [], "fallback": []}, None
        try:
            mtime = os.path.getmtime(self.path) if os.path.exists(self.path) else None
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f), mtime
        except Exception:
            return {}, None

    def _build_from_supabase(self):
        faq_items = get_faq_items()
        sys_msgs = get_system_messages()
        if not faq_items and not any(v for v in sys_msgs.values() if v):
            return None
        return {
            "faq": [{"id": it["id"], "resposta": it.get("resposta") or it.get("answer", ""), "tags": it.get("tags", []), "variacoes": it.get("variacoes", [])} for it in faq_items],
            "saudacoes": [sys_msgs.get("saudacoes", "")],
            "saudacoes_nome": [sys_msgs.get("saudacoes_nome", "")],
            "apresentacoes": [sys_msgs.get("apresentacoes", "")],
            "precos_disponivel": [sys_msgs.get("precos_disponivel", "")],
            "precos_calculado": [sys_msgs.get("precos_calculado", "")],
            "precos_cta": [sys_msgs.get("precos_cta", "")],
            "indisponivel": [sys_msgs.get("indisponivel", "")],
            "indisponivel_alternativas": [sys_msgs.get("indisponivel_alternativas", "")],
            "despedidas": [sys_msgs.get("despedidas", "")],
            "agradecimento": [sys_msgs.get("agradecimento", "")],
            "need_info_intro": [sys_msgs.get("need_info_intro", "")],
            "need_info_outro": [sys_msgs.get("need_info_outro", "")],
            "confirmar_reserva": [sys_msgs.get("confirmar_reserva", "")],
            "pix_pagamento": [sys_msgs.get("pix_pagamento", "")],
            "pix_info": [sys_msgs.get("pix_info", "")],
            "alternativas_datas_intro": [sys_msgs.get("alternativas_datas_intro", "")],
            "alternativas_datas_outro": [sys_msgs.get("alternativas_datas_outro", "")],
            "alternativas_imoveis_intro": [sys_msgs.get("alternativas_imoveis_intro", "")],
            "alternativas_imoveis_outro": [sys_msgs.get("alternativas_imoveis_outro", "")],
            "excesso_capacidade": [sys_msgs.get("excesso_capacidade", "")],
            "datas_invalidas": [sys_msgs.get("datas_invalidas", "")],
            "menu_faq": [sys_msgs.get("menu_faq", "")],
            "pergunta_imovel": [sys_msgs.get("pergunta_imovel", "")],
            "fallback": [sys_msgs.get("fallback", "")],
            "card_ask_cpf": [sys_msgs.get("card_ask_cpf", "")],
            "card_ask_details": [sys_msgs.get("card_ask_details", "")],
            "card_ask_postal": [sys_msgs.get("card_ask_postal", "")],
            "card_processing": [sys_msgs.get("card_processing", "")],
            "card_approved": [sys_msgs.get("card_approved", "")],
            "card_failed": [sys_msgs.get("card_failed", "")],
        }

    def _ensure_fresh(self):
        # Check Supabase first
        if supabase_configured():
            try:
                result = self._build_from_supabase()
                if result is not None:
                    self._data = result
                    self._mtime = "supabase"
                    return
            except Exception:
                pass
        # Check Blob next
        if blob_available():
            try:
                all_data = blob_read()
                if isinstance(all_data, dict):
                    faq_data = all_data.get("faq")
                    if isinstance(faq_data, dict):
                        self._data = faq_data
                        self._mtime = "blob"
                        return
                    if faq_data is None and "saudacoes" in all_data:
                        self._data = all_data
                        self._mtime = "blob"
                        return
            except Exception:
                pass
        # Check /tmp
        tmp_path = "/tmp/faq_premiumhost.json"
        if os.path.exists(tmp_path):
            try:
                mtime = os.path.getmtime(tmp_path)
                if mtime != self._mtime:
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                        self._mtime = mtime
            except Exception:
                pass

    def reload(self):
        self._data, self._mtime = self._load()

    def find_faq(self, text, property_key=None):
        self._ensure_fresh()
        text_lower = text.lower()
        best = None
        best_score = 0

        # Check general FAQ
        for item in self._data.get("faq", []):
            score = sum(1 for tag in item["tags"] if tag in text_lower)
            if score > best_score:
                best_score = score
                best = item

        # Check property-specific FAQ
        if property_key:
            prop_faqs = self._data.get("propriedades", {}).get(property_key, {}).get("faq", [])
            for item in prop_faqs:
                score = sum(1 for tag in item["tags"] if tag in text_lower)
                if score > best_score:
                    best_score = score
                    best = item

        if best and best_score >= 2:
            return best
        if best and best_score == 1 and len(text_lower.split()) <= 8:
            return best
        return None

    def get_random(self, key, default=None):
        self._ensure_fresh()
        items = self._data.get(key, [])
        if not items:
            return default
        return random.choice(items)

    def format_random(self, key, default=None, **kwargs):
        template = self.get_random(key, default=default)
        if not template:
            return None
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    def get_faq_topics(self):
        """Return list of FAQ topic IDs for menu display."""
        topics = []
        for item in self._data.get("faq", []):
            topics.append({"id": item["id"], "tags": item["tags"][:3]})
        return topics

    def get_faq_by_id(self, topic_id):
        for item in self._data.get("faq", []):
            if item["id"] == topic_id:
                return item
        return None

    def get_all_faq(self):
        return self._data

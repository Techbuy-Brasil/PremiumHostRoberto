import json
import os
import random
from pathlib import Path


class KnowledgeBase:
    def __init__(self, faq_path=None):
        if faq_path is None:
            faq_path = str(Path(__file__).parent / "faq.json")
        self.path = faq_path
        self._data = self._load()

    def _load(self):
        # Try /tmp first (admin edits via API persist here on Vercel)
        tmp_path = "/tmp/faq_premiumhost.json"
        if os.path.exists(tmp_path):
            try:
                with open(tmp_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Fall back to local faq.json
        if not os.path.exists(self.path):
            return {"faq": [], "saudacoes": [], "apresentacoes": [], "precos_disponivel": [],
                    "precos_calculado": [], "indisponivel": [], "despedidas": [], "agradecimento": []}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def reload(self):
        self._data = self._load()

    def find_faq(self, text, property_key=None):
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
        items = self._data.get(key, [])
        if not items:
            return default
        return random.choice(items)

    def format_random(self, key, **kwargs):
        template = self.get_random(key)
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

    def get_all_faq(self):
        return self._data

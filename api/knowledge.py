import json
import os
import random
from pathlib import Path

from blob_store import blob_get_key, blob_read, blob_available


class KnowledgeBase:
    def __init__(self, faq_path=None):
        if faq_path is None:
            faq_path = str(Path(__file__).parent / "faq.json")
        self.path = faq_path
        self._data, self._mtime = self._load()

    def _load(self):
        # Try Vercel Blob first (persists across all instances)
        if blob_available():
            try:
                all_data = blob_read()
                if isinstance(all_data, dict):
                    faq_data = all_data.get("faq")
                    if isinstance(faq_data, dict):
                        return faq_data, "blob"
                    # Legacy: flat blob with FAQ at top level
                    if faq_data is None and "saudacoes" in all_data:
                        return all_data, "blob"
            except Exception:
                pass

        # Try /tmp next (admin edits via API persist here on Vercel)
        tmp_path = "/tmp/faq_premiumhost.json"
        if os.path.exists(tmp_path):
            try:
                with open(tmp_path, "r", encoding="utf-8") as f:
                    return json.load(f), os.path.getmtime(tmp_path)
            except Exception:
                pass

        # Fall back to local faq.json
        if not os.path.exists(self.path):
            return {"faq": [], "saudacoes": [], "apresentacoes": [], "precos_disponivel": [],
                    "precos_calculado": [], "indisponivel": [], "despedidas": [], "agradecimento": []}, None
        try:
            mtime = os.path.getmtime(self.path) if os.path.exists(self.path) else None
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f), mtime
        except Exception:
            return {}, None

    def _ensure_fresh(self):
        # Check Blob first
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

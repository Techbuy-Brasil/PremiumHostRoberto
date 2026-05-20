from datetime import datetime

class ConversationStore:
    def __init__(self, data_dir=None):
        self._guests = {}

    def get_guest(self, guest_id):
        return self._guests.get(guest_id, {"guest_id": guest_id, "conversations": [], "preferences": {}})

    def save_guest(self, data):
        self._guests[data["guest_id"]] = data

    def add_conversation(self, guest_id, message, role="guest"):
        data = self.get_guest(guest_id)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
        }
        data["conversations"].append(entry)
        self.save_guest(data)
        return data

    def update_preferences(self, guest_id, preferences):
        data = self.get_guest(guest_id)
        data["preferences"].update(preferences)
        self.save_guest(data)

    def get_recent_quotes(self, guest_id, limit=5):
        data = self.get_guest(guest_id)
        quotes = [c for c in data["conversations"] if "quote" in c]
        return quotes[-limit:]

    def update_conversion_status(self, guest_id, status):
        data = self.get_guest(guest_id)
        data["conversion_status"] = status
        data["conversion_date"] = datetime.now().isoformat()
        self.save_guest(data)

    def get_stats(self):
        stats = {
            "total_guests": len(self._guests),
            "total_conversations": 0,
            "conversions": 0,
            "quotes_sent": 0,
        }
        for guest_id, data in self._guests.items():
            stats["total_conversations"] += len(data.get("conversations", []))
            if data.get("conversion_status") == "booked":
                stats["conversions"] += 1
            quotes = [c for c in data.get("conversations", []) if "quote" in c]
            stats["quotes_sent"] += len(quotes)
        return stats

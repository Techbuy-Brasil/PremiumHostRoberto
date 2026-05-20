import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


class Property:
    def __init__(self, key, data):
        self.key = key
        self.id = data["id"]
        self.name = data["name"]
        self.short_name = data["short_name"]
        self.location = data["location"]
        self.address = data["address"]
        self.capacity = data["capacity"]
        self.bedrooms = data["bedrooms"]
        self.beds = data["beds"]
        self.bathrooms = data["bathrooms"]
        self.base_price = data["base_price"]
        self.base_guests = data["base_guests"]
        self.extra_guest_fee = data["extra_guest_fee"]
        self.cleaning_fee = data["cleaning_fee"]
        self.amenities = data["amenities"]
        self.description = data["description"]
        self.holiday_packages = data.get("holiday_packages", {})

    def get_holiday_package(self, package_key):
        return self.holiday_packages.get(package_key)

    def summary(self):
        return (
            f"{self.name}\n"
            f"  Localizacao: {self.location}\n"
            f"  Capacidade: {self.capacity} hospedes\n"
            f"  {self.bedrooms} quarto(s), {self.beds} cama(s), {self.bathrooms} banheiro(s)\n"
            f"  Diaria base: R$ {self.base_price:.0f} (ate {self.base_guests} hospedes)\n"
            f"  Taxa hospede extra: R$ {self.extra_guest_fee:.0f}/pessoa/noite\n"
            f"  Taxa de limpeza: {'Gratis' if self.cleaning_fee == 0 else f'R$ {self.cleaning_fee:.0f}'}\n"
        )

    def amenities_text(self):
        return "\n".join(f"  + {a}" for a in self.amenities)


class PropertyManager:
    def __init__(self, config_path=None):
        path = config_path or CONFIG_PATH
        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.properties = {}
        for key, data in self.config["properties"].items():
            self.properties[key] = Property(key, data)

    def get_property(self, key):
        return self.properties.get(key)

    def list_properties(self):
        return list(self.properties.keys())

    def search_by_name(self, term):
        term = term.lower()
        results = []
        for p in self.properties.values():
            if term in p.name.lower() or term in p.short_name.lower() or term in p.location.lower():
                results.append(p)
        return results

    def get_pricing_rules(self):
        return self.config.get("pricing_rules", {})

    def get_holidays(self):
        h = {}
        h["nacional"] = self.config.get("holidays_br", {})
        h["estadual"] = self.config.get("holidays_ba", {})
        h["municipal"] = self.config.get("holidays_salvador", {})
        return h

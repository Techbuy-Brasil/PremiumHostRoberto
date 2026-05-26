from datetime import date
import json
import os

from blob_store import blob_get_key
from supabase_db import configured as supabase_configured
from supabase_db import get_pricing_config, get_property_overrides, get_date_overrides


PRECOS_TMP = "/tmp/precos_premiumhost.json"


def _load_overrides():
    if supabase_configured():
        try:
            cfg = get_pricing_config()
            if cfg:
                props = get_property_overrides()
                date_ovr = get_date_overrides()
                properties = {}
                for pk, pv in props.items():
                    p = dict(pv)
                    p.pop("property_key", None)
                    p.pop("updated_at", None)
                    properties[pk] = {k: v for k, v in p.items() if v is not None}
                date_overrides = []
                for d in date_ovr:
                    date_overrides.append({
                        "start": d["start_date"],
                        "end": d["end_date"],
                        "multiplier": float(d["multiplier"]),
                    })
                return {"general": cfg, "properties": properties, "date_overrides": date_overrides}
        except Exception:
            pass
    blob = blob_get_key("pricing")
    if blob is not None:
        return blob
    if os.path.exists(PRECOS_TMP):
        try:
            with open(PRECOS_TMP, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


class PricingEngine:
    def __init__(self, property_obj, holiday_calendar, overrides=None):
        self.property = property_obj
        self.calendar = holiday_calendar
        self._overrides = overrides or _load_overrides()
        self._prop_overrides = self._overrides.get("properties", {}).get(property_obj.key, {})
        self._general = self._overrides.get("general", {})
        self._date_overrides = self._overrides.get("date_overrides", [])
        hs_months = self._general.get("high_season_months")
        if hs_months:
            self.calendar.high_season_months = hs_months
        min_default = self._general.get("min_nights_default")
        min_hs = self._general.get("min_nights_high_season")
        if min_default is not None or min_hs is not None:
            cfg = self.calendar.config
            if "pricing_rules" not in cfg:
                cfg["pricing_rules"] = {}
            if "min_nights" not in cfg["pricing_rules"]:
                cfg["pricing_rules"]["min_nights"] = {}
            if min_default is not None:
                cfg["pricing_rules"]["min_nights"]["default"] = min_default
            if min_hs is not None:
                cfg["pricing_rules"]["min_nights"]["high_season"] = min_hs

    def check_availability(self, checkin, checkout):
        nights = (checkout - checkin).days
        if nights <= 0:
            return False, "Data de check-out deve ser posterior ao check-in."

        min_nights_needed = self.calendar.get_min_nights(checkin, checkout)
        if min_nights_needed > 0 and nights < min_nights_needed:
            return False, f"Período mínimo de {min_nights_needed} noites para estas datas."

        return True, None

    def check_holiday_package(self, checkin, checkout):
        nights = (checkout - checkin).days

        for pkg_key, pkg in self.property.holiday_packages.items():
            if nights == pkg["min_nights"]:
                if "carnaval" in pkg_key and self.calendar.is_carnaval_period(checkin):
                    return pkg
                if "ano_novo" in pkg_key and self.calendar.is_ano_novo_period(checkin, checkout):
                    return pkg
        return None

    def calculate_daily_rate(self, d):
        base_price = self._prop_overrides.get("base_price", self.property.base_price)
        rate = base_price

        hs_mult = self._general.get("high_season_multiplier",
                    self.calendar.config.get("pricing_rules", {}).get("high_season_multiplier", 2.0))

        weekend_surcharge = self._general.get("weekend_surcharge",
                              self.calendar.config.get("pricing_rules", {}).get("weekend_surcharge", {}))

        weekend_mult = self.calendar.get_weekend_multiplier(d, weekend_surcharge)

        if self.calendar.is_high_season(d):
            rate *= hs_mult

        if weekend_mult > 1.0:
            rate *= weekend_mult

        for od in self._date_overrides:
            start = date.fromisoformat(od["start"])
            end = date.fromisoformat(od["end"])
            if start <= d <= end:
                rate *= od.get("multiplier", 1.0)
                break

        return round(rate, 2)

    def calculate_total(self, checkin, checkout, guests=2):
        nights = (checkout - checkin).days

        holiday_pkg = self.check_holiday_package(checkin, checkout)
        if holiday_pkg:
            total = holiday_pkg["price"]
            breakdown = {
                "package": holiday_pkg["description"],
                "total": total,
                "nights": nights,
                "nightly_avg": round(total / nights, 2),
                "extra_guests_fee": 0,
                "cleaning_fee": 0,
                "guests": guests,
            }
            return breakdown

        total = 0
        daily_rates = []
        for d in self.calendar.date_range(checkin, checkout):
            rate = self.calculate_daily_rate(d)
            daily_rates.append(rate)
            total += rate

        override_base_guests = self._prop_overrides.get("base_guests", self.property.base_guests)
        override_extra_fee = self._prop_overrides.get("extra_guest_fee", self.property.extra_guest_fee)
        override_cleaning = self._prop_overrides.get("cleaning_fee", self.property.cleaning_fee)

        extra_guests = max(0, guests - override_base_guests)
        extra_fee_total = extra_guests * override_extra_fee * nights
        total += extra_fee_total

        cleaning_fee = override_cleaning
        total += cleaning_fee

        breakdown = {
            "daily_rates": daily_rates,
            "total": round(total, 2),
            "nights": nights,
            "nightly_avg": round(total / nights, 2),
            "extra_guests_fee": extra_fee_total,
            "cleaning_fee": cleaning_fee,
            "guests": guests,
            "extra_guests": extra_guests,
        }
        return breakdown

    def format_pricing_summary(self, checkin, checkout, guests=2):
        breakdown = self.calculate_total(checkin, checkout, guests)
        total = breakdown["total"]
        nights = breakdown["nights"]
        guests_count = breakdown["guests"]
        nightly_avg = breakdown["nightly_avg"]

        season_label = self.calendar.get_season_label(checkin, checkout)

        lines = []
        lines.append(f"  Período: {checkin.strftime('%d/%m/%Y')} a {checkout.strftime('%d/%m/%Y')}")
        lines.append(f"  Noites: {nights}")
        lines.append(f"  Hóspedes: {guests_count}")
        lines.append(f"  Temporada: {season_label}")

        if "package" in breakdown:
            lines.append(f"  Pacote especial: {breakdown['package']}")
            lines.append(f"  Média por noite: R$ {nightly_avg:.0f}")
        else:
            lines.append(f"  Média por noite: R$ {nightly_avg:.0f}")

        if breakdown.get("extra_guests_fee", 0) > 0:
            extra = breakdown["extra_guests"]
            lines.append(f"  Taxa de hóspedes extras ({extra} pessoa(s)): R$ {breakdown['extra_guests_fee']:.0f}")

        if breakdown.get("cleaning_fee", 0) > 0:
            lines.append(f"  Taxa de limpeza: R$ {breakdown['cleaning_fee']:.0f}")

        lines.append(f"  TOTAL: R$ {total:.0f}")

        return "\n".join(lines), breakdown

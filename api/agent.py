import re
from datetime import datetime, date, timedelta

from properties import PropertyManager
from holidays import HolidayCalendar
from pricing import PricingEngine
from templates import ResponseTemplates
from storage import ConversationStore


class Agent:
    def __init__(self, config_path=None):
        self.pm = PropertyManager(config_path)
        self.calendar = HolidayCalendar(config_path)
        self.templates = ResponseTemplates()
        self.store = ConversationStore()
        self.current_guest = None
        self.current_property = None

    def identify_guest(self, guest_name, guest_id=None):
        if not guest_id:
            guest_id = guest_name.lower().replace(" ", "_")
        self.current_guest = guest_id
        if guest_name:
            self.store.update_preferences(guest_id, {"name": guest_name, "last_contact": datetime.now().isoformat()})
        return self.store.get_guest(guest_id)

    def identify_property(self, text):
        text = text.lower()

        property_map = {
            "farol": "farol_barra_flat_214",
            "farol barra": "farol_barra_flat_214",
            "flat 214": "farol_barra_flat_214",
            "barra flat": "farol_barra_flat_214",
            "ondina": "ondina_apt_hotel_441",
            "ondina apt": "ondina_apt_hotel_441",
            "apart hotel 441": "ondina_apt_hotel_441",
            "hotel 441": "ondina_apt_hotel_441",
            "the plaza": "the_plaza_407",
            "plaza 407": "the_plaza_407",
            "plaza": "the_plaza_407",
            "smart": "smart_convencoes_509",
            "smart conven": "smart_convencoes_509",
            "convenções": "smart_convencoes_509",
            "convencoes": "smart_convencoes_509",
            "509": "smart_convencoes_509",
        }

        for keyword, prop_key in property_map.items():
            if keyword in text:
                return self.pm.get_property(prop_key)
        return None

    def extract_dates(self, text):
        month_map = {
            "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3,
            "abril": 4, "maio": 5, "junho": 6, "julho": 7,
            "agosto": 8, "setembro": 9, "outubro": 10,
            "novembro": 11, "dezembro": 12,
        }

        range_patterns = [
            r"(?:do\s+)?(?:dia\s+)?(\d{1,2})\s*(?:a|ao|ate)\s*(?:o\s+)?(?:dia\s+)?(\d{1,2})\s+de\s+([a-zçãéê]+)",
            r"(?:de\s+)?(?:dia\s+)?(\d{1,2})\s*(?:a|ao|ate)\s*(?:dia\s+)?(\d{1,2})\s+(?:de\s+)?([a-zçãéê]+)",
        ]
        for range_pat in range_patterns:
            match = re.search(range_pat, text, re.IGNORECASE)
            if match:
                d1, d2, month_name = match.groups()
                m = month_map.get(month_name.lower())
                if m:
                    year = datetime.now().year
                    try:
                        return [date(year, m, int(d1)), date(year, m, int(d2))]
                    except ValueError:
                        pass

        numeric_pattern = r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?"
        found_dates = []
        for match in re.finditer(numeric_pattern, text):
            d, m, y = int(match.group(1)), int(match.group(2)), match.group(3)
            y = int(y) if y else datetime.now().year
            if y < 100:
                y += 2000
            try:
                found_dates.append(date(y, m, d))
            except ValueError:
                pass

        if len(found_dates) >= 2:
            return sorted(found_dates)[:2]

        single_pattern = r"(\d{1,2})\s+de\s+([a-zçãéê]+)(?:\s+de\s+(\d{2,4}))?"
        single_dates = []
        for match in re.finditer(single_pattern, text, re.IGNORECASE):
            d, month_name, y = int(match.group(1)), match.group(2).lower(), match.group(3)
            m = month_map.get(month_name)
            if m:
                y = int(y) if y else datetime.now().year
                if y < 100:
                    y += 2000
                try:
                    single_dates.append(date(y, m, d))
                except ValueError:
                    pass

        if len(single_dates) >= 2:
            return sorted(single_dates)[:2]
        if single_dates:
            return single_dates[:1]
        if found_dates:
            return found_dates[:1]

        return []

    def extract_guests(self, text):
        patterns = [
            r"(\d+)\s*(?:hóspedes|hospedes|pessoas|adultos|convidados)",
            r"(?:para|somos|seremos|vão|vamos)\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def extract_name(self, text):
        name_patterns = [
            r"(?:meu nome é|me chamo|sou o|sou a|é o|é a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)",
            r"^(?:olá|ola|boa tarde|bom dia|boa noite|oi),?\s*(?:tudo bem)?\s*(?:sou|é)?\s*(?:o|a)?\s*([A-ZÀ-Ú][a-zà-ú]+)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def parse_message(self, text):
        info = {}

        name = self.extract_name(text)
        if name:
            info["name"] = name

        dates = self.extract_dates(text)
        if len(dates) >= 2:
            info["checkin"] = dates[0]
            info["checkout"] = dates[1]
        elif len(dates) == 1:
            info["checkin"] = dates[0]

        guests = self.extract_guests(text)
        if guests:
            info["guests"] = guests

        prop = self.identify_property(text)
        if prop:
            info["property"] = prop

        if re.search(r"criança|crianças|crianca|criancas|bebê|bebe|crian", text, re.IGNORECASE):
            info["has_children"] = True

        if re.search(r"pet|pets|animal|cachorro|gato|dog|cat", text, re.IGNORECASE):
            info["has_pets"] = True

        return info

    def missing_info(self, info):
        missing = []
        if "checkin" not in info:
            missing.append("checkin")
        if "checkout" not in info:
            missing.append("checkout")
        if "guests" not in info:
            missing.append("guests")
        return missing

    def suggest_alternatives(self, checkin, checkout, property_obj):
        nights = (checkout - checkin).days
        suggestions = []

        for offset in [7, 14, -7, -14]:
            new_checkin = checkin + timedelta(days=offset)
            new_checkout = checkout + timedelta(days=offset)
            if new_checkin > date.today():
                engine = PricingEngine(property_obj, self.calendar)
                avail, _ = engine.check_availability(new_checkin, new_checkout)
                if avail:
                    breakdown = engine.calculate_total(new_checkin, new_checkout)
                    label = f"{new_checkin.strftime('%d/%m')} a {new_checkout.strftime('%d/%m')}"
                    suggestions.append({
                        "label": label,
                        "total": breakdown["total"],
                        "nights": (new_checkout - new_checkin).days,
                    })

        return suggestions[:3]

    def get_all_properties_for_alternatives(self):
        alternatives = []
        for key in self.pm.list_properties():
            p = self.pm.get_property(key)
            alternatives.append({
                "name": p.name,
                "location": p.location,
                "price": p.base_price,
                "capacity": p.capacity,
                "highlights": ", ".join(p.amenities[:4]),
            })
        return alternatives

    def respond(self, message, guest_name=None, guest_id=None):
        if guest_name or guest_id:
            self.identify_guest(guest_name or guest_id, guest_id)

        self.store.add_conversation(self.current_guest or "anon", message, "guest")

        info = self.parse_message(message)

        if info.get("name") and not guest_name:
            self.store.update_preferences(self.current_guest or "anon", {"name": info["name"]})

        prop = info.get("property") or self.current_property
        if not prop:
            detected = self.identify_property(message)
            if detected:
                prop = detected
                self.current_property = prop

        if not prop:
            other_props = self.get_all_properties_for_alternatives()
            return self.templates.welcome_message()

        self.current_property = prop
        missing = self.missing_info(info)

        if missing:
            extra_info = ""
            if prop:
                extra_info = f"Voce perguntou sobre o {prop.name}! Otima escolha!\n\n"

            if info.get("checkin") and not info.get("checkout"):
                extra_info += f"Entendi que o check-in seria dia {info['checkin'].strftime('%d/%m/%Y')}. "
                extra_info += "Qual seria a data de check-out?\n\n"
                remaining = [m for m in missing if m != "checkin"]
            elif info.get("checkout") and not info.get("checkin"):
                extra_info += f"Entendi que o check-out seria dia {info['checkout'].strftime('%d/%m/%Y')}. "
                extra_info += "Qual seria a data de check-in?\n\n"
                remaining = [m for m in missing if m != "checkout"]
            else:
                remaining = missing

            if remaining:
                return f"{extra_info}{self.templates.need_info(remaining)}"

            return extra_info.strip()

        checkin = info["checkin"]
        checkout = info["checkout"]
        guests = info.get("guests", 2)

        if guests > prop.capacity:
            return (
                f"O **{prop.name}** tem capacidade máxima de **{prop.capacity} hóspedes**. "
                f"Para {guests} pessoas, que tal dar uma olhada em um dos nossos outros imóveis? "
                f"Temos opções maiores como o Farol Barra Flat ou Ondina Apart Hotel que "
                f"comportam ate 6 pessoas!"
            )

        if checkout <= checkin:
            return (
                "A data de check-out precisa ser posterior à data de check-in. "
                "Pode verificar as datas? 😊"
            )

        engine = PricingEngine(prop, self.calendar)
        avail, avail_msg = engine.check_availability(checkin, checkout)

        if not avail:
            suggestions = self.suggest_alternatives(checkin, checkout, prop)
            if suggestions:
                alt_msg = self.templates.alternative_dates(prop.name, suggestions)
                other_props = self.get_all_properties_for_alternatives()
                alt_msg += f"\n{self.templates.alternative_property(other_props)}"
                return alt_msg
            else:
                other_props = self.get_all_properties_for_alternatives()
                return (
                    f"Infelizmente nao temos disponibilidade no {prop.name} para "
                    f"{checkin.strftime('%d/%m/%Y')} a {checkout.strftime('%d/%m/%Y')} "
                    f"e nao encontrei datas proximas alternativas.\n\n"
                    f"{self.templates.alternative_property(other_props)}"
                )

        breakdown = engine.calculate_total(checkin, checkout, guests)
        total = breakdown["total"]
        nights = breakdown["nights"]
        nightly_avg = breakdown["nightly_avg"]

        season_context = self.calendar.describe_period_context(checkin, checkout)

        extra_info = ""
        if breakdown.get("extra_guests_fee", 0) > 0:
            extra_info += f"*Taxa de hóspedes extras: R$ {breakdown['extra_guests_fee']:.0f}*\n"

        response = self.templates.available(
            property_name=prop.name,
            checkin_str=checkin.strftime("%d/%m/%Y"),
            checkout_str=checkout.strftime("%d/%m/%Y"),
            total=total,
            nights=nights,
            guests=guests,
            nightly_avg=nightly_avg,
            amenities_text=prop.amenities_text(),
            season_context=season_context,
            extra_info=extra_info,
        )

        self.store.add_conversation(
            self.current_guest or "anon",
            {
                "type": "quote",
                "property": prop.name,
                "checkin": checkin.isoformat(),
                "checkout": checkout.isoformat(),
                "guests": guests,
                "total": total,
                "nights": nights,
            },
            "agent",
        )

        return response

    def get_stats(self):
        return self.store.get_stats()

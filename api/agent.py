import re
from datetime import datetime, date, timedelta

from properties import PropertyManager
from holidays import HolidayCalendar
from pricing import PricingEngine, _load_overrides
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

    faq_keywords = {
        "checkin": [
            r"check[-\s]?in", r"entrada", r"chegad", r"hospedar",
            r"fazer checkin", r"fazer o checkin", r"entregar chave",
            r"retirar chave", r"acessar", r"entrar", r"early",
            r"antes das 14", r"antes do horario",
        ],
        "checkout": [
            r"check[-\s]?out", r"sa[íi]da", r"sair", r"sair do apt",
            r"late check", r"sair mais tarde", r"depois das 11",
            r"horario de sair", r"ate que horas",
        ],
        "incluso": [
            r"inclus[oó]?", r"oferece", r"tem ", r"possui",
            r"item", r"equipad", r"acomodac", r"utensilio",
            r"cozinha", r"o que vend", r"o que esta incluso",
            r"roupa de cama", r"toalha", r"secador", r"ferro",
            r"ar condicionado", r"wifi", r"wi.fi",
            r"limpeza", r"taxa de limpeza",
        ],
        "pagamento": [
            r"pagamento", r"pagar", r"pix", r"cartao", r"cartão",
            r"credito", r"crédito", r"boleto", r"parcel",
            r"transferencia", r"transferência", r"deposito",
            r"depósito", r"forma de pagamento", r"como pagar",
            r"sinal", r"entrada", r"reserva", r"garantir",
            r"cancelamento", r"cancelar", r"reembolso",
            r"politica de cancelamento", r"politica de reserva",
        ],
        "explore": [
            r"explorar", r"salvador", r"o que fazer", r"turismo",
            r"praia", r"farol da barra", r"pelourinho", r"mercado modelo",
            r"elevador", r"restaurant", r"bar", r"balada",
            r"aeroporto", r"chegar", r"como chegar", r"transporte",
            r"uber", r"taxi", r"táxi", r"onibus", r"ônibus",
            r"localizac", r"localização", r"perto", r"proximo",
            r"próximo", r"vizinhan", r"bairro", r"regiao", r"região",
            r"passeio", r"pontos turisticos", r"o que visitar",
        ],
        "estacionamento": [
            r"estacionamento", r"garagem", r"vaga", r"carro",
            r"estacionar", r"onde estacionar", r"tem garagem",
            r"estaciona", r"parque", r"estacionamento gratis",
        ],
        "piscina": [
            r"piscina", r"lazer", r"area de lazer", r"área de lazer",
            r"piscina no predio", r"tem piscina", r"piscina gratis",
            r"academia", r"sauna", r"lazer",
        ],
        "seguranca": [
            r"seguran", r"portaria", r"cameras", r"câmeras",
            r"seguranca 24h", r"portaria 24h", r"e seguro",
            r"perigoso", r"assalto",
        ],
    }

    def _detect_faq_intent(self, text):
        text_lower = text.lower()
        for topic, patterns in self.faq_keywords.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return topic

        if re.search(r"duvida|dúvida|pergunta|perguntar|info|informaç", text_lower):
            return "menu"

        return None

    def _detect_greeting(self, text):
        return bool(re.search(r"^(oi|ola|olá|bom dia|boa tarde|boa noite|hey|há quanto tempo|e ai|e aí)",
                    text.strip(), re.IGNORECASE))

    def _detect_thanks(self, text):
        return bool(re.search(r"obrigad|valeu|brigad|agradec|thanks|thank|grato", text, re.IGNORECASE))

    def _detect_goodbye(self, text):
        return bool(re.search(r"tchau|ate logo|até logo|ate mais|até mais|flw|falou|bye|adeus|obrigad.*(?:era isso|so isso|só isso|so era)",
                    text, re.IGNORECASE))

    def _detect_booking_intent(self, text):
        return bool(re.search(r"(?:quero|gostaria de|vou|vamos) (?:reservar|confirmar|fechar|alugar|garantir)",
                    text, re.IGNORECASE))

    def _detect_pix_intent(self, text):
        return bool(re.search(r"(?:chave|como.*pix|passa.*pix|qual.*pix|pix.*qual|pagar.*pix|fazer pix|pagamento.*pix)",
                    text, re.IGNORECASE))

    def identify_guest(self, guest_name, guest_id=None):
        if not guest_id:
            guest_id = guest_name.lower().replace(" ", "_")
        self.current_guest = guest_id
        if guest_name:
            self.store.update_preferences(guest_id, {"name": guest_name, "last_contact": datetime.now().isoformat()})
        return self.store.get_guest(guest_id)

    def identify_property(self, text):
        text_lower = text.lower()

        property_map = {
            "farol barra flat 214": "farol_barra_flat_214",
            "farol barra flat": "farol_barra_flat_214",
            "barra flat 214": "farol_barra_flat_214",
            "flat 214": "farol_barra_flat_214",
            "214": "farol_barra_flat_214",

            "farol barra flat 304": "farol_barra_flat_304",
            "barra flat 304": "farol_barra_flat_304",
            "flat 304": "farol_barra_flat_304",
            "304": "farol_barra_flat_304",

            "ondina apart hotel 441": "ondina_apt_hotel_441",
            "ondina apt hotel 441": "ondina_apt_hotel_441",
            "ondina apt 441": "ondina_apt_hotel_441",
            "apart hotel 441": "ondina_apt_hotel_441",
            "hotel 441": "ondina_apt_hotel_441",
            "ondina 441": "ondina_apt_hotel_441",

            "ondina apart hotel 305": "ondina_apt_hotel_305",
            "ondina apt hotel 305": "ondina_apt_hotel_305",
            "ondina apt 305": "ondina_apt_hotel_305",
            "ondina 305": "ondina_apt_hotel_305",

            "the plaza 407": "the_plaza_407",
            "plaza 407": "the_plaza_407",
            "plaza": "the_plaza_407",

            "smart convencoes 509": "smart_convencoes_509",
            "smart convenções 509": "smart_convencoes_509",
            "smart 509": "smart_convencoes_509",
            "convencoes 509": "smart_convencoes_509",
        }

        for keyword, prop_key in property_map.items():
            if keyword in text_lower:
                return self.pm.get_property(prop_key)

        # fallback: try to find any property name mention
        for key_name in ["farol barra", "ondina", "the plaza", "plaza", "smart conven", "barra flat"]:
            if key_name in text_lower:
                for kw, pk in property_map.items():
                    if kw == key_name or kw.startswith(key_name):
                        return self.pm.get_property(pk)

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
            r"(?:para|somos|seremos|vão|vamos|sou|é)\s*(\d+)",
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

        if re.search(r"criança|crianças|crianca|criancas|bebê|bebe", text, re.IGNORECASE):
            info["has_children"] = True

        if re.search(r"pet|pets|animal|cachorro|gato|dog|cat", text, re.IGNORECASE):
            info["has_pets"] = True

        return info

    def missing_info(self, info):
        missing = []
        if "property" not in info and not self.current_property:
            missing.append("property")
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

        # Handle social/conversational intents first
        text_stripped = message.strip()

        if self._detect_greeting(text_stripped) and len(text_stripped) < 60:
            guest_data = self.store.get_guest(self.current_guest or "anon")
            saved_name = guest_data.get("preferences", {}).get("name")
            if saved_name:
                return self.templates.greeting(saved_name)
            # check if message has a name
            name = self.extract_name(text_stripped)
            if name:
                self.store.update_preferences(self.current_guest or "anon", {"name": name})
                return self.templates.greeting(name)
            # simple greeting with no name, check if we already know the guest
            if guest_id and len(guest_data.get("conversations", [])) > 1:
                return self.templates.greeting()
            return self.templates.welcome_message()

        if self._detect_thanks(text_stripped):
            return self.templates.thanks_reply()

        if self._detect_goodbye(text_stripped):
            return self.templates.goodbye()

        # Parse for structured info (dates, property, guests)
        info = self.parse_message(text_stripped)
        if info.get("name"):
            self.store.update_preferences(self.current_guest or "anon", {"name": info["name"]})

        has_quote_info = bool(info.get("property") and info.get("checkin")) or \
                         bool(self.current_property and info.get("checkin") and info.get("checkout"))

        # Only fall through to FAQ if there's no pricing info in the message
        if not has_quote_info:
            faq_topic = self._detect_faq_intent(text_stripped)
            if faq_topic:
                if faq_topic == "menu":
                    return self.templates.faq_menu()
                resposta = self.templates.faq_resposta(faq_topic)
                if resposta:
                    return resposta

        # Pix / payment info
        if self._detect_pix_intent(text_stripped):
            return self.templates.pix_info()

        prop = info.get("property") or self.current_property
        if not prop:
            detected = self.identify_property(message)
            if detected:
                prop = detected
                self.current_property = prop

        if not prop:
            other_props = self.get_all_properties_for_alternatives()
            return self.templates.no_property_match()

        self.current_property = prop

        # Check booking confirmation intent
        if self._detect_booking_intent(text_stripped) and hasattr(self, '_last_quote'):
            return self.templates.confirm_booking(
                prop.name,
                self._last_quote["checkin"].strftime("%d/%m/%Y"),
                self._last_quote["checkout"].strftime("%d/%m/%Y"),
                self._last_quote["total"],
            )

        missing = self.missing_info(info)

        if missing:
            extra = ""
            if info.get("checkin") and not info.get("checkout"):
                extra = f"Entendi que o check-in seria dia {info['checkin'].strftime('%d/%m/%Y')}. "
                remaining = [m for m in missing if m != "checkin"]
            elif info.get("checkout") and not info.get("checkin"):
                extra = f"Entendi que o check-out seria dia {info['checkout'].strftime('%d/%m/%Y')}. "
                remaining = [m for m in missing if m != "checkout"]
            else:
                remaining = missing

            if remaining:
                return f"{extra}{self.templates.need_info(remaining)}"
            return extra.strip()

        checkin = info["checkin"]
        checkout = info["checkout"]
        guests = info.get("guests", 2)

        if guests > prop.capacity:
            return self.templates.over_capacity(prop.name, prop.capacity, guests)

        if checkout <= checkin:
            return self.templates.invalid_dates()

        overrides = _load_overrides()
        engine = PricingEngine(prop, self.calendar, overrides)
        avail, avail_msg = engine.check_availability(checkin, checkout)

        if not avail:
            suggestions = self.suggest_alternatives(checkin, checkout, prop)
            if suggestions:
                response = self.templates.unavailable(prop.name,
                    checkin.strftime("%d/%m/%Y"), checkout.strftime("%d/%m/%Y"))
                response += f"\n\n{self.templates.alternative_dates(prop.name, suggestions)}"
                return response
            else:
                other_props = self.get_all_properties_for_alternatives()
                response = self.templates.unavailable(prop.name,
                    checkin.strftime("%d/%m/%Y"), checkout.strftime("%d/%m/%Y"))
                response += f"\n\n{self.templates.alternative_property(other_props)}"
                return response

        breakdown = engine.calculate_total(checkin, checkout, guests)
        total = breakdown["total"]
        nights = breakdown["nights"]
        nightly_avg = breakdown["nightly_avg"]

        # Store for booking confirmation
        self._last_quote = {
            "checkin": checkin,
            "checkout": checkout,
            "total": total,
            "property": prop,
        }

        season_context = self.calendar.describe_period_context(checkin, checkout)

        extra_info = ""
        if breakdown.get("extra_guests_fee", 0) > 0:
            extra_info += f"*Taxa de hóspedes extras: R$ {breakdown['extra_guests_fee']:.0f}*"

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

import re
from datetime import datetime, date, timedelta

from properties import PropertyManager
from holidays import HolidayCalendar
from pricing import PricingEngine, _load_overrides
from templates import ResponseTemplates
from storage import ConversationStore
from knowledge import KnowledgeBase


class Agent:
    def __init__(self, config_path=None):
        self.pm = PropertyManager(config_path)
        self.calendar = HolidayCalendar(config_path)
        self.knowledge = KnowledgeBase()
        self.templates = ResponseTemplates(self.knowledge)
        self.store = ConversationStore()
        self.current_guest = None
        self.current_property = None

    def _get_memory(self, guest_id):
        """Get remembered conversation context for this guest."""
        data = self.store.get_guest(guest_id)
        return data.get("preferences", {}).get("conversation_memory", {})

    def _save_memory(self, guest_id, memory):
        """Save conversation context for this guest."""
        prefs = self.store.get_guest(guest_id).get("preferences", {})
        prefs["conversation_memory"] = memory
        self.store.update_preferences(guest_id, prefs)

    def _get_card_state(self, guest_id):
        prefs = self.store.get_guest(guest_id).get("preferences", {})
        return prefs.get("card_state")

    def _set_card_state(self, guest_id, state):
        prefs = self.store.get_guest(guest_id).get("preferences", {})
        if state is None:
            prefs.pop("card_state", None)
        else:
            prefs["card_state"] = state
        self.store.update_preferences(guest_id, prefs)

    def _save_lead(self, name, phone, property_name, checkin, checkout, total, guests, status="pre_reserva"):
        """Save a lead to Supabase system_messages."""
        try:
            from supabase_db import upsert_system_message
            import json
            key = f"_lead_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.current_guest or 'anon'}"
            data = {
                "nome": name, "phone": phone,
                "property": property_name, "checkin": str(checkin), "checkout": str(checkout),
                "total": total, "guests": guests, "status": status,
                "created_at": datetime.now().isoformat()
            }
            upsert_system_message(key, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            print(f"Save lead error: {e}", flush=True)

    def _extract_name_phone(self, text):
        """Extract name and phone from user message. Returns (name, phone) or (None, None)."""
        phone = None
        phone_pat = r"(?:\+?55)?\s*\(?\d{2}\)?\s*\d{4,5}-?\d{4}"
        m = re.search(phone_pat, text)
        if m:
            phone = m.group(0).strip()
        if not phone:
            return None, None
        # Name: try extract_name patterns first
        name = self.extract_name(text)
        if not name:
            before = text[:text.find(m.group(0))].strip()
            words = [w for w in before.split() if len(w) > 1 and not re.search(r"\d", w)]
            fillers = {"meu", "minha", "nome", "eh", "e", "de", "da", "do", "em", "para", "com", "por", "os", "as", "um", "uma", "no", "na", "sou", "o", "a", "te", "seu", "sua"}
            words = [w for w in words if w.lower() not in fillers]
            if words:
                name = " ".join(words[:2])
        return name or "Cliente", phone

    def _detect_faq_intent(self, text):
        """Use KnowledgeBase to find the best FAQ match."""
        text_lower = text.lower()
        if re.search(r"duvida|dúvida|pergunta|perguntar|info|informaç|sobre o que|o que você sabe", text_lower):
            return "menu"

        # Use KnowledgeBase for smart matching (reflects admin edits)
        faq_item = self.knowledge.find_faq(text)
        if faq_item:
            return faq_item["id"]

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

    def _detect_card_intent(self, text):
        return bool(re.search(r"\b(cartao|cartão|credito|crédito|parcelado|parcela|dividir|card|debito|débito)\b",
                    text, re.IGNORECASE))

    def identify_guest(self, guest_name, guest_id=None):
        if not guest_id:
            guest_id = guest_name.lower().replace(" ", "_")
        # Reset per-user state when guest changes
        if guest_id != self.current_guest:
            self.current_property = None
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
            "ondina apt 441": "ondina_apt_hotel_441",
            "apart hotel 441": "ondina_apt_hotel_441",
            "ondina 441": "ondina_apt_hotel_441",
            "441": "ondina_apt_hotel_441",
            "ondina apart hotel 305": "ondina_apt_hotel_305",
            "ondina apt 305": "ondina_apt_hotel_305",
            "ondina 305": "ondina_apt_hotel_305",
            "the plaza 407": "the_plaza_407",
            "plaza 407": "the_plaza_407",
            "plaza": "the_plaza_407",
            "407": "the_plaza_407",
            "smart convencoes 509": "smart_convencoes_509",
            "smart convenções 509": "smart_convencoes_509",
            "smart 509": "smart_convencoes_509",
            "convencoes 509": "smart_convencoes_509",
            "509": "smart_convencoes_509",
        }

        for keyword, prop_key in property_map.items():
            if keyword in text_lower:
                return self.pm.get_property(prop_key)

        for key_name in ["farol barra", "ondina", "the plaza", "smart conven", "barra flat"]:
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
            r"(?:para|somos|seremos|serão|vão|vamos)\s+(\d+)",
            r"(?:sou|é)\s+(\d+)\s+(?:pessoas?|hospedes|hóspedes)",
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

    def parse_message(self, text, guest_id=None):
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

        gid = self.current_guest or "anon"
        self.store.add_conversation(gid, message, "guest")

        text_stripped = message.strip()

        # --- SOCIAL INTENTS ---
        if self._detect_greeting(text_stripped) and len(text_stripped) < 60:
            guest_data = self.store.get_guest(gid)
            saved_name = guest_data.get("preferences", {}).get("name")
            if saved_name:
                return self.templates.greeting(saved_name)
            name = self.extract_name(text_stripped)
            if name:
                self.store.update_preferences(gid, {"name": name})
                return self.templates.greeting(name)
            if gid and len(guest_data.get("conversations", [])) > 1:
                return self.templates.greeting()
            return self.templates.welcome_message()

        if self._detect_thanks(text_stripped):
            return self.templates.thanks_reply()

        if self._detect_goodbye(text_stripped):
            return self.templates.goodbye()

        # --- CARD PAYMENT FLOW (state machine) ---
        card_state = self._get_card_state(gid)
        if card_state:
            state = card_state.get("step")
            if state == "awaiting_cpf":
                cpf_match = re.search(r"(\d{11})", text_stripped)
                if cpf_match:
                    cpf = cpf_match.group(1)
                    card_state["cpf"] = cpf
                    card_state["step"] = "awaiting_details"
                    self._set_card_state(gid, card_state)
                    return self.templates.card_ask_details()
                return "CPF invalido! Digite apenas os numeros do CPF (11 digitos):"

            elif state == "awaiting_details":
                parts = [p.strip() for p in text_stripped.replace(";", ",").split(",")]
                if len(parts) >= 4:
                    card_state["holder"] = parts[0]
                    card_state["number"] = re.sub(r"\D", "", parts[1])
                    card_state["expiry"] = parts[2].strip()
                    card_state["cvv"] = re.sub(r"\D", "", parts[3])
                    card_state["step"] = "awaiting_postal"
                    self._set_card_state(gid, card_state)
                    return self.templates.card_ask_postal()
                return "Nao entendi! Mande neste formato:\n\n**Nome do titular, Numero do cartao, Validade (mes/ano), CVV**\n\nExemplo: Joao Silva, 4111111111111111, 12/2028, 123"

            elif state == "awaiting_postal":
                parts = [p.strip() for p in text_stripped.replace(";", ",").split(",")]
                if len(parts) >= 1:
                    cep = re.sub(r"\D", "", parts[0])
                    addr_num = re.sub(r"\D", "", parts[1]) if len(parts) > 1 else "0"
                    if len(cep) == 8:
                        card_state["postal"] = cep
                        card_state["address_number"] = addr_num
                        # Process payment via Asaas
                        try:
                            import asaas
                            q = getattr(self, '_last_quote', None)
                            if not q:
                                self._set_card_state(gid, None)
                                return "Desculpe, perdi os dados da reserva. Pode comecar de novo? :)"
                            card_total = q["total"] * 1.2
                            # Parse expiry
                            exp_parts = card_state["expiry"].replace("/", " ").split()
                            exp_month = exp_parts[0].zfill(2) if exp_parts else "12"
                            exp_year = exp_parts[1] if len(exp_parts) > 1 else str(datetime.now().year + 1)
                            if len(exp_year) == 2:
                                exp_year = "20" + exp_year
                            # Create or find customer
                            guest_data = self.store.get_guest(gid)
                            prefs = guest_data.get("preferences", {})
                            guest_name = prefs.get("name", card_state.get("holder", "Hospede"))
                            guest_phone = prefs.get("phone", "")
                            customer = asaas.find_customer_by_cpf(card_state["cpf"])
                            if not customer:
                                customer = asaas.create_customer(
                                    name=guest_name,
                                    email="",
                                    cpf_cnpj=card_state["cpf"],
                                    phone=guest_phone,
                                    postal_code=cep,
                                    address_number=addr_num,
                                )
                            if not customer or "id" not in customer:
                                err = asaas.get_last_error()
                                self._set_card_state(gid, None)
                                return self.templates.card_failed(err or "Erro ao criar cliente no Asaas")
                            # Create payment
                            payment = asaas.create_payment(
                                customer_id=customer["id"],
                                value=card_total,
                                due_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                                description=f"Reserva {q['property'].name} - {q['checkin'].strftime('%d/%m')} a {q['checkout'].strftime('%d/%m')}",
                                installments=card_state.get("installments", 1),
                                card_holder_name=card_state["holder"],
                                card_number=card_state["number"],
                                expiry_month=exp_month,
                                expiry_year=exp_year,
                                ccv=card_state["cvv"],
                                holder_name=guest_name,
                                holder_email="",
                                holder_cpf=card_state["cpf"],
                                holder_phone=guest_phone,
                                holder_postal_code=cep,
                                holder_address_number=addr_num,
                            )
                            self._set_card_state(gid, None)
                            if payment and payment.get("id"):
                                if payment.get("status") in ("CONFIRMED", "RECEIVED"):
                                    return self.templates.card_approved(payment["id"], card_total, card_state.get("installments", 1))
                                return self.templates.card_failed(f"Status: {payment.get('status', 'desconhecido')}")
                            err = asaas.get_last_error()
                            return self.templates.card_failed(err or "Erro ao processar pagamento")
                        except Exception as e:
                            self._set_card_state(gid, None)
                            print(f"Card payment error: {e}", flush=True)
                            return self.templates.card_failed(str(e))
                    return "CEP invalido! Digite o CEP com 8 digitos (ex: 40000000) e o numero separado por virgula."
                return "Mande o CEP e numero do endereco separados por virgula (ex: 40000000, 123)"

        # --- CARD INTENT DETECTION ---
        if self._detect_card_intent(text_stripped):
            if not hasattr(self, '_last_quote'):
                # Try to restore from guest preferences
                prefs = self.store.get_guest(gid).get("preferences", {})
                lq = prefs.get("last_quote")
                if lq:
                    prop = self.pm.get_property(lq.get("property_key", ""))
                    if prop:
                        self._last_quote = {
                            "checkin": date.fromisoformat(lq["checkin"]) if isinstance(lq["checkin"], str) else lq["checkin"],
                            "checkout": date.fromisoformat(lq["checkout"]) if isinstance(lq["checkout"], str) else lq["checkout"],
                            "total": lq["total"],
                            "property": prop,
                        }
            if hasattr(self, '_last_quote'):
                q = self._last_quote
                card_total = q["total"] * 1.2
                self._set_card_state(gid, {
                    "step": "awaiting_cpf",
                    "installments": 1,
                    "total": card_total,
                })
                return self.templates.card_ask_cpf(card_total)
            # No quote found — ask user to request one first
            return "Para pagar no cartão, preciso antes fazer uma cotação. Me informe o imóvel, check-in, check-out e número de hóspedes!"

        # --- PARSE MESSAGE ---
        info = self.parse_message(text_stripped, gid)
        if info.get("name"):
            self.store.update_preferences(gid, {"name": info["name"]})

        # --- FAQ CHECK (based ONLY on current message, not memory) ---
        has_quote_in_current_msg = bool(info.get("checkin") and info.get("checkout"))
        if not has_quote_in_current_msg:
            faq_topic = self._detect_faq_intent(text_stripped)
            if faq_topic:
                if faq_topic == "menu":
                    return self.templates.faq_menu()
                resposta = self.templates.faq_resposta(faq_topic)
                if resposta:
                    return resposta

        # Detect "outro imóvel", "outra opção", etc. → clear property before memory merge
        want_other_property = bool(re.search(r"\b(outro|outra|outras|outros|alternativa|outras? opc)[a-z]*\s*(imovel|imóvel|apartamento|opcao|opção)?", text_stripped, re.IGNORECASE))
        if want_other_property:
            self.current_property = None

        # Detect "outra data", "outro período" → clear dates
        clear_dates = bool(re.search(r"\b(outra|outro|outras|outros|diferente|nova|novo)\s*(data|datas|periodo|período|dia|dias)", text_stripped, re.IGNORECASE))

        # Merge with saved memory (skip property_key if user asked for another property, skip dates if asking for other dates)
        memory = self._get_memory(gid)
        if not info.get("checkin") and memory.get("checkin") and not clear_dates:
            info["checkin"] = date.fromisoformat(memory["checkin"]) if isinstance(memory["checkin"], str) else memory["checkin"]
        if not info.get("checkout") and memory.get("checkout") and not clear_dates:
            info["checkout"] = date.fromisoformat(memory["checkout"]) if isinstance(memory["checkout"], str) else memory["checkout"]
        if not info.get("guests") and memory.get("guests"):
            info["guests"] = memory["guests"]
        if not info.get("property") and not self.current_property and memory.get("property_key") and not want_other_property:
            self.current_property = self.pm.get_property(memory["property_key"])

        # Persist current known info to memory (before any early return)
        partial = {}
        if info.get("checkin"):
            partial["checkin"] = info["checkin"].isoformat() if hasattr(info["checkin"], "isoformat") else info["checkin"]
        if info.get("checkout"):
            partial["checkout"] = info["checkout"].isoformat() if hasattr(info["checkout"], "isoformat") else info["checkout"]
        if info.get("guests"):
            partial["guests"] = info["guests"]
        if info.get("property"):
            partial["property_key"] = info["property"].key
        if partial:
            self._save_memory(gid, partial)

        # --- PIX INFO (before property gate too) ---
        if self._detect_pix_intent(text_stripped):
            return self.templates.pix_info()

        # --- PROPERTY IDENTIFICATION ---
        # Try numbered selection (1-5) BEFORE falling back to current_property
        num_map = {"1": "farol_barra_flat_214", "2": "farol_barra_flat_304",
                   "3": "ondina_apt_hotel_441", "4": "the_plaza_407", "5": "smart_convencoes_509"}
        stripped = text_stripped.strip()
        if stripped in num_map:
            prop_from_num = self.pm.get_property(num_map[stripped])
        else:
            prop_from_num = None

        prop = info.get("property") or prop_from_num or self.current_property
        prop_identified_now = False
        if not prop:
            detected = self.identify_property(message)
            if detected:
                prop = detected
                self.current_property = prop
                prop_identified_now = True

        if not prop:
            other_props = self.get_all_properties_for_alternatives()
            return self.templates.ask_property()

        self.current_property = prop

        # --- BOOKING INTENT ---
        if self._detect_booking_intent(text_stripped) and hasattr(self, '_last_quote'):
            return self.templates.confirm_booking(
                prop.name,
                self._last_quote["checkin"].strftime("%d/%m/%Y"),
                self._last_quote["checkout"].strftime("%d/%m/%Y"),
                self._last_quote["total"],
            )

        # --- LEAD DETECTION (user providing personal info after booking confirmation) ---
        if hasattr(self, '_last_quote'):
            name, phone = self._extract_name_phone(text_stripped)
            if name and phone:
                q = self._last_quote
                guests = info.get("guests", 2)
                signal = q["total"] / 2
                self._save_lead(name, phone, q["property"].name,
                                q["checkin"], q["checkout"], q["total"], guests)
                # Send email notification
                try:
                    import email_notify
                    if email_notify.configured():
                        ok = email_notify.send_lead_notification(
                            self.current_guest or "anon", name, phone,
                            q["property"].name, str(q["checkin"]), str(q["checkout"]),
                            guests, q["total"], "pre_reserva"
                        )
                        if not ok:
                            print(f"Email notify failed: {email_notify.LAST_ERROR}", flush=True)
                    else:
                        print("Email notify: SENDGRID_API_KEY not configured", flush=True)
                except Exception as e:
                    print(f"Email notify error: {e}", flush=True)
                # Generate PIX payload for 50% signal
                try:
                    from pix import gerar_pix_payload
                    pix_code = gerar_pix_payload(signal)
                    import urllib.parse
                    pix_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(pix_code)}"
                except Exception:
                    pix_code = None
                    pix_qr_url = None
                return self.templates.pix_payment(
                    q["property"].name,
                    q["checkin"].strftime("%d/%m/%Y"),
                    q["checkout"].strftime("%d/%m/%Y"),
                    q["total"], signal, name, pix_code, pix_qr_url
                )

        # --- PRICING FLOW ---
        missing = self.missing_info(info)

        # If only guests is missing and message is a bare number, use it
        # (but only if the same number wasn't already used for property identification)
        if missing == ["guests"] and not info.get("guests") and not prop_identified_now:
            is_standalone_num = re.match(r"^\s*(\d{1,2})\s*$", text_stripped)
            if is_standalone_num:
                info["guests"] = int(is_standalone_num.group(1))
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

        # Save to memory
        new_memory = {
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "guests": guests,
            "property_key": prop.key,
        }
        self._save_memory(gid, new_memory)

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

        self._last_quote = {
            "checkin": checkin,
            "checkout": checkout,
            "total": total,
            "property": prop,
        }
        # Persist last_quote in guest preferences for cross-instance resilience
        prefs = self.store.get_guest(gid).get("preferences", {})
        prefs["last_quote"] = {
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "total": total,
            "property_key": prop.key,
        }
        self.store.update_preferences(gid, prefs)

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

        self.store.add_conversation(gid, {
            "type": "quote",
            "property": prop.name,
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "guests": guests,
            "total": total,
            "nights": nights,
        }, "agent")

        return response

    def get_stats(self):
        return self.store.get_stats()

import random


class ResponseTemplates:
    def __init__(self, knowledge=None):
        self.knowledge = knowledge

    def _r(self, key, default=None, **kwargs):
        if self.knowledge:
            return self.knowledge.format_random(key, default=default, **kwargs)
        return default

    def _choose(self, alternatives):
        return random.choice(alternatives)

    def welcome_message(self):
        return self._r("apresentacoes",
            "Oi! Aqui é o Roberto, da PremiumHost! :)\n\n"
            "Temos apartamentos incríveis em Salvador — na Barra e em Ondina, "
            "pé na areia ou pertinho de tudo.\n\n"
            "Me conta: qual imóvel te interessou, quantas pessoas vão ficar "
            "e quais datas você está pensando? Assim já faço as contas pra você!"
        )

    def greeting(self, name=None):
        if name:
            return self._choose([
                f"Oi {name}, prazer! Aqui é o Roberto da PremiumHost! "
                "Como posso te ajudar com a sua hospedagem em Salvador?",
                f"Fala {name}! Beleza? Aqui é o Roberto :) "
                "Como posso te ajudar?",
                f"Oi {name}! Bem-vindo à PremiumHost! Aqui é o Roberto. "
                "Me conta o que você está procurando!",
            ])
        return self._r("saudacoes",
            "Oi! Aqui é o Roberto :) Tudo bem?\n\n"
            "Quer saber sobre disponibilidade, preços, ou tem alguma dúvida "
            "sobre os apartamentos? Pode perguntar à vontade!"
        )

    def thanks_reply(self):
        return self._r("agradecimento",
            "Imagina! É um prazer ajudar :)",
        ) + self._choose([
            " Se precisar de mais alguma coisa, é só chamar! "
            "Tô sempre por aqui ou no WhatsApp (71) 99290-0979.",
            " Se surgir qualquer dúvida, pode perguntar ou me mandar "
            "um zap no (71) 99290-0979.",
            " Tô aqui pra isso! Se precisar de mais ajuda, é só falar :)",
        ])

    def goodbye(self):
        return self._r("despedidas",
            "Foi um prazer conversar com você! :)"
            "\n\nQuando quiser, é só me chamar de novo. "
            "E se precisar falar mais rápido, meu WhatsApp é (71) 99290-0979. "
            "Um abraço!"
        )

    def need_info(self, missing_fields, known_info=None):
        msg = "Claro! Só mais algumas informações pra eu fazer a simulação certinha:\n\n"
        for field in missing_fields:
            if field == "property":
                msg += "* Qual apartamento você tem interesse?\n"
            elif field == "checkin":
                msg += "* Qual a data de check-in?\n"
            elif field == "checkout":
                msg += "* Qual a data de check-out?\n"
            elif field == "guests":
                msg += "* Quantos hóspedes vão ficar?\n"
        msg += "\nVou esperar aqui!"
        return msg

    def available(self, property_name, checkin_str, checkout_str, total, nights, guests, nightly_avg, amenities_text, season_context, extra_info=""):
        intro = self._r("precos_disponivel", "Boas notícias! O {nome} está disponível! :)",
                       nome=property_name)
        calc = self._r("precos_calculado",
            "Pra {guests} hóspedes, do dia {checkin} ao {checkout} "
            "({nights} noites), o valor total fica em **R$ {total}** "
            "— uma média de R$ {media}/noite.",
            guests=guests, checkin=checkin_str, checkout=checkout_str,
            nights=nights, total=f"{total:.0f}", media=f"{nightly_avg:.0f}")

        msg = f"{intro}\n\n{calc}"
        if extra_info:
            msg += f"\n\n{extra_info}"
        msg += (
            f"\n\nO apartamento conta com:\n{amenities_text}"
            f"\n\n{season_context}"
            "\n\n"
            "Se quiser garantir, é só me avisar que eu passo as instruções "
            "de reserva e pagamento :)"
        )
        return msg

    def unavailable(self, property_name, checkin_str, checkout_str):
        intro = self._r("indisponivel", "Poxa, infelizmente o {nome} já está reservado para o período :(",
                       nome=property_name)
        return (
            f"{intro}\n\n"
            "Mas calma! Posso sugerir algumas alternativas:\n\n"
            "* Datas próximas no mesmo imóvel\n"
            "* Outro apartamento nosso — temos opções parecidas\n\n"
            "O que você prefere?"
        )

    def alternative_dates(self, property_name, suggested_periods):
        msg = f"Que tal uma dessas opções no {property_name}?\n\n"
        for i, period in enumerate(suggested_periods, 1):
            msg += f"{i}. {period['label']} — R$ {period['total']:.0f} ({period['nights']} noites)\n"
        msg += "\nSe interessou por alguma? Ou prefere ver outros imóveis?"
        return msg

    def alternative_property(self, properties_list):
        msg = "Temos outras opções igualmente legais:\n\n"
        for p in properties_list:
            msg += f"* **{p['name']}** — {p['location']}\n"
            msg += f"  A partir de R$ {p['price']:.0f}/noite · até {p['capacity']} hóspedes\n\n"
        msg += "Se interessou por algum? Me fala que eu faço a simulação!"
        return msg

    def over_capacity(self, property_name, capacity, guests):
        return (
            f"Olha, o {property_name} comporta no máximo {capacity} hóspedes. "
            f"Pra {guests} pessoas infelizmente não vai dar :(\n\n"
            "Mas temos outras opções maiores! O **Farol Barra Flat 214** ou o "
            "**Ondina Apart Hotel 441** comportam até 6 pessoas.\n\n"
            "Quer que eu veja a disponibilidade pra algum deles?"
        )

    def invalid_dates(self):
        return (
            "A data de check-out precisa ser depois do check-in, hein! :)"
            "\n\nPode verificar e me mandar as datas certinhas?"
        )

    def faq_resposta(self, topic=None):
        if topic and self.knowledge:
            item = self.knowledge.get_faq_by_id(topic)
            if item:
                if item.get("variacoes"):
                    return random.choice(item["variacoes"])
                return item.get("resposta")
        return None

    def faq_menu(self):
        return self._r("menu_faq",
            "Pergunta pra mim! Posso te ajudar com:\n\n"
            "• Horários de check-in / check-out\n"
            "• O que está incluso\n"
            "• Formas de pagamento e cancelamento\n"
            "• Localização e pontos turísticos\n"
            "• Estacionamento / Piscina / Lazer\n"
            "• Pets e crianças\n"
            "• Como chegar do aeroporto\n"
            "• Supermercados e farmácias perto\n\n"
            "É só perguntar! :)"
        )

    def ask_property(self):
        return self._r("pergunta_imovel",
            "Entendi! Qual imóvel você está interessado?\n\n"
            "• Farol da Barra Flat 214\n"
            "• Farol da Barra Flat 304\n"
            "• Ondina Apart Hotel 441\n"
            "• The Plaza 407\n"
            "• Smart Convenções 509\n\n"
            "Me fala qual deles que eu faço as contas pra você! :)"
        )

    def fallback(self):
        return self._r("fallback",
            "Entendi! Deixa eu ver se posso ajudar...\n\n"
            "Se você estiver procurando disponibilidade, me passa: "
            "o apartamento, as datas e quantos hóspedes.\n"
            "Se for uma dúvida sobre a hospedagem, pode perguntar "
            "que eu respondo na hora! :)\n\n"
            "Ou se preferir, pode falar direto comigo no WhatsApp: "
            "(71) 99290-0979"
        )

    def confirm_booking(self, property_name, checkin_str, checkout_str, total):
        return (
            f"Perfeito! Quer confirmar a reserva do {property_name} "
            f"de {checkin_str} a {checkout_str} no valor de R$ {total:.0f}? :)\n\n"
            "Se sim, vou precisar de:\n"
            "• Nome completo\n• Número de WhatsApp\n"
            "• Sinal de 50% via PIX\n\n"
            "Após o pagamento, envio a confirmação com todas as instruções "
            "de acesso! Pode me passar os dados?"
        )

    def pix_payment(self, property_name, checkin_str, checkout_str, total, signal, guest_name, pix_code=None, pix_qr_url=None):
        return (
            f"Perfeito, {guest_name}! Sua reserva do {property_name} "
            f"de {checkin_str} a {checkout_str} no valor de R$ {total:.0f} "
            "esta quase confirmada!\n\n"
            f"Para garantir, preciso do sinal de **R$ {signal:.0f}** (50%) via PIX.\n\n"
            "Chave Pix Aleatoria\n\n"
            "**Chave PIX:** `b1b74e94-2687-4ea1-831b-6351b97e7929`\n\n"
            "Apos o pagamento, me avise aqui que ja confirmo sua reserva "
            "e envio as instrucoes de acesso! :)"
        )

    def pix_info(self):
        return (
            "Para pagamento via PIX:\n\n"
            "**Chave PIX:** `b1b74e94-2687-4ea1-831b-6351b97e7929`\n\n"
            "Me avisa quando fizer o pagamento que ja confirmo tudo! :)"
        )

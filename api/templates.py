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
            return self._r("saudacoes_nome",
                f"Oi {name}, prazer! Aqui e o Roberto da PremiumHost! "
                "Como posso te ajudar com a sua hospedagem em Salvador?")
        return self._r("saudacoes",
            "Oi! Aqui é o Roberto :) Tudo bem?\n\n"
            "Quer saber sobre disponibilidade, preços, ou tem alguma dúvida "
            "sobre os apartamentos? Pode perguntar à vontade!"
        )

    def thanks_reply(self):
        return self._r("agradecimento",
            "Imagina! E um prazer ajudar :)"
            " Se precisar de mais alguma coisa, e so chamar! "
            "To sempre por aqui ou no WhatsApp (71) 99290-0979.")

    def goodbye(self):
        return self._r("despedidas",
            "Foi um prazer conversar com você! :)"
            "\n\nQuando quiser, é só me chamar de novo. "
            "E se precisar falar mais rápido, meu WhatsApp é (71) 99290-0979. "
            "Um abraço!"
        )

    def need_info(self, missing_fields, known_info=None):
        intro = self._r("need_info_intro", "Claro! So mais algumas informacoes pra eu fazer a simulacao certinha:\n\n")
        fields_text = {"property": "* Qual apartamento voce tem interesse?\n",
                       "checkin": "* Qual a data de check-in?\n",
                       "checkout": "* Qual a data de check-out?\n",
                       "guests": "* Quantos hospedes vao ficar?\n"}
        msg = intro
        for field in missing_fields:
            msg += fields_text.get(field, "")
        msg += self._r("need_info_outro", "\nVou esperar aqui!")
        return msg

    def available(self, property_name, checkin_str, checkout_str, total, nights, guests, nightly_avg, amenities_text, season_context, extra_info=""):
        intro = self._r("precos_disponivel", "Boas noticias! O {nome} esta disponivel! :)",
                       nome=property_name)
        calc = self._r("precos_calculado",
            "Pra {guests} hospedes, do dia {checkin} ao {checkout} "
            "({nights} noites), o valor total fica em **R$ {total}** "
            "— uma media de R$ {media}/noite.",
            guests=guests, checkin=checkin_str, checkout=checkout_str,
            nights=nights, total=f"{total:.0f}", media=f"{nightly_avg:.0f}")

        cta = self._r("precos_cta",
            "\n\nSe quiser garantir, e so me avisar que eu passo as instrucoes "
            "de reserva e pagamento :)")
        msg = f"{intro}\n\n{calc}"
        if extra_info:
            msg += f"\n\n{extra_info}"
        msg += f"\n\nO apartamento conta com:\n{amenities_text}"
        msg += f"\n\n{season_context}"
        msg += cta
        return msg

    def unavailable(self, property_name, checkin_str, checkout_str):
        intro = self._r("indisponivel", "Poxa, infelizmente o {nome} ja esta reservado para o periodo :(",
                       nome=property_name)
        alt = self._r("indisponivel_alternativas",
            "\n\nMas calma! Posso sugerir algumas alternativas:\n\n"
            "* Datas proximas no mesmo imovel\n"
            "* Outro apartamento nosso — temos opcoes parecidas\n\n"
            "O que voce prefere?")
        return f"{intro}{alt}"

    def alternative_dates(self, property_name, suggested_periods):
        msg = self._r("alternativas_datas_intro", f"Que tal uma dessas opcoes no {property_name}?\n\n")
        for i, period in enumerate(suggested_periods, 1):
            msg += f"{i}. {period['label']} — R$ {period['total']:.0f} ({period['nights']} noites)\n"
        msg += self._r("alternativas_datas_outro", "\nSe interessou por alguma? Ou prefere ver outros imoveis?")
        return msg

    def alternative_property(self, properties_list):
        msg = self._r("alternativas_imoveis_intro", "Temos outras opcoes igualmente legais:\n\n")
        for p in properties_list:
            msg += f"* **{p['name']}** — {p['location']}\n"
            msg += f"  A partir de R$ {p['price']:.0f}/noite · ate {p['capacity']} hospedes\n\n"
        msg += self._r("alternativas_imoveis_outro", "Se interessou por algum? Me fala que eu faço a simulacao!")
        return msg

    def over_capacity(self, property_name, capacity, guests):
        return self._r("excesso_capacidade",
            f"Olha, o {property_name} comporta no maximo {capacity} hospedes. "
            f"Pra {guests} pessoas infelizmente nao vai dar :(\n\n"
            "Mas temos outras opcoes maiores! O **Farol Barra Flat 214** ou o "
            "**Ondina Apart Hotel 441** comportam ate 6 pessoas.\n\n"
            "Quer que eu veja a disponibilidade pra algum deles?")

    def invalid_dates(self):
        return self._r("datas_invalidas",
            "A data de check-out precisa ser depois do check-in, hein! :)"
            "\n\nPode verificar e me mandar as datas certinhas?")

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
        return self._r("confirmar_reserva",
            "Perfeito! Quer confirmar a reserva do {nome} "
            "de {checkin} a {checkout} no valor de R$ {total:.0f}? :)\n\n"
            "Se sim, vou precisar de:\n"
            "• Nome completo\n• Numero de WhatsApp\n"
            "• Sinal de 50% via PIX\n\n"
            "Apos o pagamento, envio a confirmacao com todas as instrucoes "
            "de acesso! Pode me passar os dados?",
            nome=property_name, checkin=checkin_str, checkout=checkout_str,
            total=total)

    def pix_payment(self, property_name, checkin_str, checkout_str, total, signal, guest_name, pix_code=None, pix_qr_url=None):
        msg = self._r("pix_pagamento",
            "Pra garantir sua reserva e simples 😄\n\n"
            "Voce faz **50% via Pix** e o restante paga no dia da hospedagem.\n\n"
            "Se optar por **cartao**, acrescenta 20% no valor e pode dividir ate 6 vezes. "
            "Para pagamento em cartao envie mensagem direto para o "
            "WhatsApp 71-99290-0979 (ou volte para pagina principal, "
            "clique no Botao do WhatsApp no canto inferior direito da tela).\n\n"
            "Se for no **Pix**, e so me enviar o comprovante para "
            "WhatsApp 71-99290-0979 com nome completo e cidade 👍\n"
            "Em seguida voce recebera o resumo e instrucoes do check-in.\n\n"
            "**Chave Pix Aleatoria**\n"
            "**Chave PIX:** `b1b74e94-2687-4ea1-831b-6351b97e7929`\n"
            "**Chave PIX e-mail:** robertotechbuy15@gmail.com",
            guest=guest_name, nome=property_name, checkin=checkin_str,
            checkout=checkout_str, total=total, signal=signal)
        return msg

    def pix_info(self):
        return self._r("pix_info",
            "Para pagamento via PIX:\n\n"
            "**Chave PIX:** `b1b74e94-2687-4ea1-831b-6351b97e7929`\n\n"
            "Me avisa quando fizer o pagamento que ja confirmo tudo! :)")

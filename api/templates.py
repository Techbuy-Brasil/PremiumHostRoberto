class ResponseTemplates:
    @staticmethod
    def welcome_message():
        return (
            "Oi! Aqui é o Roberto, da PremiumHost! :)"
            "\n\n"
            "Temos apartamentos incríveis em Salvador — na Barra e em Ondina, "
            "pé na areia ou pertinho de tudo."
            "\n\n"
            "Me conta: qual imóvel te interessou, quantas pessoas vão ficar "
            "e quais datas você está pensando? Assim já faço as contas pra você!"
        )

    @staticmethod
    def greeting(name=None):
        if name:
            return (
                f"Oi {name}, prazer! Aqui é o Roberto da PremiumHost! "
                "Como posso te ajudar com a sua hospedagem em Salvador?"
            )
        return (
            "Oi! Aqui é o Roberto :) Tudo bem?"
            "\n\n"
            "Quer saber sobre disponibilidade, preços, ou tem alguma dúvida "
            "sobre os apartamentos? Pode perguntar à vontade!"
        )

    @staticmethod
    def thanks_reply():
        return (
            "Imagina! É um prazer ajudar :)"
            "\n\n"
            "Se precisar de mais alguma coisa, é só chamar! "
            "Tô sempre por aqui ou no WhatsApp (71) 99290-0979."
        )

    @staticmethod
    def goodbye():
        return (
            "Foi um prazer conversar com você! :)"
            "\n\n"
            "Quando quiser, é só me chamar de novo. "
            "E se precisar falar mais rápido, meu WhatsApp é (71) 99290-0979. "
            "Um abraço!"
        )

    @staticmethod
    def need_info(missing_fields, known_info=None):
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

    @staticmethod
    def analyzing():
        return "Deixa eu verificar aqui no sistema..."

    @staticmethod
    def available(property_name, checkin_str, checkout_str, total, nights, guests, nightly_avg, amenities_text, season_context, extra_info=""):
        msg = (
            f"Boas notícias! O {property_name} está disponível para essas datas! :)"
            "\n\n"
            f"Pra {guests} hóspedes, do dia {checkin_str} ao {checkout_str} "
            f"({nights} noites), o valor total fica em **R$ {total:.0f}** "
            f"— uma média de R$ {nightly_avg:.0f}/noite."
        )
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

    @staticmethod
    def unavailable(property_name, checkin_str, checkout_str):
        return (
            f"Poxa, infelizmente o {property_name} já está reservado para "
            f"o período de {checkin_str} a {checkout_str} :("
            "\n\n"
            "Mas calma! Posso sugerir algumas alternativas:"
            "\n\n"
            "* Datas próximas no mesmo imóvel"
            "* Outro apartamento nosso — temos opções parecidas"
            "\n\n"
            "O que você prefere?"
        )

    @staticmethod
    def alternative_dates(property_name, suggested_periods):
        msg = f"Que tal uma dessas opções no {property_name}?\n\n"
        for i, period in enumerate(suggested_periods, 1):
            msg += f"{i}. {period['label']} — R$ {period['total']:.0f} ({period['nights']} noites)\n"
        msg += "\nSe interessou por alguma? Ou prefere ver outros imóveis?"
        return msg

    @staticmethod
    def alternative_property(properties_list):
        msg = "Temos outras opções igualmente legais:\n\n"
        for p in properties_list:
            msg += f"* **{p['name']}** — {p['location']}\n"
            msg += f"  A partir de R$ {p['price']:.0f}/noite · até {p['capacity']} hóspedes\n\n"
        msg += "Se interessou por algum? Me fala que eu faço a simulação!"
        return msg

    @staticmethod
    def over_capacity(property_name, capacity, guests):
        return (
            f"Olha, o {property_name} comporta no máximo {capacity} hóspedes. "
            f"Pra {guests} pessoas infelizmente não vai dar :("
            "\n\n"
            "Mas temos outras opções maiores! O **Farol Barra Flat 214** ou o "
            "**Ondina Apart Hotel 441** comportam até 6 pessoas."
            "\n\n"
            "Quer que eu veja a disponibilidade pra algum deles?"
        )

    @staticmethod
    def invalid_dates():
        return (
            "A data de check-out precisa ser depois do check-in, hein! :)"
            "\n\n"
            "Pode verificar e me mandar as datas certinhas?"
        )

    @staticmethod
    def faq_resposta(topic=None):
        faqs = {
            "checkin": (
                "Sobre o check-in: o horário padrão é a partir das **14h**.\n"
                "Precisa chegar mais cedo? Dá pra solicitar early check-in "
                "(sujeito a disponibilidade, taxa de R$ 50).\n"
                "O acesso é 100% digital — mando as instruções pelo WhatsApp "
                "até 24h antes da chegada."
            ),
            "checkout": (
                "O check-out é até as **11h** do dia da saída.\n"
                "Se quiser sair mais tarde, o late check-out até 15h sai por "
                "R$ 70 (sujeito a disponibilidade)."
            ),
            "incluso": (
                "Todos os apartamentos são completos e incluem:\n"
                "• Ar-condicionado\n• Wi-Fi de alta velocidade\n• TV\n"
                "• Cozinha equipada (fogão, geladeira, micro-ondas, utensílios)\n"
                "• Roupa de cama e banho\n• Secador de cabelo\n• Ferro de passar\n"
                "• Taxa de limpeza **grátis**\n\n"
                "Cada imóvel tem seus diferenciais — piscina, academia, "
                "vista pro mar, etc. Dá uma olhada na página do apartamento!"
            ),
            "pagamento": (
                "Aceitamos **PIX, transferência bancária, cartão de crédito** "
                "(via link de pagamento, parcela em até 3x sem juros) e dinheiro.\n\n"
                "Sinal de **50%** no ato da reserva, o restante até 7 dias antes do check-in. "
                "Reservas de última hora (menos de 7 dias) pedimos o valor integral.\n\n"
                "Cancelamento grátis até 7 dias antes — reembolso integral. "
                "Entre 3 e 7 dias, 50%. Menos de 3 dias, não reembolsamos."
            ),
            "explore": (
                "Você vai amar a localização! Os apartamentos ficam na **Barra e Ondina**, "
                "as melhores regiões de Salvador.\n\n"
                "Perto dali você encontra:\n"
                "• Farol da Barra\n• Praia da Barra e Porto da Barra\n"
                "• Mercado Modelo\n• Pelourinho\n• Elevador Lacerda\n"
                "• Muitos restaurantes, bares, mercados e farmácias a pé\n\n"
                "O aeroporto fica a 30-40 minutos. Dá pra ir de táxi (R$ 60-80) "
                "ou Uber (R$ 40-60). Não precisa de carro — a região tem tudo perto!"
            ),
            "estacionamento": (
                "A disponibilidade de garagem varia conforme o condomínio. "
                "Alguns imóveis têm vaga inclusa. "
                "Me fala qual apartamento te interessou que eu confirmo pra você!"
            ),
            "piscina": (
                "Sim! A maioria dos nossos imóveis tem acesso à piscina do condomínio. "
                "É só verificar nas fotos da página de cada apartamento."
            ),
            "seguranca": (
                "A Barra e Ondina são regiões seguras e bem movimentadas, "
                "com avenidas iluminadas. Os condomínios têm portaria 24h e câmeras. "
                "Como em qualquer cidade grande, é bom ficar atento aos pertences "
                "em áreas mais cheias."
            ),
        }
        if topic and topic in faqs:
            return faqs[topic]
        return None

    @staticmethod
    def faq_menu():
        return (
            "Pergunta pra mim! Posso te ajudar com:\n\n"
            "• Horários de check-in / check-out\n"
            "• O que está incluso no apartamento\n"
            "• Formas de pagamento\n"
            "• Cancelamento\n"
            "• Localização e pontos turísticos\n"
            "• Estacionamento\n"
            "• Piscina e lazer\n"
            "• Como chegar do aeroporto\n\n"
            "É só perguntar! :)"
        )

    @staticmethod
    def no_property_match():
        return (
            "Não consegui identificar qual imóvel você está procurando. "
            "Temos essas opções:\n\n"
            "1. **Farol Barra Flat 214** — Barra\n"
            "2. **Farol Barra Flat 304** — Barra\n"
            "3. **Ondina Apart Hotel 441** — Ondina\n"
            "4. **Ondina Apart Hotel 305** — Ondina\n"
            "5. **The Plaza 407** — Ondina\n"
            "6. **Smart Convenções 509** — Armação\n\n"
            "Qual te chamou mais atenção?"
        )

    @staticmethod
    def fallback():
        return (
            "Entendi! Deixa eu ver se posso ajudar..."
            "\n\n"
            "Se você estiver procurando disponibilidade, me passa: "
            "o apartamento, as datas e quantos hóspedes.\n"
            "Se for uma dúvida sobre a hospedagem, pode perguntar "
            "que eu respondo na hora! :)"
            "\n\n"
            "Ou se preferir, pode falar direto comigo no WhatsApp: "
            "(71) 99290-0979"
        )

    @staticmethod
    def confirm_booking(property_name, checkin_str, checkout_str, total):
        return (
            f"Perfeito! Quer confirmar a reserva do {property_name} "
            f"de {checkin_str} a {checkout_str} no valor de R$ {total:.0f}? :)"
            "\n\n"
            "Se sim, vou precisar de:\n"
            "• Nome completo\n"
            "• CPF\n"
            "• Um sinal de 50% via PIX ou cartão\n\n"
            "Após o pagamento, envio a confirmação com todas as instruções "
            "de acesso! Pode me passar os dados?"
        )

    @staticmethod
    def pix_info():
        return (
            "Para pagamento via PIX, a chave é:\n"
            "**premiumhostroberto@gmail.com**\n"
            "(Banco Nubank — Roberto Alves)\n\n"
            "Me avisa quando fizer o pagamento que já confirmo tudo! :)"
        )

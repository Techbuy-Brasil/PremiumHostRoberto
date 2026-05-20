class ResponseTemplates:
    @staticmethod
    def welcome_message():
        return (
            "Ola! Seja bem-vindo ao atendimento PremiumHost Roberto!\n\n"
            "Temos apartamentos incriveis em Salvador:\n"
            "1. Farol Barra Flat 214 - Barra\n"
            "2. Ondina Apart Hotel 441 - Ondina\n"
            "3. Ondina Apart Hotel 305 - Ondina\n"
            "4. Smart Convencoes 509 - Armacao\n"
            "5. The Plaza Ondina - Ondina\n"
            "6. Farol Barra Flat 304 - Barra\n\n"
            "Para comecar, me diga qual imovel te interessou, "
            "as datas e quantos hospedes."
        )

    @staticmethod
    def available(property_name, checkin_str, checkout_str, total, nights, guests, nightly_avg, amenities_text, season_context, extra_info=""):
        return (
            f"Verifiquei aqui e suas datas estao disponiveis!\n\n"
            f"Para {guests} hospedes, do dia {checkin_str} ao dia {checkout_str} "
            f"({nights} noites), o valor total fica em R$ {total:.0f} "
            f"(media de R$ {nightly_avg:.0f}/noite).\n\n"
            f"{extra_info}"
            f"A hospedagem possui:\n"
            f"{amenities_text}\n\n"
            f"{season_context}\n\n"
            f"Caso deseje, posso te ajudar com a confirmacao agora mesmo!"
        )

    @staticmethod
    def unavailable(property_name, checkin_str, checkout_str, reason):
        return (
            f"Infelizmente nao ha disponibilidade para o periodo solicitado "
            f"({checkin_str} a {checkout_str}).\n\n"
            f"{reason}\n\n"
            f"Gostaria de verificar outras datas ou nossos outros imoveis?"
        )

    @staticmethod
    def need_info(missing_fields):
        questions = {
            "checkin": "Qual a data de check-in desejada?",
            "checkout": "Qual a data de check-out desejada?",
            "guests": "Quantos hospedes serao?",
        }
        msg = "Para fazer a simulacao, preciso de algumas informacoes:\n\n"
        for field in missing_fields:
            if field in questions:
                msg += f"* {questions[field]}\n"
        msg += "\nMe diga que ja calculo tudo pra voce!"
        return msg

    @staticmethod
    def alternative_dates(property_name, suggested_periods):
        msg = f"Que tal considerar uma destas opcoes no {property_name}?\n\n"
        for i, period in enumerate(suggested_periods, 1):
            msg += f"{i}. {period['label']} - R$ {period['total']:.0f} ({period['nights']} noites)\n"
        msg += "\nOu se preferir, posso mostrar nossos outros imoveis!"
        return msg

    @staticmethod
    def alternative_property(properties_list):
        msg = "Temos outros imoveis incriveis em Salvador:\n\n"
        for p in properties_list:
            msg += f"* {p['name']} - {p['location']}\n"
            msg += f"  A partir de R$ {p['price']:.0f}/noite | {p['capacity']} hospedes\n\n"
        msg += "Se interessou por algum? Me avise que faco uma simulacao!"
        return msg

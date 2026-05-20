import sys
import io

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class ResponseTemplates:
    @staticmethod
    def greeting(guest_name=None):
        if guest_name:
            return f"Olá {guest_name}, tudo bem?"
        return "Olá, tudo bem?"

    @staticmethod
    def available(property_name, checkin_str, checkout_str, total, nights, guests, nightly_avg, amenities_text, season_context, extra_info=""):
        return (
            f"Verifiquei aqui e suas datas estão disponiveis!\n\n"
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
            f"Infelizmente verifiquei que nao ha disponibilidade para o periodo solicitado "
            f"({checkin_str} a {checkout_str}).\n\n"
            f"{reason}\n\n"
            f"Gostaria que eu verificasse outras datas ou um dos nossos outros imoveis "
            f"incriveis em Salvador?"
        )

    @staticmethod
    def need_info(missing_fields):
        questions = {
            "checkin": "Qual a data de check-in desejada?",
            "checkout": "Qual a data de check-out desejada?",
            "guests": "Quantos hospedes serao?",
            "children": "Havera criancas na hospedagem?",
            "pets": "Voce pretende levar pets?",
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
        msg += "\nOu se preferir, posso mostrar nossos outros imoveis disponiveis!"
        return msg

    @staticmethod
    def alternative_property(properties_list):
        msg = "Temos outros imoveis incriveis em Salvador disponiveis:\n\n"
        for p in properties_list:
            msg += f"* {p['name']} - {p['location']}\n"
            msg += f"  A partir de R$ {p['price']:.0f}/noite | {p['capacity']} hospedes\n"
            msg += f"  Destaques: {p['highlights']}\n\n"
        msg += "Se interessou por algum? Me avise que faco uma simulacao personalizada!"
        return msg

    @staticmethod
    def closing(guest_name=None):
        base = "Fico a disposicao para qualquer duvida! Tenha um otimo dia"
        if guest_name:
            base = f"Fico a disposicao para qualquer duvida, {guest_name}! Tenha um otimo dia"
        return base

    @staticmethod
    def welcome_message():
        return (
            "Ola! Seja bem-vindo ao atendimento inteligente de hospedagem!\n\n"
            "Temos 4 imoveis incriveis em Salvador:\n"
            "1. Farol Barra Flat 214 - Barra, vista para o mar, piscina na cobertura\n"
            "2. Ondina Apart Hotel 441 - Ondina, pe na areia, infraestrutura completa\n"
            "3. The Plaza 407 - Ondina, piscina privativa, 2 suites\n"
            "4. Smart Convencoes 509 - Armacao, studio moderno pertinho da praia\n\n"
            "Para comecar, me diga:\n"
            "- Qual imovel te interessou?\n"
            "- Qual data de check-in e check-out?\n"
            "- Quantos hospedes?\n\n"
            "Vou calcular tudo pra voce!"
        )

    @staticmethod
    def human_handoff():
        return (
            "Estou transferindo seu atendimento para um de nossos consultores "
            "humanos que podera te ajudar com mais detalhes. "
            "Aguarde um instante que ja entraremos em contato!"
        )

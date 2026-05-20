from datetime import date


class PricingEngine:
    def __init__(self, property_obj, holiday_calendar):
        self.property = property_obj
        self.calendar = holiday_calendar

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
        rate = self.property.base_price

        weekend_mult = self.calendar.get_weekend_multiplier(d)

        if self.calendar.is_high_season(d):
            rate *= 2.0

        if weekend_mult > 1.0:
            rate *= weekend_mult

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

        extra_guests = max(0, guests - self.property.base_guests)
        extra_fee_total = extra_guests * self.property.extra_guest_fee * nights
        total += extra_fee_total

        cleaning_fee = self.property.cleaning_fee
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

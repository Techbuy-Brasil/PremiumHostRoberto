from datetime import date, timedelta
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


class HolidayCalendar:
    def __init__(self, config_path=None):
        path = config_path or CONFIG_PATH
        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.nacionais = self._parse_dates(self.config.get("holidays_br", {}))
        self.estaduais = self._parse_dates(self.config.get("holidays_ba", {}))
        self.municipais = self._parse_dates(self.config.get("holidays_salvador", {}))
        self.high_season_months = self.config.get("pricing_rules", {}).get("high_season_months", [1, 2, 7])
        self.carnaval_dates = self._parse_carnaval(self.config.get("holidays_br", {}).get("carnaval", []))

    def _parse_dates(self, holidays_dict):
        parsed = {}
        for name, val in holidays_dict.items():
            if isinstance(val, list):
                parsed[name] = [date.fromisoformat(d) for d in val]
            else:
                parsed[name] = date.fromisoformat(val)
        return parsed

    def _parse_carnaval(self, carnaval_list):
        return [date.fromisoformat(d) for d in carnaval_list]

    def is_high_season(self, d):
        return d.month in self.high_season_months

    def is_weekend(self, d):
        return d.weekday() >= 5

    def is_friday(self, d):
        return d.weekday() == 4

    def is_saturday(self, d):
        return d.weekday() == 5

    def is_sunday(self, d):
        return d.weekday() == 6

    def get_weekend_multiplier(self, d):
        rules = self.config.get("pricing_rules", {}).get("weekend_surcharge", {})
        if self.is_saturday(d):
            return rules.get("saturday", 1.25)
        if self.is_friday(d) or self.is_sunday(d):
            return rules.get("friday", 1.20)
        return 1.0

    def is_holiday(self, d):
        for h_list in [self.nacionais, self.estaduais, self.municipais]:
            for name, val in h_list.items():
                if isinstance(val, list) and d in val:
                    return True
                elif isinstance(val, date) and d == val:
                    return True
        return False

    def is_carnaval_period(self, d):
        return d in self.carnaval_dates

    def is_ano_novo_period(self, checkin, checkout):
        ano_novo = self.nacionais.get("ano_novo")
        if ano_novo and (checkin <= ano_novo < checkout):
            return True
        return False

    def get_season_label(self, checkin, checkout):
        labels = []
        if self.is_ano_novo_period(checkin, checkout):
            labels.append("Reveillon/Ano Novo")
        if any(self.is_carnaval_period(d) for d in self.date_range(checkin, checkout)):
            labels.append("Carnaval")
        if any(self.is_high_season(d) for d in self.date_range(checkin, checkout)):
            labels.append("Alta Temporada")
        if not labels:
            labels.append("Baixa Temporada")
        return ", ".join(labels)

    def get_min_nights(self, checkin, checkout):
        rules = self.config.get("pricing_rules", {}).get("min_nights", {})
        default_min = rules.get("default", 1)
        high_season_min = rules.get("high_season", 2)

        nights = (checkout - checkin).days

        if any(self.is_high_season(d) for d in self.date_range(checkin, checkout)):
            if nights < high_season_min:
                return high_season_min
        if nights < default_min:
            return default_min
        return 0

    @staticmethod
    def date_range(start, end):
        for n in range((end - start).days):
            yield start + timedelta(days=n)

    def describe_period_context(self, checkin, checkout):
        context_parts = []
        season = self.get_season_label(checkin, checkout)
        context_parts.append(f"Período: {season}")

        if "Carnaval" in season:
            context_parts.append("Salvador e o destino mais procurado do Brasil no Carnaval")
        if "Alta Temporada" in season:
            context_parts.append("Procura elevada - recomendo garantir a reserva o quanto antes")
        if "Reveillon" in season:
            context_parts.append("Reveillon em Salvador e magico com a queima de fogos no Farol da Barra")

        return " | ".join(context_parts)

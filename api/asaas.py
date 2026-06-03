import os
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta

ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "")
USE_SANDBOX = os.environ.get("ASAAS_SANDBOX", "true").lower() == "true"

BASE_URL = "https://sandbox.asaas.com/api/v3" if USE_SANDBOX else "https://api.asaas.com/v3"

LAST_ERROR = ""


def _headers():
    return {
        "access_token": ASAAS_API_KEY,
        "Content-Type": "application/json",
    }


def configured():
    return bool(ASAAS_API_KEY)


def _api(method: str, path: str, data: dict = None):
    global LAST_ERROR
    url = f"{BASE_URL}/{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            LAST_ERROR = f"Asaas HTTP {e.code}: {err_body}"
        except Exception:
            LAST_ERROR = f"Asaas HTTP {e.code}"
        return None
    except Exception as e:
        LAST_ERROR = f"{type(e).__name__}: {e}"
        return None


def create_customer(name: str, email: str, cpf_cnpj: str, phone: str,
                    postal_code: str = "", address_number: str = "") -> dict:
    data = {
        "name": name,
        "email": email,
        "cpfCnpj": re.sub(r"\D", "", cpf_cnpj),
        "phone": re.sub(r"\D", "", phone),
        "notificationDisabled": True,
    }
    if postal_code:
        data["postalCode"] = re.sub(r"\D", "", postal_code)
    if address_number:
        data["addressNumber"] = address_number
    return _api("POST", "customers", data)


def find_customer_by_cpf(cpf_cnpj: str) -> dict:
    clean = re.sub(r"\D", "", cpf_cnpj)
    result = _api("GET", f"customers?cpfCnpj={clean}")
    if result and result.get("data"):
        return result["data"][0]
    return None


def create_payment(customer_id: str, value: float, due_date: str, description: str,
                   installments: int = 1,
                   card_holder_name: str = "", card_number: str = "",
                   expiry_month: str = "", expiry_year: str = "", ccv: str = "",
                   holder_name: str = "", holder_email: str = "",
                   holder_cpf: str = "", holder_phone: str = "",
                   holder_postal_code: str = "", holder_address_number: str = "") -> dict:
    data = {
        "customer": customer_id,
        "billingType": "CREDIT_CARD",
        "value": round(value, 2),
        "dueDate": due_date,
        "description": description,
        "installmentCount": installments,
        "creditCard": {
            "holderName": card_holder_name,
            "number": re.sub(r"\D", "", card_number),
            "expiryMonth": expiry_month.zfill(2),
            "expiryYear": expiry_year,
            "ccv": ccv,
        },
        "creditCardHolderInfo": {
            "name": holder_name,
            "email": holder_email,
            "cpfCnpj": re.sub(r"\D", "", holder_cpf),
            "postalCode": re.sub(r"\D", "", holder_postal_code),
            "addressNumber": holder_address_number or "0",
            "phone": re.sub(r"\D", "", holder_phone),
        },
    }
    return _api("POST", "payments", data)


def get_payment(payment_id: str) -> dict:
    return _api("GET", f"payments/{payment_id}")


def get_last_error() -> str:
    return LAST_ERROR
import os
import json
import urllib.request
import urllib.error

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "fotosflatssalvador@gmail.com")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "fotosflatssalvador@gmail.com")

LAST_ERROR = ""


def configured():
    return bool(SENDGRID_API_KEY)


def send_lead_notification(guest_id, name, phone, property_name, checkin, checkout, guests, total, status):
    global LAST_ERROR
    status_labels = {
        "consultou_preco": "Consultou preco",
        "pre_reserva": "Quer reservar",
        "lead_reserva": "Enviou WhatsApp",
    }
    label = status_labels.get(status, status)
    if not configured():
        LAST_ERROR = "SENDGRID_API_KEY not configured"
        return False
    subject = f"[Lead] {name or 'Anonimo'} - {property_name or 'Sem imovel'} ({label})"
    body = (
        f"Novo lead capturado!\n\n"
        f"Status: {label}\n"
        f"Nome: {name or 'Nao informado'}\n"
        f"WhatsApp: {phone or 'Nao informado'}\n"
        f"Imovel: {property_name or 'Nao informado'}\n"
        f"Check-in: {checkin or 'Nao informado'}\n"
        f"Check-out: {checkout or 'Nao informado'}\n"
        f"Hospedes: {guests or 0}\n"
        f"Total: R$ {total:.0f} ({total/2:.0f} de sinal)\n\n"
        f"Lead link: https://premiumhost-roberto.vercel.app/admin-leads.html"
    )
    data = json.dumps({
        "personalizations": [{"to": [{"email": NOTIFY_EMAIL}]}],
        "from": {"email": FROM_EMAIL},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        LAST_ERROR = ""
        return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        LAST_ERROR = f"SendGrid HTTP {e.code}: {error_body}"
        return False
    except Exception as e:
        LAST_ERROR = f"{type(e).__name__}: {e}"
        return False

PIX_TEMPLATE_BEFORE = "00020101021126580014br.gov.bcb.pix0136d08856a0-9ab3-43b7-8763-c861c205d53d520400005303986"
PIX_TEMPLATE_AFTER = "5802BR5919TECHBUY INFORMATICA6008SALVADOR62070503***"


def _crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def gerar_pix_payload(valor: float) -> str:
    valor_str = f"{valor:.2f}"
    amount_field = f"54{len(valor_str):02d}{valor_str}"
    payload = PIX_TEMPLATE_BEFORE + amount_field + PIX_TEMPLATE_AFTER
    crc = _crc16_ccitt(payload.encode("utf-8") + b"6304")
    return payload + f"6304{crc:04X}"

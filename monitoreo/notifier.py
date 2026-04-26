"""
Alert system for Centinela bots.

Cada alerta se guarda en MongoDB → high_risk.bot_results
"""

from datetime import datetime, timezone

from mongo_conn import col_bot_results


def send_alert(
    platform: str,
    account_id: str,
    account_name: str,
    event_type: str,
    data: dict,
    score: dict | None = None,
) -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    alert = {
        "alerta_id":     f"{platform}_{account_id}_{ts}",
        "plataforma":    platform,
        "cuenta_id":     account_id,
        "cuenta_nombre": account_name,
        "tipo_evento":   event_type,
        "datos":         data,
        "scoring":       score or {},
        "generado_en":   datetime.now(timezone.utc).isoformat(),
        "estado":        "pendiente",
    }

    try:
        col_bot_results().insert_one(alert)
    except Exception as e:
        print(f"[notifier] MongoDB: {e}")

    risk = (score or {}).get("risk_level", "—")
    print(f"[notifier] ✅ {alert['alerta_id']}  riesgo={risk}")
    return alert["alerta_id"]

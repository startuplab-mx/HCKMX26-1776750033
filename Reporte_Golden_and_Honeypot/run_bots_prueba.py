"""
prueba.py — Verificación de nuevas cuentas objetivo y bots de monitoreo.

Cuentas a verificar:
  YouTube:  @baffleking123  → https://www.youtube.com/@baffleking123/shorts
  Telegram: ID -1003827165081
  TikTok:   @baffleking1235 → /video/7633055269605412104

Qué hace:
  1. Consulta cada plataforma para confirmar que la cuenta es accesible.
  2. Agrega los targets a los JSON de configuración si no existen.
  3. Verifica que los bots cargan los targets correctamente.
  4. Guarda un reporte JSON con los resultados.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import requests
from dotenv import load_dotenv

_THIS_DIR  = Path(__file__).parent
_ROOT      = _THIS_DIR.parent
_MONITOREO = _ROOT / "monitoreo"

load_dotenv(_ROOT / ".env")
sys.path.insert(0, str(_MONITOREO))
sys.path.insert(0, str(_ROOT / "Apis2BD_ETL" / "Main" / "ETL"))

YT_API_KEY  = os.getenv("YOUTUBE_API_KEY", "")
TG_API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
TG_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

_RESULTS: dict = {}
DATE_STR = datetime.now(timezone.utc).date().isoformat()

# ID numérico completo del canal de Telegram
TG_CHANNEL_PEER_ID = -1003827165081


# ──────────────────────────────────────────────────────────────────────────────
# YOUTUBE
# ──────────────────────────────────────────────────────────────────────────────

def test_youtube() -> None:
    print("\n[YouTube] Verificando @baffleking123 ...")
    if not YT_API_KEY:
        _RESULTS["youtube"] = {"status": "ERROR", "msg": "YOUTUBE_API_KEY no configurada en .env"}
        print("[YouTube] ❌  YOUTUBE_API_KEY faltante")
        return

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part":      "snippet,statistics",
                "forHandle": "@baffleking123",
                "key":       YT_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])

        if not items:
            _RESULTS["youtube"] = {
                "status": "NOT_FOUND",
                "msg":    "Canal no encontrado con forHandle=@baffleking123",
            }
            print("[YouTube] ⚠️  Canal no encontrado (puede que el handle no sea exacto).")
            return

        ch         = items[0]
        channel_id = ch["id"]
        snippet    = ch.get("snippet", {})
        stats      = ch.get("statistics", {})
        info = {
            "channel_id":       channel_id,
            "title":            snippet.get("title", ""),
            "description":      snippet.get("description", "")[:200],
            "subscriber_count": stats.get("subscriberCount"),
            "video_count":      stats.get("videoCount"),
            "url":              "https://www.youtube.com/@baffleking123",
        }
        _RESULTS["youtube"] = {"status": "OK", "data": info}
        print(
            f"[YouTube] ✅  {info['title']}  |  ID: {channel_id}"
            f"  |  Subs: {info['subscriber_count']}  |  Videos: {info['video_count']}"
        )
        _upsert_youtube_target(channel_id, info["title"])
        _fetch_and_alert_youtube(channel_id, info["title"])

    except Exception as exc:
        _RESULTS["youtube"] = {"status": "ERROR", "msg": str(exc)}
        print(f"[YouTube] ❌  {exc}")


def _fetch_and_alert_youtube(channel_id: str, channel_title: str) -> None:
    from notifier import send_alert
    from mongo_conn import col_youtube_items

    published_after = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    params = {
        "key":            YT_API_KEY,
        "channelId":      channel_id,
        "part":           "snippet",
        "order":          "date",
        "publishedAfter": published_after,
        "maxResults":     5,
        "type":           "video",
    }
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[YouTube] ⚠️  No se pudieron obtener videos: {e}")
        return

    alertados = []
    for item in resp.json().get("items", []):
        snippet  = item.get("snippet", {})
        video_id = item["id"].get("videoId")
        if not video_id:
            continue
        video = {
            "video_id":      video_id,
            "channel_id":    channel_id,
            "channel_title": channel_title,
            "title":         snippet.get("title", ""),
            "description":   snippet.get("description", ""),
            "published_at":  snippet.get("publishedAt", ""),
            "url":           f"https://www.youtube.com/watch?v={video_id}",
            "source":        "youtube",
            "collected_at":  datetime.now(timezone.utc).isoformat(),
            "bot_pescador":  True,
        }
        try:
            col_youtube_items().update_one(
                {"video_id": video_id}, {"$set": video}, upsert=True
            )
        except Exception as e:
            print(f"[YouTube] ⚠️  MongoDB centinela: {e}")

        scoring = _score(f"{video['title']} {video['description']}", "youtube")
        send_alert(
            platform="youtube",
            account_id=channel_id,
            account_name=channel_title,
            event_type="nuevo_video",
            data={
                "video_id":          video_id,
                "url":               video["url"],
                "title":             video["title"],
                "description":       video["description"][:400],
                "published_at":      video["published_at"],
                "channel_title":     channel_title,
                "target_reason":     "cuenta prueba — baffleking123",
                "target_risk_level": "medio",
            },
            score=scoring,
        )
        print(f"[YouTube] ✅  Alerta enviada: {video['title'][:60]}")
        alertados.append(video_id)

    if not alertados:
        print("[YouTube] ⚠️  Sin videos en los últimos 30 días.")
    _RESULTS.setdefault("youtube", {})["videos_alertados"] = alertados


def _upsert_youtube_target(channel_id: str, title: str) -> None:
    fp   = _MONITOREO / "bot_pescador" / "youtube" / "channels.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    if any(t["channel_id"] == channel_id for t in data["targets"]):
        print("[YouTube] Target ya existe en channels.json — sin cambios.")
        return
    data["targets"].append({
        "channel_id":    channel_id,
        "channel_title": title,
        "added_at":      DATE_STR,
        "reason":        "cuenta prueba — baffleking123",
        "risk_level":    "medio",
    })
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[YouTube] ✅  Agregado a channels.json → {title}")


# ──────────────────────────────────────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────────────────────────────────────

async def test_telegram() -> None:
    print(f"\n[Telegram] Verificando canal ID {TG_CHANNEL_PEER_ID} ...")
    if not TG_API_ID or not TG_API_HASH:
        _RESULTS["telegram"] = {
            "status": "ERROR",
            "msg":    "TELEGRAM_API_ID o TELEGRAM_API_HASH faltantes en .env",
        }
        print("[Telegram] ❌  Credenciales de API no configuradas")
        return

    session_path = str(_MONITOREO / "bot_pescador" / "sesiones" / "pescador_telegram")
    if not Path(session_path + ".session").exists():
        _RESULTS["telegram"] = {
            "status": "SIN_SESION",
            "msg":    (
                f"No hay sesión en {session_path}.session. "
                "Ejecuta monitoreo/auth_telegram.py primero."
            ),
        }
        print("[Telegram] ⚠️  Sin sesión de autenticación. Ejecuta auth_telegram.py primero.")
        return

    try:
        from telethon import TelegramClient

        async with TelegramClient(session_path, TG_API_ID, TG_API_HASH) as client:
            try:
                entity       = await client.get_entity(TG_CHANNEL_PEER_ID)
                username     = getattr(entity, "username",           None)
                title        = getattr(entity, "title",              "Sin título")
                participants = getattr(entity, "participants_count", None)

                info = {
                    "channel_id":         entity.id,
                    "username":           username,
                    "title":              title,
                    "participants_count": participants,
                    "accessible":         True,
                }
                _RESULTS["telegram"] = {"status": "OK", "data": info}
                print(
                    f"[Telegram] ✅  {title}"
                    f"  |  @{username or 'sin_username'}"
                    f"  |  Miembros: {participants}"
                )

                if not username:
                    advertencia = (
                        "El canal no tiene username público. "
                        "bot_telegram.py monitorea por username — "
                        "para monitoreo por ID numérico se requiere ajuste en el bot."
                    )
                    _RESULTS["telegram"]["advertencia"] = advertencia
                    print(f"[Telegram] ⚠️  {advertencia}")

                _upsert_telegram_target(entity.id, username, title)

                # Obtener últimos mensajes y enviar alertas
                try:
                    from notifier import send_alert
                    from mongo_conn import col_telegram_messages
                    count = 0
                    async for msg in client.iter_messages(entity, limit=5):
                        text    = msg.text or ""
                        scoring = _score(text, "telegram")
                        ch_name = username or str(entity.id)
                        msg_doc = {
                            "message_uid":  f"{entity.id}_{msg.id}",
                            "source":       "telegram",
                            "channel_id":   entity.id,
                            "channel_name": ch_name,
                            "message_id":   msg.id,
                            "date":         msg.date.isoformat() if msg.date else None,
                            "text":         text,
                            "views":        getattr(msg, "views",    0) or 0,
                            "forwards":     getattr(msg, "forwards", 0) or 0,
                            "has_media":    bool(msg.media),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "scoring":      scoring,
                            "bot_pescador": True,
                        }
                        try:
                            col_telegram_messages().update_one(
                                {"message_uid": msg_doc["message_uid"]},
                                {"$set": msg_doc},
                                upsert=True,
                            )
                        except Exception as e:
                            print(f"[Telegram] ⚠️  MongoDB centinela: {e}")
                        send_alert(
                            platform="telegram",
                            account_id=str(entity.id),
                            account_name=ch_name,
                            event_type="nuevo_mensaje",
                            data={
                                "message_id": msg.id,
                                "url":        f"https://t.me/{ch_name}/{msg.id}",
                                "text":       text[:500],
                                "date":       str(msg.date),
                                "views":      msg_doc["views"],
                                "forwards":   msg_doc["forwards"],
                                "has_media":  msg_doc["has_media"],
                                "target_reason":     "canal prueba — baffleking",
                                "target_risk_level": "medio",
                            },
                            score=scoring,
                        )
                        print(f"[Telegram] ✅  Alerta enviada: mensaje {msg.id}")
                        count += 1
                    _RESULTS["telegram"]["mensajes_alertados"] = count
                    print(f"[Telegram] {count} mensajes subidos a high_risk.bot_results")
                except Exception as e:
                    print(f"[Telegram] ⚠️  Error al obtener mensajes: {e}")

            except Exception as exc:
                _RESULTS["telegram"] = {"status": "INACCESIBLE", "msg": str(exc)}
                print(f"[Telegram] ❌  No se pudo acceder al canal: {exc}")

    except Exception as exc:
        _RESULTS["telegram"] = {"status": "ERROR", "msg": str(exc)}
        print(f"[Telegram] ❌  Error de conexión Telethon: {exc}")


def _upsert_telegram_target(channel_id: int, username, title: str) -> None:
    fp   = _MONITOREO / "bot_pescador" / "telegram" / "channels.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    if any(t.get("channel_id") == channel_id for t in data["targets"]):
        print("[Telegram] Target ya existe en channels.json — sin cambios.")
        return
    entry = {
        "channel_id": channel_id,
        "title":      title,
        "added_at":   DATE_STR,
        "reason":     "canal prueba — baffleking",
        "risk_level": "medio",
    }
    if username:
        entry["username"] = username
    data["targets"].append(entry)
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Telegram] ✅  Agregado a channels.json → {title}")


# ──────────────────────────────────────────────────────────────────────────────
# SCORING
# ──────────────────────────────────────────────────────────────────────────────

def _load_lexicon() -> dict:
    lex = _ROOT / "lexicon" / "narco_lexicon.json"
    return json.loads(lex.read_text(encoding="utf-8")) if lex.exists() else {}


def _score(text: str, platform: str = "tiktok") -> dict:
    try:
        from scoring import full_analysis
        return full_analysis(text or "", _load_lexicon(), platform=platform)
    except Exception:
        return {"score_final": 0, "risk_level": "sin_scoring"}


# ──────────────────────────────────────────────────────────────────────────────
# TIKTOK  (usa fixture local — sin scraping)
# ──────────────────────────────────────────────────────────────────────────────

FIXTURE_PATH = _THIS_DIR / "tiktok_fixture.json"


def _map_raw_to_centinela(raw: dict) -> dict:
    """Convierte el formato crudo del scraper al documento de centinela.tiktok_videos."""
    author = raw.get("authorMeta", {})
    video  = raw.get("videoMeta", {})
    return {
        "video_id":          raw["id"],
        "autor_username":    author.get("name", ""),
        "autor_id":          author.get("id", ""),
        "autor_nickname":    author.get("nickName", ""),
        "url":               raw.get("webVideoUrl", ""),
        "descripcion":       raw.get("text", ""),
        "hashtags":          [h.get("name", h) if isinstance(h, dict) else h
                              for h in raw.get("hashtags", [])],
        "fecha_publicacion": raw.get("createTimeISO"),
        "locationCreated":   raw.get("locationCreated", ""),
        "stats": {
            "digg":    raw.get("diggCount",    0),
            "share":   raw.get("shareCount",   0),
            "play":    raw.get("playCount",    0),
            "comment": raw.get("commentCount", 0),
            "collect": raw.get("collectCount", 0),
        },
        "video_meta": {
            "duration":   video.get("duration"),
            "definition": video.get("definition"),
            "format":     video.get("format"),
        },
        "source":       "tiktok",
        "bot_pescador": True,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def test_tiktok() -> None:
    print("\n[TikTok] Procesando fixture local (tiktok_fixture.json) ...")
    _upsert_tiktok_target()

    # Cargar fixture
    raw_videos = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    # Filtrar solo videos de @baffleking1235
    raw_videos = [v for v in raw_videos
                  if v.get("authorMeta", {}).get("name") == "baffleking1235"]

    if not raw_videos:
        _RESULTS["tiktok"] = {"status": "ERROR", "msg": "No hay videos de @baffleking1235 en el fixture."}
        print("[TikTok] ❌  Sin datos de @baffleking1235 en el fixture.")
        return

    docs          = [_map_raw_to_centinela(v) for v in raw_videos]
    target_info   = {"reason": "cuenta prueba — baffleking1235", "risk_level": "medio"}
    scored_videos = []

    for doc in docs:
        text    = f"{doc['descripcion']} {' '.join(doc['hashtags'])}"
        scoring = _score(text)
        doc["scoring"] = scoring

        print(
            f"[TikTok] ✅  video {doc['video_id']}"
            f"  |  plays: {doc['stats']['play']}"
            f"  |  risk: {scoring.get('risk_level', '—')}"
            f"  |  score: {scoring.get('score_final', 0)}"
        )

        # Intentar persistir en MongoDB y enviar alerta
        mongo_ok  = False
        alerta_ok = False
        try:
            from mongo_conn import col_tiktok_videos
            col_tiktok_videos().update_one(
                {"video_id": doc["video_id"]},
                {"$set": doc},
                upsert=True,
            )
            mongo_ok = True
            print(f"[TikTok] ✅  Guardado en centinela.tiktok_videos")
        except Exception as exc:
            print(f"[TikTok] ⚠️  MongoDB no disponible: {exc.__class__.__name__}")

        try:
            from notifier import send_alert
            send_alert(
                platform="tiktok",
                account_id=doc["autor_username"],
                account_name=doc["autor_username"],
                event_type="nuevo_video",
                data={
                    "video_id":          doc["video_id"],
                    "url":               doc["url"],
                    "descripcion":       doc["descripcion"][:400],
                    "hashtags":          doc["hashtags"],
                    "fecha_publicacion": str(doc["fecha_publicacion"]),
                    "stats":             doc["stats"],
                    "target_reason":     target_info["reason"],
                    "target_risk_level": target_info["risk_level"],
                },
                score=scoring,
            )
            alerta_ok = True
            print(f"[TikTok] ✅  Alerta enviada para {doc['video_id']}")
        except Exception as exc:
            print(f"[TikTok] ⚠️  Notifier no disponible: {exc.__class__.__name__}")

        scored_videos.append({
            "video_id":    doc["video_id"],
            "url":         doc["url"],
            "descripcion": doc["descripcion"],
            "fecha":       doc["fecha_publicacion"],
            "stats":       doc["stats"],
            "scoring":     scoring,
            "mongo_ok":    mongo_ok,
            "alerta_ok":   alerta_ok,
        })

    _RESULTS["tiktok"] = {
        "status":         "OK",
        "fixture":        str(FIXTURE_PATH.name),
        "videos_fixture": len(docs),
        "detalle":        scored_videos,
    }


def _upsert_tiktok_target() -> None:
    fp   = _MONITOREO / "bot_pescador" / "tiktok" / "accounts.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    if any(t["username"].lower() == "baffleking1235" for t in data["targets"]):
        print("[TikTok] Target ya existe en accounts.json — sin cambios.")
        return
    data["targets"].append({
        "username":   "baffleking1235",
        "user_id":    "",
        "url":        "https://www.tiktok.com/@baffleking1235",
        "added_at":   DATE_STR,
        "reason":     "cuenta prueba — baffleking1235",
        "risk_level": "medio",
    })
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[TikTok] ✅  Agregado @baffleking1235 a accounts.json")


# ──────────────────────────────────────────────────────────────────────────────
# VERIFICAR CARGA DE TARGETS EN LOS BOTS
# ──────────────────────────────────────────────────────────────────────────────

def test_bot_loading() -> None:
    print("\n[Bots] Verificando carga de targets en bot_tik y bot_youtube ...")
    try:
        import bot_tik
        import bot_youtube

        tiktok_targets  = bot_tik.load_targets()
        youtube_targets = bot_youtube.load_targets()

        tiktok_names = [t["username"] for t in tiktok_targets]
        youtube_ids  = [t["channel_id"] for t in youtube_targets]

        baffleking_tt = "baffleking1235" in tiktok_names
        yt_result     = _RESULTS.get("youtube", {})
        yt_ch_id      = yt_result.get("data", {}).get("channel_id")
        baffleking_yt = (yt_ch_id in youtube_ids) if yt_ch_id else None

        _RESULTS["bot_loading"] = {
            "status":                       "OK",
            "tiktok_targets":               tiktok_names,
            "youtube_targets":              youtube_ids,
            "baffleking1235_en_bot_tiktok": baffleking_tt,
            "baffleking123_en_bot_youtube": baffleking_yt,
        }

        tt_sym = "✅" if baffleking_tt else "❌"
        yt_sym = "✅" if baffleking_yt else ("❓  (YouTube sin datos)" if baffleking_yt is None else "❌")
        print(f"[Bots] TikTok  {tt_sym}  {tiktok_names}")
        print(f"[Bots] YouTube {yt_sym}  {youtube_ids}")

    except Exception as exc:
        _RESULTS["bot_loading"] = {"status": "ERROR", "msg": str(exc)}
        print(f"[Bots] ❌  {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 62)
    print("  PRUEBA — baffleking123 / baffleking1235")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 62)

    test_youtube()
    await test_telegram()
    test_tiktok()
    test_bot_loading()

    # ── Resumen ──────────────────────────────────────────────────────────────
    _SYM = {"OK": "✅", "SIN_DATOS": "⚠️", "SIN_SESION": "⚠️", "NOT_FOUND": "⚠️"}
    print("\n" + "=" * 62)
    print("  RESUMEN")
    print("=" * 62)
    for plat, res in _RESULTS.items():
        status = res.get("status", "?")
        sym    = _SYM.get(status, "❌")
        print(f"  {sym}  {plat.upper():<16} {status}")
        if status not in ("OK",):
            msg = res.get("msg") or res.get("advertencia", "")
            if msg:
                print(f"        {msg}")

    print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())

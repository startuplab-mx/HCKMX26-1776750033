import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

etl_dir = Path(__file__).parent.parent
if str(etl_dir) not in sys.path:
    sys.path.insert(0, str(etl_dir))

from scoring import full_analysis

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [YouTube] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

LEXICON_PATH            = PROJECT_ROOT / "lexicon" / "narco_lexicon.json"
SLEEP_BETWEEN_QUERIES   = 2
MAX_RESULTS_PER_QUERY   = 150   # paginamos hasta 3 paginas de 50
COMMENT_SCORE_THRESHOLD = 2


def load_lexicon():
    with open(LEXICON_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_mongo_collection():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI no configurada en .env")
    client = MongoClient(uri)
    db = client["centinela"]
    db["youtube_items"].create_index("video_id", unique=True, background=True)
    return db["youtube_items"]


def build_youtube_client(api_key):
    return build("youtube", "v3", developerKey=api_key)


def search_videos(client, query, max_results=MAX_RESULTS_PER_QUERY):
    items      = []
    page_token = None
    try:
        while len(items) < max_results:
            batch      = min(50, max_results - len(items))
            req_kwargs = dict(
                q=query,
                part="snippet",
                type="video",
                regionCode="MX",
                relevanceLanguage="es",
                maxResults=batch,
                safeSearch="none")
            if page_token:
                req_kwargs["pageToken"] = page_token
            response   = client.search().list(**req_kwargs).execute()
            items.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        log.info("Query '%s' → %d resultados", query, len(items))
    except HttpError as e:
        log.error("Error en busqueda '%s': %s", query, e)
    return items


def get_video_details(client, video_ids):
    if not video_ids:
        return []
    try:
        response = client.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids[:50])).execute()
        return response.get("items", [])
    except HttpError as e:
        log.error("Error obteniendo detalles: %s", e)
        return []


def get_channel_info(client, channel_id):
    """Obtiene metadata del canal: subs, pais, descripcion, keywords."""
    try:
        resp  = client.channels().list(
            part="snippet,statistics,brandingSettings",
            id=channel_id).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        ch    = items[0]
        snip  = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        brand = ch.get("brandingSettings", {}).get("channel", {})
        return {
            "subscriber_count":    int(stats.get("subscriberCount", 0) or 0),
            "channel_video_count": int(stats.get("videoCount", 0) or 0),
            "channel_view_count":  int(stats.get("viewCount", 0) or 0),
            "channel_country":     snip.get("country", ""),
            "channel_description": snip.get("description", "")[:3000],
            "channel_keywords":    brand.get("keywords", ""),
            "channel_created_at":  snip.get("publishedAt", "")}
    except HttpError as e:
        log.error("Error obteniendo canal %s: %s", channel_id, e)
        return {}


def get_comment_threads(client, video_id, lexicon, max_threads=100):
    """Obtiene top-level comments + replies, cada uno con su scoring."""
    comments = []
    try:
        resp = client.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=min(max_threads, 100),
            order="relevance",
            textFormat="plainText").execute()
        for item in resp.get("items", []):
            top   = item["snippet"]["topLevelComment"]["snippet"]
            ctext = top.get("textDisplay", "")
            entry = {
                "comment_id":   item["snippet"]["topLevelComment"]["id"],
                "author":       top.get("authorDisplayName"),
                "author_id":    top.get("authorChannelId", {}).get("value", ""),
                "text":         ctext,
                "likes":        top.get("likeCount", 0),
                "published_at": top.get("publishedAt"),
                "updated_at":   top.get("updatedAt"),
                "reply_count":  item["snippet"].get("totalReplyCount", 0),
                "scoring":      full_analysis(ctext, lexicon, platform="youtube"),
                "replies":      []}
            for r in (item.get("replies") or {}).get("comments", []):
                rsnip = r["snippet"]
                rtxt  = rsnip.get("textDisplay", "")
                entry["replies"].append({
                    "comment_id":   r["id"],
                    "author":       rsnip.get("authorDisplayName"),
                    "author_id":    rsnip.get("authorChannelId", {}).get("value", ""),
                    "text":         rtxt,
                    "likes":        rsnip.get("likeCount", 0),
                    "published_at": rsnip.get("publishedAt"),
                    "scoring":      full_analysis(rtxt, lexicon, platform="youtube")})
            comments.append(entry)
    except HttpError as e:
        if e.resp.status != 403:
            log.error("Error en comentarios de %s: %s", video_id, e)
    return comments


def build_video_doc(query, details, lexicon, channel_info=None):
    snippet  = details.get("snippet", {})
    stats    = details.get("statistics", {})
    content  = details.get("contentDetails", {})
    video_id = details["id"]
    title       = snippet.get("title", "")
    description = snippet.get("description", "")   # sin truncar
    tags        = snippet.get("tags", [])
    # agrega # a los tags que no lo tienen para que el scoring los detecte
    tagged_text = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    full_text   = " ".join(filter(None, [title, description, tagged_text]))
    scoring     = full_analysis(full_text, lexicon, platform="youtube")
    thumbnails  = snippet.get("thumbnails", {})
    thumb_url   = (thumbnails.get("maxres") or thumbnails.get("high") or
                   thumbnails.get("default") or {}).get("url", "")
    localized   = snippet.get("localized", {})
    doc = {
        "video_id":               video_id,
        "source":                 "youtube",
        "query":                  query,
        "url":                    f"https://www.youtube.com/watch?v={video_id}",
        "title":                  title,
        "description":            description,
        "channel_id":             snippet.get("channelId", ""),
        "channel_title":          snippet.get("channelTitle", ""),
        "published_at":           snippet.get("publishedAt", ""),
        "tags":                   tags,
        "category_id":            snippet.get("categoryId", ""),
        "default_language":       snippet.get("defaultLanguage", ""),
        "default_audio_language": snippet.get("defaultAudioLanguage", ""),
        "live_broadcast_content": snippet.get("liveBroadcastContent", ""),
        "thumbnail_url":          thumb_url,
        "localized_title":        localized.get("title", ""),
        "duration":               content.get("duration", ""),
        "definition":             content.get("definition", ""),
        "caption":                content.get("caption", ""),
        "licensed_content":       content.get("licensedContent", False),
        "view_count":             int(stats.get("viewCount", 0) or 0),
        "like_count":             int(stats.get("likeCount", 0) or 0),
        "favorite_count":         int(stats.get("favoriteCount", 0) or 0),
        "comment_count":          int(stats.get("commentCount", 0) or 0),
        "comments":               [],
        "collected_at":           datetime.now(timezone.utc).isoformat(),
        "scoring":                scoring}
    if channel_info:
        doc.update(channel_info)
    return doc


def run_collection(queries, max_queries=None):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        log.error("YOUTUBE_API_KEY no configurada en .env")
        return
    lexicon        = load_lexicon()
    yt_client      = build_youtube_client(api_key.strip())
    collection     = get_mongo_collection()
    queries        = queries if max_queries is None else queries[:max_queries]
    total_saved    = 0
    seen_ids       = set()
    channel_cache  = {}   # channel_id → channel_info dict

    for query in tqdm(queries, desc="YouTube queries"):
        search_results = search_videos(yt_client, query)
        if not search_results:
            time.sleep(SLEEP_BETWEEN_QUERIES)
            continue

        nuevos_ids = [
            item["id"]["videoId"]
            for item in search_results
            if "videoId" in item.get("id", {})
            and item["id"]["videoId"] not in seen_ids]
        seen_ids.update(nuevos_ids)

        if not nuevos_ids:
            log.info("'%s' → todos los videos ya vistos, saltando", query)
            time.sleep(SLEEP_BETWEEN_QUERIES)
            continue

        details_list  = get_video_details(yt_client, nuevos_ids)
        details_by_id = {d["id"]: d for d in details_list}

        batch_ops = []
        for item in search_results:
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id or vid_id not in details_by_id:
                continue

            ch_id = details_by_id[vid_id].get("snippet", {}).get("channelId", "")
            if ch_id and ch_id not in channel_cache:
                channel_cache[ch_id] = get_channel_info(yt_client, ch_id)

            doc = build_video_doc(
                query,
                details_by_id[vid_id],
                lexicon,
                channel_info=channel_cache.get(ch_id))

            if doc["scoring"]["score_final"] >= COMMENT_SCORE_THRESHOLD:
                log.info(
                    "Score %d → comentarios de '%s'",
                    doc["scoring"]["score_final"],
                    doc["title"][:60])
                doc["comments"] = get_comment_threads(yt_client, vid_id, lexicon)
                time.sleep(1)

            batch_ops.append(
                UpdateOne(
                    {"video_id": vid_id},
                    {"$set": doc},
                    upsert=True))

        if batch_ops:
            result      = collection.bulk_write(batch_ops, ordered=False)
            saved_count = result.upserted_count + result.modified_count
            total_saved += saved_count
            log.info("'%s' → %d videos en MongoDB", query, saved_count)
        time.sleep(SLEEP_BETWEEN_QUERIES)

    log.info("YouTube ETL completo: %d videos guardados (%d unicos vistos)", total_saved, len(seen_ids))


if __name__ == "__main__":
    lexicon = load_lexicon()
    queries = lexicon["search_queries"]["youtube"]
    run_collection(queries)

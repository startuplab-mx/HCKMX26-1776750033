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

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / "centinela_data_explorer" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [YouTube] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

LEXICON_PATH          = PROJECT_ROOT / "centinela_data_explorer" / "lexicon" / "narco_lexicon.json"
SLEEP_BETWEEN_QUERIES = 2
MAX_RESULTS_PER_QUERY = 20
COMMENT_SCORE_THRESHOLD = 10


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
    try:
        response = client.search().list(
            q=query,
            part="snippet",
            type="video",
            regionCode="MX",
            relevanceLanguage="es",
            maxResults=min(max_results, 50),
            safeSearch="none").execute()
        items = response.get("items", [])
        log.info("Query '%s' → %d resultados", query, len(items))
        return items
    except HttpError as e:
        log.error("Error en busqueda '%s': %s", query, e)
        return []


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


def get_comments(client, video_id, max_results=50):
    try:
        response = client.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            order="relevance",
            textFormat="plainText").execute()
        comments = []
        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author":       top.get("authorDisplayName"),
                "text":         top.get("textDisplay"),
                "likes":        top.get("likeCount", 0),
                "published_at": top.get("publishedAt")})
        return comments
    except HttpError as e:
        if e.resp.status != 403:
            log.error("Error en comentarios de %s: %s", video_id, e)
        return []


def build_video_doc(query, details, lexicon):
    snippet  = details.get("snippet", {})
    stats    = details.get("statistics", {})
    video_id = details["id"]
    title       = snippet.get("title", "")
    description = snippet.get("description", "")[:1000]
    tags        = snippet.get("tags", [])
    full_text   = " ".join(filter(None, [title, description, " ".join(tags)]))
    scoring     = full_analysis(full_text, lexicon, platform="youtube")
    return {
        "video_id":      video_id,
        "source":        "youtube",
        "query":         query,
        "url":           f"https://www.youtube.com/watch?v={video_id}",
        "title":         title,
        "description":   description,
        "channel_id":    snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at":  snippet.get("publishedAt", ""),
        "tags":          tags,
        "view_count":    int(stats.get("viewCount", 0)),
        "like_count":    int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "comments":      [],
        "collected_at":  datetime.now(timezone.utc).isoformat(),
        "scoring":       scoring}


def run_collection(queries, max_queries=10):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        log.error("YOUTUBE_API_KEY no configurada en .env")
        return
    lexicon    = load_lexicon()
    yt_client  = build_youtube_client(api_key.strip())
    collection = get_mongo_collection()
    queries     = queries[:max_queries]
    total_saved = 0

    for query in tqdm(queries, desc="YouTube queries"):
        search_results = search_videos(yt_client, query)
        if not search_results:
            time.sleep(SLEEP_BETWEEN_QUERIES)
            continue
        video_ids = [
            item["id"]["videoId"]
            for item in search_results
            if "videoId" in item.get("id", {})]
        details_list  = get_video_details(yt_client, video_ids)
        details_by_id = {d["id"]: d for d in details_list}

        batch_ops = []
        for item in search_results:
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id or vid_id not in details_by_id:
                continue
            doc = build_video_doc(query, details_by_id[vid_id], lexicon)
            if doc["scoring"]["score_final"] >= COMMENT_SCORE_THRESHOLD:
                log.info(
                    "Score alto (%d) → comentarios de '%s'",
                    doc["scoring"]["score_final"],
                    doc["title"][:60])
                doc["comments"] = get_comments(yt_client, vid_id)
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

    log.info("YouTube ETL completo: %d videos guardados", total_saved)


if __name__ == "__main__":
    lexicon = load_lexicon()
    queries = lexicon["search_queries"]["youtube"]
    run_collection(queries, max_queries=10)

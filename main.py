import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

ROOT         = Path(__file__).parent
LEXICON_PATH = ROOT.parent / "centinela_data_explorer" / "lexicon" / "narco_lexicon.json"
MAX_QUERIES  = 10

load_dotenv(ROOT.parent / "centinela_data_explorer" / ".env")

sys.path.insert(0, str(ROOT / "ETL"))
sys.path.insert(0, str(ROOT / "ETL" / "ETL_youtube"))
sys.path.insert(0, str(ROOT / "ETL" / "ETL_telegram"))

import etl_youtube
import etl_telegram


def load_lexicon():
    with open(LEXICON_PATH, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    args    = sys.argv[1:]
    lexicon = load_lexicon()
    targets = args if args else ["youtube", "telegram"]

    if "youtube" in targets:
        log.info("Iniciando ETL YouTube...")
        yt_queries = lexicon["search_queries"]["youtube"]
        etl_youtube.run_collection(yt_queries, max_queries=MAX_QUERIES)

    if "telegram" in targets:
        log.info("Iniciando ETL Telegram...")
        tg_queries = lexicon["search_queries"]["telegram"]
        etl_telegram.run_collection(tg_queries, max_queries=MAX_QUERIES)

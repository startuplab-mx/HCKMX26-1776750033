import re
from collections import Counter

HIGH_SPEC_HASHTAGS = {
    "#gentedelmz", "#mayozambada", "#operativamz", "#gentedelmayozambada",
    "#chapizza", "#chapiza", "#loschapitos", "#lamayiza",
    "#4letras", "#4l", "#ng", "#mencho", "#nuevageneración", "#nuevageneracion",
    "#señormencho", "#senormencho", "#elseñordelosgallos", "#elsenordelosgallos",
    "#cjng", "#jalisconuevageneracion", "#4ng", "#delta1",
    "#empresadelas4letras", "#trabajocjng",
    "#makabelico_oficial", "#makabelico", "#victormendivil",
    "#belicones", "#fracesbelicas", "#frasesbelicas", "#ondeado",
    "#trabajoparalamaña", "#trabajoparalamana"}

HIGH_SPEC_EMOJIS = {"🥷", "⛑️", "🍕", "🐓"}
LOW_SPEC_EMOJIS  = {"😈", "👿", "🧿", "💀", "🔫", "💵", "🏠"}

LOW_SPEC_HASHTAGS = {
    "#narco", "#crimen", "#sicario", "#plaza", "#jale",
    "#narcocorridos", "#corridosbelicos", "#corridostumbados",
    "#empleourgente", "#trabajourgente", "#reclutamiento",
    "#sinaloamusic", "#mana", "#maña"}

# n-gramas criminales con peso IDF manual (mas alto = mas especifico)
NGRAM_WEIGHTS = {
    # trigramas
    "ropa comida hospedaje":    4.5,
    "adiestramiento en rancho": 4.5,
    "civiles ex militares":     4.0,
    "guardia seguridad sin":    3.5,
    "gente de confianza":       3.2,
    "trabajo bien pagado":      3.0,
    "sin experiencia previa":   2.8,
    "pago semanal garantizado": 3.5,
    "empresa de seguridad":     2.0,
    "hombres y mujeres":        2.2,
    "unete a la empresa":       3.0,
    # bigramas
    "ropa comida":           3.5,
    "jale paga":             3.5,
    "adiestramiento rancho": 4.0,
    "civiles militares":     3.5,
    "plaza disponible":      3.0,
    "gente confianza":       3.0,
    "bien pagado":           2.0,
    "sin experiencia":       2.0,
    "paga bien":             2.0,
    "trabajo jale":          2.5,
    "sueldo semanal":        2.0,
    "buen sueldo":           1.8,
    "empleo urgente":        1.8,
    "empresa seria":         1.5}

# Telegram: umbral bajo, canal directo. YouTube: alto por ruido musical.
PLATFORM_RISK = {
    "youtube":  {"bajo": 1, "medio": 8,  "alto": 20},
    "telegram": {"bajo": 1, "medio": 5,  "alto": 13},
    "default":  {"bajo": 1, "medio": 10, "alto": 25}}

# En Telegram cualquier señal T2 ya es mas sospechosa
PLATFORM_CONFIDENCE = {
    "youtube":  {"confirmado": 0.75, "probable": 0.45, "sospechoso": 0.20},
    "telegram": {"confirmado": 0.62, "probable": 0.30, "sospechoso": 0.12},
    "default":  {"confirmado": 0.80, "probable": 0.50, "sospechoso": 0.20}}


def compute_tfidf_score(text):
    # TF-IDF con bigramas/trigramas. Escala 150 da rango aprox 2-30 puntos.
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < 2:
        return 0, []
    doc_len = len(words)
    ngram_freq = Counter()
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            ngram_freq[" ".join(words[i:i+n])] += 1
    total_tfidf = 0.0
    hits = []
    for ngram, idf_weight in NGRAM_WEIGHTS.items():
        freq = ngram_freq.get(ngram, 0)
        if freq > 0:
            total_tfidf += (freq / doc_len) * idf_weight
            hits.append(ngram)
    return int(total_tfidf * 150), hits


def full_analysis(text, lexicon, platform="default"):
    if not text:
        return _empty_result(platform)
    tl = text.lower()

    # T1: frases explicitas de reclutamiento
    t1_hits = []
    frases = lexicon.get("recruitment_phrases", {})
    if isinstance(frases, dict):
        for phrase in frases.get("explicit", {}).get("phrases", []):
            if phrase.lower() in tl:
                t1_hits.append(phrase[:60])
    elif isinstance(frases, list):
        for phrase in frases:
            if phrase.lower() in tl:
                t1_hits.append(phrase[:60])
    t1_score = len(t1_hits) * 10

    # T2: hashtags y emojis propios de cartel
    t2_hashtag_hits = []
    for cartel, cdata in lexicon.get("hashtags", {}).items():
        for tag in cdata.get("tags", []):
            if tag.lower() in HIGH_SPEC_HASHTAGS and tag.lower() in tl:
                t2_hashtag_hits.append(f"{tag}({cartel})")
    t2_emoji_hits = []
    for emoji in HIGH_SPEC_EMOJIS:
        count = text.count(emoji)
        if count:
            meta = lexicon.get("emojis", {}).get(emoji, {})
            cartel_name = meta.get("cartel", ["general"])[0]
            t2_emoji_hits.extend([f"{emoji}({cartel_name})"] * count)
    t2_score = len(t2_hashtag_hits) * 5 + len(t2_emoji_hits) * 4

    # T3: artistas, emojis genericos, hashtags genericos, frases soft
    t3_artist_hits = []
    for cartel, artists in lexicon.get("artists", {}).items():
        for artist in artists:
            if artist.lower() in tl:
                t3_artist_hits.append(f"{artist}({cartel})")
    t3_emoji_hits = []
    for emoji in LOW_SPEC_EMOJIS:
        count = text.count(emoji)
        if count:
            t3_emoji_hits.extend([emoji] * count)
    t3_hashtag_hits = []
    for cartel, cdata in lexicon.get("hashtags", {}).items():
        for tag in cdata.get("tags", []):
            if tag.lower() in LOW_SPEC_HASHTAGS and tag.lower() in tl:
                t3_hashtag_hits.append(tag)
    t3_soft_hits = []
    if isinstance(frases, dict):
        for phrase in frases.get("soft", {}).get("phrases", []):
            if phrase.lower() in tl:
                t3_soft_hits.append(phrase[:40])
    t3_score = (len(t3_artist_hits) * 2 + len(t3_emoji_hits)
                + len(t3_hashtag_hits) + len(t3_soft_hits) * 2)

    tfidf_score, ngram_hits = compute_tfidf_score(text)

    # cuantas categorias distintas dispararon (max 4 para el multiplicador)
    categories_fired = min(sum([
        1 if t1_hits else 0,
        1 if (t2_hashtag_hits or t2_emoji_hits) else 0,
        1 if (t3_artist_hits or t3_soft_hits) else 0,
        1 if (t3_emoji_hits or t3_hashtag_hits) else 0,
        1 if ngram_hits else 0]), 4)

    mult_table = {0: 0, 1: 0.5, 2: 1.0, 3: 1.5, 4: 2.0}
    multiplier  = mult_table[categories_fired]
    raw_score   = t1_score + t2_score + t3_score + tfidf_score
    final_score = int(raw_score * multiplier)

    # confianza: que tan probable es que sea reclutamiento real
    if t1_hits:
        base_conf = 0.8 + min(len(t1_hits) * 0.05, 0.2)
    elif t2_hashtag_hits and t2_emoji_hits:
        base_conf = 0.6
    elif t2_hashtag_hits or t2_emoji_hits:
        base_conf = 0.4 + (categories_fired - 1) * 0.1
    elif ngram_hits and (t2_hashtag_hits or t2_emoji_hits or t3_artist_hits):
        base_conf = 0.30
    elif t3_artist_hits and (t3_emoji_hits or t3_hashtag_hits):
        base_conf = 0.25
    elif ngram_hits:
        base_conf = 0.15
    else:
        base_conf = max(0.0, categories_fired * 0.05)
    confidence = round(min(base_conf, 1.0), 3)

    conf_t = PLATFORM_CONFIDENCE.get(platform, PLATFORM_CONFIDENCE["default"])
    if confidence >= conf_t["confirmado"]:
        conf_label = "confirmado"
    elif confidence >= conf_t["probable"]:
        conf_label = "probable"
    elif confidence >= conf_t["sospechoso"]:
        conf_label = "sospechoso"
    else:
        conf_label = "contextual"

    return {
        "score_final":          final_score,
        "score_raw":            raw_score,
        "risk_level":           risk_level(final_score, platform),
        "confidence":           confidence,
        "confidence_label":     conf_label,
        "platform":             platform,
        "categories_fired":     categories_fired,
        "multiplier":           multiplier,
        "t1_recruitment_count": len(t1_hits),
        "t1_recruitment_hits":  "|".join(t1_hits),
        "t2_hashtag_count":     len(t2_hashtag_hits),
        "t2_hashtag_hits":      "|".join(t2_hashtag_hits),
        "t2_emoji_count":       len(t2_emoji_hits),
        "t2_emoji_hits":        "|".join(t2_emoji_hits),
        "t3_artist_count":      len(t3_artist_hits),
        "t3_artist_hits":       "|".join(t3_artist_hits),
        "t3_emoji_hits":        "|".join(t3_emoji_hits),
        "t3_hashtag_hits":      "|".join(t3_hashtag_hits),
        "t3_soft_hits":         "|".join(t3_soft_hits),
        "tfidf_score":          tfidf_score,
        "tfidf_ngram_hits":     "|".join(ngram_hits)}


def _empty_result(platform="default"):
    return {
        "score_final": 0, "score_raw": 0, "risk_level": "sin_evidencia",
        "confidence": 0.0, "confidence_label": "contextual",
        "platform": platform, "categories_fired": 0, "multiplier": 0,
        "t1_recruitment_count": 0, "t1_recruitment_hits": "",
        "t2_hashtag_count": 0, "t2_hashtag_hits": "",
        "t2_emoji_count": 0, "t2_emoji_hits": "",
        "t3_artist_count": 0, "t3_artist_hits": "",
        "t3_emoji_hits": "", "t3_hashtag_hits": "", "t3_soft_hits": "",
        "tfidf_score": 0, "tfidf_ngram_hits": ""}


def risk_level(score, platform="default"):
    t = PLATFORM_RISK.get(platform, PLATFORM_RISK["default"])
    if score < t["bajo"]:
        return "sin_evidencia"
    if score < t["medio"]:
        return "bajo"
    if score < t["alto"]:
        return "medio"
    return "alto"

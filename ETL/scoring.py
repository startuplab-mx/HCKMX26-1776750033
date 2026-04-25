import re
from collections import Counter


def _normalize(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', text.lower())).strip()


def _parse_duration_secs(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


HIGH_SPEC_HASHTAGS = {
    "#gentedelmz", "#mayozambada", "#operativamz", "#gentedelmayozambada",
    "#chapizza", "#chapiza", "#loschapitos", "#lamayiza",
    "#4letras", "#4l", "#ng", "#mencho", "#nuevageneración", "#nuevageneracion",
    "#señormencho", "#senormencho", "#elseñordelosgallos", "#elsenordelosgallos",
    "#cjng", "#jalisconuevageneracion", "#4ng", "#delta1",
    "#empresadelas4letras", "#trabajocjng",
    "#makabelico_oficial", "#makabelico", "#victormendivil",
    "#belicones", "#fracesbelicas", "#frasesbelicas", "#ondeado",
    "#trabajoparalamaña", "#trabajoparalamana",
    "#chapitos", "#cds", "#sinaloacartel", "#mz",
    "#sicarios", "#recruitment_ng", "#recruitment.ng",
    "#4ltrs", "#4lts", "#4ng", "#jalisco4ng"}

HIGH_SPEC_EMOJIS = {"🥷", "⛑️", "🍕", "🐓"}
LOW_SPEC_EMOJIS  = {"😈", "👿", "🧿", "💀", "🔫", "💵", "🏠"}

LOW_SPEC_HASHTAGS = {
    "#narco", "#crimen", "#sicario", "#plaza", "#jale",
    "#narcocorridos", "#corridosbelicos", "#corridostumbados",
    "#empleourgente", "#trabajourgente", "#reclutamiento",
    "#sinaloamusic", "#mana", "#maña", "#jalisco", "#sinaloa",
    "#corridosbravos", "#corridomexicano", "#elcartel"}

# emojis de alerta en reacciones de Telegram
ALARM_REACTION_EMOJIS = {"😈", "👿", "💀", "🔫", "🥷", "🍕", "🐓", "⛑️"}

# Patrones de nombres de cartel para deteccion como substring (sin necesidad de #)
# Incluye leet-speak documentado (Segob 2025 / Colmex 2025)
_CARTEL_PATTERNS = [
    # CJNG — formas normales y leet
    (re.compile(r'c\.?j\.?n\.?g|cjn[g9]', re.I),          "CJNG", 5),
    (re.compile(r'4\s*letras?|4l[eE]tr[a4]s', re.I),       "CJNG", 5),
    (re.compile(r'jalisco\s*nueva\s*generac', re.I),        "CJNG", 5),
    (re.compile(r'nueva\s*generaci[oó]n', re.I),            "CJNG", 4),
    (re.compile(r'delta\s*1\b', re.I),                      "CJNG", 5),
    (re.compile(r'\bmencho\b', re.I),                       "CJNG", 4),
    (re.compile(r'\bel\s*se[nñ]or\s*de\s*los\s*gallos\b', re.I), "CJNG", 5),
    (re.compile(r'\b4\s*ng\b', re.I),                       "CJNG", 4),
    (re.compile(r'\bbelicones\b', re.I),                    "CJNG", 4),
    # CDS
    (re.compile(r'\bchapiz[ao]\b', re.I),                   "CDS", 4),
    (re.compile(r'\bchapitos\b', re.I),                     "CDS", 4),
    (re.compile(r'\bchapizza\b', re.I),                     "CDS", 5),
    (re.compile(r'\bla\s*may[ií]za\b', re.I),              "CDS", 4),
    (re.compile(r'\bgente\s*del?\s*mz\b', re.I),           "CDS", 5),
    (re.compile(r'\bmayo\s*zambada\b', re.I),               "CDS", 5),
    # CDN / Zetas
    (re.compile(r'\bcdn\b|\bc\.d\.n\b', re.I),              "CDN", 5),
    (re.compile(r'tropa\s*del?\s*infierno', re.I),          "CDN", 5),
    (re.compile(r'35\s*batall[oó]n', re.I),                 "CDN", 5),
    (re.compile(r'cartel\s*del?\s*noreste', re.I),          "CDN", 5),
    (re.compile(r'zetas\s*vieja\s*escuela|z\.?v\.?e\.?', re.I), "Zetas", 5),
    (re.compile(r'\bla\s*letra\b', re.I),                   "Zetas", 3),
    # CDG
    (re.compile(r'\bcdg\b|\bc\.d\.g\b', re.I),              "CDG", 4),
    (re.compile(r'\bescorpiones\b', re.I),                   "CDG", 4),
    # LFM
    (re.compile(r'\blfm\b|familia\s*michoacana', re.I),     "LFM", 4),
    # Leet-speak de cartel generico
    (re.compile(r'c[4@]rt[3e]l', re.I),                    "general", 4),
    (re.compile(r's[1!]c[a4]ri[o0]', re.I),                "general", 4),
    (re.compile(r'narc[o0]', re.I),                         "general", 2),
    # General
    (re.compile(r'\bla\s*ma[nñ][aá]\b', re.I),             "general", 3),
    (re.compile(r'\bplaza\b', re.I),                        "general", 2),
    (re.compile(r'\bsicario\b', re.I),                      "general", 3),
    (re.compile(r'\bjale\b', re.I),                         "general", 2),
    (re.compile(r'\bnarco\b', re.I),                        "general", 2),
]

# Roles criminales: halcón/vigía/cocinero/sicario/chofer (Segob 2025)
_CRIMINAL_ROLE_RE = re.compile(
    r'\bhalc[oó]n\b|\bvigi[aá]\b|\bcampana\b'
    r'|\bsicario\b|\bgatillero\b|\bpistolero\b|\bejecutor\b'
    r'|\bcocinero\s*(?:de\s*lab|lab\b)|laboratorio\s*(?:clan|esp)'
    r'|\bchofer\s*(?:privado|de\s*confianza)'
    r'|\btelefonista\b|\boperador\s*telef'
    r'|\bgente\s*sin\s*miedo\b'
    r'|\btrabajo\s*(?:de\s*)?(?:halc[oó]n|vigi[aá]|vigia)\b',
    re.I)

# Frases de gaming para reclutamiento (Insight Crime / Borderland Beat 2026)
_GAMING_PHRASES_RE = re.compile(
    r'trabajo\s*gamer'
    r'|ganas?\s*dinero\s*(?:real\s*)?jugando'
    r'|te\s*pago\s*(?:por\s*)?jugar'
    r'|te\s*regalo\s*(?:skins?|vidas?|armas?|items?|ítems?)'
    r'|reclutamiento\s*abierto'
    r'|únete\s*al?\s*crew|unete\s*al?\s*crew'
    r'|si\s*sabes\s*(?:usar\s*)?armas?\s*(?:tienes?\s*)?(?:jale|trabajo|chamba)'
    r'|si\s*sabes\s*moverte\s*en\s*(?:el\s*)?mapa'
    r'|trabajo\s*(?:de\s*)?vigi[aá]\s*desde\s*(?:casa|celular)'
    r'|trabajo\s*(?:de\s*)?halc[oó]n\s*desde\s*(?:casa|celular)'
    r'|jale\s*(?:real|desde\s*casa)',
    re.I)

# patron de telefono mexicano en texto (celular o fijo)
_PHONE_RE = re.compile(
    r'(?<!\d)(?:\+?52\s*)?'
    r'(?:\(?[2-9]\d{2}\)?[\s\-.]?)'
    r'\d{3}[\s\-.]?\d{4}'
    r'(?!\d)')

# patron de WhatsApp/Telegram contact call-to-action
_CONTACT_PHRASES_RE = re.compile(
    r'(?:manda|envia|escribe|escríbeme|contacta|comunicate|comunícate|'
    r'escr[ií]beme|habl[aá]me|ll[aá]m[aá]me|mensaje|msg)\s*'
    r'(?:al?\s*)?(?:priv(?:ado)?|wp|whatsapp|wsp|tel[eé]fono|num|número|numero|wa)',
    re.I)

# call-to-action directo
_CTA_RE = re.compile(
    r'(?:al\s*priv(?:ado)?|al\s*privado|por\s*privado|mp\s*para\s*info|'
    r'más\s*info\s*al\s*priv|mas\s*info\s*al\s*priv|'
    r'manda\s*(?:tu\s*)?(?:foto|datos|cv|mensaje|mp)|'
    r'info\s*al\s*whatsapp|contacto\s*al\s*wp|'
    r'escr[ií]be\s*al?\s*(?:privado|whatsapp|wp|wsp)|'
    r'comunic[aá]te\s*al?\s*(?:privado|whatsapp)|'
    r'datos\s*al\s*priv|envia\s*mp)',
    re.I)

NGRAM_WEIGHTS = {
    # trigramas de reclutamiento directo
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
    "se busca personal":        3.5,
    "las 4 letras":             4.2,
    "empresa 4 letras":         5.0,
    "cuida el rancho":          4.5,
    "hospedaje y comida":       4.0,
    "traslado y hospedaje":     4.0,
    "pago en efectivo":         2.5,
    "sin antecedentes penales": 3.0,
    "cuida la plaza":           5.0,
    "cuidar la plaza":          5.0,
    "trabajo de plaza":         4.5,
    "puro 4 letras":            5.0,
    "unico canal oficial":      4.0,
    "canal oficial delta":      5.0,
    "real hasta muerte":        3.5,
    "gente del mz":             4.5,
    "señor los gallos":         4.0,
    "trabajo en campo":         2.5,
    "paga a tiempo":            2.5,
    "empresa seria busca":      3.5,
    "necesito gente nueva":     4.0,
    "traer mas gente":          3.5,
    "sin miedo al trabajo":     3.0,
    "trabajo para hombres":     2.5,
    "gente sin miedo":          3.5,
    "te enseñamos todo":        3.0,
    "te ensenamos todo":        3.0,
    "todo incluido rancho":     4.0,
    "oportunidad para salir":   2.8,
    # bigramas de reclutamiento
    "ropa comida":       3.5,
    "jale paga":         3.5,
    "adiestramiento rancho": 4.0,
    "civiles militares": 3.5,
    "plaza disponible":  3.0,
    "gente confianza":   3.0,
    "bien pagado":       2.0,
    "sin experiencia":   2.0,
    "paga bien":         2.0,
    "trabajo jale":      2.5,
    "sueldo semanal":    2.0,
    "buen sueldo":       1.8,
    "empleo urgente":    1.8,
    "empresa seria":     1.5,
    "4 letras":          3.8,
    "cuida rancho":      4.5,
    "comida hospedaje":  4.0,
    "hospedaje incluido": 3.5,
    "traslado incluido": 3.5,
    "pago diario":       2.5,
    "hombres mujeres":   2.5,
    "trabajo disponible": 2.0,
    "guardia nocturno":  2.5,
    "nueva generacion":  3.0,
    "4 ng":              3.5,
    "delta 1":           4.5,
    "tirando charola":   5.0,
    "canal oficial":     3.0,
    "hay jale":          4.5,
    "sobra jale":        4.5,
    "tenemos jale":      4.5,
    "necesito gente":    3.5,
    "busco gente":       3.0,
    "al privado":        3.0,
    "al priv":           3.5,
    "manda whatsapp":    4.0,
    "manda mensaje":     3.0,
    "manda foto":        3.0,
    "arma larga":        3.5,
    "arma corta":        3.0,
    "cuerno chivo":      5.0,
    "calibre 50":        3.0,
    "puro cjng":         4.5,
    "numero privado":    2.5,
    "whatsapp privado":  3.5,
    "busco personas":    3.0,
    "trabajo campo":     2.5,
    "rancho trabajo":    3.0,
    "paga semanal":      2.5,
    "gente nueva":       2.5,
    "necesitas trabajo": 2.5,
    "buscamos jovenes":  3.0,
    "buscamos personas": 2.5,
    "traemos gente":     3.5,
    "sicario trabajo":   4.5,
    "plaza empleo":      4.0,
    "jalisco empleo":    3.0,
    "empleo rancho":     3.5,
    "contacta privado":  3.5,
    "info privado":      3.0,
    "mandanos mp":       3.5,
    "buen pago":         2.0,
    "pago garantizado":  2.5,
    "trabajo seguro":    2.0,
    "rancho seguro":     3.0}

PLATFORM_RISK = {
    "youtube":  {"bajo": 1, "medio": 5,  "alto": 12},
    "telegram": {"bajo": 1, "medio": 3,  "alto": 8},
    "default":  {"bajo": 1, "medio": 5,  "alto": 15}}

PLATFORM_CONFIDENCE = {
    "youtube":  {"confirmado": 0.65, "probable": 0.35, "sospechoso": 0.15},
    "telegram": {"confirmado": 0.55, "probable": 0.25, "sospechoso": 0.10},
    "default":  {"confirmado": 0.70, "probable": 0.40, "sospechoso": 0.15}}


def _hashtag_hit(tag_lower, tl):
    tag_clean = tag_lower.lstrip("#")
    return tag_lower in tl or (len(tag_clean) >= 4 and tag_clean in tl)


def detect_cartel_substrings(text):
    """
    Detecta nombres de cartel embebidos en palabras compuestas (ej. 'trabajocjng',
    'cjng_empleo', '4letrasoficial', etc.).  Devuelve (score, hits).
    """
    hits = []
    score = 0
    seen = set()
    for pattern, label, pts in _CARTEL_PATTERNS:
        m = pattern.search(text)
        if m and label not in seen:
            seen.add(label)
            hits.append(f"{m.group(0).lower()}({label})")
            score += pts
    return score, hits


def detect_phones(text):
    """Retorna lista de numeros de telefono encontrados en el texto."""
    return _PHONE_RE.findall(text)


def detect_contact_ctas(text):
    """Detecta call-to-action de contacto por privado/WhatsApp."""
    hits = []
    if _CONTACT_PHRASES_RE.search(text):
        hits.append("contacto_privado")
    if _CTA_RE.search(text):
        hits.append("cta_directo")
    return hits


def detect_criminal_roles(text):
    """Detecta menciones a roles criminales (halcón, vigía, cocinero, sicario, chofer)."""
    m = _CRIMINAL_ROLE_RE.search(text)
    return [m.group(0).lower()] if m else []


def detect_gaming_recruitment(text):
    """Detecta frases de reclutamiento en contexto de videojuegos."""
    m = _GAMING_PHRASES_RE.search(text)
    return [m.group(0).lower()] if m else []


def compute_tfidf_score(text):
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < 2:
        return 0, []
    doc_len    = len(words)
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
    tl      = text.lower()
    tl_norm = _normalize(text)

    # T1: frases explicitas de reclutamiento
    t1_hits = []
    frases = lexicon.get("recruitment_phrases", {})
    if isinstance(frases, dict):
        for phrase in frases.get("explicit", {}).get("phrases", []):
            if phrase.lower() in tl_norm:
                t1_hits.append(phrase[:60])
    elif isinstance(frases, list):
        for phrase in frases:
            if phrase.lower() in tl_norm:
                t1_hits.append(phrase[:60])
    t1_score = len(t1_hits) * 10

    # T2: hashtags (con o sin #, como substring) y emojis de cartel
    t2_hashtag_hits = []
    for cartel, cdata in lexicon.get("hashtags", {}).items():
        for tag in cdata.get("tags", []):
            tag_lower = tag.lower()
            if tag_lower in HIGH_SPEC_HASHTAGS and _hashtag_hit(tag_lower, tl):
                t2_hashtag_hits.append(f"{tag}({cartel})")
    t2_emoji_hits = []
    for emoji in HIGH_SPEC_EMOJIS:
        count = text.count(emoji)
        if count:
            meta        = lexicon.get("emojis", {}).get(emoji, {})
            cartel_name = meta.get("cartel", ["general"])[0]
            t2_emoji_hits.extend([f"{emoji}({cartel_name})"] * count)
    t2_score = len(t2_hashtag_hits) * 5 + len(t2_emoji_hits) * 4

    # T2b: nombres de cartel como substring (e.g. "trabajocjng", "4letrasoficial")
    t2b_score, t2b_hits = detect_cartel_substrings(text)

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
            tag_lower = tag.lower()
            if tag_lower in LOW_SPEC_HASHTAGS and _hashtag_hit(tag_lower, tl):
                t3_hashtag_hits.append(tag)
    t3_soft_hits = []
    if isinstance(frases, dict):
        for phrase in frases.get("soft", {}).get("phrases", []):
            if phrase.lower() in tl_norm:
                t3_soft_hits.append(phrase[:40])
    t3_score = (len(t3_artist_hits) * 2 + len(t3_emoji_hits)
                + len(t3_hashtag_hits) + len(t3_soft_hits) * 2)

    # T4: senales de contacto (telefono, CTA, privado/WhatsApp)
    phone_hits   = detect_phones(text)
    contact_hits = detect_contact_ctas(text)
    t4_score = len(phone_hits) * 8 + len(contact_hits) * 4

    # T5: roles criminales y frases de gaming (Segob 2025 / Insight Crime)
    role_hits   = detect_criminal_roles(text)
    gaming_hits = detect_gaming_recruitment(text)
    t5_score = len(role_hits) * 8 + len(gaming_hits) * 6

    tfidf_score, ngram_hits = compute_tfidf_score(text)

    categories_fired = min(sum([
        1 if t1_hits else 0,
        1 if (t2_hashtag_hits or t2_emoji_hits or t2b_hits) else 0,
        1 if (t3_artist_hits or t3_soft_hits) else 0,
        1 if (t3_emoji_hits or t3_hashtag_hits) else 0,
        1 if ngram_hits else 0,
        1 if (phone_hits or contact_hits) else 0,
        1 if (role_hits or gaming_hits) else 0]), 5)

    # Multiplier: 1-category ya no penaliza (antes era 0.5×)
    mult_table  = {0: 0, 1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.0}
    multiplier  = mult_table[categories_fired]
    raw_score   = t1_score + t2_score + t2b_score + t3_score + t4_score + t5_score + tfidf_score
    final_score = int(raw_score * multiplier)

    if t1_hits:
        base_conf = 0.8 + min(len(t1_hits) * 0.05, 0.2)
    elif t2_hashtag_hits and t2_emoji_hits:
        base_conf = 0.6
    elif t2_hashtag_hits or t2_emoji_hits:
        base_conf = 0.4 + (categories_fired - 1) * 0.08
    elif t2b_hits and ngram_hits:
        base_conf = 0.40
    elif t2b_hits:
        base_conf = 0.28
    elif ngram_hits and (t2_hashtag_hits or t2_emoji_hits or t3_artist_hits):
        base_conf = 0.30
    elif t3_artist_hits and (t3_emoji_hits or t3_hashtag_hits):
        base_conf = 0.25
    elif role_hits:
        base_conf = 0.40 + (categories_fired - 1) * 0.06
    elif gaming_hits and t2b_hits:
        base_conf = 0.35
    elif gaming_hits:
        base_conf = 0.22
    elif phone_hits or contact_hits:
        base_conf = 0.20 + (categories_fired - 1) * 0.05
    elif ngram_hits:
        base_conf = 0.18
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
        "recruitment_score":    t1_score + tfidf_score,
        "propaganda_score":     t2_score + t2b_score + t3_score,
        "contact_score":        t4_score,
        "gaming_role_score":    t5_score,
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
        "t2b_cartel_hits":      "|".join(t2b_hits),
        "t3_artist_count":      len(t3_artist_hits),
        "t3_artist_hits":       "|".join(t3_artist_hits),
        "t3_emoji_hits":        "|".join(t3_emoji_hits),
        "t3_hashtag_hits":      "|".join(t3_hashtag_hits),
        "t3_soft_hits":         "|".join(t3_soft_hits),
        "t4_phones":            "|".join(phone_hits),
        "t4_contact_hits":      "|".join(contact_hits),
        "t5_role_hits":         "|".join(role_hits),
        "t5_gaming_hits":       "|".join(gaming_hits),
        "tfidf_score":          tfidf_score,
        "tfidf_ngram_hits":     "|".join(ngram_hits)}


def metadata_signals_youtube(view_count, like_count, comment_count,
                              duration_iso, category_id, channel_subs,
                              channel_country, made_for_kids=False):
    """Señales de riesgo basadas en metadata del video/canal, no en texto."""
    flags = []
    score = 0

    secs = _parse_duration_secs(duration_iso)
    if 0 < secs < 60:
        flags.append("video_muy_corto_60s")
        score += 6
    elif 60 <= secs < 180:
        flags.append("video_corto_3min")
        score += 2

    # comentarios deshabilitados con vistas altas = ocultar conversacion
    if view_count > 1000 and comment_count == 0:
        flags.append("comentarios_deshabilitados")
        score += 6

    if view_count > 500000:
        flags.append("alcance_masivo")
        score += 4
    elif view_count > 100000:
        flags.append("alto_alcance")
        score += 2

    if view_count > 0 and like_count > 0:
        if like_count / view_count > 0.08:
            flags.append("engagement_inusual")
            score += 3

    if category_id and str(category_id) != "10":
        flags.append(f"categoria_no_musical:{category_id}")
        score += 5

    if channel_subs is not None and 0 < channel_subs < 1000:
        flags.append("canal_pequeno")
        score += 4
    elif channel_subs is not None and 1000 <= channel_subs < 5000:
        score += 2

    if channel_country == "MX":
        flags.append("origen_mexico")
        score += 2

    if made_for_kids:
        flags.append("dirigido_a_menores")
        score += 8

    return {"score": score, "flags": flags}


def metadata_signals_telegram(is_pinned, forwards, views,
                               has_buttons, reactions, phones):
    """Señales de riesgo basadas en metadata del mensaje de Telegram."""
    flags = []
    score = 0

    if is_pinned:
        flags.append("mensaje_fijado")
        score += 10

    if has_buttons:
        flags.append("botones_de_accion")
        score += 8

    if phones:
        flags.append(f"telefono_en_mensaje:{len(phones)}")
        score += 12

    if forwards and forwards > 50:
        flags.append(f"muy_viral:{forwards}_reenvios")
        score += 5
    elif forwards and forwards > 10:
        score += 2

    if views and views > 100000:
        flags.append("alcance_masivo")
        score += 4
    elif views and views > 10000:
        score += 1

    alarm_total = sum(v for k, v in reactions.items() if k in ALARM_REACTION_EMOJIS)
    if alarm_total > 50:
        flags.append(f"reacciones_alarma_masivas:{alarm_total}")
        score += 6
    elif alarm_total > 10:
        flags.append(f"reacciones_alarma:{alarm_total}")
        score += 3

    return {"score": score, "flags": flags}


def _empty_result(platform="default"):
    return {
        "score_final": 0, "score_raw": 0, "recruitment_score": 0,
        "propaganda_score": 0, "contact_score": 0, "gaming_role_score": 0,
        "risk_level": "sin_evidencia", "confidence": 0.0, "confidence_label": "contextual",
        "platform": platform, "categories_fired": 0, "multiplier": 0,
        "t1_recruitment_count": 0, "t1_recruitment_hits": "",
        "t2_hashtag_count": 0, "t2_hashtag_hits": "",
        "t2_emoji_count": 0, "t2_emoji_hits": "",
        "t2b_cartel_hits": "",
        "t3_artist_count": 0, "t3_artist_hits": "",
        "t3_emoji_hits": "", "t3_hashtag_hits": "", "t3_soft_hits": "",
        "t4_phones": "", "t4_contact_hits": "",
        "t5_role_hits": "", "t5_gaming_hits": "",
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


def channel_analysis(username, title, lexicon):
    combined = _normalize(f"{username or ''} {title or ''}")
    if not combined:
        return {"score": 0, "flags": []}
    flags = []

    for pattern in lexicon.get("account_name_patterns", {}).get("patterns", []):
        cleaned = pattern.lower().replace(".", " ")
        if cleaned in combined:
            flags.append(f"name:{pattern}")

    for hint in lexicon.get("account_name_patterns", {}).get("regex_hints", []):
        try:
            if re.search(hint, (username or "").lower()):
                flags.append(f"regex:{hint[:30]}")
        except re.error:
            pass

    for cartel, cdata in lexicon.get("hashtags", {}).items():
        for tag in cdata.get("tags", []):
            tag_clean = tag.lower().lstrip("#")
            if len(tag_clean) > 3 and tag_clean in combined:
                flags.append(f"term:{tag_clean}({cartel})")

    # detectar patron de cartel en el nombre del canal
    _, ch_hits = detect_cartel_substrings(f"{username or ''} {title or ''}")
    for h in ch_hits:
        flags.append(f"cartel:{h}")

    score = min(len(flags) * 5, 30)
    return {"score": score, "flags": flags[:15]}

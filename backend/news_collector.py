# ============================================================
# news_collector.py — Recolecta y analiza noticias crypto
# Adaptado para PostgreSQL (Supabase) y SQLite (local)
# ============================================================

import requests
import json
import time
from datetime import datetime

from config import CLAUDE_API_KEY, CRYPTO_NAMES, TEST_MODE, NEWS_MODE
from database import get_connection, USE_POSTGRES
from error_handler import setup_logger, NewsError

logger = setup_logger(__name__)

CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"
PH = "%s" if USE_POSTGRES else "?"


# ============================================================
# FUENTE 1 — CryptoCompare
# ============================================================

def fetch_cryptocompare(limit: int = 30) -> list:
    endpoints = [
        f"https://data-api.cryptocompare.com/news/v1/article/list?lang=EN&sortOrder=latest&limit={limit}",
        f"https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest",
    ]
    for url in endpoints:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("Response") == "Error":
                continue
            raw = data.get("Data", data.get("data", []))
            if isinstance(raw, list) and len(raw) > 0:
                return raw[:limit]
            elif isinstance(raw, dict) and len(raw) > 0:
                return list(raw.values())[:limit]
        except Exception as e:
            logger.debug(f"CryptoCompare endpoint falló {url}: {e}")
            continue
    return []


def scrape_article_content(url: str) -> str:
    try:
        from html.parser import HTMLParser
        headers  = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []; self._skip = False
            def handle_starttag(self, tag, attrs):
                if tag in ('script', 'style', 'nav', 'footer', 'header'): self._skip = True
            def handle_endtag(self, tag):
                if tag in ('script', 'style', 'nav', 'footer', 'header'): self._skip = False
            def handle_data(self, data):
                if not self._skip and data.strip(): self.text.append(data.strip())

        parser = TextExtractor()
        parser.feed(response.text)
        return (" ".join(parser.text))[:2000]
    except Exception:
        return ""


def parse_cryptocompare(items: list) -> list:
    noticias = []
    for item in items:
        try:
            ts        = item.get("published_on", 0)
            timestamp = int(ts) * 1000
            url       = item.get("url", "")
            noticias.append({
                "timestamp":   timestamp,
                "datetime":    datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                "title":       item.get("title", ""),
                "source":      item.get("source_info", {}).get("name", "CryptoCompare"),
                "url":         url,
                "contenido":   scrape_article_content(url) if url else item.get("title", ""),
                "fuente_tipo": "cryptoCompare",
            })
        except Exception as e:
            logger.debug(f"Error parseando noticia: {e}")
    return noticias


# ============================================================
# FUENTE 2 — Claude búsqueda macro
# ============================================================

def search_macro_news_with_claude() -> list:
    if TEST_MODE or not CLAUDE_API_KEY:
        return []
    import anthropic

    ahora  = datetime.now().strftime('%Y-%m-%d %H:%M')
    prompt = f"""Fecha: {ahora}
Busca en internet las noticias macro más recientes que afecten a criptomonedas:
1. Decisiones FED/bancos centrales  2. Inflación (CPI, PCE)  3. Conflictos geopolíticos
4. Aranceles/guerras comerciales    5. Crisis bancarias        6. Regulaciones crypto
7. Volatilidad S&P500/Nasdaq/DXY

Responde SOLO con JSON array (sin texto extra, sin markdown):
[{{"titulo":"...","resumen":"...","categoria":"fed|inflacion|geopolitica|aranceles|crisis_bancaria|regulacion_crypto|mercados|otro","razon_relevancia":"...","sentimiento":"positive|negative|neutral","impacto":"high|medium|low","fecha_aproximada":"YYYY-MM-DD"}}]
Máximo 8 noticias. Si no hay relevantes, responde [].
"""
    try:
        client  = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model=CLAUDE_HAIKU_MODEL, max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        respuesta = ""
        for block in message.content:
            if block.type == "text":
                respuesta = block.text.strip(); break

        if respuesta.startswith("```"):
            respuesta = respuesta.split("```")[1]
            if respuesta.startswith("json"): respuesta = respuesta[4:]
        respuesta = respuesta.strip()

        noticias_macro = json.loads(respuesta)
        resultado = []
        for n in noticias_macro:
            try:
                fecha = n.get("fecha_aproximada", "")
                if fecha and fecha != "reciente" and len(fecha) == 10:
                    dt  = datetime.strptime(fecha, "%Y-%m-%d")
                    ts  = int(dt.timestamp() * 1000)
                    dts = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    ts  = int(datetime.now().timestamp() * 1000)
                    dts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                ts  = int(datetime.now().timestamp() * 1000)
                dts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            resultado.append({
                "timestamp": ts, "datetime": dts,
                "title":     n.get("titulo", ""),
                "source":    "Claude Web Search",
                "url":       "",
                "contenido": n.get("resumen", ""),
                "fuente_tipo": "web_search",
                "pre_sentimiento": n.get("sentimiento", "neutral"),
                "pre_impacto":     n.get("impacto", "low"),
                "pre_resumen":     n.get("resumen", ""),
                "pre_categoria":   n.get("categoria", "macro"),
                "pre_razon":       n.get("razon_relevancia", ""),
            })
        return resultado
    except Exception as e:
        logger.warning(f"Error búsqueda macro: {e}")
        return []


# ============================================================
# ANÁLISIS CON CLAUDE
# ============================================================

def _get_recent_news_from_db(limit: int = 50) -> str:
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT title, url FROM news ORDER BY timestamp DESC LIMIT {PH}", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return "\n".join(f"  [{i}] {dict(r).get('title','')} | {dict(r).get('url','')}" for i, r in enumerate(rows)) or "Sin noticias previas."
    except Exception:
        return "Sin noticias previas."


def analyze_news_with_claude(noticias_raw: list) -> list:
    if TEST_MODE or not CLAUDE_API_KEY:
        return []
    if not noticias_raw:
        return []
    import anthropic

    noticias_en_bd = _get_recent_news_from_db(50)
    noticias_texto = ""
    for i, n in enumerate(noticias_raw):
        noticias_texto += f"\n[{i}] FUENTE: {n.get('fuente_tipo','?')}\n"
        noticias_texto += f"    TÍTULO: {n.get('title','')}\n"
        noticias_texto += f"    CONTENIDO: {n.get('contenido','')[:500]}\n"

    cryptos_str = ", ".join(list(CRYPTO_NAMES.keys())[:10])

    prompt = f"""Eres un analista experto en mercados de criptomonedas.

NOTICIAS YA EN BD (no duplicar):
{noticias_en_bd}

NOTICIAS A ANALIZAR ({len(noticias_raw)}):
{noticias_texto}

Cryptos del sistema: {cryptos_str}

Selecciona solo las nuevas y relevantes (máx 15). Responde SOLO con JSON array:
[{{"indice_original":0,"titulo":"...","resumen":"...en español 2-3 oraciones...","sentimiento":"positive|negative|neutral","impacto":"high|medium|low","cryptos_afectadas":["BTCUSDT"],"razon_impacto":"...","categoria":"crypto|macro|regulacion|geopolitica|mercados|otro","fuente_tipo":"cryptoCompare|web_search"}}]
Si no hay noticias nuevas relevantes, responde [].
"""
    try:
        client  = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model=CLAUDE_HAIKU_MODEL, max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        respuesta = ""
        for block in message.content:
            if block.type == "text":
                respuesta = block.text.strip(); break

        if respuesta.startswith("```"):
            respuesta = respuesta.split("```")[1]
            if respuesta.startswith("json"): respuesta = respuesta[4:]
        respuesta = respuesta.strip()

        noticias_analizadas = json.loads(respuesta)
        resultado = []
        for analisis in noticias_analizadas:
            idx      = analisis.get("indice_original", -1)
            original = noticias_raw[idx] if 0 <= idx < len(noticias_raw) else {}
            resultado.append({
                "timestamp":     original.get("timestamp", int(datetime.now().timestamp() * 1000)),
                "datetime":      original.get("datetime", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                "title":         analisis.get("titulo", original.get("title", "")),
                "source":        original.get("source", ""),
                "url":           original.get("url", ""),
                "crypto":        (analisis.get("cryptos_afectadas") or ["GENERAL"])[0],
                "sentiment":     analisis.get("sentimiento", "neutral"),
                "impact":        analisis.get("impacto", "low"),
                "resumen":       analisis.get("resumen", ""),
                "razon_impacto": analisis.get("razon_impacto", ""),
                "categoria":     analisis.get("categoria", "crypto"),
                "fuente_tipo":   analisis.get("fuente_tipo", original.get("fuente_tipo", "cryptoCompare")),
            })
        return resultado
    except Exception as e:
        logger.warning(f"Error analizando noticias con Claude: {e}")
        return []


# ============================================================
# GUARDADO EN BASE DE DATOS
# ============================================================

def save_news(noticias: list) -> int:
    if not noticias:
        return 0

    conn   = get_connection()
    cursor = conn.cursor()
    nuevas = 0

    for n in noticias:
        try:
            vals = (
                n.get("timestamp"), n.get("datetime"),
                n.get("title"), n.get("source"), n.get("url"),
                n.get("crypto", "GENERAL"),
                n.get("sentiment", "neutral"), n.get("impact", "low"),
                n.get("resumen", ""), n.get("razon_impacto", ""),
                n.get("categoria", "crypto"), n.get("fuente_tipo", "cryptoCompare"),
            )
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO news
                    (timestamp, datetime, title, source, url,
                     crypto, sentiment, impact,
                     resumen, razon_impacto, categoria, fuente_tipo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (timestamp) DO NOTHING
                """, vals)
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO news
                    (timestamp, datetime, title, source, url,
                     crypto, sentiment, impact,
                     resumen, razon_impacto, categoria, fuente_tipo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, vals)
            if cursor.rowcount > 0:
                nuevas += 1
        except Exception as e:
            logger.warning(f"Error guardando noticia: {e}")

    conn.commit()
    conn.close()
    return nuevas


# ============================================================
# RECOLECCIÓN PRINCIPAL
# ============================================================

def collect_news(verbose: bool = True, mode: str = None) -> int:
    modo_activo    = mode if mode else NEWS_MODE
    todas          = []

    if modo_activo in ("crypto", "ambas"):
        try:
            items   = fetch_cryptocompare(limit=30)
            cryptos = parse_cryptocompare(items)
            todas.extend(cryptos)
            if verbose: print(f"   ✅ CryptoCompare: {len(cryptos)} noticias descargadas")
        except Exception as e:
            if verbose: print(f"   ⚠️  CryptoCompare: {e}")

    if modo_activo in ("macro", "ambas") and not TEST_MODE and CLAUDE_API_KEY:
        try:
            macro = search_macro_news_with_claude()
            todas.extend(macro)
            if verbose: print(f"   ✅ Claude macro: {len(macro)} noticias encontradas")
        except Exception as e:
            if verbose: print(f"   ⚠️  Claude macro: {e}")

    if not todas:
        return 0

    analizadas = analyze_news_with_claude(todas) if not TEST_MODE and CLAUDE_API_KEY else []
    nuevas     = save_news(analizadas)
    if verbose: print(f"   💾 {nuevas} noticias nuevas guardadas")
    return nuevas


# ============================================================
# RESUMEN PARA CLAUDE ANALYST
# ============================================================

def get_news_summary(crypto: str = None, limit: int = 10) -> str:
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        if crypto:
            cursor.execute(f"""
                SELECT datetime, title, source, sentiment, impact,
                       crypto, resumen, razon_impacto, categoria, fuente_tipo
                FROM news
                WHERE crypto = {PH} OR crypto = 'GENERAL'
                ORDER BY timestamp DESC LIMIT {PH}
            """, (crypto, limit))
        else:
            cursor.execute(f"""
                SELECT datetime, title, source, sentiment, impact,
                       crypto, resumen, razon_impacto, categoria, fuente_tipo
                FROM news
                ORDER BY timestamp DESC LIMIT {PH}
            """, (limit,))
        rows = cursor.fetchall()
    except Exception as e:
        logger.warning(f"Error obteniendo noticias: {e}")
        rows = []

    conn.close()

    if not rows:
        return "No hay noticias recientes disponibles."

    resumen_txt  = f"📰 ÚLTIMAS {len(rows)} NOTICIAS:\n" + "━" * 50 + "\n"
    for row in rows:
        row = dict(row)
        sent_emoji   = "🟢" if row.get('sentiment') == "positive" else "🔴" if row.get('sentiment') == "negative" else "🟡"
        impact_emoji = "🔴" if row.get('impact') == "high" else "🟡" if row.get('impact') == "medium" else "🟢"
        cat_tag      = f"[{row.get('categoria')}] " if row.get('categoria') else ""

        resumen_txt += f"{row.get('datetime')} [{row.get('crypto')}] {cat_tag}\n"
        resumen_txt += f"{sent_emoji} {row.get('title','')}\n"
        if row.get('resumen'):
            resumen_txt += f"   📝 {row.get('resumen')}\n"
        if row.get('razon_impacto'):
            resumen_txt += f"   💡 {row.get('razon_impacto')}\n"
        resumen_txt += f"   Fuente: {row.get('source','')} | Impacto: {impact_emoji} {row.get('impact','')}\n\n"

    return resumen_txt

# ============================================================
# data_collector.py — Descarga velas de Binance y las guarda
# Adaptado para PostgreSQL (Supabase) y SQLite (local)
# ============================================================

import requests
import pandas as pd
from datetime import datetime
import time
import ta
from error_handler import (
    setup_logger, BinanceError, BinanceTimeoutError,
    BinanceRateLimitError, CryptoNotFoundError, DatabaseError
)

logger = setup_logger(__name__)

from config import (
    CRYPTOS, ACTIVE_CRYPTOS, TIMEFRAMES, CANDLES_LIMIT,
    RSI_PERIOD, EMA_FAST, EMA_SLOW, EMA_LONG,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOLLINGER_PERIOD, BOLLINGER_STD
)
from database import get_connection, get_last_timestamp, USE_POSTGRES

BINANCE_BASE_URL = "https://api2.binance.com/api/v3"


# ============================================================
# DESCARGA DE VELAS DESDE BINANCE
# ============================================================

def fetch_candles(symbol: str, interval: str, limit: int = 1000, start_time: int = None) -> list:
    url    = f"{BINANCE_BASE_URL}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time:
        params["startTime"] = start_time + 1

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as e:
        err = BinanceError("Sin conexión — verifica tu red",
                           context={"crypto": symbol, "timeframe": interval, "error": str(e)})
        err.log(logger); err.show()
        return []
    except requests.exceptions.Timeout as e:
        err = BinanceTimeoutError("Timeout con Binance",
                                  context={"crypto": symbol, "timeframe": interval, "error": str(e)})
        err.log(logger); err.show()
        return []
    except Exception as e:
        err = BinanceError("Error descargando datos de Binance",
                           context={"crypto": symbol, "timeframe": interval, "error": str(e)})
        err.log(logger); err.show()
        return []


# ============================================================
# INDICADORES TÉCNICOS
# ============================================================

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 30:
        return df
    try:
        close  = df['close']
        high   = df['high']
        low    = df['low']
        volume = df['volume']

        df['rsi'] = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi()

        macd = ta.trend.MACD(close=close, window_fast=MACD_FAST,
                              window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
        df['macd']        = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist']   = macd.macd_diff()

        df['ema_20']  = ta.trend.EMAIndicator(close=close, window=EMA_FAST).ema_indicator()
        df['ema_50']  = ta.trend.EMAIndicator(close=close, window=EMA_SLOW).ema_indicator()
        df['ema_200'] = ta.trend.EMAIndicator(close=close, window=EMA_LONG).ema_indicator()
        df['sma_200'] = ta.trend.SMAIndicator(close=close, window=200).sma_indicator()

        bb = ta.volatility.BollingerBands(close=close, window=BOLLINGER_PERIOD, window_dev=BOLLINGER_STD)
        df['bb_upper']  = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower']  = bb.bollinger_lband()
        df['bb_width']  = bb.bollinger_wband()

        adx = ta.trend.ADXIndicator(high=high, low=low, close=close, window=14)
        df['adx']     = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()

        stoch_rsi = ta.momentum.StochRSIIndicator(close=close, window=14)
        df['stoch_rsi_k'] = stoch_rsi.stochrsi_k()
        df['stoch_rsi_d'] = stoch_rsi.stochrsi_d()

        df['atr'] = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
        df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
        df['cci'] = ta.trend.CCIIndicator(high=high, low=low, close=close, window=20).cci()
        df['williams_r'] = ta.momentum.WilliamsRIndicator(high=high, low=low, close=close, lbp=14).williams_r()
        df['momentum'] = ta.momentum.ROCIndicator(close=close, window=10).roc()
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
            high=high, low=low, close=close, volume=volume).volume_weighted_average_price()

    except Exception as e:
        logger.warning(f"Error calculando indicadores: {e}")
    return df


# ============================================================
# SNAPSHOTS HISTÓRICOS
# ============================================================

def get_historical_snapshots(crypto: str, timeframe: str) -> list:
    conn    = get_connection()
    cursor  = conn.cursor()
    table   = f"candles_{crypto.lower()}_{timeframe}"

    periodos = {
        "1d": ([7, 14, 30, 60, 90], ["hace 1 sem", "hace 2 sem", "hace 1 mes", "hace 2 mes", "hace 3 mes"]),
    }
    velas_atras, nombres = periodos.get(timeframe, ([7, 14, 30], ["p1", "p2", "p3"]))
    snapshots = []

    for i, n_velas in enumerate(velas_atras):
        try:
            if USE_POSTGRES:
                cursor.execute(f"""
                    SELECT datetime, close, rsi, macd, ema_20, ema_200, adx, atr, momentum
                    FROM {table}
                    ORDER BY timestamp DESC
                    LIMIT 1 OFFSET %s
                """, (n_velas,))
            else:
                cursor.execute(f"""
                    SELECT datetime, close, rsi, macd, ema_20, ema_200, adx, atr, momentum
                    FROM {table}
                    ORDER BY timestamp DESC
                    LIMIT 1 OFFSET ?
                """, (n_velas,))
            row = cursor.fetchone()
            if row:
                row = dict(row)
                tendencia = "neutral"
                if row.get('close') and row.get('ema_200'):
                    if row['close'] > row['ema_200'] and (row.get('rsi') or 0) > 50:
                        tendencia = "alcista"
                    elif row['close'] < row['ema_200'] and (row.get('rsi') or 0) < 50:
                        tendencia = "bajista"
                snapshots.append({
                    "periodo":   nombres[i] if i < len(nombres) else f"hace {n_velas} velas",
                    "datetime":  row.get('datetime'),
                    "precio":    row.get('close'),
                    "rsi":       round(row['rsi'], 1) if row.get('rsi') else None,
                    "adx":       round(row['adx'], 1) if row.get('adx') else None,
                    "momentum":  round(row['momentum'], 2) if row.get('momentum') else None,
                    "tendencia": tendencia,
                })
        except Exception as e:
            logger.debug(f"Error snapshot: {e}")
            continue

    conn.close()
    return snapshots


# ============================================================
# GUARDADO EN BASE DE DATOS — Compatible con Postgres y SQLite
# ============================================================

def save_candles(crypto: str, timeframe: str, raw_candles: list) -> int:
    if not raw_candles:
        return 0

    df = pd.DataFrame(raw_candles, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df['timestamp'] = df['timestamp'].astype(int)
    df['datetime']  = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')

    table_name = f"candles_{crypto.lower()}_{timeframe}"
    conn   = get_connection()
    cursor = conn.cursor()

    # Cargar historial + nuevas velas para indicadores correctos
    try:
        cursor.execute(f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {table_name}
            ORDER BY timestamp ASC
        """)
        hist_rows = cursor.fetchall()
        if hist_rows:
            df_hist = pd.DataFrame([dict(r) for r in hist_rows])
            df_hist = df_hist.astype({'timestamp': int, 'open': float,
                'high': float, 'low': float, 'close': float, 'volume': float})
            df_combined = pd.concat(
                [df_hist, df[['timestamp','open','high','low','close','volume']]],
                ignore_index=True
            )
            df_combined = df_combined.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            df_combined['datetime'] = pd.to_datetime(
                df_combined['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
            df_combined = calculate_indicators(df_combined)
            new_timestamps = set(df['timestamp'].astype(int).tolist())
            df = df_combined[df_combined['timestamp'].isin(new_timestamps)].copy()
        else:
            df = calculate_indicators(df)
    except Exception as e:
        logger.warning(f"No se pudo cargar historial para {crypto} {timeframe}: {e}")
        df = calculate_indicators(df)

    nuevas = 0
    ph     = "%s" if USE_POSTGRES else "?"

    for _, row in df.iterrows():
        try:
            vals = (
                int(row['timestamp']), row['datetime'],
                row['open'], row['high'], row['low'], row['close'], row['volume'],
                row.get('rsi'),       row.get('macd'),
                row.get('macd_signal'), row.get('macd_hist'),
                row.get('ema_20'),    row.get('ema_50'),
                row.get('ema_200'),   row.get('sma_200'),
                row.get('bb_upper'),  row.get('bb_middle'),
                row.get('bb_lower'),  row.get('bb_width'),
                row.get('adx'),       row.get('adx_pos'),   row.get('adx_neg'),
                row.get('stoch_rsi_k'), row.get('stoch_rsi_d'),
                row.get('atr'),       row.get('obv'),
                row.get('cci'),       row.get('williams_r'),
                row.get('momentum'),  row.get('vwap'),
            )
            placeholders = ",".join([ph] * len(vals))

            if USE_POSTGRES:
                cursor.execute(f"""
                    INSERT INTO {table_name}
                    (timestamp, datetime, open, high, low, close, volume,
                     rsi, macd, macd_signal, macd_hist,
                     ema_20, ema_50, ema_200, sma_200,
                     bb_upper, bb_middle, bb_lower, bb_width,
                     adx, adx_pos, adx_neg, stoch_rsi_k, stoch_rsi_d,
                     atr, obv, cci, williams_r, momentum, vwap)
                    VALUES ({placeholders})
                    ON CONFLICT (timestamp) DO NOTHING
                """, vals)
            else:
                cursor.execute(f"""
                    INSERT OR IGNORE INTO {table_name}
                    (timestamp, datetime, open, high, low, close, volume,
                     rsi, macd, macd_signal, macd_hist,
                     ema_20, ema_50, ema_200, sma_200,
                     bb_upper, bb_middle, bb_lower, bb_width,
                     adx, adx_pos, adx_neg, stoch_rsi_k, stoch_rsi_d,
                     atr, obv, cci, williams_r, momentum, vwap)
                    VALUES ({placeholders})
                """, vals)

            if cursor.rowcount > 0:
                nuevas += 1
        except Exception as e:
            logger.warning(f"Error guardando vela: {e}")
            continue

    conn.commit()
    conn.close()
    return nuevas


# ============================================================
# ANÁLISIS PROFUNDO CON CLAUDE
# ============================================================

def analyze_deep_with_claude(crypto: str) -> dict:
    from config import CLAUDE_API_KEY, CLAUDE_MODEL, TEST_MODE
    import anthropic, json

    if TEST_MODE or not CLAUDE_API_KEY:
        return _mock_deep_analysis(crypto)

    conn = get_connection()
    csvs = {}; csvs_pat = {}

    configs = [
        ("15m", 200), ("30m", 200), ("1h", 200), ("4h", 150), ("1d", 365),
    ]

    for timeframe, limit in configs:
        try:
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute(f"""
                    SELECT datetime, open, high, low, close, volume,
                           rsi, macd_hist, ema_20, ema_50, ema_200,
                           adx, atr, obv, momentum, bb_upper, bb_lower
                    FROM (
                        SELECT * FROM candles_{crypto.lower()}_{timeframe}
                        ORDER BY timestamp DESC
                        LIMIT %s
                    ) sub ORDER BY timestamp ASC
                """, (limit,))
            else:
                cursor.execute(f"""
                    SELECT datetime, open, high, low, close, volume,
                           rsi, macd_hist, ema_20, ema_50, ema_200,
                           adx, atr, obv, momentum, bb_upper, bb_lower
                    FROM (
                        SELECT * FROM candles_{crypto.lower()}_{timeframe}
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ) ORDER BY timestamp ASC
                """, (limit,))
            rows = cursor.fetchall()
            if rows:
                df = pd.DataFrame([dict(r) for r in rows])
                csvs[timeframe]     = df.to_csv(index=False, float_format='%.4f')
                csvs_pat[timeframe] = df.tail(45).to_csv(index=False, float_format='%.4f')
        except Exception as e:
            logger.warning(f"Error extrayendo datos {timeframe} para {crypto}: {e}")

    conn.close()

    if not csvs:
        return _mock_deep_analysis(crypto)

    precio_actual = get_current_price(crypto)

    prompt = f"""Eres un experto en análisis técnico de criptomonedas.
Analiza los siguientes datos históricos de {crypto} y responde ÚNICAMENTE con un JSON válido.
Los datos están en orden cronológico (más antigua primero, más reciente al final).

PRECIO ACTUAL: ${precio_actual:,.4f}

DATOS 15M: {csvs.get('15m','Sin datos')}
DATOS 30M: {csvs.get('30m','Sin datos')}
DATOS 1H: {csvs.get('1h','Sin datos')}
DATOS 4H: {csvs.get('4h','Sin datos')}
DATOS 1D: {csvs.get('1d','Sin datos')}

PATRONES 15M (últimas 45 velas): {csvs_pat.get('15m','Sin datos')}
PATRONES 1H (últimas 45 velas): {csvs_pat.get('1h','Sin datos')}
PATRONES 4H (últimas 45 velas): {csvs_pat.get('4h','Sin datos')}
PATRONES 1D (últimas 45 velas): {csvs_pat.get('1d','Sin datos')}

Responde SOLO con este JSON (sin texto extra, sin markdown):
{{
  "tendencia_por_timeframe": {{
    "15m": {{"tendencia": "ALCISTA|BAJISTA|NEUTRAL", "explicacion": "..."}},
    "30m": {{"tendencia": "ALCISTA|BAJISTA|NEUTRAL", "explicacion": "..."}},
    "1h":  {{"tendencia": "ALCISTA|BAJISTA|NEUTRAL", "explicacion": "..."}},
    "4h":  {{"tendencia": "ALCISTA|BAJISTA|NEUTRAL", "explicacion": "..."}},
    "1d":  {{"tendencia": "ALCISTA|BAJISTA|NEUTRAL", "explicacion": "..."}}
  }},
  "tendencia_general": "ALCISTA|BAJISTA|NEUTRAL",
  "tendencia_explicacion": "...",
  "soportes": [{{"nivel": 0.0, "fuerza": "FUERTE|MODERADO|DEBIL", "timeframe_origen": "1h", "descripcion": "..."}}],
  "resistencias": [{{"nivel": 0.0, "fuerza": "FUERTE|MODERADO|DEBIL", "timeframe_origen": "1h", "descripcion": "..."}}],
  "stop_loss": {{"conservador": 0.0, "agresivo": 0.0, "explicacion": "..."}},
  "patrones_detectados": [{{"nombre": "...", "tipo": "bullish|bearish|neutral", "timeframe": "1h", "descripcion": "..."}}],
  "divergencias": [{{"tipo": "alcista|bajista", "indicador": "RSI|MACD|OBV", "timeframe": "1h", "descripcion": "..."}}],
  "niveles_clave": {{"soporte_critico": 0.0, "resistencia_critica": 0.0, "zona_decision": "..."}}
}}
Máximo 3 soportes y 3 resistencias. Si un timeframe no tiene datos pon NEUTRAL con "Sin datos suficientes".
"""

    try:
        client   = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message  = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        respuesta = message.content[0].text.strip()
        if respuesta.startswith("```"):
            respuesta = respuesta.split("```")[1]
            if respuesta.startswith("json"):
                respuesta = respuesta[4:]
        return json.loads(respuesta.strip())
    except Exception as e:
        logger.warning(f"Error en análisis profundo de {crypto}: {e}")
        return _mock_deep_analysis(crypto)


def _mock_deep_analysis(crypto: str) -> dict:
    tf_vacio = {"tendencia": "NEUTRAL", "explicacion": "Sin API key — configura CLAUDE_API_KEY"}
    return {
        "tendencia_por_timeframe": {
            "15m": tf_vacio, "30m": tf_vacio,
            "1h": tf_vacio, "4h": tf_vacio, "1d": tf_vacio
        },
        "tendencia_general": "NEUTRAL",
        "tendencia_explicacion": "Análisis no disponible",
        "soportes": [], "resistencias": [],
        "stop_loss": {"conservador": None, "agresivo": None, "explicacion": "No disponible"},
        "patrones_detectados": [], "divergencias": [],
        "niveles_clave": {"soporte_critico": None, "resistencia_critica": None, "zona_decision": "No disponible"}
    }


# ============================================================
# RESUMEN TÉCNICO PARA CLAUDE ANALYST
# ============================================================

def get_technical_summary(crypto: str, timeframes: list = None) -> str:
    if timeframes is None:
        from config import TIMEFRAMES
        timeframes = TIMEFRAMES

    conn    = get_connection()
    resumen = f"\n📊 ANÁLISIS TÉCNICO COMPLETO — {crypto}\n"
    resumen += "━" * 55 + "\n"

    print(f"   🤖 Analizando {crypto} con Claude (S/R, patrones, tendencia)...")
    deep_analysis = analyze_deep_with_claude(crypto)

    for timeframe in timeframes:
        table = f"candles_{crypto.lower()}_{timeframe}"
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT datetime, close, volume,
                       rsi, macd, macd_hist,
                       ema_20, ema_50, ema_200,
                       bb_upper, bb_lower, bb_width,
                       adx, adx_pos, adx_neg,
                       stoch_rsi_k, stoch_rsi_d,
                       atr, obv, cci, williams_r, momentum, vwap
                FROM {table}
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                continue
            row = dict(row)

            tf_data   = deep_analysis.get("tendencia_por_timeframe", {}).get(timeframe, {})
            tendencia = tf_data.get("tendencia", "PENDIENTE")

            fuerza_adx = "sin tendencia"
            if row.get('adx'):
                adx = row['adx']
                if adx < 20:   fuerza_adx = "sin tendencia clara"
                elif adx < 40: fuerza_adx = "tendencia moderada"
                elif adx < 60: fuerza_adx = "tendencia fuerte"
                else:          fuerza_adx = "tendencia extrema"

            sl_data = deep_analysis.get("stop_loss", {})

            resumen += f"\n⏱️  {timeframe.upper()} | {row.get('datetime')} | {tendencia}\n"
            resumen += f"   Precio: ${row.get('close', 0):,.2f} | VWAP: ${round(row['vwap'],2) if row.get('vwap') else 'N/A'}\n"
            resumen += f"   RSI: {round(row['rsi'],1) if row.get('rsi') else 'N/A'}"
            resumen += f" | StochRSI K/D: {round(row['stoch_rsi_k'],1) if row.get('stoch_rsi_k') else 'N/A'}/{round(row['stoch_rsi_d'],1) if row.get('stoch_rsi_d') else 'N/A'}\n"
            resumen += f"   MACD hist: {round(row['macd_hist'],2) if row.get('macd_hist') else 'N/A'}"
            resumen += f" | Momentum: {round(row['momentum'],2) if row.get('momentum') else 'N/A'}\n"
            resumen += f"   EMA20/50/200: {round(row['ema_20'],0) if row.get('ema_20') else 'N/A'} / {round(row['ema_50'],0) if row.get('ema_50') else 'N/A'} / {round(row['ema_200'],0) if row.get('ema_200') else 'N/A'}\n"
            resumen += f"   ADX: {round(row['adx'],1) if row.get('adx') else 'N/A'} ({fuerza_adx})\n"
            if sl_data.get("conservador"):
                resumen += f"   🛑 Stop Loss conservador: ${sl_data['conservador']:,.2f}\n"

        except Exception as e:
            resumen += f"\n   ⚠️ Error {timeframe}: {e}\n"

    # Snapshots históricos
    snapshots = get_historical_snapshots(crypto, "1d")
    if snapshots:
        resumen += "\n📅 EVOLUCIÓN HISTÓRICA (1D):\n" + "━" * 55 + "\n"
        for s in snapshots:
            resumen += f"   {s['periodo']:12} | ${s.get('precio',0):>10,.2f} | RSI:{s.get('rsi') or 'N/A'} | {s['tendencia']}\n"

    # S/R y patrones
    soportes     = deep_analysis.get("soportes", [])
    resistencias = deep_analysis.get("resistencias", [])
    niveles      = deep_analysis.get("niveles_clave", {})

    resumen += "\n🎯 SOPORTES Y RESISTENCIAS:\n"
    for r in resistencias:
        resumen += f"   🔴 ${r['nivel']:,.2f} [{r['fuerza']}] — {r['descripcion']}\n"
    for s in soportes:
        resumen += f"   🟢 ${s['nivel']:,.2f} [{s['fuerza']}] — {s['descripcion']}\n"
    if niveles.get("zona_decision"):
        resumen += f"   ⚡ Zona clave: {niveles['zona_decision']}\n"

    resumen += "\n📈 TENDENCIA POR TIMEFRAME:\n"
    tf_tendencias = deep_analysis.get("tendencia_por_timeframe", {})
    for tf in ["15m", "30m", "1h", "4h", "1d"]:
        d = tf_tendencias.get(tf, {})
        t = d.get("tendencia", "N/A")
        emoji = "🟢" if t == "ALCISTA" else "🔴" if t == "BAJISTA" else "🟡"
        resumen += f"   {emoji} {tf.upper():>3}: {t:8} — {d.get('explicacion','')}\n"
    resumen += f"\n   📊 CONCLUSIÓN: {deep_analysis.get('tendencia_general','N/A')} — {deep_analysis.get('tendencia_explicacion','N/A')}\n"

    for p in deep_analysis.get("patrones_detectados", []) + deep_analysis.get("divergencias", []):
        emoji = "🟢" if p.get('tipo') in ['bullish','alcista'] else "🔴" if p.get('tipo') in ['bearish','bajista'] else "🟡"
        tf    = f"[{p['timeframe']}] " if 'timeframe' in p else ""
        resumen += f"   {emoji} {tf}{p['nombre']}: {p['descripcion']}\n"

    conn.close()
    return resumen


# ============================================================
# RECOLECCIÓN PRINCIPAL
# ============================================================

def collect_all(verbose: bool = True) -> dict:
    resumen = {}
    for crypto in ACTIVE_CRYPTOS:
        resumen[crypto] = {}
        if verbose:
            print(f"\n📊 Recolectando {crypto}...")
        for timeframe in TIMEFRAMES:
            last_ts = get_last_timestamp(crypto, timeframe)
            limit   = CANDLES_LIMIT.get(timeframe, 1000)
            raw     = fetch_candles(crypto, timeframe, limit=limit, start_time=last_ts)
            if not raw:
                resumen[crypto][timeframe] = 0
                continue
            nuevas = save_candles(crypto, timeframe, raw)
            resumen[crypto][timeframe] = nuevas
            if verbose:
                print(f"   ✅ {timeframe}: {nuevas} velas nuevas guardadas")
            time.sleep(0.2)
    return resumen


def get_current_price(crypto: str) -> float:
    try:
        url      = f"{BINANCE_BASE_URL}/ticker/price"
        response = requests.get(url, params={"symbol": crypto}, timeout=5)
        return float(response.json()['price'])
    except Exception as e:
        logger.warning(f"Error obteniendo precio de {crypto}: {e}")
        return 0.0


def get_all_prices() -> dict:
    precios = {}
    for crypto in ACTIVE_CRYPTOS:
        precios[crypto] = get_current_price(crypto)
    return precios

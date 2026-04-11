# ============================================================
# positions.py — Gestión de posiciones de trading
# Adaptado para PostgreSQL (Supabase) y SQLite (local)
# ============================================================

from datetime import datetime
from database import get_connection, get_open_positions, get_recent_lessons, USE_POSTGRES
from data_collector import get_current_price
from config import CRYPTO_NAMES
from error_handler import setup_logger, PositionError, PositionNotFoundError, PositionAlreadyClosedError

logger = setup_logger(__name__)

PH = "%s" if USE_POSTGRES else "?"


# ============================================================
# ABRIR POSICIÓN
# ============================================================

def open_position(crypto: str, entry_price: float, entry_time: str,
                  timeframe_focus: str = None, notes: str = None) -> int:
    conn   = get_connection()
    cursor = conn.cursor()

    rsi_15m = rsi_1h = macd_1h = adx_1h = atr_1h = rsi_1d = None
    trend_1d = "desconocida"

    try:
        cursor.execute(f"""
            SELECT rsi FROM candles_{crypto.lower()}_15m
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            rsi_15m = dict(row).get('rsi')

        cursor.execute(f"""
            SELECT rsi, macd_hist, adx, atr FROM candles_{crypto.lower()}_1h
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            row = dict(row)
            rsi_1h = row.get('rsi'); macd_1h = row.get('macd_hist')
            adx_1h = row.get('adx'); atr_1h  = row.get('atr')

        cursor.execute(f"""
            SELECT rsi, close, ema_200 FROM candles_{crypto.lower()}_1d
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            row = dict(row)
            rsi_1d     = row.get('rsi')
            close_1d   = row.get('close')
            ema_200_1d = row.get('ema_200')
            trend_1d   = "alcista" if (close_1d and ema_200_1d and close_1d > ema_200_1d) else "bajista"

    except Exception as e:
        logger.warning(f"No se pudieron obtener indicadores al abrir posicion en {crypto}: {e}")

    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO positions
            (crypto, status, entry_price, entry_time, entry_timestamp,
             timeframe_focus,
             entry_rsi_15m, entry_rsi_1h, entry_rsi_1d,
             entry_macd_1h, entry_adx_1h, entry_trend_1d, entry_atr_1h,
             notes)
            VALUES (%s,'open',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            crypto, entry_price, entry_time,
            int(datetime.now().timestamp() * 1000),
            timeframe_focus,
            rsi_15m, rsi_1h, rsi_1d,
            macd_1h, adx_1h, trend_1d, atr_1h,
            notes
        ))
        position_id = cursor.fetchone()['id']
    else:
        cursor.execute("""
            INSERT INTO positions
            (crypto, status, entry_price, entry_time, entry_timestamp,
             timeframe_focus,
             entry_rsi_15m, entry_rsi_1h, entry_rsi_1d,
             entry_macd_1h, entry_adx_1h, entry_trend_1d, entry_atr_1h,
             notes)
            VALUES (?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            crypto, entry_price, entry_time,
            int(datetime.now().timestamp() * 1000),
            timeframe_focus,
            rsi_15m, rsi_1h, rsi_1d,
            macd_1h, adx_1h, trend_1d, atr_1h,
            notes
        ))
        position_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return position_id


# ============================================================
# CERRAR POSICIÓN
# ============================================================

def close_position(position_id: int, exit_price: float, exit_time: str,
                   notes: str = None) -> dict:
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM positions WHERE id = {PH}", (position_id,))
    pos = cursor.fetchone()
    if not pos:
        conn.close()
        return {}
    pos = dict(pos)

    if pos['status'] != 'open':
        conn.close()
        return {}

    entry_price = pos['entry_price']
    result_pct  = ((exit_price - entry_price) / entry_price) * 100
    result      = "win" if result_pct > 0 else "loss"

    crypto = pos['crypto']
    exit_rsi_15m = exit_rsi_1h = exit_adx_1h = None
    try:
        cursor.execute(f"SELECT rsi FROM candles_{crypto.lower()}_15m ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if row: exit_rsi_15m = dict(row).get('rsi')

        cursor.execute(f"SELECT rsi, adx FROM candles_{crypto.lower()}_1h ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            row = dict(row)
            exit_rsi_1h = row.get('rsi'); exit_adx_1h = row.get('adx')
    except Exception as e:
        logger.warning(f"No se pudieron obtener indicadores al cerrar #{position_id}: {e}")

    if USE_POSTGRES:
        notes_update = f"COALESCE(notes || ' | ' || %s::text, notes, %s)"
        cursor.execute(f"""
            UPDATE positions SET
                status         = 'closed',
                exit_price     = %s,
                exit_time      = %s,
                exit_timestamp = %s,
                result_pct     = %s,
                exit_rsi_15m   = %s,
                exit_rsi_1h    = %s,
                exit_adx_1h    = %s,
                notes          = {notes_update}
            WHERE id = %s
        """, (
            exit_price, exit_time,
            int(datetime.now().timestamp() * 1000),
            result_pct,
            exit_rsi_15m, exit_rsi_1h, exit_adx_1h,
            notes, notes,
            position_id
        ))
    else:
        cursor.execute("""
            UPDATE positions SET
                status         = 'closed',
                exit_price     = ?,
                exit_time      = ?,
                exit_timestamp = ?,
                result_pct     = ?,
                exit_rsi_15m   = ?,
                exit_rsi_1h    = ?,
                exit_adx_1h    = ?,
                notes          = COALESCE(notes || ' | ' || ?, notes, ?)
            WHERE id = ?
        """, (
            exit_price, exit_time,
            int(datetime.now().timestamp() * 1000),
            result_pct,
            exit_rsi_15m, exit_rsi_1h, exit_adx_1h,
            notes, notes,
            position_id
        ))

    conn.commit()

    lesson_id = generate_lesson(conn, cursor, pos, exit_price, result_pct, result)
    conn.close()

    return {
        "position_id": position_id,
        "crypto":      crypto,
        "entry_price": entry_price,
        "exit_price":  exit_price,
        "result_pct":  result_pct,
        "result":      result,
        "lesson_id":   lesson_id,
    }


# ============================================================
# GENERAR LECCIÓN APRENDIDA
# ============================================================

def generate_lesson(conn, cursor, pos: dict, exit_price: float,
                    result_pct: float, result: str) -> int:
    from config import CLAUDE_API_KEY, CLAUDE_MODEL, TEST_MODE
    from news_collector import get_news_summary
    import anthropic

    crypto = pos['crypto']

    contexto = f"""
Acaba de cerrarse un trade en {CRYPTO_NAMES.get(crypto, crypto)}.
Resultado: {result_pct:+.2f}% ({result.upper()})
Entrada: ${pos['entry_price']:,.4f} @ {pos['entry_time']}
Salida: ${exit_price:,.4f}
Timeframe: {pos.get('timeframe_focus', 'no especificado')}

RSI 15M al abrir: {pos.get('entry_rsi_15m') or 'N/A'}
RSI 1H al abrir: {pos.get('entry_rsi_1h') or 'N/A'}
ADX 1H al abrir: {pos.get('entry_adx_1h') or 'N/A'}
Tendencia 1D: {pos.get('entry_trend_1d') or 'N/A'}

NOTICIAS ACTIVAS: {get_news_summary(crypto, limit=5)}

Responde en este formato exacto:
FACTOR_DOMINANTE: [TÉCNICO / FUNDAMENTAL / SENTIMIENTO / AMBOS]
EXPLICACIÓN:
[2-3 oraciones]
LECCIÓN:
[1 oración accionable]
"""

    factor = "TÉCNICO"; explicacion = ""; leccion = ""

    if not TEST_MODE and CLAUDE_API_KEY:
        try:
            client  = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            message = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=500,
                messages=[{"role": "user", "content": contexto}]
            )
            respuesta = message.content[0].text
            for line in respuesta.split('\n'):
                line = line.strip()
                if line.startswith("FACTOR_DOMINANTE:"):
                    factor = line.replace("FACTOR_DOMINANTE:", "").strip()
                elif line.startswith("EXPLICACIÓN:"):
                    idx = respuesta.find("EXPLICACIÓN:") + len("EXPLICACIÓN:")
                    fin = respuesta.find("LECCIÓN:")
                    explicacion = respuesta[idx:fin].strip()
                elif line.startswith("LECCIÓN:"):
                    idx = respuesta.find("LECCIÓN:") + len("LECCIÓN:")
                    leccion = respuesta[idx:].strip()
        except Exception as e:
            logger.warning(f"Error generando lección: {e}")
            factor      = "DESCONOCIDO"
            explicacion = f"Resultado: {result_pct:+.2f}% — lección no generada"
            leccion     = "Revisar API key de Claude"
    else:
        leccion     = f"[Modo prueba] Resultado: {result_pct:+.2f}%"
        explicacion = "Sin API key configurada"

    news_ctx = get_news_summary(crypto, limit=3)

    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO lessons
            (position_id, crypto, datetime, timeframe_focus,
             situation, news_context, action_taken,
             result, result_pct, dominant_factor, lesson_text)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            pos['id'], crypto,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            pos.get('timeframe_focus', ''),
            explicacion, news_ctx,
            f"Entrada @ ${pos['entry_price']:,.4f} → Salida @ ${exit_price:,.4f}",
            result, result_pct, factor, leccion
        ))
        lesson_id = cursor.fetchone()['id']
    else:
        cursor.execute("""
            INSERT INTO lessons
            (position_id, crypto, datetime, timeframe_focus,
             situation, news_context, action_taken,
             result, result_pct, dominant_factor, lesson_text)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            pos['id'], crypto,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            pos.get('timeframe_focus', ''),
            explicacion, news_ctx,
            f"Entrada @ ${pos['entry_price']:,.4f} → Salida @ ${exit_price:,.4f}",
            result, result_pct, factor, leccion
        ))
        lesson_id = cursor.lastrowid

    conn.commit()
    return lesson_id

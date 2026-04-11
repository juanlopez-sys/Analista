# ============================================================
# database.py — Gestión de la base de datos
# Usa PostgreSQL (Supabase) en producción, SQLite en local
# ============================================================

import os
import sqlite3
from error_handler import setup_logger, DatabaseError, TableNotFoundError

logger = setup_logger(__name__)

# ── Detectar entorno ─────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")          # Supabase en producción
DATABASE_PATH = os.getenv("DATABASE_PATH", "trading_system.db")  # SQLite local

USE_POSTGRES = bool(DATABASE_URL)

# ── Importar psycopg2 solo si estamos en producción ─────────
if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise ImportError(
            "psycopg2 no instalado. Agrega 'psycopg2-binary' a requirements.txt"
        )

from config import CRYPTOS, TIMEFRAMES


# ============================================================
# CONEXIÓN — retorna conexión correcta según entorno
# ============================================================

def get_connection():
    """
    Retorna una conexión a la base de datos.
    - En producción (Render): PostgreSQL via Supabase
    - En local: SQLite
    """
    try:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn
        else:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            return conn
    except Exception as e:
        raise DatabaseError(
            "No se pudo conectar a la base de datos",
            context={"url": DATABASE_URL or DATABASE_PATH, "error": str(e)}
        )


def _placeholder():
    """Retorna el placeholder correcto según el motor de BD."""
    return "%s" if USE_POSTGRES else "?"


def _autoincrement():
    return "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _insert_ignore(table: str) -> str:
    """Genera INSERT que ignora duplicados según motor."""
    if USE_POSTGRES:
        return f"INSERT INTO {table}"   # usamos ON CONFLICT DO NOTHING al final
    return f"INSERT OR IGNORE INTO {table}"


def _conflict_ignore() -> str:
    return "ON CONFLICT DO NOTHING" if USE_POSTGRES else ""


# ============================================================
# CREAR TABLAS
# ============================================================

def create_tables():
    """Crea todas las tablas necesarias si no existen."""
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        pk     = _autoincrement()

        # Tablas de velas por crypto + timeframe
        for crypto in CRYPTOS:
            for timeframe in TIMEFRAMES:
                table_name = f"candles_{crypto.lower()}_{timeframe}"
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id          {pk},
                        timestamp   BIGINT UNIQUE,
                        datetime    TEXT,
                        open        REAL,
                        high        REAL,
                        low         REAL,
                        close       REAL,
                        volume      REAL,
                        rsi         REAL,
                        macd        REAL,
                        macd_signal REAL,
                        macd_hist   REAL,
                        ema_20      REAL,
                        ema_50      REAL,
                        ema_200     REAL,
                        sma_200     REAL,
                        bb_upper    REAL,
                        bb_middle   REAL,
                        bb_lower    REAL,
                        bb_width    REAL,
                        adx         REAL,
                        adx_pos     REAL,
                        adx_neg     REAL,
                        stoch_rsi_k REAL,
                        stoch_rsi_d REAL,
                        atr         REAL,
                        obv         REAL,
                        cci         REAL,
                        williams_r  REAL,
                        momentum    REAL,
                        vwap        REAL
                    )
                """)

        # Noticias
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS news (
                id           {pk},
                timestamp    BIGINT UNIQUE,
                datetime     TEXT,
                title        TEXT,
                source       TEXT,
                url          TEXT,
                crypto       TEXT,
                sentiment    TEXT,
                impact       TEXT,
                processed    INTEGER DEFAULT 0,
                resumen      TEXT,
                razon_impacto TEXT,
                categoria    TEXT,
                fuente_tipo  TEXT
            )
        """)

        # Posiciones
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS positions (
                id                    {pk},
                crypto                TEXT,
                status                TEXT,
                entry_price           REAL,
                entry_time            TEXT,
                entry_timestamp       BIGINT,
                exit_price            REAL,
                exit_time             TEXT,
                exit_timestamp        BIGINT,
                result_pct            REAL,
                result_usd            REAL,
                timeframe_focus       TEXT,
                entry_rsi_15m         REAL,
                entry_rsi_1h          REAL,
                entry_rsi_1d          REAL,
                entry_macd_1h         REAL,
                entry_adx_1h          REAL,
                entry_trend_1d        TEXT,
                entry_atr_1h          REAL,
                exit_rsi_15m          REAL,
                exit_rsi_1h           REAL,
                exit_adx_1h           REAL,
                claude_recommendation TEXT,
                claude_reasoning      TEXT,
                notes                 TEXT
            )
        """)

        # Lecciones
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS lessons (
                id              {pk},
                position_id     INTEGER,
                crypto          TEXT,
                datetime        TEXT,
                timeframe_focus TEXT,
                situation       TEXT,
                news_context    TEXT,
                action_taken    TEXT,
                result          TEXT,
                result_pct      REAL,
                dominant_factor TEXT,
                lesson_text     TEXT
            )
        """)

        # Análisis Claude
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS claude_analysis (
                id                {pk},
                datetime          TEXT,
                timestamp         BIGINT,
                crypto            TEXT,
                timeframe_focus   TEXT,
                technical_summary TEXT,
                news_summary      TEXT,
                recommendation    TEXT,
                confidence        TEXT,
                reasoning         TEXT,
                price_at_analysis REAL,
                was_correct       INTEGER
            )
        """)

        conn.commit()
        conn.close()
        print("✅ Base de datos inicializada correctamente")

    except Exception as e:
        raise DatabaseError(
            "Error al crear las tablas",
            context={"error": str(e)}
        )


# ============================================================
# FUNCIONES DE CONSULTA
# ============================================================

def get_last_timestamp(crypto: str, timeframe: str) -> int:
    """Retorna el último timestamp guardado. Retorna 0 si no hay datos."""
    ph = _placeholder()
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        table  = f"candles_{crypto.lower()}_{timeframe}"
        cursor.execute(f"SELECT MAX(timestamp) FROM {table}")
        result = cursor.fetchone()
        conn.close()
        if USE_POSTGRES:
            val = result['max'] if result else None
        else:
            val = result[0] if result else None
        return val if val else 0
    except Exception as e:
        raise TableNotFoundError(
            "Tabla no encontrada — ejecuta create_tables() primero",
            context={"crypto": crypto, "timeframe": timeframe, "error": str(e)}
        )


def get_candles(crypto: str, timeframe: str, limit: int = 100) -> list:
    """Retorna las últimas N velas de una crypto y timeframe."""
    ph = _placeholder()
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        table  = f"candles_{crypto.lower()}_{timeframe}"
        cursor.execute(f"""
            SELECT * FROM {table}
            ORDER BY timestamp DESC
            LIMIT {ph}
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise DatabaseError(
            "Error al obtener velas",
            context={"crypto": crypto, "timeframe": timeframe, "error": str(e)}
        )


def get_open_positions() -> list:
    """Retorna todas las posiciones abiertas."""
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM positions
            WHERE status = 'open'
            ORDER BY entry_timestamp ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise DatabaseError(
            "Error al obtener posiciones abiertas",
            context={"error": str(e)}
        )


def get_recent_lessons(limit: int = 20) -> list:
    """Retorna las últimas lecciones aprendidas."""
    ph = _placeholder()
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM lessons
            ORDER BY id DESC
            LIMIT {ph}
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise DatabaseError(
            "Error al obtener lecciones",
            context={"error": str(e)}
        )


def get_recent_news(crypto: str = None, limit: int = 10) -> list:
    """Retorna las noticias más recientes."""
    ph = _placeholder()
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        if crypto:
            cursor.execute(f"""
                SELECT * FROM news
                WHERE crypto = {ph} OR crypto = 'GENERAL'
                ORDER BY timestamp DESC
                LIMIT {ph}
            """, (crypto, limit))
        else:
            cursor.execute(f"""
                SELECT * FROM news
                ORDER BY timestamp DESC
                LIMIT {ph}
            """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise DatabaseError(
            "Error al obtener noticias",
            context={"error": str(e)}
        )


if __name__ == "__main__":
    create_tables()

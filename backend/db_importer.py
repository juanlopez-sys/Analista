# ============================================================
# db_importer.py — Importa datos desde SQLite local a Supabase
# Lee el .db subido, compara timestamps y solo inserta nuevos
# ============================================================

import sqlite3
import tempfile
import os
from pathlib import Path
from error_handler import setup_logger
from database import get_connection, USE_POSTGRES

logger = setup_logger(__name__)


def get_candle_tables(sqlite_conn) -> list:
    """Retorna todas las tablas de velas del archivo SQLite subido."""
    cursor = sqlite_conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'candles_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def get_max_timestamp_supabase(table_name: str) -> int:
    """
    Retorna el timestamp máximo que ya existe en Supabase para esa tabla.
    Si la tabla no existe o está vacía, retorna 0.
    """
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX(timestamp) FROM {table_name}")
        result = cursor.fetchone()
        conn.close()
        if USE_POSTGRES:
            val = result['max'] if result else None
        else:
            val = result[0] if result else None
        return int(val) if val else 0
    except Exception:
        return 0  # Tabla no existe todavía — importar todo


def import_candle_table(sqlite_conn, table_name: str) -> dict:
    """
    Importa una tabla de velas desde SQLite a Supabase.
    Solo inserta filas con timestamp > max existente en Supabase.
    Retorna dict con estadísticas.
    """
    # 1. Obtener el último timestamp en Supabase
    max_ts = get_max_timestamp_supabase(table_name)

    # 2. Leer solo velas nuevas del SQLite
    sqlite_cursor = sqlite_conn.cursor()
    try:
        sqlite_cursor.execute(f"""
            SELECT timestamp, datetime, open, high, low, close, volume,
                   rsi, macd, macd_signal, macd_hist,
                   ema_20, ema_50, ema_200, sma_200,
                   bb_upper, bb_middle, bb_lower, bb_width,
                   adx, adx_pos, adx_neg,
                   stoch_rsi_k, stoch_rsi_d,
                   atr, obv, cci, williams_r, momentum, vwap
            FROM {table_name}
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        """, (max_ts,))
        rows = sqlite_cursor.fetchall()
    except Exception as e:
        logger.warning(f"Error leyendo {table_name} del SQLite: {e}")
        return {"table": table_name, "nuevas": 0, "error": str(e)}

    if not rows:
        return {"table": table_name, "nuevas": 0, "error": None}

    # 3. Insertar en Supabase
    ph   = "%s" if USE_POSTGRES else "?"
    cols = """(timestamp, datetime, open, high, low, close, volume,
               rsi, macd, macd_signal, macd_hist,
               ema_20, ema_50, ema_200, sma_200,
               bb_upper, bb_middle, bb_lower, bb_width,
               adx, adx_pos, adx_neg,
               stoch_rsi_k, stoch_rsi_d,
               atr, obv, cci, williams_r, momentum, vwap)"""

    placeholders = "(" + ",".join([ph] * 30) + ")"

    if USE_POSTGRES:
        insert_sql = f"""
            INSERT INTO {table_name} {cols}
            VALUES {placeholders}
            ON CONFLICT (timestamp) DO NOTHING
        """
    else:
        insert_sql = f"""
            INSERT OR IGNORE INTO {table_name} {cols}
            VALUES {placeholders}
        """

    try:
        conn   = get_connection()
        cursor = conn.cursor()

        # Crear tabla si no existe en Supabase
        _ensure_table_exists(cursor, table_name)

        nuevas = 0
        for row in rows:
            try:
                # Convertir sqlite3.Row a tupla
                vals = tuple(row)
                cursor.execute(insert_sql, vals)
                if cursor.rowcount > 0:
                    nuevas += 1
            except Exception as e:
                logger.warning(f"Error insertando vela en {table_name}: {e}")
                continue

        conn.commit()
        conn.close()
        return {"table": table_name, "nuevas": nuevas, "error": None}

    except Exception as e:
        logger.error(f"Error importando {table_name}: {e}")
        return {"table": table_name, "nuevas": 0, "error": str(e)}


def _ensure_table_exists(cursor, table_name: str):
    """Crea la tabla de velas si no existe en Supabase."""
    pk = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    try:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id          {pk},
                timestamp   BIGINT UNIQUE,
                datetime    TEXT,
                open        REAL, high  REAL, low   REAL,
                close       REAL, volume REAL,
                rsi         REAL, macd  REAL, macd_signal REAL, macd_hist REAL,
                ema_20      REAL, ema_50 REAL, ema_200 REAL, sma_200 REAL,
                bb_upper    REAL, bb_middle REAL, bb_lower REAL, bb_width REAL,
                adx         REAL, adx_pos REAL, adx_neg REAL,
                stoch_rsi_k REAL, stoch_rsi_d REAL,
                atr         REAL, obv REAL, cci REAL,
                williams_r  REAL, momentum REAL, vwap REAL
            )
        """)
    except Exception:
        pass  # Ya existe


def import_sqlite_db(db_path: str, only_tables: list = None) -> dict:
    """
    Función principal — importa todas las tablas de velas del .db a Supabase.
    
    Args:
        db_path: Ruta al archivo .db subido
        only_tables: Lista de tablas específicas a importar (None = todas)
    
    Returns:
        Dict con resumen de la importación
    """
    try:
        sqlite_conn = sqlite3.connect(db_path)
        sqlite_conn.row_factory = sqlite3.Row
    except Exception as e:
        raise Exception(f"No se pudo abrir el archivo .db: {e}")

    # Obtener tablas de velas
    all_tables  = get_candle_tables(sqlite_conn)
    tables      = only_tables if only_tables else all_tables

    logger.info(f"Importando {len(tables)} tablas desde {db_path}")

    total_nuevas  = 0
    total_tablas  = 0
    errores       = []
    detalle       = []

    for table in tables:
        result = import_candle_table(sqlite_conn, table)
        detalle.append(result)
        if result["error"]:
            errores.append(f"{result['table']}: {result['error']}")
        else:
            total_nuevas += result["nuevas"]
            if result["nuevas"] > 0:
                total_tablas += 1
                logger.info(f"  ✅ {table}: {result['nuevas']} velas nuevas")

    sqlite_conn.close()

    return {
        "ok":           True,
        "total_nuevas": total_nuevas,
        "tablas_con_datos_nuevos": total_tablas,
        "total_tablas_procesadas": len(tables),
        "errores":      errores,
        "detalle":      [d for d in detalle if d["nuevas"] > 0]
    }

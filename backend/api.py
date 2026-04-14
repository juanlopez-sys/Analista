# ============================================================
# api.py — Servidor FastAPI
# Producción: solo API (frontend en Static Site separado)
# Local: también sirve el frontend desde /static
# ============================================================

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import sys
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

try:
    from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("\n❌ Faltan dependencias. Instala con:")
    print("   pip install -r requirements.txt\n")
    sys.exit(1)

from pydantic import BaseModel, Field
from error_handler import setup_logger, TradingSystemError
from auth_middleware import security, get_current_user
from fastapi import Depends

logger = setup_logger(__name__)

# ============================================================
# ORÍGENES PERMITIDOS (CORS)
# ============================================================

_frontend_url  = os.getenv("FRONTEND_URL", "")
_is_production = bool(os.getenv("RENDER"))

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
if _frontend_url:
    ALLOWED_ORIGINS.append(_frontend_url)

# ============================================================
# CONSTANTES DE SEGURIDAD
# ============================================================

# Tamaño máximo de archivo para import-db (50 MB)
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024

# Rate limiting simple en memoria: ventana de 60 s
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_REQUESTS = 60   # máx. requests por ventana
RATE_LIMIT_WINDOW   = 60   # segundos

def _get_client_ip(request: Request) -> str:
    """Devuelve la IP real del cliente (considera proxies)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _check_rate_limit(key: str, limit: int = RATE_LIMIT_REQUESTS,
                      window: int = RATE_LIMIT_WINDOW) -> None:
    """Lanza 429 si el key superó el límite de requests en la ventana."""
    now = time.time()
    timestamps = _rate_limit_store[key]
    # Limpiar timestamps fuera de la ventana
    _rate_limit_store[key] = [t for t in timestamps if now - t < window]
    if len(_rate_limit_store[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes. Espera un momento e intenta de nuevo."
        )
    _rate_limit_store[key].append(now)

# ============================================================
# MODELOS DE REQUEST
# ============================================================

class AnalyzeOneRequest(BaseModel):
    crypto: str = Field(..., min_length=3, max_length=20)
    style:  str = Field("5", pattern=r'^[1-5]$')

class AnalyzeAllRequest(BaseModel):
    style: str = Field("5", pattern=r'^[1-5]$')

class ChatRequest(BaseModel):
    message: str          = Field(..., min_length=1, max_length=2000)
    crypto:  Optional[str] = Field(None, max_length=20)
    history: Optional[List[dict]] = []

class OpenPositionRequest(BaseModel):
    crypto:    str   = Field(..., min_length=3, max_length=20)
    price:     float = Field(..., gt=0, lt=10_000_000)
    date:      str   = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    time:      str   = Field(..., pattern=r'^([01]?\d|2[0-3]):[0-5]\d$')
    timeframe: Optional[str] = None
    notes:     Optional[str] = Field(None, max_length=500)

class ClosePositionRequest(BaseModel):
    position_id: int   = Field(..., gt=0)
    price:       float = Field(..., gt=0, lt=10_000_000)
    date:        str   = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    time:        str   = Field(..., pattern=r'^([01]?\d|2[0-3]):[0-5]\d$')
    notes:       Optional[str] = Field(None, max_length=500)

class SaveCryptosRequest(BaseModel):
    cryptos: List[str] = Field(..., min_items=1, max_items=50)

class SaveConfigRequest(BaseModel):
    news_mode: str = Field(..., pattern=r'^(crypto|macro|ambas)$')

# ============================================================
# APLICACIÓN
# ============================================================

app = FastAPI(title="Sistema Analista Crypto", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Middleware: headers de seguridad en todas las respuestas ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"]            = "no-store"
    if _is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ── Middleware: rate limiting global por IP ───────────────────
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = _get_client_ip(request)
    try:
        _check_rate_limit(f"ip:{ip}")
    except HTTPException as e:
        return JSONResponse(status_code=429, content={"detail": e.detail})
    return await call_next(request)

# ── En local, servir el frontend directamente ─────────────
if not _is_production:
    _frontend_dir = Path(__file__).parent.parent / "frontend"
    if _frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
        logger.info(f"Frontend servido desde {_frontend_dir}")

# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():
    return {"message": "API funcionando correctamente"}


@app.get("/api/init-db")
async def init_db(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Crea todas las tablas. Ejecutar una sola vez tras el primer deploy.
    SEGURIDAD: requiere autenticación válida.
    """
    get_current_user(credentials)
    try:
        import psycopg2
        db_url  = os.getenv("DATABASE_URL", "")
        if not db_url:
            raise HTTPException(status_code=500, detail="DATABASE_URL no configurada")

        try:
            conn = psycopg2.connect(db_url)
            conn.close()
        except Exception:
            raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

        from database import create_tables
        create_tables()
        logger.info("Base de datos inicializada por usuario autenticado")
        return {"ok": True, "message": "Base de datos inicializada correctamente"}

    except HTTPException:
        raise
    except Exception:
        logger.error("Error al inicializar la base de datos", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al inicializar la base de datos")


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ============================================================
# SISTEMA
# ============================================================

@app.get("/api/system-info")
async def system_info(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from database import get_connection
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'")
        row      = cursor.fetchone()
        open_pos = list(dict(row).values())[0] if row else 0
        cursor.execute("SELECT COUNT(*) FROM news")
        row        = cursor.fetchone()
        news_count = list(dict(row).values())[0] if row else 0
        conn.close()
        return {
            "active_cryptos": len(_config.ACTIVE_CRYPTOS),
            "open_positions": open_pos,
            "news_count":     news_count,
            "news_mode":      _config.NEWS_MODE,
            "claude_ok":      bool(_config.CLAUDE_API_KEY),
            "test_mode":      _config.TEST_MODE,
        }
    except Exception:
        logger.error("Error en system-info", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# DATOS
# ============================================================

@app.post("/api/update-candles")
async def update_candles(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    return {"ok": False, "message": "Descarga desde Binance desactivada. Usá /api/import-db."}


@app.post("/api/update-news")
async def update_news(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from news_collector import collect_news
        total = collect_news(verbose=False, mode=_config.NEWS_MODE)
        return {"ok": True, "total_new": total}
    except Exception:
        logger.error("Error actualizando noticias", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/update-data")
async def update_data(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from news_collector import collect_news
        total_news = collect_news(verbose=False, mode=_config.NEWS_MODE)
        return {"ok": True, "total_candles": 0, "total_news": total_news}
    except Exception:
        logger.error("Error en update-data", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ============================================================
# IMPORTAR BASE DE DATOS LOCAL (.db)
# ============================================================

def _validate_upload(file: UploadFile, content: bytes) -> None:
    """
    Valida el archivo subido:
    - Extensión permitida (.db)
    - Tamaño máximo (MAX_UPLOAD_SIZE_BYTES)
    - Magic bytes de SQLite3 (\\x53\\x51\\x4c\\x69\\x74\\x65)
    - Nombre de archivo seguro (sin path traversal)
    """
    # Nombre seguro — solo caracteres alfanuméricos, guiones y puntos
    import re
    safe_name = Path(file.filename).name
    if not re.match(r'^[\w\-. ]+$', safe_name):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")

    if not safe_name.endswith(".db"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .db de SQLite")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {MAX_UPLOAD_SIZE_BYTES // 1024 // 1024} MB"
        )

    # Verificar magic bytes de SQLite3: "SQLite format 3\000"
    if not content.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="El archivo no es una base de datos SQLite válida")


@app.post("/api/import-db")
async def import_db(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Recibe un archivo .db de SQLite y lo importa a Supabase.
    Solo inserta velas con timestamp mayor al máximo existente (sin duplicados).
    """
    get_current_user(credentials)

    tmp_path = None
    try:
        content = await file.read()
        _validate_upload(file, content)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(f"Archivo recibido: {Path(file.filename).name} ({len(content)/1024/1024:.1f} MB)")

        from db_importer import import_sqlite_db
        resultado = import_sqlite_db(tmp_path)
        return resultado

    except HTTPException:
        raise
    except Exception:
        logger.error("Error importando .db", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al importar la base de datos")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/api/import-db-progress")
async def import_db_progress(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Igual que import-db pero responde con Server-Sent Events (SSE)
    para mostrar progreso tabla por tabla en el frontend.
    """
    from fastapi.responses import StreamingResponse
    import json as _json

    get_current_user(credentials)

    content  = await file.read()
    _validate_upload(file, content)

    tmp_path = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    logger.info(f"SSE import: {Path(file.filename).name} ({len(content)/1024/1024:.1f} MB)")

    def event_stream():
        import sqlite3 as _sqlite3
        from db_importer import get_candle_tables, import_candle_table

        def send(data: dict) -> str:
            return f"data: {_json.dumps(data)}\n\n"

        try:
            sqlite_conn = _sqlite3.connect(tmp_path)
            sqlite_conn.row_factory = _sqlite3.Row
            tables = get_candle_tables(sqlite_conn)
            total  = len(tables)

            if total == 0:
                yield send({"type": "error", "msg": "No se encontraron tablas de velas en el archivo."})
                return

            yield send({"type": "start", "total": total, "msg": f"Encontradas {total} tablas"})

            total_nuevas = 0
            tablas_ok    = 0
            errores      = []

            for i, table in enumerate(tables, 1):
                yield send({
                    "type":    "progress",
                    "current": i,
                    "total":   total,
                    "table":   table,
                    "pct":     round((i - 1) / total * 100),
                })

                result = import_candle_table(sqlite_conn, table)

                if result["error"]:
                    errores.append(f"{table}: error al importar")
                else:
                    total_nuevas += result["nuevas"]
                    if result["nuevas"] > 0:
                        tablas_ok += 1

                yield send({
                    "type":   "table_done",
                    "table":  table,
                    "nuevas": result["nuevas"],
                    "pct":    round(i / total * 100),
                    "error":  bool(result["error"]),
                })

            sqlite_conn.close()

            yield send({
                "type":         "done",
                "total_nuevas": total_nuevas,
                "tablas_ok":    tablas_ok,
                "total_tablas": total,
                "errores":      errores,
                "pct":          100,
            })

        except Exception:
            logger.error("Error en SSE import", exc_info=True)
            yield send({"type": "error", "msg": "Error interno al procesar el archivo"})
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ============================================================
# PRECIOS
# ============================================================

@app.get("/api/get-prices")
async def get_prices(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from data_collector import get_current_price
        from config import ACTIVE_CRYPTOS
        precios = {}
        for crypto in ACTIVE_CRYPTOS:
            precio = get_current_price(crypto)
            if precio > 0:
                precios[crypto] = precio
        return {"ok": True, "prices": precios}
    except Exception:
        logger.error("Error obteniendo precios", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# NOTICIAS
# ============================================================

@app.get("/api/get-news")
async def get_news(limit: int = 30, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        limit = max(1, min(limit, 100))
        from database import get_connection
        conn   = get_connection()
        cursor = conn.cursor()
        ph     = "%s" if bool(os.getenv("DATABASE_URL")) else "?"
        cursor.execute(f"""
            SELECT datetime, title, source, sentiment, impact,
                   crypto, resumen, razon_impacto, categoria, fuente_tipo, url
            FROM news
            ORDER BY timestamp DESC
            LIMIT {ph}
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        news = [dict(row) for row in rows]
        return {"ok": True, "news": news}
    except Exception:
        logger.error("Error obteniendo noticias", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# ANÁLISIS
# ============================================================

@app.post("/api/analyze-one")
async def analyze_one(req: AnalyzeOneRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from claude_analyst import analyze
        response = analyze(req.crypto, trading_style=req.style, verbose=False)
        return {"ok": True, "response": response or "Sin respuesta de Claude"}
    except TradingSystemError as e:
        e.log(logger)
        raise HTTPException(status_code=500, detail=e.message)
    except Exception:
        logger.error("Error en analyze-one", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/analyze-all")
async def analyze_all(req: AnalyzeAllRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from claude_analyst import analyze_all as _analyze_all
        results = _analyze_all(trading_style=req.style, verbose=False)
        if isinstance(results, list):
            lines = []
            for r in results:
                if isinstance(r, dict):
                    lines.append(
                        f"{'='*40}\n{r.get('crypto','—')}\n"
                        f"Recomendación: {r.get('recommendation','—')} | "
                        f"Confianza: {r.get('confidence','—')}\n{r.get('reasoning','')}"
                    )
            response = "\n".join(lines) if lines else str(results)
        else:
            response = str(results)
        return {"ok": True, "response": response}
    except Exception:
        logger.error("Error en analyze-all", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/analyze-best")
async def analyze_best(req: AnalyzeAllRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from claude_analyst import analyze_best as _analyze_best
        result   = _analyze_best(trading_style=req.style, verbose=False)
        response = result.get("response", "Sin respuesta") if isinstance(result, dict) else str(result)
        return {"ok": True, "response": response}
    except Exception:
        logger.error("Error en analyze-best", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# CHAT
# ============================================================

@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request,
               credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    # Rate limit más estricto en chat (10 req/min por IP)
    _check_rate_limit(f"chat:{_get_client_ip(request)}", limit=10, window=60)
    try:
        from claude_analyst import build_analysis_prompt, call_claude
        from news_collector import get_news_summary

        hist_text = ""
        if req.history:
            for msg in req.history[-6:]:
                role     = "Usuario" if msg.get("role") == "user" else "Claude"
                content  = str(msg.get("content", ""))[:300]
                hist_text += f"{role}: {content}\n"

        if req.crypto:
            base_prompt = build_analysis_prompt(req.crypto, user_question=req.message, trading_style="5")
        else:
            base_prompt = f"""Eres un analista experto en trading de criptomonedas.

NOTICIAS RECIENTES:
{get_news_summary(limit=5)}

{f"HISTORIAL:{chr(10)}{hist_text}" if hist_text else ""}

PREGUNTA: {req.message}
"""
        response = call_claude(base_prompt)
        return {"ok": True, "response": response or "Sin respuesta de Claude"}
    except Exception:
        logger.error("Error en chat", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# POSICIONES
# ============================================================

@app.get("/api/get-positions")
async def get_positions(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from database import get_open_positions
        from data_collector import get_current_price
        posiciones = get_open_positions()
        result     = []
        for pos in posiciones:
            precio_actual = get_current_price(pos["crypto"])
            pnl_pct = 0.0
            if pos["entry_price"] and precio_actual > 0:
                pnl_pct = ((precio_actual - pos["entry_price"]) / pos["entry_price"]) * 100
            result.append({
                "id":              pos["id"],
                "crypto":          pos["crypto"],
                "status":          pos["status"],
                "entry_price":     pos["entry_price"],
                "entry_time":      pos["entry_time"],
                "timeframe_focus": pos.get("timeframe_focus"),
                "current_price":   precio_actual,
                "pnl_pct":         round(pnl_pct, 2),
                "notes":           pos.get("notes"),
            })
        return {"ok": True, "positions": result}
    except Exception:
        logger.error("Error obteniendo posiciones", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/open-position")
async def open_position(req: OpenPositionRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from positions import open_position as _open_position
        pos_id = _open_position(
            crypto=req.crypto, entry_price=req.price,
            entry_time=req.time, timeframe_focus=req.timeframe or None,
            notes=req.notes or None,
        )
        return {"ok": True, "position_id": pos_id}
    except TradingSystemError as e:
        e.log(logger)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception:
        logger.error("Error abriendo posición", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/close-position")
async def close_position(req: ClosePositionRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from positions import close_position as _close_position
        result = _close_position(
            position_id=req.position_id, exit_price=req.price,
            exit_time=req.time, notes=req.notes or None,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Posición no encontrada o ya cerrada")
        return {"ok": True, **result}
    except HTTPException:
        raise
    except TradingSystemError as e:
        e.log(logger)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception:
        logger.error("Error cerrando posición", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# HISTORIAL Y LECCIONES
# ============================================================

@app.get("/api/get-history")
async def get_history(crypto: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from database import get_connection
        from config import CRYPTOS
        # Validar crypto contra lista blanca si se proporciona
        if crypto and crypto not in CRYPTOS:
            raise HTTPException(status_code=400, detail="Crypto no válida")
        ph   = "%s" if bool(os.getenv("DATABASE_URL")) else "?"
        conn = get_connection()
        cursor = conn.cursor()
        if crypto:
            cursor.execute(f"""
                SELECT id, crypto, entry_price, exit_price, result_pct, entry_time, exit_time, notes
                FROM positions WHERE status = 'closed' AND crypto = {ph}
                ORDER BY exit_timestamp DESC LIMIT 50
            """, (crypto,))
        else:
            cursor.execute("""
                SELECT id, crypto, entry_price, exit_price, result_pct, entry_time, exit_time, notes
                FROM positions WHERE status = 'closed'
                ORDER BY exit_timestamp DESC LIMIT 50
            """)
        rows = cursor.fetchall()
        conn.close()
        return {"ok": True, "positions": [dict(r) for r in rows]}
    except HTTPException:
        raise
    except Exception:
        logger.error("Error obteniendo historial", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.get("/api/get-lessons")
async def get_lessons(crypto: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from database import get_recent_lessons
        from config import CRYPTOS
        if crypto and crypto not in CRYPTOS:
            raise HTTPException(status_code=400, detail="Crypto no válida")
        lecciones = get_recent_lessons(limit=30)
        if crypto:
            lecciones = [l for l in lecciones if l.get("crypto") == crypto]
        return {"ok": True, "lessons": lecciones}
    except HTTPException:
        raise
    except Exception:
        logger.error("Error obteniendo lecciones", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# CONFIGURACIÓN
# ============================================================

@app.post("/api/save-cryptos")
async def save_cryptos(req: SaveCryptosRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from config import CRYPTOS
        invalid = [c for c in req.cryptos if c not in CRYPTOS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Cryptos no válidas: {', '.join(invalid)}")
        _config.ACTIVE_CRYPTOS = list(req.cryptos)
        return {"ok": True, "active_cryptos": len(req.cryptos)}
    except HTTPException:
        raise
    except Exception:
        logger.error("Error guardando cryptos", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/save-config")
async def save_config(req: SaveConfigRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        _config.NEWS_MODE = req.news_mode
        return {"ok": True, "news_mode": req.news_mode}
    except Exception:
        logger.error("Error guardando config", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# ERRORES
# ============================================================

@app.get("/api/get-errors")
async def get_errors(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        log_path = Path("trading_errors.log")
        if not log_path.exists():
            return {"ok": True, "errors": []}
        lines  = log_path.read_text(encoding="utf-8").splitlines()
        errors = [l for l in lines if "ERROR" in l or "CRITICAL" in l]
        return {"ok": True, "errors": errors[-50:]}
    except Exception:
        logger.error("Error leyendo log de errores", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/clear-errors")
async def clear_errors(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        log_path = Path("trading_errors.log")
        if log_path.exists():
            log_path.write_text("", encoding="utf-8")
        return {"ok": True}
    except Exception:
        logger.error("Error limpiando log", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ============================================================
# ARRANQUE
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando en http://localhost:{port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=not _is_production, log_level="warning")

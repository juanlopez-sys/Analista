# ============================================================
# api.py — Servidor FastAPI
# Producción: solo API (frontend en Static Site separado)
# Local: también sirve el frontend desde /static
# ============================================================

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
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

# En producción, FRONTEND_URL viene de la variable de entorno
# configurada en Render (ej: https://crypto-app.onrender.com)
_frontend_url  = os.getenv("FRONTEND_URL", "")
_is_production = bool(os.getenv("RENDER"))   # Render setea esta var automáticamente

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
    allow_headers=["Content-Type"],
)

# ── En local, servir el frontend directamente ─────────────
# En Render esto no se usa (frontend es un Static Site separado)
if not _is_production:
    _frontend_dir = Path(__file__).parent.parent / "frontend"
    if _frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
        logger.info(f"Frontend servido desde {_frontend_dir}")

# ============================================================
# HEALTH
# ============================================================

@app.get("/api/init-db")
async def init_db():
    """Crea todas las tablas. Ejecutar una sola vez tras el primer deploy."""
    try:
        from database import create_tables
        create_tables()
        return {"ok": True, "message": "Base de datos inicializada correctamente"}
    except Exception as e:
        logger.error(f"Error inicializando BD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        row = cursor.fetchone()
        open_pos = list(dict(row).values())[0] if row else 0
        cursor.execute("SELECT COUNT(*) FROM news")
        row = cursor.fetchone()
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
    except Exception as e:
        logger.error(f"Error en system-info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# DATOS
# ============================================================

@app.post("/api/update-candles")
async def update_candles(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from data_collector import collect_all
        resumen      = collect_all(verbose=False)
        total_nuevas = sum(v for tf in resumen.values() for v in tf.values())
        lines        = []
        for crypto, tfs in resumen.items():
            total = sum(tfs.values())
            if total > 0:
                lines.append(f"✓ {crypto}: {total} velas nuevas")
        return {"ok": True, "total_new": total_nuevas, "summary": "\n".join(lines) or "Sin velas nuevas"}
    except TradingSystemError as e:
        e.log(logger); raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"Error actualizando velas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-news")
async def update_news(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from news_collector import collect_news
        total = collect_news(verbose=False, mode=_config.NEWS_MODE)
        return {"ok": True, "total_new": total}
    except Exception as e:
        logger.error(f"Error actualizando noticias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-data")
async def update_data(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        from data_collector import collect_all
        from news_collector import collect_news
        resumen     = collect_all(verbose=False)
        total_velas = sum(v for tf in resumen.values() for v in tf.values())
        total_news  = collect_news(verbose=False, mode=_config.NEWS_MODE)
        return {"ok": True, "total_candles": total_velas, "total_news": total_news}
    except Exception as e:
        logger.error(f"Error en update-data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"Error obteniendo precios: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        cursor.execute(f"""
            SELECT datetime, title, source, sentiment, impact,
                   crypto, resumen, razon_impacto, categoria, fuente_tipo, url
            FROM news
            ORDER BY timestamp DESC
            LIMIT {('%s' if bool(os.getenv('DATABASE_URL')) else '?')}
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        news = [dict(row) for row in rows]
        return {"ok": True, "news": news}
    except Exception as e:
        logger.error(f"Error obteniendo noticias: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        e.log(logger); raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"Error en analyze-one: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                    lines.append(f"{'='*40}\n{r.get('crypto','—')}\nRecomendación: {r.get('recommendation','—')} | Confianza: {r.get('confidence','—')}\n{r.get('reasoning','')}")
            response = "\n".join(lines) if lines else str(results)
        else:
            response = str(results)
        return {"ok": True, "response": response}
    except Exception as e:
        logger.error(f"Error en analyze-all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-best")
async def analyze_best(req: AnalyzeAllRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from claude_analyst import analyze_best as _analyze_best
        result   = _analyze_best(trading_style=req.style, verbose=False)
        response = result.get("response", "Sin respuesta") if isinstance(result, dict) else str(result)
        return {"ok": True, "response": response}
    except Exception as e:
        logger.error(f"Error en analyze-best: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# CHAT
# ============================================================

@app.post("/api/chat")
async def chat(req: ChatRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
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
    except Exception as e:
        logger.error(f"Error en chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"Error obteniendo posiciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        e.log(logger); raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"Error abriendo posición: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        e.log(logger); raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"Error cerrando posición: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# HISTORIAL Y LECCIONES
# ============================================================

@app.get("/api/get-history")
async def get_history(crypto: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from database import get_connection
        ph   = "%s" if bool(os.getenv('DATABASE_URL')) else "?"
        conn = get_connection(); cursor = conn.cursor()
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
        rows = cursor.fetchall(); conn.close()
        return {"ok": True, "positions": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/get-lessons")
async def get_lessons(crypto: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        from database import get_recent_lessons
        lecciones = get_recent_lessons(limit=30)
        if crypto:
            lecciones = [l for l in lecciones if l.get("crypto") == crypto]
        return {"ok": True, "lessons": lecciones}
    except Exception as e:
        logger.error(f"Error obteniendo lecciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"Error guardando cryptos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/save-config")
async def save_config(req: SaveConfigRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        import config as _config
        _config.NEWS_MODE = req.news_mode
        return {"ok": True, "news_mode": req.news_mode}
    except Exception as e:
        logger.error(f"Error guardando config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear-errors")
async def clear_errors(credentials: HTTPAuthorizationCredentials = Depends(security)):
    get_current_user(credentials)
    try:
        log_path = Path("trading_errors.log")
        if log_path.exists():
            log_path.write_text("", encoding="utf-8")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# ARRANQUE
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando en http://localhost:{port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=not _is_production, log_level="warning")

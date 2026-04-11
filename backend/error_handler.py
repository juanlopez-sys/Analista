# ============================================================
# error_handler.py — Manejo centralizado de errores
# Logger + Excepciones personalizadas por módulo
# ============================================================

import logging
import traceback
import functools
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURACIÓN DEL LOGGER
# ============================================================

LOG_FILE = "trading_errors.log"

# Formato detallado para el archivo .log
LOG_FORMAT_FILE = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
)

# Formato simple para la consola
LOG_FORMAT_CONSOLE = "%(levelname)-8s | %(message)s"

def setup_logger(name: str) -> logging.Logger:
    """
    Crea y configura un logger para un módulo específico.
    Uso: logger = setup_logger(__name__)
    """
    logger = logging.getLogger(name)

    # Evitar duplicar handlers si ya fue configurado
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Handler archivo — guarda TODO (DEBUG en adelante) ──
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT_FILE))

    # ── Handler consola — muestra solo WARNING en adelante ──
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Logger principal del sistema
logger = setup_logger("trading_system")

# ============================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================

class TradingSystemError(Exception):
    """Base de todos los errores del sistema."""
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.message   = message
        self.context   = context or {}
        self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def log(self, logger: logging.Logger = None):
        """Registra el error en el log con contexto completo."""
        _logger = logger or globals()['logger']
        ctx = " | ".join([f"{k}: {v}" for k, v in self.context.items()])
        _logger.error(f"{self.__class__.__name__}: {self.message} | {ctx}")
        _logger.debug(traceback.format_exc())

    def show(self):
        """Muestra el error al usuario de forma amigable."""
        print(f"\n  ❌ {self.message}")
        if self.context:
            for k, v in self.context.items():
                print(f"     {k}: {v}")


# ── Errores de Base de Datos ─────────────────────────────────
class DatabaseError(TradingSystemError):
    """Error al conectar o consultar la base de datos."""
    pass

class TableNotFoundError(DatabaseError):
    """Tabla no encontrada en la base de datos."""
    pass

class InsertError(DatabaseError):
    """Error al insertar datos en la base de datos."""
    pass


# ── Errores de Binance / Datos de Mercado ────────────────────
class BinanceError(TradingSystemError):
    """Error al conectar o consultar Binance."""
    pass

class BinanceTimeoutError(BinanceError):
    """Timeout al conectar con Binance."""
    pass

class BinanceRateLimitError(BinanceError):
    """Se superó el rate limit de Binance."""
    pass

class CryptoNotFoundError(BinanceError):
    """La crypto no existe en Binance."""
    pass


# ── Errores de Claude API ────────────────────────────────────
class ClaudeError(TradingSystemError):
    """Error al llamar a la API de Claude."""
    pass

class ClaudeAPIKeyError(ClaudeError):
    """API Key de Claude inválida o faltante."""
    pass

class ClaudeRateLimitError(ClaudeError):
    """Se superó el rate limit de Claude."""
    pass

class ClaudeTimeoutError(ClaudeError):
    """Timeout al llamar a Claude."""
    pass


# ── Errores de Noticias ──────────────────────────────────────
class NewsError(TradingSystemError):
    """Error al recolectar noticias."""
    pass


# ── Errores de Posiciones ────────────────────────────────────
class PositionError(TradingSystemError):
    """Error al gestionar posiciones."""
    pass

class PositionNotFoundError(PositionError):
    """Posición no encontrada."""
    pass

class PositionAlreadyClosedError(PositionError):
    """Intentando cerrar una posición ya cerrada."""
    pass


# ── Errores de Validación ────────────────────────────────────
class ValidationError(TradingSystemError):
    """Error de validación de input del usuario."""
    pass

class InvalidCryptoError(ValidationError):
    """Crypto no válida o no configurada."""
    pass

class InvalidPriceError(ValidationError):
    """Precio no válido."""
    pass


# ============================================================
# DECORADOR — captura errores automáticamente
# ============================================================

def handle_errors(error_class=TradingSystemError, default=None, reraise=False):
    """
    Decorador que captura errores en cualquier función,
    los registra en el log y muestra mensaje amigable.

    Uso:
        @handle_errors(error_class=BinanceError, default=[])
        def fetch_candles(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TradingSystemError as e:
                e.log()
                e.show()
                if reraise:
                    raise
                return default
            except Exception as e:
                # Error inesperado — capturar y loggear con traceback completo
                _logger = setup_logger(func.__module__)
                _logger.error(
                    f"Error inesperado en {func.__name__}(): {type(e).__name__}: {e}"
                )
                _logger.debug(traceback.format_exc())
                print(f"\n  ❌ Error inesperado en {func.__name__}(): {e}")
                print(f"     Ver {LOG_FILE} para más detalles")
                if reraise:
                    raise
                return default
        return wrapper
    return decorator


# ============================================================
# FUNCIÓN PARA ENVOLVER BLOQUES — sin decorador
# ============================================================

def safe_run(func, *args, error_class=TradingSystemError,
             default=None, context: dict = None, **kwargs):
    """
    Ejecuta una función con manejo de errores sin necesidad de decorador.

    Uso:
        result = safe_run(fetch_candles, "BTCUSDT", "1h",
                          error_class=BinanceError,
                          default=[],
                          context={"crypto": "BTCUSDT"})
    """
    try:
        return func(*args, **kwargs)
    except TradingSystemError as e:
        e.log()
        e.show()
        return default
    except Exception as e:
        _logger = setup_logger(func.__module__ if hasattr(func, '__module__') else __name__)
        ctx_str = ""
        if context:
            ctx_str = " | " + " | ".join([f"{k}: {v}" for k, v in context.items()])
        _logger.error(
            f"Error en {func.__name__}(){ctx_str}: {type(e).__name__}: {e}"
        )
        _logger.debug(traceback.format_exc())
        print(f"\n  ❌ Error en {func.__name__}(): {e}")
        print(f"     Ver {LOG_FILE} para más detalles")
        return default


# ============================================================
# FUNCIÓN PARA VER EL LOG
# ============================================================

def show_recent_errors(n: int = 20) -> None:
    """Muestra los últimos N errores del log."""
    log_path = Path(LOG_FILE)

    if not log_path.exists():
        print("✅ Sin errores registrados aún")
        return

    lines = log_path.read_text(encoding="utf-8").splitlines()
    errors = [l for l in lines if "ERROR" in l or "CRITICAL" in l]

    if not errors:
        print("✅ Sin errores registrados aún")
        return

    print(f"\n{'═'*60}")
    print(f"  🔴 ÚLTIMOS {min(n, len(errors))} ERRORES")
    print(f"{'═'*60}")
    for line in errors[-n:]:
        print(f"  {line}")

def show_full_log(n: int = 50) -> None:
    """Muestra las últimas N líneas del log completo."""
    log_path = Path(LOG_FILE)

    if not log_path.exists():
        print("✅ Log vacío — sin eventos registrados")
        return

    lines = log_path.read_text(encoding="utf-8").splitlines()

    print(f"\n{'═'*60}")
    print(f"  📋 LOG COMPLETO (últimas {min(n, len(lines))} líneas)")
    print(f"{'═'*60}")
    for line in lines[-n:]:
        print(f"  {line}")

def clear_log() -> None:
    """Limpia el archivo de log."""
    log_path = Path(LOG_FILE)
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")
        print("✅ Log limpiado")
    else:
        print("✅ No había log que limpiar")


# ============================================================
# MENÚ DIRECTO
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("  🔍 VISOR DE ERRORES — Sistema Analista Crypto")
    print("=" * 55)
    print("\n  1 → Ver últimos errores")
    print("  2 → Ver log completo")
    print("  3 → Limpiar log")

    opcion = input("\nOpción (1-3): ").strip()

    if opcion == "1":
        show_recent_errors(n=20)
    elif opcion == "2":
        show_full_log(n=50)
    elif opcion == "3":
        confirm = input("¿Seguro? (s/n): ").strip().lower()
        if confirm == "s":
            clear_log()
    else:
        print("❌ Opción no válida")


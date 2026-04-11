# ============================================================
# config.py — Configuración central del sistema de trading
# Las API keys se leen desde el archivo .env (nunca aquí)
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------
# API KEYS (desde .env)
# ------------------------------------------------------------
CLAUDE_API_KEY      = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL        = "claude-sonnet-4-20250514"
BINANCE_API_KEY     = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET  = os.getenv("BINANCE_API_SECRET")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")

# ------------------------------------------------------------
# VERIFICACIÓN DE KEYS
# ------------------------------------------------------------
def check_api_keys():
    missing = []
    if not CLAUDE_API_KEY:      missing.append("CLAUDE_API_KEY")
    if not BINANCE_API_KEY:     missing.append("BINANCE_API_KEY")
    if not BINANCE_API_SECRET:  missing.append("BINANCE_API_SECRET")
    if not CRYPTOPANIC_API_KEY: missing.append("CRYPTOPANIC_API_KEY")

    if missing:
        print("⚠️  Faltan las siguientes API keys en tu archivo .env:")
        for key in missing:
            print(f"   ❌ {key}")
        print("🔒 Modo de prueba activado\n")
        return False

    print("✅ Todas las API keys encontradas")
    return True

# ------------------------------------------------------------
# CRYPTOS A MONITOREAR
# Formato Binance: símbolo + USDT
# ⚠️  Algunas pueden no estar disponibles en Binance,
#     el sistema las omitirá automáticamente si fallan
# ------------------------------------------------------------
CRYPTOS = [
    # Principales
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "XLMUSDT",
    "ALGOUSDT",
    "VETUSDT",

    # DeFi y ecosistema
    "AAVEUSDT",
    "INJUSDT",
    "GRTUSDT",
    "SNXUSDT",
    "CAKEUSDT",
    "SANDUSDT",

    # Layer 1 / Layer 2
    "SUIUSDT",
    "HBARUSDT",
    "SEIUSDT",
    "CKBUSDT",

    # IA y datos
    "FETUSDT",
    "MASKUSDT",

    # Gaming / Metaverso
    "AXSUSDT",
    "SLPUSDT",
    "APEUSDT",
    "MBOXUSDT",

    # Otros altcoins
    "SHIBUSDT",
    "ZENUSDT",
    "LPTUSDT",
    "XVGUSDT",
    "XECUSDT",
    "TFUELUSDT",
    "POWRUSDT",
    "OGNUSDT",
    "C98USDT",
    "DUSKUSDT",
    "IOTAUSDT",
    "SAHARAUSDT",

    # ⚠️ Estos pueden no estar en Binance, verificar:
    # "ALLOUSDT",    # Posiblemente no disponible

]

# Nombres legibles
CRYPTO_NAMES = {
    "BTCUSDT":   "Bitcoin",
    "ETHUSDT":   "Ethereum",
    "SOLUSDT":   "Solana",
    "XRPUSDT":   "Ripple",
    "DOGEUSDT":  "Dogecoin",
    "ADAUSDT":   "Cardano",
    "AVAXUSDT":  "Avalanche",
    "DOTUSDT":   "Polkadot",
    "XLMUSDT":   "Stellar",
    "ALGOUSDT":  "Algorand",
    "VETUSDT":   "VeChain",
    "AAVEUSDT":  "Aave",
    "INJUSDT":   "Injective",
    "GRTUSDT":   "The Graph",
    "SNXUSDT":   "Synthetix",
    "CAKEUSDT":  "PancakeSwap",
    "SANDUSDT":  "The Sandbox",
    "SUIUSDT":   "Sui",
    "HBARUSDT":  "Hedera",
    "SEIUSDT":   "Sei",
    "CKBUSDT":   "Nervos CKB",
    "FETUSDT":   "Fetch.ai",
    "MASKUSDT":  "Mask Network",
    "AXSUSDT":   "Axie Infinity",
    "SLPUSDT":   "Smooth Love Potion",
    "APEUSDT":   "ApeCoin",
    "MBOXUSDT":  "Mobox",
    "SHIBUSDT":  "Shiba Inu",
    "ZENUSDT":   "Horizen",
    "LPTUSDT":   "Livepeer",
    "XVGUSDT":   "Verge",
    "XECUSDT":   "eCash",
    "TFUELUSDT": "Theta Fuel",
    "POWRUSDT":  "Power Ledger",
    "OGNUSDT":   "Origin Protocol",
    "C98USDT":   "Coin98",
    "DUSKUSDT":  "Dusk Network",
    "IOTAUSDT":    "IOTA",
    "SAHARAUSDT":  "Sahara AI",
}

# ------------------------------------------------------------
# CRYPTOS ACTIVAS
# ------------------------------------------------------------
ACTIVE_CRYPTOS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "SEIUSDT",
]

# ------------------------------------------------------------
# TIMEFRAMES POR ESTILO DE TRADING
# ------------------------------------------------------------
TRADING_STYLES = {
    "1": {"nombre": "Scalping",     "timeframes": ["5m", "15m"]},
    "2": {"nombre": "Day Trading",  "timeframes": ["30m", "1h"]},
    "3": {"nombre": "Swing",        "timeframes": ["4h", "8h"]},
    "4": {"nombre": "Posicional",   "timeframes": ["1d"]},
    "5": {"nombre": "Completo",     "timeframes": ["5m", "15m", "30m", "1h", "4h", "8h", "1d"]},
}

# ------------------------------------------------------------
# TIMEFRAMES
# ------------------------------------------------------------
TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "8h", "1d"]

CANDLES_LIMIT = {
    "5m":  1000,  # ~3 días
    "15m": 1000,  # ~10 días
    "30m": 1000,  # ~20 días
    "1h":  1000,  # ~41 días
    "4h":  1000,  # ~166 días
    "8h":  1000,  # ~333 días
    "1d":  365,   # 1 año
}

# ------------------------------------------------------------
# BASE DE DATOS
# ------------------------------------------------------------
DATABASE_PATH = "trading_system.db"

# ------------------------------------------------------------
# CONFIGURACIÓN DE ANÁLISIS
# ------------------------------------------------------------
ANALYSIS_INTERVAL_MINUTES = 15
CANDLES_TO_ANALYZE        = 50
NEWS_TO_ANALYZE           = 10
LESSONS_TO_INCLUDE        = 20

# ------------------------------------------------------------
# MODO DE RECOLECCIÓN DE NOTICIAS
# "crypto" → solo CryptoCompare (noticias crypto)
# "macro"  → solo Claude búsqueda macro
# "ambas"  → ambas fuentes (default recomendado)
# ------------------------------------------------------------
NEWS_MODE = "ambas"

# ------------------------------------------------------------
# INDICADORES TÉCNICOS
# ------------------------------------------------------------
RSI_PERIOD       = 14
EMA_FAST         = 20
EMA_SLOW         = 50
EMA_LONG         = 200
MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD    = 2

# ------------------------------------------------------------
# NIVELES RSI
# ------------------------------------------------------------
RSI_OVERSOLD           = 30
RSI_OVERBOUGHT         = 70
RSI_EXTREME_OVERSOLD   = 20
RSI_EXTREME_OVERBOUGHT = 80

# ------------------------------------------------------------
# MODO DE PRUEBA
# ------------------------------------------------------------
TEST_MODE = not all([CLAUDE_API_KEY, BINANCE_API_KEY, BINANCE_API_SECRET])

if __name__ == "__main__":
    check_api_keys()
    print(f"\n📊 Total cryptos configuradas: {len(CRYPTOS)}")
    for c in CRYPTOS:
        print(f"   • {CRYPTO_NAMES.get(c, c)}")
    print(f"\n⏱️  Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"🔧 Modo prueba: {'Activado' if TEST_MODE else 'Desactivado'}")
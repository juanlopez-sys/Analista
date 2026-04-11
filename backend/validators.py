# ============================================================
# validators.py — Validación de inputs del sistema
# Usado por main.py, positions.py y futuro frontend
# ============================================================

import re
from datetime import datetime
from config import CRYPTOS, CRYPTO_NAMES, TIMEFRAMES, TRADING_STYLES

# ============================================================
# VALIDACIÓN DE CRYPTO
# ============================================================

def validate_crypto(input_str: str) -> tuple[bool, str, str]:
    """
    Valida que la crypto exista en la lista configurada.
    Acepta: "BTC", "BTCUSDT", "bitcoin", "Bitcoin"
    Retorna: (válido, símbolo_normalizado, mensaje_error)
    """
    if not input_str or not input_str.strip():
        return False, "", "❌ No ingresaste ninguna crypto"

    entrada = input_str.strip().upper()

    # Agregar USDT si no tiene
    if not entrada.endswith("USDT"):
        entrada += "USDT"

    # Verificar si existe en la lista
    if entrada in CRYPTOS:
        nombre = CRYPTO_NAMES.get(entrada, entrada)
        return True, entrada, f"✅ {nombre} ({entrada})"

    # Buscar por nombre legible
    for simbolo, nombre in CRYPTO_NAMES.items():
        if nombre.upper() == input_str.strip().upper():
            return True, simbolo, f"✅ {nombre} ({simbolo})"

    # No encontrado
    disponibles = ", ".join([CRYPTO_NAMES.get(c, c) for c in CRYPTOS[:5]]) + "..."
    return False, "", f"❌ '{input_str}' no está en la lista. Ejemplos: {disponibles}"


def ask_crypto(mensaje: str = "¿Qué crypto?") -> str:
    """
    Pide una crypto al usuario con validación.
    Repite hasta recibir una válida.
    """
    while True:
        print(f"\n{mensaje} (ej: BTC, ETH, SOL)")
        print("  Opciones disponibles:", ", ".join(
            [CRYPTO_NAMES.get(c, c) for c in CRYPTOS[:10]]
        ) + "...")
        entrada = input("→ ").strip()

        valido, simbolo, mensaje_resp = validate_crypto(entrada)
        print(f"  {mensaje_resp}")

        if valido:
            return simbolo

# ============================================================
# VALIDACIÓN DE PRECIO
# ============================================================

def validate_price(input_str: str, allow_empty: bool = False,
                   default: float = None) -> tuple[bool, float, str]:
    """
    Valida que el precio sea un número positivo.
    Retorna: (válido, precio_float, mensaje_error)
    """
    if not input_str or not input_str.strip():
        if allow_empty and default is not None:
            return True, default, f"✅ Usando precio actual: ${default:,.4f}"
        return False, 0.0, "❌ El precio no puede estar vacío"

    # Limpiar: quitar $, comas, espacios
    limpio = input_str.strip().replace("$", "").replace(",", "").replace(" ", "")

    try:
        precio = float(limpio)
    except ValueError:
        return False, 0.0, f"❌ '{input_str}' no es un número válido. Ejemplo: 69500 o 69500.50"

    if precio <= 0:
        return False, 0.0, "❌ El precio debe ser mayor a 0"

    if precio > 10_000_000:
        return False, 0.0, f"❌ Precio demasiado alto: ${precio:,.2f} — ¿Es correcto?"

    return True, precio, f"✅ Precio: ${precio:,.4f}"


def ask_price(mensaje: str = "¿Precio?", default: float = None) -> float:
    """
    Pide un precio al usuario con validación.
    Si hay default (precio actual), Enter lo acepta.
    """
    while True:
        if default:
            print(f"\n{mensaje} (Enter = ${default:,.4f})")
        else:
            print(f"\n{mensaje} (ej: 69500 o 69500.50)")

        entrada = input("→ ").strip()

        valido, precio, mensaje_resp = validate_price(
            entrada, allow_empty=True, default=default
        )
        print(f"  {mensaje_resp}")

        if valido:
            return precio

# ============================================================
# VALIDACIÓN DE HORA
# ============================================================

def validate_time(input_str: str, allow_empty: bool = False) -> tuple[bool, str, str]:
    """
    Valida formato de hora HH:MM.
    Retorna: (válido, hora_str, mensaje_error)
    """
    if not input_str or not input_str.strip():
        if allow_empty:
            ahora = datetime.now().strftime('%H:%M')
            return True, ahora, f"✅ Usando hora actual: {ahora}"
        return False, "", "❌ La hora no puede estar vacía"

    entrada = input_str.strip()

    # Formato HH:MM
    patron = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
    if re.match(patron, entrada):
        # Normalizar a HH:MM con ceros
        partes = entrada.split(':')
        hora_norm = f"{int(partes[0]):02d}:{int(partes[1]):02d}"
        return True, hora_norm, f"✅ Hora: {hora_norm}"

    return False, "", f"❌ '{entrada}' no es válido. Formato: HH:MM (ej: 10:30, 14:05)"


def ask_time(mensaje: str = "¿Hora?", allow_empty: bool = True) -> str:
    """
    Pide una hora al usuario con validación.
    Enter usa la hora actual.
    """
    while True:
        ahora = datetime.now().strftime('%H:%M')
        print(f"\n{mensaje} (formato HH:MM, Enter = {ahora})")
        entrada = input("→ ").strip()

        valido, hora, mensaje_resp = validate_time(entrada, allow_empty=allow_empty)
        print(f"  {mensaje_resp}")

        if valido:
            return hora

# ============================================================
# VALIDACIÓN DE FECHA
# ============================================================

def validate_date(input_str: str, allow_empty: bool = False) -> tuple[bool, str, str]:
    """
    Valida formato de fecha DD/MM/YYYY o YYYY-MM-DD.
    Retorna: (válido, fecha_str, mensaje_error)
    """
    if not input_str or not input_str.strip():
        if allow_empty:
            hoy = datetime.now().strftime('%Y-%m-%d')
            return True, hoy, f"✅ Usando fecha actual: {hoy}"
        return False, "", "❌ La fecha no puede estar vacía"

    entrada = input_str.strip()

    # Intentar DD/MM/YYYY
    try:
        dt = datetime.strptime(entrada, '%d/%m/%Y')
        return True, dt.strftime('%Y-%m-%d'), f"✅ Fecha: {dt.strftime('%d/%m/%Y')}"
    except ValueError:
        pass

    # Intentar YYYY-MM-DD
    try:
        dt = datetime.strptime(entrada, '%Y-%m-%d')
        return True, dt.strftime('%Y-%m-%d'), f"✅ Fecha: {dt.strftime('%d/%m/%Y')}"
    except ValueError:
        pass

    return False, "", f"❌ '{entrada}' no es válido. Formato: DD/MM/YYYY (ej: 12/03/2026)"


def ask_date(mensaje: str = "¿Fecha?", allow_empty: bool = True) -> str:
    """Pide una fecha con validación."""
    while True:
        hoy = datetime.now().strftime('%d/%m/%Y')
        print(f"\n{mensaje} (formato DD/MM/YYYY, Enter = hoy {hoy})")
        entrada = input("→ ").strip()

        valido, fecha, mensaje_resp = validate_date(entrada, allow_empty=allow_empty)
        print(f"  {mensaje_resp}")

        if valido:
            return fecha

# ============================================================
# VALIDACIÓN DE TIMEFRAME
# ============================================================

def validate_timeframe(input_str: str, allow_empty: bool = True) -> tuple[bool, str, str]:
    """
    Valida que el timeframe sea uno de los configurados.
    Retorna: (válido, timeframe_str, mensaje_error)
    """
    if not input_str or not input_str.strip():
        if allow_empty:
            return True, "", "✅ Sin timeframe específico"
        return False, "", "❌ El timeframe no puede estar vacío"

    entrada = input_str.strip().lower()

    if entrada in TIMEFRAMES:
        return True, entrada, f"✅ Timeframe: {entrada}"

    return False, "", f"❌ '{entrada}' no es válido. Opciones: {', '.join(TIMEFRAMES)}"


def ask_timeframe(mensaje: str = "¿Timeframe?") -> str:
    """Pide un timeframe con validación."""
    while True:
        print(f"\n{mensaje} (opciones: {', '.join(TIMEFRAMES)}, Enter = ninguno)")
        entrada = input("→ ").strip()

        valido, tf, mensaje_resp = validate_timeframe(entrada, allow_empty=True)
        print(f"  {mensaje_resp}")

        if valido:
            return tf

# ============================================================
# VALIDACIÓN DE OPCIÓN DE MENÚ
# ============================================================

def validate_option(input_str: str, opciones_validas: list) -> tuple[bool, str, str]:
    """
    Valida que la opción esté dentro de las válidas.
    Retorna: (válido, opción_str, mensaje_error)
    """
    if not input_str or not input_str.strip():
        return False, "", "❌ Debes elegir una opción"

    entrada = input_str.strip()

    if entrada in [str(o) for o in opciones_validas]:
        return True, entrada, ""

    return False, "", f"❌ Opción '{entrada}' no válida. Elige: {', '.join([str(o) for o in opciones_validas])}"


def ask_option(mensaje: str, opciones: list) -> str:
    """Pide una opción de menú con validación."""
    while True:
        entrada = input(f"\n{mensaje}: ").strip()
        valido, opcion, msg = validate_option(entrada, opciones)

        if valido:
            return opcion
        print(f"  {msg}")

# ============================================================
# VALIDACIÓN DE ID DE POSICIÓN
# ============================================================

def validate_position_id(input_str: str) -> tuple[bool, int, str]:
    """
    Valida que el ID de posición exista y esté abierta.
    Retorna: (válido, id_int, mensaje_error)
    """
    from database import get_connection

    if not input_str or not input_str.strip():
        return False, 0, "❌ Debes ingresar un ID de posición"

    # Limpiar # si lo tiene
    limpio = input_str.strip().replace("#", "")

    try:
        pos_id = int(limpio)
    except ValueError:
        return False, 0, f"❌ '{input_str}' no es un ID válido. Ejemplo: 1 o #1"

    # Verificar que existe y está abierta
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, crypto, status FROM positions WHERE id = ?", (pos_id,))
    pos = cursor.fetchone()
    conn.close()

    if not pos:
        return False, 0, f"❌ No existe la posición #{pos_id}"

    if pos[2] != 'open':
        return False, 0, f"❌ La posición #{pos_id} ya está cerrada"

    nombre = CRYPTO_NAMES.get(pos[1], pos[1])
    return True, pos_id, f"✅ Posición #{pos_id} — {nombre}"


def ask_position_id(mensaje: str = "¿ID de posición?") -> int:
    """Pide un ID de posición con validación."""
    while True:
        print(f"\n{mensaje} (ej: 1 o #1)")
        entrada = input("→ ").strip()

        valido, pos_id, msg = validate_position_id(entrada)
        print(f"  {msg}")

        if valido:
            return pos_id

# ============================================================
# VALIDACIÓN DE TEXTO LIBRE (notas)
# ============================================================

def validate_notes(input_str: str, max_length: int = 500) -> tuple[bool, str, str]:
    """
    Valida notas opcionales — limita longitud.
    Retorna: (válido, texto_str, mensaje_error)
    """
    if not input_str or not input_str.strip():
        return True, "", "✅ Sin notas"

    texto = input_str.strip()

    if len(texto) > max_length:
        return False, "", f"❌ Texto demasiado largo ({len(texto)} chars). Máximo: {max_length}"

    return True, texto, f"✅ Notas guardadas"


def ask_notes(mensaje: str = "¿Notas? (opcional)") -> str:
    """Pide notas opcionales con validación."""
    while True:
        print(f"\n{mensaje} (Enter para omitir, máx 500 caracteres)")
        entrada = input("→ ").strip()

        valido, notas, msg = validate_notes(entrada)
        if not entrada:
            return ""
        print(f"  {msg}")

        if valido:
            return notas

# ============================================================
# VALIDACIÓN DE ESTILO DE TRADING
# ============================================================

def ask_trading_style(mensaje: str = "¿Para qué tipo de trading?") -> str:
    """Pide el estilo de trading con validación."""
    print(f"\n{mensaje}")
    print("  1 → Scalping     (5M, 15M)")
    print("  2 → Day Trading  (30M, 1H)")
    print("  3 → Swing        (4H, 8H)")
    print("  4 → Posicional   (1D)")
    print("  5 → Todos los timeframes")

    return ask_option("Opción", ["1", "2", "3", "4", "5"])


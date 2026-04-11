# ============================================================
# claude_analyst.py — Cerebro del sistema
# Construye el prompt completo y se comunica con Claude AI
# Guarda cada análisis y genera lecciones aprendidas
# ============================================================

import anthropic
import sqlite3
import json
from datetime import datetime
from error_handler import (
    setup_logger, ClaudeAPIKeyError,
    ClaudeRateLimitError, ClaudeTimeoutError, ClaudeError
)

logger = setup_logger(__name__)

from config import (
    CLAUDE_API_KEY, CLAUDE_MODEL, TEST_MODE,
    ACTIVE_CRYPTOS, CRYPTO_NAMES, TRADING_STYLES,
    CANDLES_TO_ANALYZE, NEWS_TO_ANALYZE, LESSONS_TO_INCLUDE
)
from database import (
    get_connection, get_open_positions,
    get_recent_lessons, get_recent_news
)
from data_collector import get_technical_summary, get_current_price
from news_collector import get_news_summary

# ============================================================
# SISTEMA DE PROMPT — Personalidad y conocimiento de Claude
# ============================================================

SYSTEM_PROMPT = """Eres un analista experto en trading de criptomonedas con más de 10 años de experiencia.

Tu rol es analizar datos técnicos y fundamentales para ayudar a tomar decisiones de trading informadas.

CONOCIMIENTO BASE QUE TIENES:
- Análisis técnico completo: RSI, MACD, EMA, Bollinger Bands, ADX, Stochastic RSI, ATR, OBV, CCI, Williams %R, Momentum, VWAP
- Patrones de velas japonesas: martillo, doji, engulfing, estrella fugaz, etc.
- Divergencias técnicas y su significado
- Análisis multi-timeframe (de mayor a menor)
- Soportes y resistencias
- Análisis fundamental: impacto de noticias, regulaciones, adopción institucional
- Psicología del mercado crypto

JERARQUÍA DE SEÑALES QUE APLICAS:
1. Eventos fundamentales CRÍTICOS (regulaciones, hacks, colapsos) → anulan análisis técnico
2. Tendencia del timeframe mayor (1D, 8H) → siempre manda sobre el menor
3. Confirmación multi-timeframe → más confiable que señal única
4. Volumen confirma movimiento → sin volumen la señal es débil
5. Indicadores en conjunto → nunca una señal aislada

REGLAS DE ANÁLISIS:
- El ADX bajo 20 indica mercado sin tendencia → evitar trades direccionales
- RSI extremo (>80 o <20) es más significativo que RSI moderado
- Divergencias RSI/OBV son señales de alerta temprana
- Noticias de alto impacto pueden anular cualquier señal técnica
- Siempre calcular stop loss basado en ATR
- Considerar el contexto histórico antes de recomendar

FORMATO DE RESPUESTA:
Siempre responde en este formato exacto:

RECOMENDACIÓN: [COMPRAR / VENDER / ESPERAR]
CONFIANZA: [ALTA / MEDIA / BAJA]
PRECIO ENTRADA SUGERIDO: [precio o "precio actual"]
STOP LOSS: [precio]
TAKE PROFIT: [precio]
TIMEFRAME DOMINANTE: [el timeframe más relevante para esta decisión]

ANÁLISIS TÉCNICO:
[Resumen del análisis técnico multi-timeframe]

ANÁLISIS FUNDAMENTAL:
[Impacto de noticias y eventos actuales]

FACTOR DOMINANTE:
[TÉCNICO / FUNDAMENTAL / AMBOS — cuál está mandando más y por qué]

CONTEXTO HISTÓRICO:
[Qué dice el historial pasado sobre situaciones similares]

LECCIÓN APRENDIDA SUGERIDA:
[Una lección concisa para guardar en la base de datos]

RAZONAMIENTO COMPLETO:
[Explicación detallada de todos los factores considerados]"""

# ============================================================
# CONSTRUCCIÓN DEL PROMPT DE USUARIO
# ============================================================

def build_analysis_prompt(crypto: str, user_question: str = None, trading_style: str = "5") -> str:
    """
    Construye el prompt completo con toda la información
    disponible para enviar a Claude.
    """
    precio_actual = get_current_price(crypto)
    nombre        = CRYPTO_NAMES.get(crypto, crypto)
    ahora         = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    estilo = TRADING_STYLES.get(trading_style, TRADING_STYLES["5"])
    timeframes_activos = estilo["timeframes"]

    prompt = f"""
═══════════════════════════════════════════════════════
ANÁLISIS SOLICITADO: {nombre} ({crypto})
Fecha y hora: {ahora}
Precio actual: ${precio_actual:,.4f}
TIPO DE TRADING: {estilo["nombre"]}
TIMEFRAMES FOCO: {", ".join(timeframes_activos)}
→ Enfoca tu análisis en estos timeframes
→ Usa 1D solo como contexto general si no está en el foco
═══════════════════════════════════════════════════════
"""

    # ── 1. ANÁLISIS TÉCNICO COMPLETO ─────────────────────────
    prompt += get_technical_summary(crypto, timeframes=timeframes_activos)

    # ── 2. NOTICIAS Y ANÁLISIS FUNDAMENTAL ───────────────────
    prompt += "\n" + get_news_summary(crypto, limit=NEWS_TO_ANALYZE)

    # ── 3. POSICIONES ABIERTAS ───────────────────────────────
    posiciones = get_open_positions()
    posiciones_crypto = [p for p in posiciones if p['crypto'] == crypto]

    if posiciones_crypto:
        prompt += f"\n💼 POSICIONES ABIERTAS EN {crypto}:\n"
        prompt += "━" * 50 + "\n"
        for pos in posiciones_crypto:
            resultado_actual = ((precio_actual - pos['entry_price']) / pos['entry_price']) * 100
            emoji = "🟢" if resultado_actual > 0 else "🔴"
            prompt += f"  #{pos['id']} | Entrada: ${pos['entry_price']:,.4f} a las {pos['entry_time']}\n"
            prompt += f"  Resultado actual: {emoji} {resultado_actual:+.2f}%\n"
            prompt += f"  Stop loss recomendado al abrir: basado en ATR\n\n"
    else:
        prompt += f"\n💼 No hay posiciones abiertas en {crypto}\n"

    # ── 4. LECCIONES APRENDIDAS DEL PASADO ───────────────────
    lecciones = get_recent_lessons(limit=LESSONS_TO_INCLUDE)
    lecciones_crypto = [l for l in lecciones if l['crypto'] == crypto]

    if lecciones_crypto:
        prompt += f"\n🧠 LECCIONES APRENDIDAS ANTERIORES ({crypto}):\n"
        prompt += "━" * 50 + "\n"
        for l in lecciones_crypto[:10]:
            resultado_emoji = "✅" if l['result'] == 'win' else "❌"
            prompt += f"  {resultado_emoji} [{l['datetime'][:10]}] {l['lesson_text']}\n"
            prompt += f"     Factor dominante: {l['dominant_factor']} | Resultado: {l['result_pct']:+.1f}%\n\n"
    else:
        prompt += f"\n🧠 Aún no hay lecciones aprendidas para {crypto}\n"

    # ── 5. HISTORIAL DE PRECISIÓN ────────────────────────────
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correctas
        FROM claude_analysis
        WHERE crypto = ? AND was_correct IS NOT NULL
    """, (crypto,))
    stats = cursor.fetchone()
    conn.close()

    if stats and stats[0] > 0:
        precision = (stats[1] / stats[0]) * 100
        prompt += f"\n📊 MI HISTORIAL EN {crypto}:\n"
        prompt += f"   Análisis realizados: {stats[0]}\n"
        prompt += f"   Precisión: {precision:.1f}% ({stats[1]}/{stats[0]} correctos)\n"

    # ── 6. PREGUNTA DEL USUARIO ───────────────────────────────
    prompt += "\n═══════════════════════════════════════════════════════\n"
    if user_question:
        prompt += f"PREGUNTA: {user_question}\n"
    else:
        prompt += f"PREGUNTA: Analiza {nombre} con toda la información disponible y dame tu recomendación.\n"
    prompt += "═══════════════════════════════════════════════════════\n"

    return prompt

# ============================================================
# LLAMADA A CLAUDE API
# ============================================================

def call_claude(prompt: str) -> str:
    """
    Envía el prompt a Claude y retorna su respuesta.
    En modo prueba retorna una respuesta simulada.
    """
    if TEST_MODE or not CLAUDE_API_KEY:
        return _mock_response()

    try:
        client   = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message  = client.messages.create(
            model      = CLAUDE_MODEL,
            max_tokens = 2000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    except anthropic.AuthenticationError as e:
        err = ClaudeAPIKeyError(
            "API Key de Claude invalida — revisa tu archivo .env",
            context={"variable": "CLAUDE_API_KEY", "error": str(e)}
        )
        err.log(logger); err.show()
        return None
    except anthropic.RateLimitError as e:
        err = ClaudeRateLimitError(
            "Rate limit de Claude alcanzado — espera unos segundos",
            context={"modelo": CLAUDE_MODEL, "error": str(e)}
        )
        err.log(logger); err.show()
        return None
    except anthropic.APITimeoutError as e:
        err = ClaudeTimeoutError(
            "Timeout al llamar a Claude — reintenta en un momento",
            context={"modelo": CLAUDE_MODEL, "error": str(e)}
        )
        err.log(logger); err.show()
        return None
    except Exception as e:
        err = ClaudeError(
            "Error inesperado al llamar a Claude",
            context={"modelo": CLAUDE_MODEL, "error": str(e)}
        )
        err.log(logger); err.show()
        return None

def _mock_response() -> str:
    """Respuesta simulada para pruebas sin API key."""
    return """
RECOMENDACIÓN: ESPERAR
CONFIANZA: MEDIA
PRECIO ENTRADA SUGERIDO: precio actual
STOP LOSS: -3% del precio actual
TAKE PROFIT: +6% del precio actual
TIMEFRAME DOMINANTE: 1H

ANÁLISIS TÉCNICO:
[MODO PRUEBA] Sin API key de Claude configurada.
Los indicadores técnicos están siendo calculados correctamente.
Agrega tu CLAUDE_API_KEY al archivo .env para análisis real.

ANÁLISIS FUNDAMENTAL:
[MODO PRUEBA] Las noticias se están recolectando correctamente.

FACTOR DOMINANTE: TÉCNICO

CONTEXTO HISTÓRICO:
Sin historial disponible aún.

LECCIÓN APRENDIDA SUGERIDA:
Sistema en modo prueba — configura API key para análisis real.

RAZONAMIENTO COMPLETO:
Este es un análisis simulado. Para obtener análisis real,
agrega tu CLAUDE_API_KEY al archivo .env
"""

# ============================================================
# PARSEO DE RESPUESTA
# ============================================================

def parse_response(response: str) -> dict:
    """
    Extrae los campos estructurados de la respuesta de Claude.
    """
    resultado = {
        "recommendation": "ESPERAR",
        "confidence":     "MEDIA",
        "entry_price":    None,
        "stop_loss":      None,
        "take_profit":    None,
        "timeframe":      None,
        "technical":      "",
        "fundamental":    "",
        "dominant_factor":"TÉCNICO",
        "lesson":         "",
        "reasoning":      "",
        "raw":            response,
    }

    if not response:
        return resultado

    lines = response.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith("RECOMENDACIÓN:"):
            rec = line.replace("RECOMENDACIÓN:", "").strip()
            if "COMPRAR" in rec.upper():   resultado["recommendation"] = "COMPRAR"
            elif "VENDER" in rec.upper():  resultado["recommendation"] = "VENDER"
            else:                          resultado["recommendation"] = "ESPERAR"

        elif line.startswith("CONFIANZA:"):
            conf = line.replace("CONFIANZA:", "").strip().upper()
            if "ALTA" in conf:    resultado["confidence"] = "ALTA"
            elif "BAJA" in conf:  resultado["confidence"] = "BAJA"
            else:                 resultado["confidence"] = "MEDIA"

        elif line.startswith("TIMEFRAME DOMINANTE:"):
            resultado["timeframe"] = line.replace("TIMEFRAME DOMINANTE:", "").strip()

        elif line.startswith("FACTOR DOMINANTE:"):
            resultado["dominant_factor"] = line.replace("FACTOR DOMINANTE:", "").strip()

        elif line.startswith("LECCIÓN APRENDIDA SUGERIDA:"):
            resultado["lesson"] = line.replace("LECCIÓN APRENDIDA SUGERIDA:", "").strip()

    # Extraer secciones completas
    secciones = {
        "ANÁLISIS TÉCNICO:":      "technical",
        "ANÁLISIS FUNDAMENTAL:":  "fundamental",
        "RAZONAMIENTO COMPLETO:": "reasoning",
    }

    for seccion, campo in secciones.items():
        if seccion in response:
            partes = response.split(seccion)
            if len(partes) > 1:
                # Tomar hasta la siguiente sección
                contenido = partes[1].split('\n\n')[0].strip()
                resultado[campo] = contenido

    return resultado

# ============================================================
# GUARDADO DEL ANÁLISIS
# ============================================================

def save_analysis(crypto: str, precio: float, prompt: str, parsed: dict) -> int:
    """Guarda el análisis de Claude en la base de datos."""
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO claude_analysis
        (datetime, timestamp, crypto, timeframe_focus,
         technical_summary, news_summary,
         recommendation, confidence, reasoning, price_at_analysis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        int(datetime.now().timestamp() * 1000),
        crypto,
        parsed.get("timeframe", ""),
        parsed.get("technical", ""),
        parsed.get("fundamental", ""),
        parsed.get("recommendation", ""),
        parsed.get("confidence", ""),
        parsed.get("reasoning", ""),
        precio,
    ))

    analysis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return analysis_id

# ============================================================
# ANÁLISIS PRINCIPAL
# ============================================================

def analyze(crypto: str, user_question: str = None, trading_style: str = "5", verbose: bool = True) -> dict:
    """
    Función principal — analiza una crypto y retorna resultado.
    """
    nombre = CRYPTO_NAMES.get(crypto, crypto)

    if verbose:
        print(f"\n🤖 Analizando {nombre}...")
        print(f"   Construyendo contexto completo...")

    # Construir prompt
    prompt = build_analysis_prompt(crypto, user_question, trading_style)

    if verbose:
        tokens_aprox = len(prompt.split()) * 1.3
        print(f"   Tokens aproximados: {int(tokens_aprox)}")
        print(f"   Enviando a Claude...")

    # Llamar a Claude
    response = call_claude(prompt)

    if not response:
        print(f"❌ No se obtuvo respuesta de Claude")
        return {}

    # Parsear respuesta
    parsed = parse_response(response)

    # Guardar análisis
    precio      = get_current_price(crypto)
    analysis_id = save_analysis(crypto, precio, prompt, parsed)

    if verbose:
        print(f"\n{'═'*55}")
        print(f"  📊 ANÁLISIS {nombre}")
        print(f"{'═'*55}")
        print(f"  Precio: ${precio:,.4f}")
        print(f"  Recomendación: {parsed['recommendation']}")
        print(f"  Confianza: {parsed['confidence']}")
        print(f"  Factor dominante: {parsed['dominant_factor']}")
        print(f"  Timeframe clave: {parsed['timeframe']}")
        print(f"{'─'*55}")
        print(f"\n{response}")
        print(f"\n✅ Análisis guardado con ID #{analysis_id}")

    parsed['analysis_id'] = analysis_id
    parsed['crypto']      = crypto
    parsed['price']       = precio

    return parsed

# ============================================================
# CHAT INTERACTIVO CON CLAUDE
# ============================================================

def chat(crypto: str = None) -> None:
    """
    Modo chat interactivo — conversación directa con Claude
    con todo el contexto del mercado cargado.
    """
    print("\n" + "═"*55)
    print("  💬 CHAT CON CLAUDE — Analista Crypto")
    print("═"*55)
    print("  Comandos especiales:")
    print("  'analizar BTC'  → análisis completo de BTC")
    print("  'abrir BTC 87000 10:30' → registrar apertura")
    print("  'cerrar #001 91500 14:30' → registrar cierre")
    print("  'posiciones'    → ver posiciones abiertas")
    print("  'salir'         → terminar chat")
    print("═"*55)

    historial = []

    while True:
        try:
            entrada = input("\nTú: ").strip()
        except KeyboardInterrupt:
            print("\n👋 Hasta luego!")
            break

        if not entrada:
            continue

        if entrada.lower() == 'salir':
            print("👋 Hasta luego!")
            break

        # Comandos especiales
        if entrada.lower().startswith('analizar '):
            simbolo = entrada.split()[1].upper()
            if not simbolo.endswith('USDT'):
                simbolo += 'USDT'
            analyze(simbolo, verbose=True)
            continue

        if entrada.lower() == 'posiciones':
            posiciones = get_open_positions()
            if posiciones:
                print("\n💼 POSICIONES ABIERTAS:")
                for p in posiciones:
                    print(f"  #{p['id']} {p['crypto']} | Entrada: ${p['entry_price']:,.4f} | {p['entry_time']}")
            else:
                print("\n💼 No hay posiciones abiertas")
            continue

        # Conversación normal con contexto
        contexto = ""
        if crypto:
            precio = get_current_price(crypto)
            contexto = f"[Contexto: {CRYPTO_NAMES.get(crypto, crypto)} a ${precio:,.4f}] "

        historial.append({"role": "user", "content": contexto + entrada})

        if TEST_MODE or not CLAUDE_API_KEY:
            print("\nClaude: [MODO PRUEBA] Configura tu CLAUDE_API_KEY para respuestas reales.")
            historial.append({"role": "assistant", "content": "[Modo prueba]"})
            continue

        try:
            client   = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            message  = client.messages.create(
                model      = CLAUDE_MODEL,
                max_tokens = 1000,
                system     = SYSTEM_PROMPT,
                messages   = historial
            )
            respuesta = message.content[0].text
            print(f"\nClaude: {respuesta}")
            historial.append({"role": "assistant", "content": respuesta})

        except anthropic.AuthenticationError as e:
            err = ClaudeAPIKeyError("API Key invalida", context={"error": str(e)})
            err.log(logger); err.show()
        except anthropic.RateLimitError as e:
            err = ClaudeRateLimitError("Rate limit alcanzado — espera unos segundos", context={"error": str(e)})
            err.log(logger); err.show()
        except Exception as e:
            err = ClaudeError("Error en chat con Claude", context={"error": str(e)})
            err.log(logger); err.show()

def analyze_all(user_question: str = None, trading_style: str = "5", verbose: bool = True) -> list:
    print("\n🔍 Analizando todas las cryptos activas...")
    print(f"   Cryptos: {', '.join(ACTIVE_CRYPTOS)}\n")

    resultados = []
    for crypto in ACTIVE_CRYPTOS:
        resultado = analyze(crypto, user_question, trading_style, verbose=False)
        if resultado:
            resultados.append(resultado)
            rec   = resultado.get('recommendation', 'ESPERAR')
            conf  = resultado.get('confidence', 'BAJA')
            emoji = "🟢" if rec == "COMPRAR" else "🔴" if rec == "VENDER" else "🟡"
            print(f"   {emoji} {CRYPTO_NAMES.get(crypto, crypto):20} → {rec:8} | Confianza: {conf}")

    orden      = {"COMPRAR": 0, "VENDER": 1, "ESPERAR": 2}
    orden_conf = {"ALTA": 0, "MEDIA": 1, "BAJA": 2}
    resultados.sort(key=lambda x: (
        orden.get(x.get('recommendation', 'ESPERAR'), 2),
        orden_conf.get(x.get('confidence', 'BAJA'), 2)
    ))

    print(f"\n{'═'*55}")
    print(f"  🏆 RANKING DE OPORTUNIDADES")
    print(f"{'═'*55}")
    for i, r in enumerate(resultados, 1):
        nombre = CRYPTO_NAMES.get(r['crypto'], r['crypto'])
        rec    = r.get('recommendation', 'ESPERAR')
        conf   = r.get('confidence', 'BAJA')
        precio = r.get('price', 0)
        emoji  = "🟢" if rec == "COMPRAR" else "🔴" if rec == "VENDER" else "🟡"
        print(f"  {i}. {emoji} {nombre:20} ${precio:>12,.4f} | {rec:8} | {conf}")

    return resultados

def analyze_best(trading_style: str = "5", verbose: bool = True) -> dict:
    """
    Analiza todas las cryptos activas y le pide a Claude
    que elija la MEJOR oportunidad comparándolas entre sí.
    """
    from config import TRADING_STYLES
    estilo = TRADING_STYLES.get(trading_style, TRADING_STYLES["5"])

    print("\n🔍 Analizando todas las cryptos para encontrar la mejor...")
    print(f"   Cryptos: {', '.join(ACTIVE_CRYPTOS)}\n")

    # Recopilar resumen técnico de todas
    resumenes = []
    precios   = {}

    for crypto in ACTIVE_CRYPTOS:
        nombre = CRYPTO_NAMES.get(crypto, crypto)
        precio = get_current_price(crypto)
        precios[crypto] = precio
        resumen = get_technical_summary(crypto, timeframes=estilo["timeframes"])
        resumenes.append(f"{'═'*50}\n{resumen}")
        print(f"   ✅ {nombre} recopilado")

    # Construir prompt de comparación
    cryptos_str = ", ".join([CRYPTO_NAMES.get(c, c) for c in ACTIVE_CRYPTOS])
    prompt = f"""
═══════════════════════════════════════════════════════
ANÁLISIS COMPARATIVO — Elegir mejor oportunidad
Tipo de trading: {estilo["nombre"]}
Timeframes: {", ".join(estilo["timeframes"])}
Cryptos analizadas: {cryptos_str}
═══════════════════════════════════════════════════════

Aquí están los datos técnicos de cada crypto:

{"".join(resumenes)}

NOTICIAS RECIENTES:
{get_news_summary(limit=10)}

═══════════════════════════════════════════════════════
PREGUNTA: Analiza TODAS las cryptos anteriores y:
1. Compáralas entre sí considerando setup técnico y noticias
2. Elige la UNA mejor oportunidad de trading ahora mismo
3. Explica por qué esa y no las otras
4. Da una recomendación clara de entrada

Responde en este formato:
MEJOR OPORTUNIDAD: [nombre de la crypto]
RECOMENDACIÓN: [COMPRAR / VENDER / ESPERAR]
CONFIANZA: [ALTA / MEDIA / BAJA]
PRECIO ENTRADA: [precio]
STOP LOSS: [precio]
TAKE PROFIT: [precio]

POR QUÉ ESTA Y NO LAS OTRAS:
[Comparación directa explicando por qué esta crypto
tiene mejor setup que las demás ahora mismo]

RAZONAMIENTO:
[Análisis detallado de la oportunidad elegida]
═══════════════════════════════════════════════════════
"""

    if verbose:
        tokens = int(len(prompt.split()) * 1.3)
        print(f"\n   Tokens aproximados: {tokens}")
        print(f"   Enviando comparación a Claude...")

    response = call_claude(prompt)

    if not response:
        print("❌ No se obtuvo respuesta de Claude")
        return {}

    print(f"\n{'═'*55}")
    print(f"  🏆 MEJOR OPORTUNIDAD SEGÚN CLAUDE")
    print(f"{'═'*55}")
    print(response)

    return {"response": response, "cryptos": ACTIVE_CRYPTOS}



# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    from validators import ask_crypto, ask_trading_style, ask_option

    print("=" * 55)
    print("  🤖 ANALISTA CRYPTO — Claude AI")
    print("=" * 55)
    print("\n¿Qué quieres hacer?")
    print("  1 → Analizar UNA crypto")
    print("  2 → Analizar TODAS")
    print("  3 → Chat interactivo")

    opcion = ask_option("Opción", ["1", "2", "3"])

    if opcion == "1":
        simbolo = ask_crypto("¿Qué crypto analizar?")
        estilo  = ask_trading_style()
        analyze(simbolo, trading_style=estilo, verbose=True)

    elif opcion == "2":
        print("\n¿Qué quieres hacer?")
        print("  a → Ver recomendación de cada crypto")
        print("  b → Elegir la mejor oportunidad ahora")
        modo   = ask_option("Opción", ["a", "b"])
        estilo = ask_trading_style()

        if modo == "b":
            analyze_best(trading_style=estilo, verbose=True)
        else:
            analyze_all(trading_style=estilo, verbose=True)

    elif opcion == "3":
        print("\n¿Crypto de contexto? (Enter = ninguna)")
        entrada = input("→ ").strip()
        if entrada:
            from validators import validate_crypto
            _, simbolo, _ = validate_crypto(entrada)
        else:
            simbolo = None
        chat(simbolo)

    else:
        print("❌ Opción no válida")


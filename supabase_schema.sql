-- ============================================================
-- supabase_schema.sql
-- Ejecuta este script en Supabase → SQL Editor → New Query
-- Crea TODAS las tablas necesarias para el sistema
-- ============================================================

-- ── EXTENSIONES ─────────────────────────────────────────────
-- (ya vienen activadas en Supabase por defecto)

-- ============================================================
-- TABLA: news
-- ============================================================
CREATE TABLE IF NOT EXISTS news (
    id            SERIAL PRIMARY KEY,
    timestamp     BIGINT UNIQUE,
    datetime      TEXT,
    title         TEXT,
    source        TEXT,
    url           TEXT,
    crypto        TEXT,
    sentiment     TEXT,
    impact        TEXT,
    processed     INTEGER DEFAULT 0,
    resumen       TEXT,
    razon_impacto TEXT,
    categoria     TEXT,
    fuente_tipo   TEXT
);

CREATE INDEX IF NOT EXISTS idx_news_timestamp ON news (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_news_crypto    ON news (crypto);

-- ============================================================
-- TABLA: positions
-- ============================================================
CREATE TABLE IF NOT EXISTS positions (
    id                    SERIAL PRIMARY KEY,
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
);

CREATE INDEX IF NOT EXISTS idx_positions_status    ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_crypto    ON positions (crypto);
CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions (entry_timestamp DESC);

-- ============================================================
-- TABLA: lessons
-- ============================================================
CREATE TABLE IF NOT EXISTS lessons (
    id              SERIAL PRIMARY KEY,
    position_id     INTEGER REFERENCES positions(id),
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
);

CREATE INDEX IF NOT EXISTS idx_lessons_crypto ON lessons (crypto);
CREATE INDEX IF NOT EXISTS idx_lessons_id     ON lessons (id DESC);

-- ============================================================
-- TABLA: claude_analysis
-- ============================================================
CREATE TABLE IF NOT EXISTS claude_analysis (
    id                SERIAL PRIMARY KEY,
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
);

CREATE INDEX IF NOT EXISTS idx_analysis_crypto    ON claude_analysis (crypto);
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON claude_analysis (timestamp DESC);

-- ============================================================
-- TABLAS DE VELAS — una por cada crypto + timeframe
-- Se crean dinámicamente. Este script crea las de las
-- 4 cryptos activas por defecto (BTC, ETH, SOL, SEI).
-- Las demás se crean automáticamente cuando las activas.
-- ============================================================

-- Función helper para crear tablas de velas
CREATE OR REPLACE FUNCTION create_candle_table(table_name TEXT)
RETURNS void AS $$
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I (
            id          SERIAL PRIMARY KEY,
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
        )', table_name);
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %I (timestamp DESC)',
        'idx_' || replace(table_name, '-', '_') || '_ts',
        table_name
    );
END;
$$ LANGUAGE plpgsql;

-- Crear tablas para las cryptos activas por defecto
DO $$
DECLARE
    cryptos TEXT[] := ARRAY[
        'btcusdt','ethusdt','solusdt','seiusdt',
        'xrpusdt','dogeusdt','adausdt','avaxusdt',
        'dotusdt','xlmusdt','algousdt','vetusdt',
        'aaveusdt','injusdt','grtusdt','snxusdt',
        'cakeusdt','sandusdt','suiusdt','hbarusdt',
        'ckbusdt','fetusdt','maskusdt','axsusdt',
        'slpusdt','apeusdt','mboxusdt','shibusdt',
        'zenusdt','lptusdt','xvgusdt','xecusdt',
        'tfuelusdt','powrusdt','ognusdt','c98usdt',
        'duskusdt','iotausdt','saharausdt'
    ];
    timeframes TEXT[] := ARRAY['5m','15m','30m','1h','4h','8h','1d'];
    crypto TEXT;
    tf TEXT;
BEGIN
    FOREACH crypto IN ARRAY cryptos LOOP
        FOREACH tf IN ARRAY timeframes LOOP
            PERFORM create_candle_table('candles_' || crypto || '_' || tf);
        END LOOP;
    END LOOP;
END $$;

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Supabase lo activa por defecto. Lo configuramos para que
-- solo usuarios autenticados puedan leer/escribir.
-- ============================================================

-- Habilitar RLS en todas las tablas de negocio
ALTER TABLE news            ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE lessons         ENABLE ROW LEVEL SECURITY;
ALTER TABLE claude_analysis ENABLE ROW LEVEL SECURITY;

-- Política: cualquier usuario autenticado puede hacer todo
-- (ya que el control de acceso lo maneja el backend con JWT)
CREATE POLICY "authenticated_full_access" ON news
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_full_access" ON positions
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_full_access" ON lessons
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_full_access" ON claude_analysis
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- VERIFICACIÓN FINAL
-- ============================================================
SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

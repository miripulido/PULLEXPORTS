-- ================================================================
-- AutoExport - Schema para Supabase (PostgreSQL)
-- Ejecuta esto en el SQL Editor de Supabase
-- ================================================================

-- Tabla principal de coches
CREATE TABLE IF NOT EXISTS cars (
    id            BIGSERIAL PRIMARY KEY,
    url           TEXT UNIQUE NOT NULL,
    source        TEXT NOT NULL,          -- autoscout24 / mobile.de / kleinanzeigen / leboncoin
    title         TEXT,
    make          TEXT,
    model         TEXT,
    year          INTEGER,
    km            INTEGER,
    price         INTEGER NOT NULL,       -- precio en origen (€)
    country       TEXT,                  -- DE / FR / BE / PL / PT
    cv            INTEGER,               -- caballos
    fuel          TEXT,

    -- Análisis de oportunidad
    spain_ref_price    INTEGER,           -- precio referencia en España (coches.net)
    total_cost_estimate INTEGER,          -- price + gastos homologación/transporte
    estimated_profit   INTEGER,          -- spain_ref_price - total_cost_estimate
    margin_pct         NUMERIC(5,2),     -- % margen sobre precio venta
    opportunity_score  INTEGER,          -- score 0-100

    scraped_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para filtrar rápido en el dashboard
CREATE INDEX IF NOT EXISTS idx_cars_country     ON cars (country);
CREATE INDEX IF NOT EXISTS idx_cars_price       ON cars (price);
CREATE INDEX IF NOT EXISTS idx_cars_score       ON cars (opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_cars_make        ON cars (make);
CREATE INDEX IF NOT EXISTS idx_cars_scraped_at  ON cars (scraped_at DESC);

-- Row Level Security: solo lectura pública (para el dashboard)
ALTER TABLE cars ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public_read" ON cars
    FOR SELECT USING (true);

-- Solo el service role puede insertar/actualizar (el scraper usa service key)
CREATE POLICY "service_write" ON cars
    FOR ALL USING (auth.role() = 'service_role');

-- Vista útil: solo coches con margen positivo, ordenados por score
CREATE OR REPLACE VIEW good_opportunities AS
SELECT
    id, source, title, make, model, year, km, price, country, cv,
    spain_ref_price, total_cost_estimate, estimated_profit, margin_pct,
    opportunity_score, url, scraped_at
FROM cars
WHERE
    estimated_profit > 0
    AND opportunity_score >= 60
    AND scraped_at > NOW() - INTERVAL '7 days'
ORDER BY opportunity_score DESC;

-- Función para estadísticas del dashboard
CREATE OR REPLACE FUNCTION dashboard_stats()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'total_cars',     COUNT(*),
        'avg_margin_pct', ROUND(AVG(margin_pct)::NUMERIC, 1),
        'best_profit',    MAX(estimated_profit),
        'last_updated',   MAX(scraped_at)
    ) INTO result
    FROM cars
    WHERE scraped_at > NOW() - INTERVAL '7 days'
      AND estimated_profit > 0;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- FAQ items
CREATE TABLE IF NOT EXISTS faq_items (
  id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  property_key TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- System messages (saudacoes, apresentacoes, fallback, etc)
CREATE TABLE IF NOT EXISTS system_messages (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pricing general config (single row)
CREATE TABLE IF NOT EXISTS pricing_config (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  weekend_friday NUMERIC DEFAULT 1.20,
  weekend_saturday NUMERIC DEFAULT 1.25,
  weekend_sunday NUMERIC DEFAULT 1.20,
  high_season_multiplier NUMERIC DEFAULT 2.0,
  high_season_months INTEGER[] DEFAULT '{1,2,7}',
  min_nights_default INTEGER DEFAULT 1,
  min_nights_high_season INTEGER DEFAULT 2,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-property overrides
CREATE TABLE IF NOT EXISTS property_overrides (
  property_key TEXT PRIMARY KEY,
  base_price NUMERIC,
  base_guests INTEGER,
  extra_guest_fee NUMERIC,
  cleaning_fee NUMERIC,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Date-specific pricing multipliers
CREATE TABLE IF NOT EXISTS date_overrides (
  id SERIAL PRIMARY KEY,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  multiplier NUMERIC NOT NULL DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Calendar dates (blocked or force-available)
CREATE TABLE IF NOT EXISTS calendar_dates (
  id SERIAL PRIMARY KEY,
  property_key TEXT NOT NULL,
  date DATE NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('blocked', 'available')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(property_key, date)
);

-- Photo overrides
CREATE TABLE IF NOT EXISTS photo_overrides (
  property_key TEXT PRIMARY KEY,
  categories JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Automatic backups (snapshot before each admin save)
CREATE TABLE IF NOT EXISTS backups (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  label TEXT NOT NULL DEFAULT '',
  snapshot JSONB NOT NULL
);

-- Disable RLS for simplicity (server-side usage)
ALTER TABLE faq_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE system_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE pricing_config DISABLE ROW LEVEL SECURITY;
ALTER TABLE property_overrides DISABLE ROW LEVEL SECURITY;
ALTER TABLE date_overrides DISABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_dates DISABLE ROW LEVEL SECURITY;
ALTER TABLE photo_overrides DISABLE ROW LEVEL SECURITY;
ALTER TABLE backups DISABLE ROW LEVEL SECURITY;

-- Seed: insert default pricing config row
INSERT INTO pricing_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

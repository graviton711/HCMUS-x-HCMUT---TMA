CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS providers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_key CHAR(64) NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    legal_name TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    license_claims TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tours (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_key CHAR(64) NOT NULL UNIQUE,
    provider_id BIGINT NOT NULL REFERENCES providers(id),
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL,
    tour_name TEXT NOT NULL DEFAULT '',
    departure_city TEXT NOT NULL DEFAULT '',
    destinations JSONB NOT NULL DEFAULT '[]',
    route JSONB NOT NULL DEFAULT '[]',
    transport TEXT NOT NULL DEFAULT ''
        CHECK (transport IN ('', 'flight', 'bus', 'train', 'cruise', 'mixed')),
    accommodation TEXT NOT NULL DEFAULT '',
    duration_days INTEGER,
    duration_nights INTEGER,
    price NUMERIC(18, 2),
    currency TEXT NOT NULL DEFAULT 'VND',
    price_type TEXT NOT NULL DEFAULT ''
        CHECK (price_type IN ('', 'fixed', 'from', 'contact')),
    departure_pattern TEXT NOT NULL DEFAULT '',
    itinerary TEXT NOT NULL DEFAULT '',
    inclusions TEXT NOT NULL DEFAULT '',
    exclusions TEXT NOT NULL DEFAULT '',
    cancellation_policy TEXT NOT NULL DEFAULT '',
    surcharges TEXT NOT NULL DEFAULT '',
    child_policy TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'provider_claimed'
        CHECK (verification_status IN ('provider_claimed', 'independently_verified')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tours_provider_departure_idx
    ON tours (provider_id, departure_city, duration_days);

CREATE TABLE IF NOT EXISTS offers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_key CHAR(64) NOT NULL UNIQUE,
    tour_id BIGINT NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    departure_date DATE,
    price NUMERIC(18, 2),
    availability TEXT NOT NULL DEFAULT 'unknown'
        CHECK (availability IN ('available', 'sold_out', 'unknown')),
    tour_code TEXT NOT NULL DEFAULT '',
    price_by_age JSONB,
    single_supplement NUMERIC(18, 2),
    flights JSONB,
    pickup_point TEXT NOT NULL DEFAULT '',
    hotel_location TEXT NOT NULL DEFAULT '',
    conditions TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS offers_tour_date_idx
    ON offers (tour_id, departure_date);

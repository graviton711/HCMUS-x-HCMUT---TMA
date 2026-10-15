-- Offer price semantics belong to each departure, never to the parent tour.
ALTER TABLE offers
    ADD COLUMN IF NOT EXISTS price_type TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS supplements TEXT NOT NULL DEFAULT '';

ALTER TABLE offers
    DROP CONSTRAINT IF EXISTS offers_price_type_check;

ALTER TABLE offers
    ADD CONSTRAINT offers_price_type_check
        CHECK (price_type IN ('fixed', 'from', 'contact', 'unknown'));

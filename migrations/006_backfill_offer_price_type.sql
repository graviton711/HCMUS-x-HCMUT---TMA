-- Preserve the legacy tour-level price basis for existing offers after 005.
-- New offer-level values are authoritative and must never be overwritten.
UPDATE offers AS o
SET price_type = t.price_type
FROM tours AS t
WHERE o.tour_id = t.id
  AND o.price_type = 'unknown'
  AND t.price_type IN ('fixed', 'from', 'contact');

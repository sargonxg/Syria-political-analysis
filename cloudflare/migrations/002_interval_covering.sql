-- Additive, idempotent performance migration. No provider records change.
CREATE INDEX IF NOT EXISTS events_country_interval ON events(country_code, date_start, date_end);

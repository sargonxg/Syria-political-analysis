-- policy-research-db/1. Import into a new, empty SQLite/D1 database.
-- The HTTP Worker only issues SELECT statements; importing is an operator action.
PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  description TEXT NOT NULL
);

CREATE TABLE research_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL CHECK (json_valid(value))
) WITHOUT ROWID;

CREATE TABLE datasets (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  version TEXT NOT NULL,
  publisher TEXT NOT NULL,
  url TEXT NOT NULL,
  license TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json))
) WITHOUT ROWID;

CREATE TABLE manifests (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL CHECK (bytes > 0),
  chunks INTEGER NOT NULL CHECK (chunks > 0)
) WITHOUT ROWID;

CREATE TABLE manifest_chunks (
  manifest_id TEXT NOT NULL REFERENCES manifests(id),
  part INTEGER NOT NULL CHECK (part >= 0),
  text TEXT NOT NULL,
  PRIMARY KEY (manifest_id, part)
) WITHOUT ROWID;

CREATE TABLE events (
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(id),
  country_code TEXT NOT NULL,
  event_year INTEGER NOT NULL,
  date_start TEXT NOT NULL,
  date_end TEXT NOT NULL,
  violence_type INTEGER NOT NULL,
  geography_precision INTEGER NOT NULL,
  date_precision INTEGER NOT NULL,
  side_a TEXT NOT NULL,
  side_b TEXT NOT NULL,
  actor_search TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  fatalities_low INTEGER NOT NULL,
  fatalities_best INTEGER NOT NULL,
  fatalities_high INTEGER NOT NULL,
  raw_record_sha256 TEXT NOT NULL,
  record_json TEXT NOT NULL CHECK (json_valid(record_json)),
  CHECK (date_start <= date_end)
);

CREATE TABLE indicators (
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(id),
  country_code TEXT NOT NULL,
  indicator_id TEXT NOT NULL,
  observation_year INTEGER NOT NULL,
  value REAL NOT NULL,
  record_json TEXT NOT NULL CHECK (json_valid(record_json))
);

CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  url TEXT NOT NULL,
  search_text TEXT NOT NULL,
  profile_json TEXT NOT NULL CHECK (json_valid(profile_json))
) WITHOUT ROWID;

CREATE TABLE semantic_lenses (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  namespace TEXT NOT NULL,
  lens_json TEXT NOT NULL CHECK (json_valid(lens_json))
) WITHOUT ROWID;

-- Created before the ready marker is written. No inference or stance is encoded.
CREATE INDEX events_country_date ON events(country_code, date_start DESC, id DESC);
-- Cover interval-count/aggregate predicates without visiting large provider JSON rows.
CREATE INDEX events_country_interval ON events(country_code, date_start, date_end);
CREATE INDEX events_country_year ON events(country_code, event_year);
CREATE INDEX events_country_type_date ON events(country_code, violence_type, date_start DESC, id DESC);
CREATE INDEX events_country_precision_date ON events(country_code, geography_precision, date_start DESC, id DESC);
CREATE INDEX events_side_a ON events(side_a COLLATE NOCASE, country_code);
CREATE INDEX events_side_b ON events(side_b COLLATE NOCASE, country_code);
CREATE INDEX indicators_country_series_year ON indicators(country_code, indicator_id, observation_year DESC, id DESC);
CREATE INDEX sources_type ON sources(type, name);

INSERT INTO schema_migrations(version, description)
VALUES (1, 'Attributed historical observations, source profiles and semantic lenses');

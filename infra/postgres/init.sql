-- ═══════════════════════════════════════════════════════════════════════════
-- TalentOrbit — PostgreSQL Init Script
-- Runs on first database creation only (docker-entrypoint-initdb.d).
--
-- Enables extensions required by Django and the intelligence/search layer.
-- ═══════════════════════════════════════════════════════════════════════════

-- Full-text search (used by SearchVectorField + SearchRank in jobs, accounts, search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID generation (used by compliance app for secure tokens)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Unaccent for accent-insensitive search
CREATE EXTENSION IF NOT EXISTS unaccent;

-- btree_gin for composite GIN indexes (SearchVector + regular fields)
CREATE EXTENSION IF NOT EXISTS btree_gin;

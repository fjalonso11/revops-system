-- Migration: 002_company_enrichments.sql
-- Adds the company_enrichments table for Exa Account Enrichment (Build A)
-- Applied: June 25, 2026

CREATE TABLE IF NOT EXISTS company_enrichments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID REFERENCES companies(id) ON DELETE CASCADE,
    company_name        VARCHAR(255),
    domain              VARCHAR(255),
    summary             TEXT,
    recent_signals      TEXT,
    risk_indicators     TEXT,
    source_urls         TEXT,
    enriched_at         TIMESTAMPTZ DEFAULT NOW(),
    enriched_date       DATE DEFAULT CURRENT_DATE,
    period_days         INT DEFAULT 90
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_enrichments_company_date
    ON company_enrichments(company_id, enriched_date);

CREATE INDEX IF NOT EXISTS idx_enrichments_company_id
    ON company_enrichments(company_id);

CREATE INDEX IF NOT EXISTS idx_enrichments_enriched_at
    ON company_enrichments(enriched_at DESC);
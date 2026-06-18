CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies (HubSpot accounts)
CREATE TABLE IF NOT EXISTS companies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hubspot_id          VARCHAR(50) UNIQUE,
    name                VARCHAR(255) NOT NULL,
    domain              VARCHAR(255),
    industry            VARCHAR(100),
    country             VARCHAR(100),
    city                VARCHAR(100),
    mrr                 DECIMAL(12, 2) DEFAULT 0,
    arr                 DECIMAL(12, 2) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    hubspot_synced_at   TIMESTAMPTZ,
    raw_data            JSONB
);

-- Contacts (HubSpot contacts)
-- lifecycle_stage values: subscriber → lead → marketingqualifiedlead → salesqualifiedlead → opportunity → customer
CREATE TABLE IF NOT EXISTS contacts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hubspot_id              VARCHAR(50) UNIQUE,
    email                   VARCHAR(255),
    first_name              VARCHAR(100),
    last_name               VARCHAR(100),
    company_id              UUID REFERENCES companies(id),
    lifecycle_stage         VARCHAR(60),
    lead_status             VARCHAR(60),
    became_lead_at          TIMESTAMPTZ,
    became_mql_at           TIMESTAMPTZ,
    became_sql_at           TIMESTAMPTZ,
    became_customer_at      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    hubspot_synced_at       TIMESTAMPTZ,
    raw_data                JSONB
);

-- Deals (HubSpot deals) — drives all three revenue metric layers
-- type values: newbusiness | existingbusiness | churn | contraction
CREATE TABLE IF NOT EXISTS deals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hubspot_id          VARCHAR(50) UNIQUE,
    name                VARCHAR(255),
    company_id          UUID REFERENCES companies(id),
    contact_id          UUID REFERENCES contacts(id),
    pipeline            VARCHAR(100),
    stage               VARCHAR(100),
    amount              DECIMAL(12, 2),
    currency            VARCHAR(3) DEFAULT 'USD',
    close_date          DATE,
    is_closed           BOOLEAN DEFAULT FALSE,
    is_won              BOOLEAN DEFAULT FALSE,
    type                VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    hubspot_synced_at   TIMESTAMPTZ,
    raw_data            JSONB
);

-- Computed revenue metrics snapshots (Volume / Velocity / Yield)
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_date   DATE NOT NULL,
    period_days     INT NOT NULL DEFAULT 30,
    layer           VARCHAR(20) NOT NULL,   -- volume | velocity | yield
    metric_name     VARCHAR(100) NOT NULL,
    value           DECIMAL(15, 4),
    currency        VARCHAR(3),
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (snapshot_date, period_days, layer, metric_name)
);

-- Sync operation audit log
CREATE TABLE IF NOT EXISTS sync_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50) NOT NULL,   -- hubspot | stripe | ...
    sync_type       VARCHAR(20) NOT NULL,   -- full | incremental
    status          VARCHAR(20) NOT NULL DEFAULT 'running',  -- running | success | failed
    records_synced  INT DEFAULT 0,
    errors          JSONB,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contacts_lifecycle_stage  ON contacts(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_contacts_company_id       ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_became_customer  ON contacts(became_customer_at);
CREATE INDEX IF NOT EXISTS idx_deals_is_won              ON deals(is_won);
CREATE INDEX IF NOT EXISTS idx_deals_is_closed           ON deals(is_closed);
CREATE INDEX IF NOT EXISTS idx_deals_closed_at           ON deals(closed_at);
CREATE INDEX IF NOT EXISTS idx_deals_type                ON deals(type);
CREATE INDEX IF NOT EXISTS idx_deals_company_id          ON deals(company_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date_layer        ON metrics_snapshots(snapshot_date, layer);
CREATE INDEX IF NOT EXISTS idx_sync_logs_source_status   ON sync_logs(source, status);

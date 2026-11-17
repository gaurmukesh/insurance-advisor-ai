-- Historical claim settlements for analysis. claimants holds the background
-- attributes that rejection outcomes are correlated against; claims holds one
-- row per claim with the insurer's raw remark plus its normalised
-- reason_category (see app/core/claim_reasons.py).
CREATE TABLE IF NOT EXISTS claimants (
    id VARCHAR PRIMARY KEY,
    external_ref VARCHAR(64) NOT NULL UNIQUE,
    age INTEGER,
    gender VARCHAR(10),
    occupation VARCHAR(50),
    annual_income DOUBLE PRECISION,
    city_tier VARCHAR(10),
    state VARCHAR(50),
    pre_existing_conditions BOOLEAN,
    policy_tenure_years DOUBLE PRECISION,
    prior_claims_count INTEGER,
    purchase_channel VARCHAR(30),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    id VARCHAR PRIMARY KEY,
    claim_no VARCHAR(64) NOT NULL UNIQUE,
    claimant_id VARCHAR NOT NULL REFERENCES claimants(id),
    insurer_name VARCHAR(100),
    policy_type VARCHAR(50),
    claim_type VARCHAR(30),
    claim_amount DOUBLE PRECISION NOT NULL,
    settled_amount DOUBLE PRECISION,
    filed_date DATE NOT NULL,
    decision_date DATE,
    status VARCHAR(20) NOT NULL,
    decision_reason_text VARCHAR(1000),
    reason_category VARCHAR(50),
    reason_classified_by VARCHAR(10),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_claims_claimant_id ON claims(claimant_id);
CREATE INDEX IF NOT EXISTS ix_claims_filed_date ON claims(filed_date);
CREATE INDEX IF NOT EXISTS ix_claims_decision_date ON claims(decision_date);
CREATE INDEX IF NOT EXISTS ix_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS ix_claims_reason_category ON claims(reason_category);

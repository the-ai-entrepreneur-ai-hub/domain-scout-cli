-- Database schema for Docker crawler

CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    crawled_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS results (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    url TEXT,
    company_name TEXT,
    legal_form VARCHAR(100),
    street TEXT,
    postal_code VARCHAR(20),
    city VARCHAR(255),
    country VARCHAR(100),
    ceo_names TEXT,
    emails TEXT,
    phone_numbers TEXT,
    fax_numbers TEXT,
    registration_number VARCHAR(100),
    vat_id VARCHAR(100),
    owner_organization TEXT,
    industry TEXT,
    company_size VARCHAR(50),
    service_product_description TEXT,
    social_links TEXT,
    raw_html TEXT,
    extracted_text TEXT,
    whois_registrar TEXT,
    whois_creation_date VARCHAR(50),
    whois_expiration_date VARCHAR(50),
    whois_owner TEXT,
    whois_emails TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, url)
);

CREATE INDEX idx_domains_status ON domains(status);
CREATE INDEX idx_results_domain ON results(domain);

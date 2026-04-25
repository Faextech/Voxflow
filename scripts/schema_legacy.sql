-- ========================================
-- NEXDIAL - SCHEMA BANCO DE DADOS
-- ========================================
-- Banco PostgreSQL com segurança, constraints e auditoria

-- ========================================
-- TABELA 1: EMPRESAS (TENANTS)
-- ========================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cnpj VARCHAR(18) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'free' 
        CHECK (plan IN ('free', 'pro', 'enterprise')),
    twilio_account_sid VARCHAR(255),
    twilio_auth_token VARCHAR(255),
    twilio_number VARCHAR(20),
    status VARCHAR(50) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'suspended', 'inactive')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_cnpj CHECK (cnpj ~ '^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$'),
    CONSTRAINT valid_email CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
    CONSTRAINT valid_name CHECK (length(name) >= 3)
);

CREATE INDEX idx_companies_email ON companies(email);
CREATE INDEX idx_companies_status ON companies(status);
CREATE INDEX idx_companies_plan ON companies(plan);
CREATE INDEX idx_companies_cnpj ON companies(cnpj);

COMMENT ON TABLE companies IS 'Empresas (Tenants) do sistema SaaS NexDial';
COMMENT ON COLUMN companies.plan IS 'Plano de assinatura: free=grátis, pro=profissional, enterprise=empresarial';

-- ========================================
-- TABELA 2: USUÁRIOS
-- ========================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'agent' 
        CHECK (role IN ('super_admin', 'admin', 'agent')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'inactive', 'suspended')),
    is_online BOOLEAN NOT NULL DEFAULT false,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(company_id, email),
    CONSTRAINT valid_email CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
    CONSTRAINT valid_name CHECK (length(name) >= 3),
    CONSTRAINT valid_password CHECK (length(password_hash) >= 60)
);

CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_last_login ON users(last_login_at);

COMMENT ON TABLE users IS 'Usuários das empresas com roles diferenciados';

-- ========================================
-- TABELA 3: CAMPANHAS
-- ========================================
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft' 
        CHECK (status IN ('draft', 'active', 'paused', 'completed', 'archived')),
    created_by INT NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    total_leads INT NOT NULL DEFAULT 0 CHECK (total_leads >= 0),
    leads_answered INT NOT NULL DEFAULT 0 CHECK (leads_answered >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_name CHECK (length(name) >= 3),
    CONSTRAINT leads_consistency CHECK (leads_answered <= total_leads)
);

CREATE INDEX idx_campaigns_company_id ON campaigns(company_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_created_by ON campaigns(created_by);
CREATE INDEX idx_campaigns_created_at ON campaigns(created_at);

COMMENT ON TABLE campaigns IS 'Campanhas de discagem de cada empresa';

-- ========================================
-- TABELA 4: LEADS
-- ========================================
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    campaign_id INT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone1 VARCHAR(20),
    phone2 VARCHAR(20),
    phone3 VARCHAR(20),
    phone4 VARCHAR(20),
    phone5 VARCHAR(20),
    status VARCHAR(50) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'contacted', 'exhausted', 'converted', 'do_not_call')),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_name CHECK (length(name) >= 2),
    CONSTRAINT at_least_one_phone CHECK (
        phone1 IS NOT NULL OR phone2 IS NOT NULL OR 
        phone3 IS NOT NULL OR phone4 IS NOT NULL OR phone5 IS NOT NULL
    ),
    CONSTRAINT valid_email CHECK (
        email IS NULL OR email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
    )
);

CREATE INDEX idx_leads_campaign_id ON leads(campaign_id);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_leads_created_at ON leads(created_at);

COMMENT ON TABLE leads IS 'Leads/Contatos das campanhas para discagem';

-- ========================================
-- TABELA 5: LOG DE CHAMADAS
-- ========================================
CREATE TABLE IF NOT EXISTS call_log (
    id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    campaign_id INT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    lead_id INT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    phone_dialed VARCHAR(20) NOT NULL,
    call_status VARCHAR(50) 
        CHECK (call_status IN ('queued', 'ringing', 'in-progress', 'completed', 'failed', 'no-answer', 'busy', 'machine')),
    call_duration_seconds INT NOT NULL DEFAULT 0 CHECK (call_duration_seconds >= 0),
    call_sid VARCHAR(255) UNIQUE,
    answered_by VARCHAR(50) CHECK (answered_by IN ('human', 'machine', 'voicemail', 'unknown')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_phone CHECK (phone_dialed ~ '^\+?[1-9]\d{1,14}$')
);

CREATE INDEX idx_call_log_company_id ON call_log(company_id);
CREATE INDEX idx_call_log_lead_id ON call_log(lead_id);
CREATE INDEX idx_call_log_user_id ON call_log(user_id);
CREATE INDEX idx_call_log_call_sid ON call_log(call_sid);
CREATE INDEX idx_call_log_created_at ON call_log(created_at);
CREATE INDEX idx_call_log_call_status ON call_log(call_status);

COMMENT ON TABLE call_log IS 'Log detalhado de todas as chamadas realizadas';

-- ========================================
-- TABELA 6: SESSION TOKENS (Revogar tokens)
-- ========================================
CREATE TABLE IF NOT EXISTS session_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    
    CONSTRAINT token_not_empty CHECK (length(token_hash) > 0)
);

CREATE INDEX idx_session_tokens_user_id ON session_tokens(user_id);
CREATE INDEX idx_session_tokens_expires_at ON session_tokens(expires_at);
CREATE INDEX idx_session_tokens_revoked_at ON session_tokens(revoked_at);

COMMENT ON TABLE session_tokens IS 'Tokens JWT com controle de revogação para logout';

-- ========================================
-- TABELA 7: AUDIT LOG (Segurança e Auditoria)
-- ========================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INT,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(50) DEFAULT 'success' CHECK (status IN ('success', 'failure')),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_action CHECK (length(action) > 0)
);

CREATE INDEX idx_audit_log_company_id ON audit_log(company_id);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);

COMMENT ON TABLE audit_log IS 'Auditoria completa de todas as ações do sistema para segurança e compliance';

-- ========================================
-- TRIGGERS (Automação)
-- ========================================

-- Atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para companies
CREATE TRIGGER trigger_companies_update BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Trigger para users
CREATE TRIGGER trigger_users_update BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Trigger para campaigns
CREATE TRIGGER trigger_campaigns_update BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Trigger para leads
CREATE TRIGGER trigger_leads_update BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ========================================
-- VIEWS (Consultas úteis)
-- ========================================

-- View: Estatísticas de campanhas
CREATE OR REPLACE VIEW campaign_stats AS
SELECT 
    c.id,
    c.name,
    c.company_id,
    COUNT(DISTINCT l.id) as total_leads,
    COUNT(DISTINCT CASE WHEN l.status = 'contacted' THEN l.id END) as leads_contacted,
    COUNT(DISTINCT CASE WHEN l.status = 'converted' THEN l.id END) as leads_converted,
    ROUND(
        COUNT(DISTINCT CASE WHEN l.status = 'contacted' THEN l.id END)::numeric / 
        NULLIF(COUNT(DISTINCT l.id), 0) * 100, 2
    ) as contact_rate_percent
FROM campaigns c
LEFT JOIN leads l ON c.id = l.campaign_id
GROUP BY c.id, c.name, c.company_id;

-- View: Estatísticas de agentes
CREATE OR REPLACE VIEW agent_stats AS
SELECT 
    u.id,
    u.name,
    u.company_id,
    COUNT(DISTINCT cl.id) as total_calls,
    COUNT(DISTINCT CASE WHEN cl.answered_by = 'human' THEN cl.id END) as successful_calls,
    AVG(cl.call_duration_seconds) as avg_duration_seconds,
    SUM(cl.call_duration_seconds) as total_duration_seconds
FROM users u
LEFT JOIN call_log cl ON u.id = cl.user_id
WHERE u.role = 'agent'
GROUP BY u.id, u.name, u.company_id;

-- ========================================
-- PERMISSIONS (Segurança)
-- ========================================

-- (Descomentar quando usar PostgreSQL em produção com múltiplos users)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;

-- ========================================
-- FIM DO SCHEMA
-- ========================================
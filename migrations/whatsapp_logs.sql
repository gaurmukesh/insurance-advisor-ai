CREATE TABLE IF NOT EXISTS whatsapp_logs (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id),
    policy_id VARCHAR REFERENCES policies(id),
    phone VARCHAR(20) NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    message_body VARCHAR(1000) NOT NULL,
    wa_message_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    sent_at TIMESTAMP DEFAULT NOW()
);

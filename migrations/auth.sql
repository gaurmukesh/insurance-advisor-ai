-- Auth: password-based advisor login.
ALTER TABLE advisors ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

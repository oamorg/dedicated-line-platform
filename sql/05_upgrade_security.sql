-- New installs also use this table via the release schema builder.
CREATE TABLE IF NOT EXISTS auth_login_limits (
  bucket_key CHAR(64) PRIMARY KEY,
  attempts INT NOT NULL,
  reset_at BIGINT NOT NULL,
  INDEX idx_login_limits_expiry (reset_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @ddl = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_users' AND COLUMN_NAME = 'auth_version') = 0, 'ALTER TABLE auth_users ADD COLUMN auth_version BIGINT NOT NULL DEFAULT 0', 'SELECT 1');
PREPARE security_stmt FROM @ddl;
EXECUTE security_stmt;
DEALLOCATE PREPARE security_stmt;
SET @ddl = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_sessions' AND COLUMN_NAME = 'auth_version') = 0, 'ALTER TABLE auth_sessions ADD COLUMN auth_version BIGINT NOT NULL DEFAULT 0', 'SELECT 1');
PREPARE security_stmt FROM @ddl;
EXECUTE security_stmt;
DEALLOCATE PREPARE security_stmt;

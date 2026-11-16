-- No seeded settings: an empty rules table uses the documented application defaults.
CREATE TABLE IF NOT EXISTS auth_login_rules (
  id TINYINT PRIMARY KEY,
  window_seconds INT NOT NULL,
  account_limit INT NOT NULL,
  ip_limit INT NOT NULL,
  version BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_ip_blocks (
  ip_address VARCHAR(45) PRIMARY KEY,
  expires_at BIGINT NOT NULL,
  blocked_at BIGINT NOT NULL,
  blocked_by BIGINT NULL,
  reason VARCHAR(255) NOT NULL,
  revision CHAR(32) NOT NULL,
  INDEX idx_ip_blocks_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

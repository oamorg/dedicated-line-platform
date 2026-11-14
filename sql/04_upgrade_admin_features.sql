SET @db = DATABASE();

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE auth_sessions ADD COLUMN ip_address VARCHAR(64) NULL AFTER token_hash',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @db
    AND table_name = 'auth_sessions'
    AND column_name = 'ip_address'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE auth_sessions ADD COLUMN user_agent VARCHAR(255) NULL AFTER ip_address',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @db
    AND table_name = 'auth_sessions'
    AND column_name = 'user_agent'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS admin_operation_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  actor_user_id BIGINT NULL,
  actor_username VARCHAR(64) NULL,
  action_code VARCHAR(64) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id BIGINT NULL,
  target_label VARCHAR(255) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'SUCCESS',
  detail_json JSON NULL,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_admin_logs_created_at (created_at),
  INDEX idx_admin_logs_actor_created (actor_user_id, created_at),
  INDEX idx_admin_logs_action_created (action_code, created_at),
  INDEX idx_admin_logs_target (target_type, target_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

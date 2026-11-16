CREATE TABLE IF NOT EXISTS import_batches (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_name VARCHAR(128) NOT NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  status VARCHAR(16) NOT NULL,
  files_total INT NOT NULL DEFAULT 0,
  rows_processed INT NOT NULL DEFAULT 0,
  rows_affected INT NOT NULL DEFAULT 0,
  rows_failed INT NOT NULL DEFAULT 0,
  message TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_import_batches_status_started_at (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer_line_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  row_hash CHAR(32) NOT NULL,
  import_batch_id BIGINT NULL,

  source_type VARCHAR(32) NOT NULL,
  source_file VARCHAR(128) NOT NULL,
  source_sheet VARCHAR(128) NOT NULL,
  source_row_number INT NULL,
  source_record_id VARCHAR(64) NULL,

  line_name VARCHAR(255) NULL,
  area VARCHAR(64) NULL,
  check_status VARCHAR(64) NULL,
  check_info VARCHAR(255) NULL,
  topology_complete VARCHAR(32) NULL,

  customer_city VARCHAR(64) NULL,
  customer_group_code VARCHAR(64) NULL,
  customer_name VARCHAR(255) NULL,
  customer_type VARCHAR(64) NULL,

  service_city VARCHAR(64) NULL,
  related_city VARCHAR(128) NULL,

  product_number VARCHAR(64) NULL,
  schedule_product_number VARCHAR(64) NULL,
  product_instance_code VARCHAR(64) NULL,
  product_type_code VARCHAR(32) NULL,
  product_type VARCHAR(64) NULL,
  sub_product_type VARCHAR(64) NULL,

  order_no VARCHAR(64) NULL,
  order_type VARCHAR(64) NULL,
  open_time DATETIME NULL,
  service_status VARCHAR(64) NULL,
  workflow_status VARCHAR(64) NULL,
  assurance_level VARCHAR(64) NULL,
  acceptance_status VARCHAR(64) NULL,

  contact_name VARCHAR(128) NULL,
  contact_phone VARCHAR(64) NULL,
  bandwidth VARCHAR(64) NULL,
  upstream_bandwidth VARCHAR(64) NULL,
  downstream_bandwidth VARCHAR(64) NULL,
  purpose_desc TEXT NULL,

  access_method VARCHAR(128) NULL,
  transmission_circuit_name TEXT NULL,
  optical_path_name TEXT NULL,
  svlan VARCHAR(64) NULL,
  cvlan VARCHAR(64) NULL,

  client_county VARCHAR(64) NULL,
  client_room_address VARCHAR(255) NULL,
  client_device_name VARCHAR(255) NULL,
  client_device_port VARCHAR(255) NULL,

  olt_device_name VARCHAR(255) NULL,
  olt_port_name VARCHAR(255) NULL,
  onu_device_name VARCHAR(255) NULL,
  onu_port_name VARCHAR(255) NULL,

  building_code VARCHAR(64) NULL,
  building_name VARCHAR(255) NULL,

  data_source VARCHAR(64) NULL,
  source_channel VARCHAR(64) NULL,
  business_tag VARCHAR(64) NULL,
  marketing_group_id VARCHAR(64) NULL,
  marketing_group_name VARCHAR(128) NULL,

  raw_data JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_customer_line_row_hash (row_hash),
  INDEX idx_line_customer_name (customer_name),
  INDEX idx_line_product_number (product_number),
  INDEX idx_line_area (area),
  INDEX idx_line_product_type (product_type),
  INDEX idx_line_open_time (open_time),
  INDEX idx_line_service_status (service_status),
  INDEX idx_line_source_type (source_type),
  INDEX idx_line_query_combo_1 (source_type, area, open_time),
  INDEX idx_line_query_combo_2 (source_type, product_number),
  INDEX idx_line_batch_id (import_batch_id),
  CONSTRAINT fk_line_import_batch FOREIGN KEY (import_batch_id) REFERENCES import_batches(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS onu_inventory (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  row_hash CHAR(32) NOT NULL,
  import_batch_id BIGINT NULL,

  source_file VARCHAR(128) NOT NULL,
  source_sheet VARCHAR(128) NOT NULL,
  source_row_number INT NULL,

  onuid VARCHAR(64) NULL,
  onu_city VARCHAR(64) NULL,
  onu_name VARCHAR(255) NULL,
  model VARCHAR(64) NULL,
  device_type VARCHAR(64) NULL,
  onu_vendor VARCHAR(64) NULL,
  auth_mode VARCHAR(64) NULL,
  sn_code VARCHAR(128) NULL,
  onu_password VARCHAR(128) NULL,
  olt_mgmt_ip VARCHAR(64) NULL,
  olt_city VARCHAR(64) NULL,
  olt_vendor VARCHAR(64) NULL,
  ponid VARCHAR(64) NULL,
  product_number VARCHAR(64) NULL,
  customer_name VARCHAR(255) NULL,
  service_type VARCHAR(64) NULL,
  client_county VARCHAR(64) NULL,

  raw_data JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_onu_row_hash (row_hash),
  INDEX idx_onu_onuid (onuid),
  INDEX idx_onu_product_number (product_number),
  INDEX idx_onu_customer_name (customer_name),
  INDEX idx_onu_service_type (service_type),
  INDEX idx_onu_client_county (client_county),
  INDEX idx_onu_query_combo_1 (service_type, client_county),
  INDEX idx_onu_query_combo_2 (service_type, product_number),
  INDEX idx_onu_batch_id (import_batch_id),
  CONSTRAINT fk_onu_import_batch FOREIGN KEY (import_batch_id) REFERENCES import_batches(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS import_errors (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT NOT NULL,
  source_file VARCHAR(128) NOT NULL,
  source_sheet VARCHAR(128) NULL,
  source_row_number INT NULL,
  error_message VARCHAR(1000) NOT NULL,
  raw_data JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_import_errors_batch_id (batch_id),
  CONSTRAINT fk_import_errors_batch FOREIGN KEY (batch_id) REFERENCES import_batches(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL UNIQUE,
  display_name VARCHAR(128) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  auth_version BIGINT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_login_limits (
  bucket_key CHAR(64) PRIMARY KEY,
  attempts INT NOT NULL,
  reset_at BIGINT NOT NULL,
  INDEX idx_login_limits_expiry (reset_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

CREATE TABLE IF NOT EXISTS auth_roles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_permissions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_user_roles (
  user_id BIGINT NOT NULL,
  role_id BIGINT NOT NULL,
  assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, role_id),
  CONSTRAINT fk_auth_user_roles_user FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_auth_user_roles_role FOREIGN KEY (role_id) REFERENCES auth_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_role_permissions (
  role_id BIGINT NOT NULL,
  permission_id BIGINT NOT NULL,
  assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id, permission_id),
  CONSTRAINT fk_auth_role_permissions_role FOREIGN KEY (role_id) REFERENCES auth_roles(id) ON DELETE CASCADE,
  CONSTRAINT fk_auth_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES auth_permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_sessions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,
  auth_version BIGINT NOT NULL DEFAULT 0,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(255) NULL,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auth_sessions_user_id (user_id),
  INDEX idx_auth_sessions_expires_at (expires_at),
  CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

INSERT INTO auth_permissions (code, description)
VALUES
  ('data.query', '查询业务数据权限'),
  ('data.export', '导出业务数据权限'),
  ('user.manage', '用户角色管理权限')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO auth_roles (name, description)
VALUES
  ('viewer', '仅查询权限'),
  ('exporter', '查询和导出权限'),
  ('admin', '管理员权限')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'viewer' AND p.code = 'data.query';

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'exporter' AND p.code = 'data.query';

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'exporter' AND p.code = 'data.export';

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'admin' AND p.code = 'data.query';

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'admin' AND p.code = 'data.export';

INSERT IGNORE INTO auth_role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM auth_roles r JOIN auth_permissions p
WHERE r.name = 'admin' AND p.code = 'user.manage';

-- No users or shared password hashes are seeded.
-- Create the first administrator using scripts/manage_users.py create-user.

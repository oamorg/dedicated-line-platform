SET @db = DATABASE();

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE customer_line_records ADD INDEX idx_line_query_combo_1 (source_type, area, open_time)',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = @db
    AND table_name = 'customer_line_records'
    AND index_name = 'idx_line_query_combo_1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE customer_line_records ADD INDEX idx_line_query_combo_2 (source_type, product_number)',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = @db
    AND table_name = 'customer_line_records'
    AND index_name = 'idx_line_query_combo_2'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE onu_inventory ADD INDEX idx_onu_query_combo_1 (service_type, client_county)',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = @db
    AND table_name = 'onu_inventory'
    AND index_name = 'idx_onu_query_combo_1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE onu_inventory ADD INDEX idx_onu_query_combo_2 (service_type, product_number)',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = @db
    AND table_name = 'onu_inventory'
    AND index_name = 'idx_onu_query_combo_2'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

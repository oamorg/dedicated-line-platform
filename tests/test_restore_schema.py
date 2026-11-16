import gzip
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import backup as b
import restore_verify as r

SQL = (b'CREATE TABLE `sample` (\n'
       b'  `name` varchar(45) COLLATE utf8mb4_unicode_ci NOT NULL,\n'
       b'  PRIMARY KEY (`name`)\n'
       b') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;\n'
       b"INSERT INTO `sample` VALUES ('value');\n"
       b'-- Dump completed on 2026-11-16 00:00:00\n')


class RestoreSchemaTests(unittest.TestCase):
    def compare(self, changed):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'source.gz', Path(folder)/'target.gz'
            for path, value in [(source,SQL),(target,changed)]:
                with gzip.open(path,'wb') as out: out.write(value)
            return r.compare_restore(source,target,b.inspect_dump(source),b.inspect_dump(target),{'sample':1})

    def test_identical_schema_passes(self):
        self.assertTrue(self.compare(SQL)['all_schema_and_data_sha256_equal'])

    def test_redundant_column_charset_passes_but_is_reported(self):
        result=self.compare(SQL.replace(b'varchar(45) COLLATE',b'varchar(45) CHARACTER SET utf8mb4 COLLATE'))
        self.assertFalse(result['all_schema_and_data_sha256_equal'])
        self.assertTrue(result['all_data_sha256_equal'])
        self.assertEqual(result['redundant_charset_declaration_tables'],['sample'])

    def test_changed_data_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b"('value')",b"('other')"))

    def test_changed_collation_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b'utf8mb4_unicode_ci',b'utf8mb4_bin'))

    def test_changed_charset_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b'varchar(45) COLLATE',b'varchar(45) CHARACTER SET latin1 COLLATE'))

    def test_changed_length_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b'varchar(45)',b'varchar(46)'))

    def test_changed_nullability_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b'NOT NULL',b'DEFAULT NULL'))

    def test_changed_index_rejected(self):
        with self.assertRaises(b.BackupError): self.compare(SQL.replace(b'PRIMARY KEY',b'UNIQUE KEY'))

    def test_default_literal_not_normalized(self):
        # An identical-looking string in a default is data, not column syntax.
        with self.assertRaises(b.BackupError):
            self.compare(SQL.replace(b'NOT NULL',b"NOT NULL DEFAULT ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'"))


if __name__ == '__main__': unittest.main()

"""Unit tests always use an isolated SQLite engine, never deployment dotenv."""
import os

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['PBKDF2_ITERATIONS'] = '240000'
os.environ['SESSION_TTL_HOURS'] = '12'
os.environ.pop('IMPORT_DATA_DIR', None)

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN=python3
VENV_DIR=""
INSTALL_DEPS=1
APPLY_SCHEMA=1
APPLY_INDEX=1
DATA_DIR=""
usage() {
  cat <<'USAGE'
Usage: ./deploy.sh [--app-dir DIR] [--python BIN] [--venv DIR]
                   [--skip-deps] [--skip-schema] [--skip-index-upgrade]
                   [--import-data DIR]
Creates the Python environment, applies SQL and checks database connectivity.
Does not create users or start a network listener.
USAGE
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-dir|--python|--venv|--import-data)
      [[ $# -ge 2 && -n "$2" ]] || { usage; exit 2; }
      case "$1" in
        --app-dir) APP_DIR="$2" ;;
        --python) PYTHON_BIN="$2" ;;
        --venv) VENV_DIR="$2" ;;
        --import-data) DATA_DIR="$2" ;;
      esac
      shift 2 ;;
    --skip-deps) INSTALL_DEPS=0; shift ;;
    --skip-schema) APPLY_SCHEMA=0; shift ;;
    --skip-index-upgrade) APPLY_INDEX=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
cd "$APP_DIR"
APP_DIR="$PWD"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  printf '%s\n' 'Created .env. Configure DATABASE_URL and run again.'
  exit 1
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  "$VENV_DIR/bin/python" -m pip install -r requirements.txt
fi
# Parse dotenv as data, never source it as shell code.
SQL_FILES=()
[[ "$APPLY_SCHEMA" -eq 0 ]] || SQL_FILES+=(sql/01_schema.sql)
[[ "$APPLY_INDEX" -eq 0 ]] || SQL_FILES+=(sql/02_upgrade_perf_indexes.sql)
SQL_FILES+=(sql/03_upgrade_long_text_columns.sql sql/04_upgrade_admin_features.sql)
"$VENV_DIR/bin/python" scripts/init_db.py "${SQL_FILES[@]}"
if [[ -n "$DATA_DIR" ]]; then
  "$VENV_DIR/bin/python" scripts/import_excel.py --data-dir "$DATA_DIR"
fi
"$VENV_DIR/bin/python" -c 'from app.main import app; assert app.openapi()["paths"]; print("Application imports and schema generation OK")'
printf '%s\n' 'Deployment preparation complete. Create an administrator before starting the server:'
printf '  %q scripts/manage_users.py create-user --username admin --display-name Administrator --role admin\n' "$VENV_DIR/bin/python"
printf '  %q -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n' "$VENV_DIR/bin/python"

#!/usr/bin/env sh
set -eu

mkdir -p data logs

if [ "${KAU_REFRESH_ON_START:-false}" = "true" ] || [ ! -f "data/search_index.joblib" ]; then
  echo "Search index is missing or refresh requested. Crawling website..."
  if ! python -m kau_can_bot refresh --max-pages "${KAU_MAX_PAGES:-1000}"; then
    echo "Website refresh failed. Starting API with current index state."
  fi
fi

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"

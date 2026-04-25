#!/usr/bin/with-contenv bashio
set -euo pipefail

bashio::log.info "Starting Slovak Energy Prices add-on"
exec python3 /usr/local/bin/app.py

#!/usr/bin/env bash
# ==============================================================================
#  Media Server Stack — Wiring Script (Step 2)
#  Connects all services together after `docker compose up -d`.
#
#  Prerequisites before running this script:
#    1. All containers must be running (docker compose up -d)
#
#  Usage:
#    chmod +x config.sh
#    ./config.sh
#
#  Requirements:
#    curl and jq — sudo apt install -y curl jq
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
#  Load .env
# ------------------------------------------------------------------------------

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill it in."
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

SERVER_IP="${SERVER_IP:-localhost}"
QBIT_USER="${QBIT_USER:-admin}"

# ------------------------------------------------------------------------------
#  Colours and helpers
# ------------------------------------------------------------------------------

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

wait_for() {
    local name="$1"
    local url="$2"
    local attempts=0
    local max=30

    info "Waiting for $name..."
    until curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null \
          | grep -qE '^(200|401|403)$'; do
        attempts=$((attempts + 1))
        [ "$attempts" -ge "$max" ] && error "$name did not respond. Check: docker logs ${name,,}"
        sleep 3
    done
    success "$name is ready"
}

read_api_key() {
    local config_file="$1"
    local attempts=0
    local max=20

    until [ -f "$config_file" ]; do
        attempts=$((attempts + 1))
        [ "$attempts" -ge "$max" ] && error "Config not found: $config_file"
        sleep 3
    done

    grep -oP '(?<=<ApiKey>)[^<]+' "$config_file"
}

# ------------------------------------------------------------------------------
#  Preflight
# ------------------------------------------------------------------------------

echo ""
echo "======================================"
echo "  Media Server Stack — Wiring"
echo "======================================"
echo ""

# ------------------------------------------------------------------------------
#  Wait for all services
# ------------------------------------------------------------------------------

echo ""
info "Waiting for all services to be ready..."
wait_for "Prowlarr"    "http://${SERVER_IP}:${PROWLARR_PORT}/login"
wait_for "Sonarr"      "http://${SERVER_IP}:${SONARR_PORT}/login"
wait_for "Radarr"      "http://${SERVER_IP}:${RADARR_PORT}/login"
wait_for "qBittorrent" "http://${SERVER_IP}:${QBIT_PORT}"
wait_for "Bazarr"      "http://${SERVER_IP}:${BAZARR_PORT}"

# ------------------------------------------------------------------------------
#  Resolve qBittorrent password
# ------------------------------------------------------------------------------

echo ""
info "Resolving qBittorrent password..."

info "QBIT_PASS not set — reading temporary password from container logs..."

attempts=0
max=20
QBIT_PASS=""
until [ -n "$QBIT_PASS" ]; do
    QBIT_PASS=$(docker logs qbittorrent 2>&1 \
        | grep -oP '(?<=temporary password is provided for this session: )\S+' \
        | tail -1 || true)
    attempts=$((attempts + 1))
    [ "$attempts" -ge "$max" ] && error "Could not find temporary password in qBittorrent logs."
    [ -z "$QBIT_PASS" ] && sleep 3
done

success "Temporary password found: ${QBIT_PASS}"

QB_STATUS=$(curl -sf \
    -o /dev/null \
    -w "%{http_code}" \
    -c /tmp/qbit_cookies.txt \
    -H "Referer: http://${SERVER_IP}:${QBIT_PORT}" \
    -H "Origin: http://${SERVER_IP}:${QBIT_PORT}" \
    --data-urlencode "username=${QBIT_USER}" \
    --data-urlencode "password=${QBIT_PASS}" \
    "http://${SERVER_IP}:${QBIT_PORT}/api/v2/auth/login" || echo "000")

if [[ "$QB_STATUS" != "200" && "$QB_STATUS" != "204" ]]; then
    echo ""
    warn "qBittorrent returned HTTP ${QB_STATUS} (expected 200 or 204)"
    [ "$QB_STATUS" = "401" ] && warn "IP may be temporarily banned. Restart qbittorrent container and try again."
    error "qBittorrent authentication failed. Check QBIT_USER and QBIT_PASS in .env"
fi

success "qBittorrent authenticated"

# ------------------------------------------------------------------------------
#  Read *arr API keys
# ------------------------------------------------------------------------------

echo ""
info "Reading API keys..."

SONARR_KEY=$(read_api_key "${SONARR_CONFIG}/config.xml")
success "Sonarr:   ${SONARR_KEY:0:8}..."

RADARR_KEY=$(read_api_key "${RADARR_CONFIG}/config.xml")
success "Radarr:   ${RADARR_KEY:0:8}..."

PROWLARR_KEY=$(read_api_key "${PROWLARR_CONFIG}/config.xml")
success "Prowlarr: ${PROWLARR_KEY:0:8}..."

# ------------------------------------------------------------------------------
#  Connect qBittorrent to Sonarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting qBittorrent to Sonarr..."

RESULT=$(curl -sf -X POST \
    "http://${SERVER_IP}:${SONARR_PORT}/api/v3/downloadclient" \
    -H "X-Api-Key: ${SONARR_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"qBittorrent\",
        \"implementation\": \"QBittorrent\",
        \"configContract\": \"QBittorrentSettings\",
        \"enable\": true,
        \"protocol\": \"torrent\",
        \"priority\": 1,
        \"fields\": [
            {\"name\": \"host\",       \"value\": \"qbittorrent\"},
            {\"name\": \"port\",       \"value\": ${QBIT_PORT}},
            {\"name\": \"username\",   \"value\": \"${QBIT_USER}\"},
            {\"name\": \"password\",   \"value\": \"${QBIT_PASS}\"},
            {\"name\": \"tvCategory\", \"value\": \"tv-sonarr\"}
        ]
    }" 2>/dev/null || echo "")

if echo "$RESULT" | jq -e '.id' &>/dev/null; then
    success "qBittorrent connected to Sonarr"
else
    warn "qBittorrent may already be connected to Sonarr — skipping"
fi

# ------------------------------------------------------------------------------
#  Connect qBittorrent to Radarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting qBittorrent to Radarr..."

RESULT=$(curl -sf -X POST \
    "http://${SERVER_IP}:${RADARR_PORT}/api/v3/downloadclient" \
    -H "X-Api-Key: ${RADARR_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"qBittorrent\",
        \"implementation\": \"QBittorrent\",
        \"configContract\": \"QBittorrentSettings\",
        \"enable\": true,
        \"protocol\": \"torrent\",
        \"priority\": 1,
        \"fields\": [
            {\"name\": \"host\",          \"value\": \"qbittorrent\"},
            {\"name\": \"port\",          \"value\": ${QBIT_PORT}},
            {\"name\": \"username\",      \"value\": \"${QBIT_USER}\"},
            {\"name\": \"password\",      \"value\": \"${QBIT_PASS}\"},
            {\"name\": \"movieCategory\", \"value\": \"radarr\"}
        ]
    }" 2>/dev/null || echo "")

if echo "$RESULT" | jq -e '.id' &>/dev/null; then
    success "qBittorrent connected to Radarr"
else
    warn "qBittorrent may already be connected to Radarr — skipping"
fi

# ------------------------------------------------------------------------------
#  Connect Prowlarr to Sonarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting Prowlarr to Sonarr..."

RESULT=$(curl -sf -X POST \
    "http://${SERVER_IP}:${PROWLARR_PORT}/api/v1/applications" \
    -H "X-Api-Key: ${PROWLARR_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Sonarr\",
        \"implementation\": \"Sonarr\",
        \"configContract\": \"SonarrSettings\",
        \"syncLevel\": \"fullSync\",
        \"fields\": [
            {\"name\": \"prowlarrUrl\",    \"value\": \"http://prowlarr:${PROWLARR_PORT}\"},
            {\"name\": \"baseUrl\",        \"value\": \"http://sonarr:${SONARR_PORT}\"},
            {\"name\": \"apiKey\",         \"value\": \"${SONARR_KEY}\"},
            {\"name\": \"syncCategories\", \"value\": [5000, 5010, 5020, 5030, 5040, 5045, 5050]}
        ]
    }" 2>/dev/null || echo "")

if echo "$RESULT" | jq -e '.id' &>/dev/null; then
    success "Prowlarr connected to Sonarr"
else
    warn "Prowlarr may already be connected to Sonarr — skipping"
fi

# ------------------------------------------------------------------------------
#  Connect Prowlarr to Radarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting Prowlarr to Radarr..."

RESULT=$(curl -sf -X POST \
    "http://${SERVER_IP}:${PROWLARR_PORT}/api/v1/applications" \
    -H "X-Api-Key: ${PROWLARR_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Radarr\",
        \"implementation\": \"Radarr\",
        \"configContract\": \"RadarrSettings\",
        \"syncLevel\": \"fullSync\",
        \"fields\": [
            {\"name\": \"prowlarrUrl\",    \"value\": \"http://prowlarr:${PROWLARR_PORT}\"},
            {\"name\": \"baseUrl\",        \"value\": \"http://radarr:${RADARR_PORT}\"},
            {\"name\": \"apiKey\",         \"value\": \"${RADARR_KEY}\"},
            {\"name\": \"syncCategories\", \"value\": [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070, 2080]}
        ]
    }" 2>/dev/null || echo "")

if echo "$RESULT" | jq -e '.id' &>/dev/null; then
    success "Prowlarr connected to Radarr"
else
    warn "Prowlarr may already be connected to Radarr — skipping"
fi

# ------------------------------------------------------------------------------
#  Configure Sonarr root folders
# ------------------------------------------------------------------------------

echo ""
info "Configuring Sonarr root folders..."

for folder in "/media/tvshows" "/media/anime"; do
    RESULT=$(curl -sf -X POST \
        "http://${SERVER_IP}:${SONARR_PORT}/api/v3/rootfolder" \
        -H "X-Api-Key: ${SONARR_KEY}" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"${folder}\"}" \
        2>/dev/null || echo "")

    if echo "$RESULT" | jq -e '.id' &>/dev/null; then
        success "Sonarr root folder added: ${folder}"
    else
        warn "Sonarr root folder may already exist: ${folder} — skipping"
    fi
done

# ------------------------------------------------------------------------------
#  Configure Radarr root folder
# ------------------------------------------------------------------------------

echo ""
info "Configuring Radarr root folder..."

RESULT=$(curl -sf -X POST \
    "http://${SERVER_IP}:${RADARR_PORT}/api/v3/rootfolder" \
    -H "X-Api-Key: ${RADARR_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"path\": \"/media/movies\"}" \
    2>/dev/null || echo "")

if echo "$RESULT" | jq -e '.id' &>/dev/null; then
    success "Radarr root folder added: /media/movies"
else
    warn "Radarr root folder may already exist: /media/movies — skipping"
fi

# ------------------------------------------------------------------------------
#  Connect Bazarr to Sonarr and Radarr
#  Bazarr has no settings API — we patch its config.yaml directly and
#  restart the container so it boots with the correct connection details.
# ------------------------------------------------------------------------------

echo ""
info "Configuring Bazarr to Sonarr and Radarr connections..."

BAZARR_YAML="${BAZARR_CONFIG}/config/config.yaml"

[ -f "$BAZARR_YAML" ] || error "Bazarr config not found at ${BAZARR_YAML}. Is the bazarr container running?"

sed -i \
    -e 's/^  use_sonarr:.*/  use_sonarr: true/' \
    -e 's/^  use_radarr:.*/  use_radarr: true/' \
    "$BAZARR_YAML"

sed -i "/^sonarr:/,/^[a-z]/{
    s|^  ip:.*|  ip: sonarr|
    s|^  apikey:.*|  apikey: ${SONARR_KEY}|
    s|^  port:.*|  port: ${SONARR_PORT}|
    s|^  base_url:.*|  base_url: ''|
}" "$BAZARR_YAML"

sed -i "/^radarr:/,/^[a-z]/{
    s|^  ip:.*|  ip: radarr|
    s|^  apikey:.*|  apikey: ${RADARR_KEY}|
    s|^  port:.*|  port: ${RADARR_PORT}|
    s|^  base_url:.*|  base_url: ''|
}" "$BAZARR_YAML"

docker restart bazarr > /dev/null
wait_for "Bazarr" "http://${SERVER_IP}:${BAZARR_PORT}"
success "Bazarr connected to Sonarr and Radarr"

# ------------------------------------------------------------------------------
#  Done
# ------------------------------------------------------------------------------

echo ""
echo "======================================"
echo "  Configuration Complete"
echo "======================================"
echo ""
echo "  Remaining manual steps:"
echo ""
echo "  1. Add indexers in Prowlarr"
echo "     and Radarr automatically:"
echo "     http://${SERVER_IP}:${PROWLARR_PORT} > Indexers > Add Indexer"
echo ""
echo "  2. Add subtitle providers in Bazarr:"
echo "     http://${SERVER_IP}:${BAZARR_PORT}"
echo "     Settings > Providers > Add Provider"
echo "     Recommended: OpenSubtitles (free account required)"
echo "     For anime: also add Animetosho"
echo ""
echo "  3. Setup Shoko Server:"
echo "     http://${SERVER_IP}:${SHOKO_PORT}"
echo ""
echo "======================================"
echo ""
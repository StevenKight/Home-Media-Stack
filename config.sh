#!/usr/bin/env bash
# ==============================================================================
#  Media Server Stack — Wiring Script (Step 2)
#  Connects all services together after `docker compose up -d`.
#
#  Prerequisites before running this script:
#    1. All containers must be running (docker compose up -d)
#    2. Jellyfin first-run setup must be complete in the browser:
#       http://<server-ip>:JELLYFIN_PORT
#    3. JELLYFIN_USER and JELLYFIN_PASS must be set in .env
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

for cmd in curl jq; do
    command -v "$cmd" &>/dev/null || error "$cmd is required. Run: sudo apt install -y curl jq"
done

if [ -z "${JELLYFIN_PASS:-}" ]; then
    error "JELLYFIN_PASS is not set in .env. Complete the Jellyfin setup wizard first:
    http://localhost:${JELLYFIN_PORT}
  Then add your password to .env and re-run this script."
fi

# Verify Jellyseerr wizard has been completed by checking if its
# API returns a valid status rather than redirecting to /setup
echo ""
info "Checking Jellyseerr is initialised..."
JSEERR_STATUS=$(docker exec jellyseerr wget -qO- \
    http://localhost:5055/api/v1/status \
    2>/dev/null || echo "")

if echo "$JSEERR_STATUS" | jq -e '.version' &>/dev/null; then
    success "Jellyseerr is initialised"
else
    error "Jellyseerr setup wizard has not been completed.
  Open http://localhost:${JELLYSEERR_PORT}/setup in your browser,
  sign in with your Jellyfin credentials, then re-run this script.
  You can skip the Sonarr/Radarr steps in the wizard —
  this script will handle those automatically."
fi

# ------------------------------------------------------------------------------
#  Wait for all services
# ------------------------------------------------------------------------------

echo ""
info "Waiting for all services to be ready..."
wait_for "Prowlarr"    "http://${SERVER_IP}:${PROWLARR_PORT}/login"
wait_for "Sonarr"      "http://${SERVER_IP}:${SONARR_PORT}/login"
wait_for "Radarr"      "http://${SERVER_IP}:${RADARR_PORT}/login"
wait_for "qBittorrent" "http://${SERVER_IP}:${QBIT_PORT}"
wait_for "Jellyfin"    "http://${SERVER_IP}:${JELLYFIN_PORT}/health"

info "Waiting for Jellyseerr..."
attempts=0
max=30
until docker exec jellyseerr wget -qO- http://localhost:5055/api/v1/status &>/dev/null; do
    attempts=$((attempts + 1))
    [ "$attempts" -ge "$max" ] && error "Jellyseerr did not respond. Check: docker logs jellyseerr"
    sleep 3
done
success "Jellyseerr is ready"

# ------------------------------------------------------------------------------
#  Resolve qBittorrent password
# ------------------------------------------------------------------------------

echo ""
info "Resolving qBittorrent password..."

if [ -n "${QBIT_PASS:-}" ]; then
    info "Using password from .env"
else
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
    echo ""
    warn "This password changes on every restart until you set a permanent one."
    warn "After this script finishes, set a permanent password in qBittorrent:"
    warn "  http://${SERVER_IP}:${QBIT_PORT} > Tools > Options > Web UI > Password"
    warn "Then add it to .env:  QBIT_PASS=yourpassword"
    echo ""
fi

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
#  Authenticate with Jellyfin and get API key
# ------------------------------------------------------------------------------

echo ""
info "Authenticating with Jellyfin..."

JELLYFIN_AUTH=$(curl -sf -X POST \
    "http://${SERVER_IP}:${JELLYFIN_PORT}/Users/AuthenticateByName" \
    -H "Content-Type: application/json" \
    -H 'X-Emby-Authorization: MediaBrowser Client="setup", Device="setup", DeviceId="setup", Version="1.0.0"' \
    -d "{\"Username\": \"${JELLYFIN_USER}\", \"Pw\": \"${JELLYFIN_PASS}\"}" \
    2>/dev/null || echo "")

if [ -z "$JELLYFIN_AUTH" ]; then
    error "Could not authenticate with Jellyfin. Check JELLYFIN_USER and JELLYFIN_PASS in .env"
fi

JELLYFIN_TOKEN=$(echo "$JELLYFIN_AUTH" | jq -r '.AccessToken')

if [ -z "$JELLYFIN_TOKEN" ] || [ "$JELLYFIN_TOKEN" = "null" ]; then
    error "Could not retrieve Jellyfin access token. Check credentials in .env"
fi

success "Jellyfin authenticated"

# Create a named API key for Jellyseerr
JELLYFIN_API_KEY=$(curl -sf -X POST \
    "http://${SERVER_IP}:${JELLYFIN_PORT}/Auth/Keys" \
    -H "Authorization: MediaBrowser Token=\"${JELLYFIN_TOKEN}\"" \
    -H "Content-Type: application/json" \
    2>/dev/null | jq -r '.Key // empty' || echo "")

# Fall back to session token if key endpoint unavailable
JELLYFIN_API_KEY="${JELLYFIN_API_KEY:-$JELLYFIN_TOKEN}"
success "Jellyfin API key obtained: ${JELLYFIN_API_KEY:0:8}..."

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
#  Connect Jellyseerr to Sonarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting Jellyseerr to Sonarr..."

# Retrieve Jellyseerr API key for Sonarr/Radarr connections
JELLYSEERR_KEY=$(docker exec jellyseerr wget -qO- \
    http://localhost:5055/api/v1/settings/main \
    2>/dev/null | jq -r '.apiKey // empty' || echo "")

if [ -n "$JELLYSEERR_KEY" ]; then
    RESULT=$(docker exec jellyseerr wget -qO- \
        --post-data="{\"name\": \"Sonarr\", \"hostname\": \"sonarr\", \"port\": ${SONARR_PORT}, \"apiKey\": \"${SONARR_KEY}\", \"useSsl\": false, \"activeProfileId\": 1, \"activeDirectory\": \"/media/tvshows\", \"activeAnimeProfileId\": 1, \"activeAnimeDirectory\": \"/media/anime\", \"isDefault\": true, \"enableSeasonFolders\": true}" \
        --header="Content-Type: application/json" \
        --header="X-Api-Key: ${JELLYSEERR_KEY}" \
        http://localhost:5055/api/v1/settings/sonarr \
        2>/dev/null || echo "")

    if echo "$RESULT" | jq -e '.id' &>/dev/null; then
        success "Jellyseerr connected to Sonarr"
    else
        warn "Jellyseerr may already be connected to Sonarr — skipping"
    fi
else
    warn "Could not retrieve Jellyseerr API key — connect Sonarr manually in Jellyseerr settings"
fi

# ------------------------------------------------------------------------------
#  Connect Jellyseerr to Radarr
# ------------------------------------------------------------------------------

echo ""
info "Connecting Jellyseerr to Radarr..."

if [ -n "$JELLYSEERR_KEY" ]; then
    RESULT=$(docker exec jellyseerr wget -qO- \
        --post-data="{\"name\": \"Radarr\", \"hostname\": \"radarr\", \"port\": ${RADARR_PORT}, \"apiKey\": \"${RADARR_KEY}\", \"useSsl\": false, \"activeProfileId\": 1, \"activeDirectory\": \"/media/movies\", \"isDefault\": true}" \
        --header="Content-Type: application/json" \
        --header="X-Api-Key: ${JELLYSEERR_KEY}" \
        http://localhost:5055/api/v1/settings/radarr \
        2>/dev/null || echo "")

    if echo "$RESULT" | jq -e '.id' &>/dev/null; then
        success "Jellyseerr connected to Radarr"
    else
        warn "Jellyseerr may already be connected to Radarr — skipping"
    fi
else
    warn "Could not retrieve Jellyseerr API key — connect Radarr manually in Jellyseerr settings"
fi

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
echo "  1. Add indexers in Prowlarr — they sync to Sonarr"
echo "     and Radarr automatically:"
echo "     http://${SERVER_IP}:${PROWLARR_PORT} > Indexers > Add Indexer"
echo ""
echo "  2. Set Jellyfin playback preferences (for anime):"
echo "     User Settings > Playback"
echo "     Audio: Japanese | Subtitles: English | Mode: Always"
echo ""
if [ -z "${QBIT_PASS:-}" ]; then
    echo "  3. Set a permanent qBittorrent password then add"
    echo "     QBIT_PASS=yourpassword to your .env file."
    echo ""
fi
echo "======================================"
echo ""
#!/usr/bin/env bash
# ==============================================================================
#  Media Server Stack — Directory Setup (Step 1)
#  Run this before `docker compose up -d`.
#
#  Reads paths from your .env file and creates all required
#  directories with the correct ownership.
#
#  Usage:
#    chmod +x setup.sh
#    ./setup.sh
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
#  Load .env
# ------------------------------------------------------------------------------

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill it in first."
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

SERVER_IP="${SERVER_IP:-localhost}"

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

make_dir() {
    local dir="$1"
    if [ -d "$dir" ]; then
        warn "Already exists: $dir"
    else
        mkdir -p "$dir"
        success "Created: $dir"
    fi
}

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

# ------------------------------------------------------------------------------
#  Preflight
# ------------------------------------------------------------------------------

echo ""
echo "======================================"
echo "  Media Server Stack — Directory Setup"
echo "======================================"
echo ""

[ -z "${PUID:-}" ] && error "PUID is not set in .env"
[ -z "${PGID:-}" ] && error "PGID is not set in .env"

# ------------------------------------------------------------------------------
#  Privilege check — detect whether sudo is needed for directory ops
# ------------------------------------------------------------------------------

if [ "$EUID" -ne 0 ]; then
    _check="${MEDIA_ROOT}"
    while [ ! -d "$_check" ]; do
        _check=$(dirname "$_check")
    done

    if [ ! -w "$_check" ]; then
        error "Cannot write to ${_check} as the current user.
  Re-run this script with elevated permissions:
    sudo ./setup.sh"
    fi
fi

info "Running as PUID=${PUID} PGID=${PGID}"
echo ""

# ------------------------------------------------------------------------------
#  Media directories
# ------------------------------------------------------------------------------

info "Creating media directories..."
make_dir "${MEDIA_ROOT}/movies"
make_dir "${MEDIA_ROOT}/tvshows"
make_dir "${MEDIA_ROOT}/anime"
make_dir "${MEDIA_ROOT}/music"
make_dir "${MEDIA_ROOT}/photos"

# ------------------------------------------------------------------------------
#  Downloads directory
# ------------------------------------------------------------------------------

echo ""
info "Creating downloads directory..."
make_dir "${DOWNLOADS_DIR}"

# ------------------------------------------------------------------------------
#  Service config directories
# ------------------------------------------------------------------------------

echo ""
info "Creating service config directories..."
make_dir "${SONARR_CONFIG}"
make_dir "${RADARR_CONFIG}"
make_dir "${PROWLARR_CONFIG}"
make_dir "${QBIT_CONFIG}"
make_dir "${BAZARR_CONFIG}"

# ------------------------------------------------------------------------------
#  Set ownership on everything
# ------------------------------------------------------------------------------

echo ""
info "Setting ownership to ${PUID}:${PGID}..."

chown -R "${PUID}:${PGID}" \
    "${MEDIA_ROOT}" \
    "${DOWNLOADS_DIR}" \
    "${SONARR_CONFIG}" \
    "${RADARR_CONFIG}" \
    "${PROWLARR_CONFIG}" \
    "${QBIT_CONFIG}" \
    "${BAZARR_CONFIG}"

success "Ownership set"

# ------------------------------------------------------------------------------
#  Build and run containers
# ------------------------------------------------------------------------------

echo ""
docker compose up -d

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
wait_for "Shoko"       "http://${SERVER_IP}:${SHOKO_PORT}"

# ------------------------------------------------------------------------------
#  Done
# ------------------------------------------------------------------------------

echo ""
echo "======================================"
echo "  Directories Ready"
echo "======================================"
echo ""
echo "  Media:"
echo "    ${MEDIA_ROOT}/movies"
echo "    ${MEDIA_ROOT}/tvshows"
echo "    ${MEDIA_ROOT}/anime"
echo "    ${MEDIA_ROOT}/music"
echo "    ${MEDIA_ROOT}/photos"
echo ""
echo "  Downloads:  ${DOWNLOADS_DIR}"
echo ""
echo "  Configs:"
echo "    ${SONARR_CONFIG}"
echo "    ${RADARR_CONFIG}"
echo "    ${PROWLARR_CONFIG}"
echo "    ${QBIT_CONFIG}"
echo "    ${BAZARR_CONFIG}"
echo ""
echo "======================================"
echo "  Containers Ready"
echo "======================================"
echo ""
echo "  Shoko:       http://${SERVER_IP}:${SHOKO_PORT}"
echo "  Bazarr:      http://${SERVER_IP}:${BAZARR_PORT}"
echo "  Sonarr:      http://${SERVER_IP}:${SONARR_PORT}"
echo "  Radarr:      http://${SERVER_IP}:${RADARR_PORT}"
echo "  Prowlarr:    http://${SERVER_IP}:${PROWLARR_PORT}"
echo "  qBittorrent: http://${SERVER_IP}:${QBIT_PORT}"
echo ""
echo "======================================"
echo "  Next Steps"
echo "======================================"
echo ""
echo "    1. ./config.sh"
echo ""
echo "======================================"
echo ""
# Home Media Server Stack

A self-hosted home media server built on Ubuntu Server 24.04 LTS and Docker. Streams movies, TV shows, anime, music, and photos to any device on your local network with no cloud accounts, no telemetry, and no data leaving your home.

Designed for local network use only. No port forwarding or external access required.

---

## Stack Overview

| Service | Purpose | Default Port |
|---|---|---|
| [Jellyfin](https://jellyfin.org) | Media server — stream everything | `:8096` |
| [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) | Discovery, recommendations, and requests | `:5055` |
| [Sonarr](https://sonarr.tv) | TV show and anime library manager | `:8989` |
| [Radarr](https://radarr.video) | Movie library manager | `:7878` |
| [Prowlarr](https://github.com/Prowlarr/Prowlarr) | Indexer manager — syncs sources to Sonarr and Radarr | `:9696` |
| [qBittorrent](https://www.qbittorrent.org) | Torrent download client | `:8081` |
| [Bazarr](https://www.bazarr.media) | Automatic subtitle downloader | `:6767` |

All ports are configurable in `.env`.

---

## Privacy

No service in this stack sends personal data, usage habits, or identifiable information to any external party.

| Service | Telemetry | External Calls | Notes |
|---|---|---|---|
| Jellyfin | None | None | Disable usage stats on first launch |
| Sonarr / Radarr | None | TVDB / TMDB title lookups | IP + title name only |
| Prowlarr | None | Indexer sites for search results | IP + search terms only |
| qBittorrent | None | Torrent peers and trackers | Standard torrent traffic |
| Jellyseerr | None | TMDB for discovery browsing | IP + search terms only |
| Bazarr | None | OpenSubtitles / Animetosho | IP + title name only |

---

## Prerequisites

- A machine running **Ubuntu Server 24.04 LTS** (bare metal, no desktop environment)
- Static IP assigned to the server — via DHCP reservation on your router or set directly on the machine
- Sufficient storage for your media library
- `curl` and `jq` installed: `sudo apt install -y curl jq`

---

## Getting Started

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Log out and back in for the group change to take effect.

### 2. Configure your environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | What to set | How to find it |
|---|---|---|
| `PUID` / `PGID` | Your user and group ID | Run `id` in terminal |
| `TZ` | Your timezone | [Timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| `MEDIA_ROOT` | Where your media storage is mounted | e.g. `/mnt/storage` or `/srv/media` |
| `SERVER_IP` | This machine's local IP address | Run `hostname -I` |

All other values (ports, config paths) have sensible defaults and can be left as-is unless you have conflicts.

### 3. Run the setup script

```bash
chmod +x setup.sh
sudo ./setup.sh
```

This creates all required directories with correct ownership, starts all containers, and waits until every service is ready. It prints URLs and next steps when complete.

### 4. Complete Jellyfin first-run setup

Open Jellyfin in your browser at `http://<server-ip>:8096` and follow the setup wizard. Create your admin account and add your media libraries. Note the password you set.

Then add your credentials to `.env`:

```
JELLYFIN_USER=yourusername
JELLYFIN_PASS=yourpassword
```

### 5. Complete Jellyseerr first-run setup

Open Jellyseerr at `http://<server-ip>:5055/setup` and sign in with your Jellyfin credentials. You can skip the Sonarr and Radarr steps — the wiring script handles those automatically.

### 6. Run the wiring script

```bash
chmod +x config.sh
./config.sh
```

This authenticates with every service and wires them together automatically:

- Connects qBittorrent to Sonarr and Radarr as the download client
- Registers Prowlarr with Sonarr and Radarr for indexer syncing
- Configures root media folders in Sonarr and Radarr
- Links Jellyseerr to Sonarr, Radarr, and Jellyfin

### 7. Verify everything is running

```bash
docker compose ps
```

All services should show `running`. To view logs for a specific service:

```bash
docker compose logs jellyfin
```

---

## Post-Setup Configuration

### Prowlarr — Add indexers

The wiring script connects Prowlarr to Sonarr and Radarr, but you still need to add your indexers. Go to **Indexers > Add Indexer**, search by name, and use the test button before saving. Once saved, Prowlarr pushes them to Sonarr and Radarr automatically — do not add indexers directly in either app.

#### **Public indexers** (no account required):

| Indexer | Best for |
|---|---|
| YTS | Movies — very clean releases |
| EZTV | TV shows |
| The Pirate Bay | Broad coverage of everything |
| 1337x | General — movies, TV, anime |
| Nyaa | Anime — the standard, essentially required |
| TokyoTosho | Anime — secondary source, good for niche titles |

#### **Private trackers** (account required, some invite-only):

| Tracker | Best for |
|---|---|
| BTN (BroadcasTheNet) | TV shows — invite only, considered the best TV tracker |
| PTP (PassThePopcorn) | Movies — invite only, extremely high quality |
| AnimeBytes | Anime — better than Nyaa for older or niche titles, invite only |
| MAM (MyAnonamouse) | Books and audiobooks |

### qBittorrent — Set a permanent password

On first startup, qBittorrent generates a temporary password that changes on every restart. After the wiring script runs:

1. Open qBittorrent at `http://<server-ip>:8081`
2. Go to **Tools > Options > Web UI** and set a permanent password
3. Add it to `.env`: `QBIT_PASS=yourpassword`

### Bazarr — Subtitle provider setup

The wiring script connects Bazarr to Sonarr and Radarr, but subtitle providers require your account credentials and must be added manually.

1. Open Bazarr at `http://<server-ip>:6767`
2. Go to **Settings > Providers** and add at least one provider:
   - **OpenSubtitles.com** — free account required at opensubtitles.com
   - **Animetosho** — no account needed, recommended for anime
3. Go to **Settings > Languages**, create a language profile containing English, and set it as the default for both Series and Movies
4. Go to **Movies** and **Series**, select all existing content, and bulk edit to assign the English profile — this covers content added before the profile was set
5. Go to **System > Tasks** and run **Search for Missing Subtitles** to trigger an immediate download across your library

### Jellyseerr — Requesting content

Users browse and request content through Jellyseerr. Requests flow automatically into Sonarr or Radarr without users needing access to any other service.

---

## Pre-Download Checklist

Before requesting or downloading anything, verify the full pipeline is correctly wired. Work through this once after `config.sh` completes.

### Prowlarr

- Confirm at least one indexer is listed under **Indexers**
- Click the test icon on each indexer to confirm it is reachable
- Go to **Settings > Apps** and confirm Sonarr and Radarr both show green

### Sonarr

- Go to **Settings > Media Management > Root Folders** and confirm `/media/tvshows` and `/media/anime` are listed
- Go to **Settings > Download Clients** and confirm qBittorrent shows green
- Go to **Settings > Indexers** and confirm your Prowlarr indexers have synced through

### Radarr

- Go to **Settings > Media Management > Root Folders** and confirm `/media/movies` is listed
- Go to **Settings > Download Clients** and confirm qBittorrent shows green
- Go to **Settings > Indexers** and confirm your Prowlarr indexers have synced through

### qBittorrent

- Confirm you can log in with your permanent password
- Go to **Tools > Options > Downloads** and confirm the default save path is `/downloads`
- Go to **Tools > Options > Connection** — a red port status means port `6881` is not forwarded on your router, which will significantly reduce download speeds. Forward `6881` TCP and UDP to your server's LAN IP in your router's admin panel.

### Bazarr

- Go to **Settings > Sonarr** and **Settings > Radarr** and click **Test** on both — should return a version number
- Confirm at least one subtitle provider is listed under **Settings > Providers**
- Confirm a language profile is assigned under **Settings > Languages** with defaults set for both Series and Movies
- Confirm your library is populated under **Movies** and **Series**

### Jellyfin

- Confirm all libraries exist and point to the correct folders under **Dashboard > Libraries**
- Run a scan on each library to pick up any existing content
- Go to your profile **Settings > Playback** and set:
  - Preferred audio language: Japanese
  - Preferred subtitle language: English
  - Subtitle mode: Always

### Jellyseerr

- Go to **Settings > Services** and confirm both Sonarr and Radarr show green
- Go to **Settings > Users** and configure request permissions for household members

### End-to-End Test

Run through this once before giving others access:

1. Request a movie in Jellyseerr
2. Confirm it appears in Radarr as Monitored
3. Confirm a download starts in qBittorrent within a few minutes
4. Confirm the file is imported in Radarr once downloaded
5. Confirm the movie appears in Jellyfin
6. Confirm subtitles were downloaded in Bazarr
7. Play the movie in Jellyfin and confirm subtitles appear

If every step passes the full pipeline is working correctly.

---

## Directory Structure

Paths below reflect the defaults in `.env.example`. They can be changed to any location by editing `.env`.

```
/srv/
├── media/
│   ├── movies/          # Radarr output → Jellyfin source
│   ├── tvshows/         # Sonarr output → Jellyfin source
│   ├── anime/           # Sonarr output → Jellyfin source
│   ├── music/           # Jellyfin music library
│   └── photos/          # Jellyfin photo library
├── downloads/           # qBittorrent download folder
├── jellyfin/
│   ├── config/          # Jellyfin config and database
│   └── cache/           # Transcoding cache
├── sonarr/config/
├── radarr/config/
├── prowlarr/config/
├── qbittorrent/config/
├── bazarr/config/
└── jellyseerr/config/
```

---

## Hardware Notes

This stack runs well on modest hardware. Reference build:

- **CPU:** AMD Ryzen 5 5500 (6-core, 12-thread, 4.2GHz boost)
- **RAM:** 16GB DDR4-3200
- **OS Drive:** Any SSD (NVMe recommended)
- **Media Storage:** Any HDD or SSD with sufficient capacity

The Ryzen 5 5500 has no integrated GPU. The `devices: /dev/dri` lines in the Jellyfin section of `docker-compose.yaml` are commented out by default for this reason. The 6-core processor handles software transcoding adequately, and most modern clients on a local network will direct play without triggering transcoding at all.

For machines with an Intel integrated GPU, enable hardware transcoding after starting the stack:

```bash
sudo apt install -y intel-media-va-driver-non-free
sudo usermod -aG render $USER
```

Then in Jellyfin go to **Dashboard > Playback** and enable Intel QSV. Uncomment the `devices` section in `docker-compose.yaml` and restart the Jellyfin container.

---

## Useful Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a single service
docker compose restart jellyfin

# View live logs for a service
docker compose logs -f sonarr

# Pull latest images and restart
docker compose pull && docker compose up -d

# Check resource usage across containers
docker stats
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

You are free to use, modify, and distribute this project, but any derivative work must also be distributed under the same license terms.
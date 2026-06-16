# Home Media Server Stack

> This project is intended for use with legally obtained media. The authors take no responsibility for how the software is used.


A self-hosted home media server built on Ubuntu Server 24.04 LTS and Docker. Automatically finds, downloads, organises, and subtitles movies, TV shows, and anime — fully local, no cloud accounts, no telemetry.

Designed for local network use only. No port forwarding or external access required.

---

## Stack Overview

| Service | Purpose | Default Port |
|---|---|---|
| [Sonarr](https://sonarr.tv) | TV show and anime library manager | `:8989` |
| [Radarr](https://radarr.video) | Movie library manager | `:7878` |
| [Prowlarr](https://github.com/Prowlarr/Prowlarr) | Indexer manager — syncs sources to Sonarr and Radarr | `:9696` |
| [qBittorrent](https://www.qbittorrent.org) | Torrent download client | `:8081` |
| [Bazarr](https://www.bazarr.media) | Automatic subtitle downloader | `:6767` |
| [Shoko Server](https://shokoanime.com) | Anime library manager — AniDB identification and metadata | `:8111` |

All ports are configurable in `.env`.

---

## Privacy

No service in this stack sends personal data, usage habits, or identifiable information to any external party.

| Service | Telemetry | External Calls | Notes |
|---|---|---|---|
| Sonarr / Radarr | None | TVDB / TMDB title lookups | IP + title name only |
| Prowlarr | None | Indexer sites for search results | IP + search terms only |
| qBittorrent | None | Torrent peers and trackers | Standard torrent traffic |
| Bazarr | None | OpenSubtitles / Animetosho | IP + title name only |
| Shoko Server | None | AniDB for anime identification | IP + anime title only |

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

### 3. Deploy

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

This runs the full deployment in one shot:

- Creates all required directories with correct ownership
- Starts all containers and waits until every service is ready
- Authenticates with every service and wires them together:
  - Connects qBittorrent to Sonarr and Radarr as the download client
  - Registers Prowlarr with Sonarr and Radarr for indexer syncing
  - Configures root media folders in Sonarr and Radarr
  - Connects Bazarr to Sonarr and Radarr

### 4. Verify everything is running

```bash
docker compose ps
```

All services should show `running`. To view logs for a specific service:

```bash
docker compose logs -f sonarr
```

---

## Post-Setup Configuration

### Prowlarr — Add indexers

The wiring script connects Prowlarr to Sonarr and Radarr, but you still need to add your indexers. Go to **Indexers > Add Indexer**, search by name, and use the test button before saving. Once saved, Prowlarr pushes them to Sonarr and Radarr automatically — do not add indexers directly in either app.

### Shoko Server — First-run setup

Shoko requires a one-time setup wizard before it can manage your library. Sonarr still handles searching and downloading — Shoko takes over AniDB identification, metadata, and organisation of `/media/anime`.

1. Open Shoko at `http://<server-ip>:8111`
2. Complete the setup wizard — create an admin account and connect to AniDB
3. Go to **Import Folders** and add `/media/anime` as an import folder
4. Trigger an initial scan to let Shoko identify your existing anime library

### Bazarr — Subtitle provider setup

The wiring script connects Bazarr to Sonarr and Radarr, but subtitle providers require your account credentials and must be added manually.

1. Open Bazarr at `http://<server-ip>:6767`
2. Go to **Settings > Providers** and add at least one provider:
   - **OpenSubtitles.com** — free account required at opensubtitles.com
   - **Animetosho** — no account needed, recommended for anime
3. Go to **Settings > Languages**, create a language profile containing English, and set it as the default for both Series and Movies
4. Go to **Movies** and **Series**, select all existing content, and bulk edit to assign the English profile — this covers content added before the profile was set
5. Go to **System > Tasks** and run **Search for Missing Subtitles** to trigger an immediate download across your library

---

## Pre-Download Checklist

Before downloading anything, verify the full pipeline is correctly wired. Work through this once after `./deploy.sh` completes.

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

### Shoko Server

- Open the web UI and confirm the setup wizard is complete
- Confirm `/media/anime` is listed under **Import Folders**
- Confirm AniDB connection is active under **Settings > AniDB**
- Trigger a manual scan and confirm anime titles are being identified

### End-to-End Test

Run through this once to confirm the full pipeline:

1. Add a movie in Radarr and trigger a search
2. Confirm a download starts in qBittorrent within a few minutes
3. Confirm the file is imported in Radarr once downloaded
4. Confirm subtitles were downloaded in Bazarr

If every step passes the full pipeline is working correctly.

---

## Directory Structure

Paths below reflect the defaults in `.env.example`. They can be changed to any location by editing `.env`.

```
/srv/
├── media/
│   ├── movies/          # Radarr output
│   ├── tvshows/         # Sonarr output
│   ├── anime/           # Sonarr output
│   ├── music/
│   └── photos/
├── downloads/           # qBittorrent download folder
├── sonarr/config/
├── radarr/config/
├── prowlarr/config/
├── qbittorrent/config/
├── bazarr/config/
└── shoko/config/
```

---

## Hardware Notes

This stack runs well on modest hardware. Reference build:

- **CPU:** AMD Ryzen 5 5500 (6-core, 12-thread, 4.2GHz boost)
- **RAM:** 16GB DDR4-3200
- **OS Drive:** Any SSD (NVMe recommended)
- **Media Storage:** Any HDD or SSD with sufficient capacity

---

## Useful Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a single service
docker compose restart sonarr

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

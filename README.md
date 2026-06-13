# Home Media Server Stack

A self-hosted home media server built on Ubuntu Server 24.04 LTS and Docker. Streams movies, TV shows, anime, music, and photos to any device on your local network with no cloud accounts, no telemetry, and no data leaving your home.

Designed for local network use only. No port forwarding or external access required.

---

## Stack Overview

| Service | Purpose | Port |
|---|---|---|
| [Jellyfin](https://jellyfin.org) | Media server — stream everything | `:8096` |
| [Sonarr](https://sonarr.tv) | TV show and anime library manager | `:8989` |
| [Radarr](https://radarr.video) | Movie library manager | `:7878` |
| [Shoko Server](https://shokoanime.com) | Anime metadata via AniDB | `:8111` |
| [Bazarr](https://www.bazarr.media) | Automatic subtitle downloader | `:6767` |
| [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) | Discovery, recommendations, and requests | `:5055` |
| [Filebrowser](https://filebrowser.org) | Web file manager for USB/SD copying | `:8080` |
| [Pi-hole](https://pi-hole.net) | Network-wide ad and tracker blocking | `:8053` |
| [Unbound](https://nlnetlabs.nl/projects/unbound) | Local recursive DNS resolver | internal |

---

## Privacy

No service in this stack sends personal data, usage habits, or identifiable information to any external party.

| Service | Telemetry | External Calls | Notes |
|---|---|---|---|
| Jellyfin | None | None | Disable usage stats on first launch |
| Filebrowser | None | None | Fully local |
| Sonarr / Radarr | None | TVDB / TMDB title lookups | IP + title name only |
| Shoko Server | None | AniDB title lookups | IP + title name only |
| Bazarr | None | OpenSubtitles / Animetosho | IP + title name only |
| Jellyseerr | None | TMDB for discovery browsing | IP + search terms only |
| Pi-hole | None | Blocklist updates | Actively improves privacy |
| Unbound | None | Root DNS servers directly | Eliminates third-party DNS visibility |

DNS resolution chain:

```
Your devices → Pi-hole :53 (ad blocking) → Unbound :5335 (recursive resolution) → Root DNS servers
```

No Cloudflare, Google, or ISP DNS server sees your queries.

---

## Prerequisites

- A machine running **Ubuntu Server 24.04 LTS** (bare metal, no desktop environment)
- Static IP assigned to the server — via DHCP reservation on your router or set directly on the machine
- Sufficient storage for your media library

---

## Getting Started

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Log out and back in after this for the group change to take effect.

### 2. Install udisks2 for USB/SD auto-mounting

```bash
sudo apt install -y udisks2
```

Mounts USB drives and SD cards to `/media/<label>` automatically when plugged in.

### 3. Create directory structure

```bash
sudo mkdir -p /srv/media/{movies,tvshows,anime,music,photos}
sudo mkdir -p /srv/{jellyfin,filebrowser,sonarr,radarr,shoko,bazarr,jellyseerr,pihole,unbound}
sudo mkdir -p /srv/downloads
sudo chown -R $USER:$USER /srv
```

### 4. Create Filebrowser config

```bash
echo '{}' > /srv/filebrowser/settings.json
touch /srv/filebrowser/filebrowser.db
```

### 5. Configure docker-compose.yml

Before starting, edit `docker-compose.yml` and update the following:

| Variable | What to change | How to find it |
|---|---|---|
| `PUID=1000` | Your user ID | Run `id` in terminal |
| `PGID=1000` | Your group ID | Run `id` in terminal |
| `user: "1000:1000"` | Your UID:GID (Filebrowser only) | Run `id` in terminal |
| `TZ=America/New_York` | Your timezone | [Timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| `WEBPASSWORD=changeme` | Pi-hole admin password | Set something strong |

If your machine has no integrated GPU, remove these two lines from the Jellyfin section:

```yaml
    devices:
      - /dev/dri:/dev/dri
```

If your media lives on a different drive, update all `/srv/media/...` paths to match — keep them consistent across all services.

### 6. Start the stack

```bash
docker compose up -d
```

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

### Shoko + Jellyfin (Anime)

1. Open Shoko at `http://<server-ip>:8111` and let it scan your `/media/anime` folder
2. In Jellyfin, go to **Admin > Plugins** and install the Shoko plugin
3. Set your anime library metadata source to **Shoko**

This gives you AniDB metadata, correct series grouping, and proper artwork across your entire anime library, including correct matching of files with non-standard naming.

### Bazarr (Subtitles)

1. Open Bazarr at `http://<server-ip>:6767`
2. Go to **Settings > Sonarr**, enter `http://sonarr:8989` and paste your Sonarr API key (found in Sonarr under **Settings > General**)
3. Repeat for **Settings > Radarr** at `http://radarr:7878`
4. Add **OpenSubtitles** as a provider (free account required)
5. For anime, also add **Animetosho** — it has better coverage for seasonal and niche titles
6. Set your preferred subtitle languages

### Jellyfin Audio and Subtitle Preferences (Anime)

In Jellyfin, go to your **user settings > Playback** and set:

- **Preferred audio language:** Japanese
- **Preferred subtitle language:** English
- **Subtitle mode:** Always

These preferences apply automatically across all devices and episodes.

### Jellyseerr (Discovery and Requests)

1. Open Jellyseerr at `http://<server-ip>:5055`
2. Sign in with your Jellyfin account when prompted
3. Connect to **Sonarr**: `http://sonarr:8989` + API key
4. Connect to **Radarr**: `http://radarr:7878` + API key

For niche or seasonal anime, [AniList](https://anilist.co) has a more comprehensive recommendation engine than Jellyseerr's TMDB-based discovery. The typical workflow is to find a title on AniList, then search for and request it through Jellyseerr.

### Pi-hole + Unbound (Private DNS)

Unbound starts automatically and Pi-hole is pre-configured to forward to it via `PIHOLE_DNS_=unbound#5335` — no manual DNS configuration is needed beyond pointing your router at the server.

1. Open Pi-hole at `http://<server-ip>:8053/admin` and confirm Unbound appears under **Settings > DNS**
2. In your router's admin panel, set the primary DNS server to this server's IP address
3. All devices on the network now resolve DNS through Pi-hole + Unbound with no third-party DNS visibility
4. Confirm it is working by watching the live query log in the Pi-hole dashboard

### Filebrowser (Offline Viewing)

1. Open Filebrowser at `http://<server-ip>:8080`
2. Default login is `admin` / `admin` — change this on first login
3. Plug in a USB drive or SD card — it auto-mounts and appears under `/media` in Filebrowser
4. Copy files from your library to the drive for offline viewing

---

## Directory Structure

```
/srv/
├── media/
│   ├── movies/          # Radarr output → Jellyfin source
│   ├── tvshows/         # Sonarr output → Jellyfin source
│   ├── anime/           # Sonarr + Shoko → Jellyfin source
│   ├── music/           # Jellyfin music library
│   └── photos/          # Jellyfin photo library
├── downloads/           # Download client drop folder
├── jellyfin/
│   ├── config/          # Jellyfin config and database
│   └── cache/           # Transcoding cache
├── sonarr/config/
├── radarr/config/
├── shoko/config/
├── bazarr/config/
├── jellyseerr/config/
├── filebrowser/
├── pihole/
└── unbound/
```

---

## Hardware Notes

This stack runs well on modest hardware. Reference build:

- **CPU:** AMD Ryzen 5 5500 (6-core, 12-thread, 4.2GHz boost)
- **RAM:** 16GB DDR4-3200
- **OS Drive:** Any SSD (NVMe recommended)
- **Media Storage:** Any HDD or SSD with sufficient capacity

The Ryzen 5 5500 has no integrated GPU. Remove the `devices: /dev/dri` lines from the Jellyfin section for this CPU. The 6-core processor handles software transcoding adequately, and most modern clients on a local network will direct play without triggering transcoding at all.

For machines with an Intel integrated GPU, enable hardware transcoding after starting the stack:

```bash
sudo apt install -y intel-media-va-driver-non-free
sudo usermod -aG render $USER
```

Then in Jellyfin go to **Dashboard > Playback** and enable Intel QSV.

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

## Contributing

Contributions, custom implementations, and enhancements are welcome. Feel free to open a pull request or issue for additional service integrations, custom scripts and automations, hardware-specific configuration guides, or general improvements to the stack.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

You are free to use, modify, and distribute this project, but any derivative work must also be distributed under the same license terms.
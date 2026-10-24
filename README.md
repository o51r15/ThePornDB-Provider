<div align="center">

# tpdb-provider

**Plex metadata provider for ThePornDB — scenes, movies and JAV, identified from your filenames.**

The successor to [ThePornDB.bundle](https://github.com/ThePornDatabase/ThePornDB.bundle), rebuilt as an HTTP service against the custom metadata provider API that Plex shipped in PMS 1.43.0 — the replacement Plex built so that agents like the bundle could stop depending on the retired Plug-ins system.

[![GitHub last commit](https://img.shields.io/github/last-commit/o51r15/ThePornDB-Provider)](https://github.com/o51r15/ThePornDB-Provider)
[![Build](https://img.shields.io/github/actions/workflow/status/o51r15/ThePornDB-Provider/build.yml?label=build)](https://github.com/o51r15/ThePornDB-Provider/actions)
[![GHCR](https://img.shields.io/badge/ghcr.io-tpdb--provider-blue?logo=docker&logoColor=white)](https://github.com/o51r15/ThePornDB-Provider/pkgs/container/tpdb-provider)
[![Plex](https://img.shields.io/badge/plex-1.43%2B-e5a00d.svg)](https://www.plex.tv/)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

> **Why this exists** — Plex removed the Plug-ins system from PMS years ago but kept the legacy metadata agents running, in their words, "until we had a suitable replacement for those." That replacement arrived in **PMS 1.43.0**: a metadata provider is now an HTTP API the server queries, using [the same API as Plex's own Movie and Series agents](https://forums.plex.tv/t/announcement-custom-metadata-providers/934384). The same release also stops showing legacy agents when you create a library, and Plex has said it plans "to completely remove the legacy agents system from new PMS releases in 2026," telling agent maintainers "it would be a great time to hop in and implement your agent using the new metadata provider method." This is that migration for ThePornDB: the matching logic, preference set and TPDB field mapping are ported from the bundle, so the behaviour you had is intact — it just runs beside Plex instead of inside it.

## What It Does

Plex sends a match request with whatever it knows about a file — filename, title, year, sometimes a hash. tpdb-provider cleans that up, hands it to ThePornDB's `parse` endpoint, and returns a fully populated item: real scene or movie title, studio, release date, runtime, cast with headshots, genres, poster and background art, trailer, and site / parent / network collections.

One container serves four providers off separate paths, so a single deployment covers a scene library, a movie library and optionally JAV without running anything else. Nothing leaves your network except the calls to ThePornDB itself.

## Features

- **Drop-in for the old bundles** — `/scenes` and `/movies` reproduce the Scenes and Movies agents: movie-type libraries, matched on filename, no renaming required
- **Filename identification** — the raw filename goes to TPDB's `parse` endpoint, the same call the bundle relied on; handles `Site - YYYY-MM-DD - Title`, release-style `Site.YY.MM.DD.stuff`, and messier names
- **Every bundle preference ported** — cleanup regex, score method, custom title format, collection prefixes, oshash matching, collected-tagging, all as environment variables
- **Full metadata** — title, studio, summary, release date, runtime, content rating, genres, cast with face images, poster and background art, trailers
- **Collections** — site, parent and network collections with optional prefixes, so a movie library still browses by studio
- **TV hierarchy** — optional `/tv` provider models the site as a show, release years as seasons, scenes as episodes
- **Hint-name tolerant** — title, file, year and hash are each resolved from every key name Plex has been observed to use, so a movie request arriving as `name`/`file` matches the same as a scene one arriving as `title`/`filename`
- **Concurrent upstream paging** — a site's scene list is fetched in parallel at 100 per page; a 4000-scene site went from 201 serial requests to 41, cold listing 36s → 3s
- **Response caching** — in-process TTL cache keyed on URL and params, so Plex's repeated children calls cost nothing
- **Self-check endpoint** — `/scenes/selftest` makes a real API call and reports exactly which upstream fields are present, missing or empty
- **Bulk renamer** — `tools/rename_for_plex.py` converts a library to the only naming Plex's TV scanner can number, resolving every file against TPDB for the real title; dry run by default
- **52 tests** — every one written against a bug that actually occurred against a live Plex server
- **Docker-native** — GHCR images, non-root container, healthcheck, CI-built `:dev` and `:latest`

## Quick Start

### Docker Compose (recommended)

```bash
# 1. Create your compose file
mkdir -p ~/tpdb-provider
curl -o ~/tpdb-provider/docker-compose.yml \
  https://raw.githubusercontent.com/o51r15/ThePornDB-Provider/main/docker-compose.yml

# 2. Add your TPDB token
cd ~/tpdb-provider
echo 'TPDB_API_KEY=your-token-here' > .env
echo 'TZ=America/New_York' >> .env

# 3. Run
docker compose up -d
```

Verify: **http://your-server:8080/scenes** — a `MediaProvider` document comes back when it's working.

> **Updating:** `docker compose pull && docker compose up -d`

> **Security:** Plex sends custom providers **unauthenticated** requests — provider auth is not implemented yet. Plex calls this "fine for development or local-only hosting" and advises waiting before publishing a public API. Keep this on your LAN.

### Docker Compose File

```yaml
services:
  tpdb-provider:
    image: ghcr.io/o51r15/tpdb-provider:dev   # :latest for tagged releases
    container_name: tpdb-provider
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - TZ=America/New_York
    env_file:
      - .env
```

### From Source

```bash
git clone https://github.com/o51r15/ThePornDB-Provider.git && cd ThePornDB-Provider
pip install -r requirements.txt
cp .env.example .env                        # add your TPDB_API_KEY
TPDB_API_KEY=... python3 wsgi.py            # dev
gunicorn --bind 0.0.0.0:8080 wsgi:app       # prod
```

## Providers

One container, four paths. Register whichever you need as separate providers in Plex.

| Path | Plex library | Model | Filenames | Default |
|---|---|---|---|---|
| **`/scenes`** | Movie | One scene = one item, grouped by site / parent / network collections | Any — matched on filename | **On** |
| **`/movies`** | Movie | One release = one item, for full-length titles rather than site scenes | Any — matched on filename | **On** |
| `/jav` | Movie | Same, against TPDB's JAV collection | Any — matched on filename | Off — set `TPDB_JAV_ENABLE=true` |
| `/tv` | TV Shows | Site = show, release year = season, scene = episode | Must carry `S<year>E<MMDD>` | On, but needs a rename pass |

## Plex Setup

1. **Settings → Metadata Agents → Add Provider** → `http://your-server:8080/scenes`
2. **Add Agent** — name it, then set the provider you just added as **Primary**
3. Create a **Movie** library and pick that agent in the library's **Advanced** pane

Repeat with `http://your-server:8080/movies` for a full-length movie library. Each path is a distinct provider with its own identifier, so both agents coexist.

> **A refresh never re-matches.** Items that failed to match are stored as `local://` stubs and stay that way forever. Only a fresh scan of a file Plex has not seen, or a manual **Fix Match**, creates a new binding. After changing provider behaviour, Fix Match one item to verify, then recreate the library.

> **If a new agent doesn't appear in the dropdown,** hard-refresh Plex Web (`Ctrl+Shift+R`). The agent list is cached client-side; `GET /system/agents?mediaType=1` on the server is the source of truth.

## Configuration

Everything is environment variables — the provider API has no Plex-side
preferences pane, so the bundle's `DefaultPrefs.json` moved to `.env`.

| Variable | Bundle preference | Default | Description |
|---|---|---|---|
| `TPDB_API_KEY` | `personal_api_key` | — | **Required.** Token from your theporndb.net account settings |
| `TPDB_MOVIES_ENABLE` | — | `true` | Serve `/movies` |
| `TPDB_JAV_ENABLE` | — | `false` | Serve `/jav` |
| `TPDB_MATCH_BY_FILENAME` | `match_by_filepath_enable` | `true` | Use the filename rather than Plex's cleaned title |
| `TPDB_CLEANUP_ENABLE` | `filepath_cleanup_enable` | `false` | Apply cleanup regexes before searching |
| `TPDB_OSHASH_ENABLE` | `oshash_matching_enable` | `false` | Leave off — Plex's own hash makes TPDB 422 the whole call |
| `TPDB_CUSTOM_TITLE_ENABLE` | `custom_title_enable` | `false` | Rewrite item titles |
| `TPDB_COLLECTIONS_FROM_SITE` | `collections_from_site` | `true` | Also `_PARENTS_`, `_NETWORKS_`, `_TAGS_` |
| `TPDB_CACHE_TTL` | — | `3600` | Response cache lifetime, seconds; `0` disables |
| `TPDB_LOG_LEVEL` | `logging_level` | `INFO` | `DEBUG` logs the hints Plex sends |

**[Full configuration reference →](https://github.com/o51r15/ThePornDB-Provider/wiki/Configuration)** — all 38 variables,
each mapped to the bundle preference it replaces.

## TV Provider

Register `/tv` against a **TV Shows** library and each site becomes a show,
each release year a season, each scene an episode (`2019-01-25` → **S2019E0125**).

**It requires renaming your library first.** Plex's TV scanner will not assign
a season or episode to typical scene filenames, so they land in
`[Unknown Season]` and can never bind. This is Plex's side, by design — the old
Python plug-ins could hook the scanner and Plex has stated there is "no plan
currently" to offer that in the new API. The included
`tools/rename_for_plex.py` converts a library to the one form the scanner
parses, resolving each file against TPDB for the real title, dry run by default.

**If renaming isn't something you want to do, use `/scenes`.** It matches on
filename alone and has none of this constraint, which is why it's the drop-in
replacement for the old Scenes bundle.

**[TV provider and renaming guide →](https://github.com/o51r15/ThePornDB-Provider/wiki/TV-Provider-and-Renaming)**

## Endpoints

Each provider path (`/scenes`, `/movies`, `/jav`, `/tv`) exposes the same
shape: a manifest at the root, `POST /library/metadata/matches`, and
`GET /library/metadata/{ratingKey}` plus `/children`, `/grandchildren`,
`/images` and `/extras`. There is a `/selftest` per provider and a `/health`
for liveness.

GUIDs follow `<identifier>://<type>/<ratingKey>`.

**[Full endpoint reference →](https://github.com/o51r15/ThePornDB-Provider/wiki/Endpoints)**

## Notes on Plex's Provider API

Plex's provider API has undocumented behaviour that costs real debugging time —
paging that arrives as query parameters, nested containers that must be objects
rather than arrays, hint keys that change name by library type, and the fact
that a provider cannot influence scanning at all.

**[Plex provider API notes →](https://github.com/o51r15/ThePornDB-Provider/wiki/Plex-Provider-API-Notes)** — each entry
recorded from the failure it caused.

## Docker Images

| Tag | When it's built | Moves? |
|---|---|---|
| `ghcr.io/o51r15/tpdb-provider:dev` | Every push to `main` or `provider` | Yes — latest commit |
| `ghcr.io/o51r15/tpdb-provider:latest` | Tagged releases only | Yes — newest release |
| `ghcr.io/o51r15/tpdb-provider:1.0` | Tagged releases | Yes — newest 1.0.x |
| `ghcr.io/o51r15/tpdb-provider:1.0.0` | The release itself | No — pin to this |

Note the image tags carry **no `v` prefix** even though the git tags do:
`git tag v1.0.0` produces `:1.0.0`. Pin to the exact version in production;
`:dev` is the development stream and will break.

Cut a release with `git tag -a v1.0.0 -m v1.0.0 && git push fork v1.0.0`.

## Tests

```bash
python3 tests/test_provider.py     # 22
python3 tests/test_tv.py           # 30
```

Upstream is stubbed, so no token is needed. They cover the manifest shape, every match path, pagination via both query params and headers, the nested-container shapes, episode index derivation, hint-key resolution and hash handling.

## Documentation

- **[Configuration](https://github.com/o51r15/ThePornDB-Provider/wiki/Configuration)** — every environment variable, with the bundle preference it replaces
- **[Endpoints](https://github.com/o51r15/ThePornDB-Provider/wiki/Endpoints)** — the HTTP surface each provider path exposes
- **[TV Provider and Renaming](https://github.com/o51r15/ThePornDB-Provider/wiki/TV-Provider-and-Renaming)** — why `/tv` needs renamed files, and the bulk renamer
- **[Plex Provider API Notes](https://github.com/o51r15/ThePornDB-Provider/wiki/Plex-Provider-API-Notes)** — undocumented behaviour, each recorded from a real failure
- **[Troubleshooting](https://github.com/o51r15/ThePornDB-Provider/wiki/Troubleshooting)** — start here when nothing matches

## Requirements

- **Plex Media Server 1.43.0+** — the release that introduced custom metadata providers; there is no way to register one on an earlier server
- **A ThePornDB API token** — from your account settings at [theporndb.net](https://theporndb.net/)
- **Docker**, or **Python 3.9+** to run from source
- Network reachability from the Plex server to this service

## Tech Stack

Python 3.9+ (`python:3.12-slim` in the image), Flask blueprints, gunicorn, `requests` with a thread-local session and `ThreadPoolExecutor` paging, GitHub Actions → GHCR

## Links

- [Plex Metadata Providers API](https://developer.plex.tv/pms/) — the spec this implements
- [ThePornDB](https://theporndb.net/) — the metadata source
- [Issues](https://github.com/o51r15/ThePornDB-Provider/issues) — bugs and feature requests

## License

[MIT](LICENSE). Ported from [ThePornDB.bundle](https://github.com/ThePornDatabase/ThePornDB.bundle),
which carries no license of its own; the MIT grant here covers this rewrite.

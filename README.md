<div align="center">

# tpdb-provider

**Plex metadata provider for ThePornDB — scenes, movies and JAV, identified from your filenames.**

The successor to [ThePornDB.bundle](https://github.com/ThePornDatabase/ThePornDB.bundle). Plex Media Server 1.43 removed the plug-in framework every `.bundle` agent depended on; this is the same behaviour reimplemented against Plex's new HTTP metadata provider API.

[![GitHub last commit](https://img.shields.io/github/last-commit/o51r15/ThePornDB.bundle)](https://github.com/o51r15/ThePornDB.bundle)
[![Build](https://img.shields.io/github/actions/workflow/status/o51r15/ThePornDB.bundle/build.yml?label=build)](https://github.com/o51r15/ThePornDB.bundle/actions)
[![GHCR](https://img.shields.io/badge/ghcr.io-tpdb--provider-blue?logo=docker&logoColor=white)](https://github.com/o51r15/ThePornDB.bundle/pkgs/container/tpdb-provider)
[![Plex](https://img.shields.io/badge/plex-1.43%2B-e5a00d.svg)](https://www.plex.tv/)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)

</div>

---

> **Why this exists** — PMS 1.43 dropped plug-in agents, so ThePornDB.bundle and every fork of it stopped loading. Plex's replacement is a REST API: a provider is an external HTTP service the server queries, not Python 2 running inside it. The matching logic, preference set and TPDB field mapping here are ported from the bundle, so the behaviour you had is intact — the dead scaffolding is gone.

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
  https://raw.githubusercontent.com/o51r15/ThePornDB.bundle/main/docker-compose.yml

# 2. Add your TPDB token
cd ~/tpdb-provider
echo 'TPDB_API_KEY=your-token-here' > .env
echo 'TZ=America/New_York' >> .env

# 3. Run
docker compose up -d
```

Verify: **http://your-server:8080/scenes** — a `MediaProvider` document comes back when it's working.

> **Updating:** `docker compose pull && docker compose up -d`

> **Security:** Plex sends custom providers **unauthenticated** requests. Keep this on your LAN until Plex ships provider auth.

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
git clone https://github.com/o51r15/ThePornDB.bundle.git && cd ThePornDB.bundle
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

Everything is environment variables — the provider API has no Plex-side preferences pane, so the bundle's `DefaultPrefs.json` moved to `.env`.

| Variable | Bundle preference | Default | Description |
|---|---|---|---|
| `TPDB_API_KEY` | `personal_api_key` | — | **Required.** Token from your theporndb.net account settings |
| `TPDB_API_BASE` | — | `https://api.theporndb.net` | Upstream base URL |
| `TPDB_TIMEOUT` | — | `30` | Upstream request timeout, seconds |
| `TPDB_RETRIES` | — | `3` | Upstream retry attempts |
| `TPDB_CACHE_TTL` | — | `3600` | Response cache lifetime, seconds; `0` disables |
| `TPDB_IDENTIFIER` | — | `tv.plex.agents.custom.theporndb.scenes` | Must start with `tv.plex.agents.custom.` |
| `TPDB_TITLE` | — | `ThePornDB Scenes` | Name Plex shows for the provider |
| `TPDB_MOVIES_ENABLE` | — | `true` | Serve `/movies` |
| `TPDB_MOVIES_IDENTIFIER` | — | `…theporndb.movies` | |
| `TPDB_MOVIES_TITLE` | — | `ThePornDB Movies` | |
| `TPDB_JAV_ENABLE` | — | `false` | Serve `/jav` |
| `TPDB_JAV_IDENTIFIER` | — | `…theporndb.jav` | |
| `TPDB_JAV_TITLE` | — | `ThePornDB JAV` | |
| `TPDB_TV_IDENTIFIER` | — | `…theporndb.tv` | |
| `TPDB_TV_TITLE` | — | `ThePornDB Scenes (TV)` | |
| `TPDB_MATCH_BY_FILENAME` | `match_by_filepath_enable` | `true` | Use the filename rather than Plex's cleaned title |
| `TPDB_STRIP_PATH` | `filepath_strip_path_enable` | `true` | Search the basename, not the full path |
| `TPDB_CLEANUP_ENABLE` | `filepath_cleanup_enable` | `false` | Apply the cleanup regexes below |
| `TPDB_CLEANUP_REGEX` | `filepath_cleanup` | — | Comma-separated regexes stripped before searching |
| `TPDB_CLEANUP_REPLACE` | `filepath_replace` | — | Replacement for the above |
| `TPDB_SCORE_METHOD` | `score_method` | `default` | `default` or `custom` |
| `TPDB_CUSTOM_SCORE` | `custom_score` | `{site} {date} {title}` | Levenshtein target when `custom` |
| `TPDB_MAX_RESULTS` | — | `20` | Matches returned per request |
| `TPDB_MAX_PAGE_SIZE` | — | `500` | Ceiling on a client-requested page size |
| `TPDB_OSHASH_ENABLE` | `oshash_matching_enable` | `false` | Leave off — see below |
| `TPDB_CUSTOM_TITLE_ENABLE` | `custom_title_enable` | `false` | Rewrite item titles |
| `TPDB_CUSTOM_TITLE` | `custom_title` | `{actors} - {title} [{studio}/{series}]` | |
| `TPDB_CONTENT_RATING` | — | `XXX` | |
| `TPDB_COLLECTIONS_FROM_SITE` | `collections_from_site` | `true` | |
| `TPDB_COLLECTIONS_FROM_PARENTS` | `collections_from_parents` | `true` | |
| `TPDB_COLLECTIONS_FROM_NETWORKS` | `collections_from_networks` | `true` | |
| `TPDB_COLLECTIONS_FROM_TAGS` | `create_all_tag_collection_tags` | `false` | |
| `TPDB_COLLECTION_SITE_PREFIX` | `collection_site_prefix` | — | Also `_PARENT_` and `_NETWORK_` |
| `TPDB_SAVE_TO_COLLECTION` | `save_to_collection` | `false` | Marks scenes collected on TPDB |
| `TPDB_SITE_PAGE_SIZE` | — | `100` | Upstream max is 100; higher returns empty |
| `TPDB_MAX_SITE_PAGES` | — | `60` | 6000 scenes per site |
| `TPDB_SITE_FETCH_WORKERS` | — | `8` | Concurrent page fetches |
| `TPDB_LOG_LEVEL` | `logging_level` | `INFO` | `DEBUG` logs the hints Plex sends |

### About `TPDB_OSHASH_ENABLE`

Leave it off unless your files genuinely carry OpenSubtitles hashes. Plex puts its **own** hash in every match request, and TPDB rejects any `hash` that isn't 16 hex digits by failing the entire call:

```
422 {"message":"The hash must be valid hash.","errors":{"hash":["The hash must be valid hash."]}}
```

Forwarding it blindly returned empty results for every file in the library. The provider now only sends a hash matching `^[0-9a-fA-F]{16}$`, and only when this is enabled.

## TV Provider

Register `/tv` against a **TV Shows** library and each site becomes a show, each release year a season, each scene an episode.

**Read this before committing to it.** TPDB scenes have no episode number, so `/tv` derives one from the air date: `2019-01-25` becomes **S2019E0125**. Stable, ordered, unique within a site-year; two scenes from the same site on the same day share an index but stay distinct by GUID.

The catch is Plex's side, not the provider's. **Plex's TV scanner will not number typical scene filenames** — it reads the date but assigns no season or episode, so they land in `[Unknown Season]` and can never bind:

| Filename | Plex scanner result |
|---|---|
| `Show - 2019-01-18 - Title [WEBDL-1080p].mkv` | no index, no season |
| `Show.24.06.27.performer.XXX.mkv` | season 1, arbitrary episode |
| `Show - S2019E0118 - Title.mkv` | **index 118, season 2019** |

The included renamer converts a library to the third form, looking each file up in TPDB so the title is authoritative rather than parsed:

```bash
python3 tools/rename_for_plex.py '/path/to/Scenes'              # dry run + TSV report
python3 tools/rename_for_plex.py '/path/to/Scenes' --apply
python3 tools/rename_for_plex.py '/path/to/Scenes' --only 'Baby Got Boobs'
```

It handles ISO dates, `YY.MM.DD` release style and `DD.MM.YYYY`, skips names already in `S##E##` form, and refuses to guess — same-day collisions it can't resolve from the filename are reported as `AMBIGUOUS` and left alone.

**If renaming isn't something you want to do, use `/scenes`.** It matches on filename alone and has none of this constraint, which is why it's the drop-in replacement for the old Scenes bundle.

## Endpoints

Each provider path (`/scenes`, `/movies`, `/jav`, `/tv`) exposes the same shape.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/{provider}` | Provider manifest |
| `POST` | `/{provider}/library/metadata/matches` | Match feature |
| `GET` | `/{provider}/library/metadata/{ratingKey}` | Metadata — `?includeChildren=1` embeds children |
| `GET` | `/{provider}/library/metadata/{ratingKey}/children` | Seasons of a show, or episodes of a season |
| `GET` | `/{provider}/library/metadata/{ratingKey}/grandchildren` | Every episode of a show |
| `GET` | `/{provider}/library/metadata/{ratingKey}/images` | Artwork |
| `GET` | `/{provider}/library/metadata/{ratingKey}/extras` | Trailers |
| `GET` | `/{provider}/selftest?q=<title>` | Validates the live upstream contract |
| `GET` | `/health` | Liveness |

GUIDs follow `<identifier>://<type>/<ratingKey>`. TV rating keys are prefixed `show-<siteId>`, `season-<siteId>-<year>`, `ep-<sceneUuid>`.

## Notes on Plex's Provider API

Undocumented behaviour that cost real debugging time, recorded so the next person doesn't repeat it:

- **Paging arrives as query parameters** on GETs (`?X-Plex-Container-Start=…`), not only as headers. Reading headers alone makes every page return the same slice, and Plex will happily walk offsets 0→580 receiving identical bodies.
- **Nested containers must be objects**, never arrays — `{"size": n, "Metadata": [...]}`. This bit twice, on `Children` and again on `Extras`. An array fails the *entire* response with `failed to parse JSON response: 'object expected' at 1:NN`, where `NN` is the byte offset of the offending `[` — count to that column to find which key is wrong.
- **Hint keys are not consistent.** The same field arrives as `title` or `name`, `filename` or `file`, depending on library type. Reading one spelling only makes every lookup answer with an empty container, and Plex logs `Primary provider … failed to return a result, skipping item` and silently reverts the library to its built-in agent.
- **Plex never sends a `type: 4` episode match.** It matches the show, then the season with `includeChildren=1`, and binds files to the children in that response. A season returned without its episodes binds nothing.
- **Its scanner falls back to season 1** when it can't parse a season from the filename, so the provider recovers the year from any date it can find in the name.
- **A refresh never re-matches.** `local://` stubs are permanent until a fresh scan or a manual Fix Match.

## Docker Images

| Tag | When it's built |
|---|---|
| `ghcr.io/o51r15/tpdb-provider:dev` | Every push to `main` or `provider` |
| `ghcr.io/o51r15/tpdb-provider:latest` | Tagged releases only |
| `ghcr.io/o51r15/tpdb-provider:vX.Y.Z` | The release itself |

Cut a release with `git tag v1.0.0 && git push fork --tags`.

## Tests

```bash
python3 tests/test_provider.py     # 22
python3 tests/test_tv.py           # 30
```

Upstream is stubbed, so no token is needed. They cover the manifest shape, every match path, pagination via both query params and headers, the nested-container shapes, episode index derivation, hint-key resolution and hash handling.

## Requirements

- **Plex Media Server 1.43.0+** — custom metadata providers do not exist before this
- **A ThePornDB API token** — from your account settings at [theporndb.net](https://theporndb.net/)
- **Docker**, or **Python 3.9+** to run from source
- Network reachability from the Plex server to this service

## Tech Stack

Python 3.9+ (3.12 in the image), Flask blueprints, gunicorn, `requests` with a thread-local session and `ThreadPoolExecutor` paging, Alpine (Docker), GitHub Actions → GHCR

## Links

- [Plex Metadata Providers API](https://developer.plex.tv/pms/) — the spec this implements
- [ThePornDB](https://theporndb.net/) — the metadata source
- [Issues](https://github.com/o51r15/ThePornDB.bundle/issues) — bugs and feature requests

## License

Ported from [ThePornDB.bundle](https://github.com/ThePornDatabase/ThePornDB.bundle); the original project carries no license file, and neither does this fork.

# Security Policy

## Reporting a vulnerability

Open a [security advisory](https://github.com/o51r15/ThePornDB-Provider/security/advisories/new)
rather than a public issue. If advisories are unavailable to you, open an issue
that says only that you have a security report and asks for a contact route —
do not include details in it.

## Scope and known exposure

Two things are worth stating plainly, because they are properties of Plex's
provider API rather than bugs in this project:

- **Plex sends custom metadata providers unauthenticated requests.** Provider
  authentication is not implemented in the Plex API yet. Anything that can
  reach the port can query it, and Plex itself advises waiting before
  publishing a public provider API. Run this on a trusted network. Do not
  expose port 8080 to the internet.
- **Your ThePornDB token lives in the provider's environment.** It is read
  from `TPDB_API_KEY` and sent only to `TPDB_API_BASE`
  (`https://api.theporndb.net` by default). Keep `.env` out of version
  control — it is gitignored — and remember that `docker inspect` and the
  process environment expose it to anyone with host access.

The provider holds no user credentials, stores nothing to disk, and its cache
is in-process only.

## Supported versions

Fixes land on `main` and ship in the next `:dev` image and the next tagged
release. Only the latest release is supported.

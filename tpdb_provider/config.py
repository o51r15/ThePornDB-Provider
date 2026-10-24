"""Configuration, carried over from the old bundle's DefaultPrefs.json.

Everything is read from environment variables because the new metadata
provider API has no Plex-side preferences UI.
"""
import os
import sys


def truthy(value):
    """One definition of true, for env flags and query parameters alike.

    tv.py had two: one accepting ('1','true') and one accepting
    ('1','true','True'), so includeChildren=True was honoured in one place
    and silently ignored in the other - and a season returned without its
    children binds nothing.
    """
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return truthy(raw)


def _str(name, default=''):
    val = os.environ.get(name)
    return default if val is None else val


def _int(name, default):
    """An int setting, falling back instead of killing the process.

    These were int(_str(...)) evaluated at class-definition time, so one
    non-numeric value crashed the container at import with a bare
    ValueError and no indication of which variable was at fault.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return int(raw.strip())
    except ValueError:
        sys.stderr.write(
            '%s=%r is not a number; using %d\n' % (name, raw, default))
        return default


class Config(object):
    # --- upstream ---
    api_base = _str('TPDB_API_BASE', 'https://api.theporndb.net')
    api_key = _str('TPDB_API_KEY')
    timeout = _int('TPDB_TIMEOUT', 30)
    retries = _int('TPDB_RETRIES', 3)
    cache_ttl = _int('TPDB_CACHE_TTL', 3600)
    # Hard ceiling on cached upstream responses. A site page holds up to
    # TPDB_SITE_PAGE_SIZE scenes, so this bounds memory; without a cap the
    # cache only ever dropped an entry when that exact key was requested
    # again after expiry, and grew for the life of the process.
    cache_max_entries = _int('TPDB_CACHE_MAX_ENTRIES', 1000)

    # --- provider identity ---
    identifier = _str('TPDB_IDENTIFIER', 'tv.plex.agents.custom.theporndb.scenes')
    title = _str('TPDB_TITLE', 'ThePornDB Scenes')
    version = _str('TPDB_VERSION', '2.0.0')

    # --- matching ---
    # 'default' = upstream relevance order, 'custom' = Levenshtein against a format string
    score_method = _str('TPDB_SCORE_METHOD', 'default')
    custom_score = _str('TPDB_CUSTOM_SCORE', '{site} {date} {title}')
    oshash_enable = _bool('TPDB_OSHASH_ENABLE', False)
    match_by_filename = _bool('TPDB_MATCH_BY_FILENAME', True)
    strip_path = _bool('TPDB_STRIP_PATH', True)
    cleanup_enable = _bool('TPDB_CLEANUP_ENABLE', False)
    # Comma-separated, inherited from the bundle's pref format. A pattern
    # containing a comma - any {2,} quantifier - is split and dropped with
    # a warning; use a bounded {2,8} form instead.
    cleanup_regex = _str('TPDB_CLEANUP_REGEX')
    cleanup_replace = _str('TPDB_CLEANUP_REPLACE')
    # TPDB's parse endpoint ignores release tokens it recognises, but any it
    # does not are treated as part of the title and kill the match outright:
    # 'Submissived Constance 1080p' matched, 'Submissived Constance 720hd'
    # returned nothing at all.
    strip_release_junk = _bool('TPDB_STRIP_RELEASE_JUNK', True)
    # On a miss, retry with trailing words dropped. 'Full Hi' is too ordinary
    # to strip blindly, so trimming finds it without guessing at real title
    # words. 0 disables.
    match_retry_depth = _int('TPDB_MATCH_RETRY_DEPTH', 3)
    max_results = _int('TPDB_MAX_RESULTS', 20)
    max_page_size = _int('TPDB_MAX_PAGE_SIZE', 500)

    # --- metadata shaping ---
    content_rating = _str('TPDB_CONTENT_RATING', 'XXX')
    collections_from_site = _bool('TPDB_COLLECTIONS_FROM_SITE', True)
    collections_from_parents = _bool('TPDB_COLLECTIONS_FROM_PARENTS', True)
    collections_from_networks = _bool('TPDB_COLLECTIONS_FROM_NETWORKS', True)
    collections_from_tags = _bool('TPDB_COLLECTIONS_FROM_TAGS', False)
    collection_site_prefix = _str('TPDB_COLLECTION_SITE_PREFIX')
    collection_parent_prefix = _str('TPDB_COLLECTION_PARENT_PREFIX')
    collection_network_prefix = _str('TPDB_COLLECTION_NETWORK_PREFIX')
    custom_title_enable = _bool('TPDB_CUSTOM_TITLE_ENABLE', False)
    custom_title = _str('TPDB_CUSTOM_TITLE', '{actors} - {title} [{studio}/{series}]')
    save_to_collection = _bool('TPDB_SAVE_TO_COLLECTION', False)

    # --- movies provider (full releases, TPDB /movies endpoint) ---
    movies_identifier = _str('TPDB_MOVIES_IDENTIFIER',
                             'tv.plex.agents.custom.theporndb.movies')
    movies_title = _str('TPDB_MOVIES_TITLE', 'ThePornDB Movies')
    movies_enable = _bool('TPDB_MOVIES_ENABLE', True)

    # --- jav provider (TPDB /jav endpoint) ---
    jav_identifier = _str('TPDB_JAV_IDENTIFIER',
                          'tv.plex.agents.custom.theporndb.jav')
    jav_title = _str('TPDB_JAV_TITLE', 'ThePornDB JAV')
    jav_enable = _bool('TPDB_JAV_ENABLE', False)

    # --- tv provider (site = show, year = season, scene = episode) ---
    tv_identifier = _str('TPDB_TV_IDENTIFIER', 'tv.plex.agents.custom.theporndb.tv')
    tv_title = _str('TPDB_TV_TITLE', 'ThePornDB Scenes (TV)')
    site_page_size = _int('TPDB_SITE_PAGE_SIZE', 100)
    max_site_pages = _int('TPDB_MAX_SITE_PAGES', 60)
    site_fetch_workers = _int('TPDB_SITE_FETCH_WORKERS', 8)

    # --- service ---
    log_level = _str('TPDB_LOG_LEVEL', 'INFO')


config = Config()

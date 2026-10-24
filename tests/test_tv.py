import importlib, os, sys, unittest
from unittest import mock

os.environ.update({'TPDB_API_KEY': 'k', 'TPDB_CACHE_TTL': '0'})
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from tpdb_provider import create_app
from tpdb_provider import tpdb, tv
from tpdb_provider import config as config_mod

SITE = {'id': 92, 'name': 'Baby Got Boobs', 'short_name': 'babygotboobs',
        'description': 'Big tits.', 'poster': 'http://img/site-poster.jpg',
        'logo': 'http://img/site-logo.png', 'network_id': 20,
        'network': {'id': 20, 'name': 'Brazzers'}}

SITES = [SITE, {'id': 93, 'name': 'Baby Got Boobs Extra', 'short_name': 'bgbx'}]


def scene(sid, date, title):
    return {'id': sid, 'title': title, 'date': date, 'duration': 1800,
            'description': 'd', 'site': SITE, 'site_id': 92,
            'tags': [{'name': 'Anal'}],
            'performers': [{'name': 'P One', 'face': 'http://img/p.jpg'}],
            'posters': {'large': 'http://img/p.jpg'},
            'background': {'full': 'http://img/bg.jpg'}}


SCENES = [
    scene('aaa', '2019-01-25', 'Squeaky Clean'),
    scene('bbb', '2019-04-05', 'Sauna'),
    scene('ccc', '2020-07-15', 'Pool Shy'),
]


class TVTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()

    def test_manifest_has_all_three_types(self):
        mp = self.app.get('/tv').get_json()['MediaProvider']
        self.assertEqual([t['type'] for t in mp['Types']], [2, 3, 4])
        self.assertTrue(mp['identifier'].startswith('tv.plex.agents.custom.'))
        self.assertEqual(mp['Types'][0]['Scheme'][0]['scheme'], mp['identifier'])

    def test_episode_index_from_date(self):
        self.assertEqual(tv.episode_index({'date': '2019-01-25'}), 125)
        self.assertEqual(tv.episode_index({'date': '2019-12-31'}), 1231)
        self.assertIsNone(tv.episode_index({'date': ''}))

    def test_key_roundtrip(self):
        self.assertEqual(tv.parse_key('show-92'), ('show', '92', None))
        self.assertEqual(tv.parse_key('season-92-2019'), ('season', '92', '2019'))
        self.assertEqual(tv.parse_key('ep-aaa'), ('episode', 'aaa', None))
        self.assertEqual(tv.parse_key('junk'), (None, None, None))

    def test_match_show_exact_scores_100(self):
        with mock.patch.object(tpdb, 'search_sites', return_value=SITES):
            r = self.app.post('/tv/library/metadata/matches',
                              json={'type': 2, 'title': 'Baby Got Boobs'})
        items = r.get_json()['MediaContainer']['Metadata']
        self.assertEqual(items[0]['title'], 'Baby Got Boobs')
        self.assertEqual(items[0]['score'], 100)
        self.assertEqual(items[0]['type'], 'show')
        self.assertEqual(items[0]['ratingKey'], 'show-92')
        self.assertEqual(items[0]['studio'], 'Brazzers')

    def test_match_episode_by_grandparent_and_date(self):
        with mock.patch.object(tpdb, 'search_scenes', return_value=SCENES) as m:
            r = self.app.post('/tv/library/metadata/matches',
                              json={'type': 4,
                                    'grandparentTitle': 'Baby Got Boobs',
                                    'date': '2019-01-25',
                                    'title': 'Squeaky Clean'})
        self.assertIn('Baby Got Boobs', m.call_args[0][0])
        self.assertIn('2019-01-25', m.call_args[0][0])
        top = r.get_json()['MediaContainer']['Metadata'][0]
        self.assertEqual(top['score'], 100)
        self.assertEqual(top['title'], 'Squeaky Clean')
        self.assertEqual(top['index'], 125)
        self.assertEqual(top['parentIndex'], 2019)
        self.assertEqual(top['grandparentTitle'], 'Baby Got Boobs')
        self.assertEqual(top['type'], 'episode')

    def test_episode_date_pulled_from_filename(self):
        with mock.patch.object(tpdb, 'search_scenes', return_value=SCENES) as m:
            self.app.post('/tv/library/metadata/matches',
                          json={'type': 4, 'grandparentTitle': 'Baby Got Boobs',
                                'filename': 'Baby Got Boobs - 2019-04-05 - Sauna [WEBDL-1080p].mp4'})
        self.assertIn('2019-04-05', m.call_args[0][0])

    def test_match_season(self):
        with mock.patch.object(tpdb, 'search_sites', return_value=SITES):
            r = self.app.post('/tv/library/metadata/matches',
                              json={'type': 3, 'parentTitle': 'Baby Got Boobs',
                                    'index': 2019})
        item = r.get_json()['MediaContainer']['Metadata'][0]
        self.assertEqual(item['type'], 'season')
        self.assertEqual(item['index'], 2019)
        self.assertEqual(item['ratingKey'], 'season-92-2019')
        self.assertEqual(item['parentRatingKey'], 'show-92')

    def test_wrong_type_returns_empty(self):
        r = self.app.post('/tv/library/metadata/matches',
                          json={'type': 1, 'title': 'x'})
        self.assertEqual(r.get_json()['MediaContainer']['size'], 0)

    def test_metadata_dispatch(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'get_scene', return_value=SCENES[0]):
            show = self.app.get('/tv/library/metadata/show-92').get_json()
            season = self.app.get('/tv/library/metadata/season-92-2019').get_json()
            ep = self.app.get('/tv/library/metadata/ep-aaa').get_json()
        self.assertEqual(show['MediaContainer']['Metadata'][0]['type'], 'show')
        self.assertEqual(season['MediaContainer']['Metadata'][0]['type'], 'season')
        e = ep['MediaContainer']['Metadata'][0]
        self.assertEqual(e['type'], 'episode')
        self.assertEqual(e['duration'], 1800000)
        self.assertEqual(e['grandparentRatingKey'], 'show-92')
        self.assertEqual(e['parentRatingKey'], 'season-92-2019')
        self.assertEqual([g['tag'] for g in e['Genre']], ['Anal'])
        self.assertEqual(e['Role'][0]['tag'], 'P One')

    def test_guids_follow_scheme(self):
        with mock.patch.object(tpdb, 'get_scene', return_value=SCENES[0]):
            e = self.app.get('/tv/library/metadata/ep-aaa').get_json()['MediaContainer']['Metadata'][0]
        ident = tv.config.tv_identifier
        self.assertEqual(e['guid'], '%s://episode/ep-aaa' % ident)
        self.assertEqual(e['parentGuid'], '%s://season/season-92-2019' % ident)
        self.assertEqual(e['grandparentGuid'], '%s://show/show-92' % ident)

    def test_show_children_are_seasons_grouped_by_year(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/show-92/children')
        items = r.get_json()['MediaContainer']['Metadata']
        self.assertEqual([i['index'] for i in items], [2019, 2020])
        self.assertEqual([i['leafCount'] for i in items], [2, 1])

    def test_season_children_are_that_years_episodes_in_date_order(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/season-92-2019/children')
        items = r.get_json()['MediaContainer']['Metadata']
        self.assertEqual([i['index'] for i in items], [125, 405])
        self.assertEqual(r.get_json()['MediaContainer']['totalSize'], 2)

    def test_grandchildren_all_episodes_paginated(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/show-92/grandchildren',
                             headers={'X-Plex-Container-Start': '1',
                                      'X-Plex-Container-Size': '1'})
        mc = r.get_json()['MediaContainer']
        self.assertEqual((mc['offset'], mc['size'], mc['totalSize']), (1, 1, 3))
        self.assertEqual(mc['Metadata'][0]['index'], 405)

    def test_404s(self):
        with mock.patch.object(tpdb, 'get_site', return_value=None), \
             mock.patch.object(tpdb, 'get_scene', return_value=None):
            self.assertEqual(self.app.get('/tv/library/metadata/show-1').status_code, 404)
            self.assertEqual(self.app.get('/tv/library/metadata/ep-x').status_code, 404)
            self.assertEqual(self.app.get('/tv/library/metadata/junk').status_code, 404)

    def test_scenes_for_site_survives_a_failed_page(self):
        pages = {
            1: {'data': [scene('a', '2019-01-01', 'a')], 'meta': {'last_page': 3}},
            2: None,
            3: {'data': [scene('c', '2019-03-03', 'c')], 'meta': {'last_page': 3}},
        }
        with mock.patch.object(tpdb, 'get_json',
                               side_effect=lambda p, q=None: pages[q['page']]):
            got = tpdb.scenes_for_site(92)
        self.assertEqual([s['id'] for s in got], ['a', 'c'])

    def test_scenes_for_site_walks_pagination(self):
        pages = {
            1: {'data': [scene('a', '2019-01-01', 'a')], 'meta': {'last_page': 3}},
            2: {'data': [scene('b', '2019-02-02', 'b')], 'meta': {'last_page': 3}},
            3: {'data': [scene('c', '2019-03-03', 'c')], 'meta': {'last_page': 3}},
        }
        with mock.patch.object(tpdb, 'get_json',
                               side_effect=lambda p, q=None: pages[q['page']]):
            got = tpdb.scenes_for_site(92)
        self.assertEqual([s['id'] for s in got], ['a', 'b', 'c'])

    def test_scenes_for_site_respects_page_cap(self):
        page = {'data': [scene('a', '2019-01-01', 'a')], 'meta': {'last_page': 999}}
        calls = []
        def fake(p, q=None):
            calls.append(q['page'])
            return page
        with mock.patch.object(tpdb, 'get_json', side_effect=fake):
            tpdb.scenes_for_site(92, max_pages=4)
        # pages 2..N are fetched concurrently, so order is not guaranteed
        self.assertEqual(sorted(calls), [1, 2, 3, 4])


class PagingTest(unittest.TestCase):
    """Regression: Plex sends paging as query params on GET, not headers."""

    def setUp(self):
        self.app = create_app().test_client()

    def _grandchildren(self, qs='', **kw):
        return self.app.get('/tv/library/metadata/show-92/grandchildren' + qs, **kw)

    def test_query_params_drive_paging(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            a = self._grandchildren('?X-Plex-Container-Start=0&X-Plex-Container-Size=2')
            b = self._grandchildren('?X-Plex-Container-Start=2&X-Plex-Container-Size=2')
        ka = [m['ratingKey'] for m in a.get_json()['MediaContainer']['Metadata']]
        kb = [m['ratingKey'] for m in b.get_json()['MediaContainer']['Metadata']]
        self.assertEqual(len(ka), 2)
        self.assertEqual(len(kb), 1)
        self.assertNotEqual(ka, kb)          # the actual bug: these were equal
        self.assertEqual(a.get_json()['MediaContainer']['offset'], 0)
        self.assertEqual(b.get_json()['MediaContainer']['offset'], 2)

    def test_headers_still_work(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self._grandchildren(headers={'X-Plex-Container-Start': '1',
                                             'X-Plex-Container-Size': '1'})
        self.assertEqual(r.get_json()['MediaContainer']['offset'], 1)

    def test_query_param_beats_header(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self._grandchildren('?X-Plex-Container-Start=2',
                                    headers={'X-Plex-Container-Start': '0'})
        self.assertEqual(r.get_json()['MediaContainer']['offset'], 2)

    def test_plex_asking_for_100_gets_more_than_default_20(self):
        many = [scene('id%d' % i, '2019-%02d-01' % ((i % 12) + 1), 't%d' % i)
                for i in range(60)]
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=many):
            r = self._grandchildren('?X-Plex-Container-Start=0&X-Plex-Container-Size=100')
        mc = r.get_json()['MediaContainer']
        self.assertEqual(mc['size'], 60)
        self.assertEqual(mc['totalSize'], 60)

    def test_extras_is_empty_container_not_404(self):
        r = self.app.get('/tv/library/metadata/show-92/extras')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['MediaContainer']['totalSize'], 0)


class IncludeChildrenTest(unittest.TestCase):
    """Plex fetches season-<id>-<year>?includeChildren=1 and expects the
    episodes inline; without them it sees an empty season and matches nothing."""

    def setUp(self):
        self.app = create_app().test_client()

    def test_season_embeds_its_episodes(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/season-92-2019?includeChildren=1')
        item = r.get_json()['MediaContainer']['Metadata'][0]
        kids = item['Children']['Metadata']
        self.assertEqual([k['index'] for k in kids], [125, 405])
        self.assertTrue(all(k['type'] == 'episode' for k in kids))
        self.assertTrue(all(k['guid'].startswith(tv.config.tv_identifier) for k in kids))

    def test_show_embeds_its_seasons(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/show-92?includeChildren=1')
        kids = r.get_json()['MediaContainer']['Metadata'][0]['Children']['Metadata']
        self.assertEqual([k['index'] for k in kids], [2019, 2020])

    def test_no_children_key_when_not_requested(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/season-92-2019')
        self.assertNotIn('Children', r.get_json()['MediaContainer']['Metadata'][0])

    def test_episode_in_embedded_children_is_fully_identified(self):
        """The whole point: each child is a real TPDB scene, not a stub."""
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/season-92-2019?includeChildren=1')
        ep = r.get_json()['MediaContainer']['Metadata'][0]['Children']['Metadata'][0]
        self.assertEqual(ep['title'], 'Squeaky Clean')
        self.assertEqual(ep['originallyAvailableAt'], '2019-01-25')
        self.assertEqual(ep['duration'], 1800000)
        self.assertEqual(ep['Role'][0]['tag'], 'P One')
        self.assertEqual([g['tag'] for g in ep['Genre']], ['Anal'])
        self.assertTrue(ep['thumb'])


class ChildrenShapeTest(unittest.TestCase):
    """Regression for the bug that broke every season match.

    Plex rejected the whole response with
    'failed to parse JSON response: object expected at 1:44'.
    Column 44 is the '[' in {"MediaContainer":{"Metadata":[{"Children":[
    because Flask sorts keys and Children sorts first.
    """

    def setUp(self):
        self.app = create_app().test_client()

    def test_children_is_an_object_not_an_array(self):
        with mock.patch.object(tpdb, 'search_sites', return_value=[SITE]), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.post('/tv/library/metadata/matches',
                              json={'type': 3, 'parentTitle': 'Baby Got Boobs',
                                    'index': 2019, 'includeChildren': 1})
        kids = r.get_json()['MediaContainer']['Metadata'][0]['Children']
        self.assertIsInstance(kids, dict)
        self.assertEqual(kids['size'], len(kids['Metadata']))
        self.assertEqual(kids['size'], 2)

    def test_byte_44_is_not_a_bracket(self):
        """Guard the exact failure Plex reported."""
        with mock.patch.object(tpdb, 'search_sites', return_value=[SITE]), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.post('/tv/library/metadata/matches',
                              json={'type': 3, 'parentTitle': 'Baby Got Boobs',
                                    'index': 2019, 'includeChildren': 1})
        raw = r.get_data(as_text=True)
        self.assertTrue(raw.startswith('{"MediaContainer":{"Metadata":[{"Children":{'),
                        'Children must open with { not [ - got: %r' % raw[:60])

    def test_show_children_is_object_too(self):
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            r = self.app.get('/tv/library/metadata/show-92?includeChildren=1')
        kids = r.get_json()['MediaContainer']['Metadata'][0]['Children']
        self.assertIsInstance(kids, dict)
        self.assertEqual(kids['size'], 2)

    def test_every_response_is_valid_json_plex_can_parse(self):
        import json as _json
        with mock.patch.object(tpdb, 'get_site', return_value=SITE), \
             mock.patch.object(tpdb, 'get_scene', return_value=SCENES[0]), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=SCENES):
            for url in ('/tv',
                        '/tv/library/metadata/show-92?includeChildren=1',
                        '/tv/library/metadata/season-92-2019?includeChildren=1',
                        '/tv/library/metadata/ep-aaa',
                        '/tv/library/metadata/show-92/children',
                        '/tv/library/metadata/show-92/grandchildren'):
                raw = self.app.get(url).get_data(as_text=True)
                _json.loads(raw)
                self.assertNotIn('":[{"Children":[', raw, url)


class MalformedDateTests(unittest.TestCase):
    """A single non-string date must not 500 an entire show."""

    def setUp(self):
        self.app = create_app().test_client()
        self.site = {'id': 92, 'name': 'S92'}
        self.good = [{'id': 's%d' % i, 'title': 'S%d' % i,
                      'date': '2019-05-%02d' % (i + 1),
                      'site': {'id': 92, 'name': 'S92'}} for i in range(3)]

    def _serve(self, scenes, url):
        with mock.patch.object(tpdb, 'get_site', return_value=self.site), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=scenes):
            return self.app.get(url)

    def test_bad_date_does_not_break_the_season(self):
        for bad in (20190405, {'y': 2019}, ['2019-05-01']):
            scenes = self.good + [{'id': 'bad', 'title': 'B', 'date': bad}]
            for url in ('/tv/library/metadata/season-92-2019/children',
                        '/tv/library/metadata/show-92?includeChildren=1',
                        '/tv/library/metadata/show-92/grandchildren'):
                resp = self._serve(scenes, url)
                self.assertEqual(resp.status_code, 200, '%r %s' % (bad, url))

    def test_the_good_scenes_still_come_back(self):
        scenes = self.good + [{'id': 'bad', 'title': 'B', 'date': 20190405}]
        resp = self._serve(scenes, '/tv/library/metadata/season-92-2019/children')
        keys = [m['ratingKey']
                for m in resp.get_json()['MediaContainer']['Metadata']]
        for scene in self.good:
            self.assertIn('ep-%s' % scene['id'], keys)

    def test_episodes_for_does_not_mutate_the_caller_list(self):
        scenes = [{'id': 'b', 'date': '2019-05-02', 'site': {'id': 92}},
                  {'id': 'a', 'date': '2019-05-01', 'site': {'id': 92}}]
        before = [s['id'] for s in scenes]
        self._serve(scenes, '/tv/library/metadata/show-92/grandchildren')
        self.assertEqual([s['id'] for s in scenes], before)


class TVMatchPagingTests(unittest.TestCase):
    """Show and episode matches had the same truncate-then-slice bug."""

    def setUp(self):
        self.app = create_app().test_client()
        self.sites = [{'id': i, 'name': 'Site %02d' % i} for i in range(1, 51)]

    def _page(self, start, size):
        with mock.patch.object(tpdb, 'search_sites', return_value=self.sites):
            resp = self.app.post(
                '/tv/library/metadata/matches'
                '?X-Plex-Container-Start=%d&X-Plex-Container-Size=%d' % (start, size),
                json={'type': 2, 'title': 'Site'})
        return resp.get_json()['MediaContainer']

    def test_show_match_page_two_is_not_empty(self):
        self.assertEqual(self._page(0, 5)['size'], 5)
        self.assertEqual(self._page(5, 5)['size'], 5, 'page two came back empty')

    def test_show_match_total_is_not_truncated(self):
        self.assertEqual(self._page(0, 5)['totalSize'], 20)

    def test_show_match_pages_do_not_repeat(self):
        seen = []
        for start in (0, 5, 10, 15):
            seen += [m['ratingKey'] for m in self._page(start, 5)['Metadata']]
        self.assertEqual(len(seen), len(set(seen)))


class SeasonKeyTests(unittest.TestCase):
    """A malformed season ratingKey must 404, not 500.

    make_season int()s the year, so parse_key handing back whatever
    followed 'season-' turned a bad key into an unhandled ValueError.
    """

    def setUp(self):
        self.app = create_app().test_client()
        self.site = {'id': 92, 'name': 'S92'}
        self.scenes = [{'id': 's%d' % i, 'title': 'S%d' % i,
                        'date': '2019-05-%02d' % (i + 1),
                        'site': {'id': 92, 'name': 'S92'}} for i in range(3)]

    def _get(self, url):
        with mock.patch.object(tpdb, 'get_site', return_value=self.site), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=self.scenes):
            return self.app.get(url)

    def test_malformed_year_404s(self):
        for key in ('season-92-20x9', 'season-92-2019extra', 'season-92',
                    'season--2019', 'season-92-19', 'season-'):
            resp = self._get('/tv/library/metadata/%s' % key)
            self.assertEqual(resp.status_code, 404, key)

    def test_malformed_year_404s_on_children_too(self):
        for key in ('season-92-20x9', 'season-92'):
            resp = self._get('/tv/library/metadata/%s/children' % key)
            self.assertEqual(resp.status_code, 404, key)

    def test_a_valid_key_echoes_itself(self):
        resp = self._get('/tv/library/metadata/season-92-2019')
        item = resp.get_json()['MediaContainer']['Metadata'][0]
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(item['ratingKey'], 'season-92-2019')
        self.assertEqual(item['index'], 2019)

    def test_the_response_key_matches_the_request_not_the_site_record(self):
        other = {'id': 999, 'name': 'Renamed'}
        with mock.patch.object(tpdb, 'get_site', return_value=other), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=self.scenes):
            resp = self.app.get('/tv/library/metadata/season-92-2019')
        item = resp.get_json()['MediaContainer']['Metadata'][0]
        self.assertEqual(item['ratingKey'], 'season-92-2019')


class UpstreamFailureTests(unittest.TestCase):
    """A failed site lookup must not read as a legitimately empty season.

    tpdb.get_json returns None for a timeout or 5xx exactly as for a 404,
    so answering 200 with an empty container told Plex the season really
    was empty, and Plex stops rather than retrying.
    """

    def setUp(self):
        self.app = create_app().test_client()

    def _get(self, url):
        with mock.patch.object(tpdb, 'get_site', return_value=None), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=[]):
            return self.app.get(url)

    def test_season_children_404_when_the_site_lookup_fails(self):
        self.assertEqual(
            self._get('/tv/library/metadata/season-92-2019/children').status_code, 404)

    def test_grandchildren_404_when_the_site_lookup_fails(self):
        self.assertEqual(
            self._get('/tv/library/metadata/show-92/grandchildren').status_code, 404)

    def test_show_children_already_404ed_and_still_do(self):
        self.assertEqual(
            self._get('/tv/library/metadata/show-92/children').status_code, 404)


class SiteWalkCachingTests(unittest.TestCase):
    """Serving a show must not re-walk the site for every season."""

    def setUp(self):
        os.environ['TPDB_CACHE_TTL'] = '3600'
        importlib.reload(config_mod)
        importlib.reload(tpdb)
        importlib.reload(tv)
        self.app = create_app().test_client()
        self.scenes = [
            {'id': 's%03d' % i, 'title': 'S%d' % i,
             'date': '%d-05-%02d' % (2019 + (i % 3), (i % 28) + 1),
             'site': {'id': 92, 'name': 'S92'}} for i in range(60)]
        self.pages = 0

    def tearDown(self):
        os.environ['TPDB_CACHE_TTL'] = '0'
        importlib.reload(config_mod)
        importlib.reload(tpdb)
        importlib.reload(tv)

    def _get_json(self, path, params=None):
        if path == '/scenes' and params and 'site_id' in params:
            self.pages += 1
            return {'data': self.scenes, 'meta': {'last_page': 1}}
        return None

    def test_show_and_seasons_walk_the_site_once(self):
        with mock.patch.object(tpdb, 'get_json', side_effect=self._get_json), \
             mock.patch.object(tpdb, 'get_site', return_value={'id': 92, 'name': 'S92'}):
            self.app.get('/tv/library/metadata/show-92?includeChildren=1')
            for year in (2019, 2020, 2021):
                self.app.get('/tv/library/metadata/season-92-%d?includeChildren=1' % year)
        self.assertEqual(self.pages, 1,
                         'the site was walked %d times, expected 1' % self.pages)

    def test_the_cached_list_survives_a_mutating_caller(self):
        with mock.patch.object(tpdb, 'get_json', side_effect=self._get_json):
            first = tpdb.scenes_for_site(92)
            first.reverse()
            del first[0]
            second = tpdb.scenes_for_site(92)
        self.assertEqual(len(second), len(self.scenes))
        self.assertEqual(second[0]['id'], self.scenes[0]['id'])


class EpisodePagingCostTests(unittest.TestCase):
    """A children page must map only the slice it returns."""

    def setUp(self):
        self.app = create_app().test_client()
        self.scenes = [
            {'id': 's%03d' % i, 'title': 'S%d' % i, 'date': '2019-05-%02d' % ((i % 28) + 1),
             'site': {'id': 92, 'name': 'S92'}} for i in range(300)]

    def test_only_the_page_is_built(self):
        built = []
        real = tv.scene_to_episode

        def counting(scene, site=None):
            built.append(scene['id'])
            return real(scene, site)

        with mock.patch.object(tpdb, 'get_site', return_value={'id': 92, 'name': 'S92'}), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=list(self.scenes)), \
             mock.patch.object(tv, 'scene_to_episode', side_effect=counting):
            resp = self.app.get(
                '/tv/library/metadata/show-92/grandchildren'
                '?X-Plex-Container-Start=0&X-Plex-Container-Size=20')
        body = resp.get_json()['MediaContainer']
        self.assertEqual(body['size'], 20)
        self.assertEqual(body['totalSize'], 300)
        self.assertEqual(len(built), 20,
                         'built %d episodes to return 20' % len(built))

    def test_paging_still_covers_everything_exactly_once(self):
        seen = []
        with mock.patch.object(tpdb, 'get_site', return_value={'id': 92, 'name': 'S92'}), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=list(self.scenes)):
            for start in range(0, 300, 50):
                body = self.app.get(
                    '/tv/library/metadata/show-92/grandchildren'
                    '?X-Plex-Container-Start=%d&X-Plex-Container-Size=50' % start
                ).get_json()['MediaContainer']
                seen += [m['ratingKey'] for m in body['Metadata']]
        self.assertEqual(len(seen), 300)
        self.assertEqual(len(set(seen)), 300)

    def test_include_children_still_returns_every_episode(self):
        with mock.patch.object(tpdb, 'get_site', return_value={'id': 92, 'name': 'S92'}), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=list(self.scenes)):
            resp = self.app.get('/tv/library/metadata/season-92-2019?includeChildren=1')
        children = resp.get_json()['MediaContainer']['Metadata'][0]['Children']
        self.assertEqual(children['size'], 300)


class SweepTVTests(unittest.TestCase):
    """TV-side items from the audit sweep."""

    def setUp(self):
        self.app = create_app().test_client()
        self.site = {'id': 92, 'name': 'S92'}
        self.scenes = [{'id': 's%d' % i, 'title': 'S%d' % i,
                        'date': '2019-05-%02d' % (i + 1),
                        'site': {'id': 92, 'name': 'S92'}} for i in range(3)]

    def _get(self, url):
        with mock.patch.object(tpdb, 'get_site', return_value=self.site), \
             mock.patch.object(tpdb, 'scenes_for_site', return_value=list(self.scenes)):
            return self.app.get(url)

    def test_include_children_accepts_every_spelling(self):
        for value in ('1', 'true', 'True', 'YES', 'on'):
            item = self._get('/tv/library/metadata/season-92-2019?includeChildren=%s'
                             % value).get_json()['MediaContainer']['Metadata'][0]
            self.assertIn('Children', item, value)

    def test_include_children_off_means_off(self):
        item = self._get('/tv/library/metadata/season-92-2019?includeChildren=0'
                         ).get_json()['MediaContainer']['Metadata'][0]
        self.assertNotIn('Children', item)

    def test_size_zero_probe_returns_no_items(self):
        body = self._get('/tv/library/metadata/show-92/grandchildren'
                         '?X-Plex-Container-Size=0').get_json()['MediaContainer']
        self.assertEqual(body['size'], 0)
        self.assertEqual(body['totalSize'], 3)

    def test_two_digit_year_is_bounded(self):
        self.assertIsNone(tv._hint_date({'filename': 'Site.98.05.01.scene.mp4'}))
        self.assertEqual(tv._hint_date({'filename': 'Site.24.06.27.scene.mp4'}),
                         '2024-06-27')

    def test_show_match_strips_the_extension(self):
        seen = {}

        def fake(query):
            seen['q'] = query
            return []

        with mock.patch.object(tpdb, 'search_sites', side_effect=fake):
            self.app.post('/tv/library/metadata/matches',
                          json={'type': 2,
                                'filename': '/tv/Baby Got Boobs/BGB.2019-01-25.mkv'})
        self.assertNotIn('.mkv', seen.get('q', ''))


if __name__ == '__main__':
    unittest.main(verbosity=2)

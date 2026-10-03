"""Tests for publish.py: no network, no Airtable.  python3 -m unittest discover -s tools/announcements"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish as P  # noqa: E402

F = P.F
NOW = dt.datetime(2026, 10, 3, 9, 30, tzinfo=dt.timezone.utc)
TODAY = '2026-10-03'


def png(w=4, h=3) -> bytes:
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + b'\xff\x00\x00' * w for _ in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def jpg(w=640, h=480) -> bytes:
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\0\x01\x01\0\0\x01\0\x01\0\0'
    sof0 = b'\xff\xc0' + struct.pack('>HBHHB', 17, 8, h, w, 3) + b'\x01\x22\x00\x02\x11\x01\x03\x11\x01'
    return b'\xff\xd8' + app0 + sof0 + b'\xff\xd9'


def rec(rid, created='2026-10-03T08:00:00.000Z', status='Publish', **kw):
    f = {F['heading']: 'Summer School 2027', F['text']: 'Five days of hands-on XPS.\nPlaces are limited.',
         F['expires']: '2027-04-01', F['audience']: 'Everyone', F['status']: status, F['created']: created}
    for k, v in kw.items():
        if v is None:
            f.pop(F[k], None)
        else:
            f[F[k]] = v
    return {'id': rid, 'createdTime': created, 'fields': f}


def att(url='https://v5.airtableusercontent.com/x/pic.png', name='pic.png'):
    return [{'id': 'att1', 'url': url, 'filename': name}]


def no_image(url):
    raise AssertionError('no picture should be downloaded')


def feeds_from(p, before=None):
    """The feeds after applying plan p to `before` ({name: (msg, bytes)})."""
    out = dict(before or {n: (None, None) for n in P.FEEDS})
    for n in P.FEEDS:
        if n in p['files']:
            data = p['files'][n]
            out[n] = (None, None) if data is None else (P.parse_feed(data), data)
    return out


def applied(records, p):
    """The records as Airtable holds them after the write-back."""
    out = []
    for r in records:
        r = json.loads(json.dumps(r))
        r['fields'].update(p['updates'].get(r['id'], {}))
        out.append(r)
    return out


EMPTY = {n: (None, None) for n in P.FEEDS}


class Parser(unittest.TestCase):
    """The port of news::parse, on the cases test_announcements.cpp checks."""
    today = '2026-09-29'
    good = ('HXPS-ANNOUNCEMENT-2\r\nid: summer-school-2027\r\nExpires: 2027-04-01\r\n'
            'title: HarwellXPS Summer School 2027\r\nimage: images/summer-school-2027.png\r\n'
            'link: https://www.harwellxps.uk/summer-school\r\nbutton: Register\r\ncolour: blue\r\n\r\n'
            'Five days of hands-on XPS.\r\nPlaces are limited.\r\n\r\n')

    def parse(self, s, today=None):
        return P.parse_feed(s.encode('utf-8') if isinstance(s, str) else s, self.today if today is None else today)

    def test_format1(self):
        m = self.parse('HXPS-ANNOUNCEMENT-1\nsummer-school-2027\n2027-08-01\nSummer school\nJoin us for XPS training.')
        self.assertEqual((m['id'], m['format'], m['image'], m['link']), ('summer-school-2027', 1, '', ''))
        self.assertIsNone(self.parse('HXPS-ANNOUNCEMENT-1\nx\n2020-08-01\nOld\nExpired'))
        self.assertIsNone(self.parse('a' * 17000))

    def test_format2(self):
        m = self.parse(self.good)
        self.assertEqual(m['title'], 'HarwellXPS Summer School 2027')
        self.assertEqual((m['image'], m['link'], m['button']),
                         ('images/summer-school-2027.png', 'https://www.harwellxps.uk/summer-school', 'Register'))
        self.assertEqual(m['body'], 'Five days of hands-on XPS.\r\nPlaces are limited.')
        self.assertEqual(self.parse(b'\xef\xbb\xbf' + self.good.encode())['id'], 'summer-school-2027')

    def test_format2_rejections(self):
        g = self.good
        for bad in (g.replace('https://www.harwellxps.uk', 'http://www.harwellxps.uk'),
                    g.replace('www.harwellxps.uk', 'harwellxps.uk.evil.example'),
                    g.replace('www.harwellxps.uk', 'user@harwellxps.uk'),
                    g.replace('www.harwellxps.uk', 'harwellxps.uk:8443'),
                    g.replace('images/summer-school-2027.png', '../x.png'),
                    g.replace('images/summer-school-2027.png', '/x.png'),
                    g.replace('images/summer-school-2027.png', 'images/x.gif'),
                    g.replace('Register', 'R' * 33),
                    g.replace('link: https://www.harwellxps.uk/summer-school\r\n', ''),
                    g.replace('\r\n\r\nFive', '\r\nno colon\r\n\r\nFive'),
                    g.replace('2027-04-01', '2027-13-01'),
                    g.replace('\r\n\r\nFive', 'Five'),
                    g.replace('summer-school-2027\r\n', 'summer school\r\n'),
                    g.split('\r\n\r\n')[0] + '\r\n\r\n'):
            self.assertIsNone(self.parse(bad), bad[:120])
        self.assertIsNotNone(self.parse(g.replace('www.harwellxps.uk/summer-school', 'github.com/harwellxps-hub/x')))
        self.assertIsNone(self.parse(g.replace('www.harwellxps.uk/summer-school', 'github.com/someone/x')))
        m = self.parse(g.replace('button: Register\r\n', ''))
        self.assertEqual(m['button'], 'Find out more')

    def test_lengths_are_utf16(self):
        t = self.good.replace('HarwellXPS Summer School 2027', '\U0001F600' * 70)    # 140 units
        self.assertIsNotNone(self.parse(t))
        self.assertIsNone(self.parse(self.good.replace('HarwellXPS Summer School 2027', '\U0001F600' * 71)))


class Publishing(unittest.TestCase):
    def run_plan(self, records, feeds=EMPTY, fetch=no_image, now=NOW, today=TODAY):
        return P.plan(records, feeds, today, now, fetch)

    def test_everyone_with_picture(self):
        r = rec('recA', image=att(), link='https://www.harwellxps.uk/summer-school', button='Register')
        p = self.run_plan([r], fetch=lambda url: png())
        u = p['updates']['recA']
        mid = u[F['msgid']]
        self.assertTrue(mid.startswith('summer-school-2027-20261003-'), mid)
        self.assertEqual(u[F['status']], 'Published')
        self.assertIs(u[F['again']], False)
        self.assertIn('both feeds', u[F['note']])
        self.assertEqual(set(p['files']), {P.PUBLIC, P.TEAM, 'images/%s.png' % mid})
        self.assertEqual(p['files'][P.PUBLIC], p['files'][P.TEAM])
        m = P.parse_feed(p['files'][P.PUBLIC], TODAY)
        self.assertEqual((m['title'], m['image'], m['button'], m['expires']),
                         ('Summer School 2027', 'images/%s.png' % mid, 'Register', '2027-04-01'))
        self.assertEqual(m['body'], 'Five days of hands-on XPS.\r\nPlaces are limited.')
        self.assertEqual(p['published'], ['recA'])
        self.assertEqual(p['keep_images'], {'images/%s.png' % mid})

    def test_team_only(self):
        p = self.run_plan([rec('recA', audience='Team (testing edition)')])
        self.assertEqual(set(p['files']), {P.TEAM})
        self.assertIn('team feed is read by testing-edition builds', p['updates']['recA'][F['note']])

    def test_link_without_button_gets_the_default(self):
        p = self.run_plan([rec('recA', link='https://harwellxps.guru/auger')])
        self.assertNotIn(b'button:', p['files'][P.PUBLIC])
        self.assertEqual(P.parse_feed(p['files'][P.PUBLIC])['button'], 'Find out more')

    def test_rejections_list_every_reason(self):
        r = rec('recA', heading=None, text='  ', expires='2026-10-02', audience=None,
                link='http://example.com', button='x' * 33)
        p = self.run_plan([r])
        u = p['updates']['recA']
        self.assertEqual(u[F['status']], 'Rejected')
        for words in ('Add a heading', 'Add the text', 'has passed', 'Choose the audience', 'The link must be',
                      'button text is 33'):
            self.assertIn(words, u[F['note']])
        self.assertEqual(p['files'], {})
        self.assertNotIn('recA', p['needs_commit'])

    def test_link_rules(self):
        ok = ['https://www.harwellxps.uk/x', 'https://harwellxps.guru', 'https://HarwellXPS.uk/?a=1',
              'https://github.com/harwellxps-hub/harwellxps-armoury-for-casaxps/releases']
        bad = ['http://www.harwellxps.uk/', 'https://harwellxps.uk.example.com/', 'https://evilharwellxps.uk/',
               'https://github.com/other/x', 'https://harwellxps.uk:444/', 'https://a@harwellxps.uk/',
               'https://www.harwellxps.uk/a b', 'https://www.harwellxps.uk/é', 'https://harwellxps.uK/']
        for link in ok:
            self.assertEqual(P.problems(rec('r', link=link), TODAY), [], link)
        for link in bad:
            self.assertTrue(P.problems(rec('r', link=link), TODAY), link)

    def test_length_limits(self):
        self.assertEqual(P.problems(rec('r', heading='\U0001F600' * 70), TODAY), [])
        self.assertIn('141', P.problems(rec('r', heading='a' * 141), TODAY)[0])
        # a line break counts as two, as the Armoury joins lines with \r\n
        self.assertEqual(P.problems(rec('r', text='a' * 3998 + '\n' + 'b'), TODAY), ['The text is 4001 characters (a line break counts as 2); the limit is 4,000.'])
        self.assertEqual(P.problems(rec('r', text='a' * 3997 + '\nb'), TODAY), [])
        self.assertEqual(P.problems(rec('r', button='b' * 32, link='https://harwellxps.uk'), TODAY), [])
        self.assertEqual(P.problems(rec('r', button='Go'), TODAY), ['The button needs a link.'])

    def test_largest_message_fits(self):
        r = rec('recA', heading='€' * 140, text='€' * 4000, link='https://harwellxps.uk/' + 'a' * 470,
                button='€' * 32)
        p = self.run_plan([r])
        self.assertEqual(p['updates']['recA'][F['status']], 'Published')
        self.assertLess(len(p['files'][P.PUBLIC]), P.FEED_LIMIT)

    def test_text_is_cleaned(self):
        r = rec('recA', heading='  Two\twords\n here ', text='\n\nLine one\r\nLine\x00 two\x07\n\n\n')
        p = self.run_plan([r])
        m = P.parse_feed(p['files'][P.PUBLIC])
        self.assertEqual(m['title'], 'Two words here')
        self.assertEqual(m['body'], 'Line one\r\nLine two')

    def test_pictures(self):
        cases = [(png(4097, 10), '4097 x 10'), (b'GIF89a' + b'\0' * 20, 'PNG or JPG'),
                 (png() + b'\0' * P.IMAGE_LIMIT, 'over 1 MB')]
        for data, words in cases:
            p = self.run_plan([rec('recA', image=att())], fetch=lambda url, d=data: d)
            self.assertEqual(p['updates']['recA'][F['status']], 'Rejected')
            self.assertIn(words, p['updates']['recA'][F['note']])
        p = self.run_plan([rec('recA', image=att() + att())], fetch=lambda url: jpg())
        mid = p['updates']['recA'][F['msgid']]
        self.assertIn('images/%s.jpg' % mid, p['files'])
        self.assertIn('Only the first of the 2 pictures', p['updates']['recA'][F['note']])

    def test_download_failure_is_retried(self):
        def fail(url):
            raise OSError('timed out')
        p = self.run_plan([rec('recA', image=att())], fetch=fail)
        self.assertEqual(p['updates']['recA'], {F['note']: p['updates']['recA'][F['note']]})
        self.assertIn('trying again', p['updates']['recA'][F['note']])
        self.assertEqual(p['files'], {})

    def test_ids(self):
        r = rec('recA')
        a = self.run_plan([r], now=NOW)['updates']['recA'][F['msgid']]
        b = self.run_plan([r], now=NOW + dt.timedelta(hours=5))['updates']['recA'][F['msgid']]
        self.assertEqual(a, b, 'a failed write-back must not lead to a second id')
        self.assertTrue(P.valid_id(a) and len(a) <= 80)
        again = self.run_plan([rec('recA', msgid=a)])['updates']['recA'][F['msgid']]
        self.assertEqual(again, a, 'a corrected message keeps its id')
        a2 = self.run_plan([rec('recA', msgid=a, again=True)])['updates']['recA'][F['msgid']]
        self.assertEqual(a2, a + '-2')
        a3 = self.run_plan([rec('recA', msgid=a2, again=True)])['updates']['recA'][F['msgid']]
        self.assertEqual(a3, a + '-3')
        other = self.run_plan([rec('recB')])['updates']['recB'][F['msgid']]
        self.assertNotEqual(other, a)
        long = self.run_plan([rec('recC', heading='x' * 140)])['updates']['recC'][F['msgid']]
        self.assertTrue(P.valid_id(long) and len(long) <= 80, long)
        sym = self.run_plan([rec('recD', heading='Ångström & \U0001F600')])['updates']['recD'][F['msgid']]
        self.assertTrue(P.valid_id(sym), sym)

    def test_withdraw(self):
        first = [rec('recA', image=att())]
        p1 = self.run_plan(first, fetch=lambda url: png())
        feeds = feeds_from(p1)
        mid = p1['updates']['recA'][F['msgid']]
        records = applied(first, p1)
        records[0]['fields'][F['status']] = 'Withdraw'
        p2 = self.run_plan(records, feeds)
        self.assertEqual(p2['files'], {P.PUBLIC: None, P.TEAM: None})
        self.assertEqual(p2['keep_images'], set())
        self.assertEqual(p2['updates']['recA'][F['status']], 'Withdrawn')
        self.assertIn('Taken out of both feeds', p2['updates']['recA'][F['note']])
        self.assertTrue(mid)
        p3 = self.run_plan([rec('recZ', status='Withdraw')])
        self.assertIn('nothing to take out', p3['updates']['recZ'][F['note']])
        self.assertEqual(p3['files'], {})

    def test_replacement_and_partial_replacement(self):
        p1 = self.run_plan([rec('recA')])
        records = applied([rec('recA')], p1)
        feeds = feeds_from(p1)
        # a team message takes the team feed only; A stays Published, with a note
        b = rec('recB', created='2026-10-03T09:00:00.000Z', heading='Team test', audience='Team (testing edition)')
        p2 = self.run_plan(records + [b], feeds)
        self.assertEqual(set(p2['files']), {P.TEAM})
        self.assertNotIn(F['status'], p2['updates']['recA'])
        self.assertIn('Still in the public feed; replaced by "Team test" in the team feed', p2['updates']['recA'][F['note']])
        records, feeds = applied(records + [b], p2), feeds_from(p2, feeds)
        # an everyone message replaces both
        c = rec('recC', created='2026-10-03T09:10:00.000Z', heading='Everyone again')
        p3 = self.run_plan(records + [c], feeds)
        self.assertEqual(p3['updates']['recA'][F['status']], 'Withdrawn')
        self.assertEqual(p3['updates']['recB'][F['status']], 'Withdrawn')
        self.assertIn('Replaced by "Everyone again"', p3['updates']['recB'][F['note']])
        records, feeds = applied(records + [c], p3), feeds_from(p3, feeds)
        # and then nothing more to do
        p4 = self.run_plan(records, feeds)
        self.assertEqual((p4['files'], p4['updates'], p4['log']), ({}, {}, []))

    def test_same_run_later_wins(self):
        a = rec('recA', created='2026-10-03T08:00:00.000Z', heading='First')
        b = rec('recB', created='2026-10-03T08:05:00.000Z', heading='Second')
        p = self.run_plan([b, a])
        self.assertEqual(p['updates']['recA'][F['status']], 'Withdrawn')
        self.assertIn('"Second"', p['updates']['recA'][F['note']])
        self.assertEqual(p['updates']['recB'][F['status']], 'Published')
        self.assertEqual(P.parse_feed(p['files'][P.PUBLIC])['title'], 'Second')
        self.assertEqual(p['published'], ['recB'])

    def test_republish_same_text_changes_nothing(self):
        p1 = self.run_plan([rec('recA')])
        records, feeds = applied([rec('recA')], p1), feeds_from(p1)
        records[0]['fields'][F['status']] = 'Publish'
        p2 = self.run_plan(records, feeds)
        self.assertEqual(p2['files'], {})
        self.assertEqual(p2['updates']['recA'][F['status']], 'Published')

    def test_drafts_and_rejected_are_left_alone(self):
        p = self.run_plan([rec('recA', status='Draft'), rec('recB', status='Rejected'), rec('recC', status=None)])
        self.assertEqual((p['files'], p['updates']), ({}, {}))


class Pictures(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(P.image_info(png(17, 9)), ('png', 17, 9))
        self.assertEqual(P.image_info(jpg(1200, 630)), ('jpg', 1200, 630))
        self.assertIsNone(P.image_info(b'<svg/>'))


def remove_tree(path):
    """rmtree that also removes git's read-only object files (Windows)."""
    def writable(func, p, *_):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=writable)
    else:
        shutil.rmtree(path, onerror=writable)


class Repository(unittest.TestCase):
    """write_files, and main --apply against a throwaway remote."""

    def setUp(self):
        real = os.path.join(P.ROOT, 'announcements')
        self.before = sorted(os.listdir(real)) if os.path.isdir(real) else None
        self.addCleanup(lambda: self.assertEqual(sorted(os.listdir(real)) if os.path.isdir(real) else None, self.before))
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(remove_tree, self.tmp)

    def test_write_files(self):
        folder = os.path.join(self.tmp, 'announcements')
        os.makedirs(os.path.join(folder, 'images'))
        for rel, data in (('images/old.png', png()), ('feed.txt', b'same')):
            with open(os.path.join(folder, rel), 'wb') as fh:
                fh.write(data)
        p = {'files': {'feed.txt': b'same', 'feed-testing.txt': b'new', 'images/new.png': png()},
             'keep_images': {'images/new.png'}}
        self.assertEqual(P.write_files(p, folder), ['feed-testing.txt', 'images/new.png', 'images/old.png'])
        self.assertEqual(sorted(os.listdir(os.path.join(folder, 'images'))), ['new.png'])

    def test_main_apply_commits_and_pushes(self):
        def run(*args, cwd=None):
            return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
        remote, work = os.path.join(self.tmp, 'remote.git'), os.path.join(self.tmp, 'work')
        run('git', 'init', '-q', '--bare', '-b', 'main', remote)
        run('git', 'clone', '-q', remote, work)
        run('git', '-C', work, 'checkout', '-q', '-b', 'main')
        os.makedirs(os.path.join(work, 'announcements'))
        with open(os.path.join(work, 'announcements', 'README.md'), 'w') as fh:
            fh.write('x\n')
        run('git', '-C', work, '-c', 'user.name=t', '-c', 'user.email=t@t', 'add', '.')
        run('git', '-C', work, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', 'start')
        run('git', '-C', work, 'push', '-q', 'origin', 'main')
        recs = os.path.join(self.tmp, 'records.json')
        with open(recs, 'w') as fh:
            json.dump({'records': [rec('recA', link='https://harwellxps.uk/x')]}, fh)
        old = (P.ROOT, P.FOLDER, os.environ.get('GITHUB_REF_NAME'))
        P.ROOT, P.FOLDER = work, os.path.join(work, 'announcements')
        os.environ['GITHUB_REF_NAME'] = 'main'
        try:
            self.assertEqual(P.main(['--apply', '--records', recs, '--today', TODAY]), 0)
        finally:
            P.ROOT, P.FOLDER = old[0], old[1]
            if old[2] is None:
                os.environ.pop('GITHUB_REF_NAME', None)
            else:
                os.environ['GITHUB_REF_NAME'] = old[2]
        log = run('git', '--git-dir', remote, 'log', '--format=%an|%s', '-1', 'main')
        self.assertEqual(log, 'HarwellXPS announcements|Announcements: publish "Summer School 2027" (both feeds)')
        files = run('git', '--git-dir', remote, 'ls-tree', '-r', '--name-only', 'main', 'announcements')
        self.assertEqual(files.split('\n'), ['announcements/README.md', 'announcements/feed-testing.txt', 'announcements/feed.txt'])


if __name__ == '__main__':
    unittest.main()

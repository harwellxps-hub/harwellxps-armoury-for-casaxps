#!/usr/bin/env python3
"""Publish the Armoury's startup announcement from Airtable into this repository.

Staff write messages in the Softr staff section (Airtable: base "HarwellXPS Armoury Announcements",
table "Armoury Announcements").  This script, run by .github/workflows/announcements.yml, turns them into the
files the HarwellXPS Armoury for CasaXPS reads once per launch:

    announcements/feed.txt          the public feed (public and, until the next build, testing editions)
    announcements/feed-testing.txt  the team feed (testing edition, from the build after 3 Oct 2026)
    announcements/images/<id>.png   the picture beside the feed

and writes back to each record what happened (Status Published / Rejected / Withdrawn, the reason,
the message id, when, and the commit).

Status in Airtable          what this script does
  Draft                     nothing
  Publish                   checks it; Everyone -> both feeds, Team -> feed-testing.txt only;
                            Published, or Rejected with every reason; a later Publish replaces the
                            message in that feed, and the replaced record becomes Withdrawn
  Withdraw                  takes its message out of every feed that carries it -> Withdrawn

The rules are the Armoury's own (1-armoury-for-casaxps/src/announcements.hpp; docs/ANNOUNCEMENTS.md):
a message that breaks one is skipped silently by every copy, so it is refused here instead, with
the reason, and the feed is parsed again with a line-for-line port of the Armoury's parser before
it is written.  A feed the port cannot read is never committed.

Usage:
    python3 tools/announcements/publish.py --apply        # in the workflow (needs AIRTABLE_TOKEN,
                                                          # AIRTABLE_BASE, AIRTABLE_TABLE; git push)
    python3 tools/announcements/publish.py                # dry run: says what it would do
    python3 tools/announcements/publish.py --records r.json --today 2026-10-03   # offline (tests)

Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, 'announcements')
IMAGES = 'images'

# Airtable field ids (base "HarwellXPS Armoury Announcements" appqTYLsSpCbIGQgi, table "Armoury
# Announcements" tblAu9Oi2YIVY7ugs; a base of its own so the token reaches nothing else).
# Ids, not names, so a field renamed in Airtable does not break publishing.
F = {
    'heading': 'fld367hkmYWUV8dYO', 'image': 'fldq85PbLzCx1k8GZ', 'text': 'fld13B7RVshwMK2jz',
    'link': 'fldzt0DOnWvs1lZH5', 'button': 'flddC7bZtDUfLSwJP', 'expires': 'fldZh174Cy6YJzlQ1',
    'audience': 'fldq4JczgbciDnw4O', 'status': 'fldS1R1k7OQo6rbzo', 'again': 'fldeAf7QLx1pw1eYj',
    'msgid': 'fldTq0wHGJkjqz2Ba', 'note': 'fldZRk8deMBZW1nqH', 'published_at': 'fldJGCWWm4yfFq8AX',
    'commit': 'fldQ03Nu4otLjVCZX', 'created': 'fldz8wH2G1dhA1hfe',
}
PUBLIC, TEAM = 'feed.txt', 'feed-testing.txt'
FEEDS = (PUBLIC, TEAM)
AUDIENCE = {'Everyone': (PUBLIC, TEAM), 'Team (testing edition)': (TEAM,)}
FEED_LIMIT = 16384
IMAGE_LIMIT = 1 << 20
IMAGE_SIDE = 4096
MAGIC = 'HXPS-ANNOUNCEMENT-2'
ALLOWED_LINKS = 'https:// on harwellxps.uk, harwellxps.guru (or a subdomain) or github.com/harwellxps-hub/...'


# ------------------------------------------------------------------ the Armoury's rules (announcements.hpp)
def u16(s: str) -> int:
    """Length as the Armoury counts it: UTF-16 code units (std::wstring on Windows)."""
    return len(s.encode('utf-16-le')) // 2


def valid_id(i: str) -> bool:
    return 0 < len(i) <= 80 and re.fullmatch(r'[A-Za-z0-9_.\-]+', i) is not None


def valid_date(d: str) -> bool:
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', d or ''):
        return False
    return '01' <= d[5:7] <= '12' and '01' <= d[8:10] <= '31'


def link_allowed(url: str) -> bool:
    """news::linkAllowed: https, no credentials or port, harwellxps.uk / .guru (or a subdomain), or
    github.com/harwellxps-hub/..."""
    scheme = 'https://'
    if u16(url) > 500 or url[:len(scheme)].lower() != scheme:
        return False
    if any(c <= ' ' or c in '"<>\\\x7f' for c in url):
        return False
    rest = url[len(scheme):]
    m = re.search(r'[/?#]', rest)
    host, path = (rest[:m.start()], rest[m.start():]) if m else (rest, '')
    host = host.lower()
    if not host or '@' in host or ':' in host:
        return False
    for d in ('harwellxps.uk', 'harwellxps.guru'):
        if host == d or host.endswith('.' + d):
            return True
    return host == 'github.com' and path.lower().startswith('/harwellxps-hub/')


def image_path_allowed(p: str) -> bool:
    if not p or u16(p) > 200 or p[0] == '/' or '..' in p or '//' in p:
        return False
    if re.fullmatch(r'[A-Za-z0-9_./\-]+', p) is None:
        return False
    low = p.lower()
    return any(len(low) > len(e) and low.endswith(e) for e in ('.png', '.jpg', '.jpeg'))


def parse_feed(data: bytes, today: str = '') -> dict | None:
    """Line-for-line port of news::parse for format 2 (and 1): the message dict, or None when the
    Armoury would ignore the feed.  `today` '' = no expiry check (as the preview)."""
    if len(data) > FEED_LIMIT or b'\0' in data:
        return None
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return None
    if text.startswith('﻿'):
        text = text[1:]
    lines = text.split('\n')
    pos = 0

    def line():
        nonlocal pos
        if pos >= len(lines):
            return None
        s = lines[pos]
        pos += 1
        return s[:-1] if s.endswith('\r') else s

    m = {'id': '', 'title': '', 'body': '', 'image': '', 'link': '', 'button': '', 'expires': '', 'format': 0}
    magic = line()
    if magic == 'HXPS-ANNOUNCEMENT-1':
        m['format'] = 1
        m['id'], m['expires'], m['title'] = line() or '', line() or '', line() or ''
    elif magic == MAGIC:
        m['format'] = 2
        saw_blank = False
        while True:
            s = line()
            if s is None:
                break
            if s.strip(' \t') == '':
                saw_blank = True
                break
            if ':' not in s:
                return None
            key, value = s.split(':', 1)
            key, value = key.strip(' \t').lower(), value.strip(' \t')
            if key in ('id', 'expires', 'title', 'image', 'link', 'button'):
                m[key] = value
        if not saw_blank:
            return None
        if m['image'] and not image_path_allowed(m['image']):
            return None
        if m['link'] and not link_allowed(m['link']):
            return None
        if u16(m['button']) > 32 or (m['button'] and not m['link']):
            return None
        if m['link'] and not m['button']:
            m['button'] = 'Find out more'
    else:
        return None
    if not valid_id(m['id']) or not m['title'] or u16(m['title']) > 140 or not valid_date(m['expires']):
        return None
    if today and m['expires'] < today:
        return None
    body = ''
    while True:
        s = line()
        if s is None:
            break
        if body:
            body += '\r\n'
        body += s
    body = body.rstrip('\r\n')
    if not body or u16(body) > 4000:
        return None
    m['body'] = body
    return m


# ------------------------------------------------------------------ pictures
def image_info(b: bytes):
    """(kind 'png'|'jpg', width, height) for a PNG or JPEG, else None."""
    if b[:8] == b'\x89PNG\r\n\x1a\n' and len(b) >= 24 and b[12:16] == b'IHDR':
        w, h = struct.unpack('>II', b[16:24])
        return 'png', w, h
    if b[:3] == b'\xff\xd8\xff':
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack('>H', b[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack('>HH', b[i + 5:i + 9])
                return 'jpg', w, h
            i += 2 + seg
        return 'jpg', 0, 0
    return None


# ------------------------------------------------------------------ records -> messages
def clean(s) -> str:
    """Airtable text without control characters (tabs and line breaks kept), line breaks as \n."""
    s = '' if s is None else str(s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    return ''.join(c for c in s if (c in '\n\t' or ord(c) >= 32) and c != '\x7f' and not 0xD800 <= ord(c) <= 0xDFFF)


def one_line(s) -> str:
    return re.sub(r'\s+', ' ', clean(s)).strip()


def slug(s: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s[:40].rstrip('-') or 'announcement'


def field_name(v) -> str:
    """A single select as the REST API returns it (a string; a {name} dict is accepted too)."""
    return (v.get('name') or '') if isinstance(v, dict) else (v or '')


def status_of(rec: dict) -> str:
    return field_name(rec['fields'].get(F['status']))


def message_id(rec: dict, heading: str, taken: set) -> str:
    """The id the record's message goes out under.

    Kept from its last publication, so a corrected message is not shown again to people who have
    already seen it, unless "Show again to everyone" is ticked: then the next number.  Built from
    the record (heading, creation date, a tag from the record id), not the clock, so a run whose
    write-back to Airtable failed publishes the same id again on the next run, not a new one."""
    f = rec['fields']
    old = one_line(f.get(F['msgid']))
    if old and valid_id(old) and not f.get(F['again']):
        return old
    created = re.sub(r'[^0-9]', '', (f.get(F['created']) or rec.get('createdTime') or '')[:10]) or '0'
    stem = '%s-%s-%s' % (slug(heading), created, hashlib.sha1(rec['id'].encode('utf-8')).hexdigest()[:6])
    n = 1
    if old:
        m = re.fullmatch(re.escape(stem) + r'(?:-([0-9]+))?', old)
        if m:
            n = int(m.group(1) or 1) + 1
    while True:
        candidate = stem if n == 1 else '%s-%d' % (stem, n)
        if candidate not in taken and candidate != old:
            return candidate
        n += 1


def local_stamp(now: dt.datetime) -> str:
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo('Europe/London')).strftime('%d %b %Y, %H:%M UK time')
    except Exception:                                      # no time-zone data on this machine
        return now.astimezone(dt.timezone.utc).strftime('%d %b %Y, %H:%M UTC')


def feeds_text(names) -> str:
    names = list(names)
    if set(names) == {PUBLIC, TEAM}:
        return 'both feeds'
    return ' and '.join({PUBLIC: 'the public feed', TEAM: 'the team feed'}[n] for n in names)


def problems(rec: dict, today: str) -> list:
    """Every reason the Armoury would not show this record (text fields only; the picture is
    checked once it has been downloaded)."""
    f, out = rec['fields'], []
    heading, text = one_line(f.get(F['heading'])), clean(f.get(F['text'])).strip('\n')
    link, button = one_line(f.get(F['link'])), one_line(f.get(F['button']))
    expires = one_line(f.get(F['expires']))
    if not heading:
        out.append('Add a heading.')
    elif u16(heading) > 140:
        out.append('The heading is %d characters; the limit is 140.' % u16(heading))
    body_len = u16(text.replace('\n', '\r\n'))
    if not text.strip():
        out.append('Add the text.')
    elif body_len > 4000:
        out.append('The text is %d characters (a line break counts as 2); the limit is 4,000.' % body_len)
    if not expires:
        out.append('Set an expiry date.')
    elif not valid_date(expires):
        out.append('The expiry date %r is not a date.' % expires)
    elif expires < today:
        out.append('The expiry date (%s) has passed.' % expires)
    if field_name(f.get(F['audience'])) not in AUDIENCE:
        out.append('Choose the audience: Everyone, or Team (testing edition).')
    if link and not (link.isascii() and link_allowed(link)):   # ASCII: towlower and str.lower agree there
        out.append('The link must be %s.' % ALLOWED_LINKS)
    if button and not link:
        out.append('The button needs a link.')
    if u16(button) > 32:
        out.append('The button text is %d characters; the limit is 32.' % u16(button))
    return out


def render(msg: dict) -> bytes:
    head = [MAGIC, 'id: ' + msg['id'], 'expires: ' + msg['expires'], 'title: ' + msg['title']]
    if msg.get('image'):
        head.append('image: ' + msg['image'])
    if msg.get('link'):
        head.append('link: ' + msg['link'])
        if msg.get('button'):
            head.append('button: ' + msg['button'])
    return ('\n'.join(head) + '\n\n' + msg['body'] + '\n').encode('utf-8')


def plan(records: list, feeds: dict, today: str, now: dt.datetime, fetch_image) -> dict:
    """Decide everything; touch nothing.  `feeds` = {feed name: (parsed message or None, bytes or None)}
    as they are in the repository; fetch_image(url) -> bytes (raises on failure).

    Returns {'files': {path under announcements/: bytes, or None to delete}, 'keep_images': set,
    'updates': {record id: Airtable fields}, 'published': [record ids], 'needs_commit': set of record
    ids whose update is only true once the commit is pushed, 'log': [lines], 'summary': [phrases]}."""
    files, updates, published, needs_commit, log, summary = {}, {}, [], set(), [], []
    current = {n: (feeds.get(n) or (None, None))[0] for n in FEEDS}
    final = dict(current)                                  # feed name -> message after this run
    stamp = local_stamp(now)
    by_created = sorted(records, key=lambda r: (r['fields'].get(F['created']) or r.get('createdTime') or '', r['id']))

    # 1. Withdraw: take the record's message out of every feed that carries it.
    for r in by_created:
        if status_of(r) != 'Withdraw':
            continue
        f = r['fields']
        mid = one_line(f.get(F['msgid']))
        gone = [n for n in FEEDS if final[n] and mid and final[n]['id'] == mid]
        for n in gone:
            final[n] = None
        updates[r['id']] = {F['status']: 'Withdrawn', F['note']: (
            'Taken out of %s at %s. Copies of the Armoury that have not shown it yet will not show it.' % (feeds_text(gone), stamp)
            if gone else 'It was not in a feed at %s, so there was nothing to take out.' % stamp)}
        needs_commit.add(r['id'])
        log.append('withdraw %s (%s): %s' % (r['id'], mid or 'no message id', ', '.join(gone) or 'not in a feed'))
        if gone:
            summary.append('withdraw "%s"' % one_line(f.get(F['heading'])))

    # 2. Publish, oldest first: a later message replaces an earlier one in the same feed.
    owners = {}                                            # message id -> records that hold it
    for r in records:
        mid = one_line(r['fields'].get(F['msgid']))
        if mid:
            owners.setdefault(mid, set()).add(r['id'])
    assigned, went = set(), {}
    for r in by_created:
        if status_of(r) != 'Publish':
            continue
        f = r['fields']
        errs = problems(r, today)
        img_bytes, img_kind, extra = None, None, ''
        atts = f.get(F['image']) or []
        if atts and not errs:
            a = atts[0]
            try:
                img_bytes = fetch_image(a.get('url'))
            except Exception as e:                         # transient: keep Publish, try again next run
                updates[r['id']] = {F['note']: 'Could not download the picture at %s (%s); trying again on the next run.' % (stamp, e)}
                log.append('retry %s: picture download failed: %s' % (r['id'], e))
                continue
            info = image_info(img_bytes)
            if info is None:
                errs.append('The picture must be a PNG or JPG (%s is neither).' % (a.get('filename') or 'the file'))
            else:
                img_kind, w, h = info
                if len(img_bytes) > IMAGE_LIMIT:
                    errs.append('The picture is over 1 MB; the limit is 1 MB.')
                if w > IMAGE_SIDE or h > IMAGE_SIDE:
                    errs.append('The picture is %d x %d px; the limit is 4096 px a side.' % (w, h))
            if len(atts) > 1:
                extra = ' Only the first of the %d pictures is used.' % len(atts)
        if errs:
            updates[r['id']] = {F['status']: 'Rejected', F['note']: 'Not published (%s):\n- %s' % (stamp, '\n- '.join(errs))}
            log.append('reject %s: %s' % (r['id'], ' | '.join(errs)))
            continue
        heading = one_line(f[F['heading']])
        taken = {i for i, held in owners.items() if held - {r['id']}} | assigned
        mid = message_id(r, heading, taken)
        assigned.add(mid)
        msg = {'id': mid, 'expires': one_line(f[F['expires']]), 'title': heading,
               'link': one_line(f.get(F['link'])), 'button': one_line(f.get(F['button'])),
               'body': clean(f[F['text']]).strip('\n'), 'image': ''}
        if img_bytes is not None:
            msg['image'] = '%s/%s.%s' % (IMAGES, mid, img_kind)
        data = render(msg)
        if parse_feed(data, today) is None:                # cannot happen after problems(); never commit it
            reason = ('too long for the feed (%d bytes; the limit is 16 KB)' % len(data) if len(data) > FEED_LIMIT
                      else 'not readable by the Armoury')
            updates[r['id']] = {F['status']: 'Rejected', F['note']: 'Not published (%s): the message is %s.' % (stamp, reason)}
            log.append('reject %s: %s' % (r['id'], reason))
            continue
        msg['_data'], msg['_image'] = data, img_bytes
        targets = AUDIENCE[field_name(f[F['audience']])]
        for n in targets:
            final[n] = msg
        went[r['id']] = (msg, targets, extra)

    # 2b. What actually went out: a later record in the same run may have taken a feed.
    for rid, (msg, targets, extra) in went.items():
        kept = [n for n in targets if final[n] is msg]
        lost = [n for n in targets if n not in kept]
        later = sorted({final[n]['title'] for n in lost if final[n]})
        needs_commit.add(rid)
        if not kept:
            updates[rid] = {F['status']: 'Withdrawn', F['msgid']: msg['id'], F['again']: False, F['note']: (
                'Not published: "%s", published after it at %s, took its place in %s.' % ('", "'.join(later), stamp, feeds_text(targets)))}
            log.append('overtaken %s (%s)' % (rid, msg['id']))
            continue
        published.append(rid)
        note = 'Published to %s at %s as message %s. Each copy of the Armoury shows it once, at its next launch.' % (
            feeds_text(kept), stamp, msg['id'])
        if lost:
            note += ' "%s", published after it, took its place in %s.' % ('", "'.join(later), feeds_text(lost))
        if kept == [TEAM]:
            note += ' The team feed is read by testing-edition builds made after 3 Oct 2026.'
        updates[rid] = {F['status']: 'Published', F['msgid']: msg['id'], F['again']: False,
                        F['published_at']: now.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        F['note']: note + extra}
        log.append('publish %s -> %s as %s' % (rid, ', '.join(kept), msg['id']))
        summary.append('publish "%s" (%s)' % (msg['title'], feeds_text(kept)))

    # 3. Earlier publications this run displaced.
    for r in records:
        if status_of(r) != 'Published' or r['id'] in updates:
            continue
        mid = one_line(r['fields'].get(F['msgid']))
        was_in = [n for n in FEEDS if mid and current[n] and current[n]['id'] == mid]
        lost = [n for n in was_in if not (final[n] and final[n]['id'] == mid)]
        if not lost:
            continue
        still = [n for n in was_in if n not in lost]
        later = sorted({final[n]['title'] for n in lost if final[n]})
        what = 'replaced by "%s"' % '", "'.join(later) if later else 'taken out'
        needs_commit.add(r['id'])
        if still:
            updates[r['id']] = {F['note']: 'Still in %s; %s in %s at %s.' % (feeds_text(still), what, feeds_text(lost), stamp)}
        else:
            updates[r['id']] = {F['status']: 'Withdrawn', F['note']: '%s%s at %s.' % (what[0].upper(), what[1:], stamp)}
        log.append('displaced %s (%s) from %s' % (r['id'], mid, ', '.join(lost)))

    # 4. Files: the feeds that changed and their pictures; pictures nothing points at go.
    keep = set()
    for n in FEEDS:
        m = final[n]
        if m is not None and m.get('image'):
            keep.add(m['image'])
        if m is current[n]:
            continue
        if m is not None and m.get('_image') is not None:
            files[m['image']] = m['_image']                # written only if its bytes differ
        if m is None or (feeds.get(n) or (None, None))[1] != m['_data']:
            files[n] = None if m is None else m['_data']
    return {'files': files, 'keep_images': keep, 'updates': updates, 'published': published,
            'needs_commit': needs_commit, 'log': log, 'summary': summary}


# ------------------------------------------------------------------ the repository
def read_feeds() -> dict:
    out = {}
    for n in FEEDS:
        p = os.path.join(FOLDER, n)
        data = None
        if os.path.isfile(p):
            with open(p, 'rb') as fh:
                data = fh.read()
        out[n] = (parse_feed(data) if data is not None else None, data)
    return out


def write_files(p: dict, folder: str | None = None) -> list:
    """Apply p['files'] under announcements/, delete pictures nothing refers to; the paths changed."""
    folder, changed = folder or FOLDER, []
    for rel, data in p['files'].items():
        path = os.path.join(folder, rel)
        if data is None:
            if os.path.exists(path):
                os.remove(path)
                changed.append(rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        old = None
        if os.path.isfile(path):
            with open(path, 'rb') as fh:
                old = fh.read()
        if old != data:
            with open(path, 'wb') as fh:
                fh.write(data)
            changed.append(rel)
    img_dir = os.path.join(folder, IMAGES)
    if os.path.isdir(img_dir):
        for name in sorted(os.listdir(img_dir)):
            rel = IMAGES + '/' + name
            if rel not in p['keep_images'] and os.path.isfile(os.path.join(img_dir, name)):
                os.remove(os.path.join(img_dir, name))
                changed.append(rel)
    return changed


def git(*args) -> str:
    return subprocess.run(['git', '-C', ROOT] + list(args), check=True, capture_output=True, text=True).stdout.strip()


def commit(summary: list) -> str:
    """Commit announcements/ and push; one rebase and retry if main moved meanwhile.  The sha."""
    branch = os.environ.get('GITHUB_REF_NAME') or 'main'
    git('add', '-A', 'announcements')
    title = 'Announcements: ' + ('; '.join(summary) or 'tidy')
    if len(title) > 100:
        title = title[:97] + '...'
    git('-c', 'user.name=HarwellXPS announcements', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit', '-m', title, '-m', '\n'.join(summary) + '\n\nPublished from Airtable by tools/announcements/publish.py.')
    try:
        git('push', 'origin', 'HEAD:refs/heads/' + branch)
    except subprocess.CalledProcessError:
        git('pull', '--rebase', 'origin', branch)
        git('push', 'origin', 'HEAD:refs/heads/' + branch)
    return git('rev-parse', 'HEAD')


# ------------------------------------------------------------------ Airtable
def api(method, url, token, body=None):
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode('utf-8'),
                                 headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch_records(base, table, token) -> list:
    out, offset = [], None
    while True:
        q = {'returnFieldsByFieldId': 'true', 'pageSize': '100'}
        if offset:
            q['offset'] = offset
        page = api('GET', 'https://api.airtable.com/v0/%s/%s?%s' % (base, table, urllib.parse.urlencode(q)), token)
        out += page.get('records', [])
        offset = page.get('offset')
        if not offset:
            return out


def update_records(base, table, token, updates: dict):
    items = [{'id': k, 'fields': v} for k, v in updates.items()]
    for i in range(0, len(items), 10):
        api('PATCH', 'https://api.airtable.com/v0/%s/%s' % (base, table), token,
            {'records': items[i:i + 10], 'returnFieldsByFieldId': True})


def download(url: str) -> bytes:
    """An Airtable attachment (its link expires after a few hours, hence the copy in the repository)."""
    if not url or not url.startswith('https://'):
        raise ValueError('no https link to the file')
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as r:
        return r.read(IMAGE_LIMIT + 1)                      # one byte over is enough to say "over 1 MB"


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apply', action='store_true', help='write, commit, push and update Airtable')
    ap.add_argument('--records', help='read records from this JSON file instead of Airtable (tests)')
    ap.add_argument('--today', help='YYYY-MM-DD (UTC) instead of today')
    a = ap.parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)
    today = a.today or now.strftime('%Y-%m-%d')
    base, table, token = os.environ.get('AIRTABLE_BASE'), os.environ.get('AIRTABLE_TABLE'), os.environ.get('AIRTABLE_TOKEN')
    if a.records:
        with open(a.records, encoding='utf-8') as fh:
            records = json.load(fh)
        records = records.get('records', []) if isinstance(records, dict) else records
    else:
        if not (base and table and token):
            print('AIRTABLE_BASE, AIRTABLE_TABLE and AIRTABLE_TOKEN are needed (repository variables and secret).', file=sys.stderr)
            return 2
        records = fetch_records(base, table, token)
    p = plan(records, read_feeds(), today, now, download)
    for line in p['log'] or ['nothing to do']:
        print(line)
    if not a.apply:
        for rel, data in p['files'].items():
            print('--- %s: %s' % (rel, 'delete' if data is None else '%d bytes' % len(data)))
            if data is not None and rel.endswith('.txt'):
                print(data.decode('utf-8'))
        return 0
    write_back = bool(token and not a.records)
    updates = p['updates']
    changed = write_files(p)
    if changed:
        try:
            sha = commit(p['summary'])
        except subprocess.CalledProcessError as e:
            why = (e.stderr or e.stdout or str(e)).strip().splitlines()
            why = why[-1][:200] if why else 'git failed'
            print('commit/push failed: %s' % why, file=sys.stderr)
            # nothing went out: leave Publish / Withdraw as they are so the next run tries again
            updates = {k: {F['note']: 'Publishing failed at %s (%s); trying again on the next run.' % (local_stamp(now), why)}
                       for k in p['needs_commit'] if status_of_id(records, k) in ('Publish', 'Withdraw')}
            updates.update({k: v for k, v in p['updates'].items() if k not in p['needs_commit']})
            if write_back and updates:
                update_records(base, table, token, updates)
            return 1
        server = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
        repo = os.environ.get('GITHUB_REPOSITORY', 'harwellxps-hub/harwellxps-armoury-for-casaxps')
        for k in p['published']:
            updates[k][F['commit']] = '%s/%s/commit/%s' % (server, repo, sha)
        print('committed %s: %s' % (sha[:10], ', '.join(changed)))
    if write_back and updates:
        try:
            update_records(base, table, token, updates)
        except (urllib.error.URLError, OSError) as e:
            # the feed is out; the next run sees the same records and republishes the same ids
            print('the feed is published but Airtable could not be updated: %s' % e, file=sys.stderr)
            return 1
    return 0


def status_of_id(records: list, rid: str) -> str:
    return next((status_of(r) for r in records if r['id'] == rid), '')


if __name__ == '__main__':
    sys.exit(main())

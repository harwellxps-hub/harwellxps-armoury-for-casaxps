# Announcements

The HarwellXPS Armoury for CasaXPS reads one file in this folder once per launch, for its startup
message, and a News list when someone opens News:

| Edition | Startup message | News |
|---|---|---|
| public | `feed.txt` | `news.txt` |
| testing | `feed-testing.txt` (builds from 3 Oct 2026; earlier ones read `feed.txt`) | `news-testing.txt` |

All under `https://raw.githubusercontent.com/harwellxps-hub/harwellxps-armoury-for-casaxps/main/announcements/`.
A missing file is silently ignored. Each message id pops up once per installation; News keeps
every announcement still on offer, expired ones included.

## Do not edit these files by hand

HarwellXPS staff write messages on the Softr staff page (Airtable: HarwellXPS Database, table
*Armoury Announcements*). [`.github/workflows/announcements.yml`](../.github/workflows/announcements.yml)
runs [`tools/announcements/publish.py`](../tools/announcements/publish.py) every 15 minutes: it checks
each message against the Armoury's rules, writes the feeds, the News lists and the pictures in
`images/`, commits as *HarwellXPS announcements*, and reports back to the Airtable record. A hand
edit is overwritten by the next publication, and pictures nothing refers to are deleted.

## The format (for reference)

```text
HXPS-ANNOUNCEMENT-2
id: summer-school-2027-20261003-3fa9c1
expires: 2027-04-01
title: HarwellXPS Summer School 2027
image: images/summer-school-2027-20261003-3fa9c1.png
link: https://www.harwellxps.uk/summer-school
button: Register

Five days of hands-on XPS at the Research Complex at Harwell.
Places are limited — register by 1 March.
```

| Line | Rule |
|---|---|
| `id` | required; letters, digits, `-`, `_`, `.`; up to 80 |
| `expires` | required; `YYYY-MM-DD` (UTC); not shown after that day |
| `title` | required; up to 140 characters |
| `image` | optional; a `.png`/`.jpg` in this folder tree, up to 1 MB and 4096 px; shown up to 512 × 280 |
| `link` | optional; `https://` on harwellxps.uk, harwellxps.guru (or a subdomain) or github.com/harwellxps-hub only |
| `button` | optional; the link button's words (up to 32); default "Find out more"; needs a link |
| blank line | then the message: plain text, up to 4,000 characters; the file under 16 KB |

A bad value makes every copy ignore the whole message, which is why the publisher refuses it first.

The News lists are the same messages, newest first, after a first line `HXPS-NEWS-1` and separated
by lines reading `HXPS-NEWS-ITEM`; each also carries `published: YYYY-MM-DD` and `item: <key>`.

Preview (nothing is fetched or written):

```powershell
HarwellXPS-Armoury.exe --preview-announcement "C:\Users\munke\HarwellXPS Armoury\public-repo\announcements\feed.txt"
HarwellXPS-Armoury.exe --preview-news "C:\Users\munke\HarwellXPS Armoury\public-repo\announcements\news-testing.txt"
```

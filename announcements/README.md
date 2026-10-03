# Announcements feed

The HarwellXPS Armoury for CasaXPS reads one file in this folder once per launch:

| Edition | Feed |
|---|---|
| public | `https://raw.githubusercontent.com/harwellxps-hub/harwellxps-armoury-for-casaxps/main/announcements/feed.txt` |
| testing | `…/announcements/feed-testing.txt` (builds from 3 Oct 2026; earlier ones read `feed.txt`) |

A missing feed is silently ignored. Each message id is shown once per installation; users can turn
announcements off with the tick box in the window.

## Do not edit these files by hand

HarwellXPS staff write messages on the Softr staff page (Airtable: HarwellXPS Database, table
*Armoury Announcements*). [`.github/workflows/announcements.yml`](../.github/workflows/announcements.yml)
runs [`tools/announcements/publish.py`](../tools/announcements/publish.py) every 15 minutes: it checks
each message against the Armoury's rules, writes `feed.txt` / `feed-testing.txt` and the picture in
`images/`, commits as *HarwellXPS announcements*, and reports back to the Airtable record. A hand
edit is overwritten by the next publication, and pictures that neither feed uses are deleted.

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

Preview a feed (nothing is fetched or written):

```powershell
HarwellXPS-Armoury.exe --preview-announcement "C:\Users\munke\HarwellXPS Armoury\public-repo\announcements\feed.txt"
```

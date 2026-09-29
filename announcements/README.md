# Announcements feed

The HarwellXPS Armoury for CasaXPS (public edition) reads `feed.txt` in this folder once per launch:
`https://raw.githubusercontent.com/harwellxps-hub/harwellxps-armoury-for-casaxps/main/announcements/feed.txt`

There is no `feed.txt` until the first real message: a missing feed is silently ignored. Each
message id is shown once per installation; users can turn announcements off with the tick box.

```text
HXPS-ANNOUNCEMENT-2
id: summer-school-2027
expires: 2027-04-01
title: HarwellXPS Summer School 2027
image: images/summer-school-2027.png
link: https://www.harwellxps.uk/summer-school
button: Register

Five days of hands-on XPS at the Research Complex at Harwell.
Places are limited — register by 1 March.
```

| Line | Rule |
|---|---|
| `id` | required; letters, digits, `-`, `_`, `.`; up to 80. A new id for every message. |
| `expires` | required; `YYYY-MM-DD` (UTC); not shown after that day |
| `title` | required; up to 140 characters |
| `image` | optional; a `.png`/`.jpg` in this folder tree (e.g. `images/x.png`), up to 1 MB and 4096 px |
| `link` | optional; `https://` on harwellxps.uk, harwellxps.guru (or a subdomain) or github.com/harwellxps-hub only |
| `button` | optional; the link button's words (up to 32); default "Find out more" |
| blank line | then the message: plain text, up to 4,000 characters; the file under 16 KB |

Preview before pushing (nothing is fetched or written):

```powershell
HarwellXPS-Armoury.exe --preview-announcement "C:\Users\munke\HarwellXPS Armoury\public-repo\announcements\feed.txt"
```

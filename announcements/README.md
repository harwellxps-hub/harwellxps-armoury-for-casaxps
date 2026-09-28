# Announcements feed

The Armoury (public and testing editions) reads `feed.txt` in this folder once per launch:
`https://raw.githubusercontent.com/harwellxps-hub/harwellxps-armoury-for-casaxps/main/announcements/feed.txt`

There is no `feed.txt` until the first real message: a missing feed is silently ignored.

Format, one field per line, UTF-8 plain text, at most 16 KB:

```text
HXPS-ANNOUNCEMENT-1
unique-message-id
2027-08-01
Short title
Your message, with optional further lines.
```

- Line 2: a new ID for every message (letters, digits, `-`, `_`, `.`; up to 80 characters). Each ID is shown once per computer.
- Line 3: expiry date (UTC, `YYYY-MM-DD`); expired messages are ignored.
- Title up to 140 characters; body up to 4,000. Plain text only: nothing in it can run.

Images and a link button are planned for the first public release; this file will document the extra
fields when they exist. Images will live in `announcements/images/`.

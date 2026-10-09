# HarwellXPS Armoury for CasaXPS

Add tools to CasaXPS and get more out of it. The Armoury is a small Windows program from
[HarwellXPS](https://www.harwellxps.uk), the UK's national XPS facility. It docks your own licensed
copy of CasaXPS and runs HarwellXPS tools alongside it, with a Sample Library to keep your spectra,
samples and analyses together.

Free to use. Please read "Using it in your work" below.

## What you need

- Windows 10 or 11, 64-bit
- A licensed installation of CasaXPS (not included; the Armoury never changes Casa or its licence)
- Microsoft Edge WebView2 Runtime (already on most Windows 10/11 machines) for the in-app tools

## Install

1. Download the ZIP from the Releases page (or SourceForge). You can check it against the `.sha256` file.
2. Extract the **whole** ZIP to a folder you can write to (for example `Documents\HarwellXPS Armoury`).
   Do not run it from inside the ZIP.
3. Run `HarwellXPS-Armoury.exe`.

There is no installer and it does not need administrator rights. If Windows shows a SmartScreen
warning the first time, choose **More info**, then **Run anyway**.

## What is included

| Tool | What it does |
|---|---|
| XPS Import | Opens Thermo Avantage (.VGD) folders and Kratos ESCApe (.experiment) files in CasaXPS; name your samples, define experimental variables, and group spectra into VAMAS files |
| Lineshape Tester | Tests and optimises Casa lineshape parameters, with shared groups and doublet constraints |
| Spectrum Plotter | Publication figures from Casa fits: overlays, stacks, panels; SVG, PNG and Excel export |
| Sample Library | A folder of your own for imported spectra, samples, sessions and analyses. On by default; choose its folder in the Library settings |

More tools (for example Correlation Analysis) are released separately as individual downloads and
added from the Plugin manager.

## The Sample Library

- It is a folder you choose, on your own computer. Nothing in it is sent anywhere.
- Raw data is never changed. Files are copied in, checked with SHA-256 before and after copying, and
  stored read-only. **Check library** re-verifies every file at any time.
- Nothing is deleted: records are archived, and anything damaged is reported, never silently replaced.
- Avoid a folder synced by OneDrive, Dropbox, Box, Google Drive or iCloud while the library is in use.

## Plugins and safety

A copy of the Armoury only runs plugin versions HarwellXPS has approved and signed; modified or
unapproved packages are refused. `SECURITY.md` in the download describes exactly what runs, what
plugins may ask Casa to do, and what leaves your computer.

## What leaves your computer

Once per launch the Armoury fetches two small signed text files from this repository over HTTPS: the
announcement feed (occasional HarwellXPS news such as training courses; **News** in the Armoury lists
earlier ones) and the list of current plugin versions. Nothing about you or your computer is sent.
Both can be turned off in `armour.ini`.

## Using it in your work

The Armoury and its tools are free to use. HarwellXPS is funded by EPSRC and asks that you acknowledge
it in publications that use these tools: please include one or more of the HarwellXPS grant codes
listed at [harwellxps.uk](https://www.harwellxps.uk) in your acknowledgements.

The software is provided as it is, with no warranty. Check your own results; you are responsible for
the analysis you publish.

## This repository

It holds the downloads, the plugin packages and the Armoury's announcement feed. The program itself is
distributed as a ready-to-run download.

- [`downloads/`](downloads/): released builds, each with a `.sha256` checksum
- [`plugins/`](plugins/): signed plugin packages
- [`announcements/`](announcements/): the announcement feed

## Not a Casa Software product

CasaXPS is a product of Casa Software Ltd. The HarwellXPS Armoury for CasaXPS is an independent tool
and is not made or endorsed by Casa Software Ltd.

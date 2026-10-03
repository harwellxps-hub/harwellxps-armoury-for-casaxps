# HarwellXPS Armoury for CasaXPS

Add plugins to CasaXPS and get more out of it. The Armoury is a small Windows program from
[HarwellXPS](https://www.harwellxps.uk), the EPSRC national facility for photoelectron spectroscopy.
It docks your own licensed copy of CasaXPS and runs HarwellXPS plugins alongside it.

This repository holds the downloads, the plugin packages and the Armoury's announcement feed.

## What you need

- Windows 10 or 11, 64-bit
- A licensed installation of CasaXPS (not included; the Armoury never changes Casa or its licence)
- Microsoft Edge WebView2 Runtime (already on most Windows 10/11 machines) for the in-app tools

## Included tools

| Tool | What it does |
|---|---|
| XPS Import | Opens Thermo Avantage (.VGD) folders and Kratos ESCApe (.experiment) files in CasaXPS |
| Lineshape Tester | Optimises Casa lineshape parameters, with shared groups and doublet constraints |
| Correlation Analysis | Correlation and phase-model analysis of fitted VAMAS series (Bhatt, Isaacs, Liu and Palgrave, 2024) |
| Spectrum Plotter | Publication figures from Casa fits: overlays, stacks, panels; SVG, PNG and Excel export |

## Downloads

See [`downloads/`](downloads/) and the Releases page. Extract the whole ZIP to a folder you can write to
and run `HarwellXPS-Armoury.exe`.

## Plugins

Plugin packages are in [`plugins/`](plugins/). A copy of the Armoury only runs plugin versions
HarwellXPS has approved; modified packages are refused.

## Announcements

Once per launch the Armoury fetches [`announcements/feed.txt`](announcements/) from this repository
over HTTPS, to show occasional HarwellXPS news (training courses, new plugins). Nothing about you or
your computer is sent. Tick *Don't show announcements again* in the window, or set `Enabled=0` under
`[Announcements]` in `armour.ini`, to stop it.

## Not a Casa Software product

CasaXPS is a product of Casa Software Ltd. The HarwellXPS Armoury for CasaXPS is an independent tool
and is not made or endorsed by Casa Software Ltd.

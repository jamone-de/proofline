# Design notes

Result of the short style check (step 0). Sources: the JamOneAI website (jamoneai.de, read in the browser, CSS custom properties inspected) and the Defconder project (README, dashboard build). A project literally named Agentwarden or custodoc does not exist as a folder under C:\Projekte; both only appear as product colors on jamoneai.de (`--color-agentwarden: #ef4444`, `--color-custodoc: #0e7490`), so nothing more could be learned from them.

What the style looks like and how Brightshop applies it:

- **Typeface.** IBM Plex Sans everywhere, IBM Plex Mono for identifiers (order numbers, SKUs, bins). Headlines are tight (negative letter spacing) and heavy. The fonts are bundled as woff2 (SIL OFL) so the app works offline.
- **Palette.** Deep navy ink `#0a1f3b`, a calm blue primary `#1b4e8c`, one warm gold accent `#b8956a`, cool greys (`#f4f6f8`, `#dbe0e5`). Semantic colors are muted (green `#2e7d5b`, red `#b23a3a`, amber `#b8863a`). Brightshop uses navy for the side rail and primary buttons and gold only as the single accent (brand mark, active nav marker, eyebrow labels, highlighted KPI).
- **Shape and density.** 6 to 10 px radii, 1 px hairline borders, very soft shadows, generous whitespace but compact tables. Cards on a light grey canvas, never boxes inside boxes.
- **Hierarchy.** Small uppercase tracked eyebrow labels above large page titles; numbers are tabular and set large in KPI cards; muted secondary text under primary values.
- **Sober tone.** No gradients, no illustrations, no emoji. Status is communicated with small soft badges, not loud colors.
- **Theming.** Light by default with a matching dark theme (navy surfaces, the gold lifts slightly). Follows the OS setting, with a manual toggle stored in localStorage.
- **Docs and tooling.** READMEs are short and structural (what lives where, how to start), German for concept documents, one-command starts (`start.bat`-style). Brightshop keeps the README in English as requested and ships one obvious command (`python -m brightshop`).

# Documentation site

The browsable docs for [`bcgov/agent-skills`](https://github.com/bcgov/agent-skills).
Built with a **zero-dependency template engine** (Bash + a tiny Node script)
and served from GitHub Pages.

## TL;DR

```bash
cd docs
./build.sh         # build the static site + search index
open index.html    # macOS — use xdg-open on Linux, start on Windows
```

## What's in here

```
docs/
├── _partials/                 # Shared header + footer (injected into every page)
│   ├── header.html
│   └── footer.html
│
├── _pages/                    # Source content — one file per page
│   ├── _template.html         # Starter for new pages (skipped by build)
│   ├── index.html             # Home
│   ├── catalog.html           # Skill catalog
│   ├── consume.html           # How to install a skill
│   ├── contribute.html        # How to add a skill
│   ├── spec.html              # SKILL.md spec summary
│   ├── architecture.html      # Pipeline & governance
│   └── faq.html               # FAQ
│
├── assets/                    # Static assets shipped as-is
│   ├── bc_citz_logo.jpg
│   ├── favicon.svg
│   ├── search.js              # FlexSearch client wiring
│   └── search-index.json      # Generated — full-text search index
│
├── build.sh                   # Template engine + search index trigger
├── generate-search-index.js   # Node — parses built HTML → search-index.json
├── README.md                  # This file
│
└── *.html                     # Build output, served by GitHub Pages
```

## How the template engine works

Each page in `_pages/` starts with two HTML comments that the build script reads:

```html
<!-- TITLE: My Page Title -->
<!-- NAV: catalog -->

<h1>Page content starts here</h1>
```

| Metadata | What it does                                                |
| -------- | ----------------------------------------------------------- |
| `TITLE`  | Substituted into the `<title>` tag and the visible heading  |
| `NAV`    | Marks the matching nav item as `active` (uppercased: `NAV_CATALOG`) |

`build.sh` then concatenates `_partials/header.html` + page content + `_partials/footer.html`, replaces `{{PAGE_TITLE}}`, `{{NAV_*}}`, and `{{YEAR}}`, and writes the assembled HTML next to itself at `docs/<page>.html`.

After all pages are written, the script invokes `generate-search-index.js`, which:

1. Walks every `*.html` at the docs root.
2. Auto-assigns `id=` attributes to any `h1`/`h2`/`h3` missing one (so deep-links work).
3. Writes `assets/search-index.json`, consumed in the browser by [FlexSearch](https://github.com/nextapps-de/flexsearch) (loaded from a CDN by `assets/search.js`).

## Adding a new page

1. **Create the source file** at `_pages/<slug>.html`:

   ```html
   <!-- TITLE: My New Page -->
   <!-- NAV: mynewpage -->

   <h1>My New Page</h1>
   <p>Use any HTML. The header bundles all CSS.</p>
   ```

2. **Add a nav link** in `_partials/header.html`:

   ```html
   <a href="mynewpage.html" class="{{NAV_MYNEWPAGE}}">My New Page</a>
   ```

3. **Add the clear-line** in `build.sh` so inactive instances render blank:

   ```bash
   header="${header//\{\{NAV_MYNEWPAGE\}\}/}"
   ```

4. **Build and check**:

   ```bash
   ./build.sh
   open mynewpage.html
   ```

The build is fast enough (milliseconds) that there's no watch mode — just re-run `./build.sh`.

## Available CSS classes

The header bundles a small in-house framework — no Tailwind, no external CSS. See `_pages/_template.html` for a live cheat-sheet covering:

- **Layout** — `.grid` / `.grid-2` / `.grid-3` / `.grid-4`
- **Components** — `.card`, `.card-gold`, `.alert .alert-info|alert-warning|alert-success`, `.badge .badge-gold|badge-blue`
- **Interactive** — `.card-link`, `.card-arrow`, `.feature-icon`, `.hero`
- **Typography** — `h1`–`h3` styled defaults, `code`, `pre`, `table`

## Deployment

GitHub Pages runs `./build.sh` on every push to `main` that touches `docs/**` and publishes the output. The workflow lives at `.github/workflows/pages.yml`.

## Why Bash instead of Jekyll/Hugo/etc?

1. **Tiny footprint** — Bash + Node, no plugin ecosystem to keep alive.
2. **Runs anywhere** — laptop, WSL, GitHub Actions runner.
3. **Easy to read** — `build.sh` is ~100 lines of plain shell.
4. **Fast** — full rebuild in milliseconds.
5. **GitHub Pages native** — no custom build action required beyond `bash`.

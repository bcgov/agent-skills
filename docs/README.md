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
│   ├── header.html            # Owns the nav block, brand, and bundled CSS
│   └── footer.html
│
├── _pages/                    # Source content — one file per page
│   ├── _template.html         # Starter + live cheat-sheet for components (build skips it)
│   └── <page>.html            # Browse the directory for the current set
│
├── assets/                    # Static assets shipped as-is (favicon, logos, search wiring)
│
├── build.sh                   # Template engine + search index trigger
├── generate-search-index.js   # Node — parses built HTML → search-index.json
├── README.md                  # This file
│
└── *.html                     # Build output, served by GitHub Pages
```

A couple of conventions baked into this layout:

- **`_pages/` is the only place to write content.** Each file becomes one page
  at the docs root; the build script never edits `_pages/` itself.
- **`_partials/` is shared chrome.** A nav, brand, or styling change happens
  once in `header.html` and lands on every page.
- **The root `*.html` files are build output.** Don't edit them by hand;
  they're overwritten on every `./build.sh`.

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

   Crib from [`_pages/_template.html`](_pages/_template.html) for the
   available components (cards, alerts, badges, grids, hero, etc.). It
   doubles as a live cheat-sheet, so whatever's there is what you can use.

2. **Add a nav link** in the nav block of `_partials/header.html` (look for
   the existing `<a href="..." class="{{NAV_<NAME>}}">` entries and add yours
   next to them).

3. **Register the clear-line** in `build.sh` next to the existing
   `header="${header//\{\{NAV_<NAME>\}\}/}"` block, so inactive instances of
   the new placeholder render blank instead of leaking through.

4. **Build and check**:

   ```bash
   ./build.sh
   open mynewpage.html
   ```

The build is fast enough (milliseconds) that there's no watch mode; just
re-run `./build.sh`.

## Styling and components

The header bundles a small in-house CSS framework. No Tailwind, no external
stylesheet. The authoritative reference is
[`_pages/_template.html`](_pages/_template.html), which renders every
available component (layout grids, cards, alerts, badges, hero blocks,
typography defaults) in one page. Open it in a browser after a build to see
the full vocabulary; copy the markup from there into your page.

## Deployment

GitHub Pages runs `./build.sh` on every push to `main` that touches
`docs/**`. The Pages workflow lives under
[`.github/workflows/`](../.github/workflows/) and uploads the built `docs/`
directory as the Pages artifact: no separate publish step, no custom build
action beyond Bash + Node.

## Why a small Bash build instead of Jekyll/Hugo/etc?

The footprint stays tiny: Bash plus a small Node script, and no plugin
ecosystem to keep alive. The same command runs on a laptop, in WSL, and on the
GitHub Actions runner, so there's nothing to install before contributing.
`build.sh` is short enough to skim end-to-end in a sitting, and the full
rebuild finishes in milliseconds, which is why there's no watch mode.

It's a deliberately small surface. If the docs ever grow past what `build.sh`
comfortably handles, switching to a real static site generator is a one-time
port rather than a daily tax.

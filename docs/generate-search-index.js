#!/usr/bin/env node
/**
 * generate-search-index.js
 *
 * Parses every built HTML page in the docs directory, auto-adds id= attributes
 * to any h1/h2/h3 that is missing one, and writes assets/search-index.json so
 * the browser can feed it into FlexSearch without any server.
 *
 * Usage:  node generate-search-index.js <docs_dir>
 * Called from build.sh after all pages are assembled.
 *
 * No external npm dependencies – only Node.js built-ins.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const BASIC_ENTITY_REPLACEMENTS = {
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
  "&nbsp;": " ",
  "&amp;": "&",
};
const BASIC_ENTITY_RE = /&(lt|gt|quot|#39|nbsp|amp);/g;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Remove HTML tags and decode basic entities. */
function stripHtml(html) {
  return html.replace(/<[^>]+>/g, " ").replace(BASIC_ENTITY_RE, (match) => {
    return BASIC_ENTITY_REPLACEMENTS[match] ?? match;
  });
}

/** Collapse whitespace. */
function norm(str) {
  return str.replace(/\s+/g, " ").trim();
}

/** Convert heading text to a URL-safe slug. */
function slugify(text) {
  return (
    text
      .toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/-{2,}/g, "-")
      .replace(/^-+|-+$/g, "") || "section"
  );
}

/** Return at most maxLen chars of text, breaking at word boundary. */
function excerpt(text, maxLen) {
  maxLen = maxLen || 220;
  text = norm(text);
  if (text.length <= maxLen) return text;
  const cut = text.lastIndexOf(" ", maxLen);
  return text.slice(0, cut > 0 ? cut : maxLen) + "…";
}

// ---------------------------------------------------------------------------
// Per-page processing
// ---------------------------------------------------------------------------

// Matches <h1>, <h2>, <h3> with optional attributes, capturing everything.
const HEADING_RE = /<(h[123])([^>]*)>([\s\S]*?)<\/h[123]>/gi;
const ID_ATTR_RE = /\bid="([^"]+)"/i;
const H1_RE = /<h1[^>]*>([\s\S]*?)<\/h1>/i;
const TITLE_RE = /<title[^>]*>([\s\S]*?)<\/title>/i;

function getPageTitle(html, filename) {
  const h1 = H1_RE.exec(html);
  if (h1) return norm(stripHtml(h1[1]));

  const t = TITLE_RE.exec(html);
  if (t) {
    return norm(stripHtml(t[1]))
      .replace(/\s*\|\s*BC Gov Agent Skills\s*$/, "")
      .trim();
  }
  return filename;
}

function processPage(filepath, filename) {
  let html = fs.readFileSync(filepath, "utf8");

  const pageTitle = getPageTitle(html, filename);

  // Collect all heading matches (positions + content)
  const headingMatches = [];
  let m;
  HEADING_RE.lastIndex = 0;
  while ((m = HEADING_RE.exec(html)) !== null) {
    headingMatches.push({
      index: m.index,
      fullLen: m[0].length,
      tag: m[1], // h1 / h2 / h3
      attrs: m[2], // everything between <hN and >
      inner: m[3], // content between open/close tag
      original: m[0],
    });
  }

  // Pre-collect existing IDs to avoid collisions when generating new ones.
  const usedIds = new Set();
  for (const h of headingMatches) {
    const idM = ID_ATTR_RE.exec(h.attrs);
    if (idM) usedIds.add(idM[1]);
  }

  // Assign an ID to every heading (existing or generated).
  for (const h of headingMatches) {
    const idM = ID_ATTR_RE.exec(h.attrs);
    if (idM) {
      h.sectionId = idM[1];
    } else {
      const base = slugify(norm(stripHtml(h.inner)));
      let candidate = base;
      let counter = 1;
      while (usedIds.has(candidate)) {
        candidate = `${base}-${counter++}`;
      }
      usedIds.add(candidate);
      h.sectionId = candidate;
    }
    h.sectionTitle = norm(stripHtml(h.inner));
  }

  // Build index entries: text is content between this heading and the next.
  const entries = [];
  for (let i = 0; i < headingMatches.length; i++) {
    const h = headingMatches[i];
    const start = h.index + h.fullLen;
    const end =
      i + 1 < headingMatches.length ? headingMatches[i + 1].index : html.length;

    const sectionText = norm(stripHtml(html.slice(start, end)));

    entries.push({
      page: filename,
      pageTitle,
      sectionId: h.sectionId,
      sectionTitle: h.sectionTitle,
      text: sectionText,
      excerpt: excerpt(sectionText),
    });
  }

  // Patch missing id= attributes back into the HTML.
  let patched = html;
  // Process in reverse order so string positions stay valid.
  for (let i = headingMatches.length - 1; i >= 0; i--) {
    const h = headingMatches[i];
    if (ID_ATTR_RE.test(h.attrs)) continue; // already had an id

    const newOpen = `<${h.tag} id="${h.sectionId}"${h.attrs}>`;
    const newFull = `${newOpen}${h.inner}</${h.tag}>`;
    patched =
      patched.slice(0, h.index) + newFull + patched.slice(h.index + h.fullLen);
  }

  if (patched !== html) {
    fs.writeFileSync(filepath, patched, "utf8");
  }

  return { entries, patched: patched !== html };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const docsDir = path.resolve(process.argv[2] || __dirname);
const assetsDir = path.join(docsDir, "assets");

const candidates = fs
  .readdirSync(docsDir)
  .filter((f) => f.endsWith(".html") && !f.startsWith("_"))
  .sort();

let allEntries = [];
let patchCount = 0;

for (const filename of candidates) {
  const filepath = path.join(docsDir, filename);
  try {
    const { entries, patched } = processPage(filepath, filename);
    allEntries = allEntries.concat(entries);
    if (patched) patchCount++;
  } catch (err) {
    process.stderr.write(`  WARNING: skipping ${filename}: ${err.message}\n`);
  }
}

if (!fs.existsSync(assetsDir)) fs.mkdirSync(assetsDir, { recursive: true });
fs.writeFileSync(
  path.join(assetsDir, "search-index.json"),
  JSON.stringify(allEntries),
  "utf8",
);

console.log(
  `  Search index: ${allEntries.length} sections across ${candidates.length} pages` +
    ` (${patchCount} files patched with heading IDs)`,
);

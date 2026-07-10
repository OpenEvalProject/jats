# Include `<back>` matter (Methods, figure legends, references) + harden non-JATS input

## Why this is needed

`jats convert` — the tool's primary command — only walked `<body>`. **bioRxiv**, a
first-class supported source, places **Methods, Extended Data / Supplementary figure
legends, Data/Code availability, Author contributions, Acknowledgements, and the entire
reference list inside `<back>`.** So `convert` silently dropped ~⅔ of a typical preprint.

Measured on a real bioRxiv preprint (`10.64898/2026.06.30.735642`), and validated across
**11 bioRxiv splicing papers** from one month:

| | `convert` before | `convert` after (this PR) |
|---|---:|---:|
| words | 8,169 | 18,873 |
| `## Methods` | ✗ | ✓ |
| `## References` (formatted list) | ✗ | ✓ (47 entries) |

The README already advertised "References (when available)" as output and defines
`<back>` — this PR makes that promise true. It also fixes a **half-applied-fix
inconsistency**: `text --section` gained `back`, so no command silently drops `<back>`.

## "Doesn't `text --section all` already give me this?" — No.

This is worth addressing head-on, because it's the natural objection.

- **`text` emits an unstructured text blob**; `convert` emits **semantic Markdown**. On the
  same paper: `convert` produces 28 headings and a 47-entry formatted reference list
  (`- [n] Author … (year). Title. Journal.`); `text --section all` produces **0** markdown
  structure lines — references come out as an inline run of `Author , 446 , 926 – 9 .`
  fragments with no `## References`, no `## Methods`, no per-reference boundaries.
- They serve different jobs: `text`/`find` are for search/indexing over raw content;
  `convert` is for a **readable, structured document** (the tool's headline feature and its
  README's stated output contract: title, headings, references-as-list). A blob is not a
  substitute for structured Markdown.
- Crucially, **`text --section all` including `<back>` is itself part of THIS PR** — before
  it, `text --section all` *also* dropped `<back>` (it only read `<body>`). So it isn't a
  pre-existing alternative that makes the PR redundant; it's the same gap fixed consistently
  across commands. The `convert` fix is the substantive one; the `text` fix is for parity.

**Net:** the PR is needed because `convert` is the command whose entire purpose is
structured Markdown, and that command was losing most of every bioRxiv paper. No text-mode
flag substitutes for that.

## What changed

- **`models.py`**: `Article.back` (sections) + `Article.bibliography` (list of
  `BibReference`). `Article.references` (the inline-citation id→DOI map) is untouched, so
  citation hyperlinking is unaffected.
- **`parser.py`**:
  - `parse_body(container_tag=…)` generalized; `parse_back()` reuses it on `<back>` (plus
    `<ack>` handling), so titles/nesting/paragraphs/figures/tables/equations are handled by
    the existing, tested section machinery.
  - `parse_bibliography()` renders `<ref-list>` using `citation.itertext()` — faithful and
    robust across `citation`/`element-citation`/`mixed-citation` variants.
  - **Robustness:** `parse_jats_xml` now raises a clear `ValueError` when handed a non-JATS
    document (e.g. a bioRxiv "Page Not Found" HTML page returned on a 404/rate-limit for a
    `.source.xml` URL — its analytics `<script>` has an unescaped `&` that previously caused
    a cryptic `XMLSyntaxError: EntityRef: expecting ';'`). Also rejects well-formed
    non-`<article>` docs.
- **`converter.py`**: renders `article.back` (shared section renderer) then a `## References`
  block; honors `--no-refs` for DOI links.
- **`main.py`**: `convert --no-back` opt-out; `text --section {…,back}` so `text`/`find` are
  consistent with `convert`.

## Backward compatibility

- `convert --no-back` reproduces the old body-only output **byte-for-byte** (verified).
- New model fields default empty; a paper with no `<back>` converts unchanged (no empty
  `## References`).
- `references` DOI-map behavior unchanged.

## Tests

`pytest -q` → **12 passed.** New: `tests/test_back_matter.py` (back sections + bibliography
parse/render, `--no-back`, `--no-refs`, no-`<back>` regression, `text --section back/all/body`)
and `tests/test_invalid_input.py` (HTML-404 page and non-JATS XML → `ValueError`).

## Scope / non-goals

- Figure **image content** (what a plot shows) and equations stored as `<graphic>` images
  are not recoverable from the XML by any tool — out of scope. This PR recovers everything
  the XML *does* contain in `<back>`.

## Field validation

Run across 11 unseen bioRxiv splicing preprints: 8 full-content papers all gained their
Methods + 47–54-entry reference lists; 3 recent posts were abstract-only *in the XML* (not a
tool issue); the one crash encountered (HTML error page) is the input-hardening fix above.

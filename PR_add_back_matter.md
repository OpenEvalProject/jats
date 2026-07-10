# PR proposal: include `<back>` matter (Methods, figure legends, references, acknowledgements)

## Problem

`jats convert` only walks `<body>`. For **bioRxiv** preprints — a first-class supported source
— the publisher places **Methods, Extended Data / Supplementary figure legends, Data/Code
availability, Author contributions, Acknowledgements, and the entire reference list** inside
`<back>`, not `<body>`. As a result the tool silently drops ~⅔ of a typical bioRxiv paper.

Measured on a real preprint (OpenSplice, bioRxiv `10.64898/2026.05.22.727141`):
- `jats convert` → **7,482 words** (body only; no Methods, no refs, no legends)
- `pandoc -f jats` (which does walk `<back>`) → **18,066 words** (complete)
- `<back>` is 135 KB vs `<body>` 77 KB — the majority of the article.

The README already documents `<back>` ("References, acknowledgments, etc.") and lists
"References (when available)" as output, and `Article` has a `references` field — but no code
path reads `<back>` sections or emits a reference list. `grep -n back jats/parser.py` → 0 hits.

## Root cause (in the current code)

- `parse_body()` (`jats/parser.py`) starts from `root.find('.//body')` and iterates its
  `<sec>` children. `<back>` is never visited.
- `parse_references()` (`jats/parser.py:435`) does `root.findall('.//ref')` but only builds a
  `{ref_id: DOI}` **lookup map** to hyperlink inline citations — it never captures or emits the
  bibliographic entries, and `Article.references` stays a DOI dict.
- `convert_to_markdown()` (`jats/converter.py:192`) renders only `article.body`.

## Design

Reuse the existing section-parsing machinery — `<back>` sections are the same
`<sec>/<title>/<p>/<disp-formula>` shape `parse_body` already handles (verified on real XML).
Two changes to the parser, one to the model, one to the converter. Fully backward-compatible
and opt-outable.

### 1. `jats/models.py` — capture back sections + structured references

```python
@dataclass
class BibReference:
    """A bibliographic entry from <ref-list> (distinct from the id→DOI citation map)."""
    ref_id: str
    label: Optional[str] = None        # "4." — as printed
    text: str = ""                     # human-readable citation (itertext of <citation>)
    doi: Optional[str] = None

@dataclass
class Article:
    ...
    body: List[Section] = field(default_factory=list)
    back: List[Section] = field(default_factory=list)          # NEW: Methods, legends, ack, availability…
    bibliography: List[BibReference] = field(default_factory=list)  # NEW: rendered ref list
    # `references: Dict[str,str]` stays as-is (the inline-citation DOI map) — unchanged.
```

Keeping `references` (the DOI map) untouched avoids breaking `extract_text_with_citations`.

### 2. `jats/parser.py` — factor out section parsing, run it on `<back>`; parse the ref-list

- **Refactor:** extract the per-container `<sec>` loop from `parse_body` into a private
  `_parse_sections(container, figures, tables, references, figure_urls, no_refs)` that takes any
  element (a `<body>` or a `<back>`). `parse_body` becomes
  `_parse_sections(root.find('.//body'), ...)`; add
  `parse_back(root, ...) = _parse_sections(root.find('.//back'), ...)`.
  This is a pure refactor — no behavior change for `<body>`.

  One tweak: `<back>` sometimes holds `<ack>` (acknowledgements) as a sibling of `<sec>` rather
  than a `<sec>`; treat `<ack>` like a section titled "Acknowledgements". Also exclude the
  `<ref-list>` subtree from section parsing (it's rendered separately, step below) so it isn't
  double-emitted as prose.

- **New `parse_bibliography(root) -> List[BibReference]`:** iterate
  `root.findall('.//ref-list/ref')`; for each, read `<label>`, find the
  `citation|element-citation|mixed-citation`, and take `''.join(citation.itertext())` normalized
  on whitespace as the human-readable text (verified: yields
  `"Landrum, M. J. et al. ClinVar: … Nucleic Acids Res 42, D980"`), plus any
  `pub-id[@pub-id-type="doi"]`. This is deliberately simple and faithful — no fragile per-field
  reconstruction; the source already orders the citation text correctly.

- Wire both into `parse_jats_xml`:
  ```python
  body = parse_body(root, figures, tables, references, figure_urls, no_refs)
  back = parse_back(root, figures, tables, references, figure_urls, no_refs)
  bibliography = parse_bibliography(root)
  return Article(..., body=body, back=back, bibliography=bibliography, ...)
  ```

### 3. `jats/converter.py` — render back sections + a `## References` block

After the `for section in article.body` loop in `convert_to_markdown`:

```python
for section in article.back:          # same rendering as body sections
    _render_section(section, md_parts)

if article.bibliography:
    md_parts.append("## References\n")
    for ref in article.bibliography:
        lbl = f"{ref.label} " if ref.label else ""
        line = f"{lbl}{ref.text}".strip()
        if ref.doi:
            line += f" https://doi.org/{ref.doi}"
        md_parts.append(f"- {line}")
```

(Refactor the existing body item-rendering into a small `_render_section` helper so body and
back share it.) Respect `--no-refs` for the DOI suffix, consistent with current behavior.

### 4. Optional CLI flag (nice-to-have, not required)

Default to including back matter (it's the correct, complete behavior). Add `--no-back` for
callers who explicitly want body-only, mirroring the existing `--no-refs` style:

```python
p.add_argument("--no-back", action="store_true",
               help="Exclude <back> matter (Methods, references, legends) from output")
```

## Tests (`tests/`)

- Add a small fixture XML with a `<back>` containing one `<sec><title>Methods</title>` + a
  `<ref-list>` of 2 `<ref>`s.
- Assert the converted Markdown contains `## Methods`, the method paragraph text, `## References`,
  and both citation strings.
- Regression: an XML with no `<back>` still converts (back=[], bibliography=[]) — no crash, no
  trailing empty `## References`.
- Assert `--no-back` produces body-only output identical to today's.

## Why this shape

- **Minimal + reuses existing logic** — the `<sec>` parser already handles titles, nesting
  levels, paragraphs, figures, tables, and `disp-formula` (equations). `<back>` sections need no
  new content handling; they were simply never visited.
- **Backward compatible** — `references` DOI-map untouched; new fields default empty; `--no-back`
  restores old output exactly.
- **Faithful references** — using `citation.itertext()` matches how the source orders the
  citation and avoids brittle field-by-field reconstruction across `citation` /
  `element-citation` / `mixed-citation` variants.

## Scope / non-goals

- Figure *image content* (what a plot shows) is still out of scope — that's not in the XML at
  all. This PR recovers everything the XML *does* contain in `<back>`.
- `<table-wrap>` inside `<back>` sections is already handled by the reused section parser.

# jats - JATS XML Parser

A Python CLI tool for converting JATS (Journal Article Tag Suite) XML files to Markdown format, with support for extracting peer review comments and author responses.

## Overview

jats parses JATS XML files from scientific publishers (bioRxiv, eLife, etc.) and converts them to clean, readable Markdown. It's particularly useful for working with preprint manuscripts and their associated peer review materials.

### Key Features

- Convert JATS XML articles to Markdown
- Extract peer review comments and author responses from multi-article XML files
- Support for bioRxiv manifest files (optional metadata)
- Organize reviews and responses by revision round
- Simple CLI interface with stdout or file output

## Installation

### Prerequisites

- Python >=3.10

### Install with uv (recommended)

```bash
cd jats
uv pip install -e .
```

### Install with pip

```bash
cd jats
pip install -e .
```

## Usage

### Basic Conversion

Convert a JATS XML file to Markdown:

```bash
# Output to stdout
jats convert article.xml

# Output to file
jats convert article.xml -o article.md

# With bioRxiv manifest file (optional)
jats convert article.xml -m manifest.xml -o article.md
```

### Extract Peer Reviews

Extract peer review comments and author responses from JATS XML files that include sub-articles (common in eLife and some bioRxiv articles):

```bash
# Extract reviews and responses to separate files
jats convert article.xml -o article.md -r output_base

# Creates:
# - output_base_reviews.md    (all review comments, organized by round)
# - output_base_responses.md  (all author responses, organized by round)
```

The `-r` flag extracts sub-articles with the following JATS article types:
- **Review comments**: decision-letter, referee-report, editor-report, reviewer-report
- **Author responses**: author-comment, reply

Reviews and responses are automatically organized by revision round using JATS4R `peer-review-revision-round` metadata (defaults to round 1 if not specified).

## Examples

### Convert bioRxiv Preprint

```bash
jats convert 2023.01.01.12345.xml -o paper.md
```

### Convert eLife Article with Peer Reviews

```bash
# Convert main article and extract reviews
jats convert elife-12345-v1.xml -o paper.md -r elife-12345-v1

# Output files:
# - paper.md                        (main article)
# - elife-12345-v1_reviews.md      (peer review comments)
# - elife-12345-v1_responses.md    (author responses)
```

### bioRxiv with Manifest

```bash
# manifest.xml provides additional metadata
jats convert article.xml -m manifest.xml -o article.md
```

## Input File Format

jats expects JATS XML files following the [JATS (Journal Article Tag Suite)](https://jats.nlm.nih.gov/) standard. This format is used by:

- **bioRxiv** and **medRxiv** preprint servers
- **eLife** journal
- **PubMed Central** (PMC)
- Many other scientific publishers

### JATS XML Structure

A typical JATS XML file contains:
- `<front>`: Article metadata (title, authors, abstract)
- `<body>`: Main article content organized in sections
- `<back>`: References, acknowledgments, etc.
- `<sub-article>`: Optional peer review materials (eLife, some bioRxiv)

### Manifest Files (bioRxiv)

bioRxiv articles may include an optional `manifest.xml` file that provides:
- Collection/category information
- Version history
- Links to published versions
- Peer review URLs

## Output Format

jats converts JATS XML to clean, readable Markdown with:

- Article title as H1 heading
- Authors with affiliations
- Abstract
- Body sections with appropriate heading levels
- Inline figures with captions
- References (when available)

### Peer Review Output

When using `-r`, peer review materials are extracted to separate Markdown files:

**Reviews file** (`*_reviews.md`):
```markdown
# Revision Round 1

## Reviewer 1

[Review content...]

---

## Reviewer 2

[Review content...]
```

**Responses file** (`*_responses.md`):
```markdown
# Revision Round 1

## Author Response

[Response content...]
```

## Development

### Running Tests

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

### Project Structure

```
jats/
├── jats/
│   ├── __init__.py
│   ├── main.py         # CLI entry point
│   ├── parser.py       # JATS XML parsing
│   ├── converter.py    # Markdown conversion
│   └── models.py       # Data models
├── tests/
│   ├── test_*.py       # Test files
│   └── *.xml           # Test fixtures
├── pyproject.toml      # Package configuration
└── README.md
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development documentation and code style guide.

## JATS Resources

- [JATS Documentation](https://jats.nlm.nih.gov/)
- [JATS4R (JATS for Reuse)](https://jats4r.org/) - Recommendations for peer review tagging
- [bioRxiv JATS XML](https://www.biorxiv.org/about/FAQ#JATS)
- [eLife JATS XML](https://elifesciences.org/labs/c079f973/jats-xml-a-format-for-archiving-and-exchanging-scientific-content)

## License

MIT

## Support

For issues or questions, please open an issue on GitHub.

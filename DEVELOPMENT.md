# Code Style Guide: jxp (JATS XML Parser)

## Project Overview

A Python CLI tool and package for parsing and converting JATS (Journal Article Tag Suite) XML files from various sources (bioRxiv, eLife, etc.) to multiple output formats, with primary focus on Markdown conversion.

## Key Design Decisions

1. **Modular Architecture**: Separate parsers for each source (bioRxiv, eLife) and converters for each output format (Markdown, HTML, etc.)
2. **Type-Safe Models**: Comprehensive Pydantic models that capture all relevant JATS information
3. **Explicit Input Types**: Users must specify the source with `-i/--itype` flag to handle source-specific variations
4. **Optional Manifest Support**: bioRxiv articles can include optional `manifest.xml` for enhanced metadata
5. **Extensible Design**: Easy to add new sources and output formats through registration patterns
6. **Modern Python**: Requires Python 3.12+, uses type hints, Pydantic v2, and modern tooling (uv, ruff)

## Quick Start for Developers

```bash
# Clone repository
git clone https://github.com/yourusername/jxp.git
cd jxp

# Install in development mode with uv
uv pip install -e ".[dev]"

# Run tests
make test

# Format code
make format

# Try the CLI
jxp convert -i biorxiv examples/biorxiv/article.xml
```

## Project Structure

```
jxp/
├── README.md
├── LICENSE
├── pyproject.toml
├── .pre-commit-config.yaml
├── Makefile
├── jxp/
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   ├── models/
│   │   ├── __init__.py
│   │   ├── article.py             # Article model
│   │   ├── metadata.py            # Metadata model
│   │   ├── author.py              # Author and affiliation models
│   │   ├── section.py             # Body section models
│   │   ├── reference.py           # Reference/citation models
│   │   └── element.py             # Content element models (figures, tables, etc.)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py                # Base parser interface
│   │   ├── biorxiv.py             # bioRxiv-specific parser
│   │   └── elife.py               # eLife-specific parser
│   ├── converters/
│   │   ├── __init__.py
│   │   ├── base.py                # Base converter interface
│   │   └── markdown.py            # Markdown converter
│   ├── utils.py                   # Utility functions
│   ├── jxp_convert.py             # Convert command implementation
│   ├── jxp_validate.py            # Validate command implementation
│   ├── jxp_info.py                # Info command implementation
│   └── schema/
│       └── jats-schema.xsd        # JATS schema for validation
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── biorxiv/
│   │   │   ├── sample.xml
│   │   │   └── manifest.xml
│   │   └── elife/
│   │       └── sample.xml
│   ├── test_parsers.py
│   ├── test_converters.py
│   ├── test_jxp_convert.py
│   └── test_utils.py
└── docs/
    ├── INSTALLATION.md
    ├── USAGE.md
    ├── EXAMPLES.md
    └── JATS_STRUCTURE.md
```

## Technology Stack

### Core Dependencies
- **Python**: ≥3.12
- **lxml**: XML parsing and validation
- **pydantic**: Data models and validation
- **click** or **argparse**: CLI framework
- **pyyaml**: Optional YAML configuration

### Development Dependencies
- **pytest**: Testing framework
- **pytest-cov**: Test coverage
- **pytest-mock**: Mocking for tests
- **ruff**: Linting and formatting
- **pre-commit**: Git hooks
- **build**: Package building
- **twine**: PyPI uploads

## pyproject.toml Configuration

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "jxp"
version = "0.1.0"
description = "JATS XML Parser: Convert JATS XML articles to various formats"
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"
authors = [{ name = "Your Name", email = "your.email@example.com" }]
keywords = ["jats", "xml", "markdown", "converter", "publishing", "biorxiv", "elife"]
classifiers = [
    "Environment :: Console",
    "Intended Audience :: Science/Research",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Text Processing :: Markup :: XML",
    "Topic :: Utilities",
]
dependencies = [
    "lxml>=5.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "pytest-mock>=3.14",
    "pre-commit>=4.0",
    "build>=1.0",
    "ruff>=0.9",
]

[project.scripts]
jxp = "jxp.main:main"

[tool.setuptools.packages.find]
include = ["jxp", "jxp.*"]

[tool.setuptools.package-data]
"jxp" = ["schema/*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--cov=jxp"

[tool.ruff]
line-length = 88
target-version = "py312"
exclude = [".git", "__pycache__", "build", "dist", ".venv"]

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501", "E203"]
```

## Code Organization Patterns

### 1. CLI Structure (main.py)

```python
"""Main module for jxp CLI.

This module provides the main entry point for the jxp command-line interface.
It handles argument parsing, command routing, and execution of subcommands.
"""

import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter

from . import __version__
from .jxp_convert import run_convert, setup_convert_args
from .jxp_validate import run_validate, setup_validate_args
from .jxp_info import run_info, setup_info_args


def setup_parser():
    """Create and configure the main argument parser.

    Returns:
        Tuple of (parser, command_to_parser dict).
    """
    parser = ArgumentParser(
        description=f"""
jxp {__version__}: JATS XML Parser for scientific articles.

GitHub: https://github.com/yourusername/jxp
Documentation: https://yourusername.github.io/jxp/
""",
        formatter_class=RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<CMD>")

    command_to_parser = {
        "convert": setup_convert_args(subparsers),
        "validate": setup_validate_args(subparsers),
        "info": setup_info_args(subparsers),
    }

    return parser, command_to_parser


def main() -> None:
    """Main entry point for the jxp CLI."""
    parser, command_to_parser = setup_parser()
    
    # Handle no arguments
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    
    args = parser.parse_args()
    
    # Route to appropriate command
    command_map = {
        "convert": run_convert,
        "validate": run_validate,
        "info": run_info,
    }
    
    if args.command in command_map:
        command_map[args.command](parser, args)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 2. Subcommand Module Pattern (jxp_convert.py)

Each subcommand should follow this three-function pattern:

```python
"""Convert module for jxp CLI.

This module provides functionality to convert JATS XML files to various output formats.
Supports multiple input types (bioRxiv, eLife) and output formats (Markdown, etc.).
"""

from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import Optional

from jxp.parsers import get_parser
from jxp.converters import get_converter


def setup_convert_args(parser) -> ArgumentParser:
    """Create and configure the convert command subparser.

    Args:
        parser: The main argument parser to add the convert subparser to.

    Returns:
        The configured convert subparser.
    """
    subparser = parser.add_parser(
        "convert",
        description="""
Convert JATS XML file to specified output format.

Examples:
jxp convert -i biorxiv article.xml                       # Convert bioRxiv to markdown (stdout)
jxp convert -i biorxiv article.xml -o article.md         # Convert to file
jxp convert -i biorxiv article.xml -m manifest.xml       # Include manifest metadata
jxp convert -i elife article.xml -t gfm -o article.md    # Use GitHub-flavored markdown
---
""",
        help="Convert JATS XML to another format",
        formatter_class=RawTextHelpFormatter,
    )

    # Required arguments
    subparser.add_argument(
        "-i",
        "--itype",
        required=True,
        choices=["biorxiv", "elife"],
        help="Input type (source of JATS XML)"
    )
    subparser.add_argument(
        "xml",
        type=Path,
        help="JATS XML file to convert"
    )
    
    # Optional arguments
    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output file (default: stdout)",
        default=None,
    )
    subparser.add_argument(
        "-t",
        "--otype",
        choices=["markdown", "html", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    subparser.add_argument(
        "-f",
        "--flavor",
        choices=["commonmark", "gfm", "pandoc"],
        default="commonmark",
        help="Markdown flavor (only applies when otype=markdown)"
    )
    subparser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        help="Optional manifest.xml file (bioRxiv only)",
        default=None,
    )
    
    return subparser


def validate_convert_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate the convert command arguments.

    Args:
        parser: The argument parser.
        args: The parsed arguments.

    Raises:
        parser.error: If any validation fails.
    """
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")
    
    # Validate manifest file
    if args.manifest:
        if args.itype != "biorxiv":
            parser.error("Manifest file only supported for bioRxiv input type")
        if not args.manifest.exists():
            parser.error(f"Manifest file does not exist: {args.manifest}")
        if args.manifest.name.lower() != "manifest.xml":
            parser.error("Manifest file must be named 'manifest.xml'")


def run_convert(parser: ArgumentParser, args: Namespace) -> None:
    """Run the convert command.

    Args:
        parser: The argument parser.
        args: The parsed arguments.
    """
    validate_convert_args(parser, args)

    # Get appropriate parser for input type
    parser_cls = get_parser(args.itype)
    jats_parser = parser_cls()
    
    # Parse JATS XML (with optional manifest for bioRxiv)
    article = jats_parser.parse(args.xml, manifest=args.manifest)
    
    # Get appropriate converter for output type
    converter_cls = get_converter(args.otype)
    converter = converter_cls(flavor=args.flavor if args.otype == "markdown" else None)
    
    # Convert to output format
    output_content = converter.convert(article)
    
    # Output
    if args.output:
        args.output.write_text(output_content)
        print(f"Converted {args.xml} -> {args.output}", file=sys.stderr)
    else:
        print(output_content)
```

### 3. Comprehensive Pydantic Models

The models are designed to be general enough to capture all relevant JATS information across different publishers.

```python
"""Comprehensive models for JATS article structure.

These models provide a complete representation of JATS XML articles,
capturing metadata, body content, and back matter.
"""

from datetime import date
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# Author and Affiliation Models
# ============================================================================

class AffiliationInput(BaseModel):
    """Input for creating an Affiliation."""
    affiliation_id: Optional[str] = Field(default=None, description="Unique identifier")
    institution: Optional[str] = Field(default=None, description="Institution name")
    department: Optional[str] = Field(default=None, description="Department or division")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State or province")
    country: Optional[str] = Field(default=None, description="Country")
    postal_code: Optional[str] = Field(default=None, description="Postal code")


class Affiliation(BaseModel):
    """Institutional affiliation."""
    affiliation_id: str
    institution: Optional[str] = None
    department: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class AuthorContribution(BaseModel):
    """Author contribution information."""
    contribution_type: str  # e.g., "conceptualization", "data-curation"
    description: Optional[str] = None


class AuthorInput(BaseModel):
    """Input for creating an Author.
    
    Attributes:
        author_id: Unique identifier for the author.
        given_names: Author's given names (first/middle).
        surname: Author's surname (family name).
        suffix: Name suffix (Jr., III, etc.).
        email: Contact email address.
        orcid: ORCID identifier.
        affiliation_ids: List of affiliation IDs.
        corresponding: Whether this is a corresponding author.
        equal_contrib: Whether author made equal contribution.
        contributions: List of specific contributions.
        deceased: Whether the author is deceased.
    """
    author_id: Optional[str] = Field(default=None)
    given_names: Optional[str] = Field(default=None)
    surname: Optional[str] = Field(default=None)
    suffix: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    orcid: Optional[str] = Field(default=None)
    affiliation_ids: List[str] = Field(default_factory=list)
    corresponding: bool = Field(default=False)
    equal_contrib: bool = Field(default=False)
    contributions: List[AuthorContribution] = Field(default_factory=list)
    deceased: bool = Field(default=False)
    
    def to_author(self) -> "Author":
        """Convert input to Author model."""
        return Author(
            author_id=self.author_id or "auto-id",
            given_names=self.given_names or "",
            surname=self.surname or "",
            suffix=self.suffix,
            email=self.email,
            orcid=self.orcid,
            affiliation_ids=self.affiliation_ids,
            corresponding=self.corresponding,
            equal_contrib=self.equal_contrib,
            contributions=self.contributions,
            deceased=self.deceased,
        )


class Author(BaseModel):
    """Author information."""
    author_id: str
    given_names: str
    surname: str
    suffix: Optional[str] = None
    email: Optional[str] = None
    orcid: Optional[str] = None
    affiliation_ids: List[str] = Field(default_factory=list)
    corresponding: bool = False
    equal_contrib: bool = False
    contributions: List[AuthorContribution] = Field(default_factory=list)
    deceased: bool = False


# ============================================================================
# Metadata Models
# ============================================================================

class ArticleIdentifier(BaseModel):
    """Article identifier (DOI, PMID, etc.)."""
    id_type: str  # doi, pmid, pmcid, publisher-id, etc.
    value: str


class ArticleDate(BaseModel):
    """Article date with type."""
    date_type: str  # received, accepted, published, epub, etc.
    date_value: date
    

class FundingSource(BaseModel):
    """Funding source information."""
    institution: Optional[str] = None
    institution_id: Optional[str] = None  # FundRef ID, etc.
    award_id: Optional[str] = None
    principal_investigator: Optional[str] = None


class License(BaseModel):
    """License information."""
    license_type: str  # cc-by, cc-by-nc, etc.
    license_url: Optional[HttpUrl] = None
    license_text: Optional[str] = None


class Keyword(BaseModel):
    """Keyword or subject term."""
    keyword: str
    keyword_type: Optional[str] = None  # author-keyword, mesh-term, etc.


class Abstract(BaseModel):
    """Article abstract.
    
    Can be structured (with sections) or unstructured.
    """
    abstract_type: Optional[str] = None  # author, editor, graphical, etc.
    title: Optional[str] = None
    sections: List["Section"] = Field(default_factory=list)  # For structured abstracts
    content: Optional[str] = None  # For unstructured abstracts


class Metadata(BaseModel):
    """Complete article metadata."""
    # Basic identification
    title: str
    subtitle: Optional[str] = None
    identifiers: List[ArticleIdentifier] = Field(default_factory=list)
    
    # Authors and affiliations
    authors: List[Author] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    
    # Editorial information
    journal_title: Optional[str] = None
    journal_abbrev: Optional[str] = None
    publisher: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    article_type: Optional[str] = None  # research-article, review-article, etc.
    
    # Dates
    dates: List[ArticleDate] = Field(default_factory=list)
    
    # Content metadata
    abstracts: List[Abstract] = Field(default_factory=list)
    keywords: List[Keyword] = Field(default_factory=list)
    
    # Rights and funding
    copyright_statement: Optional[str] = None
    copyright_year: Optional[int] = None
    copyright_holder: Optional[str] = None
    license: Optional[License] = None
    funding_sources: List[FundingSource] = Field(default_factory=list)
    
    # Additional metadata
    subject_categories: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Content Element Models
# ============================================================================

class ContentType(str, Enum):
    """Types of content elements."""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    CODE = "code"
    QUOTE = "quote"
    SUPPLEMENTARY = "supplementary"


class Figure(BaseModel):
    """Figure with caption and metadata."""
    figure_id: str
    label: Optional[str] = None  # "Figure 1", "Fig. 1", etc.
    caption: Optional[str] = None
    graphic_href: Optional[str] = None  # Path to image file
    alt_text: Optional[str] = None
    attribution: Optional[str] = None


class Table(BaseModel):
    """Table with caption and content."""
    table_id: str
    label: Optional[str] = None  # "Table 1", etc.
    caption: Optional[str] = None
    content: str  # HTML or other representation
    footer: Optional[str] = None


class ListItem(BaseModel):
    """List item content."""
    content: str
    subitems: List["ListItem"] = Field(default_factory=list)


class List(BaseModel):
    """Ordered or unordered list."""
    list_type: str  # "bullet", "ordered", "alpha", etc.
    items: List[ListItem] = Field(default_factory=list)


class Equation(BaseModel):
    """Mathematical equation."""
    equation_id: Optional[str] = None
    label: Optional[str] = None
    content: str  # LaTeX, MathML, or other format
    format: str = "latex"  # latex, mathml, image


class CodeBlock(BaseModel):
    """Code block."""
    language: Optional[str] = None
    content: str


class Quote(BaseModel):
    """Block quotation."""
    content: str
    attribution: Optional[str] = None


class CrossReference(BaseModel):
    """Cross-reference to another element."""
    ref_type: str  # fig, table, sec, bibr, etc.
    rid: str  # Referenced element ID
    label: Optional[str] = None


class ContentElement(BaseModel):
    """Generic content element."""
    element_type: ContentType
    content: Any  # Can be str, Figure, Table, List, etc.


# ============================================================================
# Section Models
# ============================================================================

class Section(BaseModel):
    """Article section (can be nested).
    
    Represents a section of the article body or a structured abstract.
    """
    section_id: Optional[str] = None
    title: Optional[str] = None
    content: List[ContentElement] = Field(default_factory=list)
    subsections: List["Section"] = Field(default_factory=list)


# ============================================================================
# Reference Models
# ============================================================================

class ReferenceAuthor(BaseModel):
    """Author in a reference."""
    given_names: Optional[str] = None
    surname: str


class Reference(BaseModel):
    """Bibliographic reference."""
    reference_id: str
    label: Optional[str] = None  # [1], 1., etc.
    
    # Publication details
    authors: List[ReferenceAuthor] = Field(default_factory=list)
    article_title: Optional[str] = None
    source: Optional[str] = None  # Journal, book, etc.
    year: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    fpage: Optional[str] = None  # First page
    lpage: Optional[str] = None  # Last page
    
    # Identifiers
    doi: Optional[str] = None
    pmid: Optional[str] = None
    url: Optional[HttpUrl] = None
    
    # Raw citation (if parsing fails)
    raw_citation: Optional[str] = None


# ============================================================================
# Back Matter Models
# ============================================================================

class BackMatter(BaseModel):
    """Article back matter."""
    acknowledgments: Optional[str] = None
    author_contributions: Optional[str] = None
    competing_interests: Optional[str] = None
    data_availability: Optional[str] = None
    appendices: List[Section] = Field(default_factory=list)
    glossary: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Complete Article Model
# ============================================================================

class Article(BaseModel):
    """Complete JATS article representation.
    
    This model captures the full structure of a JATS article including
    metadata, body content, references, and back matter.
    """
    metadata: Metadata
    body: List[Section] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    back_matter: Optional[BackMatter] = None
    
    # Optional: Raw XML for debugging or custom processing
    raw_xml: Optional[str] = Field(default=None, exclude=True)


# Enable forward references
Section.model_rebuild()
ListItem.model_rebuild()
```

### 4. Parser Architecture

The parser system uses a base class with source-specific implementations to handle variations in JATS XML structure across different publishers.

```python
"""Base parser interface for JATS XML.

This module defines the abstract base class for JATS parsers and
provides factory functions for getting the appropriate parser.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Type
from lxml import etree

from jxp.models.article import Article


class BaseJATSParser(ABC):
    """Abstract base parser for JATS XML files.
    
    Subclasses implement source-specific parsing logic while
    maintaining a consistent interface.
    """
    
    def __init__(self):
        """Initialize the parser."""
        self.namespaces = {
            'jats': 'http://jats.nlm.nih.gov',
            'xlink': 'http://www.w3.org/1999/xlink',
            'mml': 'http://www.w3.org/1998/Math/MathML',
        }
    
    def parse(self, xml_path: Path, manifest: Optional[Path] = None) -> Article:
        """Parse JATS XML file into Article model.
        
        Args:
            xml_path: Path to JATS XML file.
            manifest: Optional path to manifest file (source-specific).
            
        Returns:
            Parsed Article object.
            
        Raises:
            ValueError: If XML is malformed or invalid.
            FileNotFoundError: If xml_path doesn't exist.
        """
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        # Parse main XML
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        
        # Parse optional manifest (if supported and provided)
        manifest_data = None
        if manifest:
            manifest_data = self._parse_manifest(manifest)
        
        # Build article model
        return self._build_article(root, manifest_data)
    
    @abstractmethod
    def _parse_manifest(self, manifest_path: Path) -> dict:
        """Parse source-specific manifest file.
        
        Args:
            manifest_path: Path to manifest file.
            
        Returns:
            Dictionary of manifest data.
        """
        pass
    
    @abstractmethod
    def _build_article(self, root: etree.Element, manifest_data: Optional[dict]) -> Article:
        """Build Article model from XML root and optional manifest.
        
        Args:
            root: Root element of JATS XML.
            manifest_data: Optional manifest data.
            
        Returns:
            Complete Article object.
        """
        pass
    
    # Helper methods for common parsing tasks
    
    def _extract_text(self, element: Optional[etree.Element]) -> Optional[str]:
        """Extract all text content from an element."""
        if element is None:
            return None
        return "".join(element.itertext()).strip()
    
    def _get_element_text(self, root: etree.Element, xpath: str) -> Optional[str]:
        """Get text from first matching element."""
        elements = root.xpath(xpath, namespaces=self.namespaces)
        if elements:
            return self._extract_text(elements[0])
        return None


# ============================================================================
# BioRxiv Parser
# ============================================================================

class BioRxivParser(BaseJATSParser):
    """Parser for bioRxiv JATS XML files.
    
    Handles bioRxiv-specific XML structure and optional manifest.xml
    that contains additional metadata.
    """
    
    def _parse_manifest(self, manifest_path: Path) -> dict:
        """Parse bioRxiv manifest.xml file.
        
        The manifest contains additional metadata like:
        - Collection information
        - Version history
        - Related articles
        - Peer review links
        
        Args:
            manifest_path: Path to manifest.xml.
            
        Returns:
            Dictionary of manifest metadata.
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
        tree = etree.parse(str(manifest_path))
        root = tree.getroot()
        
        manifest_data = {
            "collection": self._get_element_text(root, ".//collection"),
            "version": self._get_element_text(root, ".//version"),
            "related_articles": [],
            "peer_review_url": self._get_element_text(root, ".//peer-review-url"),
        }
        
        # Extract related articles
        for related in root.xpath(".//related-article", namespaces=self.namespaces):
            manifest_data["related_articles"].append({
                "doi": related.get("doi"),
                "type": related.get("related-article-type"),
            })
        
        return manifest_data
    
    def _build_article(self, root: etree.Element, manifest_data: Optional[dict]) -> Article:
        """Build Article from bioRxiv JATS XML.
        
        Args:
            root: Root element of JATS XML.
            manifest_data: Optional data from manifest.xml.
            
        Returns:
            Complete Article object.
        """
        # Parse metadata
        metadata = self._parse_metadata(root, manifest_data)
        
        # Parse body
        body = self._parse_body(root)
        
        # Parse references
        references = self._parse_references(root)
        
        # Parse back matter
        back_matter = self._parse_back_matter(root)
        
        return Article(
            metadata=metadata,
            body=body,
            references=references,
            back_matter=back_matter,
        )
    
    def _parse_metadata(self, root: etree.Element, manifest_data: Optional[dict]):
        """Parse article metadata from front matter."""
        # Implementation details...
        pass
    
    def _parse_body(self, root: etree.Element):
        """Parse article body sections."""
        # Implementation details...
        pass
    
    def _parse_references(self, root: etree.Element):
        """Parse reference list."""
        # Implementation details...
        pass
    
    def _parse_back_matter(self, root: etree.Element):
        """Parse back matter."""
        # Implementation details...
        pass


# ============================================================================
# eLife Parser
# ============================================================================

class ELifeParser(BaseJATSParser):
    """Parser for eLife JATS XML files.
    
    Handles eLife-specific XML structure and metadata organization.
    """
    
    def _parse_manifest(self, manifest_path: Path) -> dict:
        """eLife doesn't use manifest files.
        
        Raises:
            NotImplementedError: eLife doesn't support manifest files.
        """
        raise NotImplementedError("eLife parser does not support manifest files")
    
    def _build_article(self, root: etree.Element, manifest_data: Optional[dict]) -> Article:
        """Build Article from eLife JATS XML.
        
        Args:
            root: Root element of JATS XML.
            manifest_data: Should be None for eLife.
            
        Returns:
            Complete Article object.
        """
        # Parse metadata (eLife-specific structure)
        metadata = self._parse_metadata(root)
        
        # Parse body
        body = self._parse_body(root)
        
        # Parse references
        references = self._parse_references(root)
        
        # Parse back matter
        back_matter = self._parse_back_matter(root)
        
        return Article(
            metadata=metadata,
            body=body,
            references=references,
            back_matter=back_matter,
        )
    
    def _parse_metadata(self, root: etree.Element):
        """Parse eLife article metadata."""
        # Implementation details...
        pass
    
    def _parse_body(self, root: etree.Element):
        """Parse eLife article body."""
        # Implementation details...
        pass
    
    def _parse_references(self, root: etree.Element):
        """Parse eLife references."""
        # Implementation details...
        pass
    
    def _parse_back_matter(self, root: etree.Element):
        """Parse eLife back matter."""
        # Implementation details...
        pass


# ============================================================================
# Parser Factory
# ============================================================================

_PARSER_REGISTRY: dict[str, Type[BaseJATSParser]] = {
    "biorxiv": BioRxivParser,
    "elife": ELifeParser,
}


def get_parser(source: str) -> Type[BaseJATSParser]:
    """Get parser class for specified source.
    
    Args:
        source: Source identifier (biorxiv, elife, etc.).
        
    Returns:
        Parser class for the source.
        
    Raises:
        ValueError: If source is not supported.
    """
    if source not in _PARSER_REGISTRY:
        supported = ", ".join(_PARSER_REGISTRY.keys())
        raise ValueError(f"Unsupported source: {source}. Supported: {supported}")
    
    return _PARSER_REGISTRY[source]


def register_parser(source: str, parser_cls: Type[BaseJATSParser]) -> None:
    """Register a new parser for a source.
    
    Args:
        source: Source identifier.
        parser_cls: Parser class to register.
    """
    _PARSER_REGISTRY[source] = parser_cls
```

### 6. Testing Pattern

```python
"""Tests for jxp convert command."""

import pytest
from pathlib import Path
from jxp.jxp_convert import run_convert, validate_convert_args
from argparse import Namespace, ArgumentParser


@pytest.fixture
def sample_biorxiv_xml(tmp_path):
    """Create a sample bioRxiv JATS XML file."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD v1.2 20190208//EN" "JATS-archivearticle1.dtd">
    <article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML">
        <front>
            <article-meta>
                <title-group>
                    <article-title>Sample bioRxiv Article</article-title>
                </title-group>
                <contrib-group>
                    <contrib contrib-type="author">
                        <name>
                            <surname>Smith</surname>
                            <given-names>John</given-names>
                        </name>
                    </contrib>
                </contrib-group>
                <abstract>
                    <p>This is a test abstract.</p>
                </abstract>
            </article-meta>
        </front>
        <body>
            <sec>
                <title>Introduction</title>
                <p>This is the introduction.</p>
            </sec>
        </body>
        <back>
            <ref-list>
                <ref id="ref1">
                    <element-citation>
                        <person-group person-group-type="author">
                            <name>
                                <surname>Doe</surname>
                                <given-names>Jane</given-names>
                            </name>
                        </person-group>
                        <article-title>A reference article</article-title>
                        <year>2023</year>
                    </element-citation>
                </ref>
            </ref-list>
        </back>
    </article>
    """
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def sample_manifest(tmp_path):
    """Create a sample manifest.xml for bioRxiv."""
    manifest_content = """<?xml version="1.0"?>
    <manifest>
        <collection>neuroscience</collection>
        <version>1</version>
        <related-article doi="10.1101/12345" related-article-type="preprint"/>
    </manifest>
    """
    manifest_file = tmp_path / "manifest.xml"
    manifest_file.write_text(manifest_content)
    return manifest_file


def test_convert_biorxiv_to_stdout(sample_biorxiv_xml, capsys):
    """Test converting bioRxiv XML to stdout."""
    parser = ArgumentParser()
    args = Namespace(
        itype="biorxiv",
        xml=sample_biorxiv_xml,
        output=None,
        otype="markdown",
        flavor="commonmark",
        manifest=None,
    )
    
    run_convert(parser, args)
    captured = capsys.readouterr()
    
    assert "Sample bioRxiv Article" in captured.out
    assert "Introduction" in captured.out
    assert "John Smith" in captured.out


def test_convert_biorxiv_with_manifest(sample_biorxiv_xml, sample_manifest, tmp_path):
    """Test converting bioRxiv XML with manifest to file."""
    output_file = tmp_path / "output.md"
    parser = ArgumentParser()
    args = Namespace(
        itype="biorxiv",
        xml=sample_biorxiv_xml,
        output=output_file,
        otype="markdown",
        flavor="commonmark",
        manifest=sample_manifest,
    )
    
    run_convert(parser, args)
    
    assert output_file.exists()
    content = output_file.read_text()
    assert "Sample bioRxiv Article" in content


def test_convert_gfm_flavor(sample_biorxiv_xml, tmp_path):
    """Test GitHub-flavored Markdown conversion."""
    output_file = tmp_path / "output.md"
    parser = ArgumentParser()
    args = Namespace(
        itype="biorxiv",
        xml=sample_biorxiv_xml,
        output=output_file,
        otype="markdown",
        flavor="gfm",
        manifest=None,
    )
    
    run_convert(parser, args)
    
    assert output_file.exists()


def test_validate_missing_input_file():
    """Test validation fails for missing input file."""
    parser = ArgumentParser()
    args = Namespace(
        itype="biorxiv",
        xml=Path("/nonexistent/file.xml"),
        output=None,
        otype="markdown",
        flavor="commonmark",
        manifest=None,
    )
    
    with pytest.raises(SystemExit):
        validate_convert_args(parser, args)


def test_validate_manifest_for_wrong_itype():
    """Test validation fails when manifest provided for non-bioRxiv."""
    parser = ArgumentParser()
    args = Namespace(
        itype="elife",
        xml=Path("test.xml"),
        output=None,
        otype="markdown",
        flavor="commonmark",
        manifest=Path("manifest.xml"),
    )
    
    with pytest.raises(SystemExit):
        validate_convert_args(parser, args)


# ============================================================================
# Parser Tests
# ============================================================================

def test_biorxiv_parser(sample_biorxiv_xml):
    """Test bioRxiv parser."""
    from jxp.parsers import get_parser
    
    parser_cls = get_parser("biorxiv")
    parser = parser_cls()
    
    article = parser.parse(sample_biorxiv_xml)
    
    assert article.metadata.title == "Sample bioRxiv Article"
    assert len(article.metadata.authors) == 1
    assert article.metadata.authors[0].surname == "Smith"
    assert len(article.body) > 0


def test_biorxiv_parser_with_manifest(sample_biorxiv_xml, sample_manifest):
    """Test bioRxiv parser with manifest."""
    from jxp.parsers import get_parser
    
    parser_cls = get_parser("biorxiv")
    parser = parser_cls()
    
    article = parser.parse(sample_biorxiv_xml, manifest=sample_manifest)
    
    assert article.metadata.title == "Sample bioRxiv Article"
    # Additional assertions based on manifest data


# ============================================================================
# Converter Tests
# ============================================================================

def test_markdown_converter():
    """Test Markdown converter."""
    from jxp.converters import get_converter
    from jxp.models.article import Article, Metadata, Author
    
    # Create minimal article
    article = Article(
        metadata=Metadata(
            title="Test Article",
            authors=[Author(
                author_id="1",
                given_names="John",
                surname="Doe",
            )],
        ),
        body=[],
        references=[],
    )
    
    converter_cls = get_converter("markdown")
    converter = converter_cls()
    
    markdown = converter.convert(article)
    
    assert "# Test Article" in markdown
    assert "John Doe" in markdown


def test_markdown_gfm_flavor():
    """Test GitHub-flavored Markdown."""
    from jxp.converters.markdown import MarkdownConverter
    
    converter = MarkdownConverter(flavor="gfm")
    assert converter.flavor == "gfm"


def test_markdown_invalid_flavor():
    """Test invalid Markdown flavor raises error."""
    from jxp.converters.markdown import MarkdownConverter
    
    with pytest.raises(ValueError):
        MarkdownConverter(flavor="invalid")
```

## Naming Conventions

### Files and Modules
- Main CLI: `main.py`
- Subcommands: `jxp_<command>.py` (e.g., `jxp_convert.py`, `jxp_validate.py`)
- Models: Descriptive names in `models/` directory (e.g., `article.py`, `metadata.py`, `author.py`)
- Parsers: Source-specific in `parsers/` directory (e.g., `biorxiv.py`, `elife.py`)
- Converters: Format-specific in `converters/` directory (e.g., `markdown.py`)
- Tests: `test_<module>.py` (e.g., `test_parsers.py`, `test_converters.py`)

### Functions
- Setup args: `setup_<command>_args(parser)`
- Validate args: `validate_<command>_args(parser, args)`
- Run command: `run_<command>(parser, args)`
- Utility functions: `snake_case` (e.g., `parse_jats`, `convert_to_markdown`)

### Classes
- Models: `PascalCase` (e.g., `Article`, `Metadata`, `Section`)
- Input models: `<Model>Input` (e.g., `AuthorInput`, `ArticleInput`)

### Variables
- Use descriptive `snake_case` names
- Constants: `UPPER_SNAKE_CASE`
- Short names acceptable in limited scopes (e.g., `i`, `j` for indices)

## Documentation Standards

### Module Docstrings
```python
"""Brief one-line description.

More detailed explanation if needed. Can include examples, usage notes,
and references to related modules.
"""
```

### Function Docstrings
```python
def parse_jats(xml_path: Path) -> Article:
    """Parse a JATS XML file into an Article model.

    Args:
        xml_path: Path to the JATS XML file.

    Returns:
        Article model representing the parsed content.

    Raises:
        ValueError: If XML is malformed or invalid.
        FileNotFoundError: If xml_path doesn't exist.
    """
```

### Class Docstrings
```python
class Article(BaseModel):
    """Complete JATS article representation.
    
    This model captures the full structure of a JATS article including
    metadata, body content, and references.
    
    Attributes:
        metadata: Article metadata (title, authors, etc.).
        body: List of top-level sections.
        references: Bibliography entries.
    """
```

## Code Quality Tools

### Makefile
```makefile
.PHONY: clean build upload release test lint

clean:
	rm -rf build dist *.egg-info
	rm -rf .coverage .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

build:
	uv run python -m build

upload:
	uvx twine upload dist/*

version:
	@uv run python -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_bytes().decode())['project']['version'])"

release:
	@if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then echo "Switch to main"; exit 1; fi
	@if [ -n "$(git status --porcelain)" ]; then echo "Working tree not clean"; exit 1; fi
	@git pull --ff-only
	@uv run pytest || exit 1
	@version=$(make version); \
	git tag -a "v$version" -m "Release v$version"; \
	git push origin main && git push origin --tags; \
	make clean build upload
```

### Pre-commit Configuration
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.1
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

## Best Practices

### Type Hints
- Use type hints for all function signatures
- Use `Optional[T]` for nullable values
- Use `List[T]`, `Dict[K, V]` for collections
- Import from `typing` module

### Error Handling
- Use specific exception types
- Validate user input early
- Provide helpful error messages
- Use `parser.error()` for CLI argument errors

### Code Style
- Follow PEP 8 (enforced by ruff)
- Line length: 88 characters (Black-compatible)
- Use f-strings for formatting
- Prefer pathlib over os.path
- Use context managers (`with`) for file operations

### Testing
- One test file per module
- Use descriptive test names: `test_<what>_<condition>`
- Use fixtures for reusable test data
- Aim for high coverage (>80%)
- Test both success and failure cases

- Git Workflow
- Commit messages: Present tense, imperative mood
- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- Keep commits focused and atomic
- Run tests before committing (via pre-commit)

## Common Development Tasks

### Adding a New JATS Element Type

When you need to parse a new JATS element (e.g., supplementary materials):

1. **Add to ContentType enum:**
```python
# jxp/models/element.py
class ContentType(str, Enum):
    # ...existing types...
    SUPPLEMENTARY = "supplementary"
```

2. **Create model class:**
```python
class SupplementaryMaterial(BaseModel):
    """Supplementary material."""
    supp_id: str
    label: Optional[str] = None
    caption: Optional[str] = None
    mimetype: Optional[str] = None
    href: Optional[str] = None
```

3. **Update parser:**
```python
# In parser's _parse_body or relevant method
def _parse_supplementary(self, element):
    return SupplementaryMaterial(
        supp_id=element.get('id'),
        label=self._get_element_text(element, './/label'),
        # ...
    )
```

4. **Update converter:**
```python
# In converter's _convert_element
elif element.element_type == ContentType.SUPPLEMENTARY:
    return self._convert_supplementary(element.content)

def _convert_supplementary(self, supp):
    return f"**{supp.label}:** [Download]({supp.href})"
```

### Debugging XML Parsing

Use these utilities for debugging JATS XML structure:

```python
# Print XML tree structure
from lxml import etree

tree = etree.parse('article.xml')
print(etree.tostring(tree, pretty_print=True).decode())

# Find all elements with a specific tag
elements = tree.xpath('//sec')
for elem in elements:
    print(elem.tag, elem.get('id'))

# Print all attributes of an element
for key, value in element.attrib.items():
    print(f"{key}: {value}")
```

### Testing New Parsers

Template for testing new parser implementations:

```python
def test_new_source_parser(tmp_path):
    """Test new source parser."""
    # 1. Create test XML
    xml_content = """<?xml version="1.0"?>
    <article>...</article>
    """
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content)
    
    # 2. Parse
    from jxp.parsers import get_parser
    parser = get_parser("newsource")()
    article = parser.parse(xml_file)
    
    # 3. Assert expected structure
    assert article.metadata.title == "Expected Title"
    assert len(article.body) > 0
    
    # 4. Verify specific fields
    assert article.metadata.authors[0].surname == "Smith"
```

### Performance Optimization Tips

For large JATS files:

1. **Use iterparse for streaming:**
```python
from lxml import etree

def parse_large_file(xml_path):
    context = etree.iterparse(xml_path, events=('start', 'end'))
    for event, elem in context:
        if event == 'end' and elem.tag == 'ref':
            # Process reference
            elem.clear()  # Free memory
```

2. **Lazy load sections:**
```python
class Article(BaseModel):
    # Use generators for large sections
    @property
    def body_sections(self):
        for section in self._body:
            yield section
```

3. **Cache parsed results:**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def parse_reference(ref_xml):
    # Parse reference XML
    pass
```

## Troubleshooting

### Common Issues

**Issue**: lxml installation fails
- **Solution**: Install system dependencies: `apt-get install libxml2-dev libxslt-dev` (Ubuntu) or `brew install libxml2` (macOS)

**Issue**: Parser fails on valid JATS XML
- **Solution**: Check namespace handling. Many JATS files use default namespace:
```python
namespaces = {'jats': 'http://jats.nlm.nih.gov'}
# May need to use local-name() in XPath
elements = root.xpath('.//*[local-name()="article-title"]')
```

**Issue**: Markdown output has encoding issues
- **Solution**: Ensure UTF-8 encoding throughout:
```python
output_file.write_text(markdown, encoding='utf-8')
```

**Issue**: Memory usage high with large files
- **Solution**: Use streaming parser (iterparse) or process in chunks

## Documentation Standards

### Adding Examples

Place example files in `tests/fixtures/`:
```
tests/fixtures/
├── biorxiv/
│   ├── simple_article.xml
│   ├── complex_article.xml
│   └── manifest.xml
└── elife/
    └── sample_article.xml
```

Reference in documentation:
```markdown
See `tests/fixtures/biorxiv/simple_article.xml` for a minimal example.
```

### Updating API Documentation

When adding new public methods:
1. Add comprehensive docstring with Args/Returns/Raises
2. Include usage example in docstring
3. Update relevant documentation in `docs/`
4. Consider adding to cookbook/FAQ if it solves common problem

---

## Quick Reference: Key Files

| File/Directory | Purpose |
|---------------|---------|
| `jxp/main.py` | CLI entry point, argument parsing, command routing |
| `jxp/jxp_convert.py` | Convert command implementation |
| `jxp/models/article.py` | Complete Article model and all submodels |
| `jxp/models/metadata.py` | Metadata-specific models (authors, affiliations, etc.) |
| `jxp/parsers/base.py` | Abstract base parser class |
| `jxp/parsers/biorxiv.py` | bioRxiv-specific parser with manifest support |
| `jxp/parsers/elife.py` | eLife-specific parser |
| `jxp/converters/base.py` | Abstract base converter class |
| `jxp/converters/markdown.py` | Markdown converter with multiple flavors |
| `jxp/utils.py` | Shared utility functions |
| `tests/conftest.py` | Pytest fixtures and configuration |
| `tests/fixtures/` | Example JATS files for testing |
| `pyproject.toml` | Project configuration, dependencies, metadata |
| `.pre-commit-config.yaml` | Git hooks for code quality |
| `Makefile` | Common development tasks |

## Summary

This code style guide provides a complete blueprint for building `jxp`, a modular and extensible JATS XML parser and converter. The design emphasizes:

- **Type safety** through Pydantic models
- **Extensibility** through parser and converter registration patterns
- **Source awareness** via explicit input type flags
- **Modern Python practices** with tools like uv and ruff
- **Comprehensive testing** with pytest
- **Clean CLI design** following seqspec patterns

Follow these patterns consistently to maintain code quality and make the project easy to extend and maintain.

## CLI Design Principles

### Command Structure
```
jxp convert -i <itype> <input.xml> [options]      # Convert with required input type
jxp convert -i biorxiv article.xml                # bioRxiv to markdown (stdout)
jxp convert -i biorxiv article.xml -m manifest.xml # Include manifest
jxp convert -i elife article.xml -t html          # eLife to HTML
jxp validate -i <itype> <input.xml>               # Validate XML
jxp info <input.xml>                              # Display article info
```

### Options
- Use short (`-o`) and long (`--output`) forms
- Required positional arguments first
- Optional flags after
- Provide sensible defaults
- Use `--help` for documentation

### Output
- Default to stdout for data output
- Use stderr for progress/status messages
- Provide `--quiet` flag for automation
- Provide `--verbose` flag for debugging

## Version Management

- Use semantic versioning (MAJOR.MINOR.PATCH)
- Update version in `pyproject.toml`
- Maintain `CHANGELOG.md` with release notes
- Tag releases in git: `v0.1.0`
- Document breaking changes clearly

## Source-Specific Considerations

### bioRxiv Support

bioRxiv articles may have an optional `manifest.xml` file that contains additional metadata:

**Manifest Structure:**
- Collection/category information
- Version history
- Related article links (e.g., published version)
- Peer review URLs

**Usage:**
```bash
# Without manifest (article metadata only)
jxp convert -i biorxiv article.xml -o output.md

# With manifest (enhanced metadata)
jxp convert -i biorxiv article.xml -m manifest.xml -o output.md
```

**Parser Implementation:**
- Manifest is optional; parser should work without it
- Manifest data should supplement, not replace, article metadata
- Store manifest data in `custom_metadata` field for preservation

### eLife Support

eLife articles follow a slightly different JATS structure:

**Key Differences:**
- No manifest file support
- Different metadata organization
- Specific handling of research articles vs reviews
- Enhanced data availability statements

**Usage:**
```bash
jxp convert -i elife article.xml -o output.md
```

## Extensibility Patterns

### Adding New Input Sources

To add support for a new source (e.g., PLoS, PMC):

1. **Create parser class:**
```python
# jxp/parsers/plos.py
from jxp.parsers.base import BaseJATSParser

class PLoSParser(BaseJATSParser):
    def _parse_manifest(self, manifest_path):
        # PLoS-specific manifest handling
        pass
    
    def _build_article(self, root, manifest_data):
        # PLoS-specific parsing logic
        pass
```

2. **Register parser:**
```python
# jxp/parsers/__init__.py
from .plos import PLoSParser
register_parser("plos", PLoSParser)
```

3. **Update CLI:**
```python
# Add "plos" to choices in jxp_convert.py
choices=["biorxiv", "elife", "plos"]
```

### Adding New Output Formats

To add support for a new output format (e.g., HTML, JSON):

1. **Create converter class:**
```python
# jxp/converters/html.py
from jxp.converters.base import BaseConverter

class HTMLConverter(BaseConverter):
    def convert(self, article):
        # HTML conversion logic
        pass
```

2. **Register converter:**
```python
# jxp/converters/__init__.py
from .html import HTMLConverter
register_converter("html", HTMLConverter)
```

3. **Update CLI:**
```python
# Add "html" to choices in jxp_convert.py
choices=["markdown", "html", "json"]
```
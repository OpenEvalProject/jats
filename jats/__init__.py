"""jats: JATS XML Parser for scientific articles."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jats")
except PackageNotFoundError:
    __version__ = "0.0.0"

# Bundle functions
from .bundle import build_citation_occurrences, build_document_bundle

# Conversion functions
from .converter import (
    convert_response_to_markdown,
    convert_review_to_markdown,
    convert_to_markdown,
)

# Core parsing functions
from .parser import (
    parse_abstract,
    parse_affiliations_detailed,
    parse_authors,
    parse_doi,
    parse_jats_xml,
    parse_pub_date,
    parse_title,
)

__all__ = [
    # Bundle functions
    "build_document_bundle",
    "build_citation_occurrences",
    # Parser functions
    "parse_jats_xml",
    "parse_doi",
    "parse_title",
    "parse_abstract",
    "parse_pub_date",
    "parse_authors",
    "parse_affiliations_detailed",
    # Converter functions
    "convert_to_markdown",
    "convert_review_to_markdown",
    "convert_response_to_markdown",
]

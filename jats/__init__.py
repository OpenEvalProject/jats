"""jats: JATS XML Parser for scientific articles."""

__version__ = "0.1.0"

# Core parsing functions
from .parser import (
    parse_jats_xml,
    parse_doi,
    parse_title,
    parse_abstract,
    parse_pub_date,
    parse_authors,
    parse_affiliations_detailed,
)

# Conversion functions
from .converter import (
    convert_to_markdown,
    convert_review_to_markdown,
    convert_response_to_markdown,
)

__all__ = [
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

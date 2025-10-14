"""Data models for JATS articles."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Author:
    """Author information."""

    given_names: str
    surname: str
    orcid: Optional[str] = None
    affiliation_id: Optional[str] = None
    affiliation: Optional[str] = None
    corresponding: bool = False


@dataclass
class Figure:
    """Figure with caption and metadata."""

    figure_id: str
    label: Optional[str] = None
    caption: Optional[str] = None
    graphic_href: Optional[str] = None
    file_path: Optional[str] = None  # From manifest


@dataclass
class ContentItem:
    """Content item in a section (paragraph or figure)."""

    item_type: str  # 'paragraph' or 'figure'
    text: Optional[str] = None  # For paragraphs
    figure: Optional[Figure] = None  # For figures


@dataclass
class Section:
    """Article section."""

    title: Optional[str] = None
    content_items: List[ContentItem] = field(default_factory=list)


@dataclass
class Reviewer:
    """Reviewer information from sub-article."""

    given_names: str
    surname: str
    role: Optional[str] = None
    affiliation: Optional[str] = None
    orcid: Optional[str] = None
    is_anonymous: bool = False


@dataclass
class SubArticle:
    """Sub-article (reviewer comments, author response)."""

    article_type: str  # e.g., 'article-commentary', 'reply'
    title: str
    doi: Optional[str] = None
    reviewers: List[Reviewer] = field(default_factory=list)
    body: List[Section] = field(default_factory=list)

    # JATS4R custom metadata
    revision_round: Optional[int] = None  # peer-review-revision-round
    recommendation: Optional[str] = None  # peer-review-recommendation


@dataclass
class Article:
    """Complete article representation."""

    title: str
    authors: List[Author] = field(default_factory=list)
    affiliations: Dict[str, str] = field(default_factory=dict)  # id -> text
    abstract: str = ""
    body: List[Section] = field(default_factory=list)
    sub_articles: List[SubArticle] = field(default_factory=list)

    # Metadata for different sources
    is_elife: bool = False
    article_id: Optional[str] = None  # eLife article ID for CDN URLs

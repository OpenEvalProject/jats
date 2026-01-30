"""Data models for JATS articles."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Author:
    """Author information."""

    given_names: str
    surname: str
    orcid: Optional[str] = None
    affiliation_ids: List[str] = field(default_factory=list)  # Multiple affiliation IDs
    corresponding: bool = False
    position: Optional[int] = None  # Author order (1-indexed)

    # Legacy fields for backwards compatibility
    affiliation_id: Optional[str] = None
    affiliation: Optional[str] = None


@dataclass
class Figure:
    """Figure with caption and metadata."""

    figure_id: str
    label: Optional[str] = None
    caption: Optional[str] = None
    graphic_href: Optional[str] = None
    file_path: Optional[str] = None  # From manifest


@dataclass
class TableCell:
    """Table cell with content and attributes."""

    content: str
    rowspan: Optional[int] = None
    colspan: Optional[int] = None


@dataclass
class Table:
    """Table with caption and data."""

    table_id: str
    label: Optional[str] = None
    caption: Optional[str] = None
    headers: List[List[TableCell]] = field(default_factory=list)  # List of header rows
    rows: List[List[TableCell]] = field(default_factory=list)  # List of data rows
    footer: Optional[str] = None


@dataclass
class ContentItem:
    """Content item in a section (paragraph, figure, or table)."""

    item_type: str  # 'paragraph', 'figure', or 'table'
    text: Optional[str] = None  # For paragraphs
    figure: Optional[Figure] = None  # For figures
    table: Optional['Table'] = None  # For tables


@dataclass
class Section:
    """Article section."""

    title: Optional[str] = None
    content_items: List[ContentItem] = field(default_factory=list)
    level: int = 2  # Heading level (2=##, 3=###, etc.)


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
    affiliations: Dict[str, str] = field(default_factory=dict)  # id -> text (legacy)
    affiliations_detailed: Dict[str, Dict[str, Optional[str]]] = field(default_factory=dict)  # id -> structured data
    references: Dict[str, str] = field(default_factory=dict)  # ref-id -> DOI
    figure_urls: Dict[str, str] = field(default_factory=dict)  # figure-id -> image URL
    abstract: str = ""
    body: List[Section] = field(default_factory=list)
    sub_articles: List[SubArticle] = field(default_factory=list)

    # Metadata for different sources
    is_elife: bool = False
    article_id: Optional[str] = None  # eLife article ID for CDN URLs


@dataclass
class ElifeAssessment:
    """eLife assessment data from JATS XML editor-report sub-article."""

    assessment: Optional[str] = None  # Assessment body text
    editor_name: Optional[str] = None  # Reviewing editor name
    affiliation: Optional[str] = None  # Editor affiliation
    findings_significance: Optional[str] = None  # Significance rating
    evidence_strength: Optional[str] = None  # Evidence strength rating

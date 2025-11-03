"""JATS XML parser."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lxml import etree

from .models import Article, Author, ContentItem, Figure, Reviewer, Section, SubArticle


def parse_affiliations_detailed(root: etree.Element) -> Dict[str, Dict[str, Optional[str]]]:
    """Parse detailed affiliation information from JATS XML.

    Returns:
        Dictionary mapping affiliation IDs to structured affiliation data with keys:
        - institution, department, city, country, ror
    """
    contrib_group = root.find('.//contrib-group')
    if contrib_group is None:
        return {}

    affiliations = {}
    for aff in contrib_group.findall('.//aff'):
        aff_id = aff.get('id', '')

        # Extract structured affiliation data
        institution = None
        department = None
        city = None
        country = None
        ror = None

        # Look for ROR identifier
        ror_elem = aff.find('.//institution-id[@institution-id-type="ror"]')
        if ror_elem is not None and ror_elem.text:
            ror_text = ror_elem.text.strip()
            # Extract ROR ID from URL if present
            if 'ror.org/' in ror_text:
                ror = ror_text.split('ror.org/')[-1]
            else:
                ror = ror_text

        # Look for institution elements
        inst_elems = aff.findall('.//institution')
        if inst_elems:
            # First, identify which elements are departments
            dept_inst = None
            non_dept_insts = []

            for inst in inst_elems:
                if inst.get('content-type') == 'dept' and inst.text:
                    dept_inst = inst.text.strip()
                elif inst.text:
                    non_dept_insts.append(inst.text.strip())

            # Set department if we found one
            if dept_inst:
                department = dept_inst

            # Set institution from non-department institutions
            if non_dept_insts:
                if len(non_dept_insts) == 1:
                    institution = non_dept_insts[0]
                else:
                    # Multiple institutions, concatenate them
                    institution = ', '.join(non_dept_insts)
            elif not dept_inst and inst_elems:
                # No dept attribute found, treat first as institution
                institution = inst_elems[0].text.strip() if inst_elems[0].text else None

        # Look for city
        city_elem = aff.find('.//named-content[@content-type="city"]')
        if city_elem is not None and city_elem.text:
            city = city_elem.text.strip()
        elif aff.find('.//city') is not None:
            city_elem = aff.find('.//city')
            if city_elem.text:
                city = city_elem.text.strip()

        # Look for country
        country_elem = aff.find('.//country')
        if country_elem is not None and country_elem.text:
            country = country_elem.text.strip()

        affiliations[aff_id] = {
            'institution': institution,
            'department': department,
            'city': city,
            'country': country,
            'ror': ror
        }

    return affiliations


def parse_authors(root: etree.Element) -> Tuple[List[Author], Dict[str, str]]:
    """Parse author information from JATS XML.

    Returns:
        Tuple of (authors list, affiliations dict)
    """
    contrib_group = root.find('.//contrib-group')
    if contrib_group is None:
        return [], {}

    # Parse affiliations
    affiliations = {}
    for aff in contrib_group.findall('.//aff'):
        aff_id = aff.get('id', '')

        # Get all text from affiliation, excluding label and institution-id
        parts = []
        for elem in aff.iter():
            if elem.tag in ['label', 'institution-id']:
                continue
            if elem.text and elem.text.strip():
                text = elem.text.strip().strip(',').strip()
                if text:
                    parts.append(text)
            if elem.tail and elem.tail.strip():
                tail = elem.tail.strip().strip(',').strip()
                if tail:
                    parts.append(tail)

        affiliation_text = ' '.join(parts)
        affiliations[aff_id] = affiliation_text

    # Parse authors
    authors = []
    for position, contrib in enumerate(contrib_group.findall('.//contrib[@contrib-type="author"]'), start=1):
        # Get name
        name_elem = contrib.find('.//name')
        if name_elem is None:
            continue

        given = name_elem.find('given-names')
        surname = name_elem.find('surname')

        given_text = given.text if given is not None else ''
        surname_text = surname.text if surname is not None else ''

        # Get ORCID
        orcid = None
        orcid_elem = contrib.find('.//contrib-id[@contrib-id-type="orcid"]')
        if orcid_elem is not None and orcid_elem.text:
            orcid = orcid_elem.text.replace('http://orcid.org/', '').replace(
                'https://orcid.org/', ''
            )

        # Get ALL affiliation references (not just first)
        affiliation_ids = []
        aff_refs = contrib.findall('.//xref[@ref-type="aff"]')
        for aff_ref in aff_refs:
            aff_id = aff_ref.get('rid', '')
            if aff_id and aff_id in affiliations:
                affiliation_ids.append(aff_id)

        # Check if corresponding author
        corresponding = contrib.get('corresp') == 'yes'

        # For backwards compatibility, set first affiliation as affiliation_id
        affiliation_id = affiliation_ids[0] if affiliation_ids else None
        affiliation = affiliations[affiliation_id] if affiliation_id else None

        authors.append(
            Author(
                given_names=given_text,
                surname=surname_text,
                orcid=orcid,
                affiliation_ids=affiliation_ids,
                corresponding=corresponding,
                position=position,
                # Legacy fields
                affiliation_id=affiliation_id,
                affiliation=affiliation,
            )
        )

    return authors, affiliations


def parse_title(root: etree.Element) -> str:
    """Extract article title."""
    title = root.find('.//article-title')
    if title is None:
        return ""

    # Use itertext() to get all text including from child elements like <italic>
    return ''.join(title.itertext()).strip()


def parse_abstract(root: etree.Element) -> str:
    """Extract abstract text.

    Uses itertext() to match the text extraction used by find command
    and extract_text_with_citations() for consistency.
    """
    abstract = root.find('.//abstract')
    if abstract is None:
        return ""

    # Use itertext() for consistency with find and body paragraph extraction
    # This ensures queries extracted from markdown can be found in XML
    return ''.join(abstract.itertext()).strip()


def parse_doi(root: etree.Element) -> str:
    """Extract DOI from article metadata."""
    doi_elem = root.find('.//article-id[@pub-id-type="doi"]')
    if doi_elem is not None and doi_elem.text:
        return doi_elem.text.strip()
    return ""


def parse_references(root: etree.Element) -> Dict[str, str]:
    """Parse references to build mapping of ref-id to DOI.

    Returns:
        Dictionary mapping reference IDs to DOIs
    """
    references = {}

    for ref in root.findall('.//ref'):
        ref_id = ref.get('id')
        if not ref_id:
            continue

        # Look for DOI in pub-id elements
        doi_elem = ref.find('.//pub-id[@pub-id-type="doi"]')
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()
            references[ref_id] = doi

    return references


def parse_pub_date(root: etree.Element) -> str:
    """Extract publication date from article metadata.

    Returns date in YYYY-MM-DD format, or empty string if not found.
    """
    # Look for pub-date with date-type="pub"
    pub_date = root.find('.//pub-date[@date-type="pub"]')

    # If not found, try pub-date with pub-type="epub" or just first pub-date
    if pub_date is None:
        pub_date = root.find('.//pub-date[@pub-type="epub"]')
    if pub_date is None:
        pub_date = root.find('.//pub-date')

    if pub_date is None:
        return ""

    # Extract day, month, year
    year_elem = pub_date.find('year')
    month_elem = pub_date.find('month')
    day_elem = pub_date.find('day')

    year = year_elem.text.strip() if year_elem is not None and year_elem.text else ""
    month = month_elem.text.strip() if month_elem is not None and month_elem.text else "01"
    day = day_elem.text.strip() if day_elem is not None and day_elem.text else "01"

    if not year:
        return ""

    # Pad month and day with leading zeros if needed
    month = month.zfill(2)
    day = day.zfill(2)

    return f"{year}-{month}-{day}"


def load_manifest(manifest_path: Path) -> Dict[str, str]:
    """Load figure mappings from manifest.xml.

    Returns:
        Dictionary mapping figure IDs to file paths
    """
    if not manifest_path.exists():
        return {}

    try:
        tree = etree.parse(str(manifest_path))
        root = tree.getroot()

        figure_map = {}

        # Get namespace from root element
        ns_uri = root.nsmap.get(None)

        if ns_uri:
            ns = {'m': ns_uri}
            for item in root.findall('.//m:item[@type="figure"]', ns):
                fig_id = item.get('id')
                instance = item.find('.//m:instance', ns)
                if fig_id and instance is not None:
                    href = instance.get('href')
                    if href:
                        figure_map[fig_id] = href
        else:
            for item in root.findall('.//item[@type="figure"]'):
                fig_id = item.get('id')
                instance = item.find('.//instance')
                if fig_id and instance is not None:
                    href = instance.get('href')
                    if href:
                        figure_map[fig_id] = href

        return figure_map
    except Exception as e:
        print(f"Error loading manifest: {e}")
        return {}


def build_figure_urls(
    figures: Dict[str, Figure], article_id: str = None, is_elife: bool = False
) -> Dict[str, str]:
    """Build mapping of figure IDs to their image URLs.

    Args:
        figures: Dictionary of Figure objects
        article_id: Article ID for constructing eLife URLs
        is_elife: Whether this is an eLife article

    Returns:
        Dictionary mapping figure IDs to image URLs
    """
    figure_urls = {}

    for fig_id, figure in figures.items():
        # Determine image URL
        if figure.file_path:
            # Use manifest path if available (bioRxiv)
            image_url = figure.file_path
        elif figure.graphic_href:
            graphic_href = figure.graphic_href
            # For eLife articles, construct web URL
            if is_elife and article_id:
                # Convert .tif to .jpg for web display
                base_filename = graphic_href.replace('.tif', '')
                image_url = f"https://cdn.elifesciences.org/articles/{article_id}/{base_filename}.jpg"
            else:
                image_url = graphic_href
        else:
            continue

        figure_urls[fig_id] = image_url

    return figure_urls


def parse_figures(
    root: etree.Element, figure_map: Optional[Dict[str, str]] = None
) -> Dict[str, Figure]:
    """Parse figures from JATS XML.

    Returns:
        Dictionary mapping figure IDs to Figure objects
    """
    figures = {}

    for fig in root.findall('.//fig'):
        fig_id = fig.get('id')
        if not fig_id:
            continue

        # Get label
        label = None
        label_elem = fig.find('label')
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        # Get caption
        caption = None
        caption_elem = fig.find('.//caption')
        if caption_elem is not None:
            # Remove supplementary-material elements before processing
            # (source data files that we don't want in the caption text)
            for supp_mat in caption_elem.findall('.//supplementary-material'):
                parent = supp_mat.getparent()
                if parent is not None:
                    parent.remove(supp_mat)

            caption_parts = []
            for elem in caption_elem.iter():
                # Skip title elements
                if elem.tag == 'title':
                    continue
                if elem.text:
                    caption_parts.append(elem.text)
                if elem.tail:
                    caption_parts.append(elem.tail)
            caption_text = ''.join(caption_parts).strip()
            if caption_text:
                caption = caption_text

        # Get graphic href (direct child of fig, not nested in caption/inline-formula)
        graphic_href = None
        graphic_elem = fig.find('graphic')
        if graphic_elem is not None:
            href = graphic_elem.get('{http://www.w3.org/1999/xlink}href')
            if href:
                graphic_href = href

        # Use manifest mapping if available
        file_path = None
        if figure_map and fig_id in figure_map:
            file_path = figure_map[fig_id]

        figures[fig_id] = Figure(
            figure_id=fig_id,
            label=label,
            caption=caption,
            graphic_href=graphic_href,
            file_path=file_path,
        )

    return figures


def extract_text_with_citations(
    elem: etree.Element,
    references: Optional[Dict[str, str]] = None,
    figure_urls: Optional[Dict[str, str]] = None
) -> str:
    """Extract text from element, converting citation and figure xrefs to markdown links.

    Args:
        elem: XML element to extract text from
        references: Dictionary mapping ref-ids to DOIs
        figure_urls: Dictionary mapping figure-ids to image URLs

    Returns:
        Text with citations and figure references converted to markdown links
    """
    if references is None:
        references = {}
    if figure_urls is None:
        figure_urls = {}

    parts = []

    # Add element's text
    if elem.text:
        parts.append(elem.text)

    # Process children
    for child in elem:
        # Handle citation xrefs
        if child.tag == 'xref' and child.get('ref-type') == 'bibr':
            ref_id = child.get('rid')
            citation_text = ''.join(child.itertext()).strip()

            # Convert to markdown link if DOI is available
            if ref_id and ref_id in references:
                doi = references[ref_id]
                parts.append(f"[{citation_text}](https://doi.org/{doi})")
            else:
                # No DOI available, keep plain text
                parts.append(citation_text)

        # Handle figure xrefs
        elif child.tag == 'xref' and child.get('ref-type') == 'fig':
            fig_id = child.get('rid')
            figure_text = ''.join(child.itertext()).strip()

            # Convert to markdown link if figure URL is available
            if fig_id and fig_id in figure_urls:
                fig_url = figure_urls[fig_id]
                parts.append(f"[{figure_text}]({fig_url})")
            else:
                # No URL available, keep plain text
                parts.append(figure_text)

        else:
            # Recursively extract text from other elements
            parts.append(extract_text_with_citations(child, references, figure_urls))

        # Add tail text after child
        if child.tail:
            parts.append(child.tail)

    return ''.join(parts)


def parse_body(
    root: etree.Element,
    figures: Optional[Dict[str, Figure]] = None,
    references: Optional[Dict[str, str]] = None,
    figure_urls: Optional[Dict[str, str]] = None
) -> List[Section]:
    """Parse article body sections.

    Returns:
        List of Section objects
    """
    if figures is None:
        figures = {}
    if figure_urls is None:
        figure_urls = {}

    body = root.find('.//body')
    if body is None:
        return []

    sections = []
    for sec in body.findall('.//sec'):
        section = Section()

        # Get section title
        title_elem = sec.find('title')
        if title_elem is not None:
            # Use itertext() to get all text including from child elements like <italic>
            section.title = ''.join(title_elem.itertext()).strip()

        # Get section content (paragraphs and figures in order)
        for child in sec:
            if child.tag == 'p':
                # Check if paragraph contains embedded figures (eLife style)
                embedded_figs = child.findall('.//fig')

                if embedded_figs:
                    # Paragraph has embedded figures
                    if child.text:
                        para_text = child.text.strip()
                        if para_text:
                            section.content_items.append(
                                ContentItem(item_type='paragraph', text=para_text)
                            )

                    # Process each embedded figure
                    for fig in embedded_figs:
                        fig_id = fig.get('id')
                        if fig_id and fig_id in figures:
                            section.content_items.append(
                                ContentItem(
                                    item_type='figure', figure=figures[fig_id]
                                )
                            )

                        if fig.tail and fig.tail.strip():
                            section.content_items.append(
                                ContentItem(item_type='paragraph', text=fig.tail.strip())
                            )
                else:
                    # Normal paragraph without embedded figures
                    # Extract text with citation and figure links
                    para_text = extract_text_with_citations(child, references, figure_urls).strip()
                    if para_text:
                        section.content_items.append(
                            ContentItem(item_type='paragraph', text=para_text)
                        )

            elif child.tag == 'fig':
                # Figure as direct child of section (bioRxiv style)
                fig_id = child.get('id')
                if fig_id and fig_id in figures:
                    section.content_items.append(
                        ContentItem(item_type='figure', figure=figures[fig_id])
                    )

            elif child.tag == 'fig-group':
                # Figure group containing multiple figures (eLife supplements)
                for fig in child.findall('.//fig'):
                    fig_id = fig.get('id')
                    if fig_id and fig_id in figures:
                        section.content_items.append(
                            ContentItem(item_type='figure', figure=figures[fig_id])
                        )

            elif child.tag == 'sec':
                # Nested section - skip for now
                continue

        if section.content_items or section.title:
            sections.append(section)

    return sections


def parse_reviewers(sub_article: etree.Element) -> List[Reviewer]:
    """Parse reviewer information from sub-article.

    Returns:
        List of Reviewer objects
    """
    reviewers = []

    contrib_group = sub_article.find('.//contrib-group')
    if contrib_group is None:
        return []

    for contrib in contrib_group.findall('.//contrib'):
        # Get name
        name_elem = contrib.find('.//name')
        is_anonymous = False
        given_text = ''
        surname_text = ''

        if name_elem is None:
            # Anonymous reviewer
            is_anonymous = True
            given_text = 'Anonymous'
            surname_text = 'Reviewer'
        else:
            given = name_elem.find('given-names')
            surname = name_elem.find('surname')

            given_text = given.text if given is not None and given.text else ''
            surname_text = surname.text if surname is not None and surname.text else ''

            # Check if name is actually empty (anonymous)
            if not given_text and not surname_text:
                is_anonymous = True
                given_text = 'Anonymous'
                surname_text = 'Reviewer'

        # Get role
        role = None
        role_elem = contrib.find('.//role')
        if role_elem is not None and role_elem.text:
            role = role_elem.text.strip()

        # Get ORCID
        orcid = None
        orcid_elem = contrib.find('.//contrib-id[@contrib-id-type="orcid"]')
        if orcid_elem is not None and orcid_elem.text:
            orcid = orcid_elem.text.replace('http://orcid.org/', '').replace(
                'https://orcid.org/', ''
            )

        # Get affiliation
        affiliation = None
        aff_elem = contrib.find('.//aff')
        if aff_elem is not None:
            aff_parts = []
            for elem in aff_elem.iter():
                if elem.text and elem.text.strip():
                    aff_parts.append(elem.text.strip())
                if elem.tail and elem.tail.strip():
                    aff_parts.append(elem.tail.strip())
            if aff_parts:
                affiliation = ' '.join(aff_parts)

        reviewers.append(
            Reviewer(
                given_names=given_text,
                surname=surname_text,
                role=role,
                affiliation=affiliation,
                orcid=orcid,
                is_anonymous=is_anonymous,
            )
        )

    return reviewers


def parse_sub_articles(
    root: etree.Element, figures: Optional[Dict[str, Figure]] = None
) -> List[SubArticle]:
    """Parse sub-articles (reviewer comments, author responses).

    Returns:
        List of SubArticle objects
    """
    if figures is None:
        figures = {}

    sub_articles = []

    for sub_elem in root.findall('.//sub-article'):
        # Get article type
        article_type = sub_elem.get('article-type', '')

        # Get title
        title = ''
        title_elem = sub_elem.find('.//article-title')
        if title_elem is not None:
            title = ''.join(title_elem.itertext()).strip()

        # Get DOI
        doi = None
        doi_elem = sub_elem.find('.//article-id[@pub-id-type="doi"]')
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()

        # Parse JATS4R custom metadata
        revision_round = None
        recommendation = None

        custom_meta_group = sub_elem.find('.//custom-meta-group')
        if custom_meta_group is not None:
            for custom_meta in custom_meta_group.findall('.//custom-meta'):
                meta_name_elem = custom_meta.find('meta-name')
                meta_value_elem = custom_meta.find('meta-value')

                if meta_name_elem is not None and meta_value_elem is not None:
                    meta_name = meta_name_elem.text
                    meta_value = meta_value_elem.text

                    if meta_name == 'peer-review-revision-round' and meta_value:
                        try:
                            revision_round = int(meta_value)
                        except ValueError:
                            # Invalid revision round, skip
                            pass

                    elif meta_name == 'peer-review-recommendation' and meta_value:
                        recommendation = meta_value

        # Parse reviewers
        reviewers = parse_reviewers(sub_elem)

        # Parse body (using the same parse_body logic but on sub-article body)
        body_sections = []
        body = sub_elem.find('.//body')
        if body is not None:
            # Create a temporary section to hold all content
            section = Section()

            # Process paragraphs directly under body
            for p in body.findall('.//p'):
                # Use itertext() to get all text in document order
                para_text = ''.join(p.itertext()).strip()
                if para_text:
                    section.content_items.append(
                        ContentItem(item_type='paragraph', text=para_text)
                    )

            if section.content_items:
                body_sections.append(section)

        sub_articles.append(
            SubArticle(
                article_type=article_type,
                title=title,
                doi=doi,
                reviewers=reviewers,
                body=body_sections,
                revision_round=revision_round,
                recommendation=recommendation,
            )
        )

    return sub_articles


def parse_jats_xml(xml_path: Path, manifest_path: Optional[Path] = None) -> Article:
    """Parse JATS XML file and return Article object.

    Args:
        xml_path: Path to XML file
        manifest_path: Optional path to manifest.xml

    Returns:
        Article object
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # Auto-detect manifest.xml if not provided
    if manifest_path is None:
        xml_dir = xml_path.parent
        parent_dir = xml_dir.parent
        potential_manifest = parent_dir / 'manifest.xml'
        if potential_manifest.exists():
            manifest_path = potential_manifest

    # Detect if this is an eLife article
    is_elife = False
    article_id = None

    journal_id_elem = root.find('.//journal-id[@journal-id-type="publisher-id"]')
    if journal_id_elem is not None and journal_id_elem.text:
        is_elife = journal_id_elem.text.lower() == 'elife'

    if is_elife:
        article_id_elem = root.find('.//article-id[@pub-id-type="publisher-id"]')
        if article_id_elem is not None:
            article_id = article_id_elem.text

    # Load manifest if provided
    figure_map = {}
    if manifest_path:
        figure_map = load_manifest(manifest_path)

    # Parse components
    title = parse_title(root)
    authors, affiliations = parse_authors(root)
    affiliations_detailed = parse_affiliations_detailed(root)
    references = parse_references(root)
    abstract = parse_abstract(root)
    figures = parse_figures(root, figure_map)
    figure_urls = build_figure_urls(figures, article_id, is_elife)
    body = parse_body(root, figures, references, figure_urls)
    sub_articles = parse_sub_articles(root, figures)

    return Article(
        title=title,
        authors=authors,
        affiliations=affiliations,
        affiliations_detailed=affiliations_detailed,
        references=references,
        figure_urls=figure_urls,
        abstract=abstract,
        body=body,
        sub_articles=sub_articles,
        is_elife=is_elife,
        article_id=article_id,
    )


# ============================================================================
# Text finding functionality
# ============================================================================


def get_element_xpath(element: etree.Element, root: etree.Element) -> str:
    """Get deterministic XPath for an element with positional predicates.

    Args:
        element: Element to get XPath for
        root: Root element of the document

    Returns:
        XPath string with positional predicates (e.g., /article/body/sec[1]/p[2])
    """
    if element == root:
        return f"/{root.tag}"

    path_parts = []
    current = element

    while current is not None and current != root:
        parent = current.getparent()
        if parent is None:
            break

        # Count position among siblings of same tag
        siblings = [c for c in parent if c.tag == current.tag]
        if len(siblings) > 1:
            # Multiple siblings with same tag - add position
            position = siblings.index(current) + 1  # 1-indexed
            path_parts.insert(0, f"{current.tag}[{position}]")
        else:
            # Only child with this tag - no position needed
            path_parts.insert(0, current.tag)

        current = parent

    # Build full path from root
    return f"/{root.tag}/" + "/".join(path_parts)


def normalize_text(text: str, case_sensitive: bool = False) -> str:
    """Normalize text for matching.

    Applies same normalization as markdown conversion:
    - Normalize Unicode punctuation to ASCII equivalents
    - Collapse runs of whitespace into single space
    - Trim leading/trailing whitespace
    - Optional case normalization

    Args:
        text: Text to normalize
        case_sensitive: If False, convert to lowercase

    Returns:
        Normalized text
    """
    import re
    import unicodedata

    # Normalize Unicode to NFC form (canonical composition)
    text = unicodedata.normalize('NFC', text)

    # Replace Unicode punctuation with ASCII equivalents
    # This handles smart quotes, em/en dashes, etc. commonly found in XML
    replacements = {
        '\u2018': "'",  # ' (left single quotation mark) -> '
        '\u2019': "'",  # ' (right single quotation mark) -> '
        '\u201a': "'",  # ‚ (single low-9 quotation mark) -> '
        '\u201b': "'",  # ‛ (single high-reversed-9 quotation mark) -> '
        '\u201c': '"',  # " (left double quotation mark) -> "
        '\u201d': '"',  # " (right double quotation mark) -> "
        '\u201e': '"',  # „ (double low-9 quotation mark) -> "
        '\u201f': '"',  # ‟ (double high-reversed-9 quotation mark) -> "
        '\u2013': '-',  # – (en dash) -> -
        '\u2014': '--', # — (em dash) -> --
        '\u2010': '-',  # ‐ (hyphen) -> -
        '\u2011': '-',  # ‑ (non-breaking hyphen) -> -
        '\u2012': '-',  # ‒ (figure dash) -> -
        '\u2015': '--', # ― (horizontal bar) -> --
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)

    # Collapse whitespace (including newlines, tabs) to single space
    normalized = re.sub(r'\s+', ' ', text.strip())
    if not case_sensitive:
        normalized = normalized.lower()
    return normalized


def is_text_block_element(element: etree.Element) -> bool:
    """Check if element is a text block we should index.

    We index block-level text elements, not inline formatting.
    This matches the structure used in markdown conversion.

    Args:
        element: Element to check

    Returns:
        True if this is a text block element
    """
    text_block_tags = {
        'p',            # Paragraph
        'title',        # Section title
        'article-title',  # Article title
        'abstract',     # Abstract (may contain p elements, but also direct text)
        'caption',      # Figure/table caption
        'label',        # Figure/table label
        'list-item',    # List item
        'td',           # Table cell
        'th',           # Table header
    }
    return element.tag in text_block_tags


def find_text_locations(
    root: etree.Element,
    queries: List[str],
    case_sensitive: bool = False
) -> List[Dict]:
    """Find locations of query strings in JATS XML.

    Builds a normalized text representation of the document and finds exact
    matches, returning precise XML-anchored locations.

    Args:
        root: Root element of JATS XML document
        queries: List of query strings to find
        case_sensitive: If False (default), perform case-insensitive matching

    Returns:
        List of match dictionaries, one per query. Each dict contains:
        - query: The query string
        - start: {"xpath": str, "char_offset": int} (if found)
        - stop: {"xpath": str, "char_offset": int} (if found)
        - len: Length of match in characters (if found)

        If query not found, only "query" field is present.
    """
    # Step 1: Build text index by traversing XML tree
    # Collect (xpath, text, start_pos, end_pos) for each text block
    text_blocks = []
    current_global_pos = 0

    # Walk tree in document order
    for elem in root.iter():
        if not is_text_block_element(elem):
            continue

        # Extract text using itertext() (same as converter)
        raw_text = ''.join(elem.itertext())
        normalized = normalize_text(raw_text, case_sensitive)

        if not normalized:
            continue

        xpath = get_element_xpath(elem, root)
        text_len = len(normalized)

        text_blocks.append({
            'xpath': xpath,
            'text': normalized,
            'start_pos': current_global_pos,
            'end_pos': current_global_pos + text_len,
        })

        # +1 for space between blocks (mimics markdown paragraph spacing)
        current_global_pos += text_len + 1

    # Step 2: Build full searchable text by joining blocks with spaces
    full_text = ' '.join(block['text'] for block in text_blocks)

    # Step 3: Search for each query
    results = []

    for query in queries:
        normalized_query = normalize_text(query, case_sensitive)

        # Skip empty queries
        if not normalized_query:
            results.append({'query': query})
            continue

        # Find first occurrence
        match_start = full_text.find(normalized_query)

        if match_start == -1:
            # Not found
            results.append({'query': query})
            continue

        match_end = match_start + len(normalized_query)

        # Step 4: Map global positions back to (xpath, char_offset)
        start_xpath = None
        start_offset = None
        stop_xpath = None
        stop_offset = None

        for block in text_blocks:
            # Check if match starts in this block
            if start_xpath is None:
                if block['start_pos'] <= match_start < block['end_pos']:
                    start_xpath = block['xpath']
                    start_offset = match_start - block['start_pos']

            # Check if match ends in this block
            if block['start_pos'] < match_end <= block['end_pos']:
                stop_xpath = block['xpath']
                stop_offset = match_end - block['start_pos']
                break

            # Handle case where match ends exactly at block boundary
            # (between two blocks, in the space)
            if block['end_pos'] == match_end:
                stop_xpath = block['xpath']
                stop_offset = len(block['text'])
                break

        # Build result
        if start_xpath and stop_xpath:
            results.append({
                'query': query,
                'start': {'xpath': start_xpath, 'char_offset': start_offset},
                'stop': {'xpath': stop_xpath, 'char_offset': stop_offset},
                'len': len(normalized_query)
            })
        else:
            # Edge case: match found but couldn't map (shouldn't happen)
            results.append({'query': query})

    return results

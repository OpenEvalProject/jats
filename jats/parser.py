"""JATS XML parser."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lxml import etree

from .models import Article, Author, ContentItem, Figure, Reviewer, Section, SubArticle, Table, TableCell


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

    # Remove DOI elements (eLife style)
    # Remove <object-id pub-id-type="doi"> elements
    for obj_id in abstract.findall('.//object-id[@pub-id-type="doi"]'):
        parent = obj_id.getparent()
        if parent is not None:
            parent.remove(obj_id)

    # Remove <p><bold>DOI:</bold> <ext-link>...</ext-link></p> paragraphs
    for para in abstract.findall('.//p'):
        bold_elem = para.find('bold')
        if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
            parent = para.getparent()
            if parent is not None:
                parent.remove(para)

    # Use itertext() for consistency with find and body paragraph extraction
    # This ensures queries extracted from markdown can be found in XML
    return ''.join(abstract.itertext()).strip()


def mathml_to_latex(elem: etree.Element) -> str:
    """Convert MathML element to LaTeX string.

    Handles common MathML elements for inline and display math formulas.

    Args:
        elem: MathML element (typically <mml:math>)

    Returns:
        LaTeX representation of the formula
    """
    # Get tag name without namespace
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

    # Text content (for mi, mn, mo elements)
    if tag in ['mi', 'mn', 'mo', 'mtext']:
        text = elem.text or ''
        # Handle special characters
        if tag == 'mo':
            # Common operators
            replacements = {
                '≠': '\\neq',
                '≤': '\\leq',
                '≥': '\\geq',
                '∈': '\\in',
                '∞': '\\infty',
                '×': '\\times',
                '÷': '\\div',
                '±': '\\pm',
                '∓': '\\mp',
                '∂': '\\partial',
                '∫': '\\int',
                '∑': '\\sum',
                '∏': '\\prod',
                '√': '\\sqrt',
                '∇': '\\nabla',
                '∆': '\\Delta',
                'α': '\\alpha',
                'β': '\\beta',
                'γ': '\\gamma',
                'δ': '\\delta',
                'ε': '\\epsilon',
                'θ': '\\theta',
                'λ': '\\lambda',
                'μ': '\\mu',
                'π': '\\pi',
                'σ': '\\sigma',
                'τ': '\\tau',
                'φ': '\\phi',
                'ω': '\\omega',
            }
            return replacements.get(text, text)
        elif tag == 'mi':
            # Greek letters in variable names
            greek = {
                'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta',
                'ε': '\\epsilon', 'θ': '\\theta', 'λ': '\\lambda', 'μ': '\\mu',
                'π': '\\pi', 'σ': '\\sigma', 'τ': '\\tau', 'φ': '\\phi', 'ω': '\\omega',
            }
            return greek.get(text, text)
        return text

    # Row/grouping
    if tag == 'mrow':
        parts = []
        for child in elem:
            parts.append(mathml_to_latex(child))
        return ''.join(parts)

    # Subscript
    if tag == 'msub':
        children = list(elem)
        if len(children) >= 2:
            base = mathml_to_latex(children[0])
            sub = mathml_to_latex(children[1])
            return f'{base}_{{{sub}}}'
        return ''

    # Superscript
    if tag == 'msup':
        children = list(elem)
        if len(children) >= 2:
            base = mathml_to_latex(children[0])
            sup = mathml_to_latex(children[1])
            return f'{base}^{{{sup}}}'
        return ''

    # Subscript and superscript
    if tag == 'msubsup':
        children = list(elem)
        if len(children) >= 3:
            base = mathml_to_latex(children[0])
            sub = mathml_to_latex(children[1])
            sup = mathml_to_latex(children[2])
            return f'{base}_{{{sub}}}^{{{sup}}}'
        return ''

    # Fraction
    if tag == 'mfrac':
        children = list(elem)
        if len(children) >= 2:
            num = mathml_to_latex(children[0])
            den = mathml_to_latex(children[1])
            return f'\\frac{{{num}}}{{{den}}}'
        return ''

    # Square root
    if tag == 'msqrt':
        content = ''.join(mathml_to_latex(child) for child in elem)
        return f'\\sqrt{{{content}}}'

    # Root with index
    if tag == 'mroot':
        children = list(elem)
        if len(children) >= 2:
            base = mathml_to_latex(children[0])
            index = mathml_to_latex(children[1])
            return f'\\sqrt[{index}]{{{base}}}'
        return ''

    # Math element (root)
    if tag == 'math':
        parts = []
        for child in elem:
            parts.append(mathml_to_latex(child))
        return ''.join(parts)

    # Default: recursively process children
    parts = []
    for child in elem:
        parts.append(mathml_to_latex(child))
    return ''.join(parts)


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
    root: etree.Element,
    figure_map: Optional[Dict[str, str]] = None,
    no_refs: bool = False
) -> Dict[str, Figure]:
    """Parse figures from JATS XML.

    Args:
        root: Root XML element
        figure_map: Optional mapping of figure IDs to file paths
        no_refs: If True, strip URL links from references

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

            # Remove DOI elements (eLife style)
            # Remove <object-id pub-id-type="doi"> elements
            for obj_id in caption_elem.findall('.//object-id[@pub-id-type="doi"]'):
                parent = obj_id.getparent()
                if parent is not None:
                    parent.remove(obj_id)

            # Remove <p><bold>DOI:</bold> <ext-link>...</ext-link></p> paragraphs
            for para in caption_elem.findall('.//p'):
                bold_elem = para.find('bold')
                if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
                    parent = para.getparent()
                    if parent is not None:
                        parent.remove(para)

            # Use extract_text_with_citations to properly handle inline elements
            # (superscripts, subscripts, italics, etc.)
            caption_text = extract_text_with_citations(caption_elem, no_refs=no_refs)

            # Remove title text if present (title is handled separately via label)
            title_elem = caption_elem.find('title')
            if title_elem is not None:
                title_text = ''.join(title_elem.itertext()).strip()
                if title_text and caption_text.startswith(title_text):
                    # Remove title and any following whitespace/punctuation
                    caption_text = caption_text[len(title_text):].strip()
                    # Remove leading period/colon if present
                    if caption_text and caption_text[0] in '.:-':
                        caption_text = caption_text[1:].strip()

            caption_text = caption_text.strip()
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


def parse_media(
    root: etree.Element,
    no_refs: bool = False
) -> Dict[str, Figure]:
    """Parse media elements (movies/videos) from JATS XML.

    Media elements are treated as Figure objects for consistency with other
    visual content in the article.

    Args:
        root: Root XML element
        no_refs: If True, strip URL links from references

    Returns:
        Dictionary mapping media IDs to Figure objects
    """
    media_items = {}

    for media in root.findall('.//media'):
        media_id = media.get('id')
        if not media_id:
            continue

        # Remove <object-id pub-id-type="doi"> elements BEFORE processing
        # (these appear at the top level of media element, not just in caption)
        for obj_id in media.findall('./object-id[@pub-id-type="doi"]'):
            parent = obj_id.getparent()
            if parent is not None:
                parent.remove(obj_id)

        # Get label
        label = None
        label_elem = media.find('label')
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        # Get caption
        caption = None
        caption_elem = media.find('.//caption')
        if caption_elem is not None:
            # Remove <object-id pub-id-type="doi"> elements from caption
            for obj_id in caption_elem.findall('.//object-id[@pub-id-type="doi"]'):
                parent = obj_id.getparent()
                if parent is not None:
                    parent.remove(obj_id)

            # Remove <p><bold>DOI:</bold> <ext-link>...</ext-link></p> paragraphs
            for para in caption_elem.findall('.//p'):
                bold_elem = para.find('bold')
                if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
                    parent = para.getparent()
                    if parent is not None:
                        parent.remove(para)

            # Use extract_text_with_citations to properly handle inline elements
            caption_text = extract_text_with_citations(caption_elem, no_refs=no_refs)

            # Remove title text if present (title is handled separately via label)
            title_elem = caption_elem.find('title')
            if title_elem is not None:
                title_text = ''.join(title_elem.itertext()).strip()
                if title_text and caption_text.startswith(title_text):
                    # Remove title and any following whitespace/punctuation
                    caption_text = caption_text[len(title_text):].strip()
                    # Remove leading period/colon if present
                    if caption_text and caption_text[0] in '.:-':
                        caption_text = caption_text[1:].strip()

            caption_text = caption_text.strip()
            if caption_text:
                caption = caption_text

        # Get media href (xlink:href attribute)
        media_href = None
        href = media.get('{http://www.w3.org/1999/xlink}href')
        if href:
            media_href = href

        # Create Figure object to represent media
        media_items[media_id] = Figure(
            figure_id=media_id,
            label=label,
            caption=caption,
            graphic_href=media_href,
            file_path=None,
        )

    return media_items


def parse_tables(root: etree.Element, no_refs: bool = False) -> Dict[str, Table]:
    """Parse tables from JATS XML.

    Args:
        root: Root XML element
        no_refs: If True, strip URL links from references

    Returns:
        Dictionary mapping table IDs to Table objects
    """
    tables = {}

    for table_wrap in root.findall('.//table-wrap'):
        table_id = table_wrap.get('id')
        if not table_id:
            continue

        # Get label
        label = None
        label_elem = table_wrap.find('label')
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        # Get caption
        caption = None
        caption_elem = table_wrap.find('caption')
        if caption_elem is not None:
            # Remove DOI elements (eLife style)
            # Remove <object-id pub-id-type="doi"> elements
            for obj_id in caption_elem.findall('.//object-id[@pub-id-type="doi"]'):
                parent = obj_id.getparent()
                if parent is not None:
                    parent.remove(obj_id)

            # Remove <p><bold>DOI:</bold> <ext-link>...</ext-link></p> paragraphs
            for para in caption_elem.findall('.//p'):
                bold_elem = para.find('bold')
                if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
                    parent = para.getparent()
                    if parent is not None:
                        parent.remove(para)

            # Extract caption text
            caption_text = extract_text_with_citations(caption_elem, no_refs=no_refs)
            caption = caption_text.strip() if caption_text else None

        # Parse table element
        table_elem = table_wrap.find('table')
        headers = []
        rows = []

        if table_elem is not None:
            # Parse header rows
            thead = table_elem.find('thead')
            if thead is not None:
                for tr in thead.findall('tr'):
                    header_row = []
                    for cell in tr.findall('td') + tr.findall('th'):
                        cell_text = ''.join(cell.itertext()).strip()

                        # Extract rowspan and colspan attributes
                        rowspan = cell.get('rowspan')
                        colspan = cell.get('colspan')

                        rowspan_int = int(rowspan) if rowspan else None
                        colspan_int = int(colspan) if colspan else None

                        header_row.append(TableCell(
                            content=cell_text,
                            rowspan=rowspan_int,
                            colspan=colspan_int
                        ))
                    if header_row:
                        headers.append(header_row)

            # Parse body rows
            tbody = table_elem.find('tbody')
            if tbody is not None:
                for tr in tbody.findall('tr'):
                    row = []
                    for cell in tr.findall('td') + tr.findall('th'):
                        cell_text = ''.join(cell.itertext()).strip()

                        # Extract rowspan and colspan attributes
                        rowspan = cell.get('rowspan')
                        colspan = cell.get('colspan')

                        rowspan_int = int(rowspan) if rowspan else None
                        colspan_int = int(colspan) if colspan else None

                        row.append(TableCell(
                            content=cell_text,
                            rowspan=rowspan_int,
                            colspan=colspan_int
                        ))
                    if row:
                        rows.append(row)

        # Get footer
        footer = None
        footer_elem = table_wrap.find('table-wrap-foot')
        if footer_elem is not None:
            footer_text = ''.join(footer_elem.itertext()).strip()
            footer = footer_text if footer_text else None

        tables[table_id] = Table(
            table_id=table_id,
            label=label,
            caption=caption,
            headers=headers,
            rows=rows,
            footer=footer,
        )

    return tables


def extract_text_with_citations(
    elem: etree.Element,
    references: Optional[Dict[str, str]] = None,
    figure_urls: Optional[Dict[str, str]] = None,
    no_refs: bool = False
) -> str:
    """Extract text from element, converting citation and figure xrefs to markdown links.

    Args:
        elem: XML element to extract text from
        references: Dictionary mapping ref-ids to DOIs
        figure_urls: Dictionary mapping figure-ids to image URLs
        no_refs: If True, strip URL links and keep only citation text (e.g., "Author, Year")

    Returns:
        Text with citations and figure references converted to markdown links,
        or plain text if no_refs=True
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

            if no_refs:
                # Just output plain citation text
                parts.append(citation_text)
            else:
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

            if no_refs:
                # Just output plain figure text
                parts.append(figure_text)
            else:
                # Convert to markdown link if figure URL is available
                if fig_id and fig_id in figure_urls:
                    fig_url = figure_urls[fig_id]
                    parts.append(f"[{figure_text}]({fig_url})")
                else:
                    # No URL available, keep plain text
                    parts.append(figure_text)

        # Handle inline formulas
        elif child.tag == 'inline-formula':
            # Find the math element (check both with and without namespace)
            math_elem = child.find('.//{http://www.w3.org/1998/Math/MathML}math')
            if math_elem is None:
                # Try without namespace prefix
                math_elem = child.find('.//math')

            if math_elem is not None:
                # Convert MathML to LaTeX
                latex = mathml_to_latex(math_elem)
                # Wrap in inline math delimiters
                parts.append(f'${latex}$')
            else:
                # Fallback to plain text
                parts.append(''.join(child.itertext()))

        # Handle display formulas (embedded in paragraphs)
        elif child.tag == 'disp-formula':
            # Find the math element
            math_elem = child.find('.//{http://www.w3.org/1998/Math/MathML}math')
            if math_elem is None:
                math_elem = child.find('.//math')

            if math_elem is not None:
                # Convert MathML to LaTeX
                latex = mathml_to_latex(math_elem)
                # Display formulas get their own line with $$...$$
                parts.append(f'\n\n$$\n{latex}\n$$\n\n')
            else:
                # Fallback to plain text
                parts.append(''.join(child.itertext()))

        # Handle named-content elements (claim annotations)
        elif child.tag == 'named-content' and child.get('content-type') == 'scientific-claim':
            # Convert JATS <named-content> to HTML <mark> tag (preserved in markdown)
            claim_id = child.get('id', '')
            claim_ids = child.get('claim-ids', '')
            claim_text = ''.join(child.itertext()).strip()
            # Use mark tag with data attributes for frontend highlighting
            if claim_ids:
                parts.append(f'<mark data-claim-id="{claim_id}" data-claim-ids="{claim_ids}" class="claim-highlight">{claim_text}</mark>')
            else:
                parts.append(f'<mark data-claim-id="{claim_id}" class="claim-highlight">{claim_text}</mark>')

        else:
            # Recursively extract text from other elements
            parts.append(extract_text_with_citations(child, references, figure_urls, no_refs))

        # Add tail text after child
        if child.tail:
            parts.append(child.tail)

    return ''.join(parts)


def parse_body(
    root: etree.Element,
    figures: Optional[Dict[str, Figure]] = None,
    tables: Optional[Dict[str, Table]] = None,
    references: Optional[Dict[str, str]] = None,
    figure_urls: Optional[Dict[str, str]] = None,
    no_refs: bool = False
) -> List[Section]:
    """Parse article body sections.

    Args:
        root: Root XML element
        figures: Dictionary of Figure objects
        tables: Dictionary of Table objects
        references: Dictionary mapping ref-ids to DOIs
        figure_urls: Dictionary mapping figure-ids to image URLs
        no_refs: If True, strip URL links from references

    Returns:
        List of Section objects
    """
    if figures is None:
        figures = {}
    if tables is None:
        tables = {}
    if figure_urls is None:
        figure_urls = {}

    body = root.find('.//body')
    if body is None:
        return []

    sections = []
    for sec in body.findall('.//sec'):
        # Calculate section level by counting parent <sec> elements
        level = 2  # Start at h2 (## in markdown)
        parent = sec.getparent()
        while parent is not None:
            if parent.tag == 'sec':
                level += 1
            parent = parent.getparent()

        section = Section(level=level)

        # Get section title
        title_elem = sec.find('title')
        if title_elem is not None:
            # Use itertext() to get all text including from child elements like <italic>
            section.title = ''.join(title_elem.itertext()).strip()

        # Get section content (paragraphs and figures in order)
        for child in sec:
            if child.tag == 'p':
                # Check if paragraph contains embedded figures or tables (eLife style)
                embedded_figs = child.findall('.//fig')
                embedded_media = child.findall('.//media')
                embedded_tables = child.findall('.//table-wrap')

                if embedded_figs or embedded_media or embedded_tables:
                    # Paragraph has embedded figures - need to handle text chunks between figures
                    # properly extracting inline elements like <italic>, <bold>, citations, etc.
                    current_text_parts = []

                    def add_accumulated_text():
                        """Helper to add accumulated text as paragraph item."""
                        if current_text_parts:
                            accumulated = ''.join(current_text_parts).strip()
                            if accumulated:
                                section.content_items.append(
                                    ContentItem(item_type='paragraph', text=accumulated)
                                )
                            current_text_parts.clear()

                    # Add initial text before any child elements
                    if child.text:
                        current_text_parts.append(child.text)

                    # Process each child element
                    for elem in child:
                        if elem.tag == 'fig':
                            # Save accumulated text before figure
                            add_accumulated_text()

                            # Add figure
                            fig_id = elem.get('id')
                            if fig_id and fig_id in figures:
                                section.content_items.append(
                                    ContentItem(item_type='figure', figure=figures[fig_id])
                                )

                            # Add text after figure (tail)
                            if elem.tail:
                                current_text_parts.append(elem.tail)
                        elif elem.tag == 'media':
                            # Save accumulated text before media
                            add_accumulated_text()

                            # Add media (treated as figure)
                            media_id = elem.get('id')
                            if media_id and media_id in figures:
                                section.content_items.append(
                                    ContentItem(item_type='figure', figure=figures[media_id])
                                )

                            # Add text after media (tail)
                            if elem.tail:
                                current_text_parts.append(elem.tail)
                        elif elem.tag == 'fig-group':
                            # Save accumulated text before figure group
                            add_accumulated_text()

                            # Add all figures in the group
                            for fig in elem.findall('.//fig'):
                                fig_id = fig.get('id')
                                if fig_id and fig_id in figures:
                                    section.content_items.append(
                                        ContentItem(item_type='figure', figure=figures[fig_id])
                                    )

                            # Add text after figure group (tail)
                            if elem.tail:
                                current_text_parts.append(elem.tail)
                        elif elem.tag == 'table-wrap':
                            # Save accumulated text before table
                            add_accumulated_text()

                            # Add table
                            table_id = elem.get('id')
                            if table_id and table_id in tables:
                                section.content_items.append(
                                    ContentItem(item_type='table', table=tables[table_id])
                                )

                            # Add text after table (tail)
                            if elem.tail:
                                current_text_parts.append(elem.tail)
                        else:
                            # Not a figure - extract text including inline formatting
                            elem_text = extract_text_with_citations(elem, references, figure_urls, no_refs)
                            current_text_parts.append(elem_text)

                            # Add tail text (text after this element, before next sibling)
                            if elem.tail:
                                current_text_parts.append(elem.tail)

                    # Add any remaining accumulated text
                    add_accumulated_text()
                else:
                    # Normal paragraph without embedded figures
                    # Extract text with citation and figure links
                    para_text = extract_text_with_citations(child, references, figure_urls, no_refs).strip()
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

            elif child.tag == 'media':
                # Media as direct child of section
                media_id = child.get('id')
                if media_id and media_id in figures:
                    section.content_items.append(
                        ContentItem(item_type='figure', figure=figures[media_id])
                    )

            elif child.tag == 'fig-group':
                # Figure group containing multiple figures (eLife supplements)
                for fig in child.findall('.//fig'):
                    fig_id = fig.get('id')
                    if fig_id and fig_id in figures:
                        section.content_items.append(
                            ContentItem(item_type='figure', figure=figures[fig_id])
                        )

            elif child.tag == 'table-wrap':
                # Table as direct child of section
                table_id = child.get('id')
                if table_id and table_id in tables:
                    section.content_items.append(
                        ContentItem(item_type='table', table=tables[table_id])
                    )

            elif child.tag == 'disp-formula':
                # Display formula as direct child of section
                math_elem = child.find('.//{http://www.w3.org/1998/Math/MathML}math')
                if math_elem is not None:
                    latex = mathml_to_latex(math_elem)
                    # Display formulas get their own paragraph with $$...$$
                    formula_text = f'$$\n{latex}\n$$'
                    section.content_items.append(
                        ContentItem(item_type='paragraph', text=formula_text)
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


def parse_jats_xml(
    xml_path: Path,
    manifest_path: Optional[Path] = None,
    no_refs: bool = False
) -> Article:
    """Parse JATS XML file and return Article object.

    Args:
        xml_path: Path to XML file
        manifest_path: Optional path to manifest.xml
        no_refs: If True, strip URL links from references

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
    figures = parse_figures(root, figure_map, no_refs)
    media = parse_media(root, no_refs)
    # Merge media into figures (media are treated as figures for display purposes)
    figures.update(media)
    tables = parse_tables(root, no_refs)
    figure_urls = build_figure_urls(figures, article_id, is_elife)
    body = parse_body(root, figures, tables, references, figure_urls, no_refs)
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


def get_longest_segment(query: str, min_length: int = 10) -> Optional[str]:
    """Extract longest text segment from a query containing ellipsis.

    When LLMs paraphrase text with ellipsis ("..."), they typically preserve
    one or more substantial segments of the original text. This function extracts
    the longest segment, which is most likely to be found in the source document.

    Args:
        query: Query string potentially containing ellipsis
        min_length: Minimum length for a segment to be considered (default: 10 chars)

    Returns:
        Longest segment if query contains ellipsis and has valid segments,
        None otherwise
    """
    if "..." not in query:
        return None

    # Split by ellipsis and filter segments
    segments = query.split("...")
    segments = [s.strip() for s in segments if len(s.strip()) >= min_length]

    if not segments:
        return None

    # Return longest segment
    return max(segments, key=len)


def find_text_locations(
    root: etree.Element,
    queries: List[str],
    case_sensitive: bool = False
) -> List[Dict]:
    """Find locations of query strings in JATS XML.

    Builds a normalized text representation of the document and finds exact
    matches, returning precise XML-anchored locations.

    For queries containing ellipsis ("...") that don't match exactly, automatically
    tries to match the longest text segment as a fallback. This handles cases where
    LLMs paraphrase text by omitting portions.

    Args:
        root: Root element of JATS XML document
        queries: List of query strings to find
        case_sensitive: If False (default), perform case-insensitive matching

    Returns:
        List of match dictionaries, one per query. Each dict contains:
        - query: The original query string
        - start: {"xpath": str, "char_offset": int} (if found)
        - stop: {"xpath": str, "char_offset": int} (if found)
        - len: Length of match in characters (if found)
        - matched_segment: The segment that was matched in the XML
          * For exact matches: equals query
          * For ellipsis fallback: the longest segment extracted from query

        If query not found, only "query" field is present.

        To identify ellipsis fallback cases: check if matched_segment != query
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

        # Track what segment actually matched (query for exact match, or longest segment for ellipsis)
        matched_segment = query  # Default: exact match

        # If not found and query contains ellipsis, try longest segment fallback
        if match_start == -1 and "..." in query:
            longest_segment = get_longest_segment(query)
            if longest_segment:
                normalized_segment = normalize_text(longest_segment, case_sensitive)
                match_start = full_text.find(normalized_segment)
                if match_start != -1:
                    # Found using longest segment
                    matched_segment = longest_segment
                    normalized_query = normalized_segment

        if match_start == -1:
            # Not found (even after ellipsis fallback if applicable)
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
            result = {
                'query': query,
                'matched_segment': matched_segment,
                'start': {'xpath': start_xpath, 'char_offset': start_offset},
                'stop': {'xpath': stop_xpath, 'char_offset': stop_offset},
                'len': len(normalized_query)
            }
            results.append(result)
        else:
            # Edge case: match found but couldn't map (shouldn't happen)
            results.append({'query': query})

    return results

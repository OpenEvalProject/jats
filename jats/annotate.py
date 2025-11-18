"""JATS XML annotation - Version 4 with full multi-node support."""

import json
from pathlib import Path
from typing import Tuple
from lxml import etree


def inject_named_content_tags(
    xml_path: Path,
    claims_path: Path
) -> Tuple[etree._Element, int, int]:
    """Inject <named-content> tags into JATS XML at precise XPath positions."""
    with open(claims_path, 'r') as f:
        pos_claims = json.load(f)

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()

    # Try to load claims.json to get claim_ids
    claims_json_path = claims_path.parent / 'claims.json'
    claim_ids = {}
    if claims_json_path.exists():
        with open(claims_json_path, 'r') as f:
            claims_data = json.load(f)
            # Create mapping: index -> claim_id
            claim_ids = {i: c.get('claim_id', f'claim-{i}') for i, c in enumerate(claims_data)}

    # Filter and deduplicate claims
    valid_claims = []
    for idx, claim in enumerate(pos_claims):
        if claim.get('start') and claim.get('matched_segment'):
            # Add claim_id from claims.json if available
            if idx in claim_ids:
                claim['claim_id'] = claim_ids[idx]
            valid_claims.append((idx, claim))

    # Group claims by position and merge claim_ids for claims at the same position
    from collections import defaultdict
    position_groups = defaultdict(list)

    for idx, claim in valid_claims:
        xpath = claim['start']['xpath']
        char_start = claim['start'].get('char_offset', 0)
        char_stop = claim['stop'].get('char_offset')
        position_key = (xpath, char_start, char_stop)
        position_groups[position_key].append(claim)

    # Merge claims at the same position
    merged_claims = []
    duplicates_removed = 0

    for position_key, claims_at_position in position_groups.items():
        if len(claims_at_position) == 1:
            # Single claim at this position
            merged_claims.append(claims_at_position[0])
        else:
            # Multiple claims at same position - merge them
            base_claim = claims_at_position[0].copy()
            claim_ids = [c.get('claim_id', c.get('query', '')[:20]) for c in claims_at_position]

            # Store all claim_ids in the base claim
            base_claim['claim_ids'] = claim_ids
            base_claim['claim_id'] = claim_ids[0]  # Use first as primary

            merged_claims.append(base_claim)
            duplicates_removed += len(claims_at_position) - 1

    # Sort by position (reverse order to preserve offsets)
    claims_sorted = sorted(
        merged_claims,
        key=lambda x: (x['start']['xpath'], x['start'].get('char_offset', 0)),
        reverse=True
    )

    successful = 0
    failed = 0
    skipped_overlap = 0
    debug_info = []

    # Track annotated regions to detect overlaps
    annotated_regions = set()  # (xpath, char_start, char_stop)

    for claim in claims_sorted:
        try:
            xpath_start = claim['start']['xpath']
            char_start = claim['start'].get('char_offset', 0)
            char_stop = claim['stop'].get('char_offset')
            matched_text = claim['matched_segment']
            claim_id = claim.get('claim_id', claim.get('query', '')[:20])

            elements = root.xpath(xpath_start)
            if not elements:
                failed += 1
                debug_info.append(f"FAIL: XPath not found: {xpath_start}")
                continue

            element = elements[0]
            full_text = ''.join(element.itertext())

            if char_stop is None:
                char_stop = char_start + len(matched_text)
            if char_stop > len(full_text):
                char_stop = len(full_text)

            # Check for overlap with already-annotated regions
            region_key = (xpath_start, char_start, char_stop)
            overlaps = False
            for annotated_xpath, annotated_start, annotated_stop in annotated_regions:
                if annotated_xpath == xpath_start:
                    # Check if ranges overlap
                    if not (char_stop <= annotated_start or char_start >= annotated_stop):
                        overlaps = True
                        break

            if overlaps:
                skipped_overlap += 1
                debug_info.append(f"SKIP: overlaps with existing annotation: {claim_id}")
                continue

            # Get all claim_ids for this position (for merged claims)
            claim_ids_list = claim.get('claim_ids', [claim_id])

            # Attempt injection
            if inject_at_position_v4(element, char_start, char_stop, claim_id, claim_ids_list):
                successful += 1
                annotated_regions.add(region_key)
            else:
                failed += 1
                debug_info.append(f"FAIL: injection failed for {claim_id} at {xpath_start}")

        except Exception as e:
            failed += 1
            debug_info.append(f"FAIL: Exception {e} for {claim.get('query', '')[:30]}")
            continue

    import sys
    if duplicates_removed > 0:
        print(f"\nMerged {duplicates_removed} claim(s) at shared source positions", file=sys.stderr)
    if skipped_overlap > 0:
        print(f"Skipped {skipped_overlap} overlapping claim(s)", file=sys.stderr)
    if debug_info and failed > 0:
        print("\nDebug information:", file=sys.stderr)
        for info in debug_info[:10]:
            print(f"  {info}", file=sys.stderr)

    return root, successful, failed


def inject_at_position_v4(element, char_start, char_stop, claim_id, claim_ids=None):
    """
    Inject <named-content> tag with comprehensive multi-node support.

    Handles:
    1. Single text node (partial or complete)
    2. Parent.text to child.tail
    3. Tail to tail (across multiple children)
    4. Wrapping complete child elements

    Args:
        claim_ids: Optional list of all claim IDs at this position (for merged claims)
    """
    # Collect all text pieces with positions
    pieces = []  # (element, is_tail, text, char_pos_start, char_pos_end)

    def collect(node, pos):
        if node.text:
            pieces.append((node, False, node.text, pos, pos + len(node.text)))
            pos += len(node.text)

        for child in node:
            pos = collect(child, pos)
            if child.tail:
                pieces.append((child, True, child.tail, pos, pos + len(child.tail)))
                pos += len(child.tail)

        return pos

    collect(element, 0)

    # Find affected pieces
    affected = [(elem, is_tail, text, max(char_start, start) - start, min(char_stop, end) - start)
                for elem, is_tail, text, start, end in pieces
                if start < char_stop and end > char_start]

    if not affected:
        return False

    # Create wrapper
    wrapper = etree.Element("named-content")
    wrapper.set("content-type", "scientific-claim")
    wrapper.set("id", claim_id)
    wrapper.set("specific-use", "claim-validation")

    # Add claim-ids attribute if multiple claims at this position
    if claim_ids and len(claim_ids) > 1:
        wrapper.set("claim-ids", " ".join(claim_ids))

    # CASE 1: Single text node
    if len(affected) == 1:
        elem, is_tail, text, start_off, end_off = affected[0]

        before = text[:start_off]
        content = text[start_off:end_off]
        after = text[end_off:]

        if is_tail:
            # Split tail
            parent = elem.getparent()
            idx = list(parent).index(elem)
            elem.tail = before
            wrapper.text = content
            wrapper.tail = after
            parent.insert(idx + 1, wrapper)
        else:
            # Split text
            elem.text = before
            wrapper.text = content
            wrapper.tail = after
            elem.insert(0, wrapper)

        return True

    # CASE 2+: Multiple pieces - extract info
    first_elem, first_is_tail, first_text, first_start, first_end = affected[0]
    last_elem, last_is_tail, last_text, last_start, last_end = affected[-1]

    # CASE 2: Wrapping complete child element (text + tail)
    if first_elem == last_elem and not first_is_tail and last_is_tail:
        parent = element
        children = list(parent)

        if first_elem in children:
            idx = children.index(first_elem)

            if first_start > 0:
                return False

            # Move child into wrapper
            parent.remove(first_elem)
            wrapper.append(first_elem)

            # Handle tail splitting
            if last_end < len(last_text):
                first_elem.tail = last_text[:last_end]
                wrapper.tail = last_text[last_end:]
            else:
                wrapper.tail = ""

            parent.insert(idx, wrapper)
            return True

    # CASE 3: Parent.text to child.tail
    if not first_is_tail and last_is_tail:
        # Starting in parent.text, ending in a child's tail
        parent = element
        children = list(parent)

        # Check if first_elem is the parent itself
        if first_elem != parent:
            # First text is from a nested child, not the parent
            # This is a TEXT_TO_TEXT or more complex case - not yet handled
            return False

        # Split parent.text
        before_text = first_text[:first_start]
        content_start = first_text[first_start:first_end]

        parent.text = before_text
        wrapper.text = content_start

        # Find which child has the last tail
        last_child_idx = None
        for idx, child in enumerate(children):
            if child == last_elem:
                last_child_idx = idx
                break

        if last_child_idx is None:
            return False

        # Move children from start to last_child_idx into wrapper
        for idx in range(0, last_child_idx + 1):
            child = children[idx]
            parent.remove(child)
            wrapper.append(child)

        # Split last child's tail
        content_end = last_text[last_start:last_end]
        after_text = last_text[last_end:]
        last_elem.tail = content_end
        wrapper.tail = after_text

        # Insert wrapper at the beginning
        parent.insert(0, wrapper)
        return True

    # CASE 4: Tail to tail
    if first_is_tail and last_is_tail:
        # Starting in one child's tail, ending in another child's tail
        parent = element
        children = list(parent)

        # Find indices of start and end children
        start_child_idx = None
        end_child_idx = None
        for idx, child in enumerate(children):
            if child == first_elem:
                start_child_idx = idx
            if child == last_elem:
                end_child_idx = idx

        if start_child_idx is None or end_child_idx is None:
            return False

        # Split start child's tail
        before_text = first_text[:first_start]
        content_start = first_text[first_start:first_end]
        first_elem.tail = before_text
        wrapper.text = content_start

        # Move intermediate children (between start and end) into wrapper
        children_to_move = []
        for idx in range(start_child_idx + 1, end_child_idx + 1):
            children_to_move.append(children[idx])

        for child in children_to_move:
            parent.remove(child)
            wrapper.append(child)

        # Split last child's tail (now it's in wrapper)
        content_end = last_text[last_start:last_end]
        after_text = last_text[last_end:]
        last_elem.tail = content_end
        wrapper.tail = after_text

        # Insert wrapper after start_child
        parent.insert(start_child_idx + 1, wrapper)
        return True

    # CASE 5: Tail to text (modular implementation - can be easily reverted)
    if first_is_tail and not last_is_tail:
        if handle_tail_to_text_case(element, wrapper, affected):
            return True

    # Other cases not yet implemented
    return False


def handle_tail_to_text_case(element, wrapper, affected):
    """
    Handle TAIL_TO_TEXT scenario: starts in child.tail, ends in another element's text.

    This is a modular implementation that can be easily reverted if needed.
    Handles cases like claim C64 where we wrap from one element's tail through
    intermediate elements to another element's text.

    Returns True if successful, False otherwise.
    """
    first_elem, first_is_tail, first_text, first_start, first_end = affected[0]
    last_elem, last_is_tail, last_text, last_start, last_end = affected[-1]

    parent = element
    children = list(parent)

    # Find indices of start and end elements in parent's children
    start_child_idx = None
    end_child_idx = None

    for idx, child in enumerate(children):
        if child == first_elem:
            start_child_idx = idx
        if child == last_elem:
            end_child_idx = idx

    # Also check if last_elem is nested inside any child
    if end_child_idx is None:
        for idx, child in enumerate(children):
            # Check if last_elem is a descendant of this child
            for descendant in child.iter():
                if descendant == last_elem:
                    end_child_idx = idx
                    break
            if end_child_idx is not None:
                break

    if start_child_idx is None or end_child_idx is None:
        return False

    # Check if last_elem is nested (not a direct child)
    is_nested = last_elem not in children

    # Split start child's tail
    before_text = first_text[:first_start]
    content_start = first_text[first_start:first_end]
    first_elem.tail = before_text
    wrapper.text = content_start

    # Move intermediate children into wrapper (from start+1 to end inclusive)
    children_to_move = []
    for idx in range(start_child_idx + 1, end_child_idx + 1):
        children_to_move.append(children[idx])

    for child in children_to_move:
        parent.remove(child)
        wrapper.append(child)

    # Handle the last element's text
    # Check if we're wrapping the complete text (starts at 0 and goes to end)
    if last_start == 0 and last_end == len(last_text):
        # Complete text - no need to split last_elem
        # The wrapper.tail should be whatever comes after last_elem
        if is_nested:
            # last_elem is inside the wrapper now, so wrapper.tail should be
            # the tail of the child that contains last_elem
            wrapper.tail = children[end_child_idx].tail if hasattr(children[end_child_idx], 'tail') else ""
        else:
            # last_elem is a direct child now inside wrapper
            wrapper.tail = last_elem.tail if last_elem.tail else ""
            last_elem.tail = ""
    elif last_start == 0 and last_end < len(last_text):
        # Partial text from start - need to split
        if is_nested:
            # Nested + partial text is too complex for modular v1
            return False
        else:
            # Direct child with partial text - split it
            # We need to split last_elem's text and create siblings
            content_text = last_text[:last_end]
            after_text = last_text[last_end:]

            # Strategy: Insert a text node after last_elem for the remaining text
            # lxml doesn't support standalone text nodes, so we need to attach
            # the after_text to the wrapper's tail
            last_elem.text = content_text

            # The remaining text becomes the tail of the wrapper
            # But we also need to preserve last_elem's tail
            if last_elem.tail:
                wrapper.tail = after_text + last_elem.tail
            else:
                wrapper.tail = after_text
            last_elem.tail = ""
    else:
        # Partial text not from start - very complex
        return False

    # Insert wrapper after start_child
    parent.insert(start_child_idx + 1, wrapper)
    return True

"""
Plant Knowledge Service — local curated data for AI prompt enrichment.

Matches user plant species to guides.json and diagnostic questions to
seo_landing_pages.json, returning condensed context strings for injection
into the AI system prompt. All data is local (no external API calls).

Indexes are built once on first access and cached at module level.
"""

from __future__ import annotations

from typing import Optional, Dict, List

from app.utils.data import load_data_file


# ============================================================================
# MODULE-LEVEL CACHES (built on first access)
# ============================================================================

_species_index: Optional[Dict[str, dict]] = None
_diagnostic_index: Optional[Dict[str, dict]] = None


# ============================================================================
# SPECIES MATCHING — guides.json
# ============================================================================

def _build_species_index() -> Dict[str, dict]:
    """
    Build a lookup index from guides.json mapping normalized name forms
    to guide data. Called once and cached.

    Keys include: slug words, full name, scientific name, variety names,
    and also_known_as aliases — all lowercased for fuzzy matching.
    """
    guides = load_data_file("guides.json")
    index: Dict[str, dict] = {}

    for guide in guides:
        condensed = _condense_guide(guide)

        # Map multiple name forms to the same condensed guide
        names = set()

        # Primary identifiers
        if guide.get("name"):
            names.add(guide["name"].lower())
        if guide.get("scientific_name"):
            names.add(guide["scientific_name"].lower())
        if guide.get("slug"):
            # "monstera-deliciosa" -> "monstera deliciosa"
            names.add(guide["slug"].replace("-", " "))

        # Variety names and aliases
        for variety in guide.get("varieties", []):
            if variety.get("name"):
                names.add(variety["name"].lower())
            if variety.get("also_known_as"):
                names.add(variety["also_known_as"].lower())

        for name in names:
            index[name] = condensed

    return index


def _condense_guide(guide: dict) -> dict:
    """
    Extract the key fields from a guide into a compact dict suitable
    for prompt injection. Keeps the raw data so the caller can format it.
    """
    return {
        "name": guide.get("name", ""),
        "scientific_name": guide.get("scientific_name", ""),
        "watering": guide.get("water", ""),
        "watering_detail": _first_sentence(guide.get("watering", "")),
        "light": guide.get("light", ""),
        "light_detail": _first_sentence(guide.get("light_details", "")),
        "humidity": guide.get("humidity_level", ""),
        "difficulty": guide.get("difficulty", ""),
        "common_problems": guide.get("common_problems", [])[:5],
    }


def _first_sentence(text: str) -> str:
    """Return the first sentence of a paragraph (up to the first period)."""
    if not text:
        return ""
    idx = text.find(".")
    if idx == -1:
        return text[:150]
    # Include the period, cap at 200 chars
    return text[: min(idx + 1, 200)]


def get_guide_for_species(species: str) -> Optional[str]:
    """
    Match a user's plant species to a guide in guides.json.

    Uses normalized substring matching: "monstera", "Monstera Deliciosa",
    "Swiss Cheese Plant" all match the Monstera guide.

    Args:
        species: Plant species/name string from user's plant or form input

    Returns:
        Condensed care summary string (~80-120 tokens) or None if no match
    """
    global _species_index
    if _species_index is None:
        _species_index = _build_species_index()

    if not species or not species.strip():
        return None

    query = species.lower().strip()

    # Try exact match first
    if query in _species_index:
        return _format_guide_for_prompt(_species_index[query])

    # Try substring match (e.g. "monstera" matches "monstera deliciosa")
    for key, guide in _species_index.items():
        if query in key or key in query:
            return _format_guide_for_prompt(guide)

    return None


def _format_guide_for_prompt(guide: dict) -> str:
    """Format condensed guide data into a prompt-ready string."""
    lines = [f"Expert care data for {guide['name']}:"]

    if guide.get("watering_detail"):
        lines.append(f"- Watering ({guide['watering']}): {guide['watering_detail']}")
    if guide.get("light_detail"):
        lines.append(f"- Light ({guide['light']}): {guide['light_detail']}")
    if guide.get("humidity"):
        lines.append(f"- Humidity: {guide['humidity']}")

    problems = guide.get("common_problems", [])
    if problems:
        lines.append("- Common issues: " + " | ".join(problems[:3]))

    return "\n".join(lines)


# ============================================================================
# DIAGNOSTIC MATCHING — seo_landing_pages.json
# ============================================================================

# Map question keywords to landing page route_names
_DIAGNOSTIC_KEYWORDS: Dict[str, List[str]] = {
    "drooping": ["droop", "droopy", "drooping", "wilting", "wilt", "limp"],
    "overwatering": ["overwater", "soggy", "waterlog", "too much water"],
    "yellow_leaves": ["yellow", "yellowing"],
    "brown_leaves": ["brown", "browning", "crispy"],
    "curling_leaves": ["curl", "curling", "curled"],
    "root_rot": ["rot", "rotting", "mushy", "root rot"],
    "fungus_gnats": ["gnat", "gnats", "flies", "fungus gnat"],
    "not_growing": ["not growing", "stopped growing", "stunted", "leggy"],
}


def _build_diagnostic_index() -> Dict[str, dict]:
    """
    Build index mapping route_name to condensed landing page data.
    Called once and cached.
    """
    pages = load_data_file("seo_landing_pages.json")
    index: Dict[str, dict] = {}

    for page in pages:
        route = page.get("route_name")
        if route:
            index[route] = {
                "title": page.get("title", ""),
                "causes": [
                    {"title": c.get("title", ""), "fix": c.get("fix", "")}
                    for c in page.get("causes", [])[:5]
                ],
            }

    return index


def get_diagnostic_context(question: str) -> Optional[str]:
    """
    Match a diagnostic question to relevant seo_landing_pages.json content.

    Returns the top 3 causes with fixes for the best-matching landing page,
    or None if no diagnostic keywords match.

    Args:
        question: User's question text

    Returns:
        Condensed diagnostic reference string (~60-100 tokens) or None
    """
    global _diagnostic_index
    if _diagnostic_index is None:
        _diagnostic_index = _build_diagnostic_index()

    if not question:
        return None

    q_lower = question.lower()

    # Find the best matching route by keyword overlap
    best_route = None
    for route_name, keywords in _DIAGNOSTIC_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            best_route = route_name
            break

    if not best_route or best_route not in _diagnostic_index:
        return None

    page = _diagnostic_index[best_route]
    return _format_diagnostic_for_prompt(page)


def _format_diagnostic_for_prompt(page: dict) -> str:
    """Format diagnostic page data into a prompt-ready string."""
    lines = [f"Common causes of {page['title'].rstrip('?').lower().strip()}:"]

    for i, cause in enumerate(page["causes"][:3], 1):
        fix_text = _first_sentence(cause["fix"])
        lines.append(f"{i}. {cause['title']}: {fix_text}")

    return "\n".join(lines)


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def clear_knowledge_cache():
    """Clear cached indexes. Used for testing."""
    global _species_index, _diagnostic_index
    _species_index = None
    _diagnostic_index = None

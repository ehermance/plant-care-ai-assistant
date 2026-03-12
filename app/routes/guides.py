"""
Plant Care Guides — unified content hub.

Serves the /plant-care-guides/ index (species guides, hub pages, and
troubleshooting landing pages) plus individual guide pages.
"""

from __future__ import annotations
import json
import os
from flask import Blueprint, render_template, abort, current_app
from typing import Optional


guides_bp = Blueprint("guides", __name__, url_prefix="/plant-care-guides")

# Cache for guides data
_guides_cache: Optional[list] = None


def _load_guides() -> list:
    """Load guides data from JSON file, with caching."""
    global _guides_cache
    if _guides_cache is not None:
        return _guides_cache

    guides_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "guides.json"
    )

    try:
        with open(guides_path, "r", encoding="utf-8") as f:
            _guides_cache = json.load(f)
    except FileNotFoundError:
        current_app.logger.warning(f"Guides file not found: {guides_path}")
        _guides_cache = []

    return _guides_cache


def _get_guide_by_slug(slug: str) -> Optional[dict]:
    """Get a single guide by its URL slug."""
    guides = _load_guides()
    for guide in guides:
        if guide.get("slug") == slug:
            return guide
    return None


def _build_landing_page_groups() -> list[dict]:
    """Group SEO landing pages by their parent hub for the index page.

    Returns a list of dicts, each with:
      - label: section heading (e.g. "Watering Issues")
      - hub: parent hub page dict or None
      - pages: list of landing page dicts in this group
    """
    from app.routes.seo import LANDING_PAGES, HUB_PAGES

    assigned: set[str] = set()
    groups: list[dict] = []

    for hub in HUB_PAGES.values():
        pages = []
        for slug in hub.get("spoke_pages", []):
            if slug in LANDING_PAGES and slug not in assigned:
                pages.append(LANDING_PAGES[slug])
                assigned.add(slug)
        if pages:
            groups.append({"label": hub["title"], "hub": hub, "pages": pages})

    # Collect any landing pages not assigned to a hub
    remaining = [
        page for slug, page in LANDING_PAGES.items() if slug not in assigned
    ]
    if remaining:
        groups.append({"label": "More Guides", "hub": None, "pages": remaining})

    return groups


@guides_bp.route("/")
def index():
    """
    Unified content hub — species guides, hub pages, and troubleshooting.
    """
    from app.routes.seo import HUB_PAGES

    guides = _load_guides()
    hub_pages = list(HUB_PAGES.values())
    landing_page_groups = _build_landing_page_groups()
    return render_template(
        "guides/index.html",
        guides=guides,
        hub_pages=hub_pages,
        landing_page_groups=landing_page_groups,
    )


@guides_bp.route("/<slug>")
def view(slug: str):
    """
    Individual plant care guide.

    Displays detailed care information for a specific plant.
    """
    guide = _get_guide_by_slug(slug)
    if not guide:
        abort(404)

    return render_template("guides/guide.html", guide=guide)

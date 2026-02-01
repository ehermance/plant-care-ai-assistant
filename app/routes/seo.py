"""
SEO Landing Pages for high-intent plant care searches.

Problem-first pages targeting common plant care pain points like
"why are my plant leaves drooping", "am I overwatering my plant", etc.

Each page:
- Addresses a specific user pain point
- Provides empathetic, helpful content
- Funnels to /ask for personalized AI advice
- Links to related pages for internal linking
"""

from __future__ import annotations
from flask import Blueprint, render_template, abort
from typing import Optional
import os
import json


seo_bp = Blueprint("seo", __name__)


def _load_landing_pages() -> dict:
    """Load SEO landing page data from JSON file."""
    pages_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "seo_landing_pages.json"
    )
    try:
        with open(pages_path, "r", encoding="utf-8") as f:
            pages_list = json.load(f)
    except FileNotFoundError:
        return {}
    return {page["slug"]: page for page in pages_list}


# Load once at import time
LANDING_PAGES = _load_landing_pages()

# Slug to route name mapping for URL generation
SLUG_TO_ROUTE = {page["slug"]: page["route_name"] for page in LANDING_PAGES.values()}


def _get_page(slug: str) -> Optional[dict]:
    """Get landing page data by slug."""
    return LANDING_PAGES.get(slug)


def _get_related_pages(slugs: list[str]) -> list[dict]:
    """Get page data for related pages."""
    return [
        {
            "slug": slug,
            "title": LANDING_PAGES[slug]["title"],
            "route_name": LANDING_PAGES[slug]["route_name"],
        }
        for slug in slugs
        if slug in LANDING_PAGES
    ]


@seo_bp.route("/why-are-my-plant-leaves-drooping")
def drooping():
    """Why are my plant leaves drooping? landing page."""
    page = _get_page("why-are-my-plant-leaves-drooping")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/am-i-overwatering-my-plant")
def overwatering():
    """Am I overwatering my plant? landing page."""
    page = _get_page("am-i-overwatering-my-plant")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/how-often-should-i-water-my-plant")
def watering_frequency():
    """How often should I water my plant? landing page."""
    page = _get_page("how-often-should-i-water-my-plant")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/why-are-my-plant-leaves-turning-yellow")
def yellow_leaves():
    """Why are my plant leaves turning yellow? landing page."""
    page = _get_page("why-are-my-plant-leaves-turning-yellow")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/should-i-water-my-plant-today")
def water_today():
    """Should I water my plant today? landing page."""
    page = _get_page("should-i-water-my-plant-today")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/why-is-my-plant-not-growing")
def not_growing():
    """Why is my plant not growing? landing page."""
    page = _get_page("why-is-my-plant-not-growing")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/indoor-plant-care-for-beginners")
def beginners_guide():
    """Indoor plant care for beginners landing page."""
    page = _get_page("indoor-plant-care-for-beginners")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)


@seo_bp.route("/why-are-my-plant-leaves-curling")
def curling_leaves():
    """Why are my plant leaves curling? landing page."""
    page = _get_page("why-are-my-plant-leaves-curling")
    related = _get_related_pages(page["related_pages"])
    return render_template("seo/landing.html", page=page, related_pages=related)

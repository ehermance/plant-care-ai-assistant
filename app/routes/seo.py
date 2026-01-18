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


seo_bp = Blueprint("seo", __name__)


# Slug to route name mapping for URL generation
SLUG_TO_ROUTE = {
    "why-are-my-plant-leaves-drooping": "drooping",
    "am-i-overwatering-my-plant": "overwatering",
    "how-often-should-i-water-my-plant": "watering_frequency",
    "why-are-my-plant-leaves-turning-yellow": "yellow_leaves",
    "should-i-water-my-plant-today": "water_today",
}


# Landing page data - problem-first content
LANDING_PAGES = {
    "why-are-my-plant-leaves-drooping": {
        "slug": "why-are-my-plant-leaves-drooping",
        "route_name": "drooping",
        "title": "Why Are My Plant Leaves Drooping? (And What to Do)",
        "meta_description": "Drooping leaves are stressful to see. Learn the most common causes—from watering issues to light problems—and how to fix them fast.",
        "emoji": "🥀",
        "intro": "Nothing's more disheartening than seeing your once-perky plant suddenly slumping over. Don't panic—drooping leaves are one of the most common plant problems, and they're usually fixable once you identify the cause.",
        "causes": [
            {
                "title": "Underwatering",
                "description": "The most common culprit. When soil gets too dry, plants can't maintain turgor pressure in their cells, causing leaves to wilt. Check if the soil is bone dry several inches down."
            },
            {
                "title": "Overwatering",
                "description": "Ironically, too much water causes drooping too. Waterlogged roots can't absorb oxygen, leading to root rot. If the soil is soggy and smells musty, this might be your issue."
            },
            {
                "title": "Temperature stress",
                "description": "Sudden temperature changes—like cold drafts from windows or hot air from vents—can shock plants into drooping. Most houseplants prefer consistent temps between 60-75°F."
            },
            {
                "title": "Transplant shock",
                "description": "Recently repotted? Plants often droop for a few days while their roots adjust to new soil. Give them time and gentle care."
            },
            {
                "title": "Root bound",
                "description": "If roots are circling the pot with nowhere to grow, the plant can't absorb enough water or nutrients. Time for a bigger home."
            }
        ],
        "bottom_line": "Drooping can mean many things—from a simple need for water to something more serious like root rot. The key is checking soil moisture first, then investigating other factors.",
        "cta_text": "Ask PlantCareAI why your plant is drooping",
        "cta_question": "Why is my plant drooping?",
        "related_pages": ["am-i-overwatering-my-plant", "why-are-my-plant-leaves-turning-yellow"],
    },
    "am-i-overwatering-my-plant": {
        "slug": "am-i-overwatering-my-plant",
        "route_name": "overwatering",
        "title": "Am I Overwatering My Plant? Signs & Fixes",
        "meta_description": "Overwatering kills more houseplants than anything else. Learn the telltale signs you're giving your plant too much water and how to fix it.",
        "emoji": "💧",
        "intro": "Here's a hard truth: overwatering kills more houseplants than neglect ever will. It's easy to do—we want to show our plants love, and watering feels like caring. But too much of a good thing can drown your plant's roots.",
        "causes": [
            {
                "title": "Yellow leaves (especially lower ones)",
                "description": "When older leaves turn yellow and feel soft or mushy, it's often a sign the roots are sitting in too much water and can't function properly."
            },
            {
                "title": "Soil stays wet for days",
                "description": "If your soil is still moist a week after watering, you're watering too frequently or your pot lacks drainage. Roots need to breathe between waterings."
            },
            {
                "title": "Mushy stems or brown, soft roots",
                "description": "This is root rot territory. Healthy roots are white or tan and firm. If they're brown, black, or mushy, overwatering has caused decay."
            },
            {
                "title": "Fungus gnats",
                "description": "Those tiny flies hovering around your plant? They love moist soil. A gnat infestation often signals chronically wet conditions."
            },
            {
                "title": "Mold on soil surface",
                "description": "White fuzzy growth on top of your soil means it's staying too wet for too long. Good airflow and less frequent watering can help."
            }
        ],
        "bottom_line": "Most plants prefer to dry out somewhat between waterings. When in doubt, stick your finger 2 inches into the soil—if it's still moist, wait a few more days.",
        "cta_text": "Get personalized watering advice for your plant",
        "cta_question": "How often should I water my plant?",
        "related_pages": ["how-often-should-i-water-my-plant", "why-are-my-plant-leaves-drooping"],
    },
    "how-often-should-i-water-my-plant": {
        "slug": "how-often-should-i-water-my-plant",
        "route_name": "watering_frequency",
        "title": "How Often Should I Water My Plant? (Stop Guessing)",
        "meta_description": "There's no universal watering schedule. Learn how to read your plant's needs based on soil, light, humidity, and season—not just the calendar.",
        "emoji": "🚿",
        "intro": "\"Water once a week\" is the most common—and most misleading—plant care advice out there. The truth is, watering frequency depends on your specific plant, pot, soil, light, and even the weather outside.",
        "causes": [
            {
                "title": "Check the soil, not the calendar",
                "description": "Instead of watering on a schedule, stick your finger 1-2 inches into the soil. Dry? Water. Still moist? Wait. This simple test works for most plants."
            },
            {
                "title": "Consider your plant's needs",
                "description": "Succulents and cacti want to dry out completely. Tropical plants like consistent moisture. Ferns hate drying out. Know your plant's preferences."
            },
            {
                "title": "Factor in the season",
                "description": "Plants need more water during active growth (spring/summer) and less during dormancy (fall/winter). Adjust your routine as seasons change."
            },
            {
                "title": "Watch your environment",
                "description": "Bright light, low humidity, and warm temps mean faster drying. A plant near a sunny window needs water more often than one in a dim corner."
            },
            {
                "title": "Pot and soil matter",
                "description": "Terracotta dries faster than plastic. Well-draining soil dries faster than dense soil. Bigger pots hold moisture longer than small ones."
            }
        ],
        "bottom_line": "There's no magic number. The best watering schedule is the one that responds to your plant's actual needs—which change with light, temperature, humidity, and season.",
        "cta_text": "Get a personalized watering recommendation",
        "cta_question": "When should I water my plant?",
        "related_pages": ["am-i-overwatering-my-plant", "should-i-water-my-plant-today"],
    },
    "why-are-my-plant-leaves-turning-yellow": {
        "slug": "why-are-my-plant-leaves-turning-yellow",
        "route_name": "yellow_leaves",
        "title": "Why Are My Plant Leaves Turning Yellow?",
        "meta_description": "Yellow leaves can mean many things—from simple aging to serious problems. Learn the common causes and how to diagnose what's wrong with your plant.",
        "emoji": "🍂",
        "intro": "Yellow leaves are your plant's way of waving a little flag that says \"something's off.\" The tricky part? Yellowing can have many different causes, and figuring out which one applies to your plant takes some detective work.",
        "causes": [
            {
                "title": "Natural aging",
                "description": "Good news first: some yellowing is completely normal. Older leaves at the bottom of the plant naturally yellow and drop as the plant focuses energy on new growth."
            },
            {
                "title": "Overwatering",
                "description": "The #1 cause of yellow leaves. When roots sit in water, they can't absorb nutrients properly, and leaves turn yellow—often starting with lower leaves."
            },
            {
                "title": "Underwatering",
                "description": "Severely dry plants also yellow, but the leaves usually feel crispy rather than soft. Check if your soil has pulled away from the pot edges."
            },
            {
                "title": "Nutrient deficiency",
                "description": "If your plant hasn't been fertilized in a while, it might be hungry. Nitrogen deficiency shows as overall yellowing; iron deficiency yellows new growth first."
            },
            {
                "title": "Too much direct sun",
                "description": "Some plants get \"sunburned.\" If yellow patches appear on leaves facing a window, your plant might be getting too much intense light."
            }
        ],
        "bottom_line": "Yellow leaves rarely mean immediate doom. Start by checking your watering habits—that's the cause in most cases. If watering seems fine, consider light, nutrients, and natural leaf turnover.",
        "cta_text": "Ask PlantCareAI to diagnose your yellow leaves",
        "cta_question": "Why are my plant's leaves turning yellow?",
        "related_pages": ["am-i-overwatering-my-plant", "why-are-my-plant-leaves-drooping"],
    },
    "should-i-water-my-plant-today": {
        "slug": "should-i-water-my-plant-today",
        "route_name": "water_today",
        "title": "Should I Water My Plant Today?",
        "meta_description": "Not sure if it's time to water? Learn the quick checks that tell you whether your plant needs water right now—plus how weather affects watering.",
        "emoji": "🤔",
        "intro": "You're staring at your plant, watering can in hand, wondering: \"Do you need this or not?\" We've all been there. Here's how to know for sure.",
        "causes": [
            {
                "title": "Do the finger test",
                "description": "Stick your finger 1-2 inches into the soil. If it feels dry at that depth, most plants are ready for water. Still moist? Check again in a day or two."
            },
            {
                "title": "Lift the pot",
                "description": "Dry soil is surprisingly light. Once you know how heavy your pot feels after watering, you can gauge moisture by weight alone. Light = time to water."
            },
            {
                "title": "Look at the leaves",
                "description": "Some plants show subtle signs before wilting. Peace lilies droop slightly. Pothos leaves curl at the edges. Learn your plant's \"I'm thirsty\" signals."
            },
            {
                "title": "Check the weather",
                "description": "Rainy, humid day? Your plant probably doesn't need water. Dry, sunny, or heating season? It might dry out faster than usual. Weather matters even indoors."
            },
            {
                "title": "Consider the season",
                "description": "In winter, most plants slow down and need less water. In summer, they may need water twice as often. Adjust your expectations with the seasons."
            }
        ],
        "bottom_line": "When in doubt, wait. Most plants recover better from slight underwatering than from overwatering. If the soil is dry and the plant looks thirsty, go ahead and water thoroughly.",
        "cta_text": "Get a weather-aware watering recommendation",
        "cta_question": "Should I water my plant today?",
        "related_pages": ["how-often-should-i-water-my-plant", "am-i-overwatering-my-plant"],
    },
}


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

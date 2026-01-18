"""
Marketing landing pages and email management.

Provides:
- SEO landing pages (AI Plant Doctor)
- Sitemap and robots.txt
- Email unsubscribe functionality
"""

from __future__ import annotations
from flask import Blueprint, render_template, Response, current_app
from xml.sax.saxutils import escape
import os
import json


marketing_bp = Blueprint("marketing", __name__)


def _load_guide_slugs():
    """Load guide slugs for sitemap generation."""
    guides_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "guides.json"
    )
    try:
        with open(guides_path, "r", encoding="utf-8") as f:
            guides = json.load(f)
            return [g.get("slug") for g in guides if g.get("slug")]
    except FileNotFoundError:
        return []


@marketing_bp.route("/ai-plant-doctor")
def ai_plant_doctor():
    """
    SEO landing page for AI Plant Doctor feature.

    Targets keywords: "AI plant care", "plant care assistant", "plant doctor"
    Links to /ask for the actual tool.
    """
    return render_template("marketing/ai-plant-doctor.html")


@marketing_bp.route("/sitemap.xml")
def sitemap():
    """
    Dynamic XML sitemap for search engines.

    Lists all public pages with priority and change frequency.
    """
    # Use configured base URL (not request.url_root to prevent Host header injection)
    base_url = os.getenv("APP_URL", "https://plantcareai.app")

    # Static public pages with priorities
    pages = [
        {"loc": "/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": "/ask", "priority": "0.9", "changefreq": "weekly"},
        {"loc": "/ai-plant-doctor", "priority": "0.9", "changefreq": "monthly"},
        {"loc": "/plant-care-guides/", "priority": "0.8", "changefreq": "weekly"},
        {"loc": "/features/", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "/auth/signup", "priority": "0.7", "changefreq": "monthly"},
        {"loc": "/auth/login", "priority": "0.6", "changefreq": "monthly"},
        {"loc": "/terms", "priority": "0.3", "changefreq": "yearly"},
        {"loc": "/privacy", "priority": "0.3", "changefreq": "yearly"},
    ]

    # SEO landing pages (problem-first content pages)
    seo_landing_pages = [
        "/why-are-my-plant-leaves-drooping",
        "/am-i-overwatering-my-plant",
        "/how-often-should-i-water-my-plant",
        "/why-are-my-plant-leaves-turning-yellow",
        "/should-i-water-my-plant-today",
    ]
    for slug in seo_landing_pages:
        pages.append({"loc": slug, "priority": "0.8", "changefreq": "monthly"})

    # Add individual guide pages
    for slug in _load_guide_slugs():
        pages.append({
            "loc": f"/plant-care-guides/{slug}",
            "priority": "0.7",
            "changefreq": "monthly"
        })

    # Build XML
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        xml_content += "  <url>\n"
        xml_content += f"    <loc>{escape(base_url + page['loc'])}</loc>\n"
        xml_content += f"    <changefreq>{escape(page['changefreq'])}</changefreq>\n"
        xml_content += f"    <priority>{escape(page['priority'])}</priority>\n"
        xml_content += "  </url>\n"

    xml_content += "</urlset>"

    return Response(xml_content, mimetype="application/xml")


@marketing_bp.route("/robots.txt")
def robots():
    """
    Serve robots.txt from root URL.

    Search engines expect this at /robots.txt, not /static/robots.txt.
    """
    robots_path = os.path.join(current_app.static_folder, "robots.txt")
    try:
        with open(robots_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        # Provide sensible default if file is missing
        content = "User-agent: *\nAllow: /"
    return Response(content, mimetype="text/plain")


@marketing_bp.route("/unsubscribe/<token>")
def unsubscribe(token: str):
    """
    One-click unsubscribe from marketing emails.

    Token is a signed user_id that expires after 30 days.
    Shows a confirmation page after unsubscribing.
    """
    from app.services.marketing_emails import verify_unsubscribe_token, sync_to_resend_audience
    from app.services import supabase_client

    # Verify token
    user_id = verify_unsubscribe_token(token)

    if not user_id:
        return render_template(
            "marketing/unsubscribe.html",
            success=False,
            error="This unsubscribe link has expired or is invalid. Please visit your account settings to manage email preferences.",
        )

    # Get user profile
    profile = supabase_client.get_user_profile(user_id)

    if not profile:
        return render_template(
            "marketing/unsubscribe.html",
            success=False,
            error="We couldn't find your account. Please visit your account settings to manage email preferences.",
        )

    # Check if already unsubscribed
    if not profile.get("marketing_opt_in", False):
        return render_template(
            "marketing/unsubscribe.html",
            success=True,
            already_unsubscribed=True,
        )

    # Unsubscribe the user
    success, error = supabase_client.update_marketing_preference(
        user_id, marketing_opt_in=False
    )

    if success:
        # Remove from Resend Audience
        email = profile.get("email")
        if email:
            sync_to_resend_audience(email, subscribed=False)

        return render_template(
            "marketing/unsubscribe.html",
            success=True,
            already_unsubscribed=False,
        )
    else:
        return render_template(
            "marketing/unsubscribe.html",
            success=False,
            error="Something went wrong. Please try again or visit your account settings.",
        )

"""
Flask CLI commands for one-off administrative tasks.

Usage:
    flask send-legal-notification                    # Dry run (count users)
    flask send-legal-notification --to you@email.com # Test with one email
    flask send-legal-notification --confirm          # Send to all users
"""

from __future__ import annotations

import time

import click
from flask.cli import with_appcontext


@click.command("send-legal-notification")
@click.option("--confirm", is_flag=True, default=False,
              help="Actually send emails. Without this flag, only counts users (dry run).")
@click.option("--to", default=None,
              help="Send a single test email to this address instead of all users.")
@with_appcontext
def send_legal_notification_command(confirm: bool, to: str | None) -> None:
    """Send legal update notification email to all users (one-time)."""
    from app.services import supabase_client
    from app.services.email import send_legal_update_email
    from app.utils.sanitize import mask_email

    # Single-email test mode
    if to:
        click.echo(f"Sending test email to {to}...")
        result = send_legal_update_email(to)
        if result.get("success"):
            click.echo("Test email sent successfully. Check your inbox.")
        else:
            click.echo(f"Failed: {result.get('error', 'unknown')}")
        return

    admin = supabase_client.get_admin_client()
    if not admin:
        click.echo("Error: Supabase admin client not configured (SUPABASE_SERVICE_ROLE_KEY missing).")
        raise SystemExit(1)

    # Fetch all user emails via admin client (bypasses RLS)
    response = admin.table("profiles").select("id,email").execute()
    users = response.data if response and response.data else []

    if not users:
        click.echo("No users found in the profiles table.")
        return

    click.echo(f"Found {len(users)} user(s) to notify.")

    if not confirm:
        click.echo("\nDry run — no emails sent. Use --confirm to send.")
        return

    # Send emails with progress tracking
    sent = 0
    failed = 0
    skipped = 0

    for i, user in enumerate(users, 1):
        email = user.get("email")
        if not email:
            skipped += 1
            continue

        result = send_legal_update_email(email)
        if result.get("success"):
            sent += 1
        elif result.get("error") == "rate_limit":
            click.echo(f"  [{i}/{len(users)}] Rate limited — waiting 2s...")
            time.sleep(2)
            # Retry once after waiting
            result = send_legal_update_email(email)
            if result.get("success"):
                sent += 1
            else:
                failed += 1
                click.echo(f"  [{i}/{len(users)}] Failed (after retry): {mask_email(email)}")
        else:
            failed += 1
            click.echo(f"  [{i}/{len(users)}] Failed: {result.get('error', 'unknown')}")

        # Brief pause between emails to avoid rate limits
        if i < len(users):
            time.sleep(0.5)

    click.echo(f"\nDone. Sent: {sent}, Failed: {failed}, Skipped: {skipped}")

"""
Local development entry point.

Creates the Flask app via create_app() and runs the dev server. Keeps startup
simple and avoids embedding app logic here.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # For local dev only; use a proper WSGI server in production.
    app.run(debug=True)

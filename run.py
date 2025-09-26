"""
Development entrypoint.

Creates the Flask app via the application factory and runs the built-in
debug server. Useful for local development with auto-reload.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

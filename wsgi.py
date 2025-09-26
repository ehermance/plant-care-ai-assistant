"""
WSGI entrypoint for production servers (gunicorn/uwsgi).

The server imports `app` from this module to obtain the Flask application
object created by the application factory.
"""

from app import create_app

app = create_app()

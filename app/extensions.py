"""
Defines application-wide extensions. Keeps creation/import separate from
initialization to avoid circular imports. Currently provides Flask-Limiter.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Created here; initialized with app in create_app()
limiter = Limiter(key_func=get_remote_address)

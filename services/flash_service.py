"""Shared flash-message helper usable from request handlers.

The Jinja template global `flash` is registered in main.py from this same
function so templates and Python handlers stay in sync.
"""


def flash(request, message: str, category: str = "info") -> None:
    """Store a flashed message in the session for the next render."""
    if "flashed" not in request.session:
        request.session["flashed"] = []
    request.session["flashed"].append({"message": message, "category": category})

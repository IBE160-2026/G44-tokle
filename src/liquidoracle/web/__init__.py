"""Layer `web` (AD-1, AD-18): the Flask app factory, routes and server-rendered templates."""

from __future__ import annotations

from flask import Flask, render_template

from liquidoracle.settings import Settings


def create_app(settings: Settings) -> Flask:
    """Build the Flask app. It never starts a server or a worker; `liquidoracle run` does (AD-23)."""
    app = Flask(__name__)

    @app.get("/")
    def check_a_wallet() -> str:
        # Placeholder until Story 1.7 builds the real lookup page (UX-DR16).
        return render_template("check.html", offline=settings.offline)

    return app

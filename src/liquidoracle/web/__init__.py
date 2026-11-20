"""Layer `web` (AD-1, AD-18): the Flask app factory, routes and server-rendered templates.

Every page is complete without JavaScript. The words and numbers come finished from
`services.lookup`, which takes them from `core/phrases` (AD-25); templates only place them.
"""

from __future__ import annotations

from flask import Flask, Response, redirect, render_template, request, url_for

from liquidoracle.services.lookup import ADDRESS, LOOKUP_LEDE, Lookup, Outcome
from liquidoracle.settings import Settings


def create_app(settings: Settings, lookup: Lookup) -> Flask:
    """Build the Flask app. It never starts a server or a worker; `liquidoracle run` does (AD-23)."""
    app = Flask(__name__)

    @app.context_processor
    def every_page() -> dict[str, object]:
        # AD-13: the web layer reads the mode only to show the Offline pill (UX-DR18).
        return {"offline": settings.offline}

    @app.get("/")
    def check_a_wallet() -> str | Response:
        """The Lookup page (FR-1, UX-DR16). The form sends `GET /?address=…`, so it works without JavaScript."""
        error = None
        value = ""
        if "address" in request.args:
            value = request.args["address"].strip()
            address, error = lookup.check(value)
            if address is not None:
                return redirect(url_for("wallet", raw=address))
        return render_template(
            "check.html",
            lede=LOOKUP_LEDE,
            value=value,
            error=error,
            samples=lookup.sample_list(),
            not_loaded=lookup.not_loaded(),
        )

    @app.get("/wallet/<path:raw>")
    def wallet(raw: str) -> str | Response | tuple[str, int]:
        """The Verdict page (FR-8, FR-10, FR-14, UX-DR20, UX-DR23); a malformed address is *Page not found*."""
        if not ADDRESS.fullmatch(raw):
            return not_found()
        if raw != raw.lower():
            return redirect(url_for("wallet", raw=raw.lower()), code=301)
        page = lookup.wallet_page(raw)
        if page.outcome is Outcome.VERDICT:
            return render_template("verdict.html", page=page)
        samples = lookup.sample_list() if page.outcome is Outcome.NOT_AVAILABLE_OFFLINE else None
        return render_template("message.html", page=page, samples=samples)

    @app.errorhandler(404)
    @app.errorhandler(405)  # e.g. a POST to a page: no page answers it
    def not_found(error: object = None) -> tuple[str, int]:
        """UX-DR7: any bad address shows *Page not found* with a link to *Check a wallet*."""
        return render_template("not_found.html"), 404

    @app.errorhandler(500)
    def went_wrong(error: object) -> tuple[str, int]:
        """Pages never show a raw exception (Conventions › Errors): a plain page in the app's frame."""
        return render_template("error.html"), 500

    return app

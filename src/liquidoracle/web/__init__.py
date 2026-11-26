"""Layer `web` (AD-1, AD-18): the Flask app factory, routes and server-rendered templates.

Every page is complete without JavaScript. The words and numbers come finished from
`services.lookup`, which takes them from `core/phrases` (AD-25); templates only place them.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

from liquidoracle.services.lookup import (
    ADDRESS,
    FETCHING_LINE,
    LOOKUP_LEDE,
    TRY_AGAIN,
    UNAVAILABLE_HEADING,
    Lookup,
    Outcome,
)
from liquidoracle.services import scans_page as scans_page_module
from liquidoracle.services.scans_page import ScansPage, ScansView, Submitted
from liquidoracle.settings import Settings


LOCAL_NAMES = frozenset({"127.0.0.1", "localhost"})  # the names a POST may address the app by (Story 4.4 review)


def create_app(settings: Settings, lookup: Lookup, scans: ScansPage | None = None) -> Flask:
    """Build the Flask app. It never starts a server or a worker; `liquidoracle run` does (AD-23).

    `scans` is the Scans page's service; when not given it is built over the lookup's store and job queue.
    """
    app = Flask(__name__)
    built: list[ScansPage] = [] if scans is None else [scans]

    def scans_page() -> ScansPage:
        if not built:  # built on first use, so pages that never open the Scans page need no store
            built.append(ScansPage(lookup.store, jobs=lookup.jobs, seed=settings.seed,
                                   rate=settings.polymarket_requests_per_second))
        return built[0]

    def scans_html(view: ScansView, status: int = 200) -> tuple[str, int]:
        return render_template(
            "scans.html", view=view, page_title=scans_page_module.PAGE_TITLE, running_title=scans_page_module.RUNNING_TITLE,
            offline_info=scans_page_module.OFFLINE_INFO, few_after=scans_page_module.FEW_AFTER,
            warn_days=scans_page_module.WARN_DAYS, min_size=scans_page_module.MIN_SIZE, max_size=scans_page_module.MAX_SIZE,
        ), status

    @app.before_request
    def same_origin_posts_only() -> None:
        """A POST from another web page is refused, so nothing starts (Story 4.4): its `Origin` must be this app's,
        and the app must be addressed by its own local name, so a site whose name was pointed at 127.0.0.1
        (DNS rebinding) is refused too (AD-23: the app listens on 127.0.0.1 only)."""
        if request.method != "POST":
            return
        origin = request.headers.get("Origin")
        local = request.host.rsplit(":", 1)[0] in LOCAL_NAMES
        if not local or (origin is not None and origin != request.host_url.rstrip("/")):
            abort(403)

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
        """The Verdict page (FR-1, FR-2, FR-8, FR-10, FR-14, UX-DR20, UX-DR22, UX-DR23).

        A malformed address is *Page not found*. In a live run, `?job=<id>` follows a lookup job and
        `?stored=1` shows the stored snapshot whatever its age (the outage page's button).
        """
        if not ADDRESS.fullmatch(raw):
            return not_found()
        if raw != raw.lower():
            kept = {key: request.args[key] for key in ("job", "stored") if key in request.args}
            return redirect(url_for("wallet", raw=raw.lower(), **kept), code=301)
        page = lookup.wallet_page(
            raw, job=request.args.get("job", type=int), stored=request.args.get("stored") == "1"
        )
        if page.outcome is Outcome.QUEUED:
            return redirect(url_for("wallet", raw=raw, job=page.job_id))
        if page.outcome is Outcome.VERDICT:
            return render_template("verdict.html", page=page)
        if page.outcome is Outcome.FETCHING:
            return render_template("fetching.html", page=page, line=FETCHING_LINE)
        if page.outcome is Outcome.UNAVAILABLE:
            return render_template("unavailable.html", page=page, heading=UNAVAILABLE_HEADING, try_again=TRY_AGAIN)
        if page.outcome is Outcome.FAILED:
            return render_template("error.html"), 500  # the same status as the app's own error page
        samples = lookup.sample_list() if page.outcome is Outcome.NOT_AVAILABLE_OFFLINE else None
        return render_template("message.html", page=page, samples=samples)

    @app.get("/scans")
    def scan_list() -> tuple[str, int]:
        """The Scans page (FR-16, UX-DR30, UX-DR31, UX-DR32): the New Scan form, the Scan list and progress."""
        return scans_html(scans_page().view())

    @app.post("/scans")
    def start_scan() -> Response | tuple[str, int]:
        """The New Scan form. A started (or refused) Scan goes back to the list; errors and the warning stay."""
        outcome, view = scans_page().submit(
            request.form.get("cutoff", ""), request.form.get("wallets", ""), confirmed=request.form.get("confirmed") == "1"
        )
        if view is None:
            return redirect(url_for("scan_list"), code=303)
        return scans_html(view, 400 if outcome is Submitted.INVALID else 200)

    @app.post("/scans/<int:scan_id>/resume")
    def resume_scan(scan_id: int) -> Response:
        """Resume a stopped or interrupted Scan (AD-5); anything else changes nothing."""
        scans_page().resume(scan_id)
        return redirect(url_for("scan_list"), code=303)

    @app.get("/scans/estimate")
    def scan_estimate() -> Response:
        """The rough time estimate for `?wallets=N`, for scans.js (UX-DR30); `text` is null for a number not allowed."""
        reply = jsonify(text=scans_page().estimate(request.args.get("wallets", "")))
        reply.headers["Cache-Control"] = "no-store"
        return reply

    @app.errorhandler(403)
    def refused(error: object) -> tuple[str, int]:
        """A POST from another web page: plain *Page not found*-style page, nothing done."""
        return render_template("not_found.html"), 403

    @app.get("/jobs/<int:job_id>/progress")
    def job_progress(job_id: int) -> Response | tuple[Response, int]:
        """AD-5: `{status, phase, done, total, message}`, the one contract with `progress.js`."""
        progress = lookup.progress(job_id)
        if progress is None:
            return jsonify(error="no such job"), 404
        reply = jsonify(asdict(progress))
        reply.headers["Cache-Control"] = "no-store"  # every poll must reach the app
        return reply

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

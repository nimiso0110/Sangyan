"""ScamShield Bharat API. Stateless: submitted content is processed in memory and never stored or logged."""
import collections
import os
import secrets
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from . import engine, learn, llm, pages

Lang = Literal["en", "hi", "ta"]
MAX_IMG = int(os.getenv("MAX_IMAGE_MB", "5")) * 1024 * 1024
app = FastAPI(title="ScamShield Bharat", version="0.1.0", docs_url="/api/docs", redoc_url=None)
_hits = collections.defaultdict(collections.deque)
learn.install()
app.add_middleware(GZipMiddleware, minimum_size=1024)
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(req, call_next):
    r = await call_next(req)
    r.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                      "Permissions-Policy": "microphone=(self), camera=(), geolocation=()"})
    if not req.url.path.startswith("/api/docs") and req.url.path != "/api/openapi.json":  # Swagger UI loads scripts from a CDN
        r.headers["Content-Security-Policy"] = CSP
    if not req.url.path.startswith("/api/") and not req.url.path.startswith("/static/"):
        r.headers.setdefault("Cache-Control", "no-cache")
    return r


@app.exception_handler(StarletteHTTPException)
async def _http(req, exc):
    if exc.status_code == 404 and not req.url.path.startswith("/api/"):
        return HTMLResponse(pages.render("404"), 404)
    return JSONResponse({"detail": exc.detail}, exc.status_code, headers=getattr(exc, "headers", None))


def limiter(req: Request):
    q, now = _hits[req.client.host if req.client else "?"], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= int(os.getenv("RATE_LIMIT_PER_MIN", "30")):
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    lang: Lang = "en"
    use_llm: bool = False  # opt-in: sends the (masked) text to the configured AI provider


class UrlIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    lang: Lang = "en"


@app.exception_handler(RequestValidationError)
async def _bad_input(_, __):
    return JSONResponse({"detail": "Please check your input (text up to 5000 characters, a valid link, or a supported image) and try again."}, 422)


@app.exception_handler(Exception)
async def _oops(_, __):
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, 500)


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "rules+llm" if llm.enabled() else "rules", "llm": llm.enabled()}


@app.get("/api/demo-cases")
def demo_cases():
    return {"note": "Fictional examples for demonstration only.", "cases": engine.DEMO}


@app.get("/api/indicators")
def indicators(lang: Lang = "en"):
    return {"indicators": engine.indicators(lang)}


@app.get("/api/stats")
def stats():
    return engine.stats()


@app.post("/api/analyze/text", dependencies=[Depends(limiter)])
def analyze_text(b: TextIn):
    if not b.text.strip():
        raise HTTPException(422, "Please paste some text to analyse.")
    r = engine.analyze(b.text.strip(), b.lang)
    if b.use_llm:
        r = llm.enhance(r, b.text.strip(), b.lang)
    engine.record("text", r)
    return r


@app.post("/api/analyze/url", dependencies=[Depends(limiter)])
def analyze_url(b: UrlIn):
    r = engine.analyze_url(b.url, b.lang)
    if r is None:
        raise HTTPException(422, "That does not look like a valid link. Example: https://example.com/page")
    engine.record("url", r)
    return r


@app.post("/api/analyze/image", dependencies=[Depends(limiter)])
async def analyze_image(file: UploadFile = File(...), lang: Lang = Form("en"), use_llm: bool = Form(False)):
    data = await file.read(MAX_IMG + 1)
    if len(data) > MAX_IMG:
        raise HTTPException(413, f"That image is too large (maximum {MAX_IMG // 2**20} MB).")
    if not (data[:4] == b"\x89PNG" or data[:3] == b"\xff\xd8\xff" or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
        raise HTTPException(415, "Please upload a PNG, JPEG or WebP image.")
    try:
        o = await run_in_threadpool(engine.ocr, data)
        text = o["text"]
    except engine.OcrUnavailable:
        raise HTTPException(503, "Screenshot reading (OCR) is not set up on this server. Paste the text instead.")
    except Exception:
        raise HTTPException(422, "We could not read that image. Try a clearer screenshot, or paste the text instead.")
    if not text.strip():
        raise HTTPException(422, "No text was found in that image. Try a clearer screenshot, or paste the text instead.")
    r = engine.analyze(text[:5000], lang)
    if use_llm:
        r = await run_in_threadpool(llm.enhance, r, text[:5000], lang)
    engine.record("image", r)
    return {**r, "ocr_text": text[:5000], "ocr_confidence": o["confidence"],
            "ocr_languages": o["languages"], "ocr_missing": o["missing"]}


class ContribIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    lang: Lang = "en"
    label: Literal["scam", "not_scam", "unsure"]
    consent: bool


class Decide(BaseModel):
    phrase: str = Field(min_length=1, max_length=200)
    decision: Literal["approved", "rejected"]


def _admin(tok):
    want = os.getenv("ADMIN_TOKEN")
    if not want or not secrets.compare_digest(tok or "", want):
        raise HTTPException(403, "Not allowed.")


@app.post("/api/contribute", dependencies=[Depends(limiter)])
def contribute(b: ContribIn):
    if not b.consent:
        raise HTTPException(400, "Sharing needs your explicit consent.")
    return learn.contribute(b.text.strip(), b.lang, b.label)


@app.delete("/api/contribute/{token}", dependencies=[Depends(limiter)])
def uncontribute(token: str):
    return {"deleted": learn.delete(token)}


@app.get("/api/learning")
def learning():
    return {**learn.public(), "checks": engine.stats()["total"]}


@app.get("/api/admin/candidates")
def admin_candidates(x_admin_token: str = Header(None)):
    _admin(x_admin_token)
    return {"candidates": learn.candidates()}


@app.post("/api/admin/decide")
def admin_decide(b: Decide, x_admin_token: str = Header(None)):
    _admin(x_admin_token)
    try:
        learn.decide(b.phrase, b.decision)
    except ValueError:
        raise HTTPException(422, "That phrase is not a current candidate.")
    return {"ok": True}


STATIC = Path(__file__).parent / "static"


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _page(slug):
    return lambda: HTMLResponse(pages.render(slug))


for _slug in ("about", "privacy", "terms", "resources", "offline"):
    app.add_api_route(f"/{_slug}", _page(_slug), methods=["GET"], include_in_schema=False)


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg():
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    return FileResponse(STATIC / "favicon.ico", media_type="image/x-icon")


@app.get("/robots.txt", include_in_schema=False)
def robots(req: Request):
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {str(req.base_url).rstrip('/')}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(req: Request):
    b = str(req.base_url).rstrip("/")
    urls = "".join(f"<url><loc>{b}{p}</loc></url>" for p in ("/", "/about", "/resources", "/privacy", "/terms"))
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', media_type="application/xml")

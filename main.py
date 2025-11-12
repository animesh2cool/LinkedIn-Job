# main.py
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from sqlmodel import SQLModel, Session, create_engine, select
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from models import JobPost
from scraper import scrape_linkedin_for_term
from llm import summarize_text

# ------------------------------
# Load environment + logging
# ------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# ------------------------------
# Database setup
# ------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./linkedin_posts.db")
engine = create_engine(DATABASE_URL, echo=False)

# ------------------------------
# Scheduler
# ------------------------------
scheduler = BackgroundScheduler()

# ------------------------------
# Core logic
# ------------------------------
def save_posts_to_db(posts: List[dict], source: str = "linkedin"):
    with Session(engine) as session:
        for p in posts:
            raw_text = p.get("raw_text") or ""
            stmt = select(JobPost).where(JobPost.raw_text == raw_text)
            existing = session.exec(stmt).first()

            if existing:
                if not existing.summary:
                    existing.summary = p.get("summary")
                    session.add(existing)
                continue

            jp = JobPost(
                source=source,
                post_url=p.get("post_url"),
                raw_text=raw_text,
                summary=p.get("summary"),
                image_paths=",".join(p.get("images", [])) if p.get("images") else None,
                scraped_at=datetime.utcnow(),
            )
            session.add(jp)
        session.commit()
    logger.info("💾 Saved posts to database.")


def run_scrape_and_store(search_term: str, max_posts: int = 5):
    logger.info(f"🔍 Starting scrape for: {search_term}")
    scraped = scrape_linkedin_for_term(search_term=search_term, max_posts=max_posts)

    if not scraped:
        logger.warning("No posts scraped.")
        return

    # Combine all raw texts
    combined_text = "\n\n".join([p.get("raw_text", "") for p in scraped])

    # Summarize
    try:
        combined_summary = summarize_text(combined_text)
    except Exception as e:
        logger.exception("Summarization failed: %s", e)
        combined_summary = combined_text[:500]

    # Combine all images
    all_images = []
    for p in scraped:
        imgs = p.get("images") or []
        all_images.extend(imgs)

    save_posts_to_db(
        [
            {
                "raw_text": combined_text,
                "summary": combined_summary,
                "images": all_images,
            }
        ],
        source="linkedin",
    )

    logger.info("✅ One summarized post generated from 5 LinkedIn posts.")


def scheduled_job_wrapper():
    term = os.getenv("LINKEDIN_SEARCH_TERM", "Cognizant Walk-in Kolkata")
    try:
        run_in_threadpool(run_scrape_and_store, term, 5)
    except Exception as e:
        logger.exception("Scheduled job failed: %s", e)


def start_scheduler():
    trigger = CronTrigger(day_of_week="thu", hour=9, minute=0)
    scheduler.add_job(
        scheduled_job_wrapper,
        trigger,
        id="weekly_linkedin_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("🕒 Scheduler started: Weekly LinkedIn scrape set for Thursdays 09:00 (server time).")

# ------------------------------
# FastAPI setup
# ------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    logger.info("📦 Database tables created.")
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)
    logger.info("🧹 Scheduler stopped.")

app = FastAPI(title="LinkedIn Auto Scraper", lifespan=lifespan)

# ✅ Mount static before templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Jinja after static mount
templates = Jinja2Templates(directory="templates")

# ------------------------------
# Routes
# ------------------------------
@app.post("/scrape")
async def scrape_now(
    background: BackgroundTasks,
    company: str = Form(...),
    mode: str = Form(...),
    location: str = Form(...)
):
    search_term = f"{company} {mode} {location}"
    background.add_task(run_scrape_and_store, search_term, 5)
    return RedirectResponse(url="/", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with Session(engine) as session:
        stmt = select(JobPost).order_by(JobPost.scraped_at.desc())
        posts = session.exec(stmt).all()
    return templates.TemplateResponse("index.html", {"request": request, "posts": posts})


@app.get("/api/posts")
def api_posts(limit: int = 50):
    with Session(engine) as session:
        stmt = select(JobPost).order_by(JobPost.scraped_at.desc()).limit(limit)
        rows = session.exec(stmt).all()
    return rows


@app.get("/scheduler_status")
def scheduler_status():
    jobs = scheduler.get_jobs()
    return {"running": scheduler.running, "jobs": [str(j) for j in jobs]}

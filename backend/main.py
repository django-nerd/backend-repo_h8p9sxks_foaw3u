import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

from database import db, create_document, get_documents
from schemas import Project, Service

app = FastAPI(title="kupi-bassein API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "kupi-bassein backend running"}

@app.get("/test")
def test_database():
    info = {
        "database": "❌ Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            info["database"] = "✅ Connected"
            info["collections"] = db.list_collection_names()
    except Exception as e:
        info["database"] = f"⚠️ {str(e)[:120]}"
    return info

# Simple scraper utilities (idempotent, minimal and safe)
BASE_URL = "https://kupi-bassein.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FlamesBot/1.0; +https://example.com/bot)"
}

class ScrapeResult(BaseModel):
    created: int
    updated: int
    total: int

@app.post("/api/scrape/projects", response_model=ScrapeResult)
def scrape_projects():
    url = f"{BASE_URL}/portfolio"  # примерный путь; при изменении структуры можно скорректировать
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch portfolio page")
    soup = BeautifulSoup(r.text, "lxml")

    # Пытаемся найти карточки проектов (адаптивный подход по селекторам)
    cards = soup.select("a[href*='/portfolio/'], .portfolio-item, .projects-item")
    seen = set()
    created = 0
    updated = 0

    for el in cards:
        try:
            href = el.get("href") if el.name == "a" else el.select_one("a") and el.select_one("a").get("href")
            if not href:
                continue
            if href.startswith("/"):
                href_full = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                href_full = href
            else:
                href_full = f"{BASE_URL}/{href}"
            if href_full in seen:
                continue
            seen.add(href_full)

            title_el = el.get("title") or (el.text.strip() if hasattr(el, 'text') else None)
            title = title_el.strip() if isinstance(title_el, str) else (el.select_one(".title, h3, h2") or {}).get_text(strip=True) if el.select_one(".title, h3, h2") else None

            img_el = el.select_one("img") if hasattr(el, 'select_one') else None
            img = img_el.get("src") if img_el else None
            if img and img.startswith("/"):
                img = f"{BASE_URL}{img}"

            doc = Project(title=title or "Проект", image=img, specs=[], source_url=href_full)

            # Upsert by source_url
            existing = db["project"].find_one({"source_url": doc.source_url})
            if existing:
                db["project"].update_one({"_id": existing["_id"]}, {"$set": {"title": doc.title, "image": doc.image}})
                updated += 1
            else:
                create_document("project", doc)
                created += 1
        except Exception:
            continue

    total = created + updated
    return ScrapeResult(created=created, updated=updated, total=total)

@app.get("/api/projects", response_model=List[Project])
def list_projects(limit: int = 12):
    docs = get_documents("project", {}, limit=limit)
    # normalize ids and fields
    out: List[Project] = []
    for d in docs:
        try:
            out.append(Project(
                title=d.get("title", "Проект"),
                city=d.get("city"),
                image=d.get("image"),
                specs=d.get("specs", []),
                source_url=d.get("source_url"),
            ))
        except Exception:
            continue
    return out

@app.post("/api/scrape/services", response_model=ScrapeResult)
def scrape_services():
    url = f"{BASE_URL}/services"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch services page")
    soup = BeautifulSoup(r.text, "lxml")

    items = soup.select(".service, .services-item, a[href*='/services/']")
    seen = set()
    created = 0
    updated = 0

    for el in items:
        try:
            href = el.get("href") if el.name == "a" else el.select_one("a") and el.select_one("a").get("href")
            title = (el.get("title") or (el.select_one(".title, h3, h2") and el.select_one(".title, h3, h2").get_text(strip=True)) or el.get_text(strip=True))
            if not title:
                continue
            if href:
                if href.startswith("/"):
                    href_full = f"{BASE_URL}{href}"
                elif href.startswith("http"):
                    href_full = href
                else:
                    href_full = f"{BASE_URL}/{href}"
            else:
                href_full = None

            doc = Service(title=title, source_url=href_full)
            existing = db["service"].find_one({"title": doc.title})
            if existing:
                db["service"].update_one({"_id": existing["_id"]}, {"$set": {"source_url": doc.source_url}})
                updated += 1
            else:
                create_document("service", doc)
                created += 1
        except Exception:
            continue

    total = created + updated
    return ScrapeResult(created=created, updated=updated, total=total)

@app.get("/api/services", response_model=List[Service])
def list_services(limit: int = 20):
    docs = get_documents("service", {}, limit=limit)
    out: List[Service] = []
    for d in docs:
        try:
            out.append(Service(
                title=d.get("title", "Услуга"),
                description=d.get("description"),
                source_url=d.get("source_url"),
            ))
        except Exception:
            continue
    return out

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

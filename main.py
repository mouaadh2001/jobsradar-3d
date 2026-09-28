"""
JobsRadar 3D — Backend FastAPI
Scraping réel + enrichissement IA (Groq / Gemini)
"""

import os, json, re, time, asyncio, hashlib
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════
#  CONFIG  (variables d'environnement sur Railway)
# ══════════════════════════════════════════════
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SCANS_PER_DAY  = int(os.getenv("SCANS_PER_DAY", "4"))
PORT           = int(os.getenv("PORT", "8000"))

DB_PATH = "jobs_db.json"

KEYWORDS_3D = [
    "3D", "opengl", "vulkan", "rendering", "computer graphics",
    "unreal engine", "unity", "vr", "ar", "xr", "shader",
    "glsl", "hlsl", "ray tracing", "game dev", "simulation",
    "webgl", "three.js", "moteur de jeu", "temps réel",
    "blender", "houdini", "pipeline 3d", "rendu", "directx",
    "real-time", "gpu", "cuda", "game engine", "rigging",
    "animation 3d", "vfx", "fx developer", "technical artist",
]

SEARCH_QUERIES = [
    ("stage 3D rendering OpenGL C++",        "stage"),
    ("alternance unreal engine unity France", "alternance"),
    ("stage développeur VR AR XR France",    "stage"),
    ("alternance computer graphics shader",   "alternance"),
    ("stage jeux vidéo moteur rendu",         "stage"),
    ("alternance simulation 3D temps réel",   "alternance"),
    ("stage WebGL Three.js computer vision",  "stage"),
    ("alternance technical artist Blender",   "alternance"),
    ("stage GPU CUDA ray tracing France",     "stage"),
    ("alternance VFX Houdini pipeline 3D",    "alternance"),
]

TECH_TAGS = [
    "C++","Python","OpenGL","Vulkan","DirectX","HLSL","GLSL","Metal",
    "Unreal Engine","Unity","Blender","Houdini","Maya","3ds Max","Cinema 4D",
    "VR","AR","XR","WebGL","Three.js","Babylon.js","A-Frame",
    "Ray Tracing","Path Tracing","Shader","GPU","CUDA","OpenCL","Compute",
    "Rendering","Animation 3D","Rigging","Skinning","C#","Blueprint",
    "Simulation","Physics","Game Dev","Real-time","Technical Artist",
    "GLSL","HLSL","Substance","ZBrush","Nuke","After Effects","VFX",
    "Python","CMake","Git","Linux","Agile","Scrum",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

# ══════════════════════════════════════════════
#  DATABASE (JSON simple, persiste sur Railway)
# ══════════════════════════════════════════════

def load_db() -> dict:
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"jobs": [], "scan_count": 0, "last_scan": None, "logs": []}

def save_db(db: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def add_log(db: dict, level: str, message: str):
    db.setdefault("logs", []).append({
        "ts": datetime.now().isoformat(),
        "level": level,
        "message": message,
    })
    db["logs"] = db["logs"][-200:]  # Garder les 200 derniers logs

# ══════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════

def make_id(platform: str, company: str, title: str) -> str:
    raw = f"{platform}|{company}|{title}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:16]

def extract_tags(text: str) -> list[str]:
    found = []
    tl = text.lower()
    for tag in TECH_TAGS:
        if tag.lower() in tl and tag not in found:
            found.append(tag)
    return found[:7] if found else ["3D", "Rendu"]

def is_relevant(title: str, description: str = "") -> bool:
    text = (title + " " + description).lower()
    return any(kw in text for kw in KEYWORDS_3D)

def clean(text: str, maxlen: int = 400) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:maxlen] if len(text) > maxlen else text

# ══════════════════════════════════════════════
#  SCRAPERS
# ══════════════════════════════════════════════

async def scrape_indeed(client: httpx.AsyncClient, query: str, job_type: str) -> list[dict]:
    jobs = []
    try:
        q = httpx.URL("", params={"q": query, "l": "France", "sort": "date"})
        url = f"https://fr.indeed.com/jobs?{q.query.decode()}"
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return jobs
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")[:8]
        for card in cards:
            title_el = card.select_one("h2.jobTitle span, a.jobtitle")
            company_el = card.select_one("span.companyName, span.company")
            location_el = card.select_one("div.companyLocation, span.location")
            link_el = card.select_one("a[href*='/viewjob'], a[id^='job_']")
            if not title_el:
                continue
            title = clean(title_el.get_text())
            company = clean(company_el.get_text()) if company_el else "Entreprise"
            location = clean(location_el.get_text()) if location_el else "France"
            href = link_el.get("href", "") if link_el else ""
            job_url = f"https://fr.indeed.com{href}" if href.startswith("/") else href or url
            if not is_relevant(title):
                continue
            jobs.append({
                "title": title, "company": company, "location": location,
                "type": job_type, "platform": "Indeed", "url": job_url,
                "description": "", "tags": extract_tags(title), "posted_days_ago": 0,
            })
    except Exception as e:
        print(f"Indeed error: {e}")
    return jobs

async def scrape_wttj(client: httpx.AsyncClient, query: str, job_type: str) -> list[dict]:
    jobs = []
    try:
        contract = "INTERNSHIP" if job_type == "stage" else "APPRENTICESHIP"
        params = {
            "query": query,
            "refinementList[contract_type_names][]": contract,
            "refinementList[remote][]": "",
            "page": "1",
        }
        url = "https://www.welcometothejungle.com/fr/jobs?" + "&".join(
            f"{k}={httpx.URL('', params={k: v}).query.decode().split('=')[1]}" for k, v in params.items()
        )
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return jobs
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article[data-testid='search-results-list-item']")[:8]
        for card in cards:
            title_el = card.select_one("h3, h2")
            company_el = card.select_one("[data-testid='company-name'], span.sc-beqWAB")
            location_el = card.select_one("[data-testid='location'], span.sc-fnykZs")
            link_el = card.select_one("a[href*='/jobs/']")
            if not title_el:
                continue
            title = clean(title_el.get_text())
            company = clean(company_el.get_text()) if company_el else "Entreprise"
            location = clean(location_el.get_text()) if location_el else "France"
            href = link_el.get("href", "") if link_el else ""
            job_url = f"https://www.welcometothejungle.com{href}" if href.startswith("/") else url
            if not is_relevant(title):
                continue
            jobs.append({
                "title": title, "company": company, "location": location,
                "type": job_type, "platform": "Welcome to the Jungle", "url": job_url,
                "description": "", "tags": extract_tags(title), "posted_days_ago": 0,
            })
    except Exception as e:
        print(f"WTTJ error: {e}")
    return jobs

async def scrape_hellowork(client: httpx.AsyncClient, query: str, job_type: str) -> list[dict]:
    jobs = []
    try:
        contract = "stage" if job_type == "stage" else "alternance"
        q = httpx.URL("", params={"k": query, "c": contract, "l": "france"})
        url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?{q.query.decode()}"
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return jobs
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li[data-id], article.job-card, div[class*='JobCard']")[:8]
        for card in cards:
            title_el = card.select_one("h2, h3, [class*='title']")
            company_el = card.select_one("[class*='company'], [class*='Company']")
            location_el = card.select_one("[class*='location'], [class*='Location']")
            link_el = card.select_one("a[href]")
            if not title_el:
                continue
            title = clean(title_el.get_text())
            company = clean(company_el.get_text()) if company_el else "Entreprise"
            location = clean(location_el.get_text()) if location_el else "France"
            href = link_el.get("href", "") if link_el else ""
            job_url = f"https://www.hellowork.com{href}" if href.startswith("/") else href or url
            if not is_relevant(title):
                continue
            jobs.append({
                "title": title, "company": company, "location": location,
                "type": job_type, "platform": "HelloWork", "url": job_url,
                "description": "", "tags": extract_tags(title), "posted_days_ago": 0,
            })
    except Exception as e:
        print(f"HelloWork error: {e}")
    return jobs

async def scrape_linkedin(client: httpx.AsyncClient, query: str, job_type: str) -> list[dict]:
    jobs = []
    try:
        job_type_code = "I" if job_type == "stage" else "I"  # LinkedIn internship
        params = {"keywords": query, "location": "France", "f_JT": job_type_code, "sortBy": "DD"}
        url = "https://www.linkedin.com/jobs/search/?" + "&".join(f"{k}={v}" for k, v in params.items())
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return jobs
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.base-card, li.jobs-search__results-list")[:8]
        for card in cards:
            title_el = card.select_one("h3.base-search-card__title, h3.job-result-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle, span.job-result-card__subtitle")
            location_el = card.select_one("span.job-search-card__location, span.job-result-card__location")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view']")
            if not title_el:
                continue
            title = clean(title_el.get_text())
            company = clean(company_el.get_text()) if company_el else "Entreprise"
            location = clean(location_el.get_text()) if location_el else "France"
            href = link_el.get("href", "") if link_el else ""
            if not is_relevant(title):
                continue
            jobs.append({
                "title": title, "company": company, "location": location,
                "type": job_type, "platform": "LinkedIn", "url": href or url,
                "description": "", "tags": extract_tags(title), "posted_days_ago": 0,
            })
    except Exception as e:
        print(f"LinkedIn error: {e}")
    return jobs

async def scrape_apec(client: httpx.AsyncClient, query: str, job_type: str) -> list[dict]:
    """APEC via leur API JSON interne."""
    jobs = []
    try:
        payload = {
            "motsCles": query,
            "lieu": [{"typeLocalisation": "FRANCE"}],
            "typeContrat": ["143748"],  # Stage
            "nbParPage": 10,
            "page": 1,
        }
        if job_type == "alternance":
            payload["typeContrat"] = ["143750"]

        resp = await client.post(
            "https://www.apec.fr/cms/webservices/rechercheoffre/ids",
            json=payload, headers={**HEADERS, "Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            return jobs
        data = resp.json()
        ids = data.get("listeIdentifiantsOffres", [])[:6]

        for oid in ids:
            try:
                det = await client.get(
                    f"https://www.apec.fr/cms/webservices/rechercheoffre/detail?numeroOffre={oid}",
                    headers=HEADERS, timeout=10,
                )
                if det.status_code != 200:
                    continue
                d = det.json()
                title = d.get("intitule", "")
                company = d.get("nomSociete", "Entreprise")
                location = d.get("lieuTravail", {}).get("libelle", "France")
                desc = clean(re.sub(r'<[^>]+>', ' ', d.get("texteHtml", "")), 400)
                if title and is_relevant(title, desc):
                    jobs.append({
                        "title": title, "company": company, "location": location,
                        "type": job_type, "platform": "Apec",
                        "url": f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/{oid}",
                        "description": desc, "tags": extract_tags(title + " " + desc),
                        "posted_days_ago": 0,
                    })
                await asyncio.sleep(0.4)
            except:
                pass
    except Exception as e:
        print(f"Apec error: {e}")
    return jobs

# ══════════════════════════════════════════════
#  IA — GROQ
# ══════════════════════════════════════════════

async def call_groq(client: httpx.AsyncClient, prompt: str) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000, "temperature": 0.6,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq error: {e}")
    return None

# ══════════════════════════════════════════════
#  IA — GEMINI
# ══════════════════════════════════════════════

async def call_gemini(client: httpx.AsyncClient, prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.6},
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini error: {e}")
    return None

async def call_ai(client: httpx.AsyncClient, prompt: str) -> tuple[Optional[str], str]:
    result = await call_groq(client, prompt)
    if result:
        return result, "Groq llama3-70b"
    result = await call_gemini(client, prompt)
    if result:
        return result, "Gemini 1.5 Flash"
    return None, ""

async def enrich_jobs(client: httpx.AsyncClient, jobs: list[dict]) -> list[dict]:
    """Enrichit les descriptions courtes via IA."""
    to_enrich = [j for j in jobs if len(j.get("description", "")) < 60][:10]
    if not to_enrich:
        return jobs

    listing = "\n".join(
        f'{i+1}. "{j["title"]}" chez {j["company"]} ({j["location"]}) — {j["type"]}'
        for i, j in enumerate(to_enrich)
    )

    prompt = f"""Tu es un expert RH en France spécialisé dans les métiers 3D/Graphics/GameDev.

Pour ces offres de {len(to_enrich)} stages/alternances, génère une description professionnelle 
de 2-3 phrases chacune (mission, technologies utilisées, profil recherché).

Offres:
{listing}

Réponds UNIQUEMENT en JSON valide, sans texte avant/après, sans markdown:
[
  {{"index": 1, "description": "...", "tags": ["C++", "OpenGL", "Rendering"]}},
  ...
]"""

    response, ai_name = await call_ai(client, prompt)
    if not response:
        return jobs

    try:
        raw = re.sub(r'```json|```', '', response).strip()
        start, end = raw.find('['), raw.rfind(']') + 1
        enriched = json.loads(raw[start:end])
        print(f"  🤖 {ai_name} → {len(enriched)} descriptions enrichies")
        for item in enriched:
            idx = item.get("index", 0) - 1
            if 0 <= idx < len(to_enrich):
                orig = to_enrich[idx]
                orig["description"] = item.get("description", orig.get("description", ""))
                if item.get("tags"):
                    existing = set(orig.get("tags", []))
                    orig["tags"] = list(existing | set(item["tags"]))[:7]
    except Exception as e:
        print(f"  ⚠ Enrichissement échoué: {e}")
    return jobs

async def generate_ai_jobs(client: httpx.AsyncClient, count: int = 10) -> list[dict]:
    """Génère des offres supplémentaires via IA si le scraping est insuffisant."""
    prompt = f"""Génère {count} offres de stages/alternances RÉALISTES en France (date: {datetime.now().strftime('%d/%m/%Y')}).
Domaines: 3D, Rendering, OpenGL, Vulkan, Unreal Engine, Unity, VR/AR, Computer Graphics, Shader, WebGL, Blender, VFX.
Entreprises variées: studios jeux (Ubisoft, Arkane, Focus, Playground), boîtes VR/AR, ESN, Airbus, Renault, Thales, 
studios VFX, startups deep tech, médical, automobile.
Villes: Paris, Lyon, Bordeaux, Nantes, Grenoble, Toulouse, Sophia-Antipolis, Montpellier, Rennes, Remote.

Réponds UNIQUEMENT en JSON valide:
{{"jobs": [
  {{
    "title": "Stage Développeur Rendering C++/Vulkan",
    "company": "Ubisoft Paris",
    "location": "Montreuil (93)",
    "type": "stage",
    "duration": "6 mois",
    "platform": "LinkedIn",
    "url": "https://www.linkedin.com/jobs/search/?keywords=stage+rendering+vulkan",
    "description": "Rejoins l'équipe Rendering pour développer les fonctionnalités graphiques de nos titres AAA. Tu travailleras sur la pipeline Vulkan, l'optimisation GPU et les shaders GLSL/HLSL.",
    "tags": ["C++", "Vulkan", "GLSL", "Rendering", "GPU"],
    "posted_days_ago": 1
  }}
]}}"""

    response, ai_name = await call_ai(client, prompt)
    if not response:
        return []
    try:
        raw = re.sub(r'```json|```', '', response).strip()
        start, end = raw.find('{'), raw.rfind('}') + 1
        data = json.loads(raw[start:end])
        jobs = data.get("jobs", [])
        print(f"  🤖 {ai_name} → {len(jobs)} offres IA générées")
        return jobs
    except Exception as e:
        print(f"  ⚠ Génération IA échouée: {e}")
        return []

# ══════════════════════════════════════════════
#  SCAN PRINCIPAL
# ══════════════════════════════════════════════

async def run_scan():
    print(f"\n{'═'*55}")
    print(f"  🔍 SCAN — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'═'*55}")

    db = load_db()
    add_log(db, "info", f"Scan démarré — {datetime.now().strftime('%H:%M:%S')}")

    all_jobs = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=5),
    ) as client:

        # ── Scraping en parallèle (par lots) ──
        scrapers_map = {
            "Indeed": scrape_indeed,
            "WTTJ": scrape_wttj,
            "HelloWork": scrape_hellowork,
            "LinkedIn": scrape_linkedin,
            "Apec": scrape_apec,
        }

        for query, job_type in SEARCH_QUERIES:
            print(f"\n  📌 Query: \"{query}\" [{job_type}]")
            tasks = [
                fn(client, query, job_type)
                for fn in scrapers_map.values()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_jobs.extend(r)
            await asyncio.sleep(2)

        print(f"\n  📦 {len(all_jobs)} offres scrapées brutes")
        add_log(db, "info", f"Scraping terminé : {len(all_jobs)} offres brutes")

        # ── Déduplication préliminaire ──
        seen_titles = set()
        unique_jobs = []
        for j in all_jobs:
            key = f"{j['title'].lower()[:40]}|{j['company'].lower()[:20]}"
            if key not in seen_titles:
                seen_titles.add(key)
                unique_jobs.append(j)
        print(f"  🔁 {len(unique_jobs)} offres après déduplication")

        # ── Enrichissement IA ──
        has_ai = bool(GROQ_API_KEY or GEMINI_API_KEY)
        if has_ai:
            print(f"\n  🤖 Enrichissement IA des descriptions...")
            unique_jobs = await enrich_jobs(client, unique_jobs)

        # ── Compléter avec IA si peu de résultats ──
        if len(unique_jobs) < 8 and has_ai:
            needed = max(8, 15 - len(unique_jobs))
            print(f"\n  ⚠ Peu d'offres scrapées ({len(unique_jobs)}), génération IA ({needed} offres)...")
            ai_jobs = await generate_ai_jobs(client, needed)
            unique_jobs.extend(ai_jobs)
            add_log(db, "info", f"IA a généré {len(ai_jobs)} offres supplémentaires")

        # ── Sauvegarde en base ──
        existing_ids = {j["id"] for j in db["jobs"]}
        timestamp = datetime.now().isoformat()
        added = 0

        for job in unique_jobs:
            uid = make_id(job.get("platform", ""), job.get("company", ""), job.get("title", ""))
            job["id"] = uid
            if uid not in existing_ids:
                job["scanned_at"] = timestamp
                job["is_new"] = True
                job.setdefault("duration", "À préciser")
                db["jobs"].append(job)
                existing_ids.add(uid)
                added += 1

        # Marquer les anciennes
        for j in db["jobs"]:
            if j.get("scanned_at") != timestamp:
                j["is_new"] = False

        db["scan_count"] += 1
        db["last_scan"] = timestamp
        # Garder les 1000 plus récentes
        db["jobs"] = sorted(
            db["jobs"],
            key=lambda x: x.get("scanned_at", ""),
            reverse=True
        )[:1000]

        add_log(db, "success", f"Scan #{db['scan_count']} terminé — {added} nouvelles offres (total: {len(db['jobs'])})")
        save_db(db)

        print(f"\n  ✅ {added} nouvelles offres ajoutées (total: {len(db['jobs'])})")
        print(f"{'═'*55}\n")
        return added

# ══════════════════════════════════════════════
#  FASTAPI APP
# ══════════════════════════════════════════════

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage
    print("🚀 JobsRadar 3D Backend — Démarrage")
    interval_hours = 24 / SCANS_PER_DAY
    scheduler.add_job(run_scan, "interval", hours=interval_hours, id="auto_scan")
    scheduler.start()
    print(f"⏰ Scans automatiques toutes les {interval_hours:.0f}h")
    # Scan initial si base vide
    db = load_db()
    if not db["jobs"]:
        asyncio.create_task(run_scan())
    yield
    # Arrêt
    scheduler.shutdown()

app = FastAPI(
    title="JobsRadar 3D API",
    description="Backend de veille automatique des offres 3D/Graphics/GameDev en France",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    db = load_db()
    return {
        "status": "running",
        "jobs": len(db["jobs"]),
        "scan_count": db["scan_count"],
        "last_scan": db["last_scan"],
        "ai": {"groq": bool(GROQ_API_KEY), "gemini": bool(GEMINI_API_KEY)},
    }

@app.get("/api/jobs")
async def get_jobs(
    type: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    db = load_db()
    jobs = db["jobs"]

    if type and type != "all":
        jobs = [j for j in jobs if j.get("type") == type]
    if platform and platform != "all":
        jobs = [j for j in jobs if j.get("platform") == platform]
    if q:
        ql = q.lower()
        jobs = [j for j in jobs if ql in (j.get("title","") + " " + j.get("company","") + " " + " ".join(j.get("tags",[]))).lower()]

    total = len(jobs)
    jobs = jobs[offset:offset+limit]

    return {
        "jobs": jobs,
        "total": total,
        "scan_count": db["scan_count"],
        "last_scan": db["last_scan"],
        "offset": offset,
        "limit": limit,
    }

@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan)
    return {"status": "scan_started", "message": "Scan lancé en arrière-plan"}

@app.get("/api/logs")
async def get_logs(limit: int = Query(50, le=200)):
    db = load_db()
    logs = db.get("logs", [])
    return {"logs": logs[-limit:]}

@app.get("/api/stats")
async def get_stats():
    db = load_db()
    jobs = db["jobs"]
    by_platform = {}
    by_type = {}
    for j in jobs:
        p = j.get("platform", "Inconnu")
        t = j.get("type", "Inconnu")
        by_platform[p] = by_platform.get(p, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "total": len(jobs),
        "new": sum(1 for j in jobs if j.get("is_new")),
        "scan_count": db["scan_count"],
        "last_scan": db["last_scan"],
        "by_platform": by_platform,
        "by_type": by_type,
        "ai_enabled": bool(GROQ_API_KEY or GEMINI_API_KEY),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)

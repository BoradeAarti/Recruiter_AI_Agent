"""
GroqRecruit - Fixed Backend
Run: python backend.py
Then open: http://127.0.0.1:5000   (NOT file://)
"""

import os
import re
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# ── Load .env BEFORE any other imports that might need env vars
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from groq import Groq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

BASE_DIR     = str(Path(__file__).parent)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
MODEL        = "llama-3.3-70b-versatile"

# ── Flask app
app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

# ── CORS: allow everything (file://, localhost, 127.0.0.1)
CORS(app, origins="*", supports_credentials=False)

@app.after_request
def cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

@app.route("/api/<path:p>", methods=["OPTIONS"])
def preflight(p):
    return Response(status=204)

# ── Groq client
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    log.info(f"✅  Groq key: {GROQ_API_KEY[:14]}...")
else:
    log.warning("⚠️   GROQ_API_KEY missing — check your .env file")


# ════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════

def safe_json(text: str):
    """Extract JSON from Groq response, stripping markdown fences."""
    t = text.strip()
    # strip ```json ... ``` or ``` ... ```
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$",       "", t)
    t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        # find first { ... } or [ ... ]
        for pat in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
            m = re.search(pat, t)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
    raise ValueError(f"JSON parse failed. Raw start: {t[:200]}")


def groq(messages: list, temp=0.2, tokens=2048) -> str:
    r = groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temp,
        max_tokens=tokens,
    )
    return r.choices[0].message.content.strip()


# ════════════════════════════════════════════════
#  PIPELINE
# ════════════════════════════════════════════════

def step1_parse_jd(jd: str) -> dict:
    log.info("▶  Step 1: parsing JD")
    raw = groq([{
        "role": "user",
        "content": (
            "You are an expert technical recruiter. "
            "Parse the job description below. "
            "Reply with ONLY a JSON object — no markdown, no explanation.\n\n"
            f"JD:\n{jd}\n\n"
            "JSON shape:\n"
            '{"role_title":"","seniority":"Senior","required_skills":[],'
            '"preferred_skills":[],"min_years_experience":5,'
            '"education_requirement":"","industry_domain":"",'
            '"key_responsibilities":[],"nice_to_have":[]}'
        )
    }], temp=0.1, tokens=1024)
    return safe_json(raw)


def step2_generate_candidates(jd_parsed: dict, location: str, n: int) -> list:
    log.info(f"▶  Step 2: generating {n} candidates for {location}")
    role   = jd_parsed.get("role_title", "Software Engineer")
    skills = ", ".join(jd_parsed.get("required_skills", [])[:5])
    yoe    = jd_parsed.get("min_years_experience", 5)
    senior = jd_parsed.get("seniority", "Senior")
    domain = jd_parsed.get("industry_domain", "Tech")

    raw = groq([
        {
            "role": "system",
            "content": (
                "You are a senior technical recruiter with 15 years experience. "
                "You know the exact talent landscape in Indian and Gulf cities — "
                "which companies hire, which colleges produce what talent, realistic salaries. "
                "Generate DIVERSE profiles: top-tier and mid-tier companies, IIT and tier-2 colleges. "
                "Return ONLY a valid JSON array. No markdown. No explanation."
            )
        },
        {
            "role": "user",
            "content": (
                f"Generate exactly {n} realistic LinkedIn profiles.\n\n"
                f"ROLE: {senior} {role}\n"
                f"LOCATION: {location}\n"
                f"KEY SKILLS: {skills}\n"
                f"MIN EXPERIENCE: {yoe} years\n"
                f"DOMAIN: {domain}\n\n"
                "Rules:\n"
                f"- Use realistic names for {location}\n"
                "- Mix: 2 top-tier cos, 2 mid-tier, 1 junior/overqualified\n"
                "- Varied YOE around the minimum\n"
                "- Real-looking linkedin.com/in/name-hash URLs\n\n"
                "Return JSON array:\n"
                "[\n"
                "  {\n"
                '    "name": "Full Name",\n'
                '    "linkedin_url": "https://linkedin.com/in/name-abc123",\n'
                '    "current_title": "Job Title",\n'
                '    "current_company": "Company",\n'
                f'    "location": "{location}",\n'
                '    "years_experience": 7,\n'
                '    "education": {"degree": "B.Tech CS", "college": "IIT Bombay", "graduation_year": 2018},\n'
                '    "skills": ["skill1", "skill2"],\n'
                '    "past_companies": ["Co A (2yrs)", "Co B (3yrs)"],\n'
                '    "notable_achievements": ["achievement 1"],\n'
                '    "open_to_work": false,\n'
                '    "certifications": ["AWS SA"],\n'
                '    "summary": "Short 2-sentence LinkedIn summary."\n'
                "  }\n"
                "]\n"
                f"Give exactly {n} objects."
            )
        }
    ], temp=0.85, tokens=4000)

    result = safe_json(raw)
    if not isinstance(result, list):
        raise ValueError("Expected JSON array from candidate generation")
    return result[:n]


def step3_score(candidate: dict, jd_parsed: dict, location: str) -> dict:
    name = candidate.get("name", "?")
    log.info(f"   Scoring {name}")

    raw = groq([
        {
            "role": "system",
            "content": (
                "You are a rigorous recruiter. Score honestly — vary scores, "
                "penalise missing skills, reward strong fits. "
                "Return ONLY valid JSON. No markdown."
            )
        },
        {
            "role": "user",
            "content": (
                "Score this candidate against the job requirements.\n\n"
                f"JOB:\n{json.dumps(jd_parsed)}\n\n"
                f"LOCATION: {location}\n\n"
                f"CANDIDATE:\n{json.dumps(candidate)}\n\n"
                "Return ONLY this JSON (integers 0-100):\n"
                "{\n"
                '  "technical_score": 0,\n'
                '  "experience_score": 0,\n'
                '  "education_score": 0,\n'
                '  "culture_score": 0,\n'
                '  "location_score": 0,\n'
                '  "overall_score": 0,\n'
                '  "recommendation": "STRONG HIRE",\n'
                '  "key_skills_matched": [],\n'
                '  "missing_skills": [],\n'
                '  "strengths": [],\n'
                '  "gaps": [],\n'
                '  "seniority_match": "Good match",\n'
                '  "interview_questions": ["Q1?", "Q2?", "Q3?"],\n'
                '  "outreach_message": "Hi Name, ...",\n'
                '  "reasoning": "2-3 sentences."\n'
                "}\n"
                'recommendation must be one of: "STRONG HIRE", "HIRE", "CONSIDER", "PASS"'
            )
        }
    ], temp=0.15, tokens=900)

    return safe_json(raw)


# ════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════

@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "ok":    True,
        "groq":  bool(GROQ_API_KEY),
        "model": MODEL,
        "key_prefix": GROQ_API_KEY[:14] + "..." if GROQ_API_KEY else "missing"
    })


@app.route("/api/search", methods=["POST"])
def api_search():
    # ── guard
    if not groq_client:
        return jsonify({"error": "GROQ_API_KEY not set. Check .env file."}), 500

    body      = request.get_json(force=True, silent=True) or {}
    jd_text   = (body.get("jd_text") or "").strip()
    location  = (body.get("location") or "").strip()
    num_leads = max(1, min(int(body.get("num_leads") or 5), 15))

    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400
    if not location:
        return jsonify({"error": "location is required"}), 400

    log.info(f"=== New search: {location}, {num_leads} leads ===")

    try:
        # 1 — parse
        jd_parsed = step1_parse_jd(jd_text)
        log.info(f"    Role: {jd_parsed.get('role_title')} | Skills: {jd_parsed.get('required_skills')}")

        # 2 — generate
        candidates = step2_generate_candidates(jd_parsed, location, num_leads)
        log.info(f"    Generated {len(candidates)} candidates")

        # 3 — score
        cards = []
        for i, cand in enumerate(candidates):
            try:
                sc = step3_score(cand, jd_parsed, location)
            except Exception as e:
                log.warning(f"    Score failed for {cand.get('name')}: {e}")
                sc = {
                    "overall_score": 50, "recommendation": "CONSIDER",
                    "technical_score": 50, "experience_score": 50,
                    "education_score": 50, "culture_score": 50, "location_score": 80,
                    "key_skills_matched": [], "missing_skills": [],
                    "strengths": [], "gaps": ["Could not score automatically"],
                    "seniority_match": "Unknown",
                    "interview_questions": [], "outreach_message": "",
                    "reasoning": "Automated scoring failed — please review manually."
                }
            cards.append({
                "rank":                i + 1,
                "name":                cand.get("name", "Unknown"),
                "linkedin_url":        cand.get("linkedin_url", ""),
                "current_title":       cand.get("current_title", ""),
                "current_company":     cand.get("current_company", ""),
                "location":            cand.get("location", location),
                "years_experience":    cand.get("years_experience", 0),
                "education":           cand.get("education", {}),
                "skills":              cand.get("skills", []),
                "past_companies":      cand.get("past_companies", []),
                "notable_achievements":cand.get("notable_achievements", []),
                "certifications":      cand.get("certifications", []),
                "open_to_work":        cand.get("open_to_work", False),
                "summary":             cand.get("summary", ""),
                "scores":              sc,
            })
            time.sleep(0.15)

        # sort by overall
        cards.sort(key=lambda x: x["scores"].get("overall_score", 0), reverse=True)
        for i, c in enumerate(cards):
            c["rank"] = i + 1

        # build helper URLs
        role_q  = jd_parsed.get("role_title", "").replace(" ", "%20")
        sk      = jd_parsed.get("required_skills", [])
        sk_q    = "%20".join(s.replace(" ", "%20") for s in sk[:2])
        li_url  = f"https://www.linkedin.com/search/results/people/?keywords={role_q}%20{sk_q}&origin=FACETED_SEARCH"

        sk_bool = " OR ".join(f'"{s}"' for s in sk[:3])
        g_dork  = f'site:linkedin.com/in "{jd_parsed.get("role_title","")}" ({sk_bool}) "{location}"'

        log.info(f"=== Done. {len(cards)} cards returned ===")
        return jsonify({
            "status":              "ok",
            "location":            location,
            "parsed_jd":           jd_parsed,
            "total":               len(cards),
            "scorecards":          cards,
            "linkedin_search_url": li_url,
            "google_dork":         g_dork,
            "generated_at":        datetime.utcnow().isoformat(),
        })

    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "═"*52)
    print("  GroqRecruit")
    print("═"*52)
    if GROQ_API_KEY:
        print(f"  ✅  Groq key  : {GROQ_API_KEY[:14]}...")
    else:
        print("  ❌  GROQ_API_KEY missing — check .env")
    print(f"  📁  Serving    : {BASE_DIR}")
    print(f"  🌐  Open this  : http://127.0.0.1:5000")
    print("═"*52 + "\n")
    # use_reloader=False avoids double-loading .env on Windows
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)

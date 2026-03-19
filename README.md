# GroqRecruit — AI LinkedIn Sourcer

> Paste a JD → set location & lead count → get scored candidate cards instantly.

Powered by **Groq** (llama-3.3-70b) for JD parsing & AI scoring, **SerpApi** for live LinkedIn search, and **Proxycurl** for deep profile enrichment.

---

## Quick Start (5 minutes)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
cp .env.example .env
# Edit .env and add your keys (see below)
```

### 3. Run the server
```bash
python backend.py
```

### 4. Open the app
```
http://localhost:5000
```

---

## API Keys

| Service | Free Tier | Get Key |
|---------|-----------|---------|
| **Groq** (required) | Very generous — fast LLaMA-3.3-70b | [console.groq.com](https://console.groq.com) |
| **SerpApi** (recommended) | 100 searches/month free | [serpapi.com](https://serpapi.com) |
| **Proxycurl** (optional) | Pay-per-use ~$0.01/profile | [nubela.co/proxycurl](https://nubela.co/proxycurl) |

> **No SerpApi / Proxycurl key?** App runs in **demo mode** with realistic mock LinkedIn profiles — perfect for testing the UI and Groq scoring.

---

## How It Works

```
JD Text
  │
  ▼
[Groq] Parse JD → extract role, skills, seniority, boolean query
  │
  ▼
[SerpApi] Google site:linkedin.com search → raw profile list
  │
  ▼
[Proxycurl] Enrich each profile → headline, experience, skills (optional)
  │
  ▼
[Groq] Score each candidate → 4 dimension scores + recommendation
  │
  ▼
Ranked Fit Score Cards
```

---

## Scorecard Dimensions

| Dimension | What it measures |
|-----------|-----------------|
| **Technical** | Skills match against JD requirements |
| **Experience** | Years + relevance of past roles |
| **Education** | Degree fit for the role |
| **Location fit** | Proximity to target location |
| **Overall** | Weighted composite |

### Recommendations
- `STRONG HIRE` — Excellent match, reach out immediately
- `HIRE` — Good match, worth a screening call
- `CONSIDER` — Partial match, has gaps but potential
- `PASS` — Significant mismatch

---

## API Endpoints

### `POST /api/parse-jd`
Parse a JD without running search.
```json
{ "jd_text": "..." }
```

### `POST /api/search`
Full pipeline — parse JD, search LinkedIn, score candidates.
```json
{
  "jd_text":   "...",
  "location":  "Hyderabad",
  "num_leads": 5
}
```

### `GET /api/health`
Check which API keys are configured.

---

## Customisation

**Change the model** (backend.py line ~45):
```python
model="llama-3.3-70b-versatile"   # fastest, best quality
model="llama-3.1-8b-instant"      # ultra-fast, lighter scoring
model="mixtral-8x7b-32768"        # longer context window
```

**Add more search sources**: extend `search_linkedin_profiles()` to also query GitHub (`site:github.com`), AngelList, or Wellfound.

**Export scorecards**: add a `GET /api/export` route that returns CSV/JSON of the last search results.

---

## Architecture

```
recruiter/
├── backend.py        ← Flask API + Groq + SerpApi + Proxycurl
├── index.html        ← Full-stack dark UI (no build step)
├── requirements.txt
├── .env.example      ← Copy to .env and add keys
└── README.md
```

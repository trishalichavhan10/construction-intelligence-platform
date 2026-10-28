"""Multimodal Construction Intelligence Platform (Skill Wallet Capstone Project 1)."""
import json
import re
import urllib.parse

import streamlit as st
from PIL import Image

st.set_page_config(page_title="Construction Intelligence Platform", page_icon="🏗️", layout="wide")

st.markdown(
    """
    <style>
    .pill {display:inline-block;padding:4px 14px;border-radius:999px;font-weight:600;color:#fff;}
    .ok {background:#2e9d5b;} .warn {background:#e0a100;} .bad {background:#d64545;}
    .card {border:1px solid #e3e6ea;border-radius:12px;padding:14px 18px;background:#fafbfc;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# AI layer (Epic 4): Gemini multimodal calls with strict JSON contracts + demo fallback
# --------------------------------------------------------------------------
DEFAULT_MODEL = "gemini-2.5-flash"


def get_api_key() -> str:
    key = st.session_state.get("api_key", "").strip()
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def ask_gemini(prompt: str, image: Image.Image | None = None, as_json: bool = True):
    """Returns parsed JSON (or text). Raises on failure so callers can fall back."""
    from google import genai

    client = genai.Client(api_key=get_api_key())
    contents = [prompt] + ([image] if image is not None else [])
    config = {"response_mime_type": "application/json"} if as_json else None
    resp = client.models.generate_content(
        model=st.session_state.get("model", DEFAULT_MODEL), contents=contents, config=config
    )
    return parse_json(resp.text) if as_json else resp.text


SAFETY_PROMPT = """You are a construction site safety inspector (OSHA and IS 456 aware).
Analyse the photo. Respond ONLY with JSON in this exact schema:
{"safety_score": int 0-100, "overall_status": "Safe|Needs Attention|Unsafe",
 "ppe_detection": {"helmet": bool, "high_vis_vest": bool, "safety_boots": bool, "safety_harness": bool},
 "hazards": [{"hazard": str, "severity": "Low|Medium|High|Critical", "remedy": str}],
 "summary": str}
If no workers are visible, set PPE values to false and mention it in summary."""

CRACK_PROMPT = """You are a structural engineer. Analyse the concrete/wall surface photo.
Respond ONLY with JSON in this exact schema:
{"defect_type": "Hairline|Settlement|Structural Shear|Thermal Expansion|Spalling",
 "estimated_width_mm": float, "severity_score": int 0-100,
 "root_causes": [str], "recommended_repairs": [str],
 "urgency": "Monitor|Repair Soon|Immediate Action", "summary": str}"""

DEMO_SAFETY = {
    "safety_score": 62, "overall_status": "Needs Attention",
    "ppe_detection": {"helmet": True, "high_vis_vest": True, "safety_boots": False, "safety_harness": False},
    "hazards": [
        {"hazard": "Worker at height without harness", "severity": "Critical",
         "remedy": "Stop work at height until full-body harness is anchored."},
        {"hazard": "Loose materials near edge", "severity": "Medium",
         "remedy": "Install toe boards and stack materials away from edges."},
    ],
    "summary": "DEMO MODE: sample output. Add a Gemini API key for real image analysis.",
}
DEMO_CRACK = {
    "defect_type": "Settlement", "estimated_width_mm": 2.5, "severity_score": 58,
    "root_causes": ["Differential foundation settlement", "Poor soil compaction"],
    "recommended_repairs": ["Epoxy injection", "Structural re-grouting", "Crack monitoring gauges"],
    "urgency": "Repair Soon",
    "summary": "DEMO MODE: sample output. Add a Gemini API key for real image analysis.",
}


def run_analysis(prompt, image, demo):
    if get_api_key():
        try:
            return ask_gemini(prompt, image), False
        except Exception as e:  # network / quota / bad key / bad JSON
            st.warning(f"AI call failed ({type(e).__name__}); showing demo output instead.")
    return demo, True


def status_pill(text: str) -> str:
    t = text.lower()
    cls = "ok" if t in ("safe", "monitor") else "warn" if t in ("needs attention", "repair soon") else "bad"
    return f'<span class="pill {cls}">{text}</span>'


# --------------------------------------------------------------------------
# Planning & valuation (Epic 3)
# --------------------------------------------------------------------------
BUILD_RATE = {"Residential House": 1800, "Apartment Building": 2300,
              "Commercial Complex": 2600, "Industrial Shed": 1500}   # INR / sqft construction cost
MARKET_RATE = {"Residential House": 6000, "Apartment Building": 7500,
               "Commercial Complex": 9500, "Industrial Shed": 4000}  # INR / sqft finished value
TIER_COST = {"Tier 1": 1.25, "Tier 2": 1.0, "Tier 3": 0.85}
TIER_VALUE = {"Tier 1": 1.8, "Tier 2": 1.0, "Tier 3": 0.6}


def inr(amount: float) -> str:
    if amount >= 1e7:
        return f"₹{amount / 1e7:.2f} Cr"
    return f"₹{amount / 1e5:.2f} Lakh"


def plan_project(structure, sqft, tier, pct):
    budget = BUILD_RATE[structure] * sqft * TIER_COST[tier]
    full_value = MARKET_RATE[structure] * sqft * TIER_VALUE[tier]
    return {
        "budget": budget,
        "spent": budget * pct / 100,
        "valuation": full_value * (0.30 + 0.70 * pct / 100),  # land/approvals baseline + built value
        "steel_kg": sqft * 4.0,        # rule-of-thumb estimates
        "cement_bags": sqft * 0.4,
    }


# --------------------------------------------------------------------------
# Weather advisory + assistant (Epic 5)
# --------------------------------------------------------------------------
WEATHER_ADVISORY = {
    "High Wind": ["Suspend crane and hoisting operations above safe wind limits.",
                  "Secure scaffolding, sheeting and loose materials.",
                  "Halt work at height and on exposed edges."],
    "Heavy Rain": ["Cover fresh concrete; pause pours if rain is imminent.",
                   "De-energise and protect temporary electrical connections (shock hazard).",
                   "Pump out excavations and check trench shoring."],
    "Extreme Heat": ["Schedule heavy work early morning; enforce hydration breaks.",
                     "Start wet curing early and keep concrete surfaces moist.",
                     "Watch workers for heat-stress symptoms."],
    "Normal": ["Proceed with the planned schedule and run the daily toolbox talk.",
               "Complete routine PPE and equipment checks."],
}

CHAT_SYSTEM = ("You are a concise, practical construction engineering assistant for Indian sites. "
               "Reference IS codes and OSHA where relevant. Keep answers under 150 words.")

DEMO_CHAT = {
    "curing": "Keep concrete moist for at least 7 days (10+ for blended cements). Use wet burlap or ponding.",
    "crack": "Measure width. Hairline cracks (<0.3 mm) usually need sealing and monitoring; wider ones need an engineer.",
    "safety": "Daily checklist: helmets, vests, boots, harnesses at height, guarded edges, tidy materials.",
    "cost": "Use the Planning tab: cost = rate x sqft x city-tier multiplier. Add 10% contingency.",
}


def chat_reply(history):
    if get_api_key():
        try:
            convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
            return ask_gemini(f"{CHAT_SYSTEM}\n\n{convo}\nassistant:", as_json=False)
        except Exception as e:
            st.warning(f"AI call failed ({type(e).__name__}); using demo answers.")
    q = history[-1]["content"].lower()
    for k, v in DEMO_CHAT.items():
        if k in q:
            return "(Demo mode) " + v
    return "(Demo mode) Add a Gemini API key in the sidebar for full answers. Try asking about curing, cracks, safety or cost."


# --------------------------------------------------------------------------
# UI (Epic 6)
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("🏗️ Construction AI")
    st.text_input("Gemini API key", type="password", key="api_key",
                  help="Optional. Without a key the app runs in demo mode.")
    st.text_input("Model", value=DEFAULT_MODEL, key="model")
    st.success("AI mode: live" if get_api_key() else "Demo mode (no API key)")
    st.markdown("**Architecture**\n\n"
                "1. Streamlit UI\n2. Gemini multimodal analysis\n3. Strict JSON contracts\n"
                "4. Rule-based planning & valuation\n5. Weather advisory + chatbot")

st.title("Multimodal Construction Intelligence Platform")
st.caption("Site safety, crack diagnostics, planning & valuation, and a daily site assistant.")

tab1, tab2, tab3, tab4 = st.tabs(["🦺 Safety & PPE", "🧱 Crack Diagnostics", "📐 Planning & Valuation", "🌦️ Site Assistant"])

with tab1:
    up = st.file_uploader("Upload a construction site photo", type=["jpg", "jpeg", "png"], key="safety_up")
    if up:
        img = Image.open(up).convert("RGB")
        st.image(img, width=420)
        if st.button("Run safety audit", key="safety_btn"):
            with st.spinner("Analysing site..."):
                res, _ = run_analysis(SAFETY_PROMPT, img, DEMO_SAFETY)
            c1, c2 = st.columns(2)
            c1.metric("Safety score", f"{res.get('safety_score', 0)}/100")
            c2.markdown(status_pill(res.get("overall_status", "Unknown")), unsafe_allow_html=True)
            st.subheader("PPE checklist")
            for k, v in res.get("ppe_detection", {}).items():
                st.write(("✅ " if v else "❌ ") + k.replace("_", " ").title())
            st.subheader("Hazards")
            for h in res.get("hazards", []):
                st.markdown(f"{status_pill(h['severity'])} **{h['hazard']}** — {h['remedy']}", unsafe_allow_html=True)
            st.info(res.get("summary", ""))
            st.download_button("Download JSON report", json.dumps(res, indent=2), "safety_report.json")
    else:
        st.info("Upload a JPG/PNG to begin.")

with tab2:
    up = st.file_uploader("Upload a concrete or wall surface photo", type=["jpg", "jpeg", "png"], key="crack_up")
    if up:
        img = Image.open(up).convert("RGB")
        st.image(img, width=420)
        if st.button("Diagnose defect", key="crack_btn"):
            with st.spinner("Analysing surface..."):
                res, _ = run_analysis(CRACK_PROMPT, img, DEMO_CRACK)
            c1, c2, c3 = st.columns(3)
            c1.metric("Defect type", res.get("defect_type", "?"))
            c2.metric("Est. width", f"{res.get('estimated_width_mm', 0)} mm")
            c3.metric("Severity", f"{res.get('severity_score', 0)}/100")
            st.markdown("Urgency: " + status_pill(res.get("urgency", "Monitor")), unsafe_allow_html=True)
            st.subheader("Root causes")
            for r in res.get("root_causes", []):
                st.write("•", r)
            st.subheader("Recommended repairs")
            for r in res.get("recommended_repairs", []):
                st.write("•", r)
            st.info(res.get("summary", ""))
            st.download_button("Download JSON report", json.dumps(res, indent=2), "crack_report.json")
    else:
        st.info("Upload a JPG/PNG to begin.")

with tab3:
    c1, c2 = st.columns(2)
    structure = c1.selectbox("Structure type", list(BUILD_RATE))
    tier = c2.selectbox("Location tier", list(TIER_COST), help="Tier 1: metros, Tier 2: large cities, Tier 3: smaller towns")
    sqft = c1.number_input("Built-up area (sqft)", min_value=100, max_value=1_000_000, value=2000, step=100)
    pct = c2.slider("Completion %", 0, 100, 40)
    p = plan_project(structure, sqft, tier, pct)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total project budget", inr(p["budget"]))
    m2.metric("Capital spent", inr(p["spent"]))
    m3.metric("Current asset valuation", inr(p["valuation"]))
    st.progress(pct / 100, text=f"Milestone progress: {pct}%")
    n1, n2 = st.columns(2)
    n1.metric("Steel needed (est.)", f"{p['steel_kg'] / 1000:.1f} tonnes")
    n2.metric("Cement needed (est.)", f"{p['cement_bags']:.0f} bags")
    st.caption("Estimates use simple rule-of-thumb rates for planning only, not a quotation.")
    st.subheader("Conceptual architectural rendering")
    style = st.text_input("Rendering prompt", f"modern {structure.lower()}, architectural visualization, daylight")
    if st.button("Generate rendering"):
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(style)
        st.image(url, caption="Generated via Pollinations AI", use_container_width=True)

with tab4:
    weather = st.selectbox("Today's weather", list(WEATHER_ADVISORY), index=3)
    box = st.warning if weather != "Normal" else st.success
    box(f"**{weather} advisory**\n\n" + "\n".join(f"- {a}" for a in WEATHER_ADVISORY[weather]))
    st.subheader("Ask the site assistant")
    st.session_state.setdefault("messages", [])
    for m in st.session_state.messages:
        st.chat_message(m["role"]).write(m["content"])
    if q := st.chat_input("Ask about curing, safety, cracks, costs..."):
        st.session_state.messages.append({"role": "user", "content": q})
        st.chat_message("user").write(q)
        with st.chat_message("assistant"):
            ans = chat_reply(st.session_state.messages)
            st.write(ans)
        st.session_state.messages.append({"role": "assistant", "content": ans})

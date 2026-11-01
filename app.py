# app.py
# MediGuide PK - Streamlit Dashboard (3D healthcare style, all 4 tabs active)
# Run with: streamlit run app.py

import os
import time
import html
import streamlit as st
from groq import Groq
from pharmacist_agent import run_pharmacist_agent
from agent_tools import match_medicines_db, check_interactions, find_affordable_generics, med_db
from ai_helpers import ocr_image, transcribe_audio, explain_lab_report

# ------------------------------------------------------------------
# 1. PAGE CONFIG
# ------------------------------------------------------------------
st.set_page_config(
    page_title="MediGuide PK",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# 2. CUSTOM CSS
# ------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap');

.stApp {
    background:
        radial-gradient(circle at 15% 0%, rgba(37, 99, 235, 0.28) 0%, transparent 50%),
        radial-gradient(circle at 90% 10%, rgba(20, 184, 166, 0.18) 0%, transparent 45%),
        linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px) 0 0 / 40px 40px,
        linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px) 0 0 / 40px 40px,
        #0b1220;
    color: #e2e8f0;
    font-family: 'Inter', sans-serif;
}
header[data-testid="stHeader"] { background: transparent; }

section[data-testid="stSidebar"] {
    background: rgba(11, 18, 32, 0.9);
    backdrop-filter: blur(14px);
    border-right: 1px solid rgba(56, 189, 248, 0.25);
}

/* ---------------- HERO ---------------- */
.hero-wrap {
    display: flex; align-items: center; justify-content: space-between;
    gap: 2rem; padding: 1.2rem 0 0.4rem 0;
}
.hero-left { flex: 1 1 55%; min-width: 0; }
.hero-pill {
    display: inline-block; padding: 5px 14px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; color: #bae6fd;
    background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.4);
    margin-bottom: 0.8rem;
}
.hero-title {
    font-size: 3.4rem; font-weight: 800; line-height: 1.05; margin: 0;
    background: linear-gradient(90deg, #38bdf8, #2dd4bf);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-urdu {
    font-family: 'Noto Nastaliq Urdu', serif; font-size: 1.7rem;
    color: #bae6fd; direction: rtl; text-align: left; margin: 0.6rem 0 0.2rem 0;
}
.hero-sub { color: #94a3b8; font-size: 1.02rem; margin-bottom: 1.2rem; }

.stat-row { display: flex; flex-wrap: wrap; gap: 14px; }
.stat {
    min-width: 130px; padding: 12px 18px; border-radius: 16px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.stat b { display: block; font-size: 1.7rem; color: #f8fafc; }
.stat span { font-size: 0.78rem; color: #94a3b8; }

/* floating 3D icons */
.hero-icons {
    flex: 1 1 40%; display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 14px; justify-items: center; max-width: 380px;
}
.float {
    animation: floaty 5.5s ease-in-out infinite;
    filter: drop-shadow(0 16px 16px rgba(0, 0, 0, 0.5));
}
.hero-icons .float:nth-child(2) { animation-delay: -1.2s; margin-top: 22px; }
.hero-icons .float:nth-child(3) { animation-delay: -2.4s; }
.hero-icons .float:nth-child(4) { animation-delay: -3.1s; }
.hero-icons .float:nth-child(5) { animation-delay: -4.0s; margin-top: 22px; }
.hero-icons .float:nth-child(6) { animation-delay: -0.6s; }
@keyframes floaty {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-12px) rotate(2.5deg); }
}

/* feature cards (tilt on hover) */
.feature-row {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
    margin: 1.4rem 0 1.2rem 0; perspective: 900px;
}
.feature {
    padding: 16px; border-radius: 20px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.12);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    transform-style: preserve-3d;
}
.feature:hover {
    transform: rotateX(8deg) rotateY(-10deg) translateY(-6px);
    box-shadow: 0 22px 40px rgba(0, 0, 0, 0.55), 0 0 24px rgba(56, 189, 248, 0.25);
}
.feature svg { filter: drop-shadow(0 8px 8px rgba(0, 0, 0, 0.45)); }
.feature h4 { margin: 10px 0 2px 0; font-size: 1.02rem; color: #f1f5f9; }
.feature p { margin: 0; font-size: 0.82rem; color: #94a3b8; line-height: 1.4; }

@media (prefers-reduced-motion: reduce) {
    .float { animation: none; }
    .feature, .feature:hover { transition: none; transform: none; }
}
@media (max-width: 900px) {
    .hero-icons { display: none; }
    .hero-title { font-size: 2.4rem; }
    .feature-row { grid-template-columns: repeat(2, 1fr); }
}

/* ---------------- TABS ---------------- */
.stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: none; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab"] {
    background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px; padding: 12px 20px; color: #94a3b8; font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0284c7, #0d9488) !important;
    color: #ffffff !important; border-color: transparent !important;
    box-shadow: 0 6px 20px rgba(14, 165, 233, 0.45);
}

/* ---------------- CARDS ---------------- */
/* Input cards: dark glass */
[class*="st-key-input_"] {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 20px; padding: 1.4rem;
    backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 10px 34px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* Result cards: LIGHT, high contrast (easy to read Urdu) */
[class*="st-key-result_"], [class*="st-key-panel_"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 20px; padding: 1.4rem;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
}
.stApp [class*="st-key-result_"] *, .stApp [class*="st-key-panel_"] * { color: #0f172a; }
.stApp [class*="st-key-panel_"] [data-testid="stCaptionContainer"] * { color: #475569; }

/* Urdu report cards: right-to-left (panel_ cards stay left-to-right) */
[class*="st-key-result_"] {
    direction: rtl; text-align: right;
    font-family: 'Noto Nastaliq Urdu', 'Inter', serif; line-height: 2.2;
}
[class*="st-key-result_"] table { direction: rtl; border-collapse: collapse; width: 100%; }
[class*="st-key-result_"] th, [class*="st-key-result_"] td {
    border: 1px solid #cbd5e1; padding: 6px 10px;
}
[class*="st-key-result_"] th { background: #e0f2fe; }

/* Status cards (inside light panels) */
.status {
    unicode-bidi: plaintext; text-align: start;
    font-family: 'Noto Nastaliq Urdu', 'Inter', serif; line-height: 2;
    padding: 10px 16px; border-radius: 12px; margin: 8px 0;
    border-left: 6px solid; font-size: 0.98rem;
}
.stApp .status.ok   { background: #ecfdf5; border-color: #10b981; color: #065f46 !important; }
.stApp .status.warn { background: #fffbeb; border-color: #f59e0b; color: #92400e !important; }
.stApp .status.bad  { background: #fef2f2; border-color: #ef4444; color: #991b1b !important; }
.stApp .status.info { background: #eff6ff; border-color: #3b82f6; color: #1e40af !important; }

/* ---------------- INPUTS ---------------- */
.stTextArea textarea, .stTextInput input, .stNumberInput input {
    background: rgba(15, 23, 42, 0.75) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(56, 189, 248, 0.4) !important;
    border-radius: 12px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #38bdf8 !important;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.35) !important;
}
div[data-baseweb="select"] > div {
    background: rgba(15, 23, 42, 0.75) !important; color: #e2e8f0 !important;
    border: 1px solid rgba(56, 189, 248, 0.4) !important; border-radius: 12px !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: rgba(15, 23, 42, 0.6); border: 1px dashed rgba(56, 189, 248, 0.5);
    border-radius: 14px;
}

.stButton > button {
    background: linear-gradient(135deg, #0284c7, #0d9488);
    color: white; border: none; border-radius: 12px;
    padding: 0.65rem 1.6rem; font-weight: 600;
    box-shadow: 0 6px 18px rgba(14, 165, 233, 0.45);
    transition: all 0.25s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(45, 212, 191, 0.65);
    color: white;
}

div[data-testid="stAlert"] {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 12px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------
# 2b. OWN SVG 3D-STYLE ICONS (no external assets, no licence issue)
# ------------------------------------------------------------------
# Each glyph is drawn in a 64x64 box. "ACC" is replaced by the tile's dark colour.
GLYPHS = {
    "capsule": '<g transform="rotate(-45 32 32)"><rect x="8" y="20" width="48" height="24" rx="12" fill="#fff"/>'
               '<path d="M32 20h12a12 12 0 010 24H32z" fill="#fff" fill-opacity=".55"/>'
               '<rect x="31" y="20" width="2" height="24" fill="ACC" fill-opacity=".35"/></g>',
    "shield": '<path d="M32 6l22 8v16c0 14-10 23-22 28C20 53 10 44 10 30V14z" fill="#fff"/>'
              '<path d="M27 20h10v9h9v10h-9v9H27v-9h-9V29h9z" fill="ACC"/>',
    "heart": '<path d="M32 56S8 41 8 23a13 13 0 0124-6 13 13 0 0124 6c0 18-24 33-24 33z" fill="#fff"/>'
             '<path d="M14 33h11l4-9 6 17 4-8h11" fill="none" stroke="ACC" stroke-width="3.5" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
    "tube": '<g transform="rotate(30 32 32)"><rect x="22" y="6" width="20" height="5" rx="2.5" fill="#fff"/>'
            '<path d="M24 11h16v34a8 8 0 01-16 0z" fill="#fff" fill-opacity=".85"/>'
            '<path d="M24 30h16v15a8 8 0 01-16 0z" fill="ACC" fill-opacity=".75"/></g>',
    "drop": '<path d="M32 6C32 6 12 28 12 40a20 20 0 0040 0C52 28 32 6 32 6z" fill="#fff"/>'
            '<path d="M28 32h8v6h6v8h-6v6h-8v-6h-6v-8h6z" fill="ACC"/>',
    "clip": '<rect x="12" y="10" width="40" height="48" rx="8" fill="#fff"/>'
            '<rect x="22" y="5" width="20" height="10" rx="4" fill="ACC"/>'
            '<path d="M20 28h24M20 38h24M20 48h14" stroke="ACC" stroke-width="3.5" stroke-linecap="round"/>',
    "search": '<circle cx="28" cy="28" r="16" fill="#fff" fill-opacity=".3" stroke="#fff" stroke-width="6"/>'
              '<path d="M40 40l16 16" stroke="#fff" stroke-width="8" stroke-linecap="round"/>',
    "warn": '<path d="M32 8L58 52H6z" fill="#fff" stroke="#fff" stroke-width="6" stroke-linejoin="round"/>'
            '<path d="M32 22v15" stroke="ACC" stroke-width="5" stroke-linecap="round"/>'
            '<circle cx="32" cy="45" r="3.2" fill="ACC"/>',
    "thermo": '<rect x="25" y="6" width="14" height="36" rx="7" fill="#fff"/><circle cx="32" cy="46" r="12" fill="#fff"/>'
              '<rect x="29.5" y="18" width="5" height="26" rx="2.5" fill="ACC"/><circle cx="32" cy="46" r="6.5" fill="ACC"/>',
}


def icon_tile(uid, glyph_name, c1, c2, size=84):
    """Glossy 3D-looking icon tile: gradient + top highlight + rim light + drop shadow."""
    glyph = GLYPHS[glyph_name].replace("ACC", c2)
    return (
        f'<svg viewBox="0 0 80 80" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>'
        f'<linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>'
        f'<linearGradient id="h{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<filter id="s{uid}" x="-30%" y="-30%" width="160%" height="160%">'
        f'<feDropShadow dx="0" dy="3" stdDeviation="2.5" flood-color="#000" flood-opacity=".35"/></filter>'
        f'</defs>'
        f'<rect x="4" y="4" width="72" height="72" rx="22" fill="url(#g{uid})"/>'
        f'<rect x="4" y="4" width="72" height="40" rx="22" fill="url(#h{uid})"/>'
        f'<rect x="4.5" y="4.5" width="71" height="71" rx="21.5" fill="none" stroke="#fff" stroke-opacity=".35"/>'
        f'<g transform="translate(16 16) scale(.75)" filter="url(#s{uid})">{glyph}</g>'
        f'</svg>'
    )


def status_card(kind: str, text_html: str):
    """kind: ok (green) / warn (orange) / bad (red) / info (blue). text_html must be pre-escaped."""
    st.markdown(f'<div class="status {kind}">{text_html}</div>', unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


# ------------------------------------------------------------------
# 3. HELPERS
# ------------------------------------------------------------------
SYMPTOM_SYSTEM_PROMPT = """You are a careful medical information assistant for patients in Pakistan.
Rules:
- Reply in simple Urdu (Urdu script). Keep medicine names in English.
- Give: possible common causes, safe home care, common OTC options available in Pakistan (generic names only, no doses), and when to see a doctor.
- Always list RED FLAG signs that need emergency care (e.g. chest pain, trouble breathing, confusion, severe bleeding, very high fever, stiff neck).
- Never give a final diagnosis. Never give doses.
- If the person is a child under 5, pregnant, elderly, or has a chronic disease, tell them to see a doctor first.
- End with: 'یہ صرف معلومات ہیں، ڈاکٹر سے مشورہ ضرور کریں۔'
Use Markdown with short headings."""


def ask_symptom_checker(symptoms: str, age: int, gender: str) -> str:
    """Send the symptoms to Groq and return a Markdown answer in Urdu."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    user_msg = f"Age: {age}\nGender: {gender}\nSymptoms: {symptoms}"
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYMPTOM_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def run_with_spinner(message: str, func, *args, retries: int = 3):
    """Run a function with a spinner. Retries on the random Groq tool-call error.
    Returns (result, error_text)."""
    last_error = None
    with st.spinner(message):
        for attempt in range(retries):
            try:
                return func(*args), None
            except Exception as e:
                last_error = str(e)
                is_tool_glitch = (
                    "tool call validation failed" in last_error.lower()
                    or "tool_use_failed" in last_error
                )
                if is_tool_glitch and attempt < retries - 1:
                    time.sleep(1)
                    continue
                break
    return None, last_error


# ------------------------------------------------------------------
# 4. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏥 MediGuide PK")
    st.caption("Agentic AI Pharmacist")
    st.markdown("---")
    st.markdown("### 🤖 Agent Capabilities")
    st.markdown(
        """
- 🔎 **Fuzzy Database Matching**
  Finds the right medicine even when OCR text has spelling mistakes.
- 💊 **Generic Alternatives**
  Finds medicines with the same generic formula.
- ⚠️ **Interaction Checker**
  Warns about unsafe medicine combinations.
        """
    )
    st.markdown("---")
    st.markdown("### ⚙️ Tech Stack")
    st.markdown("Groq • GPT-OSS 120B / 20B • Gemini Vision OCR • Streamlit")
    st.markdown("---")
    st.caption("⚕️ For information only. Not a substitute for a doctor or pharmacist.")
    st.caption("🎓 Final Year Project — Sameen")
    st.caption("Islamia University of Bahawalpur")

# ------------------------------------------------------------------
# 5. HERO (title + real stats + floating 3D icons)
# ------------------------------------------------------------------
total_meds = len(med_db)
verified_meds = int(med_db["Verified"].sum())

hero_icons = "".join(
    f'<div class="float">{icon_tile(f"h{i}", name, c1, c2, 88)}</div>'
    for i, (name, c1, c2) in enumerate([
        ("capsule", "#60a5fa", "#1d4ed8"),
        ("shield", "#5eead4", "#0f766e"),
        ("heart", "#fda4af", "#be123c"),
        ("tube", "#c4b5fd", "#6d28d9"),
        ("drop", "#7dd3fc", "#0369a1"),
        ("clip", "#fcd34d", "#b45309"),
    ])
)

hero_html = (
    '<div class="hero-wrap">'
    '<div class="hero-left">'
    '<div class="hero-pill">Agentic AI Pharmacist</div>'
    '<div class="hero-title">MediGuide PK</div>'
    '<div class="hero-urdu">پاکستان میڈیسن AI اسسٹنٹ</div>'
    '<div class="hero-sub">Smart Medicine Assistant for Pakistan — Urdu and English</div>'
    '<div class="stat-row">'
    f'<div class="stat"><b>{total_meds:,}</b><span>Medicines in database</span></div>'
    f'<div class="stat"><b>{verified_meds:,}</b><span>Verified entries</span></div>'
    '<div class="stat"><b>2</b><span>Languages (Urdu + English)</span></div>'
    '</div>'
    '</div>'
    f'<div class="hero-icons">{hero_icons}</div>'
    '</div>'
)
st.markdown(hero_html, unsafe_allow_html=True)

features = [
    ("search", "#60a5fa", "#1d4ed8", "Medicine Search", "Fuzzy match + generic alternatives"),
    ("clip", "#5eead4", "#0f766e", "Prescription & Lab", "Photo, voice or text → Urdu report"),
    ("warn", "#fdba74", "#c2410c", "Drug Interaction", "Checks risky combinations"),
    ("thermo", "#fda4af", "#be123c", "Symptom Checker", "Simple Urdu guidance + red flags"),
]
feature_html = '<div class="feature-row">' + "".join(
    f'<div class="feature">{icon_tile(f"f{i}", g, c1, c2, 64)}<h4>{t}</h4><p>{d}</p></div>'
    for i, (g, c1, c2, t, d) in enumerate(features)
) + "</div>"
st.markdown(feature_html, unsafe_allow_html=True)

# ------------------------------------------------------------------
# 7. SESSION STATE
# ------------------------------------------------------------------
for key in ("search_report", "rx_report", "interaction_report", "symptom_report", "lab_report"):
    if key not in st.session_state:
        st.session_state[key] = None

# ------------------------------------------------------------------
# 7b. INPUT HELPERS (photo / voice -> text box)
# ------------------------------------------------------------------
def photo_input(prefix, target_key, types=("png", "jpg", "jpeg", "webp")):
    """Tasveer (ya PDF) upload karo, text nikalo aur target_key wale text box mein daalo."""
    up = st.file_uploader("📷 Upload photo", type=list(types), key=f"{prefix}_file")
    if up is not None and up.type and up.type.startswith("image/"):
        st.image(up, width=280)
    if st.button("📖 Read text from file", key=f"{prefix}_ocr_btn"):
        if up is None:
            st.warning("Please upload a file first.")
        else:
            text, err = run_with_spinner("📖 Reading the text... please wait", ocr_image, up.getvalue(), up.type)
            if err:
                st.error(f"Something went wrong: {err}")
            else:
                st.session_state[target_key] = text
                st.success("Text extracted. Please check it below and fix any mistakes.")


def voice_input(prefix, target_key):
    """Awaaz record/upload karo, text banao aur target_key wale text box mein daalo."""
    lang_label = st.selectbox("Language", ["اردو (Urdu)", "English"], key=f"{prefix}_lang")
    lang = "ur" if lang_label.startswith("اردو") else "en"
    if hasattr(st, "audio_input"):
        audio = st.audio_input("🎤 Record voice note", key=f"{prefix}_audio")
    else:
        audio = st.file_uploader("🎤 Upload audio", type=["wav", "mp3", "m4a", "ogg", "webm"], key=f"{prefix}_audio_file")
        st.caption("Direct recording ke liye Streamlit upgrade karein: pip install -U streamlit")
    if st.button("📝 Convert voice to text", key=f"{prefix}_voice_btn"):
        if audio is None:
            st.warning("Please record or upload a voice note first.")
        else:
            text, err = run_with_spinner(
                "📝 Converting voice to text...", transcribe_audio,
                audio.getvalue(), getattr(audio, "name", None) or "voice.wav", lang,
            )
            if err:
                st.error(f"Something went wrong: {err}")
            else:
                st.session_state[target_key] = text
                st.success("Text ready. Please check it below and fix any mistakes.")


# ------------------------------------------------------------------
# 8. MAIN TABS
# ------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["🔍 Medicine Search", "📄 Prescription & Lab Report",
     "⚠️ Drug Interaction", "🤒 Symptom Checker"]
)

# ---------- Tab 1: Medicine Search (seedha database, model nahi) ----------
with tab1:
    st.subheader("🔍 Medicine Search")
    st.caption("Type a medicine name (spelling mistakes are okay).")

    with st.container(key="input_search"):
        med_name = st.text_input(
            "Medicine name",
            placeholder="Example: Panadol Extra, Augmentin, Brufen",
            label_visibility="collapsed",
        )
        search_clicked = st.button("🔎 Search Medicine")

    if search_clicked:
        if not med_name.strip():
            st.warning("Please type a medicine name first.")
        else:
            try:
                st.session_state.search_report = match_medicines_db([med_name.strip()])
            except Exception as e:
                st.session_state.search_report = None
                st.error(f"Something went wrong: {e}")

    res = st.session_state.search_report
    if res:
        st.markdown("### 📋 Search Result")
        with st.container(key="panel_search"):
            for v in res["verified_medicines"]:
                status_card("ok", f"✅ <b>{esc(v['matched_name'])}</b> &nbsp;|&nbsp; Formula: {esc(v['generic_formula'] or 'N/A')}")
                if v.get("note"):
                    st.caption(v["note"])
                alt = find_affordable_generics(v["generic_formula"], "N/A")
                if alt["alternatives"]:
                    st.markdown("**اسی فارمولے والی دوائیں (ڈیٹا بیس کے مطابق):**")
                    for a in alt["alternatives"]:
                        st.markdown(f"- {a['name']}")
                st.caption(alt["note"])

            for c in res["closest_matches"]:
                status_card("warn", f"⚠️ '{esc(c['original_ocr_name'])}' کا بالکل درست نام نہیں ملا۔ سب سے قریبی نام:")
                for cand in c["candidates"]:
                    st.markdown(f"- {cand['matched_name']} ({cand['generic_formula'] or 'N/A'})")
                st.caption(c["note"])

            for u in res["unverified_medicines"]:
                status_card("bad", f"❌ '{esc(u['original_ocr_name'])}' — غیر تصدیق شدہ ({esc(u['reason'])})")
        st.caption("⚕️ یہ صرف معلومات ہیں۔ ڈاکٹر یا فارماسسٹ سے تصدیق ضرور کریں۔")

# ---------- Tab 2: Prescription & Lab Report ----------
with tab2:
    st.subheader("📄 Prescription & Lab Report")

    # ---- A. Prescription ----
    st.markdown("### 💊 Prescription (نسخہ)")
    st.caption("Type the text, upload a photo, or record a voice note. You can edit the text before analysis.")
    input_mode = st.radio(
        "Input method", ["✍️ Type", "📷 Photo", "🎤 Voice note"],
        horizontal=True, label_visibility="collapsed", key="rx_mode",
    )

    with st.container(key="input_rx"):
        if input_mode == "📷 Photo":
            photo_input("rx", "rx_text")
        elif input_mode == "🎤 Voice note":
            voice_input("rx", "rx_text")

        text_input = st.text_area(
            "Prescription text",
            key="rx_text",
            height=220,
            placeholder="Example:\nTab Panadol Extra 1+0+1\nCap Augmentin 625mg 1+0+1\nSyp Brufen 5ml TDS",
            label_visibility="collapsed",
        )
        analyze_clicked = st.button("🔬 Analyze Prescription")

    if analyze_clicked:
        if not text_input.strip():
            st.warning("Please enter some prescription text first.")
        else:
            result, err = run_with_spinner(
                "🤖 AI Pharmacist is analyzing your prescription... please wait",
                run_pharmacist_agent, text_input.strip(),
            )
            st.session_state.rx_report = result
            if err:
                st.error(f"Something went wrong: {err}")

    if st.session_state.rx_report:
        st.markdown("### 📋 Analysis Report")
        with st.container(key="result_rx"):
            st.markdown(st.session_state.rx_report)
        st.caption("⚕️ AI-generated information. Always confirm with a doctor or pharmacist.")

    # ---- B. Lab report ----
    st.markdown("---")
    st.markdown("### 🔬 Lab Report (لیب رپورٹ)")
    st.caption("Upload a photo or PDF of the report, or paste the text. You get a simple Urdu explanation. It is not a diagnosis.")

    with st.container(key="input_lab"):
        photo_input("lab", "lab_text", types=("png", "jpg", "jpeg", "webp", "pdf"))
        lab_text = st.text_area(
            "Lab report text",
            key="lab_text",
            height=200,
            placeholder="Example:\nHemoglobin 10.2 g/dL (12.0 - 15.5)\nWBC 11.8 x10^9/L (4.0 - 11.0)",
            label_visibility="collapsed",
        )
        lab_clicked = st.button("🔬 Explain Lab Report")

    if lab_clicked:
        if not lab_text.strip():
            st.warning("Please upload a report or paste its text first.")
        else:
            result, err = run_with_spinner(
                "🔬 Reading your lab report... please wait", explain_lab_report, lab_text.strip(),
            )
            st.session_state.lab_report = result
            if err:
                st.error(f"Something went wrong: {err}")

    if st.session_state.lab_report:
        st.markdown("### 📋 Lab Report Explanation")
        with st.container(key="result_lab"):
            st.markdown(st.session_state.lab_report)
        st.caption("⚕️ AI-generated information. Not a diagnosis. Always confirm with a doctor.")

# ---------- Tab 3: Drug Interaction (seedha tools, model nahi) ----------
with tab3:
    st.subheader("⚠️ Drug Interaction Checker")
    st.caption("Write one medicine per line (at least 2).")

    with st.container(key="input_interaction"):
        meds_text = st.text_area(
            "Medicines",
            height=160,
            placeholder="Example:\nDisprin\nBrufen\nWarfarin",
            label_visibility="collapsed",
        )
        interaction_clicked = st.button("⚠️ Check Interactions")

    if interaction_clicked:
        meds = [m.strip() for m in meds_text.splitlines() if m.strip()]
        if len(meds) < 2:
            st.warning("Please enter at least 2 medicines, one per line.")
        else:
            try:
                matched = match_medicines_db(meds)
                verified = matched["verified_medicines"]
                inter = check_interactions(verified) if len(verified) >= 2 else None
                st.session_state.interaction_report = {"matched": matched, "inter": inter}
            except Exception as e:
                st.session_state.interaction_report = None
                st.error(f"Something went wrong: {e}")

    rep = st.session_state.interaction_report
    if rep:
        matched, inter = rep["matched"], rep["inter"]
        st.markdown("### 📋 Interaction Report")
        with st.container(key="panel_interaction"):
            st.markdown("**ڈیٹا بیس میں ملنے والی دوائیں:**")
            for v in matched["verified_medicines"]:
                st.markdown(f"- {v['original_ocr_name']} → {v['matched_name']} ({v['generic_formula'] or 'N/A'})")

            incomplete = matched["closest_matches"] or matched["unverified_medicines"]
            for c in matched["closest_matches"]:
                status_card("warn", f"'{esc(c['original_ocr_name'])}': بالکل درست نام نہیں ملا، اس کا انٹرایکشن چیک نہیں ہوا۔")
            for u in matched["unverified_medicines"]:
                status_card("bad", f"'{esc(u['original_ocr_name'])}': غیر تصدیق شدہ، اس کا انٹرایکشن چیک نہیں ہوا۔")

            if inter is None:
                status_card("info", "انٹرایکشن چیک کے لیے کم از کم 2 تصدیق شدہ دوائیں چاہئیں۔")
            else:
                if inter["interactions"]:
                    for i in inter["interactions"]:
                        icon = "🔴" if i["severity"] == "High" else "🟠"
                        kind = "bad" if i["severity"] == "High" else "warn"
                        status_card(
                            kind,
                            f"{icon} <b>{esc(i['severity'])}</b>: {esc(', '.join(i['between']))}"
                            f"<br>{esc(i['warning'])}",
                        )
                else:
                    status_card("info", "ہمارے چھوٹے رول سیٹ میں کوئی انٹرایکشن نہیں ملا۔ یہ 'محفوظ' ہونے کا ثبوت نہیں ہے۔")
                st.caption(inter["note"])

            if incomplete:
                status_card("warn", "انٹرایکشن چیک ادھورا ہے، کچھ دوائیں تصدیق نہیں ہو سکیں۔")
        st.caption("⚕️ ڈاکٹر کے مشورے کے بغیر کوئی دوا بند یا تبدیل نہ کریں۔")

# ---------- Tab 4: Symptom Checker ----------
with tab4:
    st.subheader("🤒 Symptom Checker")
    st.caption("Describe your symptoms in Urdu or English.")

    with st.container(key="input_symptom"):
        with st.expander("🎤 Use voice instead of typing"):
            voice_input("sym", "symptom_text")
        symptoms = st.text_area(
            "Symptoms",
            key="symptom_text",
            height=140,
            placeholder="Example: 2 din se bukhar aur gale mein dard hai",
            label_visibility="collapsed",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            age = st.number_input("Age", min_value=0, max_value=120, value=25)
        with col_b:
            gender = st.selectbox("Gender", ["Male", "Female"])
        symptom_clicked = st.button("🤒 Check Symptoms")

    if symptom_clicked:
        if not symptoms.strip():
            st.warning("Please describe your symptoms first.")
        else:
            result, err = run_with_spinner(
                "🤒 Analyzing your symptoms...",
                ask_symptom_checker, symptoms.strip(), int(age), gender,
            )
            st.session_state.symptom_report = result
            if err:
                st.error(f"Something went wrong: {err}")

    if st.session_state.symptom_report:
        st.markdown("### 📋 Symptom Analysis")
        with st.container(key="result_symptom"):
            st.markdown(st.session_state.symptom_report)
        status_card("bad", "🚨 Emergency (chest pain, breathing problem, heavy bleeding)? Go to a hospital now.")
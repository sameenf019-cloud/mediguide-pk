"""
test_all.py  -  MediGuide PK ka ek-command self test.

Chalayein (project folder mein):
    python test_all.py

Part 1 (OFFLINE)  : database, matching, interactions, generics, har tab ka headless run.
Part 2 (LIVE)     : Groq / Gemini / Whisper ko asli call. Sirf tab chalta hai jab
                    GROQ_API_KEY aur GEMINI_API_KEY set hon, warna SKIP.

Note: LIVE tests mein AI ka jawab kabhi kabhi badal sakta hai. Agar sirf ek LIVE test FAIL ho
to ek baar dobara chalayein, aur lagataar FAIL ho to mujhe output bhej dein.
"""
import io
import os
import re
import sys
import wave
import time
import types

os.environ.setdefault("GROQ_API_KEY", "dummy")   # offline tests ke liye (import ke waqt chahiye)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if (detail and not ok) else ""))


def skip(name, why):
    RESULTS.append((name, None, why))
    print(f"[SKIP] {name}  ({why})")


def run(name, fn):
    """Test chalao; exception aaye to FAIL likho, crash na ho."""
    try:
        fn()
    except AssertionError as e:
        check(name, False, str(e) or "assertion failed")
    except Exception as e:  # noqa
        check(name, False, f"{type(e).__name__}: {e}")


# ======================================================================
# PART 1: OFFLINE
# ======================================================================
print("\n=== PART 1: OFFLINE TESTS ===")

import agent_tools as T


def t_db():
    assert len(T.med_db) > 6000, f"sirf {len(T.med_db)} rows"
    assert "Verified" in T.med_db.columns
    check("Database load (6000+ rows)", True)


def t_match():
    r = T.match_medicines_db(["Panadol Extra"])["verified_medicines"]
    assert r and "paracetamol" in str(r[0]["generic_formula"]).lower(), "Panadol Extra verified nahi"
    check("Panadol Extra -> verified, Paracetamol", True)

    r = T.match_medicines_db(["Panadol"])
    assert r["closest_matches"] and not r["verified_medicines"], "Panadol (unverified source) closest hona chahiye"
    check("Panadol -> closest (unverified source), verified nahi", True)

    r = T.match_medicines_db(["Paracetamol"])["verified_medicines"]
    assert r and r[0]["match_type"] == "generic_name" and r[0]["generic_formula"].lower() == "paracetamol", "Paracetamol generic naam verified nahi"
    check("Paracetamol (generic naam) -> verified", True)

    r = T.match_medicines_db(["AjeebDawa"])
    assert r["unverified_medicines"], "AjeebDawa unverified nahi aaya"
    check("AjeebDawa -> unverified", True)

    r = T.match_medicines_db(["Warfarin"])["verified_medicines"]
    assert r and r[0]["match_type"] == "exact"
    check("Warfarin -> verified", True)

    r = T.match_medicines_db(["Brufen 400mg"])["verified_medicines"]
    assert r and r[0]["match_type"] == "exact" and "400" in str(r[0]["generic_formula"]), "Brufen 400mg exact nahi"
    check("Brufen 400mg -> exact match (400mg)", True)

    r = T.match_medicines_db(["Brufen 300mg"])["verified_medicines"]
    assert r and r[0]["match_type"] == "name_match" and r[0].get("note"), "ghair-maujood strength par note nahi aaya"
    check("Brufen 300mg (db mein nahi) -> name_match + strength note", True)

    r = T.match_medicines_db(["pendol extraa"])
    assert not r["verified_medicines"] and r["closest_matches"], "ghalat spelling verified ho gayi"
    check("Ghalat spelling -> sirf closest (auto-verify nahi)", True)


def t_inter():
    r = T.check_interactions([{"generic_formula": "Warfarin"}, {"generic_formula": "Ibuprofen (600mg)"}])
    assert any(i["severity"] == "High" for i in r["interactions"]), "Warfarin+Ibuprofen High nahi aaya"
    check("Warfarin + Ibuprofen -> High interaction", True)

    r = T.check_interactions([{"generic_formula": "Paracetamol"}, {"generic_formula": "Cetirizine"}])
    txt = r["note"].lower()
    assert r["interactions"] == [] and "safe" not in txt.replace("not safe", ""), "empty interaction par 'safe' likha"
    check("Interaction khali -> 'safe' nahi likha", True)


def t_generics():
    r = T.find_affordable_generics("Paracetamol", "N/A")
    assert r["alternatives"], "Paracetamol ke alternatives khali"
    assert r["price_comparison"] is False
    check("Generics: Paracetamol ke alternatives milte hain", True)

    r = T.find_affordable_generics(None, None)
    assert r["alternatives"] == []
    check("Generics: formula None par crash nahi", True)


def t_urdu_notes():
    import re
    r = T.match_medicines_db(["Panadol"])
    note = r["closest_matches"][0]["note"]
    assert re.search(r"[\u0600-\u06FF]", note), "note Urdu script mein nahi"
    check("Tool notes Urdu script mein", True)


run("Database", t_db)
run("Matching", t_match)
run("Interactions", t_inter)
run("Generics", t_generics)
run("Urdu notes", t_urdu_notes)


# ---- ai_helpers (fake client, koi API nahi)
def t_helpers():
    import ai_helpers as H
    seen = {}

    class FakeT:
        def create(self, **kw):
            seen.update(kw)
            return types.SimpleNamespace(text="بروفن پینادول موسیقی")

    real = H._groq
    H._groq = lambda: types.SimpleNamespace(audio=types.SimpleNamespace(transcriptions=FakeT()))
    try:
        out = H.transcribe_audio(b"x", "a.wav", "ur")
    finally:
        H._groq = real
    assert out == "بروفن پینادول", f"junk strip nahi hua: {out!r}"
    assert seen.get("language") == "ur" and seen.get("prompt"), "language/prompt pass nahi hue"
    check("Voice helper: junk word hat gaya, language+hint pass", True)


run("Voice helper", t_helpers)


# ---- Streamlit app headless
def t_app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90).run()
    assert not at.exception, f"app load error: {list(at.exception)}"
    check("App load (koi error nahi)", True)
    assert len(at.tabs) == 4
    check("App: 4 tabs", True)

    def btn(label):
        return [b for b in at.button if label in b.label][0]

    at.text_input[0].set_value("Panadol Extra")
    btn("Search Medicine").click(); at.run()
    assert not at.exception and at.success, "Tab1 search fail"
    check("Tab 1: Medicine Search chalta hai", True)

    t3 = [t for t in at.text_area if t.key is None][0]
    t3.set_value("Brufen\nWarfarin")
    btn("Check Interactions").click(); at.run()
    assert not at.exception and any("High" in e.value for e in at.error), "Tab3 High interaction nahi dikhi"
    check("Tab 3: Interaction (High) dikhti hai", True)

    for key in ("rx_text", "lab_text", "symptom_text"):
        assert any(t.key == key for t in at.text_area), f"{key} box nahi mila"
    check("Tab 2/4: prescription, lab, symptom boxes maujood", True)

    assert any(r.key == "rx_mode" for r in at.radio)
    check("Tab 2: Type / Photo / Voice option maujood", True)


run("App", t_app)


# ======================================================================
# PART 2: LIVE
# ======================================================================
print("\n=== PART 2: LIVE TESTS (asli API) ===")
GROQ = os.environ.get("GROQ_API_KEY", "")
GEMINI = os.environ.get("GEMINI_API_KEY", "")
LIVE_GROQ = GROQ not in ("", "dummy")

SAMPLE_RX = "Tab Warfarin 5mg 1+0+0\nTab Brufen 400mg 1+0+1"
SAMPLE_LAB = """Blood C/E (Complete, CBC)
Hb 11.5 - 16 g/dl 14.2
MCV 75 - 95 fl 80
MCH 26 - 32 pg 25
Platelet Count 150 - 400 x10^9/l 247
MPV 7 - 11 fl 12.8
WBC Count 4 - 11 x10^9/l 7.9"""

if not LIVE_GROQ:
    skip("Groq live tests", "GROQ_API_KEY set nahi")
else:
    def t_agent_en():
        import pharmacist_agent as P
        out = P.run_pharmacist_agent(SAMPLE_RX)
        assert out, "khali report"
        assert "یہ صرف معلومات ہیں" in out, "end ka Urdu disclaimer nahi"
        assert "verified_medicines" not in out and "closest_matches" not in out, "andar ke alfaz report mein"
        assert "doctor ki hidayat" not in out.lower()
        assert ("خون" in out) or ("High" in out), "Warfarin+Brufen ki interaction warning nahi aayi"
        for m in re.finditer(r"سست|sasti|cheap", out, flags=re.I):
            ctx = out[max(0, m.start() - 45): m.end() + 45]
            negated = ("نہیں" in ctx) or ("نہ " in ctx) or ("نا " in ctx)
            assert negated, "price nahi thi par 'sasti' ka daava hua: ..." + ctx.replace("\n", " ") + "..."
        check("Agent (English naam): Urdu report, interaction, disclaimer", True)

    def t_agent_urdu():
        import pharmacist_agent as P
        out = P.run_pharmacist_agent("بروفن 400mg اور وارفرین 5mg")
        assert ("خون" in out) or ("High" in out), "Urdu-script naam se match/interaction nahi bana"
        check("Agent (Urdu script naam -> English match)", True)

    def t_lab():
        import ai_helpers as H
        out = H.explain_lab_report(SAMPLE_LAB)
        assert "MCH" in out and "MPV" in out, "MCH/MPV report mein nahi"
        banned = ["اینیمیا", "انیمیا", "آئرن", "anemia", "anaemia", "iron", "سوزش", "انفیکشن", "infection"]
        hit = [b for b in banned if b.lower() in out.lower()]
        assert not hit, f"tashkhees/wajah ke alfaz aaye: {hit}"
        assert "یہ صرف معلومات ہیں" in out, "disclaimer nahi"
        check("Lab explain: MCH/MPV pakre, koi tashkhees nahi", True)

    def t_whisper():
        import ai_helpers as H
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)       # 1 second khamoshi
        try:
            H.transcribe_audio(buf.getvalue(), "silence.wav", "ur")
        except RuntimeError as e:
            assert "koi text nahi" in str(e), str(e)   # khamoshi par khali text = theek
        check("Whisper call chalti hai (key + parameters theek)", True)

    run("Agent EN", t_agent_en)
    print("   (Groq free tier ki limit ke liye 40 second ruk raha hoon...)")
    time.sleep(40)
    run("Agent UR", t_agent_urdu)
    time.sleep(20)
    run("Lab", t_lab)
    run("Whisper", t_whisper)

if not GEMINI:
    skip("Gemini OCR live test", "GEMINI_API_KEY set nahi")
else:
    def t_ocr():
        from PIL import Image, ImageDraw, ImageFont
        import ai_helpers as H
        img = Image.new("RGB", (700, 220), "white")
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=34)
        except TypeError:
            font = ImageFont.load_default()
        d.text((20, 20), "Tab Warfarin 5mg 1+0+0", fill="black", font=font)
        d.text((20, 90), "Tab Brufen 400mg 1+0+1", fill="black", font=font)
        buf = io.BytesIO(); img.save(buf, "PNG")
        out = H.ocr_image(buf.getvalue(), "image/png")
        assert "warfarin" in out.lower() and "brufen" in out.lower(), f"OCR ghalat: {out!r}"
        check("Gemini OCR: tasveer se dawa ke naam nikle", True)

    run("OCR", t_ocr)


# ======================================================================
print("\n=== KHULASA ===")
p = sum(1 for _, ok, _ in RESULTS if ok is True)
f = sum(1 for _, ok, _ in RESULTS if ok is False)
s = sum(1 for _, ok, _ in RESULTS if ok is None)
print(f"PASS: {p}   FAIL: {f}   SKIP: {s}")
if f:
    print("FAIL wale tests ka output mujhe bhej dein.")
sys.exit(1 if f else 0)
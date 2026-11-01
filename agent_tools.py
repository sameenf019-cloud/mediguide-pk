import re
import difflib
import pandas as pd

CSV_PATH = "mediguide_db.csv"
AUTO_ACCEPT = 0.90      # is se upar similarity ho to spelling-correct karke verified maan lo
SUGGEST_CUTOFF = 0.80   # is se upar ho to "qareebi match" ke taur par dikhao

# ------------------------------------------------------------------
# Naam saaf karne ke patterns
# ------------------------------------------------------------------
_FORM = r"\b(tablets?|tabs?|capsules?|caps?|syrup|syp|suspension|injection|inj|cream|gel|drops|ointment|sachet|lotion|spray)\b"
_PACK = r"\b\d+\s*x\s*\d+(?:'s)?|\b\d+'s\b"
_SCHEDULE = r"\b\d\s*\+\s*\d\s*\+\s*\d\b|\b(?:od|bd|bid|tds|tid|qid|hs)\b"
_STRENGTH = r"\b\d+(?:\.\d+)?(?:mg|mcg|g|ml|iu)\b"


def _norm(text, keep_strength):
    """Naam ko lowercase karo, form (tablet/syrup), pack size aur dose schedule hata do."""
    t = str(text).lower().replace("’", "'")
    t = re.sub(r"(\d)\s+(mg|mcg|g|ml|iu)\b", r"\1\2", t)
    t = re.sub(_SCHEDULE, " ", t)
    t = re.sub(_PACK, " ", t)
    t = re.sub(_FORM, " ", t)
    if not keep_strength:
        t = re.sub(_STRENGTH, " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _s(x):
    """NaN ko None banao, baqi ko string."""
    return None if pd.isna(x) else str(x)


# ------------------------------------------------------------------
# Database ek baar load
# ------------------------------------------------------------------
med_db = pd.read_csv(CSV_PATH)
med_db = med_db.dropna(subset=["Medicine Name"]).reset_index(drop=True)
# Verified column (build_db.py se). Na ho to sab verified maano.
if "Verified" not in med_db.columns:
    med_db["Verified"] = True
med_db["Verified"] = med_db["Verified"].fillna(True).astype(bool)
# Verified rows pehle, taake duplicates mein verified row hi chune
med_db = med_db.sort_values("Verified", ascending=False, kind="stable").reset_index(drop=True)
med_db["key_full"] = med_db["Medicine Name"].map(lambda x: _norm(x, True))
med_db["key_name"] = med_db["Medicine Name"].map(lambda x: _norm(x, False))
def _formula_key(f):
    """'Paracetamol (500 mg)' -> 'paracetamol'. Strength hata kar sirf formula ka naam."""
    if f is None or pd.isna(f):
        return ""
    t = re.sub(r"\(.*?\)", " ", str(f).lower())
    return re.sub(r"\s+", " ", t).strip()


med_db["formula_key"] = med_db["Generic Formula"].map(_formula_key)
NAME_KEYS = sorted(k for k in set(med_db["key_name"]) if k)
_BY_NAME = med_db.drop_duplicates("key_name").set_index("key_name")


def _info(row):
    return {
        "matched_name": str(row["Medicine Name"]),
        "generic_formula": _s(row["Generic Formula"]),
        "price": _s(row["Price"]),
        "verified": bool(row["Verified"]),
    }


# ------------------------------------------------------------------
# TOOL 1: match_medicines_db
# ------------------------------------------------------------------
def match_medicines_db(extracted_medicines):
    """
    verified_medicines  : exact ya (bohat qareebi) spelling-corrected match
    closest_matches     : exact nahi mila, qareebi naam mile -> user confirm kare
    unverified_medicines: kuch nahi mila
    """
    results = {"verified_medicines": [], "closest_matches": [], "unverified_medicines": []}

    for med_name in extracted_medicines or []:
        q_full = _norm(med_name, True)
        q_name = _norm(med_name, False)

        if not q_name:
            results["unverified_medicines"].append(
                {"original_ocr_name": med_name, "reason": "نام خالی ہے یا سمجھ نہیں آیا"}
            )
            continue

        # 1) Exact match (strength ke sath), phir sirf naam ka match
        rows = med_db[med_db["key_full"] == q_full]
        match_type = "exact"
        note = None
        if rows.empty:
            rows = med_db[med_db["key_name"] == q_name]
            match_type = "name_match"
            if q_full != q_name:
                note = "دوا کا نام مل گیا لیکن یہ مقدار (strength) ڈیٹا بیس میں نہیں ملی۔ مقدار کی تصدیق ضرور کریں۔"
            else:
                note = "نام مل گیا۔ ڈیٹا بیس میں اس کی دوسری مقداریں بھی ہو سکتی ہیں، مقدار کی تصدیق کریں۔"
        # Generic (formula) naam jaise "Paracetamol": verified formulas mein dhoondo
        if rows.empty or not rows.iloc[0]["Verified"]:
            gen = med_db[(med_db["formula_key"] == q_name) & med_db["Verified"]]
            if not gen.empty:
                g = re.sub(r"\s*\(.*?\)", "", str(gen.iloc[0]["Generic Formula"])).strip()
                results["verified_medicines"].append({
                    "original_ocr_name": med_name,
                    "matched_name": g,
                    "generic_formula": g,
                    "price": None,
                    "verified": True,
                    "match_type": "generic_name",
                    "note": "یہ جنرک (فارمولے کا) نام ہے، کسی برانڈ کا نہیں۔ مقدار اور برانڈ کی تصدیق کریں۔",
                })
                continue

        if not rows.empty and not rows.iloc[0]["Verified"]:
            # Sirf unverified (supplementary) source mein mila -> verified nahi, closest_matches mein
            results["closest_matches"].append({
                "original_ocr_name": med_name,
                "candidates": [_info(rows.iloc[0])],
                "note": "یہ نام صرف غیر تصدیق شدہ ڈیٹا میں ملا۔ ڈاکٹر یا فارماسسٹ سے تصدیق کریں۔",
            })
            continue
        if not rows.empty:
            entry = {"original_ocr_name": med_name, **_info(rows.iloc[0]), "match_type": match_type}
            if note:
                entry["note"] = note
            results["verified_medicines"].append(entry)
            continue

        # 2) Fuzzy (spelling ki ghalti) aur prefix (jaise Panadol -> Panadol Extra)
        prefix = [k for k in NAME_KEYS if k.startswith(q_name + " ")]
        fuzzy = difflib.get_close_matches(q_name, NAME_KEYS, n=3, cutoff=SUGGEST_CUTOFF)

        if fuzzy:
            ratio = difflib.SequenceMatcher(None, q_name, fuzzy[0]).ratio()
            if ratio >= AUTO_ACCEPT and _BY_NAME.loc[fuzzy[0]]["Verified"]:
                results["verified_medicines"].append({
                    "original_ocr_name": med_name,
                    **_info(_BY_NAME.loc[fuzzy[0]]),
                    "match_type": "spelling_corrected",
                    "note": "ہجے درست کر کے نام ملایا گیا ہے۔ نام کی تصدیق کریں۔",
                })
                continue

        candidates = []
        for k in prefix[:3] + fuzzy:
            if k not in candidates:
                candidates.append(k)
        candidates = candidates[:5]

        if candidates:
            results["closest_matches"].append({
                "original_ocr_name": med_name,
                "candidates": [_info(_BY_NAME.loc[k]) for k in candidates],
                "note": "بالکل درست نام نہیں ملا۔ یہ سب سے قریبی نام ہیں، ضروری نہیں کہ یہ وہی دوا ہو، بالکل مختلف دوا بھی ہو سکتی ہے۔ ڈاکٹر یا فارماسسٹ سے تصدیق کریں۔",
            })
        else:
            results["unverified_medicines"].append(
                {"original_ocr_name": med_name, "reason": "ڈیٹا بیس میں نہیں ملی"}
            )

    return results


# ------------------------------------------------------------------
# TOOL 2: find_affordable_generics
# ------------------------------------------------------------------
def clean_price(price):
    """'Rs. 150.50' ko float banao. Price na ho to None."""
    if price is None or (isinstance(price, float) and pd.isna(price)):
        return None
    num = re.sub(r"[^\d.]", "", str(price))
    try:
        return float(num) if num else None
    except ValueError:
        return None


def find_affordable_generics(formula, original_price_str=None):
    """Same formula wali dawaiyan. Price data ho tabhi 'sasti' ka comparison karta hai."""
    if formula is None or pd.isna(formula) or str(formula).strip().upper() in ("", "N/A"):
        return {"alternatives": [], "price_comparison": False,
                "note": "فارمولا معلوم نہیں، متبادل نہیں مل سکتے۔"}

    same = med_db[(med_db["formula_key"] == _formula_key(formula)) & med_db["Verified"]].copy()
    if same.empty:
        return {"alternatives": [], "price_comparison": False,
                "note": "اس فارمولے کی کوئی اور دوا ڈیٹا بیس میں نہیں ملی۔"}

    same["num_price"] = pd.to_numeric(same["Price"].map(clean_price), errors="coerce")
    original = clean_price(original_price_str)

    # Price data maujood ho to sasti dawaiyan dikhao
    if original is not None and same["num_price"].notna().any():
        cheaper = same[same["num_price"] < original].sort_values("num_price").head(3)
        return {
            "price_comparison": True,
            "alternatives": [
                {"name": str(r["Medicine Name"]), "manufacturer": _s(r["Manufacturer"]), "price": _s(r["Price"])}
                for _, r in cheaper.iterrows()
            ],
            "note": "ڈیٹا بیس کی قیمتوں کے مطابق سستی دوائیں۔",
        }

    # Price data nahi: sirf same formula, "sasti" ka daava nahi
    return {
        "price_comparison": False,
        "alternatives": [
            {"name": str(r["Medicine Name"]), "manufacturer": _s(r["Manufacturer"])}
            for _, r in same.head(5).iterrows()
        ],
        "note": "ڈیٹا بیس میں قیمت موجود نہیں، اس لیے 'سستی' نہیں کہہ سکتے۔ یہ صرف وہ دوائیں ہیں جن کا فارمولا (ڈیٹا بیس کے مطابق) ایک ہے۔ فارماسسٹ سے تصدیق کریں۔",
    }


# ------------------------------------------------------------------
# TOOL 3: check_interactions (chhota starter rule-set)
# ------------------------------------------------------------------
_NSAIDS = ["ibuprofen", "diclofenac", "naproxen", "mefenamic", "ketorolac",
           "celecoxib", "etoricoxib", "nimesulide"]
_ASPIRIN = ["aspirin", "acetylsalicylic"]
_WARFARIN = ["warfarin"]
_COUMARIN_BOOSTERS = ["metronidazole"]
_CHELATED_ANTIBIOTICS = ["ciprofloxacin", "levofloxacin", "ofloxacin", "moxifloxacin",
                         "doxycycline", "tetracycline"]
_MINERALS = ["calcium", "iron", "ferrous", "magnesium", "aluminium", "aluminum", "antacid"]
_MACROLIDES = ["clarithromycin", "erythromycin"]
_STATINS = ["simvastatin", "atorvastatin", "lovastatin"]
_PDE5 = ["sildenafil", "tadalafil", "vardenafil"]
_NITRATES = ["isosorbide", "nitroglycerin", "glyceryl trinitrate"]

_RULES = [
    (_WARFARIN, _NSAIDS + _ASPIRIN, "High",
     "وارفرین کے ساتھ درد کی یہ دوائیں (NSAID/اسپرین) لینے سے خون بہنے کا بڑا خطرہ ہے۔"),
    (_WARFARIN, _COUMARIN_BOOSTERS, "High",
     "میٹرونائیڈازول وارفرین کا اثر بڑھا سکتی ہے، خون بہنے کا خطرہ ہے۔"),
    (_ASPIRIN, _NSAIDS, "High",
     "اسپرین اور دوسری درد کی دوا (NSAID) ایک ساتھ لینے سے معدے میں خون بہنے کا خطرہ بڑھتا ہے۔"),
    (_CHELATED_ANTIBIOTICS, _MINERALS, "Moderate",
     "کیلشیم/آئرن/اینٹی ایسڈ اس اینٹی بائیوٹک کا جذب کم کر سکتے ہیں۔ الگ الگ وقت پر لیں، فارماسسٹ سے وقفہ پوچھیں۔"),
    (_MACROLIDES, _STATINS, "High",
     "اس اینٹی بائیوٹک اور اسٹیٹن کے ساتھ پٹھوں کو نقصان پہنچنے کا خطرہ ہے۔"),
    (_PDE5, _NITRATES, "High",
     "یہ دونوں ایک ساتھ لینے سے بلڈ پریشر بہت گر سکتا ہے۔ خطرناک ہو سکتا ہے۔"),
]


def _hits(formulas, group):
    return {g for g in group for f in formulas if g in f}


def check_interactions(verified_medicines_list):
    formulas = []
    for med in verified_medicines_list or []:
        f = med.get("generic_formula") if isinstance(med, dict) else med
        if f and not pd.isna(f):
            formulas.append(str(f).lower())

    found = []
    for group_a, group_b, severity, warning in _RULES:
        a, b = _hits(formulas, group_a), _hits(formulas, group_b)
        if a and b:
            found.append({"severity": severity, "between": sorted(a | b), "warning": warning})

    nsaid_hits = _hits(formulas, _NSAIDS)
    if len(nsaid_hits) >= 2:
        found.append({
            "severity": "Moderate",
            "between": sorted(nsaid_hits),
            "warning": "دو NSAID درد کی دوائیں ایک ساتھ لینے سے معدے اور گردوں کو نقصان کا خطرہ بڑھتا ہے۔",
        })

    if found:
        return {"interactions": found,
                "note": "یہ چھوٹے رول سیٹ کے نتائج ہیں۔ ڈاکٹر یا فارماسسٹ سے تصدیق کریں۔"}

    return {
        "interactions": [],
        "note": "ہمارے چھوٹے رول سیٹ میں کوئی انٹرایکشن نہیں ملا۔ اس کا مطلب 'محفوظ' ہرگز نہیں، یہ صرف چند مشہور امتزاج چیک کرتا ہے۔ ڈاکٹر یا فارماسسٹ سے تصدیق کریں۔",
    }


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    for name in ["Panadol", "Panadol Extra", "Augmentn 457mg", "Augmentin", "AjeebDawa"]:
        print(name, "->", match_medicines_db([name]))
        print()

    print("--- Interaction test (Warfarin + Aspirin + Ibuprofen) ---")
    print(check_interactions([
        {"generic_formula": "Acetylsalicylic Acid"},
        {"generic_formula": "Ibuprofen"},
        {"generic_formula": "Warfarin"},
    ]))

    print("\n--- Generic test ---")
    print(find_affordable_generics("Paracetamol", "N/A"))
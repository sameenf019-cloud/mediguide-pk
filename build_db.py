"""
build_db.py  -  ek baar chalao, mediguide_db.csv ban jayegi.

Input  (zip nikaal kar ek folder mein rakhein, ya zip ko seedha same folder mein):
    mediguide_final_dataset.zip   (master_788 + essential_467 + gazette_69)
    mediguide_pakistan_supplementary_unverified.csv   (Verified=False ke sath shamil hoti hai)
    pakistan_medicines_5k.csv   (purani scrape, brand -> generic formula ke liye; file ho to merge hoti hai)

Output: mediguide_db.csv  with columns agent_tools.py already uses:
    Medicine Name, Generic Formula, Manufacturer, Price
    + Source, Verified   (naye columns, tools inhein ignore karte hain)

Usage:
    python build_db.py
    python build_db.py --no-supplementary   (supplementary bahar rakhni ho)
"""
import argparse
import html
import re
import zipfile
import pandas as pd

ZIP_PATH = "mediguide_final_dataset.zip"
SUPP_PATH = "mediguide_pakistan_supplementary_unverified.csv"
OLD_PATH = "pakistan_medicines_5k.csv"
OUT_PATH = "mediguide_db.csv"


def clean_generic(x):
    """OCR/PDF kachra hatao: □, *, \\n, html entities, footnote text."""
    t = html.unescape(str(x))
    t = t.replace("\\n", " ").replace("□", " ")
    t = re.sub(r"\*+\s*\(.*?\)", " ", t)          # *(acute or chronic use)
    t = re.sub(r"\*.*$", " ", t)                  # *including quality-assured ...
    t = re.sub(r"^\s*o\s+(?=[a-z])", "", t)       # "o lisinopril"
    t = re.sub(r"\s*\+\s*", " + ", t)             # a+b -> a + b
    t = re.sub(r"[.\s]+$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def main(include_supp):
    with zipfile.ZipFile(ZIP_PATH) as z:
        master = pd.read_csv(z.open("mediguide_master_788.csv"))

    rows = []

    # 1) Brand rows (Drug Registry): naam + company + price. Generic formula in mein NAHI hota.
    reg = master[master["source_dataset"] == "Drug Registry"]
    for _, r in reg.iterrows():
        pack = "" if pd.isna(r["pack_size"]) else f" {r['pack_size']}"
        price = r["price_after_pkr"]
        rows.append({
            "Medicine Name": f"{r['product_name']}{pack}".strip(),
            "Generic Formula": None,
            "Manufacturer": r["company"],
            "Price": None if pd.isna(price) else f"Rs. {price:g}",
            "Source": "Drug Registry",
            "Verified": True,
        })

    # 2) Generic rows (Essential Medicines list + Gazette): naam hi formula hai.
    gen = master[master["source_dataset"] != "Drug Registry"]
    seen = set()
    for _, r in gen.iterrows():
        g = clean_generic(r["medicine"])
        if not g or g.lower() in seen:
            continue
        seen.add(g.lower())
        rows.append({
            "Medicine Name": g,
            "Generic Formula": g,
            "Manufacturer": None,
            "Price": None,
            "Source": r["source_dataset"],
            "Verified": True,
        })

    # 3) Supplementary (UNVERIFIED) - sirf flag dene par
    if include_supp:
        sup = pd.read_csv(SUPP_PATH)
        for _, r in sup.iterrows():
            strength = "" if pd.isna(r["Strength"]) else f" {str(r['Strength']).strip()}"
            rows.append({
                "Medicine Name": f"{r['Drug Name']}{strength}".strip(),
                "Generic Formula": None,
                "Manufacturer": r["Manufacturer"],
                "Price": None if pd.isna(r["Price"]) else f"Rs. {r['Price']:g}",
                "Source": "Supplementary (unverified)",
                "Verified": False,
            })

    # 4) Purani scrape (brand + generic formula + price)
    import os
    if os.path.exists(OLD_PATH):
        old = pd.read_csv(OLD_PATH)   # "N/A" khud NaN ban jata hai
        for _, r in old.iterrows():
            rows.append({
                "Medicine Name": r["Medicine Name"],
                "Generic Formula": r.get("Generic Formula"),
                "Manufacturer": r.get("Manufacturer"),
                "Price": r.get("Price"),
                "Source": "Dawaai scrape (old CSV)",
                "Verified": True,
            })

    out = pd.DataFrame(rows).dropna(subset=["Medicine Name"])
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved {len(out)} rows -> {OUT_PATH}")
    print(out["Source"].value_counts().to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-supplementary", action="store_true")
    main(not ap.parse_args().no_supplementary)

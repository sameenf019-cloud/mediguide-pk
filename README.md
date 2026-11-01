# MediGuide PK

Agentic AI Pharmacist for Pakistan, in Urdu and English.
Final Year Project, Islamia University of Bahawalpur.

> **Educational project. Not medical advice.** The app gives information only.
> Always confirm with a doctor or pharmacist before taking, stopping or changing any medicine.

## What it does

1. **Medicine Search:** looks up a medicine in the database (spelling mistakes are okay) and shows other medicines with the same generic formula.
2. **Prescription and Lab Report:** type, photo or voice note input. An AI agent checks each medicine against the database and writes a simple Urdu report. Lab reports (photo, PDF or text) get a plain Urdu explanation, not a diagnosis.
3. **Drug Interaction:** checks medicine combinations against a small rule set (no LLM).
4. **Symptom Checker:** general guidance in Urdu with emergency red flags.

## Safety design

- Medicines not found in the database are marked "unverified" and are never treated as verified.
- Close name matches are shown with a warning that it may be a different medicine.
- No "cheaper" claim is made unless the database has price data.
- An empty interaction result is never described as "safe". The rule set is small and only covers a few well-known combinations.
- The agent never gives maximum daily doses.
- Every result ends with a disclaimer.

## Tech stack

Streamlit, Groq (`openai/gpt-oss-120b` agent, `openai/gpt-oss-20b` symptom and lab explainer, `whisper-large-v3` voice), Gemini Vision (OCR), pandas.

## Run locally

```bash
pip install -r requirements.txt
```

Set your own API keys as environment variables:

```powershell
$env:GROQ_API_KEY="your-groq-key"
$env:GEMINI_API_KEY="your-gemini-key"
```

```bash
streamlit run app.py
```

Never commit API keys to this repository.

## Data

`mediguide_db.csv` is built by `build_db.py` from:

- A scrape of Dawaai (brand names and generic formulas)
- Pakistan Essential Medicines list
- Drug Registry of Pakistan
- Gazette SRO-1423
- A small supplementary list marked as unverified

The raw source files are not included in this repository. The data comes from public sources and was collected for educational purposes. If you own any of the source data and want it removed, please open an issue.

## Known limitations

- The database is mostly allopathic. Homeopathic and herbal medicines come back as unverified.
- Brands from the Drug Registry have no generic formula, so they get no interaction or generic lookup.
- The interaction rule set is small. It is not a full interaction database.
- Almost no price data, so price comparison is rarely possible.
- Urdu voice recognition handles brand names poorly. English mode is better for medicine names.
- AI output can be wrong. Do not use this app for real medical decisions.

## Privacy

Photos and voice notes are sent to Groq and Google (Gemini) for processing.
Do not upload real patient data, ID numbers or phone numbers.

## Author

Sameen, Islamia University of Bahawalpur
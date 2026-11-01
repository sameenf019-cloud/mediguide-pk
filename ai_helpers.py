"""
ai_helpers.py  -  MediGuide PK ke naye features (app.py inhein import karta hai):

    ocr_image(bytes, mime_type)          -> text   (Gemini Vision, prescription/lab report photo ya PDF)
    transcribe_audio(bytes, name, lang)  -> text   (Groq Whisper, awaaz se text)
    explain_lab_report(text)             -> Urdu   (Groq, lab report ki aasaan wazahat)

Zaroori environment variables:
    GROQ_API_KEY      (pehle se hai)
    GEMINI_API_KEY    (naya, aistudio.google.com se banayein)
Optional:
    GEMINI_MODEL      (default neeche). Model ka naam badal jaye ya "not found" error aaye
                      to yahan naya naam set kar dein.
"""
import os
from groq import Groq

# Free-tier wala vision-capable Gemini model. Naam time ke sath badalte rehte hain,
# is liye env variable GEMINI_MODEL se override ho sakta hai.
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
WHISPER_MODEL = "whisper-large-v3"
# Whisper ko aam dawaon ke naam ka ishara (spelling behtar aati hai). Chhota rakhein (~224 tokens limit).
DRUG_HINT = ("Medicine names: Panadol, Paracetamol, Brufen, Ibuprofen, Augmentin, Disprin, Aspirin, Calpol, "
             "Flagyl, Ventolin, Risek, Arinac, Surbex Z, Amoxil, Ponstan, Zyrtec, Voltral, Cefspan, "
             "Warfarin, Metformin, Amlodipine, Omeprazole, Azithromycin, Ciprofloxacin.")
# Khamoshi/shor par Whisper aksar aakhir mein ye lafz khud likh deta hai
_WHISPER_JUNK = ("موسیقی",)
LAB_MODEL = "openai/gpt-oss-20b"

OCR_PROMPT = """You are an OCR engine. Transcribe ALL the text in this image/document exactly as written.
Rules:
- Do NOT correct spelling, do NOT guess, do NOT add anything that is not written.
- Keep one medicine (or one test result) per line, as in the original.
- Keep doses and schedules exactly (for example 1+0+1, 500mg, TDS).
- If a word is unreadable, write [unclear] in its place.
- Output only the transcribed text, nothing else."""

LAB_SYSTEM_PROMPT = """Tum MediGuide PK ke helper ho. Tumhe ek lab report ka text milega.
Report aasaan Urdu (Urdu script) mein likho, Markdown ke sath.

Format:
1. Chhota sa khulasa (2-3 jumlay).
2. Ek table: test ka naam | report mein likhi value | report mein likhi normal range | nishan. Nishan value ko report ki range se mila kar likho: normal / kam / zyada (range na ho to khali chhodo).
3. Un tests ki chhoti wazahat jo report ki range se bahar hain: SIRF ye likho ke test kya napta hai aur value range se kam hai ya zyada.

STRICT RULES:
- Agar report mein ek se zyada tareekhon ke columns hon, to sirf SAB SE NAYI tareekh ki values table mein do, khulasay mein saaf likho ke kaun si tareekh ki values hain, aur ye bhi likho ke report mein purani tareekhon ki values bhi hain (doctor se un ka muqabla karwayein).
- Normal range SIRF wohi likho jo report mein khud likhi hai. Agar range report mein nahi hai to likho "report mein range nahi di gayi". Apni taraf se range mat banao.
- Kisi bimari ki tashkhees (diagnosis) mat karo. Ye mat kaho ke "aap ko ye bimari hai".
- Value ke kam ya zyada hone ki WAJOOHAAT ya mumkina bimariyan BILKUL mat likho (jaise anemia, iron ki kami, infection, soozish). Kisi bimari ya kami ka naam mat lo.
- Agar baqi values normal hon to ye mat kaho ke koi bari masla hai; sirf yeh kaho ke ye value range se bahar hai aur doctor ko dikhayein.
- Koi dawa, dose ya ilaaj mat suggest karo.
- Agar koi value normal range se bahar ho to kaho ke ye apne doctor ko dikhayein.
- Agar text mein lab report nazar na aaye ya bohat adhoora ho to saaf likho ke report samajh nahi aayi.
- Report ke end mein likho: یہ صرف معلومات ہیں، ڈاکٹر سے رپورٹ کا مشورہ ضرور کریں۔"""


def _groq():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY set nahi hai.")
    return Groq(api_key=key)


def ocr_image(data: bytes, mime_type: str) -> str:
    """Tasveer ya PDF se text nikalta hai (Gemini Vision)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY set nahi hai. aistudio.google.com se key banayein, "
            "phir: setx GEMINI_API_KEY \"apni_key\" aur terminal dobara kholein."
        )
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai install nahi hai. Chalayein: pip install google-genai")

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), OCR_PROMPT],
        config=types.GenerateContentConfig(temperature=0),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Tasveer se koi text nahi nikla. Saaf tasveer ke sath dobara try karein.")
    return text


def transcribe_audio(data: bytes, filename: str = "voice.wav", language: str = "ur") -> str:
    """Awaaz ko text mein badalta hai (Groq Whisper). language: 'ur' ya 'en'."""
    client = _groq()
    result = client.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=(filename or "voice.wav", data),
        language=language,
        prompt=DRUG_HINT,
        temperature=0,
    )
    text = result if isinstance(result, str) else getattr(result, "text", "")
    text = (text or "").strip()
    for junk in _WHISPER_JUNK:
        if text.endswith(junk):
            text = text[: -len(junk)].strip()
    if not text:
        raise RuntimeError("Awaaz se koi text nahi nikla. Dobara record karein.")
    return text


def explain_lab_report(report_text: str) -> str:
    """Lab report ki aasaan Urdu wazahat (koi diagnosis ya ilaaj nahi)."""
    client = _groq()
    response = client.chat.completions.create(
        model=LAB_MODEL,
        messages=[
            {"role": "system", "content": LAB_SYSTEM_PROMPT},
            {"role": "user", "content": f"Lab report text:\n{report_text}"},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content
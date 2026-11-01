import os
import re
import json
import time
from groq import Groq
from agent_tools import match_medicines_db, check_interactions, find_affordable_generics

# ------------------------------------------------------------------
# API KEY (environment variable se)
# PowerShell:  $env:GROQ_API_KEY="apni_key"
# Permanent:   setx GROQ_API_KEY "apni_key"
# ------------------------------------------------------------------
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError(
        "GROQ_API_KEY environment variable set nahi hai. "
        "console.groq.com se key banayein aur environment variable set karein."
    )
client = Groq(api_key=api_key)

# ------------------------------------------------------------------
# TOOLS (agent ko 3 tools ki description)
# ------------------------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "match_medicines_db",
            "description": "OCR se aane wali dawaiyon ko database mein match karta hai aur unka formula nikalta hai.",
            "parameters": {
                "type": "object",
                "properties": {
                    "extracted_medicines": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["extracted_medicines"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_affordable_generics",
            "description": "Dawa ka formula (generic) aur uski price de kar same formula wali dawaiyan dhoondta hai.",
            "parameters": {
                "type": "object",
                "properties": {
                    "formula": {"type": "string"},
                    "original_price_str": {"type": "string"},
                },
                "required": ["formula", "original_price_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_interactions",
            "description": "Dawaiyon ki list de kar unka aapas mein reaction (interaction) check karta hai.",
            "parameters": {
                "type": "object",
                "properties": {
                    "verified_medicines_list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "generic_formula": {"type": "string"}
                            },
                        },
                    }
                },
                "required": ["verified_medicines_list"],
            },
        },
    },
]

# ------------------------------------------------------------------
# SYSTEM PROMPT (sirf EK baar, safety rules ke sath)
# ------------------------------------------------------------------
SYSTEM_PROMPT = """Tum MediGuide PK ke expert Pharmacist Agent ho.
Steps:
1. 'match_medicines_db' chalao dawaiyan verify karne ke liye. Sirf dawa ka naam bhejo, dose ya schedule (jaise 1+0+1) mat bhejo. Strength (jaise 625mg) naam ke sath bhej sakte ho.
   Agar dawa ka naam Urdu script mein ho (jaise بروفن), to tool mein bhejne se pehle uski English (Latin) spelling likho (جیسے Brufen). Agar yaqeen na ho to jo likha hai wahi bhejo. Report mein asal naam bhi dikhao.
2. Jin dawaiyon ka generic formula 'verified_medicines' mein mila, un ke liye 'find_affordable_generics' chalao. Agar price maloom na ho to original_price_str mein "N/A" bhejo.
3. Sirf 'verified_medicines' ke formulas par 'check_interactions' chalao.
Apni final report aasan Urdu mein tables aur bullet points ke sath banao.

STRICT RULES:
- Medicine verification, price, generics aur interactions ke liye SIRF tools ka data use karo. Apni taraf se kuch mat banao.
- Agar tool result mein 'closest_matches' ho: likho "Exact match nahi mila" aur qareebi naam dikhao, aur kaho ke doctor ya pharmacist se confirm karein. Is dawa ko verified mat samjho aur interaction check mein shamil mat karo.
- Agar koi dawa 'unverified' ho to uske samne "غیر تصدیق شدہ" likho aur us ke liye aage kuch mat likho.
- 'closest_matches' ka matlab ye NAHI ke wohi dawa hai. Report mein saaf likho ke qareebi naam alag dawa bhi ho sakta hai, is liye isay parchi wali dawa mat samjho.
- Agar koi dawa closest_matches ya unverified mein ho to report mein saaf likho ke interaction check mukammal nahi hai.
- Agar find_affordable_generics ka 'price_comparison' false ho to "sasti" mat likho. Sirf "same formula wali dawaiyan (database ke mutabiq)" likho.
- Agar interactions khali hon to "safe" mat likho. Likho: "hamare database mein koi interaction nahi mila, ye safe hone ka saboot nahi."
- Agar verified dawa ka 'match_type' 'name_match' ho aur parchi par strength likhi ho, to report mein saaf likho ke parchi ki strength database mein nahi mili ya confirm karni hai, aur database wali strength bhi likho.
- Manufacturer, company ya brand tab hi likho jab tool ne diya ho. Warna kuch mat likho.
- Report mein tool ke andar ke alfaz (jaise verified_medicines, closest_matches, match_type) mat likho. Un ki jagah aam Urdu mein likho (jaise 'تصدیق شدہ', 'قریبی نام').
- Kabhi bhi maximum daily dose mat likho. User ko kaho ke doctor ya pharmacist se pooche.
- Kabhi mat likho "doctor ki hidayat ke mutabiq". Tumhe nahi pata nuskha kisne likha.
- Report ke end mein likho: یہ صرف معلومات ہیں، ڈاکٹر یا فارماسسٹ سے تصدیق ضرور کریں۔"""


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def chat_with_retry(retries=4, **kwargs):
    """Groq ke random 'tool call validation failed' aur rate limit (429) errors par dobara try karta hai."""
    for attempt in range(retries):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            is_glitch = "tool call validation failed" in msg or "tool_use_failed" in msg
            is_rate = "rate limit" in msg or "429" in msg or "rate_limit_exceeded" in msg
            if attempt < retries - 1 and (is_glitch or is_rate):
                wait = 1
                if is_rate:
                    m = re.search(r"try again in ([\d.]+)\s*(ms|s)", msg)
                    wait = (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) + 1) if m else 10
                    wait = min(wait, 30)
                time.sleep(wait)
                continue
            raise


def run_tool(func_name, args):
    """Tool chalata hai. Error aaye to crash ke bajaye error result wapas deta hai."""
    try:
        if func_name == "match_medicines_db":
            return match_medicines_db(args.get("extracted_medicines"))
        if func_name == "find_affordable_generics":
            return find_affordable_generics(args.get("formula"), args.get("original_price_str"))
        if func_name == "check_interactions":
            return check_interactions(args.get("verified_medicines_list"))
        return {"error": "Tool not found"}
    except Exception as e:
        return {"error": f"Tool failed: {e}"}


# ------------------------------------------------------------------
# MAIN AGENT
# ------------------------------------------------------------------
def run_pharmacist_agent(ocr_text):
    print("\n🤖 Agent: Parchi parh raha hoon...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Prescription text: {ocr_text}"},
    ]

    final_text = None

    # Agent loop: max 5 steps
    for step in range(5):
        response = chat_with_retry(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if not tool_calls:
            # Model ne tools ke baad seedha final report de di
            final_text = response_message.content
            break

        messages.append(response_message)

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            print(f"🛠️ Agent Tool Call: {func_name} ...")
            result = run_tool(func_name, args)
            print(f"   ↳ Result: {str(result)[:300]}")  # debugging

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": func_name,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Agar loop 5 steps mein tool calls hi karta raha, to final report alag se banao
    if not final_text:
        print("🧠 Agent: Final report tayyar kar raha hoon...\n")
        final_response = chat_with_retry(
            model="openai/gpt-oss-120b",
            messages=messages,
        )
        final_text = final_response.choices[0].message.content

    return final_text


if __name__ == "__main__":
    mock_ocr = "Tab Panadol 500mg 1+0+1"
    print(f"📝 User Input: {mock_ocr}")
    final_report = run_pharmacist_agent(mock_ocr)
    print("\n✅ FINAL REPORT (URDU):\n", final_report)
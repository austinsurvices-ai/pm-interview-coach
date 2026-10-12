"""
Local backend for the AI Interview Coach.

Serves the frontend and makes the AI calls. Pick which AI to use with
PROVIDER in your .env file (see README):

    PROVIDER=ollama     free, runs on your own computer, no key needed (default)
    PROVIDER=gemini     free tier from Google, needs GEMINI_API_KEY
    PROVIDER=anthropic  Claude, paid, needs ANTHROPIC_API_KEY

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000 in your browser.
"""

import json
import os
import re
import urllib.error
import urllib.request
import threading
import time
from collections import defaultdict, deque

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Load settings from a .env file next to app.py, if there is one.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

PROVIDER = os.environ.get("PROVIDER", "ollama").strip().lower()
DEFAULT_MODELS = {
    "ollama": "llama3.1:8b",
    "gemini": "gemini-3.8-flash",
    "anthropic": "claude-sonnet-5-5",
}
MODEL = os.environ.get("MODEL") or DEFAULT_MODELS.get(PROVIDER, "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class FriendlyError(Exception):
    """An error whose message is safe and helpful to show on the page."""


def call_ollama(system: str, user: str, max_tokens: int) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FriendlyError(
                f"Ollama doesn't have the model '{MODEL}' yet. "
                f"In a terminal, run: ollama pull {MODEL}"
            )
        raise FriendlyError(f"Ollama returned an error ({e.code}): {e.read().decode()[:200]}")
    except urllib.error.URLError:
        raise FriendlyError(
            "Couldn't reach Ollama. Make sure the Ollama app is installed and running "
            "(see README), then try again."
        )


def call_gemini(system: str, user: str, max_tokens: int) -> str:
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError:
        raise FriendlyError("Gemini support isn't installed. Run: pip install -r requirements.txt")
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise FriendlyError("GEMINI_API_KEY is not set. Add it to your .env file (see README).")
    client = genai.Client(api_key=key)  # keep a reference so it isn't closed mid-call
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""
    except errors.ClientError as e:
        if e.code in (400, 401, 403) and "key" in str(e).lower():
            raise FriendlyError("Your Gemini API key was rejected. Check GEMINI_API_KEY in .env (or in your host's environment settings).")
        if e.code == 404:
            raise FriendlyError(f"Gemini model '{MODEL}' wasn't found. Set MODEL in .env (see README).")
        if e.code == 429:
            raise FriendlyError("You've hit Gemini's free-tier limit. Wait a minute and try again.")
        raise


def call_anthropic(system: str, user: str, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError:
        raise FriendlyError("Claude support isn't installed. Run: pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise FriendlyError("ANTHROPIC_API_KEY is not set. Add it to your .env file (see README).")
    try:
        resp = anthropic.Anthropic().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise FriendlyError("Your Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env.")
    except anthropic.NotFoundError:
        raise FriendlyError(f"Model '{MODEL}' wasn't found. Set MODEL in .env (see README).")
    return "".join(block.text for block in resp.content if block.type == "text")


PROVIDERS = {"ollama": call_ollama, "gemini": call_gemini, "anthropic": call_anthropic}


def call_ai(system: str, user: str, max_tokens: int = 1500):
    if PROVIDER not in PROVIDERS:
        raise FriendlyError(f"PROVIDER '{PROVIDER}' isn't supported. Use ollama, gemini or anthropic.")
    return parse_json(PROVIDERS[PROVIDER](system, user, max_tokens))


def parse_json(text: str):
    """Pull the JSON out of the model's reply, even if it added prose or fences."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost [...] or {...} block.
    starts = [i for i in (cleaned.find("["), cleaned.find("{")) if i != -1]
    if starts:
        start = min(starts)
        end = cleaned.rfind("]" if cleaned[start] == "[" else "}")
        if end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError("The AI's reply wasn't valid JSON. Please try again.")


# ---------- Usage limits (protect your free AI quota when the app is public) ----------
PER_PERSON_PER_HOUR = int(os.environ.get("LIMIT_PER_PERSON_PER_HOUR", "30"))
TOTAL_PER_DAY = int(os.environ.get("LIMIT_TOTAL_PER_DAY", "400"))
_lock = threading.Lock()
_per_ip = defaultdict(deque)
_day = {"date": None, "count": 0}


def client_ip() -> str:
    # Hosts like Render put the visitor's real address first in X-Forwarded-For.
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or "unknown"


def check_limits():
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _lock:
        if _day["date"] != today:
            _day["date"], _day["count"] = today, 0
        if _day["count"] >= TOTAL_PER_DAY:
            raise FriendlyError("The coach has hit its daily limit. Please come back tomorrow.")
        calls = _per_ip[client_ip()]
        while calls and now - calls[0] > 3600:
            calls.popleft()
        if len(calls) >= PER_PERSON_PER_HOUR:
            raise FriendlyError("You've used the coach a lot this hour. Take a break and try again later.")
        calls.append(now)
        _day["count"] += 1


def field(data: dict, name: str, max_len: int) -> str:
    value = (data.get(name) or "").strip()
    if len(value) > max_len:
        raise FriendlyError(f"That's too long. Keep it under {max_len} characters.")
    return value


@app.route("/")
def index():
    # Works whether index.html is in static/ or right next to app.py.
    if os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return send_from_directory(STATIC_DIR, "index.html")
    return send_from_directory(BASE_DIR, "index.html")


def friendly_error(e: Exception) -> str:
    if isinstance(e, (FriendlyError, ValueError)):
        return str(e)
    print(f"Unexpected error: {e!r}")
    return f"Something went wrong: {e}"


@app.route("/api/questions", methods=["POST"])
def questions():
    data = request.get_json(force=True, silent=True) or {}
    try:
        role = field(data, "role", 200)
        context = field(data, "context", 4000)
        if not role:
            raise FriendlyError("Enter a role to generate relevant questions.")
        check_limits()
    except FriendlyError as e:
        return jsonify({"error": str(e)}), 429 if "limit" in str(e) or "a lot" in str(e) else 400

    system = (
        "You write product manager interview questions. Return ONLY a JSON "
        'object of the form {"questions": [...]}, no prose, no markdown fences.\n'
        'Each item: {"question": "...", "focus": "one of: prioritization, '
        'metrics, stakeholder-mgmt, strategy, execution, product-sense"}'
    )
    user = (
        f"Role: {role}\nContext: {context or 'none provided'}\n\n"
        "Write 5 realistic, role-specific interview questions a hiring "
        "panel would actually ask for this role. Vary the focus area "
        "across questions."
    )

    try:
        result = call_ai(system, user, max_tokens=1500)
        if isinstance(result, dict):  # e.g. {"questions": [...]}
            result = next((v for v in result.values() if isinstance(v, list)), [])
        if not result:
            raise ValueError("The AI didn't return any questions. Please try again.")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": friendly_error(e)}), 500


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json(force=True, silent=True) or {}
    try:
        question = field(data, "question", 1000)
        answer = field(data, "answer", 6000)
        if not question or not answer:
            raise FriendlyError("Write an answer before asking for feedback.")
        check_limits()
    except FriendlyError as e:
        return jsonify({"error": str(e)}), 429 if "limit" in str(e) or "a lot" in str(e) else 400

    system = """You are a rigorous but fair PM interview coach. Score the candidate's answer against this rubric, each 1-5:
- relevance: does it actually answer what was asked?
- structure: is there a clear framework/flow (e.g. situation-action-result, prioritization logic)?
- specificity: concrete details, numbers, real examples vs. generic statements?
- business_impact: does it connect to a business outcome (revenue, retention, cost, growth, etc.)?
- clarity: is it easy to follow, concise, well-communicated?
- ownership: does the candidate describe what THEY personally did/decided, vs. describing what "the team" did in vague, diffuse terms?
- tradeoffs: does the candidate name a real trade-off or alternative they considered/rejected, and why?

Also give:
- annotations: 3-6 short verbatim quotes (5-12 words each, must appear EXACTLY in the answer) tagged "strength" or "issue", each with a one-sentence note.
- stronger_version: a rewritten version of the answer that would score higher, 3-5 sentences, same underlying experience.
- confidence: 1-5, your own confidence that this grading is correct (be honest -- lower it if the answer is ambiguous or you're guessing at the candidate's real experience).

Return ONLY JSON, no prose, no markdown fences:
{"scores": {"relevance": n, "structure": n, "specificity": n, "business_impact": n, "clarity": n, "ownership": n, "tradeoffs": n},
 "annotations": [{"quote": "...", "type": "strength|issue", "note": "..."}],
 "stronger_version": "...",
 "confidence": n}"""
    user = f"Question: {question}\n\nCandidate's answer: {answer}"

    try:
        result = call_ai(system, user, max_tokens=2000)
        if not isinstance(result, dict) or "scores" not in result:
            raise ValueError("The AI's feedback was missing scores. Please try again.")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": friendly_error(e)}), 500


if __name__ == "__main__":
    print(f"Using {PROVIDER} with model {MODEL}")
    print("Open http://localhost:5000 in your browser")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host="127.0.0.1", port=port)

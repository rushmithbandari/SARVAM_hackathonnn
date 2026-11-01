"""
SHARK TANK SIMULATOR — WEB EDITION
==================================
Flask backend that reuses the Sarvam AI brains from shark_tank.py.
The browser records your mic (WAV), the backend runs STT -> LLM -> TTS
and returns each shark line with playable audio.

Run:    ../venv/bin/python webapp/app.py    ->  http://localhost:5050
"""

import os
import random
import sys
import uuid

from flask import Flask, jsonify, request, send_file, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)

import shark_tank as st  # noqa: E402  (loads .env, creates Sarvam client)

AUDIO_DIR = os.path.join(BASE, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
SESSIONS = {}


# ------------------------------------------------------------- helpers -----

def apply_lang(session):
    """Point the shared shark_tank globals at this session's language."""
    lang = session["lang"]
    st.LANG_CODE = lang["code"]
    st.SPEECH_STYLE = lang["style"]
    st.SIGNATURES = lang["signatures"]
    st.DEAL_LINE = lang["deal_line"]
    st.OUT_LINE = lang["out_line"]


def get_session(required_phase=None):
    sid = request.form.get("session_id") or (request.get_json(silent=True) or {}).get("session_id")
    session = SESSIONS.get(sid)
    if not session:
        return None, (jsonify({"error": "Unknown session — start a new show."}), 404)
    if required_phase and session["phase"] != required_phase:
        return None, (jsonify({"error": f"Wrong phase: {session['phase']}"}), 409)
    return session, None


def founder_text(session, audio_file):
    """Save browser WAV (or take typed text) -> transcript via saaras:v3."""
    if audio_file and audio_file.filename:
        wav_path = os.path.join(
            AUDIO_DIR, f"{session['id']}_founder_{session['counter']:02d}.wav"
        )
        audio_file.save(wav_path)
        apply_lang(session)
        return st.listen(wav_path)
    return (request.form.get("text") or "").strip()


def shark_audio(session, shark, text):
    """TTS a shark line -> (filename, url)."""
    apply_lang(session)
    fname = f"{session['id']}_{session['counter']:02d}_{shark['name'].split()[0].lower()}.wav"
    st.tts_to_file(text, shark["speaker"], os.path.join(AUDIO_DIR, fname))
    session["counter"] += 1
    return fname, f"/audio/{fname}"


def line_payload(shark, text, url, cue=None):
    data = {
        "name": shark["name"],
        "tag": shark["tag"],
        "voice": shark["speaker"],
        "text": text,
        "audio": url,
    }
    if cue:
        data["cue"] = cue
    return data


def question_prompt(shark):
    return {
        "role": "system",
        "content": (
            shark["persona"] + " " + st.signature_rules(shark)
            + " Ask your ONE question now. Nothing else."
        ),
    }


# -------------------------------------------------------------- routes -----

@app.route("/")
def index():
    return send_file(os.path.join(BASE, "index.html"))


@app.route("/audio/<path:fname>")
def audio(fname):
    return send_from_directory(AUDIO_DIR, fname)


@app.route("/api/languages")
def languages():
    return jsonify(
        [{"key": k, "label": v["label"]} for k, v in st.LANGUAGES.items()]
    )


@app.route("/api/start", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}
    sid = uuid.uuid4().hex[:12]
    lang = st.LANGUAGES.get(str(data.get("lang", "1")), st.LANGUAGES[st.DEFAULT_LANG])
    SESSIONS[sid] = {
        "id": sid,
        "founder": (data.get("founder") or "").strip() or "Founder",
        "company": (data.get("company") or "").strip() or "the startup",
        "lang": lang,
        "rounds": 2 if str(data.get("rounds")) == "2" else 1,
        "transcript": [],
        "history": [],
        "round": 1,
        "si": 0,
        "counter": 1,
        "phase": "await_pitch",
    }
    return jsonify({"session_id": sid})


@app.route("/api/switch_lang", methods=["POST"])
def switch_lang():
    session, err = get_session()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    lang = st.LANGUAGES.get(str(data.get("lang", "")))
    if not lang:
        return jsonify({"error": "Unknown language"}), 400
    session["lang"] = lang
    note = f"(Language switched by founder — from now on everyone speaks {lang['label']}.)"
    session["transcript"].append(note)
    session["history"].append({"role": "system", "content": note})
    return jsonify({"ok": True, "label": lang["label"]})


@app.route("/api/pitch", methods=["POST"])
def pitch():
    session, err = get_session("await_pitch")
    if err:
        return err
    text = founder_text(session, request.files.get("audio"))
    if not text:
        return jsonify({"error": "Didn't catch that — speak again or type it."}), 400

    session["transcript"].append(f"FOUNDER ({session['company']}): {text}")
    apply_lang(session)
    session["history"] = [
        {
            "role": "system",
            "content": st.system_context(
                session["founder"], session["company"], session["transcript"]
            ),
        }
    ]

    shark = st.SHARKS[0]
    question = st.chat(session["history"] + [question_prompt(shark)])
    fname, url = shark_audio(session, shark, question)
    session["transcript"].append(f"{shark['name']}: {question}")
    session["history"].append({"role": "assistant", "content": question})
    session["phase"] = "grill"

    return jsonify(
        {
            "heard": text,
            "lines": [line_payload(shark, question, url)],
            "next": "answer",
        }
    )


@app.route("/api/answer", methods=["POST"])
def answer():
    session, err = get_session("grill")
    if err:
        return err
    text = founder_text(session, request.files.get("audio"))
    if not text:
        return jsonify({"error": "Didn't catch that — speak again or type it."}), 400

    session["transcript"].append(f"FOUNDER: {text}")
    session["history"].append({"role": "user", "content": text})
    apply_lang(session)

    shark = st.SHARKS[session["si"]]
    others = [x for x in st.SHARKS if x is not shark]
    interjector = random.choice(others)
    cut = st.chat(
        session["history"]
        + [
            {
                "role": "system",
                "content": interjector["persona"]
                + " "
                + st.signature_rules(interjector)
                + " You INTERRUPT right after the founder's last answer, "
                "before anyone else can speak. ONE punchy sentence: a "
                "suspicion, a compliment, or a rapid-fire follow-up question.",
            }
        ]
    )
    cut_fname, cut_url = shark_audio(session, interjector, cut)
    session["transcript"].append(f"{interjector['name']} (interrupts): {cut}")
    session["history"].append({"role": "assistant", "content": cut})
    lines = [line_payload(interjector, cut, cut_url, cue="cuts in")]

    grill_done = (
        session["si"] == len(st.SHARKS) - 1 and session["round"] == session["rounds"]
    )
    if grill_done:
        session["phase"] = "ready_deliberate"
        return jsonify({"heard": text, "lines": lines, "next": "deliberate"})

    session["si"] += 1
    if session["si"] >= len(st.SHARKS):
        session["si"] = 0
        session["round"] += 1
    nxt = st.SHARKS[session["si"]]
    question = st.chat(session["history"] + [question_prompt(nxt)])
    q_fname, q_url = shark_audio(session, nxt, question)
    session["transcript"].append(f"{nxt['name']}: {question}")
    session["history"].append({"role": "assistant", "content": question})
    lines.append(line_payload(nxt, question, q_url))

    return jsonify({"heard": text, "lines": lines, "next": "answer"})


@app.route("/api/force_deliberate", methods=["POST"])
def force_deliberate():
    """Founder exits the tank early — jump straight to deliberation."""
    session, err = get_session("grill")
    if err:
        return err
    note = "(Founder left the tank early — skipping straight to deliberation.)"
    session["transcript"].append(note)
    session["history"].append({"role": "system", "content": note})
    session["phase"] = "ready_deliberate"
    return jsonify({"ok": True})


@app.route("/api/deliberate", methods=["POST"])
def deliberate():
    session, err = get_session("ready_deliberate")
    if err:
        return err
    session["phase"] = "deliberating"
    apply_lang(session)
    lines = []
    for idx, shark in enumerate(st.SHARKS):
        interrupt_note = (
            " You INTERRUPT the debate: directly challenge or build on what "
            "the other shark just said. Start mid-conversation, no greetings."
            if idx > 0
            else " You open the debate: your raw take on the pitch, max 2 sentences."
        )
        take = st.chat(
            session["history"]
            + [
                {
                    "role": "system",
                    "content": shark["persona"]
                    + " "
                    + st.signature_rules(shark)
                    + interrupt_note
                    + " No question for the founder, just your take. Max 2 sentences.",
                }
            ]
        )
        fname, url = shark_audio(session, shark, take)
        session["transcript"].append(f"{shark['name']} (deliberation): {take}")
        session["history"].append({"role": "assistant", "content": take})
        lines.append(line_payload(shark, take, url))
    session["phase"] = "ready_verdicts"
    return jsonify({"lines": lines})


@app.route("/api/verdicts", methods=["POST"])
def verdicts():
    session, err = get_session("ready_verdicts")
    if err:
        return err
    session["phase"] = "done"
    apply_lang(session)

    results = []
    for shark in st.SHARKS:
        prompt = (
            f"It is final verdict time. You are {shark['name']} ({shark['tag']}). "
            "Based on the entire conversation, give YOUR verdict. Return ONLY "
            "valid JSON, no markdown fences: "
            '{"decision":"INVEST" or "OUT","amount_lakh":<number, 0 if OUT>,'
            '"equity_pct":<number, 0 if OUT>,'
            '"line":"<your spoken verdict, max 2 sentences>"}'
        )
        msgs = session["history"] + [{"role": "user", "content": prompt}]
        for attempt in (1, 2):
            raw = st.chat(msgs, temperature=0.4)
            try:
                v = st.parse_json(raw)
                break
            except Exception:
                if attempt == 2:
                    raise
        decision = str(v.get("decision", "OUT")).upper()
        if decision == "INVEST":
            line = v.get("line", "")
            if "%" not in line and "lakh" not in line.lower():
                line += " " + st.DEAL_LINE.format(
                    a=v.get("amount_lakh"), e=v.get("equity_pct")
                )
        else:
            line = f"{v.get('line', '')} {st.OUT_LINE}"
        fname, url = shark_audio(session, shark, line)
        session["transcript"].append(f"{shark['name']} VERDICT: {decision} — {line}")
        results.append(
            {
                "name": shark["name"],
                "tag": shark["tag"],
                "decision": decision,
                "amount_lakh": v.get("amount_lakh", 0) or 0,
                "equity_pct": v.get("equity_pct", 0) or 0,
                "text": line,
                "audio": url,
            }
        )

    total = sum(r["amount_lakh"] for r in results if r["decision"] == "INVEST")
    return jsonify({"verdicts": results, "total": total})


if __name__ == "__main__":
    print("=" * 56)
    print("  🦈 Shark Tank Simulator — Web Edition")
    print("  ➜  Open http://localhost:5050 in your browser")
    print("=" * 56)
    app.run(host="127.0.0.1", port=5050, debug=False)

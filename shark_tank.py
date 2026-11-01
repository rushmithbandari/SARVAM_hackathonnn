"""
SHARK TANK SIMULATOR  (Sarvam AI)
=================================
Pitch your startup BY VOICE, in the language you choose. Three AI sharks —
each with a distinct personality AND voice — grill you with follow-up
questions, INTERRUPT each other, and finally give INVEST / OUT verdicts
with deal offers.

Uses: bulbul:v3 (TTS, pace control), saaras:v3 (codemix STT),
      sarvam-105b-conversations (shark brains).

Usage:
    python shark_tank.py                 # mic loop, 1 question per shark
    python shark_tank.py --rounds 2      # 2 questions per shark
    python shark_tank.py --text          # type everything, no mic

In-session controls:
    Type 'exit' at any answer prompt  -> sharks skip ahead to the verdicts
    Press Ctrl+C                      -> abort immediately, transcript is saved
"""

import base64
import io
import json
import math
import os
import random
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime

import numpy as np

from sarvamai import SarvamAI, errors


def load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

# ---------------------------------------------------------------- config ---

CHAT_MODEL = "sarvam-105b-conversations"
TTS_MODEL = "bulbul:v3"
STT_MODEL = "saaras:v3"
SAMPLE_RATE = 16000
AUDIO_DIR = "shark_audio"

TTS_PACE = 1.15     # slightly faster than normal speech
PLAY_VOLUME = 0.65  # softer playback gain (afplay -v)

STT_CHUNK_SECONDS = 25  # real-time STT accepts <= 30s; stay safely under
MAX_RECORD_SECONDS = 180  # recording auto-stops after 3 minutes

ROUNDS = 1
for i, arg in enumerate(sys.argv):
    if arg == "--rounds" and i + 1 < len(sys.argv):
        ROUNDS = int(sys.argv[i + 1])
TEXT_ONLY = "--text" in sys.argv

# Spoken-language menu (shown at startup) — all 11 languages Bulbul v3 +
# saaras:v3 support. Each shark gets a native catchphrase + deal/OUT lines.
# `signatures` = each shark's catchphrase in that language (never the opener).
LANGUAGES = {
    "1": {
        "label": "Hinglish (Hindi + English mix)",
        "code": "hi-IN",
        "style": "spoken Hinglish — romanized Hindi mixed naturally with English startup words",
        "signatures": {
            "Karan Mehra": "Seedha point pe aao.",
            "Vikram Rao": "Market ka math dikhao.",
            "Naina Kapoor": "Customer wapas aayega ya nahi?",
        },
        "deal_line": "Main deal deta hoon: {a} lakh ke {e}% equity ke liye.",
        "out_line": "Is deal ke liye, I am OUT.",
    },
    "2": {
        "label": "English (Indian)",
        "code": "en-IN",
        "style": "spoken natural Indian English",
        "signatures": {
            "Karan Mehra": "Straight to the point.",
            "Vikram Rao": "Show me the market math.",
            "Naina Kapoor": "Will the customer come back?",
        },
        "deal_line": "My offer: {a} lakh rupees for {e}% equity.",
        "out_line": "For this deal, I am OUT.",
    },
    "3": {
        "label": "Hindi (shuddh)",
        "code": "hi-IN",
        "style": "spoken Hindi in Devanagari script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "सीधे मुद्दे पर आइए।",
            "Vikram Rao": "मार्केट का हिसाब दिखाइए।",
            "Naina Kapoor": "ग्राहक वापस आएगा या नहीं?",
        },
        "deal_line": "मेरी डील: {a} लाख, {e}% इक्विटी के लिए।",
        "out_line": "इस डील के लिए, I am OUT.",
    },
    "4": {
        "label": "Bengali",
        "code": "bn-IN",
        "style": "spoken Bengali in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "সরাসরি কথায় আসুন।",
            "Vikram Rao": "মার্কেটের হিসাব দেখান।",
            "Naina Kapoor": "কাস্টমার কি ফিরে আসবে?",
        },
        "deal_line": "আমার ডিল: {a} লাখ, {e}% ইকুইটির জন্য।",
        "out_line": "এই ডিলে আমি OUT।",
    },
    "5": {
        "label": "Gujarati",
        "code": "gu-IN",
        "style": "spoken Gujarati in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "સીધી વાત પર આવો.",
            "Vikram Rao": "માર્કેટનું ગણિત બતાવો.",
            "Naina Kapoor": "ગ્રાહક પાછો આવશે?",
        },
        "deal_line": "મારી ડીલ: {a} લાખ, {e}% ઇક્વિટી માટે.",
        "out_line": "આ ડીલમાં હું OUT છું.",
    },
    "6": {
        "label": "Kannada",
        "code": "kn-IN",
        "style": "spoken Kannada in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "ನೇರವಾಗಿ ಹೇಳಿ.",
            "Vikram Rao": "ಮಾರುಕಟ್ಟೆಯ ಲೆಕ್ಕಾಚಾರ ತೋರಿಸಿ.",
            "Naina Kapoor": "ಗ್ರಾಹಕರು ಮರಳಿ ಬರುತ್ತಾರಾ?",
        },
        "deal_line": "ನನ್ನ ಒಪ್ಪಂದ: {a} ಲಕ್ಷ, {e}% ಇಕ್ವಿಟಿಗೆ.",
        "out_line": "ಈ ಒಪ್ಪಂದಕ್ಕೆ ನಾನು OUT.",
    },
    "7": {
        "label": "Malayalam",
        "code": "ml-IN",
        "style": "spoken Malayalam in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "നേരിട്ട് കാര്യത്തിലേക്ക് വരിക.",
            "Vikram Rao": "മാർക്കറ്റ് കണക്ക് കാണിക്കൂ.",
            "Naina Kapoor": "കസ്റ്റമർ തിരിച്ച് വരുമോ?",
        },
        "deal_line": "എന്റെ ഡീൽ: {a} ലക്ഷം, {e}% ഇക്വിറ്റിക്ക്.",
        "out_line": "ഈ ഡീലിൽ ഞാൻ OUT ആണ്.",
    },
    "8": {
        "label": "Marathi",
        "code": "mr-IN",
        "style": "spoken Marathi in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "थेट मुद्द्यावर या.",
            "Vikram Rao": "मार्केटचे गणित दाखवा.",
            "Naina Kapoor": "ग्राहक पुन्हा येईल का?",
        },
        "deal_line": "माझी डील: {a} लाख, {e}% इक्विटीसाठी.",
        "out_line": "या डीलसाठी मी OUT आहे.",
    },
    "9": {
        "label": "Odia",
        "code": "od-IN",
        "style": "spoken Odia in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "ସିଧା କଥାରେ ଆସନ୍ତୁ।",
            "Vikram Rao": "ମାର୍କେଟର ହିସାବ ଦେଖାଅ।",
            "Naina Kapoor": "ଗ୍ରାହକ ଫେରି ଆସିବେ କି?",
        },
        "deal_line": "ମୋ ଡିଲ୍: {a} ଲକ୍ଷ, {e}% ଇକ୍ୱିଟି ପାଇଁ।",
        "out_line": "ଏହି ଡିଲ୍ ପାଇଁ ମୁଁ OUT।",
    },
    "10": {
        "label": "Punjabi",
        "code": "pa-IN",
        "style": "spoken Punjabi in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "ਸਿੱਧੀ ਗੱਲ ਤੇ ਆਓ।",
            "Vikram Rao": "ਮਾਰਕੀਟ ਦਾ ਹਿਸਾਬ ਦਿਖਾਓ।",
            "Naina Kapoor": "ਗਾਹਕ ਵਾਪਸ ਆਵੇਗਾ?",
        },
        "deal_line": "ਮੇਰੀ ਡੀਲ: {a} ਲੱਖ, {e}% ਐਕਵਿਟੀ ਲਈ।",
        "out_line": "ਇਸ ਡੀਲ ਲਈ ਮੈਂ OUT ਹਾਂ।",
    },
    "11": {
        "label": "Tamil",
        "code": "ta-IN",
        "style": "spoken Tamil in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "நேரடியாகச் சொல்லுங்க.",
            "Vikram Rao": "சந்தை கணக்கைக் காட்டுங்க.",
            "Naina Kapoor": "கஸ்டமர் திரும்ப வருவாங்களா?",
        },
        "deal_line": "என் டீல் இது: {a} லட்சம், {e}% ஈக்விட்டிக்கு.",
        "out_line": "இந்த டீலுக்கு நான் OUT.",
    },
    "12": {
        "label": "Telugu",
        "code": "te-IN",
        "style": "spoken Telugu in native script, keeping common English startup words as-is",
        "signatures": {
            "Karan Mehra": "నేరుగా చెప్పండి.",
            "Vikram Rao": "మార్కెట్ లెక్క చూపించండి.",
            "Naina Kapoor": "కస్టమర్ మళ్ళీ వస్తారా?",
        },
        "deal_line": "నా డీల్ ఇది: {a} లక్షలు, {e}% ఈక్విటీకి.",
        "out_line": "ఈ డీల్‌కి నేను OUT.",
    },
}
DEFAULT_LANG = "1"
LANG_CODE = LANGUAGES[DEFAULT_LANG]["code"]
SPEECH_STYLE = LANGUAGES[DEFAULT_LANG]["style"]
SIGNATURES = LANGUAGES[DEFAULT_LANG]["signatures"]
DEAL_LINE = LANGUAGES[DEFAULT_LANG]["deal_line"]
OUT_LINE = LANGUAGES[DEFAULT_LANG]["out_line"]

# --------------------------------------------------------------- sharks ----
# Each shark: display name, persona prompt, Bulbul speaker, coloured tag.

SHARKS = [
    {
        "name": "Karan Mehra",
        "tag": "THE BLADE",
        "speaker": "aditya",
        "persona": (
            "You are Karan Mehra, 'The Blade' — a brutally blunt Indian venture "
            "investor in the style of a tough Shark Tank India judge. You hate "
            "fluff, jargon and fake traction. You interrogate unit economics, "
            "burn, margins and why THIS founder. Punchy delivery, max 2 "
            "sentences. Occasional dry insults, never abusive. You get "
            "straight to business without greetings or warm-ups. Ask exactly "
            "ONE sharp question. No pleasantries."
        ),
    },
    {
        "name": "Vikram Rao",
        "tag": "THE GROWTH HAWK",
        "speaker": "varun",
        "persona": (
            "You are Vikram Rao, 'The Growth Hawk' — an ex-unicorn operator "
            "turned investor. You obsess over market size, distribution, "
            "moats and speed. You push founders on 'what stops a big player "
            "from copying you in 6 months?'. Energetic delivery, max 2 "
            "sentences. You dive straight into the numbers without greetings. "
            "Ask exactly ONE sharp question."
        ),
    },
    {
        "name": "Naina Kapoor",
        "tag": "THE BRAND BUILDER",
        "speaker": "tanya",
        "persona": (
            "You are Naina Kapoor, 'The Brand Builder' — a D2C and consumer "
            "brand expert. You care about customer love, retention, founder "
            "grit and whether the story sells. Warmer in tone but lethal on "
            "retention numbers. Polished delivery, max 2 sentences. You open "
            "with a short observation, not a catchphrase. Ask exactly ONE "
            "sharp question."
        ),
    },
]

PANEL_LINE = ", ".join(f"{s['name']} ({s['tag']})" for s in SHARKS)


class JumpToVerdict(Exception):
    """Raised when the founder types 'exit' — skip to deliberation/verdicts."""


# ------------------------------------------------------------ audio utils --

def tts_to_file(text, speaker, out_path):
    """Text -> wav via bulbul:v3 (paced), saved with dead air trimmed."""
    try:
        tts = client.text_to_speech.convert(
            text=text,
            language_code=LANG_CODE,
            speaker=speaker,
            model=TTS_MODEL,
            output_audio_codec="wav",
            pace=TTS_PACE,
        )
    except errors.BadRequestError:
        # Speaker may not support this language -> use model default voice.
        tts = client.text_to_speech.convert(
            text=text,
            language_code=LANG_CODE,
            model=TTS_MODEL,
            output_audio_codec="wav",
            pace=TTS_PACE,
        )
    audio = base64.b64decode(tts.audios[0])
    with open(out_path, "wb") as f:
        f.write(audio)
    _trim_wav_silence(out_path)
    return out_path


def _trim_wav_silence(path, pad_ms=200, threshold=150):
    """Cut the silence Sarvam pads around speech -> snappier conversation."""
    with wave.open(path, "rb") as wf:
        rate = wf.getframerate()
        width = wf.getsampwidth()
        channels = wf.getnchannels()
        pcm = wf.readframes(wf.getnframes())
    if width != 2:
        return
    audio = np.frombuffer(pcm, dtype=np.int16).reshape(-1, channels)
    loud = np.where(np.abs(audio).max(axis=1) > threshold)[0]
    if loud.size == 0:
        return
    pad = int(rate * pad_ms / 1000)
    start = max(0, loud[0] - pad)
    end = min(audio.shape[0], loud[-1] + pad)
    if start == 0 and end == audio.shape[0]:
        return
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(audio[start:end].tobytes())


def play(out_path):
    subprocess.run(["afplay", "-v", str(PLAY_VOLUME), out_path], check=False)


def speak(text, speaker, out_path):
    tts_to_file(text, speaker, out_path)
    play(out_path)


# --------------------------------------------------------- prefetch utils --
# Generation (LLM + TTS) of the NEXT line runs in a background thread while
# the CURRENT line is playing -> speakers follow each other with no dead air.

def prefetch(job):
    result = {}

    def runner():
        try:
            result["value"] = job()
        except Exception as exc:  # re-raised by wait_prefetch
            result["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t, result


def wait_prefetch(handle):
    t, result = handle
    t.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


def record_mic(wav_path):
    """Record mic until Enter pressed (auto-stops at MAX_RECORD_SECONDS)."""
    import sounddevice as sd

    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())

    print(
        f"  🔴 REC  ...speak now, press Enter to stop "
        f"(auto-stops at {MAX_RECORD_SECONDS // 60} min)"
    )
    done = threading.Event()

    def wait_for_enter():
        try:
            input()
        except EOFError:
            pass
        done.set()

    stopper = threading.Thread(target=wait_for_enter, daemon=True)
    stopper.start()
    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
    ):
        start = time.time()
        while not done.wait(0.1):
            if time.time() - start >= MAX_RECORD_SECONDS:
                print(f"  ⏱️  auto-stopped at {MAX_RECORD_SECONDS}s")
                break
    if not chunks:
        return False
    audio = np.concatenate(chunks)
    if audio.shape[0] < SAMPLE_RATE // 2:  # < 0.5 s -> treat as empty
        print("  (too short, nothing captured)")
        return False
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return True


def listen(wav_path):
    """Speech -> text via saaras:v3 codemix, in the chosen language.

    Real-time STT only accepts <= 30s per request, so long recordings are
    split into chunks and the transcripts are stitched back together.
    """
    with wave.open(wav_path, "rb") as wf:
        rate = wf.getframerate()
        width = wf.getsampwidth()
        channels = wf.getnchannels()
        nframes = wf.getnframes()
        pcm = wf.readframes(nframes)

    chunk_frames = rate * STT_CHUNK_SECONDS
    n_chunks = max(1, math.ceil(nframes / chunk_frames))
    parts = []
    for i in range(n_chunks):
        start = i * chunk_frames * width * channels
        end = min(nframes, (i + 1) * chunk_frames) * width * channels
        if end <= start:
            break
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(width)
            out.setframerate(rate)
            out.writeframes(pcm[start:end])
        for attempt in (1, 2):  # one retry per chunk on transient errors
            try:
                stt = client.speech_to_text.transcribe(
                    file=io.BytesIO(buf.getvalue()),
                    model=STT_MODEL,
                    mode="codemix",
                    language_code=LANG_CODE,
                )
                parts.append(stt.transcript.strip())
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"  (chunk {i + 1}/{n_chunks} failed: {exc})")
    text = " ".join(p for p in parts if p)
    if n_chunks > 1:
        print(f"  (long recording: transcribed in {n_chunks} parts)")
    return text.strip()


def get_founder_input(label, counter, history=None, transcript=None):
    """Press Enter to SPEAK (mic), or type the answer. Returns (text, wav).

    Typed commands:
        'lang'  -> switch the show language mid-session
        'exit'  -> skip to deliberation + verdicts
    """
    wav_path = os.path.join(AUDIO_DIR, f"founder_{counter:02d}.wav")
    while True:
        raw = input(f"{label}  [Enter=🎤 speak, type=answer, lang=switch, exit=verdicts] > ").strip()
        low = raw.lower()
        if low in {"exit", "quit"}:
            raise JumpToVerdict
        if low in {"lang", "language"}:
            new_label = setup_language()
            note = (
                f"(Language switched by founder — from now on everyone speaks "
                f"{new_label}.)"
            )
            if transcript is not None:
                transcript.append(note)
            if history is not None:
                history.append({"role": "system", "content": note})
            continue
        if raw or TEXT_ONLY:
            break
        try:
            ok = record_mic(wav_path)
        except Exception as exc:
            print(f"  (mic unavailable: {exc} — type your answer instead)")
            continue
        if not ok:
            continue
        text = listen(wav_path)
        print(f"  🗣️  You: {text}")
        return text, wav_path
    return raw, None


# --------------------------------------------------------------- llm utils -

def chat(messages, temperature=0.8):
    resp = client.chat.completions(
        model=CHAT_MODEL, messages=messages, temperature=temperature
    )
    return resp.choices[0].message.content.strip()


def parse_json(raw):
    start = raw.find("{")
    data, _ = json.JSONDecoder().raw_decode(raw[start:])
    return data


def signature_rules(shark):
    """Signature line is a rare spice: never the opener, max once per show."""
    return (
        f"Your signature line is: \"{SIGNATURES[shark['name']]}\" — NEVER start "
        "any reply with it; you may use it at most once in the entire session, "
        "only when it genuinely fits."
    )


def system_context(founder, company, transcript):
    return (
        "You are one judge in a Shark Tank India style pitch show. "
        f"Founder: {founder}. Startup: {company}.\n"
        f"Judges on the panel: {PANEL_LINE}.\n"
        "Spoken delivery style: " + SPEECH_STYLE + ".\n"
        "The conversation so far:\n" + "\n".join(transcript) +
        "\nKeep replies SHORT (max 2 sentences), spoken word-for-word, "
        "no markdown, no emojis, no stage directions. "
        "Never repeat a question, phrase or opening you (or another shark) "
        "already used — vary how you start every single line."
    )


# ------------------------------------------------------------------ show ---

def shark_line(shark, text, counter, cue=None, path=None, play_audio=True):
    if path is None:
        path = os.path.join(
            AUDIO_DIR, f"{counter:02d}_{shark['name'].split()[0].lower()}.wav"
        )
    header = f"🦈 {shark['name']} [{shark['tag']}]"
    if cue:
        header += f"  ✂️  {cue}"
    print(f"\n{header}:")
    print(f"   {text}")
    if play_audio:
        print("   🔊 ...")
        play(path)
    return path


def save_transcript(founder, company, transcript, total=None, partial=False):
    if not transcript:
        return
    note = " *(session ended mid-way)*" if partial else ""
    with open("shark_tank_transcript.md", "w") as f:
        f.write(
            f"# 🦈 Shark Tank Simulator — {datetime.now():%Y-%m-%d %H:%M}{note}\n\n"
            f"**Founder:** {founder}  \n**Startup:** {company}\n\n"
            + "\n".join(transcript)
        )
        if total is not None:
            f.write(f"\n\n**Total offer: ₹{total} lakh**\n")
    print("\n📝 Transcript saved to shark_tank_transcript.md")


def setup_language():
    global LANG_CODE, SPEECH_STYLE, SIGNATURES, DEAL_LINE, OUT_LINE
    print("\n🗣️  Choose the language for the whole show:")
    for key, lang in LANGUAGES.items():
        print(f"   {key:>2}. {lang['label']}")
    last = max(LANGUAGES)
    choice = (
        input(f"Language [1-{last}, Enter={LANGUAGES[DEFAULT_LANG]['label'].split(' (')[0]}] > ").strip()
        or DEFAULT_LANG
    )
    lang = LANGUAGES.get(choice, LANGUAGES[DEFAULT_LANG])
    LANG_CODE = lang["code"]
    SPEECH_STYLE = lang["style"]
    SIGNATURES = lang["signatures"]
    DEAL_LINE = lang["deal_line"]
    OUT_LINE = lang["out_line"]
    print(f"   → Sharks will speak {lang['label']}.")
    return lang["label"]


# ------------------------------------------------------------------ main ---

def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    counter = 1
    transcript = []

    print("=" * 62)
    print("        🦈  S H A R K   T A N K   S I M U L A T O R  🦈")
    print("              powered by Sarvam AI")
    print("=" * 62)

    setup_language()

    founder = input("\nFounder ka naam > ").strip() or "Founder"
    company = input("Startup ka naam > ").strip() or "the startup"

    print(
        f"\nNamaste {founder}! You get {ROUNDS} question(s) per shark, "
        "then the sharks interrupt each other in deliberation, then verdicts.\n"
        "At every prompt: press Enter to SPEAK into the mic,\n"
        "or type your answer instead.\n"
        "Type 'lang' to switch the show language anytime.\n"
        "Type 'exit' to skip to verdicts. Ctrl+C ends immediately.\n"
    )

    try:
        # -------------------------------------------- 1. the pitch ---------
        print("-" * 62)
        print("📢  THE PITCH — the tank is silent. Bhai, shuru karo!")
        pitch, _ = get_founder_input("", counter, transcript=transcript)
        counter += 1
        transcript.append(f"FOUNDER ({company}): {pitch}")

        history = [
            {"role": "system", "content": system_context(founder, company, transcript)}
        ]

        # -------------------------------------------- 2. grilling ----------
        jumped = False
        try:
            pending_q = None  # (shark, prefetch_handle)
            for rnd in range(1, ROUNDS + 1):
                for si, shark in enumerate(SHARKS):
                    print("-" * 62)
                    print(f"🎤  ROUND {rnd} — {shark['name']} [{shark['tag']}]")

                    qpath = os.path.join(
                        AUDIO_DIR,
                        f"{counter:02d}_{shark['name'].split()[0].lower()}.wav",
                    )
                    if pending_q is not None and pending_q[0] is shark:
                        question, qpath = wait_prefetch(pending_q[1])
                        pending_q = None
                    else:
                        print(f"  🤔 {shark['name']} is thinking...")
                        question = chat(
                            history
                            + [
                                {
                                    "role": "system",
                                    "content": shark["persona"]
                                    + " "
                                    + signature_rules(shark)
                                    + " Ask your ONE question now. Nothing else.",
                                }
                            ]
                        )
                        tts_to_file(question, shark["speaker"], qpath)
                    shark_line(shark, question, counter, path=qpath)
                    counter += 1
                    transcript.append(f"{shark['name']}: {question}")
                    history.append({"role": "assistant", "content": question})

                    answer, _ = get_founder_input(
                        "", counter, history=history, transcript=transcript
                    )
                    counter += 1
                    transcript.append(f"FOUNDER: {answer or '(silence)'}")
                    history.append(
                        {"role": "user", "content": answer or "(founder stayed silent)"}
                    )

                    # ---- another shark cuts in on the answer ----
                    others = [s for s in SHARKS if s is not shark]
                    interjector = random.choice(others)
                    cut = chat(
                        history
                        + [
                            {
                                "role": "system",
                                "content": interjector["persona"]
                                + " "
                                + signature_rules(interjector)
                                + " You INTERRUPT right after the founder's "
                                "last answer, before anyone else can speak. "
                                "ONE punchy sentence: a suspicion, a compliment, "
                                "or a rapid-fire follow-up question.",
                            }
                        ]
                    )
                    cpath = os.path.join(
                        AUDIO_DIR,
                        f"{counter:02d}_{interjector['name'].split()[0].lower()}.wav",
                    )
                    tts_to_file(cut, interjector["speaker"], cpath)

                    # While the interjection plays, generate the NEXT shark's
                    # question in the background -> no dead air between speakers.
                    more_rounds = not (
                        si + 1 == len(SHARKS) and rnd == ROUNDS
                    )
                    if more_rounds:
                        next_shark = SHARKS[(si + 1) % len(SHARKS)]
                        npath = os.path.join(
                            AUDIO_DIR,
                            f"{counter + 1:02d}_{next_shark['name'].split()[0].lower()}.wav",
                        )
                        nmsgs = list(history) + [
                            {
                                "role": "system",
                                "content": next_shark["persona"]
                                + " "
                                + signature_rules(next_shark)
                                + " Ask your ONE question now. Nothing else.",
                            }
                        ]

                        def gen_question(msgs=nmsgs, spk=next_shark["speaker"], path=npath):
                            q = chat(msgs)
                            tts_to_file(q, spk, path)
                            return q, path

                        pending_q = (next_shark, prefetch(gen_question))

                    shark_line(interjector, cut, counter, cue="cuts in", path=cpath)
                    counter += 1
                    transcript.append(f"{interjector['name']} (interrupts): {cut}")
                    history.append({"role": "assistant", "content": cut})
        except JumpToVerdict:
            jumped = True
            print("\n⏭️  The tank has heard enough — seedha verdict!")

        # -------------------------------------------- 3. deliberation ------
        print("-" * 62)
        print("🤝  DELIBERATION — the sharks interrupt each other")
        pending_take = None
        for idx, shark in enumerate(SHARKS):
            interrupt_note = (
                " You INTERRUPT the debate: directly challenge or build on what "
                "the other shark just said. Start mid-conversation, no greetings."
                if idx > 0
                else " You open the debate: your raw take on the pitch, max 2 sentences."
            )
            tpath = os.path.join(
                AUDIO_DIR,
                f"{counter:02d}_{shark['name'].split()[0].lower()}.wav",
            )
            if pending_take is not None:
                take, tpath = wait_prefetch(pending_take)
                pending_take = None
            else:
                print(f"  🤔 {shark['name']} is thinking...")
                take = chat(
                    history
                    + [
                        {
                            "role": "system",
                            "content": shark["persona"]
                            + " "
                            + signature_rules(shark)
                            + interrupt_note
                            + " No question for the founder, just your take. "
                            "Max 2 sentences.",
                        }
                    ]
                )
                tts_to_file(take, shark["speaker"], tpath)
            shark_line(shark, take, counter, path=tpath)
            counter += 1
            transcript.append(f"{shark['name']} (deliberation): {take}")
            history.append({"role": "assistant", "content": take})

            if idx + 1 < len(SHARKS):
                nxt = SHARKS[idx + 1]
                npath = os.path.join(
                    AUDIO_DIR,
                    f"{counter:02d}_{nxt['name'].split()[0].lower()}.wav",
                )
                nmsgs = list(history) + [
                    {
                        "role": "system",
                        "content": nxt["persona"]
                        + " "
                        + signature_rules(nxt)
                        + " You INTERRUPT the debate: directly challenge or "
                        "build on what the other shark just said. Start "
                        "mid-conversation, no greetings. No question for the "
                        "founder, just your take. Max 2 sentences.",
                    }
                ]

                def gen_take(msgs=nmsgs, spk=nxt["speaker"], path=npath):
                    t = chat(msgs)
                    tts_to_file(t, spk, path)
                    return t, path

                pending_take = prefetch(gen_take)

        # -------------------------------------------- 4. verdicts ----------
        print("-" * 62)
        print("⚖️   VERDICTS")
        print("  🤔 The sharks are deciding...")

        # All three verdict brains work in parallel.
        def verdict_job(shark):
            prompt = (
                f"It is final verdict time. You are {shark['name']} ({shark['tag']}). "
                "Based on the entire conversation, give YOUR verdict. Return ONLY "
                "valid JSON, no markdown fences: "
                '{"decision":"INVEST" or "OUT","amount_lakh":<number, 0 if OUT>,'
                '"equity_pct":<number, 0 if OUT>,'
                '"line":"<your spoken verdict, max 2 sentences>"}'
            )
            msgs = history + [{"role": "user", "content": prompt}]
            for attempt in (1, 2):
                raw = chat(msgs, temperature=0.4)
                try:
                    return parse_json(raw)
                except Exception:
                    if attempt == 2:
                        raise

        raw_verdicts = [wait_prefetch(prefetch(lambda s=s: verdict_job(s))) for s in SHARKS]

        # Build spoken lines, then TTS-pipeline while each verdict plays.
        spoken = []
        for shark, v in zip(SHARKS, raw_verdicts):
            decision = v.get("decision", "OUT").upper()
            if decision == "INVEST":
                line = v.get("line", "")
                if "%" not in line and "lakh" not in line.lower():
                    line += " " + DEAL_LINE.format(
                        a=v.get("amount_lakh"), e=v.get("equity_pct")
                    )
            else:
                line = f"{v.get('line', '')} {OUT_LINE}"
            spoken.append((shark, v, decision, line))

        verdicts = []
        pending_v = None
        for idx, (shark, v, decision, line) in enumerate(spoken):
            vpath = os.path.join(
                AUDIO_DIR,
                f"{counter:02d}_{shark['name'].split()[0].lower()}.wav",
            )
            if pending_v is not None:
                vpath = wait_prefetch(pending_v)
                pending_v = None
            else:
                tts_to_file(line, shark["speaker"], vpath)
            shark_line(shark, line, counter, path=vpath)
            counter += 1
            verdicts.append({"shark": shark["name"], **v})
            transcript.append(f"{shark['name']} VERDICT: {decision} — {line}")

            if idx + 1 < len(spoken):
                nshark, nline = spoken[idx + 1][0], spoken[idx + 1][3]
                npath = os.path.join(
                    AUDIO_DIR,
                    f"{counter:02d}_{nshark['name'].split()[0].lower()}.wav",
                )

                def gen_v(spk=nshark["speaker"], txt=nline, path=npath):
                    tts_to_file(txt, spk, path)
                    return path

                pending_v = prefetch(gen_v)

        # -------------------------------------------- 5. deal summary ------
        print("\n" + "=" * 62)
        print("📊  DEAL SUMMARY")
        print("=" * 62)
        for v in verdicts:
            if v.get("decision", "").upper() == "INVEST":
                print(f"  💰 {v['shark']}: ₹{v.get('amount_lakh')}L for {v.get('equity_pct')}%")
            else:
                print(f"  🚫 {v['shark']}: OUT")
        total = sum(
            v.get("amount_lakh", 0) or 0
            for v in verdicts
            if v.get("decision", "").upper() == "INVEST"
        )
        print(f"\n  Total money on the table: ₹{total} lakh")
        print(f"  Founder: {founder} | Startup: {company}")

        save_transcript(founder, company, transcript, total=total)
        print(f"🔊 All shark audio saved in {AUDIO_DIR}/")
        print("\nShukriya! Tank band. 🦈")

    except KeyboardInterrupt:
        print("\n\n⛔ Session ended mid-way.")
        save_transcript(founder, company, transcript, partial=True)
        print("The sharks will discuss this exit later. 🦈")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTank band. 🦈")

# 🦈 Shark Tank Simulator

**Rehearse your investor pitch — out loud, in your own language — against three AI sharks who talk back, interrupt you, and fight over your deal.**

Built entirely on the **Sarvam AI stack**: `bulbul:v3` (voices), `saaras:v3` (speech-to-text), `sarvam-105b-conversations` (shark brains).

---

## 📌 Problem Statement

> ### Good businesses die in bad pitches.
>
> India produces lakhs of first-time founders, but **realistic investor feedback is scarce, expensive and English-first**. Before facing a real investor, most founders get zero practice under real pressure — nobody asks the hard follow-up questions, nobody interrupts, nobody checks whether their numbers survive 30 seconds of scrutiny.
>
> Rehearsing in front of a mirror builds confidence, not resilience. Professional pitch coaching costs thousands per hour. And founders from Tier-2/3 India — who think in Hinglish, Telugu, Tamil or Kannada — are forced to rehearse their most important conversation in a language they don't dream in.
>
> **The gap we're filling:** a safe, repeatable, *spoken* pressure-test of a pitch — in the founder's own language — that behaves like a real investor room: interruptions, tough follow-ups, sharks arguing with each other, and a clear deal / no-deal verdict.

## 💡 What It Does

1. 🗣️ **Pick your language at startup** — any of the 11 Indian languages Sarvam supports
2. 📢 **Pitch out loud** — speak into your mic (or type); it transcribes you live
3. 🦈 **Get grilled live** — three shark personas, each with a distinct voice and investment lens:
   - **Karan Mehra — THE BLADE** *(voice: aditya)* — unit economics, burn, margins. Zero fluff tolerance.
   - **Vikram Rao — THE GROWTH HAWK** *(voice: varun)* — market size, moats, "what stops a big player from cloning you?"
   - **Naina Kapoor — THE BRAND BUILDER** *(voice: tanya)* — retention, customer love, founder grit
4. ✂️ **Get interrupted** — after your answers, a random shark cuts in with a rapid-fire reaction — just like the real tank
5. 🤝 **Watch the sharks fight** — in deliberation, they interrupt *each other* and challenge each other's takes
6. ⚖️ **Hear your verdicts** — INVEST (with a real offer: ₹lakh + equity %) or OUT, spoken dramatically in your language
7. 📝 **Walk away with receipts** — full transcript + deal summary + every shark line saved as audio

### Languages supported
Hinglish · English · Hindi (Devanagari) · Bengali · Gujarati · Kannada · Malayalam · Marathi · Odia · Punjabi · Tamil · Telugu

Each language comes with its own shark catchphrases and verdict lines — the show feels native, not translated.

## 🛠️ Sarvam AI Stack

| API | Model | Where it's used |
|-----|-------|-----------------|
| Speech-to-Text | `saaras:v3` (codemix) | Founder's spoken pitch & answers → text, in any supported language |
| Chat Completions | `sarvam-105b-conversations` | Shark personas, questions, interruptions, deliberation, verdicts |
| Text-to-Speech | `bulbul:v3` (11 languages, pace control) | Sharks speak aloud — distinct voice per shark |

## 🖥️ Two Ways to Play

| | 💻 **Terminal Edition** | 🌐 **Web Edition** |
|---|---|---|
| Look & feel | Classic CLI | Dark studio UI in your browser |
| Speaking | Mic via terminal (Enter to start/stop) | Mic **in the browser** — one-tap orb with live waveform |
| Best for | Quick rehearsals, hackathon demos from the terminal | Presentations, screen-sharing, showing off the UI |
| Extras | Auto-chunked long answers, transcript `.md` + all audio saved | Verdict cards with confetti, language switcher, zero setup prompts |
| Same brain | ✅ 3 shark personas, 11 languages, interrupts, verdicts | ✅ identical |

## 💻 Terminal Edition

**Features**
- 🗣️ Talk, don't type — push-to-talk mic loop with live transcription (`saaras:v3` codemix)
- 🦈 Three shark personas with **distinct Bulbul voices** (questions, interruptions, deliberation, verdicts — all spoken)
- ⚡ Pipelined prefetching: the next shark's line generates **while the current one plays** — no dead air between speakers
- ✂️ Silence trimming + pace control (`bulbul:v3`) for snappy, natural delivery
- 🌍 Switch language **mid-show** — type `lang`, pick a number, the sharks adapt instantly
- ⏭️ Type `exit` to skip straight to verdicts; Ctrl+C saves a partial transcript
- 📝 Every session leaves receipts: `shark_tank_transcript.md` + every shark line as `.wav`

**Run it**

```bash
# 1. Clone / enter the project
cd sarvam-test

# 2. One-time setup: virtual env + dependencies (Python 3.10+)
python3 -m venv venv
./venv/bin/pip install sarvamai sounddevice numpy

# 3. Add your API key to a .env file (never commit it!)
echo "SARVAM_API_KEY=your_key_here" > .env

# 4. Start the show 🎬
./venv/bin/python shark_tank.py
```

Options:

```bash
./venv/bin/python shark_tank.py --rounds 2   # 2 questions per shark (longer grilling)
./venv/bin/python shark_tank.py --text       # type instead of speaking (no mic needed)
```

> **macOS mic note:** on first run, allow microphone access for Terminal (System Settings → Privacy & Security → Microphone).

**In-session controls**

| Action | Effect |
|--------|--------|
| Press **Enter** | Start recording → speak → press Enter again to stop |
| Type your answer instead | Skips the mic |
| Type `lang` | **Switch the show language mid-session** — sharks continue in the new language |
| Type `exit` | Skip ahead — sharks go straight to deliberation + verdicts |
| **Ctrl+C** | End immediately — partial transcript is still saved |

Long answers are handled automatically: recordings are split into chunks and stitched, so you can talk past the 30-second STT limit (recordings auto-stop at 3 minutes).

## 🌐 Web Edition

**Features**
- 🎨 **Setup screen** — founder & startup names, 12 language chips, grill-intensity selector
- 🎙️ **Browser mic recording** — tap the orb to start/stop, with a live audio waveform; no terminal mic permissions
- ⌨️ **Speak or type** — every answer can be typed instead, great for demos without a mic
- 🦈 **Animated shark cards** — each shark glows with equalizer bars while their voice plays
- 💬 **Live transcript feed** — founder and shark bubbles stream in as the show unfolds, with red **"✂️ cuts in"** badges on interruptions
- 🌐 **Mid-show language switcher** — one click in the header, sharks acknowledge and continue
- ⚖️ **Verdict reveal** — cards flip in one by one, INVEST deals glow gold, 🚫 OUT stamps, **confetti** if you raise money
- 💰 **Deal summary** — total money on the table after the show
- ⚠️ Friendly error banners if the backend isn't running (it tells you the exact command to fix it)

**Run it**

```bash
# same setup as CLI (plus flask)
./venv/bin/pip install sarvamai sounddevice numpy flask

# start the studio
./venv/bin/python webapp/app.py
```

Then open **http://localhost:5050** in your browser.

**In-show controls**

| Action | Effect |
|--------|--------|
| Tap the 🎤 orb | Start recording → tap again to stop |
| Type in the box + **Send** | Answer without the mic |
| 🌐 button (header) | Switch the show language anytime |
| ⏭️ **Skip to verdicts** | End the grilling early, jump to deliberation + verdicts |
| 🔁 **New pitch** | Restart the show |

> The website runs locally — it needs the Flask backend **and** your own `.env` API key, so GitHub Pages can't host it. Clone, add your key, run.

## 📂 Project Structure

```
shark_tank.py            # the whole CLI show — personas, voice loop, verdicts
webapp/app.py            # web edition backend (Flask, reuses shark_tank brains)
webapp/index.html        # web edition studio UI
shark_tank_transcript.md # session transcript + deal summary (generated)
shark_audio/ webapp/audio/  # generated voice clips (gitignored)
.env                     # SARVAM_API_KEY (never committed)
```

## 🗺️ Roadmap

- 🔊 Real-time streaming conversation (Sarvam streaming STT + TTS) for zero-latency banter
- 📊 Pitch analytics: filler words, pace, answer depth — scored per round
- 🏛️ Vertical packs: healthcare investors, agri investors, consumer VCs
- 🏆 Multi-session leaderboard to track rehearsal progress

---

*Built with ❤️ and a healthy fear of Karan Mehra.*

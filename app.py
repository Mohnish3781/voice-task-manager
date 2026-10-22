import json
import math
import os
import random
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

from services.whisper_service import WhisperService
from services.llm_service import LLMService
from services.task_manager import TaskManager
from services.tts_service import TTSService
from services.help_service import HelpService

load_dotenv()

st.set_page_config(page_title="Voice Quest", page_icon="🎤", layout="wide")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
DEBUG = os.getenv("VTM_DEBUG") == "1"  # set VTM_DEBUG=1 to see debug prints


def debug(msg):
    if DEBUG:
        print(f"DEBUG: {msg}")


# Streaks and daily quests reset at midnight in this timezone. Change it to yours.
TIMEZONE = "Asia/Kolkata"
GAME_FILE = Path(__file__).resolve().parent / "game_state.json"

XP_VOICE_NOTE = 10
XP_TASK_ADDED = 15
XP_COMPLETE = {"high": 30, "medium": 20, "low": 10}
XP_STEP = 50  # level N starts at XP_STEP * (N - 1) ** 2

LEVEL_TITLES = [
    "Sleepy Sloth", "Tiny Planner", "Task Apprentice", "Focus Ranger",
    "Habit Knight", "Productivity Wizard", "Time Bender", "Quest Master",
    "Legendary Achiever", "Mythic Mind",
]
PRIORITY_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟢"}
CATEGORY_LABELS = {"client": "👤 Client", "business": "💼 Business", "personal": "🏠 Personal"}

PROMPTS = {
    "braindump": [
        "Tomorrow I need to call my mom, buy groceries, and finish my assignment before Friday.",
        "Remind me to drink more water, stretch for ten minutes, and sort out my desk tonight.",
        "I want to clean my room, plan a weekend trip, and wish my friend a happy birthday.",
        "Gym at six, laundry before dinner, and start the book I keep postponing.",
    ],
    "command": [
        "Add a task to book a dentist appointment.",
        "Mark the first task as complete.",
        "Add a task to call grandma this weekend.",
    ],
}

DAILY_QUESTS = [
    {"id": "voice", "icon": "🎙️", "title": "Say something", "desc": "Record one voice note", "key": "voice", "target": 1, "xp": 20},
    {"id": "added", "icon": "📝", "title": "Fill the log", "desc": "Add 3 tasks", "key": "added", "target": 3, "xp": 30},
    {"id": "done", "icon": "⚔️", "title": "Finish strong", "desc": "Complete 2 tasks", "key": "done", "target": 2, "xp": 40},
]
DAILY_BONUS_XP = 50

BADGES = [
    {"id": "first_words", "icon": "🎙️", "name": "First Words", "desc": "Record your first voice note",
     "test": lambda g, t: g["voice_sessions"] >= 1},
    {"id": "chatterbox", "icon": "🗣️", "name": "Chatterbox", "desc": "Record 10 voice notes",
     "test": lambda g, t: g["voice_sessions"] >= 10},
    {"id": "brain_dumper", "icon": "🧠", "name": "Brain Dumper", "desc": "Add 10 tasks by voice",
     "test": lambda g, t: g["voice_tasks_added"] >= 10},
    {"id": "first_win", "icon": "⚔️", "name": "First Win", "desc": "Complete your first task",
     "test": lambda g, t: g["total_completed"] >= 1},
    {"id": "slayer", "icon": "🐉", "name": "Task Slayer", "desc": "Complete 10 tasks",
     "test": lambda g, t: g["total_completed"] >= 10},
    {"id": "unstoppable", "icon": "🚀", "name": "Unstoppable", "desc": "Complete 25 tasks",
     "test": lambda g, t: g["total_completed"] >= 25},
    {"id": "self_care", "icon": "💖", "name": "Self-Care Hero", "desc": "Complete 3 personal tasks",
     "test": lambda g, t: sum(1 for x in t if x.get("completed") and x.get("category") == "personal") >= 3},
    {"id": "on_fire", "icon": "🔥", "name": "On Fire", "desc": "Reach a 3 day streak",
     "test": lambda g, t: g["best_streak"] >= 3},
    {"id": "week_warrior", "icon": "⚡", "name": "Week Warrior", "desc": "Reach a 7 day streak",
     "test": lambda g, t: g["best_streak"] >= 7},
    {"id": "clean_sweep", "icon": "🧹", "name": "Clean Sweep", "desc": "Finish every task on a list of 3 or more",
     "test": lambda g, t: len(t) >= 3 and all(x.get("completed") for x in t)},
    {"id": "level5", "icon": "👑", "name": "Level 5", "desc": "Reach level 5",
     "test": lambda g, t: level_from_xp(g["xp"]) >= 5},
]

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
THEME_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@500;600;700;800&display=swap');

:root{
  --ink:#1B1340; --mist:#EEF0FF; --grape:#7C4DFF; --tang:#FF8A3D; --pink:#FF5FA2;
  --lime:#B8F04A; --sky:#4CC9F0; --gold:#FFC93C;
  --line:2.5px solid #1B1340; --pop:4px 4px 0 #1B1340;
}
.stApp{background:var(--mist);color:var(--ink);font-family:'Nunito',sans-serif;}
.stApp p,.stApp label,.stApp li,.stApp input,.stApp textarea,.stMarkdown,.stCaption{font-family:'Nunito',sans-serif;color:var(--ink);}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5{font-family:'Fredoka',sans-serif;color:var(--ink);}
.block-container{padding-top:1.6rem;max-width:1280px;}
section[data-testid="stSidebar"]{background:#fff;border-right:var(--line);}

/* buttons */
.stButton>button,.stFormSubmitButton>button{font-family:'Nunito',sans-serif;font-weight:800;color:var(--ink);background:#fff;
  border:var(--line);border-radius:14px;box-shadow:3px 3px 0 var(--ink);transition:transform .08s,box-shadow .08s;}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translate(-1px,-1px);box-shadow:5px 5px 0 var(--ink);border-color:var(--ink);color:var(--ink);}
.stButton>button:active,.stFormSubmitButton>button:active{transform:translate(3px,3px);box-shadow:0 0 0 var(--ink);}
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"],.stFormSubmitButton>button[kind="primaryFormSubmit"]{background:var(--grape);}
.stButton>button[kind="primary"] p,.stButton>button[data-testid="stBaseButton-primary"] p{color:#fff;}

/* tabs, radio, inputs */
.stTabs [data-baseweb="tab-list"]{gap:8px;border-bottom:none;flex-wrap:wrap;}
.stTabs [data-baseweb="tab"]{background:#fff;border:var(--line);border-radius:12px;padding:6px 14px;height:auto;}
.stTabs [aria-selected="true"]{background:var(--gold);}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none;}
div[role="radiogroup"]{gap:10px;}
div[role="radiogroup"] label{background:#fff;border:var(--line);border-radius:14px;padding:8px 16px;box-shadow:3px 3px 0 var(--ink);cursor:pointer;}
div[role="radiogroup"] label:has(input:checked){background:var(--gold);}
div[data-baseweb="input"],div[data-baseweb="select"]>div,div[data-baseweb="textarea"]{border:var(--line)!important;border-radius:12px!important;background:#fff!important;}
[data-testid="stExpander"]{border:var(--line);border-radius:14px;background:#fff;}
[data-testid="stAlert"]{border:var(--line);border-radius:14px;}

/* the mic: the one thing that moves on its own */
div[data-testid="stAudioInput"]{border:var(--line);border-radius:16px;background:#fff;animation:ring 2.4s ease-out infinite;}
@keyframes ring{0%{box-shadow:4px 4px 0 var(--ink),0 0 0 0 rgba(124,77,255,.55);}70%,100%{box-shadow:4px 4px 0 var(--ink),0 0 0 14px rgba(124,77,255,0);}}
@keyframes grow{from{width:0;}}
@media (prefers-reduced-motion:reduce){div[data-testid="stAudioInput"],.xp-fill{animation:none!important;}}

/* task cards (keyed containers) */
[class*="st-key-taskcard"],[class*="st-key-taskdone"],[class*="st-key-resultcard"]{background:#fff;border:var(--line);border-radius:16px;box-shadow:var(--pop);padding:10px 14px;margin-bottom:12px;}
[class*="st-key-taskdone"]{background:#E9FFC9;}

/* hero + level HUD */
.hero{background:var(--grape);border:var(--line);border-radius:22px;box-shadow:6px 6px 0 var(--ink);padding:22px 26px;
  display:flex;flex-wrap:wrap;gap:22px;align-items:center;justify-content:space-between;margin-bottom:22px;}
.hero-title{font-family:'Fredoka',sans-serif;font-size:2.7rem;font-weight:700;line-height:1;color:#fff;}
.hero-sub{font-weight:700;margin-top:8px;color:#fff;}
.hud{display:flex;align-items:center;gap:16px;flex:1 1 440px;max-width:680px;background:#fff;border:var(--line);border-radius:18px;padding:12px 16px;flex-wrap:wrap;}
.lvl{width:66px;height:66px;border-radius:50%;background:var(--gold);border:var(--line);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Fredoka',sans-serif;line-height:1;flex:none;}
.lvl small{font-size:.7rem;font-weight:600;} .lvl b{font-size:1.7rem;}
.xp-main{flex:1 1 200px;min-width:0;}
.xp-row{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-weight:800;margin-bottom:6px;}
.xp-track{height:20px;background:#E6E3FA;border:var(--line);border-radius:999px;overflow:hidden;}
.xp-fill{height:100%;background:repeating-linear-gradient(-45deg,#B8F04A,#B8F04A 10px,#9BDD2F 10px,#9BDD2F 20px);border-right:var(--line);animation:grow .9s ease-out;}
.chips{display:flex;gap:8px;flex-wrap:wrap;}
.chip{border:var(--line);border-radius:999px;padding:4px 12px;font-weight:800;background:var(--tang);}
.chip.green{background:var(--lime);}

/* mascot + helper cards */
.voxy{display:flex;gap:12px;align-items:flex-end;margin-bottom:14px;}
.voxy-face{font-size:2rem;background:var(--gold);border:var(--line);border-radius:50%;width:54px;height:54px;display:flex;align-items:center;justify-content:center;flex:none;}
.voxy-say{background:#fff;border:var(--line);border-radius:16px 16px 16px 4px;padding:10px 14px;font-weight:700;box-shadow:3px 3px 0 var(--ink);}
.mode-card{border:var(--line);border-radius:16px;padding:12px 14px;font-weight:700;margin:12px 0;box-shadow:3px 3px 0 var(--ink);}
.mode-braindump{background:#FFD6E8;} .mode-command{background:#CFF3FF;}
.try{background:#fff;border:2.5px dashed var(--ink);border-radius:14px;padding:10px 14px;font-weight:700;margin-bottom:8px;}
.heard{background:#fff;border:var(--line);border-left:10px solid var(--grape);border-radius:14px;padding:10px 14px;margin:12px 0;font-weight:600;}
.loot{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;background:#fff;border:var(--line);border-radius:14px;padding:10px 12px;margin-bottom:10px;box-shadow:3px 3px 0 var(--ink);}
.loot-text{font-weight:800;flex:1 1 200px;}

/* pills + task text */
.pill{display:inline-block;border:2px solid var(--ink);border-radius:999px;padding:1px 10px;font-weight:800;font-size:.8rem;margin-right:6px;background:#fff;}
.pill-high{background:#FFC2C8;} .pill-medium{background:#FFE7A3;} .pill-low{background:#CDF7B5;}
.pill-xp{background:#E3D9FF;} .pill-cat{background:#D6F3FF;}
.task-text{font-weight:800;font-size:1.05rem;margin-bottom:6px;}
.task-text.done{text-decoration:line-through;opacity:.55;}

/* daily quests, badges, stats */
.dq{display:flex;gap:14px;align-items:center;background:#fff;border:var(--line);border-radius:16px;box-shadow:var(--pop);padding:12px 16px;margin-bottom:14px;}
.dq.done{background:#E9FFC9;} .dq.bonus{background:#FFF1C2;}
.dq-icon{font-size:1.9rem;} .dq-body{flex:1;}
.dq-title{font-family:'Fredoka',sans-serif;font-weight:600;font-size:1.1rem;}
.dq-desc{font-weight:600;font-size:.9rem;opacity:.8;}
.dq-xp{font-weight:800;border:2px solid var(--ink);border-radius:999px;padding:2px 12px;background:#E3D9FF;white-space:nowrap;}
.mini-track{height:12px;background:#E6E3FA;border:2px solid var(--ink);border-radius:999px;overflow:hidden;margin-top:6px;}
.mini-fill{height:100%;background:var(--grape);}
.badges{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px;}
.badge{background:#fff;border:var(--line);border-radius:16px;box-shadow:var(--pop);padding:14px;text-align:center;}
.badge.locked{background:#F0EEF8;filter:grayscale(1);opacity:.6;box-shadow:none;}
.badge-icon{font-size:2.3rem;} .badge-name{font-family:'Fredoka',sans-serif;font-weight:600;font-size:1.05rem;} .badge-desc{font-weight:600;font-size:.85rem;}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:14px;}
.tile{background:#fff;border:var(--line);border-radius:16px;box-shadow:3px 3px 0 var(--ink);padding:12px 14px;font-weight:700;}
.tile b{display:block;font-family:'Fredoka',sans-serif;font-size:2rem;line-height:1.1;}
.empty{text-align:center;background:#fff;border:2.5px dashed var(--ink);border-radius:18px;padding:34px 18px;font-weight:700;}
.empty .big{font-size:3.2rem;}
"""


def inject_theme():
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def h(markup):
    """Collapse a multi-line HTML template so Markdown never mistakes it for a code block."""
    return "".join(line.strip() for line in markup.strip().splitlines())


def show(markup):
    st.markdown(h(markup), unsafe_allow_html=True)


def clean(text):
    """Escape user or AI text for safe use inside HTML."""
    return escape(" ".join(str(text).split()))


def keyed_container(key):
    try:
        return st.container(key=key)
    except TypeError:  # older Streamlit without container keys
        return st.container()


# ---------------------------------------------------------------------------
# Game state: XP, levels, streaks, daily quests, badges
# ---------------------------------------------------------------------------
def _now():
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(TIMEZONE))
        except Exception:
            pass
    return datetime.now()


def _today():
    return _now().date()


def default_game():
    return {
        "xp": 0, "voice_sessions": 0, "voice_tasks_added": 0, "total_completed": 0,
        "awarded_ids": [], "synced_once": False,
        "streak": 0, "best_streak": 0, "last_active": None,
        "badges": [], "daily": {},
    }


def load_game():
    if "game" in st.session_state:
        return st.session_state.game
    game = default_game()
    try:
        if GAME_FILE.exists():
            game.update(json.loads(GAME_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        debug(f"Could not read game file: {e}")
    st.session_state.game = game
    return game


def save_game(game):
    try:
        GAME_FILE.write_text(json.dumps(game, indent=2), encoding="utf-8")
    except Exception as e:
        debug(f"Could not save game file: {e}")


def ensure_today(game):
    today = _today().isoformat()
    if (game.get("daily") or {}).get("date") != today:
        game["daily"] = {"date": today, "voice": 0, "added": 0, "done": 0, "claimed": []}


def level_from_xp(xp):
    return math.isqrt(int(xp) // XP_STEP) + 1


def level_floor(level):
    return XP_STEP * (level - 1) ** 2


def level_title(level):
    return LEVEL_TITLES[min(level, len(LEVEL_TITLES)) - 1]


def effective_streak(game):
    last = game.get("last_active")
    if not last:
        return 0
    today = _today()
    if last in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
        return game["streak"]
    return 0


def notify(msg, icon="✨"):
    """Queue a toast. It shows on the next render so st.rerun() can't swallow it."""
    st.session_state.setdefault("toast_queue", []).append((msg, icon))


def flush_notifications():
    for msg, icon in st.session_state.pop("toast_queue", []):
        st.toast(msg, icon=icon)
    if st.session_state.pop("celebrate", False):
        st.balloons()


def touch_streak(game):
    """Update the streak on the first activity of the day. Returns bonus XP."""
    today = _today()
    last = game.get("last_active")
    if last == today.isoformat():
        return 0
    yesterday = (today - timedelta(days=1)).isoformat()
    game["streak"] = game["streak"] + 1 if last == yesterday else 1
    game["best_streak"] = max(game["best_streak"], game["streak"])
    game["last_active"] = today.isoformat()
    return 5 * min(game["streak"], 10)


def award_xp(game, amount, reason):
    bonus = touch_streak(game)
    before = level_from_xp(game["xp"])
    game["xp"] += amount + bonus
    notify(f"+{amount} XP for {reason}", "⚡")
    if bonus:
        notify(f"{game['streak']} day streak, +{bonus} bonus XP", "🔥")
    after = level_from_xp(game["xp"])
    if after > before:
        notify(f"Level {after}: {level_title(after)}", "🎉")
        st.session_state.celebrate = True


def sync_progress(game, tasks):
    """Give XP once per completed task, whichever way it was completed (checkbox or AI assistant)."""
    current = {str(t["id"]) for t in tasks}
    awarded = {a for a in game["awarded_ids"] if a in current}
    fresh = [t for t in tasks if t.get("completed") and str(t["id"]) not in awarded]
    if fresh:
        first_sync = not game.get("synced_once")
        total = sum(XP_COMPLETE.get(t.get("priority", "medium"), 20) for t in fresh)
        game["total_completed"] += len(fresh)
        if not first_sync:
            game["daily"]["done"] += len(fresh)
        if first_sync:
            reason = "your earlier wins"
        elif len(fresh) == 1:
            reason = "completing a task"
        else:
            reason = f"completing {len(fresh)} tasks"
        award_xp(game, total, reason)
        awarded |= {str(t["id"]) for t in fresh}
    game["awarded_ids"] = sorted(awarded)
    game["synced_once"] = True


def check_daily_quests(game):
    daily = game["daily"]
    for q in DAILY_QUESTS:
        if q["id"] not in daily["claimed"] and daily.get(q["key"], 0) >= q["target"]:
            daily["claimed"].append(q["id"])
            award_xp(game, q["xp"], f"daily quest: {q['title']}")
    if "bonus" not in daily["claimed"] and all(q["id"] in daily["claimed"] for q in DAILY_QUESTS):
        daily["claimed"].append("bonus")
        award_xp(game, DAILY_BONUS_XP, "clearing every daily quest")
        st.session_state.celebrate = True


def check_badges(game, tasks):
    for b in BADGES:
        if b["id"] not in game["badges"] and b["test"](game, tasks):
            game["badges"].append(b["id"])
            notify(f"Badge unlocked: {b['name']}", "🏅")


# ---------------------------------------------------------------------------
# Services (unchanged logic)
# ---------------------------------------------------------------------------
@st.cache_resource
def init_services():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("Please set your OPENAI_API_KEY in the .env file")
        st.stop()

    whisper = WhisperService(api_key)
    llm = LLMService(api_key)
    task_manager = TaskManager()
    tts_service = TTSService()

    # Try to initialize the agent service (optional enhancement)
    agent_service = None
    try:
        from services.agent_service import AgentService
        agent_service = AgentService(api_key, task_manager)
        print("✅ Agent service initialized successfully")
    except Exception as e:
        print(f"ℹ️ Agent service not available (optional): {e}")

    help_service = HelpService(llm, agent_service)
    return whisper, llm, task_manager, tts_service, help_service


def init_state():
    defaults = {
        "mode": "braindump", "last_mode": "braindump", "current_audio_hash": None,
        "processed_tasks": None, "transcription": None, "last_command_result": None,
        "help_panel_open": False, "help_question": "", "help_response": "",
        "help_input_counter": 0, "last_help_question_processed": None,
        "help_audio_version": 0, "help_mode": "question",
        "main_audio_version": 0, "prompt_idx": random.randrange(10),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def render_hero(game, tasks):
    level = level_from_xp(game["xp"])
    lo, hi = level_floor(level), level_floor(level + 1)
    pct = int(100 * (game["xp"] - lo) / (hi - lo))
    streak = effective_streak(game)
    done = sum(1 for t in tasks if t.get("completed"))
    show(f"""
    <div class="hero">
      <div>
        <div class="hero-title">🎤 Voice Quest</div>
        <div class="hero-sub">Say what is on your mind. I turn it into quests. You level up.</div>
      </div>
      <div class="hud">
        <div class="lvl"><small>Lv</small><b>{level}</b></div>
        <div class="xp-main">
          <div class="xp-row"><span>{level_title(level)}</span><span>{game['xp'] - lo} / {hi - lo} XP</span></div>
          <div class="xp-track"><div class="xp-fill" style="width:{pct}%"></div></div>
        </div>
        <div class="chips">
          <span class="chip">🔥 {streak} day streak</span>
          <span class="chip green">✅ {done} done</span>
        </div>
      </div>
    </div>
    """)


def voxy_line(tasks):
    total = len(tasks)
    pending = sum(1 for t in tasks if not t.get("completed"))
    if total == 0:
        return "Your quest log is empty. Tap the mic and tell me what is on your mind!"
    if pending == 0:
        return "Every quest is cleared. Legendary! Ready for a new brain dump?"
    if pending == 1:
        return "Just one quest left. Finish it and claim your win!"
    return f"{pending} quests are waiting. Pick one and crush it!"


def render_loot(item):
    if isinstance(item, dict):
        text = item.get("text", "")
        priority = item.get("priority") or "medium"
        category = item.get("category")
    else:
        text, priority, category = str(item), "medium", None
    priority = priority if priority in PRIORITY_ICONS else "medium"
    category = category or "personal"
    cat_label = CATEGORY_LABELS.get(category, f"📝 {clean(str(category).title())}")
    show(f"""
    <div class="loot">
      <div class="loot-text">{clean(text)}</div>
      <div>
        <span class="pill pill-{priority}">{PRIORITY_ICONS[priority]} {priority.title()}</span>
        <span class="pill pill-cat">{cat_label}</span>
        <span class="pill pill-xp">⚡ +{XP_TASK_ADDED} XP</span>
      </div>
    </div>
    """)


# Task card callbacks. They read widget state at click time, so edits always save the typed text.
def on_check(task_manager, task_id, check_key):
    wanted = bool(st.session_state.get(check_key, False))
    current = next((t for t in task_manager.get_tasks() if t["id"] == task_id), None)
    if current is not None and bool(current.get("completed")) != wanted:
        task_manager.toggle_task(task_id)


def start_edit(edit_key, text_key, text):
    st.session_state[edit_key] = True
    st.session_state[text_key] = text


def save_edit(task_manager, task_id, edit_key, text_key):
    new_text = st.session_state.get(text_key, "").strip()
    if new_text:
        task_manager.update_task(task_id, text=new_text)
    st.session_state[edit_key] = False
    st.session_state.pop(text_key, None)


def cancel_edit(edit_key, text_key):
    st.session_state[edit_key] = False
    st.session_state.pop(text_key, None)


def delete_task(task_manager, task_id):
    task_manager.delete_task(task_id)


def render_task(task, task_manager):
    tid = task["id"]
    done = bool(task.get("completed"))
    edit_key, text_key, check_key = f"edit_{tid}", f"text_{tid}", f"check_{tid}"
    st.session_state.setdefault(edit_key, False)
    editing = st.session_state[edit_key]

    priority = task.get("priority") or "medium"
    priority = priority if priority in PRIORITY_ICONS else "medium"
    category = task.get("category")
    xp = XP_COMPLETE.get(priority, 20)

    with keyed_container(f"{'taskdone' if done else 'taskcard'}_{tid}"):
        c_check, c_body, c_edit, c_del = st.columns([0.7, 6, 0.9, 0.9], vertical_alignment="center")

        with c_check:
            st.session_state[check_key] = done  # keep the box in sync with the saved task
            st.checkbox("Done", key=check_key, label_visibility="collapsed",
                        on_change=on_check, args=(task_manager, tid, check_key))

        with c_body:
            if editing:
                if text_key not in st.session_state:
                    st.session_state[text_key] = task["text"]
                st.text_input("Edit task", key=text_key, label_visibility="collapsed")
                c_save, c_cancel = st.columns(2)
                c_save.button("💾 Save", key=f"save_{tid}", on_click=save_edit,
                              args=(task_manager, tid, edit_key, text_key))
                c_cancel.button("Cancel", key=f"cancel_{tid}", on_click=cancel_edit,
                                args=(edit_key, text_key))
            else:
                pills = f'<span class="pill pill-{priority}">{PRIORITY_ICONS[priority]} {priority.title()}</span>'
                if category:
                    pills += f'<span class="pill pill-cat">{CATEGORY_LABELS.get(category, "📝 " + clean(str(category).title()))}</span>'
                pills += f'<span class="pill pill-xp">{"✅ earned" if done else "⚡ worth"} {xp} XP</span>'
                show(f'<div class="task-text{" done" if done else ""}">{clean(task["text"])}</div>{pills}')

        with c_edit:
            if not editing:
                st.button("✏️", key=f"edit_btn_{tid}", help="Edit", on_click=start_edit,
                          args=(edit_key, text_key, task["text"]))
        with c_del:
            st.button("🗑️", key=f"del_{tid}", help="Delete", on_click=delete_task,
                      args=(task_manager, tid))


def render_daily(game):
    daily = game["daily"]
    streak = effective_streak(game)
    if streak == 0:
        streak_text = "Finish one thing today to start a streak."
    elif game.get("last_active") == _today().isoformat():
        streak_text = f"{streak} days in a row. Your best is {game['best_streak']}."
    else:
        streak_text = f"{streak} days in a row. Do one thing today to keep it alive."
    show(f"""
    <div class="dq"><div class="dq-icon">🔥</div>
      <div class="dq-body"><div class="dq-title">Streak</div><div class="dq-desc">{streak_text}</div></div></div>
    """)
    for q in DAILY_QUESTS:
        got = min(daily.get(q["key"], 0), q["target"])
        pct = int(100 * got / q["target"])
        cls = "dq done" if q["id"] in daily["claimed"] else "dq"
        show(f"""
        <div class="{cls}"><div class="dq-icon">{q['icon']}</div>
          <div class="dq-body">
            <div class="dq-title">{q['title']}</div>
            <div class="dq-desc">{q['desc']} ({got} of {q['target']})</div>
            <div class="mini-track"><div class="mini-fill" style="width:{pct}%"></div></div>
          </div>
          <div class="dq-xp">+{q['xp']} XP</div></div>
        """)
    cleared = sum(1 for q in DAILY_QUESTS if q["id"] in daily["claimed"])
    show(f"""
    <div class="dq bonus"><div class="dq-icon">🎁</div>
      <div class="dq-body"><div class="dq-title">Daily bonus</div>
      <div class="dq-desc">Clear all three quests today ({cleared} of {len(DAILY_QUESTS)})</div></div>
      <div class="dq-xp">+{DAILY_BONUS_XP} XP</div></div>
    """)


def render_badges(game):
    cards = ""
    for b in BADGES:
        unlocked = b["id"] in game["badges"]
        cards += (
            f'<div class="badge{"" if unlocked else " locked"}">'
            f'<div class="badge-icon">{b["icon"] if unlocked else "🔒"}</div>'
            f'<div class="badge-name">{b["name"]}</div><div class="badge-desc">{b["desc"]}</div></div>'
        )
    st.markdown(f"**{len(game['badges'])} of {len(BADGES)} unlocked**")
    show(f'<div class="badges">{cards}</div>')


def render_stats(stats):
    def tiles(items):
        body = "".join(f'<div class="tile">{label}<b>{stats.get(key, 0)}</b></div>' for label, key in items)
        show(f'<div class="tiles">{body}</div>')

    st.markdown("##### Overview")
    tiles([("📋 Total", "total"), ("✅ Completed", "completed"), ("⏳ Pending", "pending")])
    st.markdown("##### By priority")
    tiles([("🔴 High", "high_priority"), ("🟡 Medium", "medium_priority"), ("🟢 Low", "low_priority")])
    st.markdown("##### By category")
    tiles([("👤 Client", "client_tasks"), ("💼 Business", "business_tasks"), ("🏠 Personal", "personal_tasks")])


# ---------------------------------------------------------------------------
# Sidebar assistant (same logic as before)
# ---------------------------------------------------------------------------
def render_help_panel(whisper, help_service, task_manager):
    st.header("🤖 AI Sidekick")

    help_status = "🟢 Active" if st.session_state.help_panel_open else "⚪ Inactive"
    if st.button(f"🔧 Toggle Panel ({help_status})", key="toggle_help"):
        st.session_state.help_panel_open = not st.session_state.help_panel_open

    if not st.session_state.help_panel_open:
        return

    st.divider()
    st.markdown("### Select Mode")
    col1, col2 = st.columns(2)

    def switch_to_question():
        st.session_state.help_mode = 'question'
        st.session_state.help_response = ""

    def switch_to_command():
        st.session_state.help_mode = 'command'
        st.session_state.help_response = ""

    with col1:
        st.button(
            "❓ Question Mode" if st.session_state.help_mode != 'question' else "✅ Question Mode",
            key="mode_question", use_container_width=True,
            type="primary" if st.session_state.help_mode == 'question' else "secondary",
            on_click=switch_to_question,
        )
    with col2:
        st.button(
            "⚡ Command Mode" if st.session_state.help_mode != 'command' else "✅ Command Mode",
            key="mode_command", use_container_width=True,
            type="primary" if st.session_state.help_mode == 'command' else "secondary",
            on_click=switch_to_command,
        )

    if st.session_state.help_mode == 'question':
        st.info("📚 Ask questions about how to use the app")
    else:
        st.success("🚀 I'll execute commands for you")

    st.divider()

    mode_text = "question" if st.session_state.help_mode == 'question' else "command"
    st.markdown(f"### 🎤 Speak your {mode_text}")
    help_audio = st.audio_input(
        "Click to record",
        key=f"help_audio_{st.session_state.help_audio_version}",
    )

    if help_audio:
        help_audio_bytes = help_audio.read()
        help_transcription = whisper.transcribe(help_audio_bytes)

        if help_transcription and help_transcription != st.session_state.last_help_question_processed:
            st.session_state.help_question = help_transcription
            st.session_state.last_help_question_processed = help_transcription

            with st.spinner("Processing..."):
                help_response = help_service.get_help_response(
                    help_transcription, None, mode=st.session_state.help_mode
                )
                st.session_state.help_response = help_response

            if st.session_state.get('tasks_updated'):
                st.session_state.tasks_updated = False

            st.session_state.help_audio_version += 1
            st.rerun()

    with st.form(key="help_text_form", clear_on_submit=True):
        help_text = st.text_input(
            f"Or type your {mode_text}:",
            placeholder="Add a task to buy groceries" if st.session_state.help_mode == 'command'
            else "How do I add a task?",
        )
        submitted = st.form_submit_button("Submit", use_container_width=True)

        if submitted and help_text and help_text.strip():
            st.session_state.help_question = help_text
            st.session_state.last_help_question_processed = help_text

            current_tasks = task_manager.get_tasks()
            st.session_state.help_response = help_service.get_help_response(
                help_text, current_tasks, mode=st.session_state.help_mode
            )
            if st.session_state.get('tasks_updated'):
                st.session_state.tasks_updated = False
            st.rerun()

    st.divider()

    if st.session_state.help_question:
        st.markdown("**Transcribed/Input:**")
        st.code(st.session_state.help_question)

    if st.session_state.help_response:
        st.markdown("**Response:**")
        st.markdown(st.session_state.help_response)
        if st.button("Clear", key="clear_response"):
            st.session_state.help_response = ""
            st.session_state.help_question = ""
            st.session_state.help_audio_version += 1
            st.rerun()
    else:
        st.info(f"💭 Ready for your {mode_text}...")


# ---------------------------------------------------------------------------
# Voice zone (left column)
# ---------------------------------------------------------------------------
def next_idea():
    st.session_state.prompt_idx += 1


def reset_voice_zone():
    st.session_state.processed_tasks = None
    st.session_state.transcription = None
    st.session_state.last_command_result = None
    st.session_state.main_audio_version += 1  # fresh mic, ready for the next recording


def render_voice_zone(tasks, whisper, llm, task_manager, tts_service, help_service):
    game = st.session_state.game
    mode = st.session_state.mode

    show(f'<div class="voxy"><div class="voxy-face">🦊</div><div class="voxy-say"><b>Voxy:</b> {voxy_line(tasks)}</div></div>')

    if mode == 'braindump':
        show('<div class="mode-card mode-braindump">🧠 Brain Dump: ramble freely about everything on your mind. I will sort it into quests with priorities.</div>')
    else:
        show('<div class="mode-card mode-command">🎯 Command: give one clear order, like “Add a task to review documentation” or “Mark the first task as complete”.</div>')

    ideas = PROMPTS[mode]
    idea = ideas[st.session_state.prompt_idx % len(ideas)]
    show(f'<div class="try"><b>Try saying:</b> “{clean(idea)}”</div>')
    st.button("🎲 Another idea", key="new_idea", on_click=next_idea)

    st.markdown("### 🎙️ Voice zone")
    audio_value = st.audio_input(
        "Tap the mic, talk, then tap again to stop",
        key=f"main_audio_{st.session_state.main_audio_version}",
    )

    if audio_value:
        current_hash = hash(str(audio_value.name) + str(audio_value.size))
        if current_hash != st.session_state.current_audio_hash:
            debug("New audio detected")
            st.session_state.current_audio_hash = current_hash
            audio_bytes = audio_value.read()

            with st.spinner("🎧 Listening closely..."):
                transcription = whisper.transcribe(audio_bytes)

            if not transcription:
                st.error("I could not catch that. Check your mic and try again.")
            else:
                st.session_state.transcription = transcription
                st.session_state.processed_tasks = None
                st.session_state.last_command_result = None

                game["voice_sessions"] += 1
                game["daily"]["voice"] += 1
                award_xp(game, XP_VOICE_NOTE, "your voice note")

                if mode == 'braindump':
                    try:
                        with st.spinner("🧠 Sorting your ideas into quests..."):
                            found = llm.process_braindump(transcription)
                    except Exception as e:
                        debug(f"process_braindump failed: {e}")
                        found = None
                        notify("Something went wrong while sorting your ideas. Try again.", "⚠️")
                    if found:
                        st.session_state.processed_tasks = found
                    else:
                        notify("I could not find any tasks in that. Try adding more detail.", "🤔")
                else:
                    try:
                        with st.spinner("⚡ Running your command..."):
                            st.session_state.last_command_result = help_service.get_help_response(
                                transcription, None, mode='command'
                            )
                    except Exception as e:
                        debug(f"command failed: {e}")
                        notify("Command mode did not work from here. Use the AI Sidekick panel.", "⚠️")

                save_game(game)
                st.rerun()

    # Results persist until accepted or cleared
    if st.session_state.transcription:
        show(f'<div class="heard"><b>What I heard</b><br>{clean(st.session_state.transcription)}</div>')

    processed = st.session_state.processed_tasks
    if processed:
        st.markdown("### 🎁 Quests I found")
        for item in processed:
            render_loot(item)

        if st.button(f"⚔️ Accept {len(processed)} quest{'s' if len(processed) != 1 else ''} (+{XP_TASK_ADDED * len(processed)} XP)",
                     key="add_tasks", type="primary"):
            added = 0
            for item in processed:
                if isinstance(item, dict):
                    text = str(item.get('text', '')).strip()
                    if not text:
                        continue
                    task_manager.add_task(
                        text,
                        priority=item.get('priority', 'medium'),
                        category=item.get('category') or 'personal',
                    )
                else:
                    task_manager.add_task(str(item), priority='medium', category='personal')
                added += 1

            if added:
                game["voice_tasks_added"] += added
                game["daily"]["added"] += added
                award_xp(game, XP_TASK_ADDED * added, f"{added} new quest{'s' if added != 1 else ''}")
                save_game(game)
                tts_service.speak_confirmation('task_added', f"Added {added} tasks")
            reset_voice_zone()
            st.rerun()

    result = st.session_state.last_command_result
    if result:
        with keyed_container("resultcard_command"):
            st.markdown("**🦊 Voxy says:**")
            st.markdown(result)

    if processed or result or st.session_state.transcription:
        if st.button("Clear results", key="clear_results"):
            reset_voice_zone()
            st.rerun()


# ---------------------------------------------------------------------------
# Quest log (right column)
# ---------------------------------------------------------------------------
def render_quest_log(task_manager, llm, tts_service):
    tasks = task_manager.get_tasks()
    debug(f"Retrieved {len(tasks)} tasks")

    if not tasks:
        show("""
        <div class="empty"><div class="big">🗺️</div>
        Your quest log is empty.<br>Tap the mic and say what you need to do. Personal stuff counts too.</div>
        """)
        return

    done = sum(1 for t in tasks if t.get("completed"))
    pct = int(100 * done / len(tasks))
    show(f"""
    <div style="margin-bottom:14px">
      <div class="xp-row"><span>{done} of {len(tasks)} quests cleared</span><span>{pct}%</span></div>
      <div class="xp-track"><div class="xp-fill" style="width:{pct}%"></div></div>
    </div>
    """)

    with st.expander("🔍 Filters"):
        f1, f2, f3 = st.columns(3)
        priority_filter = f1.selectbox("Priority", ["All", "High", "Medium", "Low"], key="priority_filter")
        category_filter = f2.selectbox("Category", ["All", "Client", "Business", "Personal"], key="category_filter")
        status_filter = f3.selectbox("Status", ["All", "Pending", "Completed"], key="status_filter")

    filtered = tasks
    if priority_filter != "All":
        filtered = [t for t in filtered if t.get('priority') == priority_filter.lower()]
    if category_filter != "All":
        filtered = [t for t in filtered if t.get('category') == category_filter.lower()]
    if status_filter == "Pending":
        filtered = [t for t in filtered if not t['completed']]
    elif status_filter == "Completed":
        filtered = [t for t in filtered if t['completed']]

    if not filtered:
        st.info("No tasks match the current filters.")
    else:
        for task in filtered:
            render_task(task, task_manager)

    st.markdown("##### ⚡ Power-ups")
    p1, p2 = st.columns(2)
    with p1:
        if st.button("✨ Auto-prioritize", key="auto_prioritize"):
            with st.spinner("Ranking your quests..."):
                llm.prioritize_tasks(task_manager.get_tasks())
            tts_service.speak_confirmation('task_updated', "Tasks prioritized")
            notify("Quests re-ranked", "✨")
            st.rerun()
    with p2:
        if st.button("🧹 Clear all tasks", key="clear_all"):
            task_manager.clear_all()
            tts_service.speak_confirmation('tasks_cleared')
            notify("Quest log cleared. Your XP is safe.", "🧹")
            st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    inject_theme()
    whisper, llm, task_manager, tts_service, help_service = init_services()
    init_state()

    game = load_game()
    ensure_today(game)
    tasks = task_manager.get_tasks()
    sync_progress(game, tasks)
    check_daily_quests(game)
    check_badges(game, tasks)
    save_game(game)
    flush_notifications()

    render_hero(game, tasks)

    with st.sidebar:
        render_help_panel(whisper, help_service, task_manager)

    st.markdown("### 🎯 Choose how you want to talk")
    mode = st.radio(
        "Choose your mode:",
        ["🧠 Brain Dump", "🎯 Command"],
        horizontal=True,
        index=0 if st.session_state.mode == 'braindump' else 1,
        key="mode_selector",
        label_visibility="collapsed",
    )
    new_mode = 'braindump' if mode == "🧠 Brain Dump" else 'command'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
    if st.session_state.last_mode != st.session_state.mode:
        reset_voice_zone()
        st.session_state.last_mode = st.session_state.mode

    left, right = st.columns([5, 6], gap="large")

    with left:
        render_voice_zone(tasks, whisper, llm, task_manager, tts_service, help_service)

    with right:
        tab_log, tab_daily, tab_badges, tab_stats = st.tabs(
            ["🗡️ Quest log", "🎯 Daily quests", "🏅 Badges", "📊 Stats"]
        )
        with tab_log:
            render_quest_log(task_manager, llm, tts_service)
        with tab_daily:
            render_daily(game)
        with tab_badges:
            render_badges(game)
        with tab_stats:
            if tasks:
                render_stats(task_manager.get_stats())
            else:
                st.info("Stats appear once you have a few tasks.")


if __name__ == "__main__":
    main()

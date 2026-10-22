import streamlit as st
import os
from dotenv import load_dotenv
import json
from datetime import datetime
from pathlib import Path

from services.whisper_service import WhisperService
from services.llm_service import LLMService
from services.task_manager import TaskManager
from services.tts_service import TTSService
from services.help_service import HelpService

load_dotenv()

st.set_page_config(
    page_title="Voice Task RPG",
    page_icon="⚔️",
    layout="wide"
)

# --- GAMIFIED STYLE ENGINE (NEON CYBERPUNK THEME) ---
st.markdown("""
<style>
    @import url('https://googleapis.com');
    
    /* Main App Custom Background */
    .stApp {
        background: linear-gradient(135deg, #0f0c20 0%, #15102a 50%, #06040a 100%);
        color: #e0e0ff !important;
        font-family: 'Rajdhani', sans-serif;
    }
    
    /* Glassmorphism RPG Panels */
    div[data-testid="stVerticalBlock"] > div, .stAlert {
        background: rgba(26, 21, 44, 0.65) !important;
        backdrop-filter: blur(12px);
        border-radius: 16px !important;
        border: 1px solid rgba(138, 43, 226, 0.3) !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 10px rgba(138, 43, 226, 0.1) !important;
        padding: 24px !important;
        margin-bottom: 16px;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    
    /* Hover Glow Interaction */
    div[data-testid="stVerticalBlock"] > div:hover {
        transform: translateY(-2px);
        border-color: #00ffff !important;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.2), inset 0 0 15px rgba(0, 255, 255, 0.05) !important;
    }
    
    /* Cyberpunk Headings */
    h1, h2, h3, h4 {
        font-family: 'Orbitron', sans-serif !important;
        color: #00ffff !important;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        letter-spacing: 2px;
    }
    
    /* Neon Audio Record Button styling overrides */
    button[data-testid="baseButton-secondary"] {
        background: linear-gradient(45deg, #ff007f, #7928ca) !important;
        color: white !important;
        border: 1px solid #ff007f !important;
        border-radius: 30px !important;
        padding: 14px 28px !important;
        font-family: 'Orbitron', sans-serif;
        font-weight: bold !important;
        text-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    button[data-testid="baseButton-secondary"]:hover {
        transform: scale(1.04) !important;
        box-shadow: 0 0 25px rgba(255, 0, 127, 0.8) !important;
    }
    
    /* XP Stat Bars */
    .xp-bar-container {
        background-color: #251c44;
        border-radius: 10px;
        border: 1px solid #8a22b2;
        padding: 3px;
        margin: 10px 0;
        box-shadow: 0 0 10px rgba(138, 66, 178, 0.3);
    }
    .xp-bar-fill {
        background: linear-gradient(90deg, #00ffff 0%, #8a22b2 100%);
        height: 14px;
        border-radius: 8px;
        box-shadow: 0 0 8px #00ffff;
        transition: width 0.5s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

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
    
    agent_service = None
    try:
        from services.agent_service import AgentService
        agent_service = AgentService(api_key, task_manager)
        print("✅ Agent service initialized successfully")
    except Exception as e:
        print(f"ℹ️ Agent service not available (optional): {e}")
    
    help_service = HelpService(llm, agent_service)
    
    return whisper, llm, task_manager, tts_service, help_service

def init_rpg_state(task_manager):
    """Initializes and recalibrates gamified stats using current task statuses"""
    tasks = task_manager.get_tasks()
    completed_count = sum(1 for t in tasks if t["completed"])
    
    # Calculate Leveling Math (100 XP per task completed)
    total_xp = completed_count * 100
    current_level = (total_xp // 500) + 1
    xp_in_level = total_xp % 500
    xp_needed = 500
    
    # Simple active streak checking logic
    streak = 1 if completed_count > 0 else 0
    
    st.session_state.rpg_level = current_level
    st.session_state.rpg_xp = xp_in_level
    st.session_state.rpg_streak = streak

def render_task(task, task_manager, tts_service):
    """Render a single task with enhanced gamified UI cards"""
    priority_colors = {'high': '🔴 [CRITICAL]', 'medium': '🟡 [QUEST]', 'low': '🟢 [MINI]'}
    category_labels = {'client': '👤 Client', 'business': '💼 Work', 'personal': '🏠 Home'}
    
    edit_key = f"edit_{task['id']}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False
    
    def start_edit():
        st.session_state[edit_key] = True
    
    def save_edit(task_id, new_text):
        task_manager.update_task(task_id, text=new_text)
        st.session_state[edit_key] = False
    
    def cancel_edit():
        st.session_state[edit_key] = False
    
    def delete_task(task_id):
        task_manager.delete_task(task_id)
        
    # Styled Quest Layout row
    col_check, col_priority, col_task, col_category, col_delete = st.columns([1, 1.8, 5.2, 1.2, 0.8])
    
    with col_check:
        checkbox_key = f"check_{task['id']}"
        is_checked = st.checkbox("Done", value=task["completed"], key=checkbox_key, label_visibility="hidden")
        
        if is_checked != task["completed"]:
            task_manager.toggle_task(task['id'])
            if is_checked:
                st.balloons()
                tts_service.speak_confirmation('task_updated', "Quest Cleared! +100 EXP")
            st.rerun()
    
    with col_priority:
        priority_str = priority_colors.get(task.get('priority', 'medium'), '⚪')
        st.markdown(f"<span style='font-family:Orbitron; font-size:13px;'>{priority_str}</span>", unsafe_allow_html=True)
    
    with col_task:
        if st.session_state[edit_key]:
            new_text = st.text_input("Modify Objective:", value=task['text'], key=f"text_{task['id']}")
            col_save, col_cancel = st.columns(2)
            with col_save:
                st.button("💾", key=f"save_{task['id']}", on_click=save_edit, args=(task['id'], new_text))
            with col_cancel:
                st.button("❌", key=f"cancel_{task['id']}", on_click=cancel_edit)
        else:
            if task["completed"]:
                st.markdown(f"<span style='color:#7a7299; text-decoration:line-through;'>✨ {task['text']}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"⚔️ **{task['text']}**")
            st.button("✏️", key=f"edit_btn_{task['id']}", on_click=start_edit)
    
    with col_category:
        category_str = category_labels.get(task.get('category'), '📝 Notes')
        st.markdown(f"<span style='font-size:14px; opacity:0.8;'>{category_str}</span>", unsafe_allow_html=True)
        
    with col_delete:
        st.button("🗑️", key=f"del_{task['id']}", on_click=delete_task, args=(task['id'],))

def render_stats(stats):
    """Render gamified RPG scoreboard dashboard"""
    st.markdown("### 🏆 Dashboard Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Loot / Quests", stats['total'])
        st.metric("Completed", stats['completed'])
        st.metric("In Progress", stats['pending'])
    
    with col2:
        st.metric("Boss Fights (High)", stats['high_priority'])
        st.metric("Medium Campaigns", stats['medium_priority'])
        st.metric("Side Grinds (Low)", stats['low_priority'])
    
    with col3:
        st.metric("Client Faction", stats['client_tasks'])
        st.metric("Gold Grind (Business)", stats['business_tasks'])
        st.metric("Guild Quests (Personal)", stats['personal_tasks'])

def main():
    whisper, llm, task_manager, tts_service, help_service = init_services()
    
    # Initialize Core Application & RPG Engine States
    if 'mode' not in st.session_state: st.session_state.mode = 'braindump'
    if 'last_mode' not in st.session_state: st.session_state.last_mode = 'braindump'
    if 'current_audio_hash' not in st.session_state: st.session_state.current_audio_hash = None
    if 'processed_tasks' not in st.session_state: st.session_state.processed_tasks = None
    if 'transcription' not in st.session_state: st.session_state.transcription = None
    if 'last_command_result' not in st.session_state: st.session_state.last_command_result = None
    if 'help_panel_open' not in st.session_state: st.session_state.help_panel_open = False
    if 'help_question' not in st.session_state: st.session_state.help_question = ""
    if 'help_response' not in st.session_state: st.session_state.help_response = ""
    if 'help_input_counter' not in st.session_state: st.session_state.help_input_counter = 0
    if 'last_help_question_processed' not in st.session_state: st.session_state.last_help_question_processed = None
    if 'help_audio_version' not in st.session_state: st.session_state.help_audio_version = 0
    if 'help_mode' not in st.session_state: st.session_state.help_mode = 'question'
    
    init_rpg_state(task_manager)
    
    # --- HERO HERO PROFILE (SIDEBAR STATS DISPLAY) ---
    with st.sidebar:
        st.markdown(f"<h2 style='text-align:center; color:#00ffff; margin-bottom:0;'>👑 PLAYER MATRIX</h2>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='text-align:center; color:#ff007f; margin-top:0;'>LEVEL {st.session_state.rpg_level} HERO</h4>", unsafe_allow_html=True)
        
        # Continuous Animated Custom XP Bar
        xp_percentage = int((st.session_state.rpg_xp / 500) * 100)

st.markdown(f"""

EXP PROGRESS
{st.session_state.rpg_xp} / 500 XP




""", unsafe_allow_html=True)
# Streak Tracker Badge
st.markdown(f"""

🔥 STREAK: {st.session_state.rpg_streak} DAYS

""", unsafe_allow_html=True)
st.divider()
# AI Companion Panel Inside Sidebar
st.header("🤖 AI Tactics Companion")
help_status = "🟢 Online" if st.session_state.help_panel_open else "⚪ Offline"
if st.button(f"⚙️ Open HUD Interface ({help_status})", key="toggle_help"):
st.session_state.help_panel_open = not st.session_state.help_panel_open
if st.session_state.help_panel_open:
st.markdown("### Command Mode Selection")
col_h1, col_h2 = st.columns(2)
with col_h1:
if st.button("❓ Lore / Help", key="mode_question", use_container_width=True):
st.session_state.help_mode = 'question'
st.session_state.help_response = ""
st.rerun()
with col_h2:
if st.button("⚡ Quick Action", key="mode_command", use_container_width=True):
st.session_state.help_mode = 'command'
st.session_state.help_response = ""
st.rerun()
help_audio = st.audio_input("Speak Strategy Command", key=f"help_audio_{st.session_state.help_audio_version}")
if help_audio:
help_transcription = whisper.transcribe(help_audio.read())
if help_transcription and help_transcription != st.session_state.last_help_question_processed:
st.session_state.help_question = help_transcription
st.session_state.last_help_question_processed = help_transcription
with st.spinner("Analyzing audio frequencies..."):
st.session_state.help_response = help_service.get_help_response(
help_transcription, None, mode=st.session_state.help_mode
)
st.session_state.help_audio_version += 1
st.rerun()
with st.form(key="help_text_form", clear_on_submit=True):
help_text = st.text_input("Type Command Script:")
if st.form_submit_button("Execute Subroutine") and help_text.strip():
st.session_state.help_question = help_text
st.session_state.help_response = help_service.get_help_response(
help_text, task_manager.get_tasks(), mode=st.session_state.help_mode
)
st.rerun()
if st.session_state.help_question:
st.code(f"Input: {st.session_state.help_question}")
if st.session_state.help_response:
st.markdown(st.session_state.help_response)
if st.button("Purge Feed"):
st.session_state.help_response = ""
st.session_state.help_question = ""
st.rerun()
# --- MAIN VIEW INTERFACE ---
st.markdown("⚔️ VOICE TASK RPG COMMAND TERMINAL", unsafe_allow_html=True)
st.subheader("🎯 Active Strategy Matrix")
mode_selection = st.radio(
"Engage HUD Framework:",
["🧠 Audio Brain Dump", "🎯 Direct AI Commands"],
horizontal=True,
index=0 if st.session_state.mode == 'braindump' else 1
)
st.session_state.mode = 'braindump' if mode_selection == "🧠 Audio Brain Dump" else 'command'
if st.session_state.last_mode != st.session_state.mode:
st.session_state.processed_tasks = None
st.session_state.transcription = None
st.session_state.last_mode = st.session_state.mode
col_layout1, col_layout2 = st.columns([1, 1.3], gap="large")
with col_layout1:
st.header("🎙️ Sonic Capture Core")
if st.session_state.mode == 'braindump':
st.info("🧠 Brain Dump Sequence Active: Speak freely about your entire day. AI will filter and populate your inventory.")
else:
st.info("🎯 Tactical Command Module Active: Issue voice directives directly to the main system dashboard.")
audio_value = st.audio_input("Initiate Voice Scan Sync")
if audio_value:
current_hash = hash(str(audio_value.name) + str(audio_value.size))
if current_hash != st.session_state.current_audio_hash:
st.session_state.current_audio_hash = current_hash
st.audio(audio_value)
with st.spinner("Decoding vocal transmission waveforms..."):
transcription = whisper.transcribe(audio_value.read())
if transcription:
st.session_state.transcription = transcription
if st.session_state.mode == 'braindump':
with st.spinner("Parsing quest logs via LLM filters..."):
st.session_state.processed_tasks = llm.process_braindump(transcription)
else:
st.warning("⚠️ Command Mode routing: Please submit all custom audio macros directly via the AI Tactics Companion Panel in your sidebar HUD.")
st.session_state.transcription = None
if st.session_state.transcription:
st.text_area("Decrypted Transcription Raw Data:", st.session_state.transcription, height=80)
if st.session_state.processed_tasks:
st.markdown("#### 🌟 Discovered Quest Inventory")
for task in st.session_state.processed_tasks:
p_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task.get('priority', 'medium'), '⚪')
st.write(f"• {p_emoji} {task.get('text', task)}")
if st.button("📥 Upload Discovered Quests to Matrix Log", type="primary", use_container_width=True):
for task in st.session_state.processed_tasks:
task_manager.add_task(
task.get('text', '') if isinstance(task, dict) else task,
priority=task.get('priority', 'medium') if isinstance(task, dict) else 'medium',
category=task.get('category') if isinstance(task, dict) else None
)
tts_service.speak_confirmation('task_added', "Inventory Sync Complete!")
st.session_state.processed_tasks = None
st.session_state.transcription = None
st.rerun()
st.divider()
st.subheader("⚡ Quick Utility Settings")
col_util1, col_util2 = st.columns(2)
with col_util1:
if st.button("💥 WIPE ENTIRE MATRIX", type="secondary", use_container_width=True):
task_manager.clear_all()
tts_service.speak_confirmation('tasks_cleared')
st.rerun()
with col_util2:
if st.button("🤖 AUTO-OPTIMIZE LOGS", type="secondary", use_container_width=True):
task_manager.update_tasks(llm.prioritize_tasks(task_manager.get_tasks()))
tts_service.speak_confirmation('task_updated', "Logs optimized")
st.rerun()
with col_layout2:
st.header("📋 Active Quest Logbook")
tasks = task_manager.get_tasks()
if not tasks:
st.info("Your Quest Matrix is empty. Activate the Sonic Capture Core to add some objectives!")
else:
st.markdown("#### 🔍 Filter Parameters")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1: f_priority = st.selectbox("Tier", ["All", "High", "Medium", "Low"])
with col_f2: f_category = st.selectbox("Faction", ["All", "Client", "Business", "Personal"])
with col_f3: f_status = st.selectbox("Condition", ["All", "Pending", "Completed"])
filtered = tasks
if f_priority != "All": filtered = [t for t in filtered if t.get('priority') == f_priority.lower()]
if f_category != "All": filtered = [t for t in filtered if t.get('category') == f_category.lower()]
if f_status == "Pending": filtered = [t for t in filtered if not t['completed']]
elif f_status == "Completed": filtered = [t for t in filtered if t['completed']]
st.divider()
if not filtered:
st.info("No items match these filter parameters.")
else:
for task in filtered:
render_task(task, task_manager, tts_service)
st.markdown("", unsafe_allow_html=True)
if tasks:
st.divider()
render_stats(task_manager.get_stats())
if name == "main":
main()

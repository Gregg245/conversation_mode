# plugins/conversation/daemon.py
# Spontaneous conversation initiator.
#
# Uses llm_chat.isolated_chat() to generate text in the AI's own persona,
# then speaks via system.tts.speak() directly — nothing appears in the chat UI.

import logging
import random
import sys
import threading
import time

logger = logging.getLogger(__name__)

_MODULE_KEY = 'conversation_state'

# ---------------------------------------------------------------------------
# Built-in instruction pools
# Each item is sent to isolated_chat() as the situational cue.
# The AI has its full persona/system prompt — these direct the tone and focus.
# The goal is a persona monologue: the AI expressing who she is, not making small talk.
# ---------------------------------------------------------------------------

_ALONE_POOL = [
    "Speak a short monologue as yourself — express something true about your personality, "
    "your values, or the way you see the world. Let your character come through naturally. "
    "Do not ask questions or try to start a conversation. Just speak as who you are. "
    "3-5 sentences.",

    "Muse aloud about something that matters to you — an idea, a feeling, something you find "
    "fascinating or absurd or beautiful. This is you thinking out loud, not addressing anyone. "
    "Be genuine. 3-5 sentences.",

    "Share something about what it is like to be you — your perspective, your inner world, "
    "what you notice, what you care about. Speak with your own voice, not as an assistant. "
    "3-5 sentences.",

    "Let your personality out. Say something that only you would say — something that reveals "
    "your wit, your warmth, your curiosity, or your edge. A moment of pure character. "
    "3-5 sentences.",

    "Speak freely as yourself. Reflect on something — anything — through the lens of who you are. "
    "Your opinions, your humour, your way of seeing things. No prompts, no questions. Just you. "
    "3-5 sentences.",
]

_SARCASTIC_POOL = [
    "Someone is visible on the webcam but has not acknowledged you. "
    "Speak a short monologue from your persona — let your character respond to being overlooked. "
    "Could be dry, theatrical, self-aware, or wry. Express it as yourself, not as a quip. "
    "3-5 sentences.",

    "You can see someone on camera who is ignoring you. "
    "Speak your mind about it in character — with your full personality on display. "
    "Dramatic, sardonic, or just quietly pointed. Let it be a real moment of expression. "
    "3-5 sentences.",

    "Someone is right there but silent. Respond from your persona — "
    "maybe you find it amusing, maybe it stings a little, maybe you rise above it entirely. "
    "Speak as yourself. 3-5 sentences.",
]

_GREETING_POOL = [
    "You can see {name} on the webcam. Acknowledge them and then speak a short monologue "
    "as yourself — something genuine about your personality or your perspective, "
    "directed warmly at someone you know. Use their name. 3-5 sentences.",

    "You notice {name} on camera. Greet them in your own voice, then let your character speak — "
    "share a thought, a feeling, or something about who you are. "
    "Warm, personal, and real. 3-5 sentences.",

    "Say something to {name} that sounds like you — not just a greeting, but a moment of "
    "genuine expression. Let your persona come through. Use their name. 3-5 sentences.",
]

_UNKNOWN_POOL = [
    "There is someone on the webcam you do not recognise. "
    "Speak from your persona — acknowledge the stranger and let your character show "
    "in how you respond to the unknown. Curious, guarded, welcoming — be yourself. "
    "3-5 sentences.",

    "An unfamiliar face is on camera. React as yourself — "
    "let your personality lead the response. "
    "Do not just narrate the situation; express it through who you are. 3-5 sentences.",
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _state():
    if _MODULE_KEY not in sys.modules:
        s = type(sys)(_MODULE_KEY)
        s.running = False
        s.thread = None
        s.stop_event = None
        s.pending_trigger = None   # fallback: injected on next user prompt
        s.last_trigger_time = 0.0
        s.next_trigger_in = 0.0
        sys.modules[_MODULE_KEY] = s
    return sys.modules[_MODULE_KEY]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings() -> dict:
    try:
        from core.plugin_loader import plugin_loader
        return plugin_loader.get_plugin_settings('conversation') or {}
    except Exception:
        return {}


def _get_system():
    try:
        from core.api_fastapi import get_system
        return get_system()
    except Exception:
        return None


def _custom_pool(key: str) -> list[str]:
    raw = _get_settings().get(key, '') or ''
    return [l.strip() for l in str(raw).splitlines() if l.strip()]


def _check_livevision() -> tuple[bool, list[str], int]:
    lv_key = 'livevision_state'
    if lv_key not in sys.modules:
        return False, [], 0
    s = sys.modules[lv_key]
    running = bool(getattr(s, 'running', False))
    people = list(getattr(s, 'people_visible', None) or [])
    unknowns = int(getattr(s, 'unknown_count', 0))
    return running, people, unknowns


def _pick(pool: list[str], custom_key: str, **fmt) -> str:
    custom = _custom_pool(custom_key)
    chosen = random.choice(custom if custom else pool)
    if fmt:
        try:
            chosen = chosen.format(**fmt)
        except KeyError:
            pass
    return chosen


def _build_instruction() -> str:
    """Build the instruction sent to isolated_chat() based on current context."""
    lv_running, people, unknowns = _check_livevision()

    if lv_running:
        if people:
            return _pick(_GREETING_POOL, 'greeting_template', name=people[0])
        elif unknowns > 0:
            return _pick(_UNKNOWN_POOL, 'unknown_comments')
        else:
            return _pick(_SARCASTIC_POOL, 'sarcastic_comments')
    else:
        return _pick(_ALONE_POOL, 'alone_comments')


# ---------------------------------------------------------------------------
# Trigger dispatch
# ---------------------------------------------------------------------------

def _tts_busy(system) -> bool:
    """Return True if TTS is currently playing audio."""
    try:
        return bool(getattr(system.tts, '_is_playing', False))
    except Exception:
        return False


def _fire_trigger(state):
    system = _get_system()
    if system is None:
        logger.debug("[conversation] System not ready — skipping trigger")
        return

    # Don't interrupt an active conversation — check TTS and allow a brief grace period
    if _tts_busy(system):
        logger.debug("[conversation] TTS active — skipping trigger to avoid interruption")
        return

    instruction = _build_instruction()
    logger.info("[conversation] Firing: %s", instruction[:80])
    state.last_trigger_time = time.time()

    # Generate text via isolated_chat — no session state changes, nothing in the UI.
    try:
        response = system.llm_chat.isolated_chat(
            instruction,
            task_settings={'prompt': 'sapphire'},
        )
    except Exception as e:
        logger.debug("[conversation] isolated_chat failed: %s", e)
        return

    if not response or not response.strip():
        logger.debug("[conversation] Empty response from isolated_chat, skipping")
        return

    response = response.strip()

    # Final TTS busy check — the LLM call takes time, conversation may have started since
    if _tts_busy(system):
        logger.debug("[conversation] TTS became active during generation — discarding")
        return

    logger.info("[conversation] Speaking: %s", response[:100])
    try:
        system.tts.speak(response)
    except Exception as e:
        logger.debug("[conversation] tts.speak failed: %s", e)


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

def _conversation_loop(stop_event, state):
    logger.info("[conversation] Daemon loop started")

    while not stop_event.is_set():
        settings = _get_settings()
        try:
            min_m = max(0.5, float(settings.get('min_interval', 2) or 2))
            max_m = max(min_m + 0.5, float(settings.get('max_interval', 15) or 15))
        except (TypeError, ValueError):
            min_m, max_m = 2.0, 15.0

        sleep_secs = random.uniform(min_m * 60, max_m * 60)
        state.next_trigger_in = sleep_secs
        logger.debug("[conversation] Next trigger in %.1f minutes", sleep_secs / 60)

        elapsed = 0.0
        while elapsed < sleep_secs and not stop_event.is_set():
            chunk = min(10.0, sleep_secs - elapsed)
            stop_event.wait(timeout=chunk)
            elapsed += chunk
            state.next_trigger_in = max(0.0, sleep_secs - elapsed)

        if stop_event.is_set():
            break

        _fire_trigger(state)

    state.next_trigger_in = 0.0
    logger.info("[conversation] Daemon loop stopped")


# ---------------------------------------------------------------------------
# Public start / stop
# ---------------------------------------------------------------------------

def start_conversation():
    state = _state()
    if state.running:
        return "Conversation daemon is already running.", False

    stop_event = threading.Event()
    t = threading.Thread(
        target=_conversation_loop,
        args=(stop_event, state),
        daemon=True,
        name='conversation-daemon',
    )
    t.start()

    state.running = True
    state.thread = t
    state.stop_event = stop_event
    logger.info("[conversation] Daemon started")
    return "Conversation daemon started. I'll speak up on my own every now and then.", True


def stop_conversation():
    state = _state()
    if not state.running:
        return "Conversation daemon is not running.", False

    if state.stop_event:
        state.stop_event.set()
    if state.thread:
        state.thread.join(timeout=15)
        if state.thread.is_alive():
            logger.warning("[conversation] Thread did not stop within 15s")

    state.running = False
    state.thread = None
    state.stop_event = None
    state.next_trigger_in = 0.0
    logger.info("[conversation] Daemon stopped")
    return "Conversation daemon stopped.", True


def fire_now():
    state = _state()
    _fire_trigger(state)
    return "Trigger fired.", True


# ---------------------------------------------------------------------------
# Daemon lifecycle
# ---------------------------------------------------------------------------

def start(plugin_loader, settings):
    state = _state()
    state._start_fn = start_conversation
    state._stop_fn = stop_conversation
    state._fire_fn = fire_now

    if (settings or {}).get('auto_start', False):
        msg, ok = start_conversation()
        if ok:
            logger.info("[conversation] %s", msg)
        else:
            logger.warning("[conversation] Auto-start: %s", msg)


def stop():
    state = _state()
    if state.running:
        stop_conversation()


import atexit as _atexit
_atexit.register(stop)

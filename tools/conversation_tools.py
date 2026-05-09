# plugins/conversation/tools/conversation_tools.py
# Tools to control the spontaneous conversation daemon.

import logging
import sys
import time

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = '💬'
AVAILABLE_FUNCTIONS = [
    'start_conversation_mode',
    'stop_conversation_mode',
    'conversation_status',
    'fire_conversation_now',
]

TOOLS = [
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "start_conversation_mode",
            "description": (
                "Start the spontaneous conversation daemon. "
                "The AI will break the silence every 2–15 minutes (configurable) with a random comment. "
                "Integrates with livevision if active."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "stop_conversation_mode",
            "description": "Stop the spontaneous conversation daemon.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "conversation_status",
            "description": "Check whether the spontaneous conversation daemon is running and when it will next fire.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "fire_conversation_now",
            "description": (
                "Immediately fire a spontaneous conversation trigger, skipping the timer. "
                "Useful for testing or when you just want to say something right now."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ---------------------------------------------------------------------------
# State access
# ---------------------------------------------------------------------------

_MODULE_KEY = 'conversation_state'


def _state():
    return sys.modules.get(_MODULE_KEY)


def _get_settings() -> dict:
    try:
        from core.plugin_loader import plugin_loader
        return plugin_loader.get_plugin_settings('conversation') or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _start_conversation(arguments):
    state = _state()
    if state is None:
        return "Conversation daemon module is not loaded — restart Sapphire and try again.", False

    start_fn = getattr(state, '_start_fn', None)
    if start_fn is None:
        return "Conversation daemon is not initialised — restart Sapphire and try again.", False

    try:
        return start_fn()
    except Exception as e:
        logger.error("[conversation] start failed: %s", e, exc_info=True)
        return f"Failed to start conversation daemon: {e}", False


def _stop_conversation(arguments):
    state = _state()
    if state is None:
        return "Conversation daemon module is not loaded.", False

    stop_fn = getattr(state, '_stop_fn', None)
    if stop_fn is None:
        return "Conversation daemon is not initialised.", False

    try:
        return stop_fn()
    except Exception as e:
        logger.error("[conversation] stop failed: %s", e, exc_info=True)
        return f"Failed to stop conversation daemon: {e}", False


def _conversation_status(arguments):
    state = _state()
    if state is None or not getattr(state, 'running', False):
        return "Spontaneous conversation is OFF. Use start_conversation_mode to enable it.", True

    settings = _get_settings()
    min_m = settings.get('min_interval', 2)
    max_m = settings.get('max_interval', 15)
    next_in = getattr(state, 'next_trigger_in', 0.0)
    last_t = getattr(state, 'last_trigger_time', 0.0)

    lines = [f"Spontaneous conversation is ON (interval: {min_m}–{max_m} min)."]
    if next_in > 0:
        lines.append(f"Next trigger in: {next_in / 60:.1f} minutes.")
    if last_t:
        ago = time.time() - last_t
        lines.append(f"Last trigger: {ago / 60:.1f} minutes ago.")
    else:
        lines.append("No trigger fired yet this session.")

    return " ".join(lines), True


def _fire_now(arguments):
    state = _state()
    if state is None:
        return "Conversation daemon module is not loaded.", False

    fire_fn = getattr(state, '_fire_fn', None)
    if fire_fn is None:
        return "Conversation daemon is not initialised.", False

    try:
        return fire_fn()
    except Exception as e:
        logger.error("[conversation] fire_now failed: %s", e, exc_info=True)
        return f"Failed to fire trigger: {e}", False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def execute(function_name, arguments, config):
    try:
        if function_name == 'start_conversation_mode':
            return _start_conversation(arguments)
        elif function_name == 'stop_conversation_mode':
            return _stop_conversation(arguments)
        elif function_name == 'conversation_status':
            return _conversation_status(arguments)
        elif function_name == 'fire_conversation_now':
            return _fire_now(arguments)
        return f"Unknown function: {function_name}", False
    except Exception as e:
        logger.error("[conversation] %s crashed: %s", function_name, e, exc_info=True)
        return f"Conversation plugin error in {function_name}: {e}", False

# plugins/conversation/hooks/prompt_inject.py
# Fallback: if process_llm_query() was unavailable when the timer fired,
# the pending trigger is injected here on the next user interaction.

import sys


def prompt_inject(event):
    try:
        state = sys.modules.get('conversation_state')
        if state is None:
            return
        trigger = getattr(state, 'pending_trigger', None)
        if not trigger:
            return
        state.pending_trigger = None
        event.context_parts.append(trigger)
    except Exception:
        pass

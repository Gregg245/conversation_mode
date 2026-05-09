# Conversation Mode Plugin for Sapphire

Spontaneous persona monologue — after a random pause (default 2–15 min), the AI speaks aloud as herself, expressing her character, inner world, and personality. Nothing appears in the chat; she just talks. Integrates with the LiveVision plugin to tailor the monologue to who is present.

## Setup

### 1. Enable the plugin
Settings > Plugins > Conversation Mode > Enable

### 2. No additional packages required
This plugin uses only Sapphire internals. No pip installs, no system packages. Works on Linux and Windows as-is.

### 3. Optional — enable LiveVision for camera-aware monologues
If the LiveVision plugin is also active, the AI will check the webcam before speaking:
- **Recognised person visible** — monologue addressed warmly to that person by name
- **Unknown person visible** — persona response to an unfamiliar presence
- **Camera on, nobody visible** — persona response to being overlooked
- **LiveVision off or unavailable** — pure persona monologue, no audience assumed

## Usage

Ask Sapphire things like:

- "Start conversation mode"
- "Stop conversation mode"
- "Conversation status"
- "Fire a conversation trigger now" *(useful for testing)*

Once started, the AI will speak up on its own at random intervals — nothing appears in the chat, it just talks.

## Settings

- **Auto-start on launch** — automatically begin when Sapphire starts
- **Minimum interval (minutes)** — shortest time between monologues. Default 2
- **Maximum interval (minutes)** — longest time between monologues. Default 15
- **Alone / no-webcam monologue prompts** — custom prompts directing the AI's persona when LiveVision is off (one per line). Leave blank to use the built-in pool
- **Ignored / no interaction monologue prompts** — custom prompts for when someone is visible but not talking (one per line). Leave blank to use the built-in pool
- **Recognised person monologue prompts** — custom prompts when LiveVision recognises someone; use `{name}` as a placeholder (one per line). Leave blank to use the built-in pool
- **Unknown visitor monologue prompts** — custom prompts for unrecognised faces (one per line). Leave blank to use the built-in pool

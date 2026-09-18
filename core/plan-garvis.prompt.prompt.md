# Plan: Migrate from Ollama to LMStudio Backend

## TL;DR
Replace the Ollama backend in `ai_brain.py` with LMStudio's OpenAI-compatible API (running on localhost:1234). LMStudio uses the same OpenAI chat protocol, so the refactor involves updating imports, the API call structure, and configuration. All existing conversation history and queue-based threading can remain unchanged.

## Context
- **Current setup**: Using `ollama` Python library to call `qwen2.5:3b` model
- **Target setup**: LMStudio OpenAI-compatible API on port 1234 with `mistralai/ministral-3-14b-reasoning`
- **Architecture**: Queue-based threading with message history already in place
- **No breaking changes to UI or gesture engine** — interface remains identical

## Steps

### Phase 1: Update Dependencies
1. Remove `ollama` from the import statements in `ai_brain.py`
2. Add `openai` Python package to `requirements.txt` (LMStudio exposes an OpenAI-compatible API)
3. No changes needed to `settings.yaml` structure — keep `ai.model` as is (for consistency, though LMStudio loads the model at startup, not by name)

### Phase 2: Refactor `ai_brain.py` for LMStudio
1. Replace `import ollama` with `from openai import OpenAI`
2. Initialize OpenAI client in `AIBrain.__init__()` pointing to LMStudio's API:
   - `client = OpenAI(api_key="not-needed", base_url="http://localhost:1234/v1")`
   - Store this as `self.client`
3. Replace `_call_ollama()` method with `_call_lmstudio()`:
   - Update the API call from `ollama.chat(model=self.model, messages=messages)` to `self.client.chat.completions.create(model="local-model", messages=messages, temperature=config["ai"]["temperature"])`
   - Extract response with `.choices[0].message.content` instead of `["message"]["content"]`
4. Update print statement in `__init__` from `"Ollama Brain san sang!"` to `"LMStudio Brain san sang!"`
5. Update error handling label from `[AI Error]` to `[LMStudio Error]` (optional, for clarity)

### Phase 3: Configuration & Testing
1. Verify LMStudio is running on localhost:1234 and model is loaded
2. Test the chat flow end-to-end (trigger `ask()` → verify response queues correctly)
3. Confirm temperature, history, and system prompt still work as expected
4. No changes needed to `ask_gesture()` or gesture/voice/TTS integration

## Relevant Files
- `core/ai_brain.py` — main refactor target (`_call_ollama()` → `_call_lmstudio()`, imports, initialization)
- `requirements.txt` — add `openai` package
- `config/settings.yaml` — no changes needed (model is loaded in LMStudio UI, not by name in config)

## Verification
1. **Startup verification**: Run `main.py` and confirm print shows "LMStudio Brain san sang!" with no connection errors
2. **API connectivity**: Trigger `ask("test message")` via gesture or voice and verify response appears without timeouts
3. **History & context**: Ask multi-turn questions (e.g., "My name is [X]" → "What's my name?") and confirm LMStudio maintains context correctly
4. **Temperature behavior**: Verify responses use the configured temperature (currently 0.7) from settings.yaml
5. **Gesture responses**: Test fixed gesture responses (`OPEN_PALM`, `FIST`, etc.) still trigger correctly

## Decisions
- **API key handling**: Using empty API key (`"not-needed"`) because LMStudio doesn't require auth for localhost
- **Model parameter**: LMStudio API expects a model name in the request; using `"local-model"` as a generic placeholder (LMStudio ignores it and uses whatever is loaded)
- **Ollama removal**: Complete removal (no fallback) per user's request to fully migrate
- **Settings.yaml unchanged**: Keeping `ai.model` in config for compatibility, even though LMStudio loads the model at startup

## Further Considerations
1. **Mistral model capability**: `ministral-3-14b-reasoning` is more capable than `qwen2.5:3b` — may produce longer responses. Consider if you need to adjust system prompt for conciseness or add response trimming.
2. **Performance**: Verify LMStudio performance on your hardware vs. Ollama (3B vs 14B model is larger; may need hardware upgrade if issues arise).
3. **Future fallback**: If you want to add Ollama as a fallback (not currently planned), structure could use factory pattern to switch backends via config.

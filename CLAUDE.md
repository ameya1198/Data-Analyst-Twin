# Anvaya — Data Analyst Twin

AI-powered data analysis platform with a FastAPI backend (multi-specialist agent) and a Next.js frontend.

## Project Structure

```
Data Analyst Twin/
├── backend/          # FastAPI + WebSocket agent server
│   └── app/
│       ├── agent/         # Supervisor, Planner, Executor, Reflector, Specialists
│       ├── api/routes/    # chat.py (WebSocket), data.py, sessions.py, metrics.py
│       ├── guardrails/    # Rate limiting, confirmation, validation
│       ├── connectors/    # File ingestion (CSV/Excel/JSON/Parquet)
│       ├── models/        # Pydantic schemas
│       └── observability/ # Structured logging, metrics
└── frontend/         # Next.js 16 + React 19 + Zustand
    └── components/
        ├── chat/          # ChatInterface, MessageBubble, StreamEvent renderers
        ├── data/          # Upload panel, dataset preview
        └── charts/        # Plotly chart renderer
```

## Dev Commands

```bash
# Backend (from /backend)
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend (from /frontend)
npm run dev          # starts on port 3000
```

## Key Architecture Decisions

- **Intent-based routing**: rule-based classifier (zero LLM cost) sends requests to DIRECT / FOCUSED / FULL / CONVERSATIONAL mode
- **Plan → Execute → Reflect loop**: Planner generates steps, Executor runs them via specialist registry, Reflector evaluates quality
- **Multi-specialist design**: EDA, SQL (DuckDB), Viz (Plotly), Stats (scipy), Cleaning — each a `BaseSpecialist` subclass
- **Shared `AnalysisContext`**: all specialists read/write one context object so results compose naturally
- **WebSocket streaming**: every agent event (INTENT, PLAN, SPECIALIST_CALL, SPECIALIST_RESULT, REFLECTION, FINAL_RESPONSE) is streamed in real time
- **Session persistence**: SQLite via SQLAlchemy async; conversation memory survives server restarts

## Project Skills

Skills live in `.cursor/skills/`. Reference them by name in the Claude Code chat panel when relevant:

```
@brainstorming        — planning and ideation
@debugging-strategies — structured troubleshooting
@architecture         — system design decisions
```

**How to invoke:**

1. Open the Claude Code chat panel (Cmd+Shift+C or the sidebar icon)
2. Reference the skill naturally in your prompt:
   ```
   Use @debugging-strategies to help me find why the EDA specialist returns wrong averages
   ```
3. Claude will load and apply the skill's framework to your problem

## Guardrails & Limits

| Setting | Default | Config key |
|---|---|---|
| LLM calls per session | 50 | `max_llm_calls_per_session` |
| Specialist calls per turn | 15 | `max_specialist_calls_per_turn` |
| WS messages per 60 s | 30 | `_WS_RATE_LIMIT` in `chat.py` |
| Confirmation timeout | 120 s | `confirmation_timeout_seconds` |
| Upload file max age | 48 h | `_cleanup_upload_dir()` at startup |

## Common Gotchas

- **Column type detection**: `_classify_column` in `eda.py` strips currency/comma formatting before numeric coercion. If adding a new column type check, add it before the `_is_string_like` branch.
- **Dataset IDs**: UUIDs, not filenames. Planner prompts include the exact `dataset_id` — always use it in `tool_params`.
- **`to_llm_context()` cap**: currently 20 columns / 10 SQL preview rows. Increase if synthesis LLM misses columns in wide datasets.
- **`_supervisors` dict**: one per WebSocket session, cleaned up in the `finally` block of `chat_websocket`.
- **Zustand persistence**: only `status === "complete"` messages are saved to localStorage. In-progress/streaming state is never frozen.

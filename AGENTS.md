# AGENTS.md

Guidance for AI coding agents working in this repository.

A FastAPI backend runs a LangGraph state machine (chain-of-thought → telemetry →
embedding → vector search → persistence → LLM recommendation) and checkpoints its
state to MongoDB via `MongoDBSaver`. A Next.js frontend calls the backend through its
own API routes as a thin proxy, and renders the workflow log next to the MongoDB
documents each run produces.

## Build and test commands

```bash
# Backend, from agent/backend/
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python create_issue_embeddings.py   # seed past_issues (skips if already seeded)
python create_vector_index.py       # create issues_index (skips if it exists)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend, from agent/frontend/
npm install
npm run dev
```

**There is no automated test suite in this repository.** `pytest` and `npm test` do
not exist. To verify a change, run the backend and frontend together and exercise the
affected flow through the UI (see Smoke check below). Do not claim tests pass — there
are none.

Smoke check after a change:

1. Start the backend, then the frontend; open http://localhost:3000
2. Click "New Diagnosis", enter an issue report, click "Run Agent"
3. Confirm the left column shows the full workflow log ending in a recommendation, and
   the right column's `agent_sessions` document has `"status": "completed"`
4. If the change touches `main.py`, restart the backend manually first — it's commonly
   run without `--reload` during testing, so edits won't take effect until restarted

## Project structure

```
agent/
  backend/
    main.py                    # FastAPI app: the LangGraph workflow, all routes, all MongoDB access
    create_issue_embeddings.py # seeds past_issues with Voyage AI embeddings
    create_vector_index.py     # creates the issues_index vectorSearch index
    data/telemetry_data.csv    # simulated vehicle sensor readings
    requirements.txt           # unpinned -- pip install always resolves to latest
  frontend/
    app/page.jsx                       # the two-column dashboard UI
    app/components/InfoWizard.jsx      # the "Tell me more!" modal (leafygreen-ui Tabs + Modal)
    app/api/run-agent/route.js         # proxies GET to backend :8000/api/run-agent
    app/api/resume-agent/route.js      # proxies GET to backend :8000/api/resume-agent
    app/api/get-sessions/route.js      # proxies GET to backend :8000/api/get-sessions
    app/api/get-run-documents/route.js # proxies GET to backend :8000/api/get-run-documents
    app/api/run-agent-sse/route.js     # dead code, marked "NOT USED" in a comment
```

Notable files:

- `main.py` is the entire backend — routes, the LangGraph graph definition, and every
  MongoDB read/write live in this one file. There's no separate service/repository
  layer to route around.
- The frontend never talks to MongoDB directly; it always goes through the FastAPI
  backend at a hardcoded `http://localhost:8000`. Deploying frontend and backend to
  different hosts requires changing that URL in each `app/api/*/route.js` file.
- `data/telemetry_data.csv` is the only source of "sensor" data — there's no live
  telemetry feed. The README calls this out as a stand-in for a production API.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/run-agent?issue_report=...` | Runs the full LangGraph workflow for a new issue report |
| GET | `/api/resume-agent?thread_id=...` | Looks up a prior session by thread ID |
| GET | `/api/get-sessions` | Lists the 10 most recent sessions |
| GET | `/api/get-run-documents?thread_id=...` | Fetches one document from each collection for a given run, for the UI's right column |

## Environment variables and configuration

| Name | Required | Example | Description |
| --- | --- | --- | --- |
| `MONGO_URI` | Yes | `mongodb+srv://...` | Atlas connection string |
| `DATABASE` | Yes | `fleet_issues` | Database for everything except LangGraph checkpoints |
| `APP_NAME` | No | `devrel-demo-langgraph-voyageai-fleet` | MongoDB client `appName` for Atlas attribution |
| `TELEMETRY_PATH` | Yes | `data/telemetry_data.csv` | Path to the simulated telemetry CSV |
| `VECTOR_SEARCH_INDEX` | Yes | `issues_index` | Must match the index name `create_vector_index.py` created |
| `OPENAI_API_KEY` | Yes | | Used for chain-of-thought and the final recommendation (`gpt-4o`) |
| `VOYAGE_API_KEY` | Yes | | Used for embeddings (`voyage-3-large`) |

Constraints worth knowing before you debug a failure:

- **LangGraph checkpoints always go to a database literally named `checkpointing_db`**,
  independent of `DATABASE` — it's hardcoded as `MongoDBSaver`'s default, not read from
  an env var. Don't go looking for checkpoints in the `DATABASE` database.
- **`MongoDBSaver.from_conn_string`'s `**kwargs` are forwarded to `MongoDBSaver.__init__`,
  not to the `MongoClient` it builds internally** — there's no way to set `appName` (or
  any other client option) through it. `main.py`'s `create_mongodb_saver()` works
  around this with its own context manager that builds the `MongoClient` directly.
- **Vector search silently returns nothing if `issues_index` doesn't exist or isn't
  queryable yet** — `vector_search_tool()` catches the resulting exception and falls
  back to a generic "Vector search error" issue rather than crashing the run. A missing
  index looks like a working-but-unhelpful agent, not an obvious error.
- **`historical_recommendations.similar_issues` and `logs.similar_issues` store full
  match documents from `past_issues`, embeddings included** — see EDD.md's Known
  inconsistencies. Not wrong, just wasteful; be aware before treating document size as
  a signal of anything.
- **Telemetry numeric fields (`engine_temperature`, `oil_pressure`,
  `avg_fuel_consumption`) are persisted as strings**, cast to `float()` only at the
  point of use in Python. A MongoDB-side numeric query against `telemetry_data` (e.g.
  `$gt`) will not match these fields as stored.
- **Frontend and backend are two separate processes with no shared config** — a
  `.env` change in `agent/backend/` has no effect on the frontend, and vice versa.

## MongoDB Skills

Use the official MongoDB agent skills from https://github.com/mongodb/agent-skills
whenever the task is MongoDB-specific and a matching skill exists.

## When To Use EDD.md

Use [EDD.md](./EDD.md) as the source of truth for the MongoDB data model in this repository.

Consult [EDD.md](./EDD.md) before making changes that touch:

- MongoDB collections, document structure, or field names
- FastAPI routes that read or write database records
- Validation, form fields, API payloads, or UI that depend on persisted data
- Schema documentation, Mermaid diagrams, or entity modeling discussions

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A locally-run C++ quiz/practice app built on **Streamlit**. Users practice single-choice and true/false questions organized by exam (GESP) and knowledge point, review mistakes, manage the question bank, and ask an LLM for explanations. The UI text is Chinese; code (functions/variables) is English.

## Commands

### Run the app
```bash
./run.bat            # Windows: clears caches, installs deps, launches app
streamlit run app/0_Overview.py   # manual launch (run.bat is preferred)
```
Do **not** use `streamlit run app.py` — there is no `app.py`. The entry point is `app/0_Overview.py`, and Streamlit auto-discovers pages in `app/pages/`.

`run.bat` clears `__pycache__` and the Streamlit cache on every launch and installs deps via the Tsinghua pip mirror. If code changes aren't taking effect, run `run.bat` or manually delete `__pycache__` dirs.

### Tests
```bash
python -m pytest tests/ -v                 # all unit tests
python -m pytest tests/test_question_loader.py -v   # single file
python -m pytest tests/test_question_loader.py::TestLoadQuestions::test_load_valid_json  # single test
python test_app.py                        # smoke test: imports + basic functionality
```
Tests rely on the real `question_bank/gesp4-2606.json` fixture (they assert exact counts like 6 questions, specific knowledge points) — keep that file stable or update assertions together.

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Two data stores with different lifecycles
The app has two SQLite databases that must not be confused:

1. **`data/practice_log.db`** — **user state, persistent and append-only.** Managed by `app/core/practice_tracker.py` (`PracticeTracker` class + functional wrappers). Single table `practice_log` keyed by `question_id`, tracking `correct_count`/`wrong_count`, `mastered` flag, and timestamps. This data is not rebuildable — schema changes need migrations, never `DROP TABLE`.

2. **`data/question_bank_index.db`** — **derived index, fully rebuildable.** Managed by `app/core/question_loader.py`. The function `build_question_bank_index()` scans all `question_bank/*.json`, computes per-knowledge-point frequency buckets (必考/常考/其他), and writes the `question_index` table. `ensure_index_exists()` auto-builds it on first query. The index stores `(source_file, question_index)` pointers back into the JSON — filtered queries (`get_questions_by_filter`) resolve in the index then lazily load the actual question dicts from JSON. Knowledge points are stored as a JSON-array string and queried with `LIKE '%"kp"%'`. If you change the JSON question bank, rebuild the index (the UI has "刷新题库索引" buttons; saving edits in the management page auto-rebuilds).

**Source of truth for questions is the JSON files in `question_bank/`**, never the index DB.

### Dual knowledge-point format (new vs. legacy)
Every loader and UI function handles two coexisting schemas:
- **New**: `knowledge_points: ["变量与数据类型", ...]` (list) + per-question `exam: {type, level, date}` + `frequency`.
- **Legacy**: `knowledge_point: "变量与数据类型"` (single string), no `exam` field.

When adding question-handling code, support both — check `q.get("knowledge_points", [])` first, fall back to `q.get("knowledge_point")`. See the repeated pattern in `question_loader.py` and `practice_ui.py`.

### Page structure & shared practice UI
Streamlit multipage app:
- `app/0_Overview.py` — dashboard: knowledge-point frequency/completion/accuracy bar charts (plotly).
- `app/pages/1_Practice.py` — filter sidebar (exam type, level, frequency, knowledge points) → filtered question set → practice.
- `app/pages/2_Review.py` — mistake review; modes: all / by knowledge point / high-frequency / random.
- `app/pages/3_Question_bank_manage.py` — bank overview, table view, raw-JSON editor with validation, add-from-template.

`app/core/practice_ui.py::render_practice_ui()` is the **shared rendering component** for an individual question. It is parameterized by `is_mistake_mode` and an `on_remove_from_mistake` callback, and returns an **action dict** `{'action': 'next'|'stay'|'remove', 'next_index': int}`. Pages own `st.session_state` (e.g. `filtered_questions`, `current_index`, `mistake_questions`) and call `st.rerun()` based on the returned action. When building new practice flows, reuse `render_practice_ui` rather than re-implementing question rendering.

Note: mistake mode (`2_Review.py`) still loads from the single hardcoded `question_bank/gesp4-2606.json` via `load_questions`/`get_question_by_id`, while the practice page uses the filter index across all JSON files. This is a known asymmetry — if you touch mistake loading, align it with the index-based loader.

### AI / LLM integration
`app/core/ai_chat.py::ask_question(question, context)` uses the **OpenAI SDK** pointed at an OpenAI-compatible endpoint configured entirely via `.env`:
```
LLM_API_KEY=...
LLM_BASE_URL=...     # e.g. https://api.deepseek.com
LLM_MODEL=...         # e.g. deepseek-chat
```
It is provider-agnostic (DeepSeek, GLM, OpenAI all work). When `context` is provided, a system prompt is built from the current question / user answer / correct answer. AI is optional — missing `LLM_API_KEY` returns a friendly message and the rest of the app works fine. `tests/test_ai_chat.py` mocks `OpenAI` and sets env vars per-test.

## Conventions

- **File encoding must be UTF-8.** Chinese UI text is everywhere; non-UTF-8 `.py` files cause garbled rendering.
- **Streamlit widget `key`s must be English/IDs, never Chinese** — Chinese keys cause cache/session issues. UI labels may be Chinese.
- Every page prepends the project root to `sys.path` (`project_root = Path(__file__).parent.parent[.parent]; sys.path.insert(0, ...)`) so `from app.core...` imports resolve when Streamlit runs a page directly. Keep this shim in any new page file.
- DB paths are hardcoded relative (`data/practice_log.db`, `data/question_bank_index.db`) and the `data/` dir is created on demand. The app expects to be launched from the project root.
- The raw-JSON editor in the management page validates required fields (`id`, `knowledge_points` as a list, `type`, `question`, `answer`, `explanation`; `options` required for `single_choice`) before writing — extend this validation if you add new required fields.

## Planned / in-progress work

`docs/superpowers/specs/2026-07-08-pdf-upload-and-single-question-edit-design.md` specifies (design stage, not yet implemented): batch PDF upload with LLM parsing into JSON, a new `app/core/pdf_parser.py`, single-question editing replacing the full-JSON editor, and flattening `past_exam/` PDF storage. Check this doc before working on bank management or PDF features.

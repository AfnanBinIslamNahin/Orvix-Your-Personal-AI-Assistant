# Orvix QA Status Report

**Audit date:** 2026-10-29
**Scope:** Repository review, focused security and reliability fixes, automated regression coverage, and local Streamlit smoke test.
**Baseline:** Git working tree was clean at `fce59c8` before audit changes. The existing `assistant.db` was checked with SQLite `PRAGMA quick_check` (`ok`); its contents were not altered.

## Summary

Orvix is a local Streamlit application with SQLite persistence, Gemini and optional OpenAI answer providers, PDF extraction and retrieval, voice features, and limited macOS commands. It is a personal-use prototype rather than a production or multi-user service.

The audit found that the unauthenticated Streamlit server listened on all interfaces by default, and the local `.env` and SQLite database were world-readable. Both risks were reduced: Streamlit now binds to loopback, the existing files have private permissions, and SQLite creates/opens its database with owner-only permissions on POSIX. No database records were deleted or migrated.

The isolated Python 3.11 install, all 42 automated tests, compilation, dependency consistency check, and local HTTP smoke test passed. Live Gemini and OpenAI API behavior was not tested. The configured OpenAI credential is currently rejected as expired, and Gemini live requests may be quota limited; keep provider status marked externally blocked until credentials and quota are available.

## Repository and baseline

- Entry point: `app.py` (Streamlit UI and request/session orchestration).
- AI/PDF/voice: `assistant.py` (Gemini, PDF extraction and retrieval, transcription, TTS) and `openai_engine.py` (optional OpenAI chat/model listing).
- Local commands: `desktop_actions.py` (macOS app/file launch, Google search and bounded Calculator input).
- Persistence: `storage.py` (SQLite chats, messages, notes, and documents).
- Runtime: Python 3.11; the repository includes unittest coverage and Streamlit AppTest workflows.
- Local state: `.env`, `assistant.db`, `.venv311`; these were preserved. A separate ignored `.venv-qa` was used for clean dependency installation.
- No pre-existing `PROJECT_STATUS_REPORT.md` was present; this report was added for the requested audit deliverable.

## Findings and fixes

| ID | Severity / priority | Finding and impact | Action and regression evidence | Remaining risk |
|---|---|---|---|---|
| SEC-01 | High / P1 | Unauthenticated Streamlit UI exposed on all interfaces could allow other network users to access chats and invoke supported local commands. | Bound server to `127.0.0.1`; test `test_local_streamlit_server_is_bound_to_loopback`; runtime `lsof` confirmed `127.0.0.1:8502`, HTTP 200. | Local browser users share the same app and data; public deployment remains unsupported. |
| SEC-02 | High / P1 | `.env` and `assistant.db` had permissions allowing other local accounts to read API credentials and personal data. | Changed both existing file modes to `0600` without reading or changing their contents; `storage.py` creates new SQLite files privately and tightens existing database permissions; test `test_database_file_is_private_to_current_user`. | POSIX-only permission behavior; backups and copied files need equivalent protection. |
| REL-01 | Medium / P2 | Gemini TTS model integration requires a newer SDK API than the previous declared minimum allowed, so a clean install could fail at runtime. | Raised `google-genai` minimum to `2.25.0`; clean Python 3.11 dependency install and TTS mock tests pass. | Provider-side model access/quota is not validated by mocked tests. |
| REL-02 | Medium / P2 | UI tests had stale expectations for the current Agent mode and did not protect newer OpenAI, quota fallback, and failed-answer flows. | Updated UI expectations and added AppTest coverage for model listing display, message retention on provider failure, and browser speech fallback. | Real provider/network interactions remain untested. |
| REL-03 | Low / P3 | The app used deprecated `streamlit.components.v1.html` for HTML and browser speech. | Migrated to `st.html`; dynamic speech text is JSON-escaped and JavaScript is explicitly enabled only for the speech button. Regression test ensures deprecated calls are absent. | Browser-specific speech voices vary by OS/browser. |
| DOC-01 | Low / P3 | Setup and test instructions did not clearly describe the supported Python version, local-only binding, or current test command. | Updated README and `.env.example`; configured a current stable Gemini chat model default and documented provider credentials. | Model/account availability can change; users may need to override model IDs. |

## QA test report

| Test ID | Category | Result | Evidence | Notes |
|---|---|---|---|---|
| BASE-01 | Baseline / compilation | PASS | Python 3.11 `compileall` completed. | Before changes. |
| BASE-02 | Baseline / existing unit and UI tests | FAIL (reproduced) | 23/26 passed; 3 failures were stale assertions for the former Mac command mode and pre-Agent greeting behavior. | Test expectations updated to match actual Agent mode. |
| DB-01 | Database integrity | PASS | SQLite `PRAGMA quick_check` returned `ok`. | Existing user database contents preserved. |
| UNIT-01 | Unit/integration regression suite | PASS | 42 tests passed using isolated Python 3.11 environment. | Provider calls and OS commands are mocked. |
| STATIC-01 | Syntax/compilation | PASS | `.venv-qa/bin/python -m compileall -q ...` | Includes app modules and tests. |
| DEPS-01 | Dependency consistency | PASS | `.venv-qa/bin/python -m pip check`: no broken requirements. | Clean environment installed from `requirements.txt`. |
| DIFF-01 | Patch integrity | PASS | `git diff --check` exited successfully. | No whitespace errors. |
| UI-01 | Streamlit UI workflows | PASS | Streamlit AppTest workflows included in the 42 passing unittest cases. | Not a browser-driven visual test. |
| SMOKE-01 | Application startup/local HTTP | PASS | Streamlit started, `curl` received HTTP 200; `lsof` showed `127.0.0.1:8502`. | Temporary server was stopped after check. |
| API-01 | Gemini live API | BLOCKED | Not called during audit. User's prior quota error and account-specific access prevent safe verification. | Requires working account quota and explicit live integration configuration. |
| API-02 | OpenAI live API | BLOCKED | Existing account model request returned an expired-credential authorization error in prior inspection. | Credential value was not exposed; update it outside this audit before testing. |
| LINT-01 | Ruff/mypy/coverage | NOT TESTED | Not installed/configured in project environment. | No new tooling dependencies were added solely for this audit. |
| SEC-03 | Dependency vulnerability scan | NOT TESTED | No vulnerability scanner configured or installed. | `pip check` checks dependency consistency, not known CVEs. |
| E2E-01 | Real macOS application/audio/PDF provider workflow | NOT TESTED | Unit/AppTest workflows mock external services and OS commands. | Hardware, browser audio, live model access, and actual app launches need manual or separately configured integration testing. |

## Test execution

- Total automated tests collected and executed: **42**.
- Passed: **42**; failed: **0**; skipped: **0**.
- Baseline failures before test updates: **3**, all stale test assertions; all were corrected and the final suite passed.
- Compilation: passed.
- `pip check`: passed.
- `git diff --check`: passed.
- Coverage: not measured.
- Lint/type checks: not run; Ruff and mypy are not configured in the repository.
- Automated security/dependency vulnerability scan: not run.
- Smoke test: passed, HTTP 200 on loopback only.
- A malformed-PDF negative test logs expected parser diagnostics to stderr while correctly rejecting the input.

Commands executed for final validation:

```bash
.venv-qa/bin/python -m unittest discover -s tests -v
.venv-qa/bin/python -m compileall -q app.py assistant.py desktop_actions.py openai_engine.py storage.py tests
.venv-qa/bin/python -m pip check
git diff --check
.venv-qa/bin/python -m streamlit run app.py --server.port 8502 --server.headless true
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8502
lsof -nP -iTCP:8502 -sTCP:LISTEN
```

## Remaining issues and risk

- Live Gemini and OpenAI calls, quotas, account model catalogs, and provider error behavior still need a controlled integration check after credentials/quota are repaired.
- The app has no authentication or per-user isolation. It is now loopback-only by default; do not expose it to a network or deploy publicly without adding access control and isolation.
- Real audio device/browser speech, macOS app launching, Calculator Accessibility permission, and real scanned-PDF quality were not end-to-end tested.
- No Ruff, mypy, coverage, or dependency vulnerability scan was run.
- `.DS_Store` is already tracked by Git; adding it to `.gitignore` does not untrack the existing index entry. Remove it from the index in a follow-up while retaining any local file if desired.
- SQLite permission hardening applies on POSIX; Windows uses different file security controls.
- AI outputs and PDF summaries can still be incorrect and should be verified against source documents.

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Add a valid GEMINI_API_KEY to .env; OPENAI_API_KEY is optional for OpenAI chat.
python -m unittest discover -s tests -v
python -m compileall -q app.py assistant.py desktop_actions.py openai_engine.py storage.py tests
python -m streamlit run app.py
```

The app stores chat and document data in `assistant.db` and sends relevant context to the selected model provider. Do not commit `.env`, databases, documents, or virtual environments.

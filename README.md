# Orvix — Your Personal AI Assistant

Orvix is a local Python and Streamlit assistant for chat, PDF questions, voice messages, and basic macOS commands. It uses Gemini and can optionally use OpenAI for chat answers. It is a personal-use prototype; it does not train an AI model.

## Features

### Chat

- Choose Gemini or OpenAI and select an available chat model.
- Choose General, Tutor, Coding, or Career Mentor mode.
- Request Bengali, English, or a reply in the language you use.
- Create, switch between, rename, and delete chats. Chat history is stored locally in SQLite.
- Edit a user message and choose **Send again** to regenerate its answer. Editing an earlier message removes later turns from that chat.
- Save personal notes, which are included as context in answer requests.
- Download a chat as a text file.

Model availability depends on your API account. A model shown in the list may not support every feature or endpoint.

### PDF questions

- Attach multiple PDF files in the chat composer and ask follow-up questions in that chat.
- Selectable text is extracted locally with `pypdf`; relevant page excerpts are sent to the selected answer provider.
- Ask for a structured research-paper review covering the research question, method, findings, contributions, and limitations. Request exam practice, including MCQs or short questions with answers and page references.
- Scanned PDFs are sent to the selected provider for visual processing. There is no separate OCR pipeline.
- Limits: **10 MB per PDF**, **150 pages per PDF**, and at most **three recently attached scanned PDFs per answer**.

Check important answers against the original document. PDF responses may be incomplete, especially for difficult scans.

### Voice

- Record a voice message in the chat composer. Gemini transcribes it and combines it with any typed text.
- Agent responses use Gemini text-to-speech when available; if its quota is exhausted, a browser voice button is offered instead.
- Use **Read last answer aloud** to replay an answer. Browser voice availability and Bengali pronunciation depend on the browser and operating system.

Voice interaction is turn-based: record and submit each message. Orvix does not currently have an always-listening wake word or continuous voice conversation.

### Current information

Questions about weather and other current information use web search and include the current date in the assistant context. Gemini and OpenAI API quotas or temporary provider limits can prevent a search or answer from completing.

### Agent mode

On macOS, enable **Agent mode** in the sidebar. Orvix greets you and responds conversationally. Submitted text or transcribed voice can trigger a supported local command.

- Open an installed app by name, for example `open Calculator`, `open Notes`, or `Chrome খোলো`.
- Open a file using its full path, or ask Orvix to find its filename in **Downloads**, **Desktop**, or **Documents**. For example: `open ~/Downloads/report.pdf` or `ফাইল report.pdf খোলো`.
- If multiple files have the same name, provide the full path.
- Open a Google search, for example `google search Python tutorial` or `গুগলে AIUB সার্চ করো`.
- Perform simple arithmetic and, when asked to open Calculator, send the expression to Calculator.
- Search summaries use Gemini and may be unavailable when the API quota is exhausted.

macOS resolves app names and reports when an app cannot be opened. File lookup is limited to the named path and the common folders above. Calculator input may require macOS Accessibility permission. Agent mode does not provide unrestricted computer control or edit project files. Turn it off to return to ordinary chat and PDF questions.

## Requirements

- Python 3.11 is recommended.
- A Gemini API key is required, including when OpenAI is selected for chat. Voice, speech, and macOS search summaries use Gemini.
- OpenAI chat is optional and requires both the `openai` package and an OpenAI API key. ChatGPT subscriptions do not include OpenAI API credits.
- macOS is required for local app and file commands. Chat, PDF, and voice features can run on Mac/Linux/Windows.

## Installation

Clone the repository and create an environment:

```bash
git clone https://github.com/AfnanBinIslamNahin/Orvix-Your-Personal-AI-Assistant.git
cd Orvix-Your-Personal-AI-Assistant
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows, create the environment with `py -3.11 -m venv .venv`, activate it with `.venv\Scripts\Activate.ps1`, and copy `.env.example` to `.env`.

Add your Gemini key to `.env`:

```text
GEMINI_API_KEY=your_gemini_api_key
```

To use OpenAI for chat, also add:

```text
OPENAI_API_KEY=your_openai_api_key
```

Available models can change. Set `GEMINI_MODEL` or `GEMINI_TTS_MODEL` in `.env` if you need to override the defaults. Use model IDs available to your API account.

Start Orvix:

```bash
streamlit run app.py
```

Open the local URL printed in the terminal.

## Run tests

```bash
python -m unittest discover -s tests -v
```

The tests cover storage, PDF handling, search configuration, voice handling, and the Streamlit chat and command flows. Provider API requests and real macOS app launches are not performed by the tests.

## Data and limitations

- Chats, messages, notes, and uploaded document data are stored in `assistant.db` beside the app.
- Relevant notes, recent chat history, and PDF content are sent to the selected API provider when generating an answer. Gemini also processes voice transcription, speech generation, and desktop search summaries.
- API usage may incur charges and is subject to provider quotas and data-handling policies.
- The app is designed for one local user and does not include authentication or per-user isolation. Do not deploy it publicly without adding access controls.
- Coding mode gives coding guidance in chat; it does not edit or run local project files.
- Voice is turn-based, responses are not streamed, and desktop commands cover a limited set of actions.
- Keep API keys, databases, personal documents, and virtual environments out of public repositories.

## Project structure

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, chat flow, provider selection, uploads, and voice input |
| `assistant.py` | Gemini answers, transcription, text-to-speech, and PDF processing |
| `openai_engine.py` | Optional OpenAI answer provider and model listing |
| `storage.py` | SQLite chats, messages, notes, documents, and message editing |
| `desktop_actions.py` | macOS app/file commands, Google search, and audio formatting |
| `requirements.txt` | Python dependencies |
| `.streamlit/config.toml` | Streamlit theme settings |
| `logo.png` | Optional app logo |

## Author

**Afnan Bin Islam Nahin**

- GitHub: [AfnanBinIslamNahin](https://github.com/AfnanBinIslamNahin)
- Portfolio: [afnanbinislam.vercel.app](https://afnanbinislam.vercel.app)

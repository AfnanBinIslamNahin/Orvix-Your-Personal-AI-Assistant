# Orvix — Your Personal AI Assistant

Orvix is a Python-based personal AI assistant built with Streamlit.
It integrates Gemini and OpenAI models for conversational assistance,
document-based question answering, voice interaction, and basic macOS commands.

The project focuses on bringing text, PDF attachments, and recorded voice
messages into one chat interface.

> **Status:** Working personal-use prototype under active development.

## Current Features

### Multi-Provider AI Chat
- Choose between Gemini and OpenAI for chat responses.
- Select an answer model from a dropdown.
- Retrieve model IDs from the providers, with fallback options when retrieval fails.
- Use assistant modes: General, Tutor, Coding, and Career Mentor.
- Choose Bengali, English, or responses matching the user's language.

Model availability depends on the API account and selected endpoint.
A listed model is not guaranteed to support every feature.

### Chat History and Personal Notes
- Create, switch between, and delete separate chats.
- Store chat history locally using SQLite.
- Include recent conversation history as context for follow-up questions.
- Save and delete personal notes that can inform responses across chats.
- Download a conversation as a text file.

### PDF Question Answering
- Attach multiple PDFs directly in the chat composer.
- Ask questions about uploaded documents and continue with follow-up questions.
- Extract selectable text locally using `pypdf`.
- Select relevant PDF excerpts through keyword-based page matching.
- Send scanned PDFs to the selected provider for visual document processing.

Current processing limits:
- Maximum upload size: **10 MB per file**.
- Text extraction covers up to **150 pages per PDF**.
- Up to **three recently attached scanned PDFs** are included in one answer.

Scanned-document support depends on the selected model's capabilities.
The application does not currently include a dedicated OCR pipeline.

### Voice Interaction
- Record voice messages from the chat composer.
- Use Gemini to transcribe recorded speech.
- Combine typed text and transcribed speech in one message.
- Generate spoken responses using Gemini text-to-speech.
- Read the latest assistant answer aloud.

Voice interaction is turn-based: users record and submit a message.
It does not currently provide an always-listening wake-word assistant.

### Basic macOS Commands
- Launch supported applications through text or transcribed voice commands.
- Open Google searches in the browser.
- Generate search-grounded summaries when available.
- Read command responses aloud.

Example commands:
- `open Calculator`
- `Chrome খোলো`
- `open Safari`
- `google search Python tutorial`
- `গুগলে AIUB সার্চ করো`

Command recognition depends on transcription accuracy and the supported
command patterns. Bengali and romanized Bengali phrasing may need adjustment.

Desktop commands run on the Mac hosting the Python application.
They do not provide unrestricted control over every laptop task.

### Unified Interface
- Text input, PDF attachments, and microphone controls in one chat composer.
- Sidebar controls for chats, models, language, assistant modes, and notes.
- Custom Orvix branding and support for a local logo image.

## Technology Stack

| Area | Technology |
|------|------------|
| Programming language | Python |
| User interface | Streamlit |
| Gemini integration | Google Gen AI SDK |
| OpenAI integration | OpenAI Python SDK |
| Local storage | SQLite |
| PDF text extraction | pypdf |
| Environment configuration | python-dotenv |
| Code organization | Object-oriented Python classes |
| Desktop commands | macOS application launching and browser opening |

Gemini and OpenAI provide the pretrained large language models.
This project integrates those models through APIs; it does not train an LLM.

## Project Structure

| File | Responsibility |
|------|----------------|
| `app.py` | Streamlit interface, model selection, chat handling, and uploads |
| `assistant.py` | Gemini responses, transcription, speech generation, and PDF processing |
| `openai_engine.py` | OpenAI responses and model listing |
| `storage.py` | SQLite storage for chats, messages, notes, and documents |
| `desktop_actions.py` | macOS commands, Google search handling, and audio formatting |
| `requirements.txt` | Python dependencies |
| `logo.png` | Optional custom application logo |
| `README.md` | Project documentation |

`assistant.db` is created locally when the application runs.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AfnanBinIslamNahin/Orvix-Your-Personal-AI-Assistant.git
cd Orvix-Your-Personal-AI-Assistant
```

### 2. Create a Virtual Environment

Python 3.11 is a suitable starting point for this project.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure API Keys

Create a `.env` file in the project directory:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_available_gemini_chat_model
GEMINI_TTS_MODEL=your_available_gemini_tts_model

# Optional: enables OpenAI chat
OPENAI_API_KEY=your_openai_api_key
```

Replace the model placeholders with model IDs available to your API account.

A Gemini key is required by the current application even when OpenAI
is selected for answers, because transcription, speech, and desktop
search summaries use Gemini.

### 5. Add the Logo

Place your custom logo beside `app.py` and name it:

```text
logo.png
```

### 6. Start the Application

```bash
streamlit run app.py
```

Open the local URL shown in the terminal.

## How to Use

1. Select an AI provider and answer model.
2. Choose an assistant mode and response language.
3. Type a message, attach PDFs, or record a voice message.
4. Ask follow-up questions within the same chat.
5. Save personal notes from the sidebar when needed.
6. Enable **Mac command mode** on macOS to use supported desktop commands.
7. Disable command mode to return to normal chat and PDF questions.

The selected answer model controls conversational responses.
Voice transcription and read-aloud functionality continue to use Gemini.

## How Document Retrieval Works

For PDFs containing selectable text, Orvix:
1. Extracts text page by page.
2. Matches question keywords against document pages.
3. Supplies selected excerpts as context to the answer model.

This is keyword-based retrieval. The current implementation does not use
embeddings, a vector database, or a vector-search RAG pipeline.

Scanned PDFs follow a separate path: their PDF content is sent to a
compatible model for visual processing.

## Current Limitations

- Designed for a single local user; authentication is not implemented.
- Full conversations are saved, but only recent messages are supplied as model context.
- Answers appear after generation completes; response streaming is not implemented.
- Voice interaction requires recording and submitting each message.
- PDF answers can be incomplete or incorrect, particularly for difficult scans.
- Desktop automation currently covers supported commands rather than arbitrary tasks.
- API quotas, billing, model access, and temporary provider outages can affect features.
- LangChain, LangGraph, vector search, and general multi-step agent workflows are not implemented.

## Planned Improvements

The following are future development goals, not completed features:

- Streaming responses.
- Embedding-based document retrieval and vector search.
- More flexible Bengali and romanized Bengali command recognition.
- Broader natural-language desktop commands.
- Structured tool calling and multi-step workflows.
- Optional LangChain or LangGraph integration.
- Wake-word support such as “Hey Orvix”.
- Improved error handling and validation.

## API Usage and Local Data

Chat history, personal notes, and document content are stored locally
in SQLite. Relevant content is sent to the selected API provider when
generating an answer.

Gemini also processes voice recordings, speech generation requests,
and desktop search summaries.

Usage costs and free-tier availability depend on the provider,
model, and API account. ChatGPT subscriptions are separate from
OpenAI API billing.

Do not commit API keys, local databases, personal documents,
or virtual environments to the repository.

Recommended `.gitignore` entries:

```gitignore
.env
.env.*
!.env.example
.venv/
venv/
__pycache__/
*.py[cod]
assistant.db
assistant.db-*
.DS_Store
```

## Author

**Afnan Bin Islam Nahin**

- GitHub: [AfnanBinIslamNahin](https://github.com/AfnanBinIslamNahin)
- Portfolio: [afnanbinislam.vercel.app](https://afnanbinislam.vercel.app)

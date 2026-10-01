# My Personal AI Assistant

Python + Streamlit + Gemini personal assistant based on the JARVIS idea, with separate chats, PDF questions, recorded voice questions, read-aloud answers, Bengali responses, and personal notes. LangChain is not required.

## Run on Mac/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Gemini API key from Google AI Studio, then:

```bash
streamlit run app.py
```

On Windows activate with `.venv\\Scripts\\activate` and copy `.env.example` to `.env`.

## How it works

- Select one of four modes and an answer language. Use the chat composer to type, attach PDF files, or record a voice message. The PDF upload area is inside the composer.
- Attach one or more PDFs in the chat composer, optionally with a question. PDFs remain associated with that chat so you can ask follow-up questions. Files are limited to 10 MB each and 150 pages. Scanned PDFs use more model input and may take longer.  For selectable-text PDFs, text is extracted locally and relevant pages are sent as context. Scanned image PDFs are sent directly to Gemini for visual reading, including on follow-up questions. At most three recently attached scanned PDFs are included per request. Verify important answers against the original document.
- Save personal notes to use across chats. Chats, notes and extracted PDF text remain in `assistant.db` on the machine hosting the app. Requests include notes, recent messages and relevant PDF excerpts sent to Gemini.
- Click *Read last answer aloud* to generate speech; text is capped at 2,500 characters. Voice interaction is turn-based, not real-time.
- One local user only. Do not deploy publicly without adding authentication, per-user storage, file isolation and access controls.

Your API key and database are excluded from Git. The Gemini API, transcription and speech generation may incur usage charges depending on your account. Model IDs can be changed in `.env` when availability changes.

## Choose a provider and model

The sidebar lists likely chat-capable models returned by Gemini and OpenAI for your API keys; the list refreshes hourly. Some available IDs are specialized or only work on other endpoints, so a listed ID may still return an error for chat or PDF. Choose another model if that happens. Gemini uses `GEMINI_API_KEY`; OpenAI additionally requires `OPENAI_API_KEY` from the OpenAI API platform. ChatGPT subscriptions do not include OpenAI API credits. Add to `.env`:

```text
OPENAI_API_KEY=your_real_openai_api_key
```

Install updated dependencies with `python -m pip install -r requirements.txt` and restart Streamlit. The chosen provider handles chat answers and scanned PDFs. Recorded voice and read-aloud audio continue to use Gemini and require the Gemini key. Each request sends personal notes, recent chat history and relevant PDF content to the selected answer provider. The app stores no OpenAI response on the provider via the `store=False` option, but provider data handling policies still apply. Do not share either API key.

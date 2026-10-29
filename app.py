import json
import base64
import os
import platform
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from assistant import (
    Assistant,
    ROLES,
    extract_pdf,
    pdf_has_scanned_pages,
    relevant_pages,
    stored_pdf_has_scanned_pages,
)
from storage import Storage
from openai_engine import (
    DEFAULT_OPENAI_MODEL,
    OpenAIAssistant,
    is_openai_available,
    openai_chat_models,
)
from desktop_actions import execute_agent_request, parse_agent_request, speech_wav


load_dotenv()

logo = Path(__file__).resolve().parent / "logo.png"

st.set_page_config(
    page_title="Orvix — Your Personal AI Assistant",
    page_icon=str(logo) if logo.is_file() else "🤖",
    layout="wide",
)

st.markdown(
    """
    <style>
      :root {
        --orvix-bg: #0b0f17;
        --orvix-panel: #111825;
        --orvix-border: rgba(172, 188, 214, .12);
        --orvix-text: #edf2fb;
        --orvix-muted: #9aa8bd;
        --orvix-accent: #8b9cff;
      }
      .stApp {
        color: var(--orvix-text);
        background:
          radial-gradient(ellipse at 50% -15%, rgba(85, 105, 190, .16), transparent 48%),
          var(--orvix-bg);
      }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stSidebar"] {
        background: rgba(14, 20, 31, .96);
        border-right: 1px solid var(--orvix-border);
      }
      [data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }
      [data-testid="stMainBlockContainer"] {
        max-width: 1080px;
        padding-top: 2.4rem;
        padding-bottom: 5rem;
      }
      h1, h2, h3 { letter-spacing: -.035em; }
      h1 { font-size: clamp(1.8rem, 3vw, 2.45rem) !important; }
      [data-testid="stChatMessage"] {
        background: rgba(20, 28, 42, .72);
        border: 1px solid var(--orvix-border);
        border-radius: 18px;
        padding: 1rem 1.15rem;
        margin: .7rem 0;
      }
      [data-testid="stChatMessage"] p { line-height: 1.7; }
      [data-testid="stChatInput"] {
        border: 1px solid rgba(172, 188, 214, .2);
        border-radius: 18px;
        background: rgba(17, 24, 37, .96);
        box-shadow: 0 12px 40px rgba(0, 0, 0, .22);
      }
      [data-testid="stChatInput"]:focus-within {
        border-color: rgba(139, 156, 255, .75);
        box-shadow: 0 0 0 3px rgba(139, 156, 255, .12);
      }
      .stButton > button, [data-testid="stPopover"] > button {
        border-radius: 10px;
        border-color: var(--orvix-border);
        transition: border-color .15s ease, background .15s ease, transform .15s ease;
      }
      .stButton > button:hover, [data-testid="stPopover"] > button:hover {
        border-color: rgba(139, 156, 255, .55);
        background: rgba(139, 156, 255, .09);
      }
      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
        gap: .2rem;
      }
      hr { border-color: var(--orvix-border); }
      [data-testid="stCaptionContainer"] { color: var(--orvix-muted); }
    </style>
    """,
    unsafe_allow_html=True,
)

if logo.is_file():
    logo_col, title_col = st.columns(
        [1, 12],
        vertical_alignment="center",
    )
    with logo_col:
        st.image(str(logo), width=74)
    with title_col:
        st.title("Orvix — Your Personal AI Assistant")
        st.caption("Your personal assistant · ready when you are")
else:
    st.title("🤖 Orvix — Your Personal AI Assistant")
    st.caption("Your personal assistant · ready when you are")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error(
        "Set GEMINI_API_KEY in your .env file, then restart the app."
    )
    st.stop()

store = Storage()

# Voice and desktop search use the default Gemini model from .env.
assistant = Assistant(api_key)


def save_chat_rename(chat_id):
    key = f"chat_rename_input_{chat_id}"
    title = st.session_state.get(key, "").strip()
    if title:
        store.rename_chat(chat_id, title[:52])
    st.session_state.pop("rename_chat_id", None)


def agent_mode_changed():
    if st.session_state.get("agent_mode"):
        st.session_state.agent_greeting_pending = True


def generate_answer(question, chat_id, history, role, language, provider,
                    selected_model, api_key, openai_key):
    if provider == "Gemini":
        engine = Assistant(api_key, model=selected_model)
    else:
        engine = OpenAIAssistant(openai_key, selected_model)

    documents = store.documents(chat_id)
    context = relevant_pages(question, documents)
    scanned = [
        doc for doc in documents
        if stored_pdf_has_scanned_pages(doc["body"])
    ]
    if len(scanned) > 3:
        st.warning("Using the three most recently attached scanned PDFs in this answer.")

    return engine.answer(
        question,
        role,
        language,
        history,
        store.notes(),
        context,
        scanned[:3],
    )


def queue_agent_speech(chat_id, text):
    if st.session_state.get("gemini_tts_quota_exhausted"):
        st.session_state.agent_browser_speech = (chat_id, text)
        return
    try:
        with st.spinner("অডিও তৈরি হচ্ছে..."):
            st.session_state.command_audio = (chat_id, speech_wav(assistant, text))
    except Exception as exc:
        quota_exhausted = "RESOURCE_EXHAUSTED" in str(exc) or getattr(exc, "code", None) == 429
        if quota_exhausted:
            st.session_state.gemini_tts_quota_exhausted = True
            st.session_state.command_notice = (
                "Gemini-এর দৈনিক voice quota শেষ। নিচের Browser voice বোতামে চাপ দিয়ে শুনুন।"
            )
        else:
            st.session_state.command_notice = (
                "Gemini voice তৈরি হয়নি। নিচের Browser voice বোতামে চাপ দিয়ে শুনুন।"
            )
        st.session_state.agent_browser_speech = (chat_id, text)


def show_browser_speech(text):
    payload = json.dumps(text, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    components.html(
        f"""
        <button onclick="speakOrvix()" style="padding:8px 14px;border-radius:10px;border:1px solid #8995ad;cursor:pointer">
          🔊 Play with browser voice
        </button>
        <script>
          const orvixText = {payload};
          function speakOrvix() {{
            const utterance = new SpeechSynthesisUtterance(orvixText);
            utterance.lang = /[\\u0980-\\u09FF]/.test(orvixText) ? 'bn-BD' : 'en-US';
            const voices = window.speechSynthesis.getVoices();
            const language = utterance.lang.split('-')[0];
            utterance.voice = voices.find(v => v.lang.toLowerCase().startsWith(language)) || null;
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utterance);
          }}
        </script>
        """,
        height=52,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def list_gemini_models(key):
    from google import genai

    names = []

    with genai.Client(api_key=key) as client:
        for model in client.models.list():
            name = (model.name or "").split("/")[-1]

            if name.startswith("gemini-") and not any(
                token in name
                for token in (
                    "-tts",
                    "-live",
                    "-image",
                    "-embedding",
                    "-realtime",
                    "-transcribe",
                    "-audio",
                    "-computer-use",
                )
            ):
                names.append(name)

    return sorted(set(names))


GEMINI_CHAT_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
)


@st.cache_data(ttl=3600, show_spinner=False)
def list_openai_models(key):
    return openai_chat_models(key)


if "chat_id" not in st.session_state:
    chats = store.chats()
    st.session_state.chat_id = (
        chats[0]["id"] if chats else store.create_chat()
    )

with st.sidebar:
    agent_mode = st.toggle(
        "Agent mode",
        value=False,
        key="agent_mode",
        disabled=platform.system() != "Darwin",
        on_change=agent_mode_changed,
    )
    if agent_mode:
        st.caption("কথা বলুন বা টাইপ করুন। ভয়েসে প্রতি turn-এ রেকর্ড করে Submit করতে হবে।")

    st.divider()
    st.header("Chats")

    if st.button("＋ New chat", use_container_width=True):
        st.session_state.chat_id = store.create_chat()
        st.rerun()

    chat_rows = store.chats()
    for chat in chat_rows:
        title_col, menu_col = st.columns([0.84, 0.16], gap="small")
        label = (
            "● " if chat["id"] == st.session_state.chat_id else ""
        ) + chat["title"]
        if st.session_state.get("rename_chat_id") == chat["id"]:
            rename_key = f"chat_rename_input_{chat['id']}"
            if rename_key not in st.session_state:
                st.session_state[rename_key] = chat["title"]
            title_col.text_input(
                "Rename chat",
                key=rename_key,
                max_chars=52,
                label_visibility="collapsed",
                placeholder="Type a new chat name and press Enter",
                on_change=save_chat_rename,
                args=(chat["id"],),
            )
        elif title_col.button(
            label,
            key=f"chat_select_{chat['id']}",
            use_container_width=True,
        ):
            st.session_state.chat_id = chat["id"]
            st.rerun()

        with menu_col.popover(
            "⋮",
            key=f"chat_menu_{chat['id']}",
            use_container_width=True,
        ):
            if st.button("Rename", key=f"rename_chat_{chat['id']}", use_container_width=True):
                st.session_state[f"chat_rename_input_{chat['id']}"] = chat["title"]
                st.session_state.rename_chat_id = chat["id"]
                st.rerun()
            if st.button("Delete", key=f"delete_chat_{chat['id']}", use_container_width=True):
                store.delete_chat(chat["id"])
                st.session_state.pop(f"chat_rename_input_{chat['id']}", None)
                if st.session_state.get("rename_chat_id") == chat["id"]:
                    st.session_state.pop("rename_chat_id", None)
                if st.session_state.chat_id == chat["id"]:
                    remaining_chats = store.chats()
                    st.session_state.chat_id = (
                        remaining_chats[0]["id"] if remaining_chats
                        else store.create_chat()
                    )
                st.rerun()

    st.divider()

    role = st.selectbox("Assistant mode", [name for name in ROLES if name != "Agent"])
    if agent_mode:
        role = "Agent"

    language = st.selectbox(
        "Answer language",
        ["বাংলা", "English", "Follow my language"],
    )

    st.divider()

    provider_options = ["Gemini"]

    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key and openai_key != "your_openai_key_here" and is_openai_available():
        provider_options.append("OpenAI")

    provider = st.selectbox(
        "AI provider",
        provider_options,
    )

    if provider == "Gemini":
        default_model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.1-flash-lite",
        )

        models = list(
            dict.fromkeys(
                (default_model, *GEMINI_CHAT_MODELS)
            )
        )

        try:
            models = list(
                dict.fromkeys(
                    (*models, *list_gemini_models(api_key))
                )
            )
        except Exception as exc:
            st.warning(
                "Could not refresh Gemini models from your API key: "
                f"{exc}. Showing known model IDs instead."
            )

        st.caption(
            "Gemini models have different availability and "
            "free-tier limits; some may require billing."
        )

    else:
        default_model = DEFAULT_OPENAI_MODEL

        try:
            models = list_openai_models(openai_key)
        except Exception as exc:
            models = [default_model]
            st.caption(
                f"Could not refresh OpenAI models: {exc}"
            )

    if not models:
        models = [default_model]

    selected_model = st.selectbox(
        "Answer model",
        models,
        index=(
            models.index(default_model)
            if default_model in models
            else 0
        ),
    )

    st.caption(
        "The selection controls chat answers. "
        "Voice and desktop search use the default Gemini model."
    )

    if "OpenAI" not in provider_options:
        st.caption(
            "OpenAI requires the openai package and OPENAI_API_KEY in .env."
        )

    with st.expander("📝 Personal notes"):
        with st.form("add_note", clear_on_submit=True):
            note = st.text_area(
                "A fact or preference to remember"
            )

            if st.form_submit_button("Save note") and note.strip():
                store.add_note(note.strip())
                st.rerun()

        for note in store.notes():
            st.write(note["body"])

            if st.button(
                "Delete note",
                key=f"note_{note['id']}",
            ):
                store.delete_note(note["id"])
                st.rerun()


chat_id = st.session_state.chat_id

if st.session_state.pop("agent_greeting_pending", False):
    greeting = "হ্যালো, আমি অরভিক্স। কী খবর তোমার? কী করতে পারি?"
    store.add_message(chat_id, "assistant", greeting)
    queue_agent_speech(chat_id, greeting)
    st.rerun()

pending_resend = st.session_state.get("pending_resend")
if pending_resend and pending_resend["chat_id"] == chat_id:
    st.session_state.pop("pending_resend", None)
    current_messages = store.messages(chat_id)
    edited_message = next(
        (message for message in current_messages
         if message["id"] == pending_resend["message_id"]
         and message["role"] == "user"),
        None,
    )
    if edited_message:
        prior_messages = [
            message for message in current_messages
            if message["id"] < edited_message["id"]
        ]
        try:
            with st.spinner("Generating a new answer..."):
                reply = generate_answer(
                    edited_message["body"],
                    chat_id,
                    prior_messages,
                    role,
                    language,
                    provider,
                    selected_model,
                    api_key,
                    openai_key,
                )
            store.add_message(chat_id, "assistant", reply)
            st.rerun()
        except Exception as exc:
            error_text = str(exc)
            if "RESOURCE_EXHAUSTED" in error_text or getattr(exc, "code", None) == 429:
                st.error("Gemini API quota বা rate limit শেষ হয়েছে। সম্পাদিত message-টি সেভ আছে; quota ঠিক হলে আবার উত্তর তৈরি করো।")
            else:
                st.error(f"নতুন উত্তর তৈরি করা যায়নি: {error_text}")

messages = store.messages(chat_id)

for index, message in enumerate(messages):
    with st.chat_message(message["role"]):
        st.markdown(message["body"])

        suggestions = st.session_state.get(
            "search_suggestions", {}
        ).get((chat_id, index))

        if suggestions:
            components.html(
                suggestions,
                height=180,
                scrolling=True,
            )

        if message["role"] == "user":
            if st.session_state.get("editing_message_id") == message["id"]:
                edit_key = f"edit_message_text_{message['id']}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = message["body"].split("\n\n📎 ", 1)[0]
                edited_text = st.text_area(
                    "Edit your message",
                    key=edit_key,
                    height=110,
                )
                st.caption("Editing an earlier message removes later replies and regenerates this answer.")
                send_again, cancel_edit = st.columns(2)
                if send_again.button("Send again", key=f"resend_message_{message['id']}", use_container_width=True):
                    if edited_text.strip():
                        store.edit_user_message(
                            chat_id,
                            message["id"],
                            edited_text.strip(),
                        )
                        st.session_state.pending_resend = {
                            "chat_id": chat_id,
                            "message_id": message["id"],
                        }
                        st.session_state.pop("editing_message_id", None)
                        st.rerun()
                if cancel_edit.button("Cancel", key=f"cancel_edit_message_{message['id']}", use_container_width=True):
                    st.session_state.pop("editing_message_id", None)
                    st.session_state.pop(edit_key, None)
                    st.rerun()
            elif st.button("✏️ Edit", key=f"edit_message_{message['id']}"):
                st.session_state.editing_message_id = message["id"]
                st.rerun()

pending_audio = st.session_state.pop(
    "command_audio",
    None,
)

if pending_audio and pending_audio[0] == chat_id:
    st.audio(
        pending_audio[1],
        format="audio/wav",
        autoplay=True,
    )

browser_speech = st.session_state.pop("agent_browser_speech", None)
if browser_speech and browser_speech[0] == chat_id:
    show_browser_speech(browser_speech[1])

notice = st.session_state.pop(
    "command_notice",
    None,
)

if notice:
    st.warning(notice)

if messages:
    transcript = "\n\n".join(
        f"{message['role'].upper()}: {message['body']}"
        for message in messages
    )

    st.download_button(
        "Download this chat",
        transcript,
        file_name=f"chat_{chat_id}.txt",
        mime="text/plain",
    )

    answers = [
        message
        for message in messages
        if message["role"] == "assistant"
    ]

    if answers and st.button("🔊 Read last answer aloud"):
        queue_agent_speech(chat_id, answers[-1]["body"])
        st.rerun()


submission = st.chat_input(
    "Type a message, attach a PDF, or record your voice...",
    key=f"composer_{chat_id}",
    accept_file="multiple",
    file_type=["pdf"],
    max_upload_size=10,
    accept_audio=True,
)

if submission:
    try:
        uploaded = []

        for file in submission.files:
            raw = file.getvalue()

            if len(raw) > 10 * 1024 * 1024:
                raise ValueError(
                    f"{file.name} exceeds 10 MB."
                )

            pages = extract_pdf(raw)

            if pages:
                if pdf_has_scanned_pages(raw):
                    body = json.dumps({
                        "pages": pages,
                        "pdf_base64": base64.b64encode(raw).decode("ascii"),
                    }, ensure_ascii=False)
                else:
                    body = json.dumps(pages, ensure_ascii=False)
            else:
                body = json.dumps({
                    "pdf_base64": base64.b64encode(raw).decode("ascii")
                })

            uploaded.append((file.name, body))

        question = (submission.text or "").strip()

        if submission.audio:
            with st.spinner("Transcribing voice message..."):
                spoken = assistant.transcribe(
                    submission.audio.getvalue(),
                    mime_type=getattr(submission.audio, "type", None) or "audio/wav",
                )

            question = " ".join(
                part
                for part in (question, spoken)
                if part
            ).strip()

        if not question and uploaded:
            question = "এই PDF-এর মূল বিষয়গুলো সংক্ষেপে বুঝিয়ে দাও।"

        if not question:
            st.warning(
                "No text or spoken question was found."
            )
            st.stop()

        # Agent mode runs only commands recognized by the supported Mac action parser.
        # Other messages remain ordinary conversational requests.
        run_local_command = False
        if agent_mode and not uploaded:
            try:
                parse_agent_request(question)
                run_local_command = True
            except ValueError:
                pass

        if run_local_command:
            visible_question = question
            store.add_message(chat_id, "user", visible_question)
            try:
                with st.spinner("কমান্ডটি সম্পন্ন করছি..."):
                    reply, suggestions = execute_agent_request(question, assistant, language)
            except Exception as exc:
                reply, suggestions = f"কমান্ডটি করা যায়নি: {exc}", None
            store.add_message(chat_id, "assistant", reply)
            if suggestions:
                st.session_state.setdefault("search_suggestions", {})[(chat_id, len(messages) + 1)] = suggestions
            queue_agent_speech(chat_id, reply)
            st.rerun()

        # Normal chat and PDF mode.
        for name, body in uploaded:
            store.add_document(
                chat_id,
                name,
                body,
            )

        visible_question = question

        if uploaded:
            visible_question += "\n\n📎 " + ", ".join(
                name for name, _ in uploaded
            )

        # Persist the question before calling a provider so a temporary API
        # error cannot make the user's message disappear from the chat.
        store.add_message(chat_id, "user", visible_question)

        with st.spinner("কথা ভাবছি..." if agent_mode else "Thinking..."):
            reply = generate_answer(
                question,
                chat_id,
                messages,
                role,
                language,
                provider,
                selected_model,
                api_key,
                openai_key,
            )

        store.add_message(
            chat_id,
            "assistant",
            reply,
        )

        if agent_mode:
            queue_agent_speech(chat_id, reply)

        st.rerun()

    except Exception as exc:
        error_text = str(exc)
        if "RESOURCE_EXHAUSTED" in error_text or getattr(exc, "code", None) == 429:
            st.error("Gemini API-এর quota বা rate limit শেষ হয়েছে, তাই উত্তর তৈরি হয়নি।")
            st.info(
                "তোমার প্রশ্নটি chat-এ সেভ হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করো, "
                "অথবা AI Studio-তে usage, model-এর rate limit ও billing status দেখো।"
            )
            st.markdown(
                "[Gemini API usage ও rate limit দেখো](https://aistudio.google.com/rate-limit) · "
                "[Quota documentation](https://ai.google.dev/gemini-api/docs/rate-limits)"
            )
            with st.expander("Technical details"):
                st.code(error_text)
        else:
            st.error(f"Could not process your message: {error_text}")

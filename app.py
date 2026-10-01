import json
import base64
import os
import platform
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from assistant import Assistant, ROLES, extract_pdf, relevant_pages
from storage import Storage
from openai_engine import OpenAIAssistant, openai_chat_models
from desktop_actions import execute_command, speech_wav


load_dotenv()

logo = Path(__file__).resolve().parent / "logo.png"

st.set_page_config(
    page_title="Orvix — Your Personal AI Assistant",
    page_icon=str(logo) if logo.is_file() else "🤖",
    layout="wide",
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
else:
    st.title("🤖 Orvix — Your Personal AI Assistant")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error(
        "Set GEMINI_API_KEY in your .env file, then restart the app."
    )
    st.stop()

store = Storage()

# Voice and desktop search use the default Gemini model from .env.
assistant = Assistant(api_key)


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
    desktop_mode = st.toggle(
        "Mac command mode",
        value=False,
        disabled=platform.system() != "Darwin",
    )

    summarize_search = st.checkbox(
        "সার্চের সারাংশ দেখাও",
        value=True,
    )

    read_command = st.checkbox(
        "কমান্ডের উত্তর পড়ে শোনাও",
        value=True,
    )

    st.caption(
        "Mac mode: Chrome খোলো / গুগলে AIUB সার্চ করো। "
        "Search ও voice-এর জন্য Gemini ব্যবহার হয়।"
    )

    st.divider()
    st.header("Chats")

    if st.button("＋ New chat", use_container_width=True):
        st.session_state.chat_id = store.create_chat()
        st.rerun()

    for chat in store.chats():
        label = (
            "● " if chat["id"] == st.session_state.chat_id else ""
        ) + chat["title"]

        if st.button(
            label,
            key=f"chat_{chat['id']}",
            use_container_width=True,
        ):
            st.session_state.chat_id = chat["id"]
            st.rerun()

    if st.button(
        "Delete current chat",
        use_container_width=True,
    ):
        store.delete_chat(st.session_state.chat_id)
        chats = store.chats()
        st.session_state.chat_id = (
            chats[0]["id"] if chats else store.create_chat()
        )
        st.rerun()

    st.divider()

    role = st.selectbox("Assistant mode", list(ROLES))

    language = st.selectbox(
        "Answer language",
        ["বাংলা", "English", "Follow my language"],
    )

    st.divider()

    provider_options = ["Gemini"]

    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key and openai_key != "your_openai_key_here":
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
        default_model = "gpt-6-luna"

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
            "To enable OpenAI, set OPENAI_API_KEY in .env "
            "and install updated requirements."
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

    if answers and st.button(
        "🔊 Read last answer aloud (Gemini TTS)"
    ):
        try:
            with st.spinner("Generating audio..."):
                st.audio(
                    speech_wav(assistant, answers[-1]["body"]),
                    format="audio/wav",
                )
        except Exception as exc:
            st.error(
                f"Audio could not be generated: {exc}"
            )


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
        if desktop_mode and submission.files:
            raise ValueError(
                "PDF নিয়ে প্রশ্ন করতে Mac command mode বন্ধ করুন।"
            )

        uploaded = []

        for file in submission.files:
            raw = file.getvalue()

            if len(raw) > 10 * 1024 * 1024:
                raise ValueError(
                    f"{file.name} exceeds 10 MB."
                )

            pages = extract_pdf(raw)

            if pages:
                body = json.dumps(
                    pages,
                    ensure_ascii=False,
                )
            else:
                body = json.dumps({
                    "pdf_base64": base64.b64encode(raw).decode("ascii")
                })

            uploaded.append((file.name, body))

        question = (submission.text or "").strip()

        if submission.audio:
            with st.spinner("Transcribing voice message..."):
                spoken = assistant.transcribe(
                    submission.audio.getvalue()
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

        # Desktop mode: execute a single supported Mac command.
        if desktop_mode:
            with st.spinner("Running Mac command..."):
                reply, suggestions = execute_command(
                    question,
                    assistant,
                    language,
                    summarize_search,
                )

            store.add_message(
                chat_id,
                "user",
                question,
            )
            store.add_message(
                chat_id,
                "assistant",
                reply,
            )

            if suggestions:
                st.session_state.setdefault(
                    "search_suggestions", {}
                )[(chat_id, len(messages) + 1)] = suggestions

            if read_command:
                try:
                    with st.spinner("Generating spoken reply..."):
                        st.session_state.command_audio = (
                            chat_id,
                            speech_wav(assistant, reply),
                        )
                except Exception as exc:
                    st.session_state.command_notice = (
                        "কমান্ডের ফল সেভ হয়েছে, কিন্তু অডিও হয়নি: "
                        f"{exc}"
                    )

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

        with st.spinner("Thinking..."):
            if provider == "Gemini":
                engine = Assistant(
                    api_key,
                    model=selected_model,
                )
            else:
                engine = OpenAIAssistant(
                    openai_key,
                    selected_model,
                )

            documents = store.documents(chat_id)
            context = relevant_pages(
                question,
                documents,
            )

            scanned = [
                doc
                for doc in documents
                if doc["body"].startswith('{"pdf_base64"')
            ]

            if len(scanned) > 3:
                st.warning(
                    "Using the three most recently attached "
                    "scanned PDFs in this answer."
                )

            reply = engine.answer(
                question,
                role,
                language,
                messages,
                store.notes(),
                context,
                scanned[:3],
            )

        store.add_message(
            chat_id,
            "user",
            visible_question,
        )
        store.add_message(
            chat_id,
            "assistant",
            reply,
        )

        st.rerun()

    except Exception as exc:
        st.error(
            f"Could not process your message: {exc}"
        )
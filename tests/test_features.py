import json
import base64
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pypdf import PdfWriter

import desktop_actions
from assistant import Assistant, ROLES, extract_pdf, needs_live_search, relevant_pages
from openai_engine import OpenAIAssistant, openai_chat_models
from storage import Storage


class DesktopCommandTests(unittest.TestCase):
    def test_parse_english_and_bengali_commands(self):
        self.assertEqual(desktop_actions.parse_command("Chrome খোলো"), ("app", "Google Chrome"))
        self.assertEqual(desktop_actions.parse_command("open Safari"), ("app", "Safari"))
        self.assertEqual(desktop_actions.parse_command("গুগলে AIUB সার্চ করো"), ("search", "AIUB"))
        self.assertEqual(desktop_actions.parse_command("ফাইল report.pdf খোলো"), ("file", "report.pdf"))
        self.assertEqual(desktop_actions.parse_command("open ~/Downloads/MyPhoto.png"), ("file", "~/Downloads/MyPhoto.png"))
        self.assertEqual(desktop_actions.parse_command("open Visual Studio Code"), ("app", "Visual Studio Code"))

    def test_unknown_app_name_is_passed_to_macos_for_resolution(self):
        self.assertEqual(desktop_actions.parse_command("launch My Editor"), ("app", "My Editor"))

    def test_app_command_uses_macos_open(self):
        with patch.object(desktop_actions, "run_mac_open") as open_mac:
            reply, suggestions = desktop_actions.execute_command("open Safari", None, "English", summarize=False)
        open_mac.assert_called_once_with(["-a", "Safari"])
        self.assertIn("Safari", reply)
        self.assertIsNone(suggestions)

    def test_file_command_opens_explicit_existing_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.png"
            path.write_bytes(b"image")
            with patch.object(desktop_actions, "run_mac_open") as open_mac:
                reply, _ = desktop_actions.execute_command(f"open {path}", None, "বাংলা")
            open_mac.assert_called_once_with([str(path.resolve())])
            self.assertIn("sample.png", reply)

    def test_file_search_is_scoped_and_reports_ambiguous_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            one = root / "first"
            two = root / "second"
            one.mkdir()
            two.mkdir()
            (one / "photo.jpg").write_bytes(b"1")
            self.assertEqual(desktop_actions.resolve_local_file("photo.jpg", [root]), (one / "photo.jpg").resolve())
            (two / "photo.jpg").write_bytes(b"2")
            with self.assertRaisesRegex(ValueError, "একই নামে একাধিক"):
                desktop_actions.resolve_local_file("photo.jpg", [root])

    def test_search_command_opens_google_without_a_provider_request_when_summary_disabled(self):
        with patch.object(desktop_actions, "run_mac_open") as open_mac:
            reply, suggestions = desktop_actions.execute_command(
                "গুগলে AIUB সার্চ করো", None, "বাংলা", summarize=False
            )
        opened_url = open_mac.call_args.args[0][0]
        self.assertIn("google.com/search", opened_url)
        self.assertIn("AIUB", opened_url)
        self.assertIn("Google search", reply)
        self.assertIsNone(suggestions)

    def test_search_summary_uses_grounding_and_returns_sources(self):
        metadata = SimpleNamespace(
            grounding_chunks=[SimpleNamespace(web=SimpleNamespace(
                uri="https://example.test/source", title="Example source"
            ))],
            search_entry_point=SimpleNamespace(rendered_content="suggested searches"),
        )
        candidate = SimpleNamespace(grounding_metadata=metadata)
        result = SimpleNamespace(text="Search summary", candidates=[candidate])
        models = SimpleNamespace(generate_content=lambda **kwargs: result)
        assistant = SimpleNamespace(client=SimpleNamespace(models=models), model="test-model")

        with patch.object(desktop_actions, "run_mac_open"):
            reply, suggestions = desktop_actions.execute_command(
                "search AIUB", assistant, "বাংলা", summarize=True
            )

        self.assertIn("Search summary", reply)
        self.assertIn("https://example.test/source", reply)
        self.assertEqual(suggestions, "suggested searches")

    def test_run_mac_open_reports_missing_app(self):
        result = SimpleNamespace(returncode=1, stderr="Application not found")
        with patch.object(desktop_actions.platform, "system", return_value="Darwin"):
            with patch.object(desktop_actions.subprocess, "run", return_value=result) as run:
                with self.assertRaisesRegex(RuntimeError, "Application not found"):
                    desktop_actions.run_mac_open(["-a", "Missing App"])
        self.assertEqual(run.call_args.args[0], ["/usr/bin/open", "-a", "Missing App"])

    def test_sidebar_has_one_mac_mode_control_without_instruction_caption(self):
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
        sidebar_start = app_source.index("with st.sidebar:")
        sidebar_end = app_source.index('st.divider()', sidebar_start)
        mac_controls = app_source[sidebar_start:sidebar_end]
        self.assertIn('st.toggle(\n        "Mac command mode"', mac_controls)
        self.assertNotIn("st.checkbox", mac_controls)
        self.assertNotIn("Mac mode: Chrome খোলো", app_source)
        self.assertNotIn("সার্চের সারাংশ দেখাও", app_source)


class StorageTests(unittest.TestCase):
    def test_edit_message_removes_following_turns_and_updates_default_title(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(Path(folder) / "test.db")
            chat_id = store.create_chat()
            store.add_message(chat_id, "user", "first question")
            store.add_message(chat_id, "assistant", "first answer")
            store.add_message(chat_id, "user", "follow-up")
            store.add_message(chat_id, "assistant", "follow-up answer")
            first_id = store.messages(chat_id)[0]["id"]

            self.assertTrue(store.edit_user_message(chat_id, first_id, "edited question"))

            messages = store.messages(chat_id)
            self.assertEqual([(m["role"], m["body"]) for m in messages], [("user", "edited question")])
            self.assertEqual(store.chats()[0]["title"], "edited question")

    def test_edit_does_not_replace_a_custom_chat_title(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(Path(folder) / "test.db")
            chat_id = store.create_chat()
            store.add_message(chat_id, "user", "first question")
            store.rename_chat(chat_id, "My saved title")
            message_id = store.messages(chat_id)[0]["id"]
            store.edit_user_message(chat_id, message_id, "edited question")
            self.assertEqual(store.chats()[0]["title"], "My saved title")

    def test_personal_notes_and_documents_are_saved_and_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(Path(folder) / "test.db")
            chat_id = store.create_chat()
            store.add_note("Answer in Bengali")
            store.add_document(chat_id, "guide.pdf", "[[1, \"sample\"]]")
            self.assertEqual(store.notes()[0]["body"], "Answer in Bengali")
            self.assertEqual(store.documents(chat_id)[0]["name"], "guide.pdf")
            store.delete_note(store.notes()[0]["id"])
            store.delete_chat(chat_id)
            self.assertEqual(store.notes(), [])
            self.assertEqual(store.documents(chat_id), [])

    def test_chat_and_message_data_persist_and_delete_cascades(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(Path(folder) / "test.db")
            chat_id = store.create_chat()
            store.add_message(chat_id, "user", "hello")
            self.assertEqual(store.chats()[0]["id"], chat_id)
            self.assertEqual(store.messages(chat_id)[0]["body"], "hello")
            store.delete_chat(chat_id)
            self.assertEqual(store.chats(), [])
            self.assertEqual(store.messages(chat_id), [])


class AssistantFeatureTests(unittest.TestCase):
    def test_live_search_detection_handles_bengali_and_english(self):
        self.assertTrue(needs_live_search("আজকে বরিশালের আবহাওয়ার তথ্য দাও"))
        self.assertTrue(needs_live_search("latest weather in Barishal"))
        self.assertFalse(needs_live_search("Explain Python loops"))

    def test_pdf_relevance_uses_whole_words_and_short_bengali_terms(self):
        documents = [{
            "name": "guide.pdf",
            "body": json.dumps([
                [1, "A reactor produces energy."],
                [2, "An actor performs on stage."],
                [3, "এই বই পড়তে ভালো লাগে।"],
            ], ensure_ascii=False),
        }]
        result = relevant_pages("actor", documents)
        self.assertLess(result.index("page 2"), result.index("page 1"))
        bengali_result = relevant_pages("বই", documents)
        self.assertIn("page 3", bengali_result)

    def test_pdf_page_limit_and_blank_pdf(self):
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        single_page = BytesIO()
        writer.write(single_page)
        self.assertEqual(extract_pdf(single_page.getvalue()), [])

        oversized = PdfWriter()
        for _ in range(151):
            oversized.add_blank_page(width=72, height=72)
        pdf = BytesIO()
        oversized.write(pdf)
        with self.assertRaisesRegex(ValueError, "150 pages"):
            extract_pdf(pdf.getvalue())

    def test_gemini_answer_enables_search_for_current_questions(self):
        fake_models = SimpleNamespace(
            calls=[],
        )

        def generate_content(**kwargs):
            fake_models.calls.append(kwargs)
            return SimpleNamespace(text="Current forecast", candidates=[])

        fake_models.generate_content = generate_content
        assistant = Assistant.__new__(Assistant)
        assistant.client = SimpleNamespace(models=fake_models)
        assistant.model = "test-model"

        answer = assistant.answer("আজকের আবহাওয়া কেমন?", "General", "বাংলা", [], [])

        self.assertEqual(answer, "Current forecast")
        tools = fake_models.calls[0]["config"].tools
        self.assertTrue(tools)
        self.assertIsNotNone(tools[0].google_search)

    def test_all_assistant_modes_and_context_reach_gemini(self):
        fake_models = SimpleNamespace(calls=[])
        fake_models.generate_content = lambda **kwargs: (
            fake_models.calls.append(kwargs)
            or SimpleNamespace(text="Answer", candidates=[])
        )
        assistant = Assistant.__new__(Assistant)
        assistant.client = SimpleNamespace(models=fake_models)
        assistant.model = "test-model"

        self.assertEqual(set(ROLES), {"General", "Tutor", "Coding", "Career Mentor"})
        assistant.answer(
            "Explain this", "Coding", "বাংলা",
            [{"role": "user", "body": "Earlier question"}],
            [{"body": "Use short examples"}],
            "[guide.pdf, page 2]\nExample context",
        )
        call = fake_models.calls[0]
        self.assertIn("Mode: Coding", call["config"].system_instruction)
        self.assertIn("Respond in বাংলা", call["config"].system_instruction)
        self.assertIn("Earlier question", call["contents"][0])
        self.assertIn("Use short examples", call["contents"][0])
        self.assertIn("page 2", call["contents"][0])

    def test_scanned_pdf_bytes_are_sent_as_pdf_parts(self):
        fake_models = SimpleNamespace(calls=[])
        fake_models.generate_content = lambda **kwargs: (
            fake_models.calls.append(kwargs)
            or SimpleNamespace(text="PDF answer", candidates=[])
        )
        assistant = Assistant.__new__(Assistant)
        assistant.client = SimpleNamespace(models=fake_models)
        assistant.model = "test-model"
        pdf_data = base64.b64encode(b"%PDF test").decode("ascii")

        assistant.answer(
            "Summarize this", "General", "English", [], [],
            scanned_documents=[{"name": "scan.pdf", "body": json.dumps({"pdf_base64": pdf_data})}],
        )

        contents = fake_models.calls[0]["contents"]
        self.assertIn("Attached PDF: scan.pdf", contents[1])
        self.assertEqual(contents[2].inline_data.mime_type, "application/pdf")
        self.assertEqual(contents[2].inline_data.data, b"%PDF test")

    def test_transcription_preserves_browser_audio_mime_type(self):
        fake_models = SimpleNamespace(calls=[])

        def generate_content(**kwargs):
            fake_models.calls.append(kwargs)
            return SimpleNamespace(text=" spoken words ")

        fake_models.generate_content = generate_content
        assistant = Assistant.__new__(Assistant)
        assistant.client = SimpleNamespace(models=fake_models)
        assistant.model = "test-model"

        self.assertEqual(assistant.transcribe(b"audio", "audio/webm"), "spoken words")
        audio_part = fake_models.calls[0]["contents"][1]
        self.assertEqual(audio_part.inline_data.mime_type, "audio/webm")

    def test_tts_returns_audio_and_handles_empty_model_response(self):
        assistant = Assistant.__new__(Assistant)
        assistant.model = "test-model"

        class FakeModels:
            result = SimpleNamespace(
                candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
                    SimpleNamespace(inline_data=SimpleNamespace(data=b"RIFFaudio"))
                ]))]
            )

            def generate_content(self, **kwargs):
                return self.result

        assistant.client = SimpleNamespace(models=FakeModels())
        self.assertEqual(assistant.speak("hello"), b"RIFFaudio")
        assistant.client.models.result = SimpleNamespace(candidates=[])
        with self.assertRaisesRegex(RuntimeError, "no speech audio"):
            assistant.speak("hello")

    def test_openai_live_questions_require_web_search(self):
        fake_client = SimpleNamespace(responses=SimpleNamespace())
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            citation = SimpleNamespace(url="https://example.test/weather", title="Weather source")
            part = SimpleNamespace(annotations=[citation])
            message = SimpleNamespace(type="message", content=[part])
            return SimpleNamespace(output_text="আজকের আবহাওয়া।", output=[message])

        fake_client.responses.create = create
        assistant = OpenAIAssistant.__new__(OpenAIAssistant)
        assistant.client = fake_client
        assistant.model = "test-model"

        answer = assistant.answer("আজকের আবহাওয়া", "General", "বাংলা", [], [])

        self.assertEqual(captured["tool_choice"], "required")
        self.assertEqual(captured["tools"], [{"type": "web_search"}])
        self.assertIn("Weather source", answer)
        self.assertEqual(openai_chat_models(None), ["gpt-4o-mini", "gpt-4o", "o3-mini", "o1"])


if __name__ == "__main__":
    unittest.main()

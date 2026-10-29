import os
import tempfile
from contextlib import contextmanager
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import storage
import desktop_actions
from storage import Storage


class UiStorage(Storage):
    database_path = None

    def __init__(self, path=None, timeout=15.0):
        super().__init__(self.database_path, timeout=timeout)


class FakeModels:
    def list(self):
        return [SimpleNamespace(name="models/gemini-3.1-flash-lite")]

    def generate_content(self, **kwargs):
        audio = SimpleNamespace(data=b"RIFF" + b"0" * 40)
        parts = [SimpleNamespace(inline_data=audio)]
        return SimpleNamespace(
            text="Test regenerated answer",
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))],
        )


class FakeGenAIClient:
    def __init__(self, **kwargs):
        self.models = FakeModels()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class StreamlitUiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        UiStorage.database_path = Path(self.temp_dir.name) / "ui.db"
        self.storage = UiStorage()
        self.chat_id = self.storage.create_chat()
        self.app_path = Path(__file__).resolve().parents[1] / "app.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    @contextmanager
    def running_app(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"GEMINI_API_KEY": "ui-test-key", "OPENAI_API_KEY": ""}), \
             patch.object(storage, "Storage", UiStorage), \
             patch("google.genai.Client", FakeGenAIClient):
            app = AppTest.from_file(str(self.app_path)).run(timeout=30)
            yield app

    def test_new_chat_button_creates_and_selects_a_chat(self):
        with self.running_app() as app:
            self.assertFalse(app.exception)
            self.assertEqual([widget.label for widget in app.toggle], ["Agent mode"])
            self.assertEqual(len(app.checkbox), 0)

            next(widget for widget in app.button if widget.label.strip() == "＋  New chat").click().run(timeout=30)

            chats = UiStorage().chats()
            self.assertEqual(len(chats), 2)
            self.assertEqual(app.session_state["chat_id"], chats[0]["id"])
            self.assertFalse(app.exception)

    def test_rename_saves_when_entering_name_without_confirmation(self):
        self.storage.add_message(self.chat_id, "user", "Original question")
        with self.running_app() as app:
            app.button(key=f"rename_chat_{self.chat_id}").click().run(timeout=30)
            app.text_input(key=f"chat_rename_input_{self.chat_id}").set_value("New title").run(timeout=30)

            self.assertEqual(UiStorage().chats()[0]["title"], "New title")
            self.assertFalse(app.exception)

    def test_openai_provider_displays_model_ids_returned_by_api(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"GEMINI_API_KEY": "ui-test-key", "OPENAI_API_KEY": "configured-test-key"}), \
             patch.object(storage, "Storage", UiStorage), \
             patch("google.genai.Client", FakeGenAIClient), \
             patch("openai_engine.openai_chat_models", return_value=["gpt-4o-mini", "gpt-custom"]):
            app = AppTest.from_file(str(self.app_path)).run(timeout=30)
            provider = next(widget for widget in app.selectbox if widget.label == "AI provider")
            self.assertEqual(provider.options, ["Gemini", "OpenAI"])
            provider.select("OpenAI").run(timeout=30)
            model_select = next(widget for widget in app.selectbox if widget.label == "Answer model")
            self.assertEqual(model_select.options, ["gpt-4o-mini", "gpt-custom"])
            self.assertFalse(app.exception)

    def test_failed_answer_keeps_user_message_and_shows_error(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"GEMINI_API_KEY": "ui-test-key", "OPENAI_API_KEY": ""}), \
             patch.object(storage, "Storage", UiStorage), \
             patch("google.genai.Client", FakeGenAIClient), \
             patch("assistant.Assistant.answer", side_effect=RuntimeError("provider unavailable")):
            app = AppTest.from_file(str(self.app_path)).run(timeout=30)
            app.chat_input[0].set_value("Keep this question").run(timeout=30)
            stored = UiStorage().messages(self.chat_id)
            self.assertEqual([(m["role"], m["body"]) for m in stored], [("user", "Keep this question")])
            self.assertTrue(any("provider unavailable" in item.value for item in app.error))
            self.assertFalse(app.exception)

    def test_edit_message_and_send_again_replaces_following_answer(self):
        self.storage.add_message(self.chat_id, "user", "Original question")
        self.storage.add_message(self.chat_id, "assistant", "Old answer")
        with self.running_app() as app:
            user_message = self.storage.messages(self.chat_id)[0]
            app.button(key=f"edit_message_{user_message['id']}").click().run(timeout=30)
            app.text_area(key=f"edit_message_text_{user_message['id']}").set_value("Edited question").run(timeout=30)
            next(widget for widget in app.button if widget.label == "Send again").click().run(timeout=30)

            messages = UiStorage().messages(self.chat_id)
            self.assertEqual(
                [(message["role"], message["body"]) for message in messages],
                [("user", "Edited question"), ("assistant", "Test regenerated answer")],
            )
            self.assertFalse(app.exception)

    def test_agent_mode_greets_then_routes_app_command_to_local_opener(self):
        with self.running_app() as app:
            with patch("platform.system", return_value="Darwin"), \
                 patch.object(desktop_actions, "run_mac_open") as open_mac:
                app.toggle[0].set_value(True).run(timeout=30)
                app.chat_input[0].set_value("open Safari").run(timeout=30)

            open_mac.assert_called_once_with(["-a", "Safari"])
            messages = UiStorage().messages(self.chat_id)
            self.assertEqual(messages[0]["role"], "assistant")
            self.assertIn("হ্যালো", messages[0]["body"])
            self.assertEqual(messages[1]["body"], "open Safari")
            self.assertIn("Safari", messages[2]["body"])
            self.assertFalse(app.exception)

    def test_agent_voice_quota_uses_sanitized_browser_speech_fallback(self):
        from streamlit.testing.v1 import AppTest

        class QuotaModels(FakeModels):
            def generate_content(self, **kwargs):
                config = kwargs.get("config")
                if isinstance(config, dict) and config.get("response_modalities") == ["AUDIO"]:
                    error = RuntimeError("RESOURCE_EXHAUSTED")
                    error.code = 429
                    raise error
                return super().generate_content(**kwargs)

        class QuotaClient(FakeGenAIClient):
            def __init__(self, **kwargs):
                self.models = QuotaModels()

        with patch.dict(os.environ, {"GEMINI_API_KEY": "ui-test-key", "OPENAI_API_KEY": ""}), \
             patch.object(storage, "Storage", UiStorage), \
             patch("google.genai.Client", QuotaClient):
            app = AppTest.from_file(str(self.app_path)).run(timeout=30)
            app.toggle[0].set_value(True).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any("দৈনিক voice quota শেষ" in item.value for item in app.warning))
            self.assertTrue(any("Play with browser voice" in item.value for item in app.html))

if __name__ == "__main__":
    unittest.main()

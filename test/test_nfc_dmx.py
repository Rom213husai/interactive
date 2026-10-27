import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nfc"))
import nfc_common as common
import nfc_register as registration

spec = importlib.util.spec_from_file_location(
    "nfc_dmx", Path(__file__).resolve().parents[1] / "nfc" / "nfc_dmx.py"
)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class NFCDMXTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_fixture_addresses_and_full_scene_update(self):
        backend = Mock()
        fixtures = [Mock() for _ in range(16)]
        backend.add_fixture.side_effect = fixtures
        with patch.object(app, "SerialController", return_value=backend), patch.object(app, "DMX_START_ADDRESS", 37):
            dmx = app.DMXController("COM_TEST")
        addresses = [call.kwargs["start_channel"] for call in backend.add_fixture.call_args_list]
        self.assertEqual(addresses, list(range(37, 53)))
        first = list(range(16))
        second = [255 - value for value in first]
        dmx.set_values(first)
        dmx.set_values(second)
        for fixture, before, after in zip(fixtures, first, second):
            self.assertEqual([call.args for call in fixture.dim.call_args_list], [(before, 0), (after, 0)])
        with patch.object(app.time, "sleep"):
            dmx.close()
        backend.close.assert_called_once()
        for fixture in fixtures:
            fixture.dim.assert_called_with(0, 0)

    def test_invalid_values_do_not_partially_update_output(self):
        with patch.object(app, "SerialController"):
            dmx = app.DMXController("COM_TEST")
        dmx.fixtures = [Mock() for _ in range(16)]
        with self.assertRaises(ValueError):
            dmx.set_values([255] * 15 + [256])
        for fixture in dmx.fixtures:
            fixture.dim.assert_not_called()

    def test_scan_switches_registered_cards_and_ignores_unknown_card(self):
        first = list(range(16))
        second = [255] * 16
        cards = {"A": {"name": "first", "dmx": first}, "B": {"name": "second", "dmx": second}}
        controller = Mock()
        with patch.object(app, "DMXController", return_value=controller) as factory, patch.object(
            app, "read_uid", side_effect=["A", "A", "UNKNOWN", "B", None, "B", KeyboardInterrupt]
        ), patch.object(app.time, "sleep"):
            app.run_dmx(Mock(), cards, "COM_TEST")
        factory.assert_called_once_with("COM_TEST")
        self.assertEqual([call.args[0] for call in controller.set_values.call_args_list], [first, second, second])
        controller.close.assert_called_once()

    def test_reader_error_is_reported_and_does_not_reset_current_card(self):
        card = {"name": "card", "dmx": [255] * 16}
        controller = Mock()
        with patch.object(app, "DMXController", return_value=controller), patch.object(
            app, "read_uid", side_effect=["A", RuntimeError("reader disconnected"), "A", KeyboardInterrupt]
        ), patch.object(app.time, "sleep"):
            app.run_dmx(Mock(), {"A": card}, "COM_TEST", sound=None)
        self.assertEqual(controller.set_values.call_count, 1)
        self.assertIn("NFC読み取りエラー", self.output._new_target.getvalue())

    def test_removed_card_is_reported_as_absent(self):
        exceptions = types.ModuleType("smartcard.Exceptions")
        no_card = type("NoCardException", (Exception,), {})
        exceptions.NoCardException = no_card
        connection = Mock()
        connection.connect.side_effect = no_card("card removed")
        reader = Mock()
        reader.createConnection.return_value = connection
        with patch.dict(sys.modules, {"smartcard": types.ModuleType("smartcard"),
                                      "smartcard.Exceptions": exceptions}):
            self.assertIsNone(common.read_uid(reader))
        connection.disconnect.assert_not_called()

    def test_direct_run_loads_cards_and_uses_selected_port(self):
        cards = {"A": {"name": "card", "dmx": [0] * 16}}
        reader = Mock()
        with patch("sys.argv", ["nfc_dmx.py", "--port", "COM_TEST", "--no-sound"]), patch.object(
            app, "load_cards", return_value=cards
        ), patch.object(app, "get_reader", return_value=reader), patch.object(app, "run_dmx") as run:
            app.main()
        run.assert_called_once_with(reader, cards, "COM_TEST", sound=None)

    def test_sound_starts_before_delay_and_output_once_per_card_read(self):
        cards = {"A": {"name": "card", "dmx": [128] + [0] * 15, "animation": 1}}
        events = Mock()
        controller = events.dmx
        sound = events.sound
        layout = Mock()
        layout.frames.return_value = [(0, 0.5)]
        with patch.object(app, "DMXController", return_value=controller), patch.object(
            app, "Animator", return_value=events.animator
        ), patch.object(app, "read_uid", side_effect=["A", "A", "UNKNOWN", None, "A", KeyboardInterrupt]), patch.object(
            app.time, "sleep", side_effect=events.sleep
        ):
            app.run_dmx(Mock(), cards, layout=layout, sound=sound)
        names = [call[0] for call in events.mock_calls]
        self.assertEqual(sound.play.call_count, 2)
        self.assertTrue(all(call.kwargs == {"loops": -1} for call in sound.play.call_args_list))
        self.assertEqual(events.animator.play.call_count, 2)
        for index, name in enumerate(names):
            if name == "dmx.set_values":
                self.assertEqual(names[index - 2:index], ["sleep", "animator.stop"])
                self.assertEqual(events.mock_calls[index - 2].args, (3.0,))
                self.assertEqual(names[index - 4:index - 2], ["sound.stop", "sound.play"])
                self.assertEqual(names[index + 1], "animator.play")
        self.assertEqual(names[-2:], ["sound.stop", "dmx.close"])

    def test_sound_loop_contains_0_4_seconds_of_silence(self):
        mixer = Mock()
        mixer.get_init.return_value = (1000, -16, 2)
        source = Mock()
        source.get_raw.return_value = b"\x01\x00\x02\x00"
        self.assertIs(app.with_loop_gap(source, mixer), mixer.Sound.return_value)
        mixer.Sound.assert_called_once_with(buffer=source.get_raw.return_value + bytes(1600))

    def test_sound_file_is_loaded_and_mixer_is_closed(self):
        cards = {"A": {"name": "card", "dmx": [0] * 16}}
        audio = Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effect.mp3"
            path.touch()
            with patch("sys.argv", ["nfc_dmx.py", "--sound", str(path)]), patch.object(
                app, "load_cards", return_value=cards
            ), patch.object(app, "get_reader"), patch.dict(sys.modules, {"pygame": audio}), patch.object(
                app, "run_dmx", side_effect=RuntimeError("test cleanup")
            ) as run, patch.object(app, "with_loop_gap", return_value=Mock()) as add_gap:
                with self.assertRaisesRegex(RuntimeError, "test cleanup"):
                    app.main()
        audio.mixer.Sound.assert_called_once_with(str(path))
        add_gap.assert_called_once_with(audio.mixer.Sound.return_value, audio.mixer)
        self.assertIs(run.call_args.kwargs["sound"], add_gap.return_value)
        audio.mixer.quit.assert_called_once()

    def test_registration_saves_card_that_output_can_load(self):
        values = list(range(16))
        with tempfile.TemporaryDirectory() as directory, patch.object(
            common, "JSON_FILE", Path(directory) / "nfc_cards.json"
        ), patch.object(registration, "wait_for_card", return_value="A"), patch.object(
            registration, "wait_for_removal"
        ), patch("builtins.input", side_effect=["card", "2", ",".join(map(str, values)), "", "n"]):
            registration.register_cards(Mock(), {})
            loaded = app.load_cards()
        self.assertEqual(loaded, {"A": {"name": "card", "dmx": values}})

    def test_registration_menu_can_list_without_reader_or_dmx(self):
        with patch("sys.argv", ["nfc_register.py"]), patch.object(
            registration, "load_cards", return_value={}
        ), patch.object(registration, "get_reader") as reader, patch.object(
            app, "SerialController"
        ) as dmx, patch("builtins.input", side_effect=["2", "0"]):
            registration.main()
        reader.assert_not_called()
        dmx.assert_not_called()

    def test_real_backend_transmits_repeated_raw_dmx_frames(self):
        # 実際のSerialControllerを使い、USBポートだけを模擬する。
        port = Mock()
        received = threading.Event()
        values = [255, 0, 0, 255] + [0] * 12
        matching_frames = []

        def capture(data):
            frame = bytes(data)
            if len(frame) == 513 and frame[0] == 0 and frame[1:17] == bytes(values):
                matching_frames.append(frame)
                if len(matching_frames) >= 2:
                    received.set()
            return len(data)

        port.write.side_effect = capture
        with patch("PyDMXControl.controllers._SerialController.Serial", return_value=port), patch.object(app, "DMX_START_ADDRESS", 1):
            dmx = app.DMXController("MOCK_PORT")
            try:
                dmx.set_values(values)
                self.assertTrue(received.wait(2), "登録値のDMXフレームが継続送信されませんでした")
                self.assertTrue(port.send_break.called)
            finally:
                dmx.close()
        port.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

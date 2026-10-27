import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nfc"))
from laser import dmx_frames
import nfc_common as common
import nfc_register as registration

spec = importlib.util.spec_from_file_location("nfc_dmx", ROOT / "nfc" / "nfc_dmx.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def fake_lists():
    # list_1: 3コマ(0.1秒)、list_2: 2コマ(0.2秒)
    square = [(-100, -100, 0), (100, -100, 1), (100, 100, 1), (-100, 100, 1), (-100, -100, 1)]
    return [[(square, 0.1)] * 3, [(square, 0.2)] * 2], ["list_1", "list_2"]


class FrameValueTests(unittest.TestCase):
    def test_frames_map_to_ch4_ch5_as_found_on_the_laser(self):
        self.assertEqual(dmx_frames.frame_value(0), (189, 0))
        self.assertEqual(dmx_frames.frame_value(49), (189, 98))
        self.assertEqual(dmx_frames.frame_value(127), (189, 254))
        self.assertEqual(dmx_frames.frame_value(128), (199, 0))
        self.assertEqual(dmx_frames.frame_value(199), (199, 142))
        self.assertEqual(dmx_frames.frame_value(255), (199, 254))

    def test_frames_past_255_are_refused(self):
        # CH4 205 以降は本体が再起動した
        with self.assertRaises(ValueError):
            dmx_frames.frame_value(256)


class LayoutTests(unittest.TestCase):
    def test_animations_start_where_the_previous_ones_end(self):
        lists, names = fake_lists()
        layout = dmx_frames.Layout.from_lists(lists, names)
        self.assertEqual(layout.total, 5)
        self.assertEqual(layout.frames(1), [(0, 0.1), (1, 0.1), (2, 0.1)])
        self.assertEqual(layout.frames(2), [(3, 0.2), (4, 0.2)])
        with self.assertRaises(ValueError):
            layout.frames(3)

    def test_layout_survives_saving_and_loading(self):
        lists, names = fake_lists()
        layout = dmx_frames.Layout.from_lists(lists, names)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            layout.save(path)
            self.assertEqual(dmx_frames.load_layout(path).frames(2), layout.frames(2))

    def test_animation_past_frame_255_is_refused(self):
        layout = dmx_frames.Layout([{"name": "big", "first": 250, "secs": [0.1] * 10}])
        with self.assertRaises(ValueError):
            layout.frames(1)


class AnimatorTests(unittest.TestCase):
    def test_steps_through_the_frames_in_a_loop_until_stopped(self):
        seen = []
        timestamps = []
        lock = threading.Lock()

        def set_frame(ch4, ch5):
            with lock:
                seen.append((ch4, ch5))
                timestamps.append(time.monotonic())

        animator = dmx_frames.Animator(set_frame)
        with patch.object(dmx_frames, "LOOP_PAUSE_SECONDS", 0.03):
            animator.play([(3, 0.01), (4, 0.01)])
            time.sleep(0.15)
            animator.stop()
        self.assertFalse(animator.playing)
        with lock:
            self.assertGreaterEqual(len(seen), 4)
            self.assertEqual(seen[:4], [(189, 6), (189, 8), (189, 6), (189, 8)])
            self.assertGreaterEqual(timestamps[2] - timestamps[1], 0.035)
        count = len(seen)
        time.sleep(0.05)
        self.assertEqual(len(seen), count)  # 止めた後は書き換えない

    def test_stop_interrupts_the_loop_pause(self):
        started = threading.Event()
        animator = dmx_frames.Animator(lambda _a, _b: started.set())
        animator.play([(3, 0.01)])
        self.assertTrue(started.wait(1))
        time.sleep(0.02)
        before = time.monotonic()
        animator.stop()
        self.assertLess(time.monotonic() - before, 0.8)
        self.assertFalse(animator.playing)


class UploadFramesTests(unittest.TestCase):
    def test_sample_send_data_converts_and_fits_dmx(self):
        from laser import frames, playlist

        lists, names, _report = frames.build(str(ROOT / "laser" / "SEND_DATA"))
        layout = dmx_frames.Layout.from_lists(lists, names)
        self.assertLessEqual(layout.total, dmx_frames.DMX_FRAMES)
        for lst in lists:
            for points, secs in lst:
                data = playlist.frame(0, points, secs)
                self.assertEqual(data[:2], b"\xF0\xF1")
                self.assertEqual(data[-2:], b"\xF6\xF7")
                cleaned = playlist.clean(points)
                # 同じ座標の点が続くと本体がそのコマを受け付けない
                self.assertFalse(any(a[:2] == b[:2] for a, b in zip(cleaned, cleaned[1:])))


class NfcAnimationTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_card_with_animation_starts_on_its_first_frame_and_plays(self):
        lists, names = fake_lists()
        layout = dmx_frames.Layout.from_lists(lists, names)
        values = [128, 15] + [0] * 14
        cards = {"A": {"name": "anim", "dmx": values, "animation": 2},
                 "B": {"name": "plain", "dmx": [255] * 16}}
        controller = Mock()
        animator = Mock()
        with patch.object(app, "DMXController", return_value=controller), patch.object(
            app, "Animator", return_value=animator
        ), patch.object(app, "read_uid", side_effect=["A", "B", KeyboardInterrupt]), patch.object(
            app.time, "sleep"
        ):
            app.run_dmx(Mock(), cards, "COM_TEST", layout=layout)
        first = values.copy()
        first[3], first[4] = 189, 6           # アニメーション2の1コマ目 = 保存コマ3
        self.assertEqual([c.args[0] for c in controller.set_values.call_args_list], [first, [255] * 16])
        animator.play.assert_called_once_with(layout.frames(2))
        self.assertGreaterEqual(animator.stop.call_count, 2)   # カードB と 終了時
        controller.close.assert_called_once()

    def test_card_with_missing_animation_falls_back_to_its_values(self):
        lists, names = fake_lists()
        layout = dmx_frames.Layout.from_lists(lists, names)
        cards = {"A": {"name": "anim", "dmx": [7] * 16, "animation": 9}}
        controller = Mock()
        animator = Mock()
        with patch.object(app, "DMXController", return_value=controller), patch.object(
            app, "Animator", return_value=animator
        ), patch.object(app, "read_uid", side_effect=["A", KeyboardInterrupt]), patch.object(
            app.time, "sleep"
        ):
            app.run_dmx(Mock(), cards, "COM_TEST", layout=layout)
        self.assertEqual(controller.set_values.call_args.args[0], [7] * 16)
        animator.play.assert_not_called()

    def test_set_channel_writes_one_fixture(self):
        backend = Mock()
        fixtures = [Mock() for _ in range(16)]
        backend.add_fixture.side_effect = fixtures
        with patch.object(app, "SerialController", return_value=backend):
            dmx = app.DMXController("COM_TEST")
        dmx.set_channel(5, 42)
        fixtures[4].dim.assert_called_once_with(42, 0)
        with self.assertRaises(ValueError):
            dmx.set_channel(17, 0)

    def test_registration_stores_the_animation_number(self):
        values = list(range(16))
        with tempfile.TemporaryDirectory() as directory, patch.object(
            common, "JSON_FILE", Path(directory) / "nfc_cards.json"
        ), patch.object(registration, "wait_for_card", return_value="A"), patch.object(
            registration, "wait_for_removal"
        ), patch("builtins.input", side_effect=["card", "2", ",".join(map(str, values)), "3", "n"]):
            registration.register_cards(Mock(), {})
            loaded = app.load_cards()
        self.assertEqual(loaded, {"A": {"name": "card", "dmx": values, "animation": 3}})

    def test_bad_animation_number_is_rejected_when_loading(self):
        with self.assertRaises(ValueError):
            common.validate_animation(0)
        with self.assertRaises(ValueError):
            common.validate_animation("2")
        self.assertIsNone(common.validate_animation(None))


if __name__ == "__main__":
    unittest.main()

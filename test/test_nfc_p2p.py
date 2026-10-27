import contextlib
import io
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nfc"))
import nfc_dmx as app
import p2p


class P2PTests(unittest.TestCase):
    def setUp(self):
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_protocol_validates_scene_before_dmx_output(self):
        card = {"name": "花火", "dmx": list(range(16)), "animation": 2}
        self.assertEqual(p2p.decode_message(p2p.encode_card("ABCD", card)), ("card", "ABCD", card))
        self.assertEqual(p2p.decode_message(p2p.encode_ping()), None)
        invalid = p2p.encode_card("ABCD", {"name": "bad", "dmx": [0] * 15 + [256]})
        with self.assertRaises(ValueError):
            p2p.decode_message(invalid)
        with self.assertRaises(ValueError):
            p2p.decode_message(b"x" * (p2p.MAX_LINE + 1))

    def test_receiver_handles_card_and_sync_over_real_socket(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        card = {"name": "anim", "dmx": [128] + [0] * 15, "animation": 1}
        dmx, animator = Mock(), Mock()
        layout = Mock()
        layout.frames.return_value = [(0, 0.1)]
        with patch.object(app, "load_animation_layout", return_value=layout), patch.object(app.time, "sleep") as delay:
            worker = threading.Thread(target=app.handle_peer, args=(receiver, dmx, animator))
            worker.start()
            sender.sendall(p2p.encode_card("A", card) + p2p.encode_ping() + p2p.encode_card("A", card, sync=True))
            sender.shutdown(socket.SHUT_WR)
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(dmx.set_values.call_count, 2)
        delay.assert_called_once_with(3.0)
        self.assertEqual(animator.play.call_count, 2)

    def test_receiver_keeps_previous_animation_running_during_switch_delay(self):
        card = {"name": "anim", "dmx": [128] + [0] * 15, "animation": 1}
        connection = Mock()
        connection.makefile.return_value = io.BytesIO(
            p2p.encode_card("A", card) + p2p.encode_card("B", card)
        )
        dmx, animator = Mock(), Mock()
        layout = Mock()
        layout.frames.return_value = [(0, 0.1)]
        stops_during_delay = []

        def record_delay(seconds):
            self.assertEqual(seconds, 3.0)
            stops_during_delay.append(animator.stop.call_count)

        with patch.object(app, "load_animation_layout", return_value=layout), patch.object(
            app.time, "sleep", side_effect=record_delay
        ):
            app.handle_peer(connection, dmx, animator)

        self.assertEqual(stops_during_delay, [0, 1])
        self.assertEqual(dmx.set_values.call_count, 2)
        self.assertEqual(animator.play.call_count, 2)

    def test_sender_reconnects_and_restores_last_card_without_replaying_sound(self):
        first, second = Mock(), Mock()
        sound = Mock()
        first.sendall.side_effect = [None, BrokenPipeError("closed")]
        cards = {"A": {"name": "card", "dmx": [1] * 16}}
        with patch.object(app, "read_uid", side_effect=["A", "A", "A", KeyboardInterrupt]), patch.object(
            app.socket, "create_connection", side_effect=[first, second]
        ), patch.object(app.time, "monotonic", side_effect=[0, 3, 5]), patch.object(app.time, "sleep"):
            app.run_sender(Mock(), cards, "127.0.0.1", sound=sound)
        self.assertEqual(p2p.decode_message(first.sendall.call_args_list[0].args[0])[0], "card")
        self.assertEqual(p2p.decode_message(second.sendall.call_args.args[0])[0], "sync")
        first.close.assert_called_once()
        second.close.assert_called_once()
        sound.play.assert_called_once_with(loops=-1)
        self.assertEqual(sound.stop.call_count, 2)  # 読み取り時と終了時

    def test_sender_plays_on_each_new_scan_even_without_peer(self):
        cards = {"A": {"name": "card", "dmx": [1] * 16}}
        sound = Mock()
        with patch.object(app, "read_uid", side_effect=["A", "A", None, "A", KeyboardInterrupt]), patch.object(
            app.socket, "create_connection", side_effect=ConnectionRefusedError("offline")
        ), patch.object(app.time, "sleep"):
            app.run_sender(Mock(), cards, "127.0.0.1", sound=sound)
        self.assertEqual(sound.play.call_count, 2)
        self.assertTrue(all(call.kwargs == {"loops": -1} for call in sound.play.call_args_list))
        self.assertEqual(sound.stop.call_count, 3)

    def test_receive_mode_needs_no_nfc_reader_or_card_database(self):
        with patch("sys.argv", ["nfc_dmx.py", "--receive"]), patch.object(
            app, "load_cards"
        ) as cards, patch.object(app, "get_reader") as reader, patch.object(
            app, "run_receiver"
        ) as receive, patch.dict(sys.modules, {"pygame": None}):
            app.main()
        cards.assert_not_called()
        reader.assert_not_called()
        receive.assert_called_once_with("127.0.0.1", p2p.DEFAULT_PORT, app.DMX_PORT)

    def test_send_mode_loads_sound_on_nfc_terminal(self):
        cards = {"A": {"name": "card", "dmx": [1] * 16}}
        audio = Mock()
        with patch("sys.argv", ["nfc_dmx.py", "--send-to", "127.0.0.1"]), patch.object(
            app, "load_cards", return_value=cards
        ), patch.object(app, "get_reader", return_value=Mock()), patch.object(
            app, "run_sender"
        ) as sender, patch.object(app, "with_loop_gap", return_value=Mock()) as add_gap:
            with patch.dict(sys.modules, {"pygame": audio}):
                app.main()
        audio.mixer.Sound.assert_called_once_with(str(app.DEFAULT_SOUND))
        add_gap.assert_called_once_with(audio.mixer.Sound.return_value, audio.mixer)
        self.assertIs(sender.call_args.kwargs["sound"], add_gap.return_value)
        audio.mixer.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()

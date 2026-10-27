import sys
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ir_led"))
import sound_player
from sound_player import (PlayResult, SensorSoundPlayer, non_negative_seconds,
                          parse_ir_event, sound_name_for)


class FakeChannel:
    def __init__(self):
        self.busy = False
        self.played = []

    def get_busy(self):
        return self.busy

    def play(self, sound):
        self.played.append(sound)
        self.busy = True


class FakeMixer:
    def __init__(self, count):
        self.channels = [FakeChannel() for _ in range(count)]

    def find_channel(self):
        return next((channel for channel in self.channels if not channel.busy), None)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class SoundPlayerTest(unittest.TestCase):
    def test_parses_each_controller_and_sensor(self):
        self.assertEqual(parse_ir_event(b"IR,5,4\r\n"), (5, 4))
        self.assertEqual(parse_ir_event(b"IR,1,1\n"), (1, 1))

    def test_ignores_other_or_invalid_serial_lines(self):
        for line in (b"1\n", b"IR,6,1\n", b"IR,1,5\n", b"IR,x,1\n", b"\xff\n"):
            with self.subTest(line=line):
                self.assertIsNone(parse_ir_event(line))

    def test_default_sound_mapping(self):
        self.assertEqual(sound_name_for(1, 2), "obake2.mp3")
        self.assertEqual(sound_name_for(5, 2), "obake2.mp3")

    def test_device_specific_sound_mapping(self):
        with patch.dict(sound_player.SOUND_MAP[2], {1: "piano1.mp3"}):
            self.assertEqual(sound_name_for(2, 1), "piano1.mp3")
            self.assertEqual(sound_name_for(1, 1), "obake1.mp3")

    def test_every_device_and_sensor_has_an_existing_effect(self):
        for device_id in range(1, sound_player.DEVICE_COUNT + 1):
            for sensor_id in range(1, sound_player.SENSORS_PER_DEVICE + 1):
                with self.subTest(device_id=device_id, sensor_id=sensor_id):
                    name = sound_name_for(device_id, sensor_id)
                    self.assertTrue((sound_player.EFFECTS_DIR / name).is_file())

    def test_same_sensor_overlaps_after_interval_even_while_previous_sound_plays(self):
        sound = object()
        mixer = FakeMixer(2)
        clock = FakeClock()
        player = SensorSoundPlayer({"obake1.mp3": sound}, mixer.find_channel, 0.5, clock)

        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)
        clock.now = 0.49
        self.assertEqual(player.play(1, 1), PlayResult.TOO_SOON)
        clock.now = 0.5
        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)
        self.assertEqual([channel.played for channel in mixer.channels], [[sound], [sound]])

    def test_no_free_channel_does_not_advance_interval(self):
        mixer = FakeMixer(1)
        clock = FakeClock()
        player = SensorSoundPlayer({"obake1.mp3": object()}, mixer.find_channel, 0.5, clock)

        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)
        clock.now = 1.0
        self.assertEqual(player.play(1, 1), PlayResult.NO_CHANNEL)
        mixer.channels[0].busy = False
        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)

    def test_zero_interval_allows_immediate_overlap(self):
        mixer = FakeMixer(2)
        clock = FakeClock()
        player = SensorSoundPlayer({"obake1.mp3": object()}, mixer.find_channel, 0, clock)

        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)
        self.assertEqual(player.play(1, 1), PlayResult.PLAYED)

    def test_different_sensors_can_play_the_same_sound_at_the_same_time(self):
        sound = object()
        mixer = FakeMixer(2)
        clock = FakeClock()
        player = SensorSoundPlayer({"obake1.mp3": sound}, mixer.find_channel, 0.5, clock)

        with patch.dict(sound_player.SOUND_MAP[1], {2: "obake1.mp3"}):
            self.assertEqual(player.play(1, 1), PlayResult.PLAYED)
            self.assertEqual(player.play(1, 2), PlayResult.PLAYED)

        self.assertEqual([channel.played for channel in mixer.channels], [[sound], [sound]])

    def test_interval_must_be_finite_and_non_negative(self):
        self.assertEqual(non_negative_seconds("0"), 0)
        self.assertEqual(non_negative_seconds("0.15"), 0.15)
        for value in ("-1", "nan", "inf", "abc"):
            with self.subTest(value=value), self.assertRaises(sound_player.argparse.ArgumentTypeError):
                non_negative_seconds(value)

    def test_auto_detects_five_ports_and_tracks_reconnections(self):
        readers = {}
        events = Queue()
        available = []
        started = []
        stopped = []

        def fake_comports():
            return [SimpleNamespace(device=port) for port in available]

        def fake_read_port(port, _events, stop):
            started.append(port)
            stop.wait()
            stopped.append(port)

        with patch.object(sound_player.list_ports, "comports", side_effect=fake_comports), \
             patch.object(sound_player, "read_port", side_effect=fake_read_port):
            try:
                self.assertEqual(sound_player.refresh_auto_ports(readers, events), set())
                available[:] = [f"COM{number}" for number in range(1, 6)]
                self.assertEqual(sound_player.refresh_auto_ports(readers, events), set())
                self.assertEqual(set(readers), set(available))

                sound_player.refresh_auto_ports(readers, events)
                available[:] = ["COM1", "COM3", "COM4", "COM5", "COM6"]
                self.assertEqual(sound_player.refresh_auto_ports(readers, events), {"COM2"})
                self.assertEqual(set(readers), set(available))
            finally:
                for port_stop, thread in readers.values():
                    port_stop.set()
                for port_stop, thread in readers.values():
                    thread.join()

        self.assertEqual(set(started), {f"COM{number}" for number in range(1, 7)})
        self.assertEqual(len(started), 6)
        self.assertEqual(set(stopped), set(started))


if __name__ == "__main__":
    unittest.main()

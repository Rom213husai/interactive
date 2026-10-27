"""赤外線センサの反応をマイコンから受け取り、対応する効果音を再生する。"""

import argparse
from enum import Enum
from math import isfinite
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic

import serial
from serial.tools import list_ports


BAUD_RATE = 115200
PORT_SCAN_INTERVAL = 2
DEVICE_COUNT = 5
SENSORS_PER_DEVICE = 4
SENSOR_COUNT = DEVICE_COUNT * SENSORS_PER_DEVICE
MAX_SOUND_CHANNELS = SENSOR_COUNT * 4
DEFAULT_INTERVAL_SECONDS = 0.15
EFFECTS_DIR = Path(__file__).resolve().parent.parent / "effects"

# 外側がマイコン番号、内側がセンサ番号。各組み合わせの音声ファイル名を変更する。
# 音声ファイルは effects/number/ に置く。
SOUND_MAP = {
    1: {
        1: "obake1.mp3",
        2: "obake2.mp3",
        3: "normal_Do.mp3",
        4: "normal_Re.mp3",
    },
    2: {
        1: "kir_mi.mp3",
        2: "kir_fa.mp3",
        3: "kir_so.mp3",
        4: "kir_la.mp3",
    },
    3: {
        1: "normal_Si.mp3",
        2: "normal_Do_high.mp3",
        3: "high_Re.mp3",
        4: "high_Mi.mp3",
    },
    4: {
        1: "high_Fa.mp3",
        2: "high_So.mp3",
        3: "high_La.mp3",
        4: "high_Si.mp3",
    },
    5: {
        1: "high_Do_high.mp3",
        2: "obake2.mp3",
        3: "obake3.mp3",
        4: "obake4.mp3",
    },
}


def parse_ir_event(line):
    try:
        kind, device_text, sensor_text = line.decode("ascii").strip().split(",")
        device_id = int(device_text)
        sensor_id = int(sensor_text)
    except (UnicodeDecodeError, ValueError):
        return None

    if kind != "IR" or not 1 <= device_id <= DEVICE_COUNT or not 1 <= sensor_id <= SENSORS_PER_DEVICE:
        return None
    return device_id, sensor_id


def sound_name_for(device_id, sensor_id):
    return SOUND_MAP[device_id][sensor_id]


def non_negative_seconds(value):
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("interval must be a number of seconds") from error
    if not isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("interval must be a non-negative finite number of seconds")
    return seconds


class PlayResult(Enum):
    PLAYED = "played"
    TOO_SOON = "interval"
    NO_CHANNEL = "no free channel"


class SensorSoundPlayer:
    def __init__(self, sounds, find_channel, interval_seconds=DEFAULT_INTERVAL_SECONDS,
                 clock=monotonic):
        self.sounds = sounds
        self.find_channel = find_channel
        self.interval_seconds = interval_seconds
        self.clock = clock
        self.last_started = {}

    def play(self, device_id, sensor_id):
        sensor = (device_id, sensor_id)
        now = self.clock()
        previous = self.last_started.get(sensor)
        if previous is not None and now - previous < self.interval_seconds:
            return PlayResult.TOO_SOON

        channel = self.find_channel()
        if channel is None:
            return PlayResult.NO_CHANNEL

        name = sound_name_for(device_id, sensor_id)
        channel.play(self.sounds[name])
        self.last_started[sensor] = now
        return PlayResult.PLAYED


def read_port(port, events, stop):
    while not stop.is_set():
        try:
            with serial.Serial(port, BAUD_RATE, timeout=0.5) as connection:
                print(f"Connected: {port}", flush=True)
                while not stop.is_set():
                    event = parse_ir_event(connection.readline())
                    if event is not None:
                        events.put((port, *event))
        except (serial.SerialException, OSError) as error:
            print(f"Waiting for {port}: {error}", flush=True)
            stop.wait(2)


def refresh_auto_ports(readers, events):
    try:
        available = {port.device for port in list_ports.comports()}
    except (serial.SerialException, OSError) as error:
        print(f"Serial port discovery failed: {error}", flush=True)
        return set()

    removed = set(readers) - available
    for port in sorted(removed):
        port_stop, thread = readers.pop(port)
        port_stop.set()
        thread.join()
        print(f"Disconnected: {port}", flush=True)

    for port in sorted(available - set(readers)):
        port_stop = Event()
        thread = Thread(target=read_port, args=(port, events, port_stop))
        readers[port] = (port_stop, thread)
        thread.start()

    return removed


def main():
    parser = argparse.ArgumentParser(description="Play sounds from IR sensor events")
    parser.add_argument("ports", nargs="*",
                        help="Controller serial ports, up to five (default: auto-detect available ports)")
    parser.add_argument("--list-ports", action="store_true", help="Show available serial ports")
    parser.add_argument("--interval", type=non_negative_seconds,
                        default=DEFAULT_INTERVAL_SECONDS, metavar="SECONDS",
                        help=f"Minimum seconds between starts for the same sensor "
                             f"(default: {DEFAULT_INTERVAL_SECONDS})")
    args = parser.parse_args()

    if args.list_ports:
        for port in list_ports.comports():
            print(f"{port.device}: {port.description}")
        return

    if len(args.ports) > DEVICE_COUNT or len(set(args.ports)) != len(args.ports):
        parser.error("specify one to five distinct serial ports")

    import pygame

    pygame.mixer.init()
    pygame.mixer.set_num_channels(MAX_SOUND_CHANNELS)
    sounds = {}
    names = {
        sound_name_for(device_id, sensor_id)
        for device_id in range(1, DEVICE_COUNT + 1)
        for sensor_id in range(1, SENSORS_PER_DEVICE + 1)
    }
    for name in names:
        path = EFFECTS_DIR / name
        sounds[name] = pygame.mixer.Sound(str(path))
    sound_player = SensorSoundPlayer(sounds, pygame.mixer.find_channel, args.interval)

    events = Queue()
    stop = Event()
    threads = [Thread(target=read_port, args=(port, events, stop)) for port in args.ports]
    for thread in threads:
        thread.start()

    auto_readers = {}
    next_scan = 0
    if not args.ports:
        print("Auto-detecting serial ports...", flush=True)

    port_for_device = {}
    try:
        while True:
            if not args.ports and monotonic() >= next_scan:
                removed = refresh_auto_ports(auto_readers, events)
                port_for_device = {
                    device_id: port for device_id, port in port_for_device.items()
                    if port not in removed
                }
                next_scan = monotonic() + PORT_SCAN_INTERVAL

            try:
                port, device_id, sensor_id = events.get(timeout=0.5)
            except Empty:
                continue
            if not args.ports and port not in auto_readers:
                continue

            other_port = port_for_device.get(device_id)
            if other_port is not None and other_port != port:
                print(f"Duplicate DEVICE_ID {device_id}: {other_port} and {port}", flush=True)
            port_for_device[device_id] = port

            name = sound_name_for(device_id, sensor_id)
            result = sound_player.play(device_id, sensor_id)
            if result == PlayResult.PLAYED:
                print(f"IR {device_id}:{sensor_id} -> {name}", flush=True)
            else:
                print(f"IR {device_id}:{sensor_id} -> {name} skipped: {result.value}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for port_stop, thread in auto_readers.values():
            port_stop.set()
        for port_stop, thread in auto_readers.values():
            thread.join()
        for thread in threads:
            thread.join()
        pygame.mixer.quit()


if __name__ == "__main__":
    main()

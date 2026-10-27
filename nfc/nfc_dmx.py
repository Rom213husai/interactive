"""Scan NFC cards locally or send their settings to a separate DMX terminal.

A card with "animation": N plays animation N stored on the laser (laser/SEND_DATA,
stored with `python -m laser.upload`) by stepping CH4/CH5 frame by frame; its other
channels are output as registered.
"""

import argparse
import socket
import sys
import threading
import time
from pathlib import Path

if __package__:
    from . import p2p
    from .nfc_common import (
        DMX_START_ADDRESS,
        DMX_CHANNEL_COUNT,
        READ_INTERVAL,
        ANIMATION_CHANNELS,
        validate_dmx_values,
        show_dmx_values,
        show_animation,
        load_cards,
        get_reader,
        read_uid,
    )
else:
    import p2p
    from nfc_common import (
        DMX_START_ADDRESS,
        DMX_CHANNEL_COUNT,
        READ_INTERVAL,
        ANIMATION_CHANNELS,
        validate_dmx_values,
        show_dmx_values,
        show_animation,
        load_cards,
        get_reader,
        read_uid,
    )

# laser/（リポジトリ直下）を読み込むため
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from laser.dmx_frames import Animator, frame_value, load_layout  # noqa: E402


DMX_PORT = "COM7"
RETRY_INTERVAL = 1.0
PING_INTERVAL = 2.0


def SerialController(port):
    # NFC送信端末にはDMX用ライブラリをインストールしなくてもよい。
    from PyDMXControl.controllers import SerialController as Controller
    return Controller(port)


DEFAULT_SOUND = Path(__file__).resolve().parents[1] / "effects" / "firework2.mp3"
SOUND_LOOP_GAP = 0.15


def with_loop_gap(sound, mixer):
    """Append silence to one PCM sound so pygame can loop it with a gap."""
    rate, size, channels = mixer.get_init()
    sample_bytes = abs(size) // 8
    silence_value = 0 if size < 0 else 1 << (size - 1)
    silence_sample = silence_value.to_bytes(sample_bytes, sys.byteorder)
    silence = silence_sample * channels * round(rate * SOUND_LOOP_GAP)
    return mixer.Sound(buffer=sound.get_raw() + silence)


class DMXController:

    def __init__(self, port):
        from PyDMXControl.profiles.Generic import Dimmer
        if (
            type(DMX_START_ADDRESS) is not int
            or not 1 <= DMX_START_ADDRESS <= 513 - DMX_CHANNEL_COUNT
        ):
            raise ValueError("16チャンネルのDMX開始アドレスは1～497で指定してください")
        self.controller = SerialController(port)
        try:
            self.fixtures = [
                self.controller.add_fixture(
                    Dimmer,
                    name=f"CH{channel}",
                    start_channel=DMX_START_ADDRESS + channel - 1,
                )
                for channel in range(1, DMX_CHANNEL_COUNT + 1)
            ]
        except Exception:
            self.controller.close()
            raise

        # アニメーションのコマ送りは別スレッドから CH4/CH5 を書き換える
        self.lock = threading.Lock()
        print(f"DMX接続成功: {port}")

    def set_values(self, values):
        values = validate_dmx_values(values)
        with self.lock:
            for fixture, value in zip(self.fixtures, values):
                fixture.dim(value, 0)

    def set_channel(self, channel, value):
        if not 1 <= channel <= DMX_CHANNEL_COUNT or not 0 <= value <= 255:
            raise ValueError(f"CH{channel}={value}: CH1～CH16、0～255で指定してください")
        with self.lock:
            self.fixtures[channel - 1].dim(value, 0)

    def close(self):
        # ゼロ値の送信は停止保証ではありません
        try:
            self.set_values([0] * DMX_CHANNEL_COUNT)
            # バックグラウンド送信がゼロ値を出力する時間を確保する。
            time.sleep(READ_INTERVAL)
        finally:
            self.controller.close()

def load_animation_layout(cards):
    """アニメーション付きのカードがあれば、最後に保存したレイアウトを読む"""
    if not any(info.get("animation") for info in cards.values()):
        return None
    try:
        layout = load_layout()
    except (OSError, ValueError, KeyError) as e:
        print("レーザーアニメーションの情報を読めません:", e)
        print("アニメーション付きのカードも、登録した16チャンネルだけを出力します")
        return None
    print("レーザーアニメーション:")
    for line in layout.table():
        print("  " + line)
    return layout

def animation_frames(info, layout):
    """カードのアニメーションのコマ一覧（無い・使えないときは None）"""
    number = info.get("animation")
    if not number or layout is None:
        return None
    try:
        return layout.frames(number)
    except ValueError as e:
        print("アニメーションを再生できません:", e)
        return None


def play_sound(sound):
    if sound is None:
        return
    sound.stop()
    if sound.play(loops=-1) is None:
        print("音声を再生できませんでした（pygameの音声チャンネルを確認してください）")


def play_card(info, dmx, animator, layout, sound=None, *, sync=False):
    """Apply one card on the DMX terminal; sync restores output after reconnect."""
    print("カード:", info["name"])
    show_dmx_values(info["dmx"])
    show_animation(info)

    if not sync:
        play_sound(sound)

    frames = animation_frames(info, layout)
    values = list(info["dmx"])
    if frames:
        ch4, ch5 = ANIMATION_CHANNELS
        values[ch4 - 1], values[ch5 - 1] = frame_value(frames[0][0])
    if not sync:
        time.sleep(3.0)  # この間は前のアニメーションを動かし続ける
    animator.stop()
    dmx.set_values(values)
    if frames:
        animator.play(frames)
        print(f"レーザーアニメーション {info['animation']} を再生中"
              f"（{len(frames)}コマ、次のカードを読むまでループ）")
    print("DMX出力値を更新しました（次のカードを読むまで継続出力）")

def run_dmx(reader, cards, port=DMX_PORT, layout=None, sound=None):
    print("\n===== DMX実行モード =====")

    if not cards:
        print("カードが登録されていません")
        return

    if layout is None:
        layout = load_animation_layout(cards)

    try:
        dmx = DMXController(port)
    except (ImportError, OSError, ValueError) as e:
        print("DMX接続失敗:", e)
        return

    print("カードをかざしてください")
    print("登録済みの16チャンネルを継続出力します。Ctrl+Cで実行を終了します")

    ch4, ch5 = ANIMATION_CHANNELS
    animator = Animator(lambda a, b: (dmx.set_channel(ch4, a), dmx.set_channel(ch5, b)))
    last_uid = None

    try:
        while True:
            try:
                uid = read_uid(reader)
            except Exception as e:
                print("NFC読み取りエラー。リーダーを確認して再試行します:", e)
                time.sleep(READ_INTERVAL)
                continue

            if uid is None:
                last_uid = None

            elif uid != last_uid:
                print("\nUID:", uid)

                if uid in cards:
                    play_card(cards[uid], dmx, animator, layout, sound)

                else:
                    print("未登録カードです")

                last_uid = uid

            time.sleep(READ_INTERVAL)

    except KeyboardInterrupt:
        print("\nDMX実行モードを終了します")

    except OSError as e:
        print("DMX通信エラー:", e)

    finally:
        animator.stop()
        if sound is not None:
            sound.stop()
        try:
            dmx.close()
        except OSError as e:
            print("DMX終了処理エラー:", e)


def run_sender(reader, cards, host, tcp_port=p2p.DEFAULT_PORT, sound=None):
    """Scan locally and send only registered card actions to one direct TCP peer."""
    print(f"NFC送信モード: {host}:{tcp_port}")
    last_uid = None
    current_card = None
    pending = None
    connection = None
    next_retry = 0.0
    next_ping = 0.0
    sync_needed = False
    disconnected_reported = False

    try:
        while True:
            try:
                uid = read_uid(reader)
            except Exception as e:
                print("NFC読み取りエラー。リーダーを確認して再試行します:", e)
                time.sleep(READ_INTERVAL)
                continue

            if uid is None:
                last_uid = None
            elif uid != last_uid:
                print("\nUID:", uid)
                if uid in cards:
                    play_sound(sound)
                    current_card = (uid, cards[uid])
                    pending = current_card
                    print("送信待ち:", cards[uid]["name"])
                else:
                    print("未登録カードです")
                last_uid = uid

            now = time.monotonic()
            if connection is None and now >= next_retry:
                try:
                    connection = socket.create_connection((host, tcp_port), timeout=0.5)
                    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError as e:
                    if connection is not None:
                        connection.close()
                    connection = None
                    next_retry = now + RETRY_INTERVAL
                    if not disconnected_reported:
                        print("投影端末に接続できません。再試行します:", e)
                        disconnected_reported = True
                else:
                    print("投影端末に接続しました")
                    disconnected_reported = False
                    # 再接続時は、直近の未送信カードまたは表示中の状態を復元する。
                    sync_needed = pending is None and current_card is not None
                    next_ping = now

            if connection is not None:
                try:
                    if pending is not None:
                        connection.sendall(p2p.encode_card(*pending))
                        pending = None
                        sync_needed = False
                        next_ping = now + PING_INTERVAL
                    elif sync_needed:
                        connection.sendall(p2p.encode_card(*current_card, sync=True))
                        sync_needed = False
                        next_ping = now + PING_INTERVAL
                    elif now >= next_ping:
                        connection.sendall(p2p.encode_ping())
                        next_ping = now + PING_INTERVAL
                except OSError as e:
                    print("投影端末との接続が切れました。再接続します:", e)
                    connection.close()
                    connection = None
                    next_retry = now + RETRY_INTERVAL
                    disconnected_reported = True

            time.sleep(READ_INTERVAL)
    except KeyboardInterrupt:
        print("\nNFC送信モードを終了します")
    finally:
        if connection is not None:
            connection.close()
        if sound is not None:
            sound.stop()


def handle_peer(connection, dmx, animator):
    """Receive one peer's messages; keep the DMX output after it disconnects."""
    layout = None
    layout_checked = False
    with connection.makefile("rb") as stream:
        while True:
            line = stream.readline(p2p.MAX_LINE + 1)
            if not line:
                return
            if len(line) > p2p.MAX_LINE:
                print("受信メッセージが長すぎます。接続を切ります")
                return
            try:
                message = p2p.decode_message(line)
            except ValueError as e:
                print("受信メッセージを無視しました:", e)
                continue
            if message is None:
                continue
            kind, uid, info = message
            print("\nUID:", uid)
            if info.get("animation") and not layout_checked:
                layout = load_animation_layout({uid: info})
                layout_checked = True
            play_card(info, dmx, animator, layout, sync=(kind == "sync"))


def run_receiver(listen_host, tcp_port=p2p.DEFAULT_PORT, port=DMX_PORT):
    """Own the DMX and laser resources while accepting one NFC peer at a time."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((listen_host, tcp_port))
            listener.listen(1)
            try:
                dmx = DMXController(port)
            except (ImportError, OSError, ValueError) as e:
                print("DMX接続失敗:", e)
                return
            ch4, ch5 = ANIMATION_CHANNELS
            animator = Animator(lambda a, b: (dmx.set_channel(ch4, a), dmx.set_channel(ch5, b)))
            print(f"投影受信モード: {listen_host}:{tcp_port} / DMX: {port}")
            try:
                while True:
                    with listener.accept()[0] as connection:
                        print("NFC端末が接続しました")
                        try:
                            handle_peer(connection, dmx, animator)
                        except OSError as e:
                            print("NFC端末との通信エラー:", e)
                        print("NFC端末が切断しました。次の接続を待ちます")
            except KeyboardInterrupt:
                print("\n投影受信モードを終了します")
            finally:
                animator.stop()
                try:
                    dmx.close()
                except OSError as e:
                    print("DMX終了処理エラー:", e)
    except OSError as e:
        print("受信待ちを開始できません:", e)


def main():
    parser = argparse.ArgumentParser(description="NFCカードの登録値をDMXへ出力")
    # 旧コマンド --run も引き続き受け付ける。
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--send-to", metavar="HOST", help="NFC送信端末: 投影端末のIPアドレス")
    mode.add_argument("--receive", action="store_true", help="投影端末: NFC端末から直接受信する")
    parser.add_argument("--listen", default="127.0.0.1", metavar="HOST",
                        help="投影端末で待ち受けるIPアドレス（既定: 127.0.0.1）")
    parser.add_argument("--tcp-port", type=int, default=p2p.DEFAULT_PORT,
                        help=f"端末間通信用TCPポート（既定: {p2p.DEFAULT_PORT}）")
    parser.add_argument("--port", default=DMX_PORT, help=f"DMXポート（既定: {DMX_PORT}）")
    default_sound_option = object()
    audio = parser.add_mutually_exclusive_group()
    audio.add_argument("--sound", type=Path, default=default_sound_option,
                       help="NFC端末でカード読み取り時に再生する音声ファイル（既定: effects/firework2.mp3）")
    audio.add_argument("--no-sound", dest="sound", action="store_const", const=None,
                       help="音声を再生しない")
    parser.add_argument(
        "--laser",
        action="store_true",
        help="開始時にBluetoothでレーザーをDMXモードにし、終了時にビームを消す",
    )
    args = parser.parse_args()
    if not 1 <= args.tcp_port <= 65535:
        parser.error("--tcp-port は1～65535で指定してください")
    if args.send_to and args.laser:
        parser.error("--laser は投影端末で指定してください")
    if args.receive and args.sound is not default_sound_option:
        parser.error("--sound / --no-sound はNFC端末で指定してください")
    if args.sound is default_sound_option:
        args.sound = DEFAULT_SOUND

    cards = None
    reader = None
    if not args.receive:
        try:
            cards = load_cards()
        except (OSError, ValueError) as e:
            print("カード設定の読み込み失敗:", e)
            return
        if not cards:
            print("登録カードがありません。先に python nfc/nfc_register.py で登録してください")
            return
        print("登録済みカード:", len(cards), "枚")
        try:
            reader = get_reader()
        except RuntimeError as e:
            print("NFC接続失敗:", e)
            return

    sound = None
    pygame = None
    if not args.receive and args.sound is not None:
        if not args.sound.is_file():
            print("音声ファイルが見つかりません:", args.sound)
            return
        try:
            import pygame
        except ImportError:
            print("音声再生には python -m pip install pygame が必要です")
            return
        try:
            pygame.mixer.init()
            sound = with_loop_gap(pygame.mixer.Sound(str(args.sound)), pygame.mixer)
        except (pygame.error, OSError) as e:
            pygame.mixer.quit()
            print("音声ファイルを読み込めません:", e)
            return
    try:
        if args.send_to:
            run_sender(reader, cards, args.send_to, args.tcp_port, sound=sound)
        else:
            print(f"16チャンネル / DMX開始アドレス: {DMX_START_ADDRESS}")
            run_with_laser(reader, cards, args, sound)
    finally:
        if pygame is not None:
            pygame.mixer.quit()


def run_with_laser(reader, cards, args, sound=None):
    if args.laser:
        from laser import ble
        print("\nBluetoothでレーザーに接続してDMXモードにします（最大1分ほどかかります）")
        try:
            ble.dmx_mode()
        except (ConnectionError, OSError) as e:
            print("レーザーをDMXモードにできません:", e)
            return
        except KeyboardInterrupt:
            print("\n中止しました（レーザーはそのままです。スマホアプリで接続・切断するか電源を入れ直してください）")
            return
    try:
        if args.receive:
            run_receiver(args.listen, args.tcp_port, args.port)
        else:
            run_dmx(reader, cards, args.port, sound=sound)
    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        if args.laser:
            from laser import ble
            try:
                ble.beam_off()
            except (ConnectionError, OSError) as e:
                print("ビームを消せませんでした。レーザーの電源を切ってください:", e)


if __name__ == "__main__":
    main()

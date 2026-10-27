"""NFC reader access and shared card settings."""

import json
import time
from pathlib import Path

DMX_START_ADDRESS = 1

READ_INTERVAL = 0.2

DMX_CHANNELS = (
    "Master ON/OFF & Brightness Adjustment（点灯・消灯・明るさ）",
    "Color Change / Segmented Color / Color Drawing（色変え・途中の色変更・空白区切り）",
    "Color Flow Speed（色の流れる速度）",
    "Pattern Group Selection（パターングループ選択）",
    "Pattern Selection（CH4のグループ内のパターン選択）",
    "Built-in Dynamic Effects（内蔵ダイナミックエフェクト）",
    "Built-in Dynamic Speed（内蔵エフェクトの速度）",
    "Pattern Size（パターンサイズ）",
    "Pattern Auto Zoom（自動ズーム）",
    "Pattern Rotation Around Center（中心回転）",
    "Pattern Rotation Around X軸（X軸回転）",
    "Pattern Rotation Around Y軸（Y軸回転）",
    "Pattern Horizontal Movement（水平移動）",
    "Pattern Vertical Movement（垂直移動）",
    "Pattern X軸 Wave（X軸ウェーブ）",
    "Pattern Drawing（描画）",
)

DMX_CHANNEL_COUNT = len(DMX_CHANNELS)

JSON_FILE = Path(__file__).with_name("nfc_cards.json")

# レーザーに保存したアニメーション（laser/SEND_DATA の list_N）をカードに割り当てると、
# 再生中は CH4/CH5 をコマ送りで上書きする（laser/dmx_frames.py）。
ANIMATION_CHANNELS = (4, 5)

def validate_dmx_values(values, *, allow_short=False):
    if not isinstance(values, list):
        raise ValueError("DMX値はリストで指定してください")
    if allow_short and 1 <= len(values) < DMX_CHANNEL_COUNT:
        # 以前の登録データは未指定チャンネルを従来と同じ0で補完。
        values = values + [0] * (DMX_CHANNEL_COUNT - len(values))
    if len(values) != DMX_CHANNEL_COUNT:
        raise ValueError("DMX値はCH1～CH16の16個が必要です")
    for channel, value in enumerate(values, 1):
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError(f"CH{channel}: 0～255の整数が必要です（入力: {value!r}）")
    return values.copy()

def validate_animation(value):
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise ValueError(f"アニメーション番号は1以上の整数で指定してください（入力: {value!r}）")
    return value

def show_animation(info):
    number = info.get("animation")
    if number:
        print(f"  レーザーアニメーション: {number}（laser/SEND_DATA の {number} 番目のリスト。"
              f"CH4/CH5 はコマ送りで上書き）")

def show_dmx_values(values):
    values = validate_dmx_values(values)
    for channel, (label, value) in enumerate(zip(DMX_CHANNELS, values), 1):
        address = DMX_START_ADDRESS + channel - 1
        print(f"  CH{channel:02d} [DMX {address:03d}] {label}: {value}")

def load_cards():
    if not JSON_FILE.exists():
        return {}

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("JSONの形式が正しくありません")

    for uid, info in data.items():
        if not isinstance(info, dict) or not isinstance(info.get("name"), str):
            raise ValueError(f"カード {uid}: 名前の形式が正しくありません")
        try:
            info["dmx"] = validate_dmx_values(info.get("dmx"), allow_short=True)
            if "animation" in info:
                info["animation"] = validate_animation(info["animation"])
        except ValueError as e:
            raise ValueError(f"カード {uid}: {e}") from e
    return data

def save_cards(cards):
    temp_file = JSON_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            cards,
            f,
            ensure_ascii=False,
            indent=4
        )

    temp_file.replace(JSON_FILE)

def get_reader():
    try:
        from smartcard.System import readers
    except ImportError as e:
        raise RuntimeError("NFCリーダーを使う端末には pyscard が必要です") from e
    devices = readers()

    if not devices:
        raise RuntimeError(
            "PC/SC対応NFCリーダーが見つかりません"
        )

    print("\n検出されたリーダー:")

    for i, device in enumerate(devices):
        print(f"{i}: {device}")

    if len(devices) == 1:
        return devices[0]

    while True:
        try:
            index = int(input("使用するリーダー番号: "))
            return devices[index]
        except (ValueError, IndexError):
            print("正しい番号を入力してください")

def read_uid(reader):
    # pyscard はカードを離したとき、None ではなく NoCardException を返す。
    # 受信専用端末では pyscard が不要なので、ここで遅延インポートする。
    from smartcard.Exceptions import NoCardException

    connected = False

    try:
        connection = reader.createConnection()
        connection.connect()
        connected = True

        data, sw1, sw2 = connection.transmit(
            [0xFF, 0xCA, 0x00, 0x00, 0x00]
        )

        if (sw1, sw2) != (0x90, 0x00):
            return None

        return bytes(data).hex().upper()

    except NoCardException:
        return None

    finally:
        if connected:
            try:
                connection.disconnect()
            except Exception:
                pass

def wait_for_card(reader):
    print("\nカードをかざしてください...")
    print("Ctrl+Cでキャンセル")

    while True:
        try:
            uid = read_uid(reader)
            if uid:
                print("読み取りUID:", uid)
                return uid
        except Exception:
            pass

        time.sleep(READ_INTERVAL)

def wait_for_removal(reader):
    # 同じカードの連続登録を防ぐ
    print("カードを離してください...")

    while True:
        try:
            uid = read_uid(reader)
            if uid is None:
                break
        except Exception:
            break

        time.sleep(READ_INTERVAL)

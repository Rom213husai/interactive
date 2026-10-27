
import time
from smartcard.System import readers
from smartcard.Exceptions import CardConnectionException
import serial

# ===== 設定 =====

# USB-DMXインターフェースのCOMポート
DMX_PORT = "COM3"

# NFCタグUIDごとのDMXチャンネル値
# 例：1ch=動作モード、2ch=パターン番号
# ※実際の値はA1-B5のDMXチャンネル表に合わせて変更
TAG_ACTIONS = {
    "01234567": {1: 10, 2: 20},
    "89ABCDEF": {1: 10, 2: 80},
}

# 未登録タグを読み取ったときの値
DEFAULT_ACTION = {}

# ===== DMX送信 =====

class DMXController:
    def __init__(self, port):
        self.ser = serial.Serial(
            port=port,
            baudrate=57600,
            timeout=1
        )
        self.channels = [0] * 512

    def set_channels(self, values):
        self.channels = [0] * 512

        for channel, value in values.items():
            if not 1 <= channel <= 512:
                raise ValueError(
                    f"無効なDMXチャンネル: {channel}"
                )

            if not 0 <= value <= 255:
                raise ValueError(
                    f"無効なDMX値: {value}"
                )

            self.channels[channel - 1] = value

        self.send()

    def send(self):
        # ENTTEC DMX USB Pro互換プロトコル
        payload = bytes([0] + self.channels)
        length = len(payload)

        packet = (
            bytes([0x7E, 0x06])
            + bytes([length & 0xFF, length >> 8])
            + payload
            + bytes([0xE7])
        )

        self.ser.write(packet)

    def close(self):
        self.ser.close()


# ===== NFC読み取り =====

def read_uid(reader):
    connection = reader.createConnection()
    connection.connect()

    try:
        # PC/SCでUID取得に使われることが多いコマンド
        apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(apdu)

        if (sw1, sw2) != (0x90, 0x00):
            raise RuntimeError(
                f"UID取得失敗: SW={sw1:02X}{sw2:02X}"
            )

        return bytes(data).hex().upper()

    finally:
        connection.disconnect()


def main():
    available_readers = readers()

    if not available_readers:
        print("NFCリーダーが見つかりません")
        return

    print("検出されたリーダー:")
    for index, reader in enumerate(available_readers):
        print(f"{index}: {reader}")

    # 最初のリーダーを使用
    reader = available_readers[0]
    print("使用リーダー:", reader)

    dmx = DMXController(DMX_PORT)
    print("DMX接続:", DMX_PORT)
    print("NFCタグをかざしてください")

    last_uid = None

    try:
        while True:
            try:
                uid = read_uid(reader)

                if uid != last_uid:
                    print("NFCタグ検出:", uid)

                    action = TAG_ACTIONS.get(
                        uid, DEFAULT_ACTION
                    )

                    if action:
                        dmx.set_channels(action)
                        print("DMX送信:", action)
                    else:
                        print("登録されていないタグです")

                    last_uid = uid

            except CardConnectionException:
                # タグがない場合
                last_uid = None

            except Exception as e:
                # カード未検出や一時的な読み取りエラー
                last_uid = None
                if "UID取得失敗" in str(e):
                    print(e)

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n終了します")

    finally:
        dmx.close()


if __name__ == "__main__":
    main()


import time
from smartcard.System import readers

devices = readers()

if not devices:
    print("NFCリーダーが見つかりません")
    raise SystemExit

print("検出されたリーダー:")
for i, device in enumerate(devices):
    print(f"{i}: {device}")

reader = devices[0]
print("\n使用リーダー:", reader)
print("NFCタグをかざしてください。Ctrl+Cで終了します。")

last_uid = None

try:
    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            # タグのUIDを取得
            data, sw1, sw2 = connection.transmit(
                [0xFF, 0xCA, 0x00, 0x00, 0x00]
            )

            if (sw1, sw2) == (0x90, 0x00):
                uid = bytes(data).hex().upper()

                if uid != last_uid:
                    print("UID:", uid)
                    last_uid = uid

            connection.disconnect()

        except Exception:
            last_uid = None

        time.sleep(0.3)

except KeyboardInterrupt:
    print("\n終了しました")

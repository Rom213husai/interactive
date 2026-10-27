from PyDMXControl.controllers import SerialController
from PyDMXControl.profiles.Generic import Dimmer

# ==================================
# 設定
# ==================================
START_ADDRESS = 1
CHANNEL_COUNT = 16

# ==================================
# DMX初期化
# ==================================
dmx = SerialController("COM3")

fixtures = {}
values = {}

for ch in range(1, CHANNEL_COUNT + 1):
    address = START_ADDRESS + ch - 1

    fixtures[ch] = dmx.add_fixture(
        Dimmer,
        name=f"CH{ch}",
        start_channel=address
    )
    values[ch] = 0


def set_channel(ch, value):
    if not 1 <= ch <= CHANNEL_COUNT:
        print("無効なチャンネルです")
        return

    if not 0 <= value <= 255:
        print("値は0～255で指定してください")
        return

    # フェード時間0msで即時変更
    fixtures[ch].dim(value, 0)
    values[ch] = value

    print(f"CH{ch} = {value}")


def show_channels():
    print("\n--- DMX CHANNEL STATUS ---")

    for ch in range(1, CHANNEL_COUNT + 1):
        address = START_ADDRESS + ch - 1
        print(
            f"CH{ch:02d} "
            f"(Address {address:03d}) : "
            f"{values[ch]:3d}"
        )

    print("--------------------------\n")


def all_off():
    for ch in range(1, CHANNEL_COUNT + 1):
        fixtures[ch].dim(0, 0)
        values[ch] = 0

    print("全チャンネルを0にしました")


def show_help():
    print("""
========== DMX CONSOLE ==========

コマンド:

  CH VALUE
      チャンネルに値を設定
      例: 1 255

  CH=VALUE CH=VALUE ...
      複数チャンネルを一括設定
      例: 1=255 2=100 3=50

  list
      現在の値を表示

  off
      全チャンネルを0にする

  help
      ヘルプ表示

  exit
      終了

=================================
""")


# ==================================
# メインループ
# ==================================
try:
    show_help()

    while True:
        command = input("DMX> ").strip()

        if not command:
            continue

        if command.lower() in ("exit", "quit"):
            break

        if command.lower() == "help":
            show_help()
            continue

        if command.lower() == "list":
            show_channels()
            continue

        if command.lower() == "off":
            all_off()
            continue

        try:
            parts = command.split()

            # 複数チャンネル設定
            if all("=" in part for part in parts):
                updates = []

                for part in parts:
                    ch, value = map(int, part.split("="))

                    if not 1 <= ch <= CHANNEL_COUNT:
                        raise ValueError("無効なチャンネル")
                    if not 0 <= value <= 255:
                        raise ValueError("値は0～255")

                    updates.append((ch, value))

                for ch, value in updates:
                    set_channel(ch, value)

            # 単一チャンネル設定
            elif len(parts) == 2:
                ch = int(parts[0])
                value = int(parts[1])
                set_channel(ch, value)

            else:
                print("コマンド形式が不正です")

        except ValueError as e:
            print(f"入力エラー: {e}")

except KeyboardInterrupt:
    print("\n中断しました")

finally:
    all_off()
    dmx.close()
    print("DMXを終了しました")
"""NFC card registration, editing, listing and deletion."""

import argparse

if __package__:
    from .nfc_common import (
        DMX_CHANNELS,
        DMX_CHANNEL_COUNT,
        JSON_FILE,
        validate_dmx_values,
        validate_animation,
        show_dmx_values,
        show_animation,
        load_cards,
        save_cards,
        get_reader,
        wait_for_card,
        wait_for_removal,
    )
else:
    from nfc_common import (
        DMX_CHANNELS,
        DMX_CHANNEL_COUNT,
        JSON_FILE,
        validate_dmx_values,
        validate_animation,
        show_dmx_values,
        show_animation,
        load_cards,
        save_cards,
        get_reader,
        wait_for_card,
        wait_for_removal,
    )


def input_animation(current=None):
    print("\n===== レーザーアニメーション =====")
    print("laser/SEND_DATA の list_N に入れてレーザーへ保存したアニメーションを、番号Nで割り当てます。")
    print("割り当てると、再生中は CH4/CH5 をコマ送りで上書きします（色・回転などは上の値のまま）。")
    while True:
        raw = input(f"アニメーション番号 [現在値: {current or 'なし'} / Enterで維持 / 0でなし]: ").strip()
        if not raw:
            return current
        try:
            value = int(raw)
            return None if value == 0 else validate_animation(value)
        except ValueError:
            print("0以上の整数を入力してください")


def input_dmx_values(current_values=None):
    values = (
        [0] * DMX_CHANNEL_COUNT
        if current_values is None
        else validate_dmx_values(current_values)
    )
    print("\n===== 16チャンネル設定 =====")
    print("各値は0～255です。色・効果・停止などの値域は機器のDMX表で確認してください。")
    print("CH5のパターンはCH4のグループによって変わります。")
    show_dmx_values(values)
    while True:
        mode = input("入力方法: 1=個別設定 / 2=16個をカンマ区切り [1]: ").strip()
        if mode in ("", "1", "2"):
            break
        print("1または2を入力してください")
    if mode == "2":
        while True:
            raw = input("CH1～CH16の順に16個入力: ").strip()
            try:
                return validate_dmx_values([int(v.strip()) for v in raw.split(",")])
            except ValueError as e:
                print(f"入力エラー: {e}")
    for index, label in enumerate(DMX_CHANNELS):
        while True:
            raw = input(
                f"CH{index + 1:02d} {label} [現在値: {values[index]} / Enterで維持]: "
            ).strip()
            if not raw:
                break
            try:
                value = int(raw)
                if not 0 <= value <= 255:
                    raise ValueError
            except ValueError:
                print("0～255の整数を入力してください")
                continue
            values[index] = value
            break
    return validate_dmx_values(values)

def register_cards(reader, cards):
    print("\n===== カード登録モード =====")
    print("複数枚を連続して登録できます")

    while True:
        uid = wait_for_card(reader)

        if uid in cards:
            print("このカードは登録済みです")
            print("名前:", cards[uid]["name"])
            show_dmx_values(cards[uid]["dmx"])
            show_animation(cards[uid])

            answer = input(
                "設定を変更しますか？ (y/N): "
            ).strip().lower()

            if answer != "y":
                wait_for_removal(reader)
                continue

        name = input("カード名: ").strip()

        if not name:
            name = f"カード{len(cards) + 1}"

        current_values = cards[uid]["dmx"] if uid in cards else None
        values = input_dmx_values(current_values)
        animation = input_animation(cards[uid].get("animation") if uid in cards else None)

        cards[uid] = {
            "name": name,
            "dmx": values
        }
        if animation:
            cards[uid]["animation"] = animation

        save_cards(cards)

        print("\n登録しました！")
        print("UID:", uid)
        print("名前:", name)
        show_dmx_values(values)
        show_animation(cards[uid])
        print("保存先:", JSON_FILE)

        wait_for_removal(reader)

        answer = input(
            "\n次のカードを登録しますか？ (Y/n): "
        ).strip().lower()

        if answer == "n":
            break

def show_cards(cards):
    print("\n===== 登録カード一覧 =====")

    if not cards:
        print("登録カードはありません")
        return

    for i, (uid, info) in enumerate(cards.items(), 1):
        print(f"\n{i}. {info['name']}")
        print("   UID:", uid)
        show_dmx_values(info["dmx"])
        show_animation(info)

    print(f"\n合計: {len(cards)}枚")

def delete_card(cards):
    show_cards(cards)

    if not cards:
        return

    uid = input(
        "\n削除するカードのUID: "
    ).strip().upper()

    if uid not in cards:
        print("登録されていません")
        return

    print("削除対象:", cards[uid]["name"])

    if input("削除しますか？ (y/N): ").lower() == "y":
        del cards[uid]
        save_cards(cards)
        print("削除しました")


def main():
    parser = argparse.ArgumentParser(description="NFCカードの登録・編集・削除")
    parser.parse_args()
    try:
        cards = load_cards()
    except (OSError, ValueError) as e:
        print("カード設定の読み込み失敗:", e)
        return

    print("NFCカード登録 / 登録済み:", len(cards), "枚")
    while True:
        print("\n1. NFCカードを登録・編集")
        print("2. 登録カード一覧")
        print("3. カードを削除")
        print("0. 終了")
        try:
            choice = input("番号を入力: ").strip()
            if choice == "1":
                register_cards(get_reader(), cards)
            elif choice == "2":
                show_cards(cards)
            elif choice == "3":
                delete_card(cards)
            elif choice == "0":
                break
            else:
                print("正しい番号を入力してください")
        except KeyboardInterrupt:
            print("\nメニューに戻ります")
        except RuntimeError as e:
            print("NFC接続失敗:", e)


if __name__ == "__main__":
    main()

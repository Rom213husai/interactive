"""Direct, one-way TCP messages from the NFC terminal to the DMX terminal."""

import json

if __package__:
    from .nfc_common import validate_animation, validate_dmx_values
else:
    from nfc_common import validate_animation, validate_dmx_values


DEFAULT_PORT = 8765
MAX_LINE = 4096


def encode_card(uid, info, *, sync=False):
    """Send the card settings so the receiver needs no copy of nfc_cards.json."""
    message = {
        "version": 1,
        "type": "sync" if sync else "card",
        "uid": uid,
        "name": info["name"],
        "dmx": info["dmx"],
        "animation": info.get("animation"),
    }
    return _encode(message)


def encode_ping():
    return _encode({"version": 1, "type": "ping"})


def _encode(message):
    data = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_LINE:
        raise ValueError("送信メッセージが長すぎます")
    return data


def decode_message(line):
    """Return (kind, uid, card settings), or None for a heartbeat."""
    if len(line) > MAX_LINE or not line.endswith(b"\n"):
        raise ValueError("受信メッセージが長すぎるか途中で切れています")
    try:
        message = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("受信メッセージがJSONではありません") from e
    if not isinstance(message, dict) or message.get("version") != 1:
        raise ValueError("通信プロトコルのバージョンが異なります")
    kind = message.get("type")
    if kind == "ping":
        return None
    if kind not in ("card", "sync"):
        raise ValueError("不明なメッセージ種別です")
    uid, name = message.get("uid"), message.get("name")
    if not isinstance(uid, str) or not 1 <= len(uid) <= 128:
        raise ValueError("UIDの形式が正しくありません")
    if not isinstance(name, str) or not name:
        raise ValueError("カード名の形式が正しくありません")
    info = {"name": name, "dmx": validate_dmx_values(message.get("dmx"))}
    animation = validate_animation(message.get("animation"))
    if animation is not None:
        info["animation"] = animation
    return kind, uid, info

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
from flask import Flask, request, jsonify
import requests
import time
from datetime import datetime, timedelta

from basics_pb2 import (
    SelectedItems,
    LoadoutInfo,
    ChoosedEmotes,
    ChoosedEmote,
    RandomSlotInfo,
    QuickMsgSettings,
    QuickMsgModeSettings,
    PveSlotInfo,
    BlacklistInfoRes,
    ExternalIconInfo,
    EAccount_BanReason,
    ExternalIconStatus,
    ExternalIconShowType,
    SlotChooseType
)

from secret import key, iv

app = Flask(__name__)


def create_complete_player_activity(user_id):
    activity = SelectedItems()

    activity.avatar_id = 1001 + (user_id % 10)
    activity.skin_color = 2 + (user_id % 3)
    activity.clothes.extend([101, 102, 103, 104 + user_id % 5])
    activity.banner_id = 5001 + (user_id % 7)
    activity.head_pic = 2001 + (user_id % 4)

    for i in range(1, 4):
        loadout = activity.loadouts.add()
        loadout.loadout_id = i
        loadout.loadout_num = i
        loadout.is_free_play = (i % 2 == 0)

    activity.slots.extend([700 + i for i in range(5)])

    for i in range(1, 5):
        emote = ChoosedEmote()
        emote.slot_id = i
        emote.emote_id = 4000 + (user_id % 20) + i
        activity.emotes.emotes.append(emote)

    activity.shows.extend([800 + i for i in range(3)])
    activity.pve_primary_weapon_skin = 900 + (user_id % 10)
    activity.ranking_cards.extend([1000 + i for i in range(2)])
    activity.pin_id = 1100 + (user_id % 5)
    activity.game_bag_show = 1200 + (user_id % 3)

    for i in range(1, 3):
        random_slot = RandomSlotInfo()
        random_slot.slot = i
        random_slot.skin_ids.extend([500 + i * 10 + j for j in range(3)])
        random_slot.choose_type = SlotChooseType.SlotChooseType_RANDOM if i % 2 else SlotChooseType.SlotChooseType_SINGLE
        activity.random_slots.append(random_slot)

    activity.title = 300 + (user_id % 10)

    quick_msg = QuickMsgSettings()
    quick_msg.voice = 1 + (user_id % 3)
    for i in range(1, 3):
        mode_setting = QuickMsgModeSettings()
        mode_setting.mode = i
        mode_setting.list.extend([i * 10 + j for j in range(1, 4)])
        mode_setting.roulette.extend([i * 20 + j for j in range(1, 4)])
        quick_msg.mode_settings.append(mode_setting)

    activity.quick_msg_settings.CopyFrom(quick_msg)

    for i in range(1, 4):
        pve_slot = PveSlotInfo()
        pve_slot.index = i
        pve_slot.skin_id = 6000 + (user_id % 30) + i
        activity.pve_slots.append(pve_slot)

    activity.collection_actions.extend([1300 + i for i in range(4)])
    activity.collection_skill_skins.extend([1400 + i for i in range(5)])
    activity.load_out_v2 = 1500 + (user_id % 10)
    activity.final_shots.extend([1600 + i for i in range(3)])

    # Ban Info
    ban_info = BlacklistInfoRes()
    ban_status = user_id % 5  # Varies

    if ban_status == 0:
        ban_info.ban_reason = EAccount_BanReason.BAN_REASON_UNKNOWN
    elif ban_status == 1:
        ban_info.ban_reason = EAccount_BanReason.BAN_REASON_SKINMOD
    elif ban_status == 2:
        ban_info.ban_reason = EAccount_BanReason.BAN_REASON_IN_GAME_AUTO
    elif ban_status == 3:
        ban_info.ban_reason = EAccount_BanReason.BAN_REASON_REFUND
    else:
        ban_info.ban_reason = EAccount_BanReason.BAN_REASON_IN_GAME_AUTO_NEW

    ban_info.expire_duration = 0 if ban_status == 0 else 86400
    ban_info.ban_time = int(time.time()) - (3600 * 12 if ban_status else 0)

    # External Icon Info
    external_icon = ExternalIconInfo()
    external_icon.external_icon = f"icon_{user_id % 1000}"

    icon_status = user_id % 3
    if icon_status == 0:
        external_icon.status = ExternalIconStatus.ExternalIconStatus_NONE
    elif icon_status == 1:
        external_icon.status = ExternalIconStatus.ExternalIconStatus_NOT_IN_USE
    else:
        external_icon.status = ExternalIconStatus.ExternalIconStatus_IN_USE

    show_type = user_id % 3
    if show_type == 0:
        external_icon.show_type = ExternalIconShowType.ExternalIconShowType_NONE
    elif show_type == 1:
        external_icon.show_type = ExternalIconShowType.ExternalIconShowType_FRIEND
    else:
        external_icon.show_type = ExternalIconShowType.ExternalIconShowType_ALL

    return {
        "selected_items": activity,
        "ban_info": ban_info,
        "external_icon": external_icon
    }


def build_ban_json(uid, ban_info: BlacklistInfoRes):
    ban_reason_map = {
        0: "Unknown",
        1: "In-game auto detection",
        2: "Refund abuse",
        3: "Other reasons",
        4: "Skin modification",
        1014: "In-game auto detection (new)"
    }

    reason_code = ban_info.ban_reason
    ban_reason = ban_reason_map.get(reason_code, "Unknown")
    ban_time = ban_info.ban_time
    duration = ban_info.expire_duration

    if reason_code == 0:
        return {
            "uid": str(uid),
            "is_banned": False,
            "ban_info": None
        }

    ban_start = datetime.utcfromtimestamp(ban_time)
    ban_end = ban_start + timedelta(seconds=duration)
    return {
        "uid": str(uid),
        "is_banned": True,
        "ban_reason_code": reason_code,
        "ban_reason": ban_reason,
        "ban_time_unix": ban_time,
        "ban_time_utc": ban_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expire_duration_sec": duration,
        "expires_at_utc": ban_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ban_type": "Permanent" if duration == 0 else "Temporary"
    }


@app.route('/player-activity', methods=['GET'])
def player_activity():
    uid = request.args.get('uid')
    region = request.args.get('region')

    if not uid or not region:
        return jsonify({"error": "Missing 'uid' or 'region' query parameter"}), 400

    try:
        user_id = int(uid)
    except ValueError:
        return jsonify({"error": "Invalid UID"}), 400

    player_data = create_complete_player_activity(user_id)
    selected_items = player_data["selected_items"]
    ban_info = player_data["ban_info"]
    external_icon = player_data["external_icon"]

    response_data = {
        "uid": str(uid),
        "region": region.upper(),
        "is_banned": ban_info.ban_reason != 0,
        "ban_info": build_ban_json(uid, ban_info),
        "external_icon": {
            "external_icon": external_icon.external_icon,
            "status": ExternalIconStatus.Name(external_icon.status),
            "show_type": ExternalIconShowType.Name(external_icon.show_type)
        },
        "timestamp": int(time.time())
    }

    return jsonify(response_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
from flask import Flask, request, jsonify
import requests
import time
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
    """Create a complete player activity protobuf with ALL fields from basics.proto"""
    # Main container for player customization - SelectedItems
    activity = SelectedItems()
    
    # ===== SelectedItems Fields =====
    # Field 1: avatar_id (uint32)
    activity.avatar_id = 1001 + (user_id % 10)
    
    # Field 2: skin_color (uint32)
    activity.skin_color = 2 + (user_id % 3)
    
    # Field 3: clothes (repeated uint32)
    activity.clothes.extend([101, 102, 103, 104 + user_id % 5])
    
    # Field 4: loadouts (repeated LoadoutInfo)
    for i in range(1, 4):
        loadout = activity.loadouts.add()
        loadout.loadout_id = i
        loadout.loadout_num = i
        loadout.is_free_play = (i % 2 == 0)
    
    # Field 5: banner_id (uint32)
    activity.banner_id = 5001 + (user_id % 7)
    
    # Field 6: head_pic (uint32)
    activity.head_pic = 2001 + (user_id % 4)
    
    # Field 7: slots (repeated uint32)
    activity.slots.extend([700 + i for i in range(5)])
    
    # Field 8: emotes (ChoosedEmotes)
    for i in range(1, 5):
        emote = ChoosedEmote()
        emote.slot_id = i
        emote.emote_id = 4000 + (user_id % 20) + i
        activity.emotes.emotes.append(emote)
    
    # Field 9: shows (repeated uint32)
    activity.shows.extend([800 + i for i in range(3)])
    
    # Field 10: pve_primary_weapon_skin (uint32)
    activity.pve_primary_weapon_skin = 900 + (user_id % 10)
    
    # Field 11: ranking_cards (repeated uint32)
    activity.ranking_cards.extend([1000 + i for i in range(2)])
    
    # Field 12: pin_id (uint32)
    activity.pin_id = 1100 + (user_id % 5)
    
    # Field 13: game_bag_show (uint32)
    activity.game_bag_show = 1200 + (user_id % 3)
    
    # Field 14: random_slots (repeated RandomSlotInfo)
    for i in range(1, 3):
        random_slot = RandomSlotInfo()
        random_slot.slot = i
        random_slot.skin_ids.extend([500 + i*10 + j for j in range(3)])
        random_slot.choose_type = SlotChooseType.SlotChooseType_RANDOM if i % 2 else SlotChooseType.SlotChooseType_SINGLE
        activity.random_slots.append(random_slot)
    
    # Field 15: title (uint32)
    activity.title = 300 + (user_id % 10)
    
    # Field 16: quick_msg_settings (QuickMsgSettings)
    quick_msg = QuickMsgSettings()
    quick_msg.voice = 1 + (user_id % 3)
    
    for i in range(1, 3):
        mode_setting = QuickMsgModeSettings()
        mode_setting.mode = i
        mode_setting.list.extend([i*10 + j for j in range(1, 4)])
        mode_setting.roulette.extend([i*20 + j for j in range(1, 4)])
        quick_msg.mode_settings.append(mode_setting)
    
    activity.quick_msg_settings.CopyFrom(quick_msg)
    
    # Field 17: pve_slots (repeated PveSlotInfo)
    for i in range(1, 4):
        pve_slot = PveSlotInfo()
        pve_slot.index = i
        pve_slot.skin_id = 6000 + (user_id % 30) + i
        activity.pve_slots.append(pve_slot)
    
    # Field 18: collection_actions (repeated uint32)
    activity.collection_actions.extend([1300 + i for i in range(4)])
    
    # Field 19: collection_skill_skins (repeated uint32)
    activity.collection_skill_skins.extend([1400 + i for i in range(5)])
    
    # Field 20: load_out_v2 (uint32)
    activity.load_out_v2 = 1500 + (user_id % 10)
    
    # Field 21: final_shots (repeated uint32)
    activity.final_shots.extend([1600 + i for i in range(3)])
    
    # ===== Blacklist Info =====
    ban_info = BlacklistInfoRes()
    ban_status = user_id % 5  # Vary ban status based on user ID
    
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
    
    ban_info.expire_duration = 0 if ban_status == 0 else 86400  # 1 day if banned
    ban_info.ban_time = int(time.time()) - (3600 * 12 if ban_status else 0)
    
    # ===== External Icon Info =====
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

def protobuf_to_dict(message):
    """Convert any protobuf message to a dictionary with ALL fields"""
    if isinstance(message, SelectedItems):
        return {
            # Field 1: avatar_id
            "avatar_id": message.avatar_id,
            # Field 2: skin_color
            "skin_color": message.skin_color,
            # Field 3: clothes
            "clothes": list(message.clothes),
            # Field 4: loadouts
            "loadouts": [{
                "loadout_id": l.loadout_id,
                "loadout_num": l.loadout_num,
                "is_free_play": l.is_free_play
            } for l in message.loadouts],
            # Field 5: banner_id
            "banner_id": message.banner_id,
            # Field 6: head_pic
            "head_pic": message.head_pic,
            # Field 7: slots
            "slots": list(message.slots),
            # Field 8: emotes
            "emotes": [{
                "slot_id": e.slot_id,
                "emote_id": e.emote_id
            } for e in message.emotes.emotes],
            # Field 9: shows
            "shows": list(message.shows),
            # Field 10: pve_primary_weapon_skin
            "pve_primary_weapon_skin": message.pve_primary_weapon_skin,
            # Field 11: ranking_cards
            "ranking_cards": list(message.ranking_cards),
            # Field 12: pin_id
            "pin_id": message.pin_id,
            # Field 13: game_bag_show
            "game_bag_show": message.game_bag_show,
            # Field 14: random_slots
            "random_slots": [{
                "slot": r.slot,
                "skin_ids": list(r.skin_ids),
                "choose_type": SlotChooseType.Name(r.choose_type)
            } for r in message.random_slots],
            # Field 15: title
            "title": message.title,
            # Field 16: quick_msg_settings
            "quick_msg_settings": {
                "voice": message.quick_msg_settings.voice,
                "mode_settings": [{
                    "mode": m.mode,
                    "list": list(m.list),
                    "roulette": list(m.roulette)
                } for m in message.quick_msg_settings.mode_settings]
            },
            # Field 17: pve_slots
            "pve_slots": [{
                "index": p.index,
                "skin_id": p.skin_id
            } for p in message.pve_slots],
            # Field 18: collection_actions
            "collection_actions": list(message.collection_actions),
            # Field 19: collection_skill_skins
            "collection_skill_skins": list(message.collection_skill_skins),
            # Field 20: load_out_v2
            "load_out_v2": message.load_out_v2,
            # Field 21: final_shots
            "final_shots": list(message.final_shots)
        }
    elif isinstance(message, BlacklistInfoRes):
        return {
            "ban_reason": EAccount_BanReason.Name(message.ban_reason),
            "expire_duration": message.expire_duration,
            "ban_time": message.ban_time,
            "ban_reason_value": message.ban_reason  
        }
    elif isinstance(message, ExternalIconInfo):
        return {
            "external_icon": message.external_icon,
            "status": ExternalIconStatus.Name(message.status),
            "show_type": ExternalIconShowType.Name(message.show_type),
            "status_value": message.status,
            "show_type_value": message.show_type
        }
    return {}

@app.route('/player-activity', methods=['GET'])
def player_activity():
    """Comprehensive endpoint with ALL fields from basics.proto"""
    uid = request.args.get('uid')
    region = request.args.get('region')

    if not uid or not region:
        return jsonify({"error": "Missing 'uid' or 'region' query parameter"}), 400

    try:
        user_id = int(uid)
    except ValueError:
        return jsonify({"error": "Invalid UID"}), 400

    # Generate complete player data with ALL fields
    player_data = create_complete_player_activity(user_id)
    
    # Convert all protobuf messages to dictionaries
    response_data = {
        "user_id": user_id,
        "region": region.upper(),
        "selected_items": protobuf_to_dict(player_data["selected_items"]),
        "ban_info": protobuf_to_dict(player_data["ban_info"]),
        "external_icon": protobuf_to_dict(player_data["external_icon"]),
        "timestamp": int(time.time()),
        "credit": "@Ujjaiwal",
        "metadata": {
            "proto_version": "basics.proto",
            "fields_included": "ALL (1-21 from SelectedItems + BlacklistInfoRes + ExternalIconInfo)",
            "enum_values_included": True
        }
    }

    return jsonify(response_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
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
    # Basic appearance (fields 1-6)
    activity.avatar_id = 1001 + (user_id % 10)
    activity.skin_color = 2 + (user_id % 3)
    activity.clothes.extend([101, 102, 103, 104 + user_id % 5])
    activity.banner_id = 5001 + (user_id % 7)
    activity.head_pic = 2001 + (user_id % 4)
    
    # Loadouts (field 4 - repeated LoadoutInfo)
    for i in range(1, 4):
        loadout = activity.loadouts.add()
        loadout.loadout_id = i
        loadout.loadout_num = i
        loadout.is_free_play = (i % 2 == 0)
    
    # Slots (field 7 - repeated uint32)
    activity.slots.extend([700 + i for i in range(5)])
    
    # Emotes (field 8 - ChoosedEmotes)
    for i in range(1, 5):
        emote = ChoosedEmote()
        emote.slot_id = i
        emote.emote_id = 4000 + (user_id % 20) + i
        activity.emotes.emotes.append(emote)
    
    # Shows (field 9 - repeated uint32)
    activity.shows.extend([800 + i for i in range(3)])
    
    # PVE weapon skin (field 10)
    activity.pve_primary_weapon_skin = 900 + (user_id % 10)
    
    # Ranking cards (field 11 - repeated uint32)
    activity.ranking_cards.extend([1000 + i for i in range(2)])
    
    # Pin ID (field 12)
    activity.pin_id = 1100 + (user_id % 5)
    
    # Game bag show (field 13)
    activity.game_bag_show = 1200 + (user_id % 3)
    
    # Random slots (field 14 - repeated RandomSlotInfo)
    for i in range(1, 3):
        random_slot = RandomSlotInfo()
        random_slot.slot = i
        random_slot.skin_ids.extend([500 + i*10 + j for j in range(3)])
        random_slot.choose_type = SlotChooseType.SlotChooseType_RANDOM if i % 2 else SlotChooseType.SlotChooseType_SINGLE
        activity.random_slots.append(random_slot)
    
    # Title (field 15)
    activity.title = 300 + (user_id % 10)
    
    # Quick message settings (field 16 - QuickMsgSettings)
    quick_msg = QuickMsgSettings()
    quick_msg.voice = 1 + (user_id % 3)
    
    for i in range(1, 3):
        mode_setting = QuickMsgModeSettings()
        mode_setting.mode = i
        mode_setting.list.extend([i*10 + j for j in range(1, 4)])
        mode_setting.roulette.extend([i*20 + j for j in range(1, 4)])
        quick_msg.mode_settings.append(mode_setting)
    
    activity.quick_msg_settings.CopyFrom(quick_msg)
    
    # PVE slots (field 17 - repeated PveSlotInfo)
    for i in range(1, 4):
        pve_slot = PveSlotInfo()
        pve_slot.index = i
        pve_slot.skin_id = 6000 + (user_id % 30) + i
        activity.pve_slots.append(pve_slot)
    
    # Collection actions (field 18 - repeated uint32)
    activity.collection_actions.extend([1300 + i for i in range(4)])
    
    # Collection skill skins (field 19 - repeated uint32)
    activity.collection_skill_skins.extend([1400 + i for i in range(5)])
    
    # Loadout v2 (field 20)
    activity.load_out_v2 = 1500 + (user_id % 10)
    
    # Final shots (field 21 - repeated uint32)
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
            # Field 1-6: Basic appearance
            "avatar_id": message.avatar_id,
            "skin_color": message.skin_color,
            "clothes": list(message.clothes),
            "banner_id": message.banner_id,
            "head_pic": message.head_pic,
            
            # Field 4: Loadouts
            "loadouts": [{
                "loadout_id": l.loadout_id,
                "loadout_num": l.loadout_num,
                "is_free_play": l.is_free_play
            } for l in message.loadouts],
            
            # Field 7: Slots
            "slots": list(message.slots),
            
            # Field 8: Emotes
            "emotes": [{
                "slot_id": e.slot_id,
                "emote_id": e.emote_id
            } for e in message.emotes.emotes],
            
            # Field 9: Shows
            "shows": list(message.shows),
            
            # Field 10: PVE weapon skin
            "pve_primary_weapon_skin": message.pve_primary_weapon_skin,
            
            # Field 11: Ranking cards
            "ranking_cards": list(message.ranking_cards),
            
            # Field 12: Pin ID
            "pin_id": message.pin_id,
            
            # Field 13: Game bag show
            "game_bag_show": message.game_bag_show,
            
            # Field 14: Random slots
            "random_slots": [{
                "slot": r.slot,
                "skin_ids": list(r.skin_ids),
                "choose_type": SlotChooseType.Name(r.choose_type)
            } for r in message.random_slots],
            
            # Field 15: Title
            "title": message.title,
            
            # Field 16: Quick message settings
            "quick_msg_settings": {
                "voice": message.quick_msg_settings.voice,
                "mode_settings": [{
                    "mode": m.mode,
                    "list": list(m.list),
                    "roulette": list(m.roulette)
                } for m in message.quick_msg_settings.mode_settings]
            },
            
            # Field 17: PVE slots
            "pve_slots": [{
                "index": p.index,
                "skin_id": p.skin_id
            } for p in message.pve_slots],
            
            # Field 18: Collection actions
            "collection_actions": list(message.collection_actions),
            
            # Field 19: Collection skill skins
            "collection_skill_skins": list(message.collection_skill_skins),
            
            # Field 20: Loadout v2
            "load_out_v2": message.load_out_v2,
            
            # Field 21: Final shots
            "final_shots": list(message.final_shots)
        }
    elif isinstance(message, BlacklistInfoRes):
        return {
            # All BlacklistInfoRes fields
            "ban_reason": EAccount_BanReason.Name(message.ban_reason),
            "expire_duration": message.expire_duration,
            "ban_time": message.ban_time,
            # Include enum value for programmatic use
            "ban_reason_value": message.ban_reason  
        }
    elif isinstance(message, ExternalIconInfo):
        return {
            # All ExternalIconInfo fields
            "external_icon": message.external_icon,
            "status": ExternalIconStatus.Name(message.status),
            "show_type": ExternalIconShowType.Name(message.show_type),
            # Include enum values for programmatic use
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
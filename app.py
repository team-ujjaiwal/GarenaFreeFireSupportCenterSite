from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
from flask import Flask, request, jsonify
import requests
import uid_generator_pb2
import basics_pb2
from secret import key, iv
from datetime import datetime

app = Flask(__name__)

def hex_to_bytes(hex_string):
    return bytes.fromhex(hex_string)

def create_protobuf(akiru_, aditya):
    message = uid_generator_pb2.uid_generator()
    message.akiru_ = akiru_
    message.aditya = aditya
    return message.SerializeToString()

def protobuf_to_hex(protobuf_data):
    return binascii.hexlify(protobuf_data).decode()

def decode_hex(hex_string):
    byte_data = binascii.unhexlify(hex_string.replace(' ', ''))
    users = basics_pb2.CSGetPlayerPersonalShowRes()
    users.ParseFromString(byte_data)
    return users

def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def get_jwt_token(region):
    jwt_url = "https://ffmconnectlivegopgarenanowcom.vercel.app/token"
    response = requests.get(jwt_url)
    if response.status_code != 200:
        return None
    
    region = region.upper()
    for token_info in response.json():
        if region == "IND" and "IND" in token_info["region"]:
            return token_info
        elif region in ["NA", "BR", "SAC", "US"] and any(r in token_info["region"] for r in ["NA", "BR", "SAC", "US"]):
            return token_info
        elif region in ["SG", "ID", "VN", "TH", "TW", "ME", "PK", "RU", "CIS", "BD", "EUROPE"] and any(r in token_info["region"] for r in ["SG", "ID", "VN", "TH", "TW", "ME", "PK", "RU", "CIS", "BD", "EUROPE"]):
            return token_info
    
    return None

@app.route('/checkban', methods=['GET'])
def main():
    uid = request.args.get('uid')
    region = request.args.get('region')

    if not uid or not region:
        return jsonify({"error": "Missing 'uid' or 'region' query parameter"}), 400

    try:
        saturn_ = int(uid)
    except ValueError:
        return jsonify({"error": "Invalid UID"}), 400

    jwt_info = get_jwt_token(region)
    if not jwt_info or 'token' not in jwt_info:
        return jsonify({"error": "Failed to fetch JWT token"}), 500

    api = jwt_info['serverUrl']
    token = jwt_info['token']

    protobuf_data = create_protobuf(saturn_, 1)
    hex_data = protobuf_to_hex(protobuf_data)
    encrypted_hex = encrypt_aes(hex_data, key, iv)

    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB49',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(f"{api}/GetPlayerPersonalShow", headers=headers, data=bytes.fromhex(encrypted_hex))
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Failed to contact game server"}), 502

    hex_response = response.content.hex()

    try:
        users = decode_hex(hex_response)
    except Exception as e:
        return jsonify({"error": f"Failed to parse Protobuf: {str(e)}"}), 500

    result = {
        "uid": uid,
        "is_banned": False,
        "ban_reason_code": 0,
        "ban_reason": "",
        "ban_time_unix": 0,
        "ban_time_utc": "",
        "expire_duration_sec": 0,
        "expires_at_utc": "",
        "ban_type": ""
    }

    # Check if user has ban information in the response
    if hasattr(users, 'blacklist_info'):
        ban_info = users.blacklist_info
        result.update({
            "is_banned": True,
            "ban_reason_code": ban_info.ban_reason,
            "ban_reason": basics_pb2.EAccount_BanReason.Name(ban_info.ban_reason),
            "ban_time_unix": ban_info.ban_time,
            "ban_time_utc": datetime.utcfromtimestamp(ban_info.ban_time).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "expire_duration_sec": ban_info.expire_duration,
            "expires_at_utc": datetime.utcfromtimestamp(ban_info.ban_time + ban_info.expire_duration).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "ban_type": "Temporary" if ban_info.expire_duration > 0 else "Permanent"
        })

    if users.players:
        result['players'] = []
        for p in users.players:
            player_data = {
                'user_id': p.user_id,
                'username': p.username,
                'level': p.level,
                'rank': p.rank,
                'last_login': p.last_login,
                'country_code': p.country_code,
                'avatar': p.avatar,
                'banner': p.banner,
                'game_version': p.game_version,
                'is_online': p.is_online,
                'in_match': p.in_match
            }
            
            if p.HasField("clan_tag"):
                player_data['clan_tag'] = p.clan_tag.tag_display
            
            if p.HasField("premium"):
                player_data['premium_level'] = p.premium.premium_level
            
            result['players'].append(player_data)

    if users.HasField("clan"):
        result["clan"] = {
            "clan_name": users.clan.clan_name,
            "clan_level": users.clan.clan_level,
            "clan_xp": users.clan.clan_xp,
            "clan_xp_required": users.clan.clan_xp_required
        }

    if users.HasField("inventory"):
        result["inventory"] = {
            "inventory_id": users.inventory.inventory_id,
            "capacity": users.inventory.capacity,
            "version": users.inventory.version,
            "is_equipped": users.inventory.is_equipped,
            "last_update": users.inventory.last_update,
            "item_count": len(users.inventory.items)
        }

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
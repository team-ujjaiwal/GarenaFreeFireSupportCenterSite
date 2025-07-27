from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
import random
from datetime import datetime, timedelta

from basics_pb2 import BlacklistInfoRes, EAccount_BanReason
import uid_generator_pb2
from secret import key, iv

app = Flask(__name__)

def hex_to_bytes(hex_string):
    return bytes.fromhex(hex_string)

def create_protobuf(uid, aditya=2):  # aditya=2 for bancheck
    message = uid_generator_pb2.uid_generator()
    message.akiru_ = uid
    message.aditya = aditya
    return message.SerializeToString()

def protobuf_to_hex(protobuf_data):
    return binascii.hexlify(protobuf_data).decode()

def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def get_credentials(region):
    region = region.upper()
    if region == "IND":
        return "3942040791", "EDD92B8948F4453F544C9432DFB4996D02B4054379A0EE083D8459737C50800B"
    else:
        return "uid", "password"

def get_jwt_token(region):
    uid, password = get_credentials(region)
    jwt_url = f"https://jwt-aditya.vercel.app/token?uid={uid}&password={password}"
    response = requests.get(jwt_url)
    if response.status_code != 200:
        return None
    return response.json()

@app.route('/checkbanned', methods=['GET'])
def check_banned():
    uid = request.args.get('uid')
    region = request.args.get('region', 'IND')

    if not uid:
        return jsonify({"error": "Missing 'uid' query parameter"}), 400

    try:
        uid_int = int(uid)
    except ValueError:
        return jsonify({"error": "Invalid UID"}), 400

    jwt_info = get_jwt_token(region)
    if not jwt_info or 'token' not in jwt_info:
        return jsonify({"error": "Failed to fetch JWT token"}), 500

    api = jwt_info['serverUrl']
    token = jwt_info['token']

    protobuf_data = create_protobuf(uid_int, 2)  # 2 for bancheck
    hex_data = protobuf_to_hex(protobuf_data)
    encrypted_hex = encrypt_aes(hex_data, key, iv)

    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'ReleaseVersion': 'OB49',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(f"{api}/CheckBlacklistInfo", headers=headers, data=bytes.fromhex(encrypted_hex))
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Failed to contact game server"}), 502

    hex_response = response.content.hex()

    try:
        ban_info = BlacklistInfoRes()
        ban_info.ParseFromString(bytes.fromhex(hex_response))
    except Exception as e:
        return jsonify({"error": f"Failed to parse ban info: {str(e)}"}), 500

    # Map reason
    reason_map = {
        0: "Unknown",
        1: "In-game auto detection",
        2: "Refund abuse",
        3: "Other reasons",
        4: "Skin modification",
        246: "In-game auto detection (new)"
    }

    ban_reason_code = ban_info.ban_reason
    ban_reason = reason_map.get(ban_reason_code, "Unrecognized")

    ban_time = datetime.utcfromtimestamp(ban_info.ban_time)
    expires_at = ban_time + timedelta(seconds=ban_info.expire_duration)

    ban_type = "Permanent" if ban_info.expire_duration == 0 else "Temporary"

    result = {
        "uid": uid,
        "is_banned": True,
        "ban_reason_code": ban_reason_code,
        "ban_reason": ban_reason,
        "ban_time_unix": ban_info.ban_time,
        "ban_time_utc": ban_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expire_duration_sec": ban_info.expire_duration,
        "expires_at_utc": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ban_type": ban_type
    }

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
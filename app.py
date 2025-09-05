from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
from flask import Flask, request, jsonify
import requests
import random
import uid_generator_pb2
#from response_pb2 import ServerResponse  # For parsing server response
from GETUserCheck_pb2 import UserProfile  # For the desired output format
from secret import key, iv
import time
from datetime import datetime, timedelta

app = Flask(__name__)

def hex_to_bytes(hex_string):
    return bytes.fromhex(hex_string)

def create_protobuf(ujjaiwal_, garena):
    message = uid_generator_pb2.uid_generator()
    message.ujjaiwal_ = ujjaiwal_
    message.garena = garena
    return message.SerializeToString()

def protobuf_to_hex(protobuf_data):
    return binascii.hexlify(protobuf_data).decode()

def decode_hex(hex_string):
    byte_data = binascii.unhexlify(hex_string.replace(' ', ''))
    server_response = ServerResponse()
    server_response.ParseFromString(byte_data)
    return server_response

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
        return "3943735419", "D00171F210873075DE973C7E40936D8A56A9E5FD4DFA7F2A2CE1ED07759F9DB6"
    elif region in ["NA", "BR", "SAC", "US"]:
        return "3943737998", "92EB4C721DB698B17C1BF61F8F7ECDEC55D814FB35ADA778FA5EE1DC0AEAEDFF"
    else:
        return "3943739516", "BFA0A0D9DF6D4EE1AA92354746475A429D775BCA4D8DD822ECBC6D0BF7B51886"

def get_jwt_token(region):
    uid, password = get_credentials(region)
    jwt_url = f"https://100067.vercel.app/token?uid={uid}&password={password}"
    response = requests.get(jwt_url)
    if response.status_code != 200:
        return None
    return response.json()

def generate_ban_info(level):
    """Generate realistic ban information based on user level"""
    # Higher level users are less likely to be banned
    is_banned = random.random() < (0.3 if level < 10 else 0.1)
    
    if not is_banned:
        return {
            'is_banned': False,
            'ban_reason': '',
            'ban_period': '',
            'ban_status': 'Not Banned',
            'ban_type': 'None'
        }
    
    ban_reasons = [
        "In-game auto detection (new)",
        "Violation of terms of service",
        "Suspicious activity detected",
        "Reported by multiple players",
        "Unauthorized software usage"
    ]
    
    ban_types = ["Temporary", "Permanent"]
    ban_duration = random.randint(30, 365*7)  # 30 days to 7 years
    
    ban_date = datetime.now() - timedelta(days=random.randint(1, 365))
    
    years = ban_duration // 365
    months = (ban_duration % 365) // 30
    days = (ban_duration % 365) % 30
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)
    seconds = random.randint(0, 59)
    
    return {
        'is_banned': True,
        'ban_reason': random.choice(ban_reasons),
        'ban_period': f"{years} years {months} months {days} days {hours:02d}:{minutes:02d}:{seconds:02d}",
        'ban_status': f"Banned in {ban_date.strftime('%d %B %Y at %H:%M:%S')}",
        'ban_type': random.choice(ban_types)
    }

@app.route('/check', methods=['GET'])
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
        'ReleaseVersion': 'OB50',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(f"{api}/GetPlayerPersonalShow", headers=headers, data=bytes.fromhex(encrypted_hex))
        response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to contact game server: {str(e)}"}), 502

    hex_response = response.content.hex()

    try:
        server_response = decode_hex(hex_response)
        
        if not server_response.basicinfo:
            return jsonify({"error": "No user data found"}), 404
            
        user_info = server_response.basicinfo[0]
        
        # Generate ban information
        ban_info = generate_ban_info(user_info.level)
        
        # Create UserProfile format response
        result = {
            'uid': uid,
            'is_banned': ban_info['is_banned'],
            'ban_reason': ban_info['ban_reason'],
            'ban_period': ban_info['ban_period'],
            'ban_status': ban_info['ban_status'],
            'ban_type': ban_info['ban_type'],
            'level': str(user_info.level),
            'exp': str(user_info.Exp) if hasattr(user_info, 'Exp') else "0",
            'liked': str(user_info.likes) if hasattr(user_info, 'likes') else "0",
            'nickname': user_info.username,
            'region': user_info.region,
            'credit': '@Ujjaiwal'
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to parse response: {str(e)}",
            "response_preview": hex_response[:100] + "..." if len(hex_response) > 100 else hex_response
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
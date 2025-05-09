import time
import datetime
from datetime import UTC
import hashlib
import secrets
import json
import signal
import sys
import jwt
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from threading import Thread, Event
from functools import wraps

app = Flask(__name__)
# Configure CORS to allow credentials and specific headers
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5000", "http://127.0.0.1:5000", "http://192.168.0.209:5000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
app.config['SECRET_KEY'] = 'Summer1!'  # Change this to a secure secret key

# User database structure
USERS_FILE = 'users.json'

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Initialize with default user
        default_users = {
            'cs121287': {
                'password': hashlib.sha256('your-password-here'.encode()).hexdigest(),
                'created_at': '2025-05-09 08:52:59'
            }
        }
        save_users(default_users)
        return default_users

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

USERS = load_users()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            return jsonify({'message': 'Preflight request allowed'}), 200

        # Get token from header
        token = None
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'message': 'Token is missing'}), 401

        try:
            # Split the header and verify it starts with 'Bearer'
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({'message': 'Invalid token format'}), 401
            
            token = parts[1]

            # Decode and verify the token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['username']

            # Check if user still exists
            if current_user not in USERS:
                return jsonify({'message': 'User no longer exists'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'message': f'Token validation error: {str(e)}'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

class CoinFlip:
    def __init__(self):
        self.history = []
        self.max_history = 10
        self.stats = {
            "heads": 0,
            "tails": 0
        }
        self.stop_event = Event()
        self.load_history()

    def generate_seed(self):
        """Generate a cryptographically secure random seed"""
        try:
            return '-'.join([secrets.token_hex(4) for _ in range(4)])
        except Exception as e:
            print(f"Error generating seed: {e}")
            return None

    def hash_seed(self, seed):
        """Generate SHA-256 hash of the seed"""
        try:
            return hashlib.sha256(seed.encode()).hexdigest()
        except Exception as e:
            print(f"Error hashing seed: {e}")
            return None

    def get_next_flip_time(self):
        """Get the timestamp of the next flip (start of next minute)"""
        try:
            now = datetime.datetime.now(UTC)
            next_minute = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
            return next_minute
        except Exception as e:
            print(f"Error calculating next flip time: {e}")
            return None

    def format_datetime(self, dt):
        """Format datetime in YYYY-MM-DD HH:MM:SS format"""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def flip_coin(self):
        """Perform a coin flip and update history"""
        try:
            seed = self.generate_seed()
            if not seed:
                return None

            hash_value = self.hash_seed(seed)
            if not hash_value:
                return None

            result = "Heads" if int(hash_value[0], 16) & 1 == 0 else "Tails"
            
            flip_time = self.format_datetime(datetime.datetime.now(UTC))
            
            flip_data = {
                "time": flip_time,
                "result": result,
                "seed": seed,
                "hash": hash_value
            }
            
            # Update history with thread safety
            with app.app_context():
                self.history.insert(0, flip_data)
                if len(self.history) > self.max_history:
                    self.history.pop()
                
                self.update_stats()
                self.save_history()
            
            return flip_data
        except Exception as e:
            print(f"Error in flip_coin: {e}")
            return None

    def update_stats(self):
        """Update heads/tails statistics"""
        try:
            self.stats = {"heads": 0, "tails": 0}
            for flip in self.history:
                if flip["result"] == "Heads":
                    self.stats["heads"] += 1
                else:
                    self.stats["tails"] += 1
        except Exception as e:
            print(f"Error updating stats: {e}")

    def save_history(self):
        """Save history to a file with error handling"""
        try:
            data = {
                "history": self.history,
                "stats": self.stats,
                "last_save": self.format_datetime(datetime.datetime.now(UTC))
            }
            with open("flip_history.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def load_history(self):
        """Load history from file with error handling"""
        try:
            with open("flip_history.json", "r") as f:
                data = json.load(f)
                self.history = data["history"]
                self.stats = data["stats"]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"No history file found or invalid format: {e}")
        except Exception as e:
            print(f"Error loading history: {e}")

    def cleanup(self):
        """Cleanup resources"""
        self.stop_event.set()
        self.save_history()

coin_flipper = CoinFlip()

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight request allowed'}), 200

    auth = request.authorization
    
    if not auth or not auth.username or not auth.password:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})
    
    if auth.username not in USERS:
        return make_response('Invalid credentials', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})
    
    if USERS[auth.username]['password'] == hashlib.sha256(auth.password.encode()).hexdigest():
        token = jwt.encode({
            'username': auth.username,
            'exp': datetime.datetime.now(UTC) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'])
        
        response = jsonify({
            'token': token,
            'username': auth.username,
            'created_at': USERS[auth.username]['created_at']
        })
        return response
    
    return make_response('Invalid credentials', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})

@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight request allowed'}), 200

    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing required fields'}), 400
    
    username = data['username']
    password = data['password']
    
    # Validate username (alphanumeric only)
    if not username.isalnum():
        return jsonify({'message': 'Username must be alphanumeric'}), 400
    
    # Check if username already exists
    if username in USERS:
        return jsonify({'message': 'Username already exists'}), 409
    
    # Create new user
    USERS[username] = {
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'created_at': datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Save updated users
    save_users(USERS)
    
    # Generate token
    token = jwt.encode({
        'username': username,
        'exp': datetime.datetime.now(UTC) + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'])
    
    response = jsonify({
        'token': token,
        'username': username,
        'created_at': USERS[username]['created_at']
    })
    return response, 201

@app.route('/api/status', methods=['GET', 'OPTIONS'])
@token_required
def get_status(current_user):
    """Get current status including time, next flip, history, and stats"""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight request allowed'}), 200

    try:
        current_time = datetime.datetime.now(UTC)
        next_flip = coin_flipper.get_next_flip_time()
        
        if not next_flip:
            return jsonify({"error": "Could not calculate next flip time"}), 500
            
        seconds_until_flip = int((next_flip - current_time).total_seconds())
        
        total_flips = coin_flipper.stats["heads"] + coin_flipper.stats["tails"]
        heads_percent = (coin_flipper.stats["heads"] / total_flips * 100) if total_flips > 0 else 0
        tails_percent = (coin_flipper.stats["tails"] / total_flips * 100) if total_flips > 0 else 0
        
        return jsonify({
            "current_time": coin_flipper.format_datetime(current_time),
            "seconds_until_flip": seconds_until_flip,
            "history": coin_flipper.history,
            "stats": {
                "heads": coin_flipper.stats["heads"],
                "tails": coin_flipper.stats["tails"],
                "heads_percent": round(heads_percent, 1),
                "tails_percent": round(tails_percent, 1)
            },
            "user": current_user
        })
    except Exception as e:
        print(f"Error in get_status: {e}")
        return jsonify({"error": "Internal server error"}), 500

def run_flip_scheduler():
    """Background task to perform flips on schedule"""
    while not coin_flipper.stop_event.is_set():
        try:
            current_time = datetime.datetime.now(UTC)
            if current_time.second == 0:
                coin_flipper.flip_coin()
            time.sleep(1)
        except Exception as e:
            print(f"Error in flip scheduler: {e}")
            time.sleep(1)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("Shutting down gracefully...")
    coin_flipper.cleanup()
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start flip scheduler in a daemon thread
    flip_thread = Thread(target=run_flip_scheduler, daemon=True)
    flip_thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"Error starting server: {e}")
    finally:
        coin_flipper.cleanup()
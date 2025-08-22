from flask import Flask, render_template, request, redirect, url_for, jsonify
import datetime
import os
import traceback
import random
import requests
import json
import uuid
import qrcode
import io
import base64
from collections import Counter

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load word lists at startup
WORD_LIST = []
ANSWER_LIST = []

# Upstash Redis configuration
UPSTASH_REDIS_URL = "https://ample-chamois-15026.upstash.io"
UPSTASH_REDIS_TOKEN = "ATqyAAIjcDFhZjU5NjI5NDdhZjA0ZDE5YjIwM2RiMTNjM2Q5M2VjN7AxMA"

# In-memory storage as fallback
GAMES_STORAGE = {}
REDEMPTION_STORAGE = {}

# Puzzle system variables
LETTER_PUZZLES = []
EXPANDED_GAMES = []  # Will hold all possible games from all puzzles
CURRENT_GAME_INDEX = 0

def load_word_list(file_path='words.txt'):
    try:
        with open(file_path, 'r') as f:
            words = [line.strip().upper() for line in f if len(line.strip()) == 5 and line.strip().isalpha()]
            print(f"Loaded {len(words)} valid words from {file_path}")
            return words
    except FileNotFoundError:
        print(f"ERROR: {file_path} not found!")
        return []
    except Exception as e:
        print(f"ERROR loading {file_path}: {str(e)}")
        return []

def load_answers(file_path='answers.txt'):
    try:
        with open(file_path, 'r') as f:
            answers = [line.strip().upper() for line in f if len(line.strip()) == 5 and line.strip().isalpha()]
            print(f"Loaded {len(answers)} answer words from {file_path}")
            return answers
    except FileNotFoundError:
        print(f"ERROR: {file_path} not found!")
        return []
    except Exception as e:
        print(f"ERROR loading {file_path}: {str(e)}")
        return []

def load_letter_puzzles(file_path='letter_puzzles.txt'):
    """Load letter puzzles from text file"""
    puzzles = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                try:
                    # Parse format: FEATURED_LETTER|ANSWER|AVAILABLE_LETTERS
                    parts = line.split('|')
                    if len(parts) != 3:
                        print(f"WARNING: Invalid format on line {line_num}: {line}")
                        continue
                    
                    featured_letter = parts[0].strip().upper()
                    answer = parts[1].strip().upper()
                    available_letters = [letter.strip().upper() for letter in parts[2].split(',')]
                    
                    # Basic validation
                    if len(answer) != 5 or len(available_letters) != 12:
                        print(f"WARNING: Invalid puzzle format on line {line_num}")
                        continue
                    
                    puzzle = {
                        "available_letters": available_letters,
                        "featured_letter": featured_letter,
                        "answer": answer
                    }
                    puzzles.append(puzzle)
                    
                except Exception as e:
                    print(f"ERROR parsing line {line_num}: {line} - {str(e)}")
                    continue
        
        print(f"Loaded {len(puzzles)} base puzzles from {file_path}")
        return puzzles
        
    except FileNotFoundError:
        print(f"ERROR: {file_path} not found!")
        return []
    except Exception as e:
        print(f"ERROR loading puzzles: {str(e)}")
        return []

def can_make_word_from_letters(word, available_letters):
    """Check if word can be made from available letters"""
    available_count = Counter(available_letters)
    word_count = Counter(word.upper())
    
    for letter, needed in word_count.items():
        if available_count.get(letter, 0) < needed:
            return False
    return True

def expand_puzzles_to_all_answers():
    """Convert each puzzle into multiple games - one for each valid answer"""
    global EXPANDED_GAMES
    
    if not LETTER_PUZZLES or not WORD_LIST:
        print("ERROR: Puzzles or word list not loaded!")
        return
    
    EXPANDED_GAMES = []
    
    print("Expanding puzzles to find all valid answers...")
    
    for puzzle_num, puzzle in enumerate(LETTER_PUZZLES, 1):
        featured_letter = puzzle['featured_letter']
        available_letters = puzzle['available_letters']
        original_answer = puzzle['answer']
        
        # Find ALL valid words that can be made with featured letter
        valid_answers = []
        
        for word in WORD_LIST:
            word = word.upper()
            # Must use featured letter and be makeable from available letters
            if (featured_letter in word and 
                can_make_word_from_letters(word, available_letters)):
                valid_answers.append(word)
        
        # Create a game for each valid answer
        for answer_num, answer in enumerate(valid_answers, 1):
            game = {
                'puzzle_number': puzzle_num,
                'answer_number': answer_num,
                'total_answers_in_puzzle': len(valid_answers),
                'featured_letter': featured_letter,
                'available_letters': available_letters,
                'answer': answer,
                'original_answer': original_answer  # Keep track of original
            }
            EXPANDED_GAMES.append(game)
        
        print(f"Puzzle {puzzle_num}: Found {len(valid_answers)} valid answers")
        if len(valid_answers) > 0:
            print(f"  Featured '{featured_letter}': {', '.join(valid_answers[:5])}{'...' if len(valid_answers) > 5 else ''}")
    
    print(f"\n✅ EXPANDED TO {len(EXPANDED_GAMES)} TOTAL GAMES!")
    print(f"🎯 From {len(LETTER_PUZZLES)} puzzles to {len(EXPANDED_GAMES)} unique games")

# Load word lists once at startup
print("Loading word lists...")
WORD_LIST = load_word_list()
ANSWER_LIST = load_answers()

if not WORD_LIST:
    print("WARNING: No valid words loaded - using fallback words")
    WORD_LIST = ["HELLO", "WORLD", "FLASK", "GAMES", "WORDS", "QUICK", "BROWN", "JUMPS", "STORE", "STARE", "STEAM", "STEAL", "TIGER", "CHAIR", "HOUSE", "BREAD", "MAGIC", "PLANT", "LIGHT", "SMILE"]

if not ANSWER_LIST:
    print("WARNING: No answer words loaded - using fallback answers")
    ANSWER_LIST = ["HELLO", "WORLD", "FLASK", "GAMES", "COFFEE"]

print(f"System ready: {len(WORD_LIST)} words, {len(ANSWER_LIST)} answers")

# Load letter puzzles
print("Loading letter puzzles...")
LETTER_PUZZLES = load_letter_puzzles()

if not LETTER_PUZZLES:
    print("WARNING: No puzzles loaded - using fallback puzzles")
    LETTER_PUZZLES = [
        {
            "available_letters": ["T", "W", "N", "S", "I", "A", "W", "M", "N", "X", "R", "E"],
            "featured_letter": "T",
            "answer": "STARE"
        },
        {
            "available_letters": ["H", "O", "U", "S", "B", "L", "M", "K", "P", "E", "D", "R"],
            "featured_letter": "H",
            "answer": "HOUSE"
        },
        {
            "available_letters": ["M", "A", "G", "I", "C", "W", "N", "L", "K", "P", "F", "T"],
            "featured_letter": "M",
            "answer": "MAGIC"
        }
    ]

# Expand puzzles to all possible answers
expand_puzzles_to_all_answers()

print(f"Ready with {len(LETTER_PUZZLES)} base puzzles expanded to {len(EXPANDED_GAMES)} total games!")

# Redis helper functions with fallback to memory
def redis_get(key):
    try:
        response = requests.get(
            f"{UPSTASH_REDIS_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5
        )
        response.raise_for_status()
        result = response.json()
        return json.loads(result["result"]) if result["result"] else None
    except Exception as e:
        print(f"Redis GET error for key {key}: {str(e)} - using memory storage")
        return GAMES_STORAGE.get(key) or REDEMPTION_STORAGE.get(key)

def redis_set(key, value):
    try:
        response = requests.post(
            f"{UPSTASH_REDIS_URL}/set/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(value),
            timeout=5
        )
        response.raise_for_status()
        success = response.json().get("result") == "OK"
        if success:
            print(f"Saved {key} to Redis")
        return success
    except Exception as e:
        print(f"Redis SET error for key {key}: {str(e)} - saving to memory")
        if key.startswith("GAME_"):
            GAMES_STORAGE[key] = value
        elif key.startswith("REDEMPTION_"):
            REDEMPTION_STORAGE[key] = value
        return True

def generate_qr_code(data):
    """Generate QR code and return as base64 encoded image"""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        print(f"QR code generation error: {str(e)}")
        return None

def create_game_instance():
    """Create a game using expanded puzzle system"""
    global CURRENT_GAME_INDEX
    
    try:
        # Initialize expanded games if not done
        if not EXPANDED_GAMES:
            expand_puzzles_to_all_answers()
        
        if not EXPANDED_GAMES:
            print("ERROR: No expanded games available!")
            return None
        
        game_id = str(uuid.uuid4())
        
        # Get current game from expanded list
        current_game = EXPANDED_GAMES[CURRENT_GAME_INDEX % len(EXPANDED_GAMES)]
        
        # Move to next game
        CURRENT_GAME_INDEX += 1
        
        game_data = {
            'id': game_id,
            'type': 'letter_puzzle',
            'available_letters': current_game['available_letters'],
            'featured_letter': current_game['featured_letter'],
            'answer': current_game['answer'],
            'guess': None,
            'status': 'active',
            'created_at': datetime.datetime.now().isoformat(),
            'accessed': False,
            'redemption_code': None,
            'max_attempts': 1,
            'puzzle_number': current_game['puzzle_number'],
            'answer_number': current_game['answer_number'],
            'total_answers': current_game['total_answers_in_puzzle'],
            'game_sequence': CURRENT_GAME_INDEX
        }
        
        # Save to storage
        saved = redis_set(f"GAME_{game_id}", game_data)
        if saved:
            print(f"Game #{CURRENT_GAME_INDEX}: Puzzle {current_game['puzzle_number']}.{current_game['answer_number']} → '{current_game['answer']}' (featured: '{current_game['featured_letter']}')")
            return game_data
        else:
            print(f"Failed to save game {game_id}")
            return None
        
    except Exception as e:
        print(f"Error creating game: {str(e)}")
        traceback.print_exc()
        return None

def get_game_instance(game_id):
    """Retrieve game instance from storage"""
    try:
        return redis_get(f"GAME_{game_id}")
    except Exception as e:
        print(f"Error getting game {game_id}: {str(e)}")
        return None

def update_game_instance(game_id, game_data):
    """Update game instance in storage"""
    try:
        return redis_set(f"GAME_{game_id}", game_data)
    except Exception as e:
        print(f"Error updating game {game_id}: {str(e)}")
        return False

# Remove unused redemption functions and routes - no longer needed for simplified system

def validate_word(guess, available_letters, featured_letter):
    """Validate if the guessed word can be formed from available letters"""
    try:
        guess = guess.upper()
        
        # Check if word is 5 letters
        if len(guess) != 5:
            return False, "Word must be 5 letters long"
        
        # Check if featured letter is used
        if featured_letter not in guess:
            return False, f"You must use the featured letter '{featured_letter}'"
        
        # Check if word is in valid word list
        if guess not in WORD_LIST:
            return False, "Not a valid word"
        
        # Check if all letters are available
        available_count = {}
        for letter in available_letters:
            available_count[letter] = available_count.get(letter, 0) + 1
        
        guess_count = {}
        for letter in guess:
            guess_count[letter] = guess_count.get(letter, 0) + 1
        
        for letter, needed in guess_count.items():
            if available_count.get(letter, 0) < needed:
                return False, f"Not enough '{letter}' letters available"
        
        return True, "Valid word"
        
    except Exception as e:
        print(f"Error validating word: {str(e)}")
        return False, "Validation error"

# Routes

@app.route('/')
def root():
    return redirect(url_for('counter_device'))

@app.route('/counter_device')
def counter_device():
    """Interface for the counter device - generates QR codes for new games"""
    return render_template('counter_device.html')

@app.route('/test_game')
def test_game():
    """Quick test route - creates a game and redirects to it"""
    try:
        print("Creating test game...")
        game_data = create_game_instance()
        
        if game_data:
            game_id = game_data['id']
            print(f"Test game created with ID: {game_id}")
            print(f"Answer: {game_data['answer']}")
            print(f"Available letters: {game_data['available_letters']}")
            print(f"Featured letter: {game_data['featured_letter']}")
            
            # Redirect directly to the game
            return redirect(url_for('play_game', game_id=game_id))
        else:
            return "Failed to create test game", 500
            
    except Exception as e:
        print(f"Test game error: {str(e)}")
        return f"Error creating test game: {str(e)}", 500

@app.route('/api/create_game', methods=['POST'])
def api_create_game():
    """API endpoint to create a new game and return QR code"""
    try:
        print("Creating new letter puzzle game...")
        game_data = create_game_instance()
        
        if game_data:
            # Generate QR code with URL to the game
            game_url = url_for('play_game', game_id=game_data['id'], _external=True)
            print(f"Game URL: {game_url}")
            
            qr_code_data = generate_qr_code(game_url)
            
            if qr_code_data:
                return jsonify({
                    'success': True,
                    'game_id': game_data['id'],
                    'qr_code': qr_code_data,
                    'game_url': game_url
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to generate QR code'}), 500
        else:
            return jsonify({'success': False, 'error': 'Failed to create game - check server logs'}), 500
            
    except Exception as e:
        print(f"API create_game error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

@app.route('/api/check_game_access/<game_id>')
def check_game_access(game_id):
    """Check if a game has been accessed by a customer"""
    try:
        game_data = get_game_instance(game_id)
        if game_data:
            # Check if game has been accessed (has a guess or marked as accessed)
            accessed = game_data.get('guess') is not None or game_data.get('accessed', False)
            return jsonify({'success': True, 'accessed': accessed})
        else:
            return jsonify({'success': True, 'accessed': False})
    except Exception as e:
        print(f"Error checking game access: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/game/<game_id>')
def play_game(game_id):
    """Play a specific game instance - ONE ATTEMPT ONLY"""
    try:
        game_data = get_game_instance(game_id)
        if not game_data:
            return render_template('error.html', message="Game not found or expired"), 404
        
        # CHECK: If game is already completed, block access
        if game_data.get('status') != 'active':
            print(f"Blocked access to completed game {game_id} (status: {game_data.get('status')})")
            
            # Show different messages based on game outcome
            if game_data.get('status') == 'won':
                if game_data.get('redemption_code'):
                    message = f"🎉 You already won this puzzle and got discount code: {game_data['redemption_code']}<br><br>Scan a new QR code for another puzzle!"
                else:
                    message = "🎉 You already won this puzzle!<br><br>Scan a new QR code for another puzzle!"
            else:
                message = "❌ This puzzle has been completed.<br><br>Scan a new QR code for a fresh puzzle!"
            
            return redirect(url_for('blocked_access'))
        
        # Mark game as accessed when customer visits (first time only)
        if not game_data.get('accessed', False):
            game_data['accessed'] = True
            update_game_instance(game_id, game_data)
            print(f"Game {game_id} accessed by customer for first time")
        
        return render_template('letter_puzzle.html', 
                             game_id=game_id,
                             game_data=game_data)
    except Exception as e:
        print(f"Error loading game {game_id}: {str(e)}")
        return render_template('error.html', message="Error loading game"), 500

@app.route('/game/<game_id>/guess', methods=['POST'])
def submit_guess(game_id):
    """Submit a guess for a specific game"""
    try:
        game_data = get_game_instance(game_id)
        if not game_data or game_data['status'] != 'active':
            return jsonify({'success': False, 'error': 'Game not available'}), 400
        
        guess = request.json.get('guess', '').strip().upper()
        
        # Validate the guess
        is_valid, message = validate_word(guess, game_data['available_letters'], game_data['featured_letter'])
        if not is_valid:
            return jsonify({'success': False, 'error': message})
        
        # Update game data
        game_data['guess'] = guess
        
        # Check win condition
        if guess == game_data['answer']:
            game_data['status'] = 'won'
            # No need to create redemption codes - just show winner screen to staff
        else:
            game_data['status'] = 'lost'
        
        # Save updated game data
        update_game_instance(game_id, game_data)
        
        result = {
            'success': True,
            'status': game_data['status'],
            'word': game_data['answer']
        }
        
        # No QR codes or redemption codes needed anymore
        return jsonify(result)
        
    except Exception as e:
        print(f"Error submitting guess: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Server error processing guess'}), 500

# Redemption routes removed - simplified system uses direct winner screen verification

@app.route('/staff')
def staff_guide():
    """Staff guide for handling winning customers"""
    return render_template('staff.html')

@app.route('/ad_click')
def track_ad_click():
    """Track ad clicks and redirect to Agent Whisperer"""
    global AD_CLICKS
    AD_CLICKS += 1
    print(f"Ad clicked! Total clicks: {AD_CLICKS} - Redirecting to Agent Whisperer")
    
    # Redirect to the actual ad destination
    return redirect("https://agentwhisperer.onrender.com")

# API redemption route removed - no longer needed for simplified system

@app.route('/game/<game_id>/status')
def game_status(game_id):
    """Check game status - for frontend to verify game is still active"""
    try:
        game_data = get_game_instance(game_id)
        if not game_data:
            return jsonify({'valid': False, 'message': 'Game not found'})
        
        is_active = game_data.get('status') == 'active'
        
        return jsonify({
            'valid': is_active,
            'status': game_data.get('status'),
            'message': 'Game active' if is_active else 'Game completed'
        })
    except Exception as e:
        return jsonify({'valid': False, 'message': 'Error checking game'})

@app.route('/blocked')
def blocked_access():
    """Show blocked access page with option to get new game"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Game Completed</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .container { background: rgba(255,255,255,0.1); padding: 40px; border-radius: 20px; max-width: 500px; margin: 0 auto; }
            .btn { background: #00c851; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-size: 1.2em; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚫 Game Already Completed</h1>
            <p>This puzzle has already been played.</p>
            <p>Each QR code gives you <strong>ONE attempt only</strong>.</p>
            <br>
            <p>Go back to the cafe counter and scan a <strong>NEW QR code</strong> for a fresh puzzle!</p>
            <br>
            <a href="/counter_device" class="btn">🎯 Get New Puzzle</a>
        </div>
    </body>
    </html>
    """
def admin_game_sequence():
    """Show the full game sequence"""
    global CURRENT_GAME_INDEX, EXPANDED_GAMES
    
    if not EXPANDED_GAMES:
        expand_puzzles_to_all_answers()
    
    html = "<h1>Game Sequence</h1>"
    html += f"<p><strong>Next game will be: #{(CURRENT_GAME_INDEX % len(EXPANDED_GAMES)) + 1}</strong></p>"
    html += f"<p>Total games available: {len(EXPANDED_GAMES)}</p>"
    html += "<hr>"
    
    # Show next 20 games
    html += "<h2>Next 20 Games:</h2><ol>"
    for i in range(min(20, len(EXPANDED_GAMES))):
        game_index = (CURRENT_GAME_INDEX + i) % len(EXPANDED_GAMES)
        game = EXPANDED_GAMES[game_index]
        status = "→ NEXT" if i == 0 else ""
        html += f"<li>Game #{CURRENT_GAME_INDEX + i + 1}: Puzzle {game['puzzle_number']}.{game['answer_number']} = <strong>{game['answer']}</strong> (featured: {game['featured_letter']}) {status}</li>"
    html += "</ol>"
    
    # Show puzzle breakdown
    html += "<hr><h2>Puzzle Breakdown:</h2>"
    puzzle_counts = {}
    for game in EXPANDED_GAMES:
        puzzle_num = game['puzzle_number']
        if puzzle_num not in puzzle_counts:
            puzzle_counts[puzzle_num] = 0
        puzzle_counts[puzzle_num] += 1
    
    for puzzle_num in sorted(puzzle_counts.keys()):
        count = puzzle_counts[puzzle_num]
        html += f"<p><strong>Puzzle {puzzle_num}:</strong> {count} different answers</p>"
    
    html += f"<hr><p><a href='/counter_device'>Back to Counter Device</a></p>"
    
    return html

# Simple storage for admin metrics
AD_CLICKS = 0

@app.route('/admin')
def admin_dashboard():
    """Simple admin dashboard - 3 key metrics only"""
    try:
        # Calculate key metrics
        total_scans = CURRENT_GAME_INDEX  # Total games created (scanned)
        total_winners = sum(1 for g in GAMES_STORAGE.values() if g.get('status') == 'won')
        total_ad_clicks = AD_CLICKS
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>QWORD Admin</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                }}
                .container {{ 
                    max-width: 800px; 
                    margin: 0 auto; 
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    padding: 40px;
                    backdrop-filter: blur(10px);
                }}
                h1 {{ 
                    text-align: center; 
                    font-size: 2.5em;
                    margin-bottom: 40px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                }}
                .metrics {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 30px; 
                    margin-bottom: 40px; 
                }}
                .metric {{ 
                    background: rgba(255,255,255,0.2); 
                    padding: 30px; 
                    border-radius: 15px; 
                    text-align: center;
                    border: 1px solid rgba(255,255,255,0.3);
                }}
                .number {{ 
                    font-size: 3em; 
                    font-weight: bold; 
                    color: #feca57;
                    display: block;
                    margin-bottom: 10px;
                }}
                .label {{ 
                    font-size: 1.2em; 
                    opacity: 0.9;
                }}
                .links {{ 
                    text-align: center;
                    margin-top: 40px;
                }}
                .link {{ 
                    background: rgba(255,255,255,0.2); 
                    color: white; 
                    text-decoration: none; 
                    padding: 15px 25px; 
                    margin: 10px; 
                    border-radius: 10px; 
                    display: inline-block;
                    transition: all 0.3s ease;
                }}
                .link:hover {{ 
                    background: rgba(255,255,255,0.3); 
                    color: white;
                    text-decoration: none;
                }}
                .refresh {{ 
                    text-align: center; 
                    margin-top: 30px; 
                    opacity: 0.7;
                }}
            </style>
            <script>
                // Auto-refresh every 10 seconds
                setTimeout(() => window.location.reload(), 10000);
            </script>
        </head>
        <body>
            <div class="container">
                <h1>📊 QWORD Admin</h1>
                
                <div class="metrics">
                    <div class="metric">
                        <span class="number">{total_scans}</span>
                        <div class="label">QR Code Scans</div>
                    </div>
                    <div class="metric">
                        <span class="number">{total_winners}</span>
                        <div class="label">Winners</div>
                    </div>
                    <div class="metric">
                        <span class="number">{total_ad_clicks}</span>
                        <div class="label">Ad Clicks</div>
                    </div>
                </div>

                <div class="links">
                    <a href="/counter_device" class="link">🎯 Counter Device</a>
                    <a href="/staff" class="link">👥 Staff Guide</a>
                    <a href="/test_game" class="link">🧪 Test Game</a>
                    <a href="javascript:window.location.reload()" class="link">🔄 Refresh</a>
                </div>

                <div class="refresh">
                    Auto-refreshes every 10 seconds
                </div>
            </div>
        </body>
        </html>
        """
                             
    except Exception as e:
        print(f"Admin panel error: {str(e)}")
        return f"<h1>Admin Error</h1><p>{str(e)}</p>", 500

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'game_type': 'multi_answer_letter_puzzle',
        'puzzles_available': len(LETTER_PUZZLES),
        'total_games': len(EXPANDED_GAMES),
        'current_game_index': CURRENT_GAME_INDEX,
        'qr_scans': CURRENT_GAME_INDEX,
        'winners': sum(1 for g in GAMES_STORAGE.values() if g.get('status') == 'won'),
        'ad_clicks': AD_CLICKS
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="Internal server error"), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Multi-Answer Letter Puzzle Cafe server...")
    print(f"🎯 {len(LETTER_PUZZLES)} base puzzles")
    print(f"🎮 {len(EXPANDED_GAMES)} total unique games")
    print(f"📚 Loaded {len(WORD_LIST)} words for validation")
    print("🔗 URLs:")
    print("   Counter Device: http://localhost:5000")
    print("   TEST GAME:      http://localhost:5000/test_game")
    print("   ADMIN PANEL:    http://localhost:5000/admin")
    print("   Staff Guide:    http://localhost:5000/staff")
    print("   Health Check:   http://localhost:5000/health")
    print("   Ad Click Track: http://localhost:5000/ad_click")
    print("=" * 50)
    
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
from flask import Flask, render_template, request, session, redirect, url_for
import datetime
import os
import traceback
import random
import requests
import glob
import json
import uuid
from werkzeug.utils import secure_filename

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load word lists at startup
WORD_LIST = []
ANSWER_LIST = []

# Upstash Redis configuration
UPSTASH_REDIS_URL = "https://ample-chamois-15026.upstash.io"
UPSTASH_REDIS_TOKEN = "your-upstash-token"  # Replace with your actual token

# Admin password for simple authentication
ADMIN_PASSWORD = "admin123"

# Directory to store uploaded images
UPLOAD_FOLDER = 'static/row_images'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Load DAILY_WORD_STATE from Upstash Redis
def load_daily_word_state():
    try:
        response = requests.get(
            f"{UPSTASH_REDIS_URL}/get/DAILY_WORD_STATE",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        )
        response.raise_for_status()
        result = response.json()
        if result["result"]:
            state = json.loads(result["result"])
            print(f"Loaded DAILY_WORD_STATE from Upstash: {state}")
            return state
        else:
            print("No DAILY_WORD_STATE found in Upstash, returning default state")
            return {'word': None}
    except Exception as e:
        print(f"Error loading daily word state from Upstash: {str(e)}")
        return {'word': None}

# Save DAILY_WORD_STATE to Upstash Redis
def save_daily_word_state(state):
    try:
        response = requests.post(
            f"{UPSTASH_REDIS_URL}/set/DAILY_WORD_STATE",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(state)
        )
        response.raise_for_status()
        if response.json().get("result") == "OK":
            print(f"Saved DAILY_WORD_STATE to Upstash: {state}")
        else:
            print(f"Failed to save DAILY_WORD_STATE to Upstash, response: {response.json()}")
    except Exception as e:
        print(f"Error saving daily word state to Upstash: {str(e)}")

# Load ROW_IMAGES from Upstash Redis
def load_row_images():
    try:
        response = requests.get(
            f"{UPSTASH_REDIS_URL}/get/ROW_IMAGES",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        )
        response.raise_for_status()
        result = response.json()
        if result["result"]:
            images = json.loads(result["result"])
            print(f"Loaded ROW_IMAGES from Upstash: {images}")
            return images
        else:
            print("No ROW_IMAGES found in Upstash, returning default state")
            return {}
    except Exception as e:
        print(f"Error loading row images from Upstash: {str(e)}")
        return {}

# Save ROW_IMAGES to Upstash Redis
def save_row_images(images):
    try:
        response = requests.post(
            f"{UPSTASH_REDIS_URL}/set/ROW_IMAGES",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(images)
        )
        response.raise_for_status()
        if response.json().get("result") == "OK":
            print(f"Saved ROW_IMAGES to Upstash: {images}")
        else:
            print(f"Failed to save ROW_IMAGES to Upstash, response: {response.json()}")
    except Exception as e:
        print(f"Error saving row images to Upstash: {str(e)}")

# Load USER_PLAYED_WORDS from Upstash Redis
def load_user_played_words(session_id):
    try:
        response = requests.get(
            f"{UPSTASH_REDIS_URL}/get/USER_PLAYED_{session_id}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        )
        response.raise_for_status()
        result = response.json()
        if result["result"]:
            words = json.loads(result["result"])
            print(f"Loaded USER_PLAYED_{session_id} from Upstash: {words}")
            return words
        else:
            print(f"No USER_PLAYED_{session_id} found in Upstash, returning empty set")
            return set()
    except Exception as e:
        print(f"Error loading user played words from Upstash: {str(e)}")
        return set()

# Save USER_PLAYED_WORDS to Upstash Redis
def save_user_played_words(session_id, words):
    try:
        response = requests.post(
            f"{UPSTASH_REDIS_URL}/set/USER_PLAYED_{session_id}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(list(words))
        )
        response.raise_for_status()
        if response.json().get("result") == "OK":
            print(f"Saved USER_PLAYED_{session_id} to Upstash: {words}")
        else:
            print(f"Failed to save USER_PLAYED_{session_id} to Upstash, response: {response.json()}")
    except Exception as e:
        print(f"Error saving user played words to Upstash: {str(e)}")

# Clear USER_PLAYED_WORDS when admin sets a new word
def clear_user_played_words():
    try:
        # This is a simplistic approach; in production, you might want to list all keys and delete them selectively
        print("Clearing all user played words is not implemented due to Redis key listing limitation. Consider manual reset or advanced Redis setup.")
    except Exception as e:
        print(f"Error attempting to clear user played words: {str(e)}")

# Load states at startup
DAILY_WORD_STATE = load_daily_word_state()
ROW_IMAGES = load_row_images()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_word_list(file_path='words.txt'):
    try:
        with open(file_path, 'r') as f:
            words = [line.strip().upper() for line in f if len(line.strip()) == 5 and line.strip().isalpha()]
            return words
    except FileNotFoundError:
        return []

def load_answers(file_path='answers.txt'):
    try:
        with open(file_path, 'r') as f:
            answers = [line.strip().upper() for line in f if len(line.strip()) == 5 and line.strip().isalpha()]
            print(f"Loaded answers from answers.txt: {answers}")
            return answers
    except FileNotFoundError:
        return []

# Load word lists once at startup
WORD_LIST = load_word_list()
ANSWER_LIST = load_answers()

if not WORD_LIST or not ANSWER_LIST:
    raise RuntimeError("Failed to load word or answer lists. Server cannot start.")

def get_random_word(answer_list):
    return random.choice(answer_list)

def get_daily_word(answer_list):
    # Check if we have an override
    if DAILY_WORD_STATE.get('word'):
        print(f"Using existing DAILY_WORD_STATE word: {DAILY_WORD_STATE['word']}")
        return DAILY_WORD_STATE['word']
    
    # If no word is set, set a random word
    new_word = get_random_word(answer_list)
    DAILY_WORD_STATE['word'] = new_word
    save_daily_word_state(DAILY_WORD_STATE)
    print(f"Set new random word: {new_word}")
    clear_user_played_words()  # Clear played words when a new word is set
    return new_word

def get_feedback(guess, target):
    feedback = ['gray'] * 5
    target_list = list(target)
    guess_list = list(guess)
    for i in range(5):
        if guess_list[i] == target_list[i]:
            feedback[i] = 'green'
            target_list[i] = None
    for i in range(5):
        if feedback[i] == 'gray' and guess_list[i] in target_list:
            feedback[i] = 'yellow'
            target_list[target_list.index(guess_list[i])] = None
    return feedback

@app.route('/admin_daily_word', methods=['GET', 'POST'])
def admin_daily_word():
    try:
        # Simple password check for admin access
        password = request.args.get('password') if request.method == 'GET' else request.form.get('password')
        if password != ADMIN_PASSWORD:
            return "Unauthorized: Incorrect password.", 403

        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'override_random':
                new_word = get_random_word(ANSWER_LIST)
                DAILY_WORD_STATE['word'] = new_word
                save_daily_word_state(DAILY_WORD_STATE)
                print(f"Admin overrode word to: {new_word}")
            elif action == 'override_specific':
                new_word = request.form.get('new_word', '').strip().upper()
                print(f"Attempting to override word with: '{new_word}'")
                print(f"ANSWER_LIST contents: {ANSWER_LIST}")
                if new_word in ANSWER_LIST:
                    DAILY_WORD_STATE['word'] = new_word
                    save_daily_word_state(DAILY_WORD_STATE)
                    print(f"Admin overrode word to: {new_word}")
                else:
                    print(f"Word '{new_word}' not found in ANSWER_LIST.")
                    return "Invalid word. Please choose a word from answers.txt.", 400
            elif action == 'upload_all_row_images':
                global ROW_IMAGES
                for i in range(6):
                    file = request.files.get(f'row_{i}')
                    if file and file.filename != '' and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        ext = filename.rsplit('.', 1)[1].lower()
                        new_filename = f"row_{i}.{ext}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                        ROW_IMAGES[str(i)] = f"/static/row_images/{new_filename}"
                        print(f"Uploaded image for row {i}: {new_filename}")
                save_row_images(ROW_IMAGES)

            # Clear all user sessions to ensure the new word/images take effect immediately
            session_files = glob.glob('flask_session/*')
            for session_file in session_files:
                try:
                    os.remove(session_file)
                    print(f"Cleared session file: {session_file}")
                except Exception as e:
                    print(f"Error clearing session file {session_file}: {str(e)}")

            return redirect(url_for('admin_daily_word', password=password))

        # Show the current word and row images
        current_word = get_daily_word(ANSWER_LIST)
        today = datetime.date.today()
        return render_template('admin_daily_word.html', current_word=current_word, today=today, row_images=ROW_IMAGES)
    except Exception as e:
        print(f"Error in admin_daily_word route: {str(e)}")
        print(traceback.format_exc())
        return f"Server Error: {str(e)}", 500

@app.route('/')
def root():
    return redirect(url_for('daily_game'))

@app.route('/daily_game', methods=['GET', 'POST'])
def daily_game():
    try:
        # Generate or retrieve a unique session ID for the user
        session_id = request.cookies.get('user_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            response = make_response(render_template('wordle.html', ...))  # Placeholder for response
            response.set_cookie('user_session_id', session_id, max_age=365*24*60*60)  # 1-year expiration
            return response

        # Use a session key for this user to store their progress
        session_key = f'daily_game_{session_id}'

        # Initialize session for this user if not present
        if session_key not in session:
            session[session_key] = {
                'attempts': [],
                'feedbacks': [],
                'game_over': False,
                'won': False,
                'last_played_date': datetime.date.today().isoformat()
            }
            session.modified = True
            print(f"Session initialized for user {session_id}:", session[session_key])

        # Load played words for this user
        played_words = load_user_played_words(session_id)

        # Check if the date has changed since the last play
        last_played_date = session[session_key].get('last_played_date')
        today = datetime.date.today().isoformat()
        if last_played_date != today:
            # Reset the session if it's a new day, but retain played words
            session[session_key] = {
                'attempts': [],
                'feedbacks': [],
                'game_over': False,
                'won': False,
                'last_played_date': today
            }
            session.modified = True
            print(f"Session reset for new day for user {session_id}")

        print(f"Session state before processing for user {session_id}:", session[session_key])

        valid_words = set(WORD_LIST)
        target = get_daily_word(ANSWER_LIST)

        # Check if the player has already played this word
        if target in played_words:
            return render_template('wordle.html', error="You have already played this word. Please wait for the admin to set a new word.", 
                                 attempts=session[session_key]['attempts'], 
                                 feedbacks=session[session_key]['feedbacks'],
                                 game_over=True,
                                 row_images=ROW_IMAGES)

        if request.method == 'POST' and not session[session_key]['game_over']:
            guess = request.form.get('guess', '').strip().upper()
            if len(guess) != 5 or not guess.isalpha():
                return render_template('wordle.html', error="Please enter a valid 5-letter word.", 
                                     attempts=session[session_key]['attempts'], 
                                     feedbacks=session[session_key]['feedbacks'],
                                     row_images=ROW_IMAGES)
            if guess not in valid_words:
                return render_template('wordle.html', error="Not in word list. Try again.", 
                                     attempts=session[session_key]['attempts'], 
                                     feedbacks=session[session_key]['feedbacks'],
                                     row_images=ROW_IMAGES)

            feedback = get_feedback(guess, target)
            session[session_key]['attempts'].append(guess)
            session[session_key]['feedbacks'].append(feedback)
            session.modified = True

            if guess == target:
                session[session_key]['game_over'] = True
                session[session_key]['won'] = True
                played_words.add(target)
                save_user_played_words(session_id, played_words)
            elif len(session[session_key]['attempts']) >= 6:
                session[session_key]['game_over'] = True
                played_words.add(target)
                save_user_played_words(session_id, played_words)

            print(f"Session state after guess for user {session_id}:", session[session_key])
            return render_template('wordle.html', attempts=session[session_key]['attempts'], 
                                 feedbacks=session[session_key]['feedbacks'], 
                                 game_over=session[session_key]['game_over'], 
                                 won=session[session_key]['won'], 
                                 target=target,
                                 row_images=ROW_IMAGES)

        print(f"Session state before rendering for user {session_id}:", session[session_key])
        return render_template('wordle.html', attempts=session[session_key]['attempts'], 
                             feedbacks=session[session_key]['feedbacks'], 
                             game_over=session[session_key]['game_over'], 
                             won=session[session_key]['won'], 
                             target=target,
                             row_images=ROW_IMAGES)
    except Exception as e:
        print(f"Error in daily_game route: {str(e)}")
        print(traceback.format_exc())
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    print("Starting Flask server...")
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
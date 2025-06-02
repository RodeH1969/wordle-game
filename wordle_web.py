from flask import Flask, render_template, request, session, redirect, url_for
import datetime
import os
import traceback
import random
import requests
import glob
import json

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load word lists at startup
WORD_LIST = []
ANSWER_LIST = []

# Upstash Redis configuration (replace with your Upstash REST API URL and token)
UPSTASH_REDIS_URL = "https://ample-chamois-15026.upstash.io"
UPSTASH_REDIS_TOKEN = "<ATqyAAIjcDFhZjU5NjI5NDdhZjA0ZDE5YjIwM2RiMTNjM2Q5M2VjN3AxMA>"

# Admin password for simple authentication
ADMIN_PASSWORD = "admin123"

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

# Load DAILY_WORD_STATE at startup
DAILY_WORD_STATE = load_daily_word_state()

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
            # Override the word
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

            # Clear all user sessions to ensure the new word takes effect immediately
            session_files = glob.glob('flask_session/*')
            for session_file in session_files:
                try:
                    os.remove(session_file)
                    print(f"Cleared session file: {session_file}")
                except Exception as e:
                    print(f"Error clearing session file {session_file}: {str(e)}")

            return redirect(url_for('admin_daily_word', password=password))

        # Show the current word
        current_word = get_daily_word(ANSWER_LIST)
        today = datetime.date.today()
        return render_template('admin_daily_word.html', current_word=current_word, today=today)
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
        # Use a session key for this user to store their progress
        session_key = 'daily_game'

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
            print(f"Session initialized for user:", session[session_key])
        else:
            # Check if the date has changed since the last play
            last_played_date = session[session_key].get('last_played_date')
            today = datetime.date.today().isoformat()
            if last_played_date != today:
                # Reset the session if it's a new day
                session[session_key] = {
                    'attempts': [],
                    'feedbacks': [],
                    'game_over': False,
                    'won': False,
                    'last_played_date': today
                }
                session.modified = True
                print(f"Session reset for new day:", session[session_key])

        print(f"Session state before processing:", session[session_key])

        valid_words = set(WORD_LIST)
        target = get_daily_word(ANSWER_LIST)

        if request.method == 'POST' and not session[session_key]['game_over']:
            guess = request.form.get('guess', '').strip().upper()
            if len(guess) != 5 or not guess.isalpha():
                return render_template('wordle.html', error="Please enter a valid 5-letter word.", 
                                     attempts=session[session_key]['attempts'], 
                                     feedbacks=session[session_key]['feedbacks'])
            if guess not in valid_words:
                return render_template('wordle.html', error="Not in word list. Try again.", 
                                     attempts=session[session_key]['attempts'], 
                                     feedbacks=session[session_key]['feedbacks'])

            feedback = get_feedback(guess, target)
            session[session_key]['attempts'].append(guess)
            session[session_key]['feedbacks'].append(feedback)
            session.modified = True

            if guess == target:
                session[session_key]['game_over'] = True
                session[session_key]['won'] = True
            elif len(session[session_key]['attempts']) >= 6:
                session[session_key]['game_over'] = True

            print(f"Session state after guess:", session[session_key])
            return render_template('wordle.html', attempts=session[session_key]['attempts'], 
                                 feedbacks=session[session_key]['feedbacks'], 
                                 game_over=session[session_key]['game_over'], 
                                 won=session[session_key]['won'], 
                                 target=target)

        print(f"Session state before rendering:", session[session_key])
        return render_template('wordle.html', attempts=session[session_key]['attempts'], 
                             feedbacks=session[session_key]['feedbacks'], 
                             game_over=session[session_key]['game_over'], 
                             won=session[session_key]['won'], 
                             target=target)
    except Exception as e:
        print(f"Error in daily_game route: {str(e)}")
        print(traceback.format_exc())
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    print("Starting Flask server...")
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
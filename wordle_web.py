from flask import Flask, render_template, request, session, redirect, url_for
import datetime
import os
import traceback
import random

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load word lists at startup
WORD_LIST = []
ANSWER_LIST = []

# Store the daily word state (date and override word if set)
DAILY_WORD_STATE = {
    'date': None,  # Store the date for which the word is set
    'word': None   # Store the overridden word, if any
}

# Admin password for simple authentication (for local testing)
ADMIN_PASSWORD = "admin123"  # Change this in production or use proper authentication

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
            print(f"Loaded answers from answers.txt: {answers}")  # Debug: Log the loaded answers
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

def get_daily_word(answer_list, start_date=datetime.date(2025, 1, 1)):
    today = datetime.date.today()
    today_str = today.isoformat()

    # Check if we have an override for today
    if DAILY_WORD_STATE.get('date') == today_str and DAILY_WORD_STATE.get('word'):
        return DAILY_WORD_STATE['word']
    
    # Otherwise, use the deterministic daily word
    days_since_start = (today - start_date).days
    return answer_list[days_since_start % len(answer_list)]

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

        today = datetime.date.today()
        today_str = today.isoformat()

        if request.method == 'POST':
            # Override the daily word
            action = request.form.get('action')
            if action == 'override_random':
                new_word = get_random_word(ANSWER_LIST)
                DAILY_WORD_STATE['date'] = today_str
                DAILY_WORD_STATE['word'] = new_word
                print(f"Admin overrode daily word to: {new_word}")
            elif action == 'override_specific':
                new_word = request.form.get('new_word', '').strip().upper()
                print(f"Attempting to override daily word with: '{new_word}'")  # Debug: Log the entered word
                print(f"ANSWER_LIST contents: {ANSWER_LIST}")  # Debug: Log the ANSWER_LIST
                if new_word in ANSWER_LIST:
                    DAILY_WORD_STATE['date'] = today_str
                    DAILY_WORD_STATE['word'] = new_word
                    print(f"Admin overrode daily word to: {new_word}")
                else:
                    print(f"Word '{new_word}' not found in ANSWER_LIST.")  # Debug: Log why it failed
                    return "Invalid word. Please choose a word from answers.txt.", 400
            return redirect(url_for('admin_daily_word', password=password))

        # Show the current daily word
        current_word = get_daily_word(ANSWER_LIST)
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
            else:
                # Ensure game_over is False if reinitializing on the same day
                session[session_key]['game_over'] = False
                session[session_key]['won'] = False
                session.modified = True
                print(f"Session forced reset for user:", session[session_key])

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
    port = int(os.getenv('PORT', 5000))  # Use PORT env var if set, otherwise default to 5000
    app.run(debug=True, host='0.0.0.0', port=port)
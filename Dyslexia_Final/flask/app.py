import whisper
import language_tool_python
from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import pickle
import pandas as pd
import tempfile
import easyocr
from PIL import Image
from datetime import datetime
from pymongo import MongoClient
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pyttsx3
import random
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
whisper_model = whisper.load_model("base")
tool = language_tool_python.LanguageTool('en-US')
reader = easyocr.Reader(['en']) # type: ignore

# MongoDB setup
mongo_client = MongoClient("mongodb+srv://project:project@project.u4o6dhd.mongodb.net/?appName=project") # type: ignore
mongo_db = mongo_client["dyslexia_app"] # type: ignore
users_collection = mongo_db["users"] # type: ignore
prog_collection = mongo_db["progress"] # type: ignore
progress_collection = mongo_db.progress_assist # type: ignore
user_profile = mongo_db.user_profile # type: ignore
logs_collection = mongo_db['logs'] # type: ignore

# Dictionary for dyslexia-specific word corrections
DYSLEXIA_CORRECTIONS = {
    'scool':'school',
    'gud':'good',
    'skool':'school',
    'techer': 'teacher',
    'tehcer': 'teacher',
    'lerning': 'learning',
    # 'lern': 'learn',
    # 'reeding': 'reading',
    # 'reding': 'reading',
    # 'writting': 'writing',
    # 'riting': 'writing',
    # 'speling': 'spelling',
    # 'instruckshuns': 'instructions',
    # 'insturctions': 'instructions',
    # 'leson': 'lesson',
    # 'libary': 'library',
    # 'libery': 'library',
    # 'beacause': 'because',
    # 'becaus': 'because',
    # 'bcos': 'because',
    # 'alwais': 'always',
    # 'alwys': 'always',
    # 'sumtimes': 'sometimes',
    # 'somtimes': 'sometimes',
    # 'thay': 'they',
    # 'thier': 'their',
    # 'wich': 'which',
    # 'wihch': 'which',
    'scool': 'school', 
    # 'shcool': 'school', 'techer': 'teacher', 'tehcer': 'teacher', 'lerning': 'learning', 'lern': 'learn', 'reeding': 'reading', 'reding': 'reading', 'writting': 'writing', 'riting': 'writing', 'speling': 'spelling', 'instruckshuns': 'instructions', 'insturctions': 'instructions', 'leson': 'lesson', 'libary': 'library', 'libery': 'library', 'beacause': 'because', 'becaus': 'because', 'bcos': 'because', 'alwais': 'always', 'alwys': 'always', 'sumtimes': 'sometimes', 'somtimes': 'sometimes', 'thay': 'they', 'thier': 'their', 'ther': 'there', 'wich': 'which', 'wihch': 'which', 'whre': 'where', 'wehn': 'when', 'trie': 'try', 'tryed': 'tried', 'red': 'read', 'hav': 'have', 'kep': 'keep', 'geting': 'getting', 'goeing': 'going', 'cum': 'come', 'sa': 'saw', 'thik': 'think', 'thnking': 'thinking', 'dooing': 'doing', 'freind': 'friend', 'frend': 'friend', 'famly': 'family', 'peple': 'people', 'poeple': 'people', 'bok': 'book', 'storry': 'story', 'animel': 'animal', 'dinasor': 'dinosaur', 'dragun': 'dragon', 'pictur': 'picture', 'moovie': 'movie', 'mouvie': 'movie', 'gud': 'good', 'grate': 'great', 'hapy': 'happy', 'ez': 'easy', 'dificult': 'difficult', 'diffcult': 'difficult', 'reely': 'really', 'realy': 'really', 'quik': 'quick', 'slw': 'slow', 'yesturday': 'yesterday', 'tommorow': 'tomorrow', 'tommorrow': 'tomorrow', 'nite': 'night', 'todae': 'today', 'befor': 'before', 'aftr': 'after', 'noe': 'now', 'cant': 'can’t', 'cudnt': 'couldn’t', 'dont': 'don’t', 'wont': 'won’t', 'shudnt': 'shouldn’t', 'didnt': 'didn’t', 'thoghts': 'thoughts', 'then': 'than', 'rite': 'right', 'mispeling': 'misspelling', 'sence': 'sense', 'embarest': 'embarrassed', 'frusterating': 'frustrating', 'sum': 'some', 'alot': 'a lot', 'evry': 'every', 'somthing': 'something', 'anyting': 'anything', 'knw': 'know', 'noe': 'know'
}

# [Previous helper functions remain unchanged]
def hash_password(password): # type: ignore
    salt = os.urandom(32)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.b64encode(kdf.derive(password.encode())) # type: ignore
    return salt + key

def verify_password(stored_password, provided_password): # type: ignore
    salt = stored_password[:32]
    stored_key = stored_password[32:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.b64encode(kdf.derive(provided_password.encode()))
    return key == stored_key

def apply_dictionary_corrections(text):
    """Apply dictionary-based corrections for dyslexia-specific misspellings."""
    corrected_text = text
    for wrong, correct in DYSLEXIA_CORRECTIONS.items():
        pattern = r'\b' + re.escape(wrong) + r'\b'
        corrected_text = re.sub(pattern, correct, corrected_text, flags=re.IGNORECASE)
    return corrected_text

def correct_text(text, username):
    """Correct text using dictionary-based corrections followed by language tool."""
    dict_corrected_text = apply_dictionary_corrections(text)
    matches = tool.check(dict_corrected_text)
    final_corrected_text = language_tool_python.utils.correct(dict_corrected_text, matches)
    
    user_progress = prog_collection.find_one({"username": username}, sort=[("timestamp", -1)])
    if not user_progress:
        user_progress = {
            "username": username,
            "common_errors": {},
            "error_count": 0,
            "session_count": 0,
            "timestamp": datetime.utcnow(),
            "font_preference": "Arial"
        }
    error_map = user_progress.get("common_errors", {})
    errors = []
    
    original_words = text.split()
    corrected_words = final_corrected_text.split()
    for i, (orig, corr) in enumerate(zip(original_words, corrected_words)):
        if orig.lower() != corr.lower():
            suggestion = corr if corr else None
            if suggestion and orig.lower() != suggestion.lower():
                errors.append((orig, suggestion))
                error_map[orig] = suggestion

    for wrong, correct in DYSLEXIA_CORRECTIONS.items():
        if wrong.lower() in text.lower():
            errors.append((wrong, correct))
            error_map[wrong] = correct

    prog_collection.insert_one({
        "username": username,
        "common_errors": error_map,
        "error_count": user_progress.get("error_count", 0) + len(errors),
        "session_count": user_progress.get("session_count", 0) + 1,
        "timestamp": datetime.utcnow(),
        "font_preference": user_progress.get("font_preference", "Arial")
    })
    return final_corrected_text, errors

def train_model():
    data = pd.DataFrame({
        'text': [
            "I have truble with words", "I can read and write well",
            "Speling is dificult", "Reading is easy",
            "I confuse b and d", "I enjoy books",
            "Words are hard for me", "Reading comes naturally",
            "I mix up letters", "I love storytelling",
            "Writing is challenging", "Books are my friends",
            "Letters look jumbled", "I comprehend well",
            "Dyslexia affects me", "I have no reading issues",
            "Words dance on the page", "I read fluently",
            "Spelling tests scare me", "I ace vocabulary tests",
            "I strugle with reading", "Reading is effortless",
            "Sentences confuse me", "I understand texts quickly",
            "Puncuation is hard", "Grammar comes naturally"
        ],
        'label': ['Dyslexic', 'Not Dyslexic'] * 13
    })
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    model = make_pipeline(TfidfVectorizer(max_features=100), RandomForestClassifier(n_estimators=200))
    model.fit(data['text'], data['label'])
    with open("dyslexia_model.pkl", "wb") as f:
        pickle.dump(model, f)
    return model

def load_model():
    if not os.path.exists("dyslexia_model.pkl"):
        return train_model()
    with open("dyslexia_model.pkl", "rb") as f:
        return pickle.load(f)

def predict(text):
    model = load_model()
    return model.predict([text])[0]

def extract_text_from_image(image_file):
    try:
        # Convert image to format EasyOCR expects (can be PIL Image or path)
        results = reader.readtext(image_file.read())
        text = " ".join([res[1] for res in results])
        return text
    except Exception as e:
        print(f"OCR error: {e}")
        # Fallback to Tesseract if EasyOCR fails
        try:
            image_file.seek(0)
            img = Image.open(image_file).convert("L")
            text = pytesseract.image_to_string(img)
            return text
        except:
            return None

def transcribe_audio(audio_file):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_file.read())
            temp_path = tmp.name
        
        # Audio transcription should happen after the file is closed for Windows compatibility
        result = whisper_model.transcribe(temp_path)
        return result['text']
    except Exception as e:
        print(f"Transcription error: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

@app.route('/')
def homeapp():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and verify_password(user['password_hash'], password):
            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = str(user['_id'])
            return redirect(url_for('app_page'))
        flash('Invalid credentials', 'error')
    return render_template('login1.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']
        if password != confirm:
            flash("Passwords don't match", 'error')
        elif users_collection.find_one({'username': username}):
            flash("User already exists", 'error')
        else:
            users_collection.insert_one({'username': username, 'password_hash': hash_password(password)})
            flash("Registered. Please login.", 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/app', methods=['GET', 'POST'])
def app_page():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    username = session['username']
    result = None
    original_text = None
    corrected_text = None
    errors = []
    transcript = None
    has_errors = False  # Modified: New flag to indicate if errors were detected

    if request.method == 'POST':
        input_method = request.form.get('input_method', 'text')

        if input_method == 'text':
            text_input = request.form.get('text_input', '').strip()
            transcript = text_input
        elif input_method == 'audio' and 'audio_file' in request.files:
            audio_file = request.files['audio_file']
            if audio_file.filename:
                transcript = transcribe_audio(audio_file)
                if not transcript:
                    flash('Audio transcription failed.', 'error')
        elif input_method == 'image' and 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file.filename:
                transcript = extract_text_from_image(image_file)

        if transcript and len(transcript.strip()) >= 1:
            corrected_text, errors = correct_text(transcript, username)
            result = predict(transcript)
            original_text = transcript
            has_errors = len(errors) > 0  # Modified: Set flag based on presence of errors
        else:
            flash("Text too short or not detected", "warning")

    font_pref = "Arial"
    user_latest = prog_collection.find_one({"username": username}, sort=[("timestamp", -1)])
    if user_latest:
        font_pref = user_latest.get("font_preference", "Arial")

    return render_template("app.html", username=username, result=result,
                           original_text=original_text, corrected_text=corrected_text,
                           errors=errors, font_preference=font_pref, transcript=transcript,
                           has_errors=has_errors)  # Modified: Pass has_errors instead of dyslexia

@app.route('/module')
def module():
    user_id = session.get('user_id', 'guest')
    print(user_id)
    user = user_profile.find_one({'user_id': user_id}) or {"capability_score": 1.0}
    capability_score = user.get('capability_score', 1.0)

    practice_paragraph = generate_custom_paragraph(capability_score)
    session['practice_paragraph'] = practice_paragraph

    progress_history = get_all_progress(user_id)
    previous_texts = [item['reference_text'] for item in progress_history]

    previous_texts = [
    ref if len(ref) <= 40 else ref[:37] + "..."
    for ref in previous_texts   
    ]

    return render_template('module.html', reference_text=practice_paragraph, module_id=0, previous_texts=previous_texts)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



from pymongo import MongoClient

genai.configure(api_key='AIzaSyDtaqP73ub3cZ5L_VZAZHTrdnn3TP_b-Bk')

engine = pyttsx3.init()


def save_progress(user_id, reference_text, incorrect_words, text_done, audio_done):
    progress_data = {
        "user_id": user_id,
        "text_done": text_done,
        "audio_done": audio_done,
        "reference_text": reference_text,
        "incorrect_words": incorrect_words,
    }
    progress_collection.insert_one(progress_data)

def get_all_progress(user_id):
    return list(progress_collection.find({"user_id": user_id}).sort("module_id", 1))


def get_latest_progress(user_id):
    return progress_collection.find_one({"user_id": user_id}, sort=[('_id', -1)])


def update_user_capability(user_id, reference_text, incorrect_words):
    total_words = len(reference_text.split())
    incorrect_count = len(incorrect_words)

    profile = user_profile.find_one({"user_id": user_id}) or {
        "user_id": user_id,
        "capability_score": 1.0,
        "history": {
            "total_attempts": 0,
            "total_words": 0,
            "total_errors": 0
        }
    }

    profile["history"]["total_attempts"] += 1
    profile["history"]["total_words"] += total_words
    profile["history"]["total_errors"] += incorrect_count

    total_words = profile["history"]["total_words"]
    total_errors = profile["history"]["total_errors"]
    profile["capability_score"] = max(0.1, round(1 - (total_errors / total_words), 2))

    user_profile.update_one({"user_id": user_id}, {"$set": profile}, upsert=True)


def generate_custom_paragraph(capability_score):
    if capability_score < 0.80:
        prompt = "Write a very simple English paragraph using short and easy words. Use 2-3 sentences that are clear and beginner-friendly."
    elif capability_score < 0.83:
        prompt = "Create a basic English paragraph using simple vocabulary. Keep it under 4 sentences with clear ideas and minimal complexity."
    elif capability_score < 0.87:
        prompt = "Generate an easy English paragraph with some basic vocabulary. Use short sentences and keep the paragraph friendly for early learners."
    elif capability_score < 0.91:
        prompt = "Write an intermediate English paragraph using slightly challenging vocabulary. Include 3-4 sentences with clear structure."
    elif capability_score < 0.95:
        prompt = "Generate a moderately advanced English paragraph with a few uncommon words. Aim for 4-5 sentences with a smooth flow."
    else:
        prompt = "Write a challenging English paragraph using complex vocabulary and varied sentence structures. Make it 5-6 sentences long and intellectually engaging."


    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([prompt])
        print(response.text.strip())
        return response.text.strip()
    except Exception as e:
        print("Gemini API error:", e)
        return "The sun rises in the east and sets in the west."

@app.route('/homepage')
def homepage():
    return render_template('homepage.html')

@app.route('/history')
def history():
    user_id = session.get('user_id', 'guest')

    user_progress = list(progress_collection.find({"user_id": user_id}))

    # Convert ObjectId to string to make JSON serializable
    for entry in user_progress:
        entry['_id'] = str(entry['_id'])

    user_profile_data = user_profile.find_one({"user_id": user_id})
    capability_score = user_profile_data.get("capability_score", 0) if user_profile_data else 0

    docs = list(progress_collection.find({"user_id": user_id}))  # Convert cursor to list


# Temporary list to store all correct words (in order of appearance)
    correct_words_ordered = []

    for doc in docs:
        incorrect_words = doc.get("incorrect_words", [])
        for word in incorrect_words:
            correct = word.get("correct")
            if correct:
                correct_words_ordered.append(correct.lower().strip())  # Normalize

    # Reverse the list so newest entries come first
    correct_words_ordered.reverse()

    # Now pick unique words in this reversed order
    seen = set()
    unique_correct_words = []
    for word in correct_words_ordered:
        if word not in seen:
            unique_correct_words.append(word)
            seen.add(word)

    # Get the top 10 most recent unique correct words
    top_10_unique_correct = unique_correct_words[:10]

    # Display
    # print("Top 10 Unique Corrected Words (Newest First)")
    # print("=" * 45)
    for word in top_10_unique_correct:
        print(f"{word:>20}")
    return render_template("history.html",
                           history_list=user_progress,
                           capability_score=capability_score,
                           top_corrected_words=top_10_unique_correct)


@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    data = request.get_json() or {}
    rate = int(data.get('rate', 150))
    
    # Prioritize text sent from frontend, fallback to session or DB
    text = data.get('text')
    if not text:
        user_id = session.get('user_id', 'guest')
        progress = get_latest_progress(user_id)
        text = (progress["reference_text"] if progress and progress.get("reference_text") else session.get('practice_paragraph', ''))
    
    if not text or not text.strip():
        return jsonify({'error': 'No text provided for audio generation'}), 400

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_path = temp_file.name
        
        engine.setProperty('rate', rate)
        engine.save_to_file(text, temp_path)
        engine.runAndWait()

        with open(temp_path, 'rb') as f:
            audio_base64 = base64.b64encode(f.read()).decode('utf-8')
        os.remove(temp_path)
        return jsonify({'audio': f'data:audio/wav;base64,{audio_base64}'})
    except Exception as e:
        print(f"Audio generation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/word_audio')
def word_audio():
    word = request.args.get('word', '')
    if not word:
        return jsonify({'error': 'No word provided'}), 400
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_path = temp_file.name
    
    engine.setProperty('rate', 150)
    engine.save_to_file(word, temp_path)
    engine.runAndWait()

    with open(temp_path, 'rb') as f:
        audio_base64 = base64.b64encode(f.read()).decode('utf-8')
    os.remove(temp_path)
    return jsonify({'audio': f'data:audio/wav;base64,{audio_base64}'})

@app.route('/retrain', methods=['POST'])
def retrain():
    try:
        train_model()
        return jsonify({"message": "Model retrained successfully!"})
    except Exception as e:
        return jsonify({"message": f"Error retraining model: {str(e)}"}), 500

import re

def clean_word(word):
    # Remove punctuation like -, ., , ? !
    return re.sub(r'[.,?!:;]', '', word.lower()).strip()

import difflib
def compare_texts(user_text, reference_text):
    reference_words = [clean_word(w) for w in reference_text.split() if clean_word(w)]
    user_words = [clean_word(w) for w in user_text.split() if clean_word(w)]

    matcher = difflib.SequenceMatcher(None, reference_words, user_words)
    incorrect_words = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            for ref_word, user_word in zip(reference_words[i1:i2], user_words[j1:j2]):
                incorrect_words.append({'user': user_word, 'correct': ref_word})
            
            # Handle length mismatches between segments
            if (i2 - i1) > (j2 - j1):  # Missing user words
                for ref_word in reference_words[i1 + (j2 - j1):i2]:
                    incorrect_words.append({'user': '', 'correct': ref_word})
            elif (j2 - j1) > (i2 - i1):  # Extra user words
                for user_word in user_words[j1 + (i2 - i1):j2]:
                    incorrect_words.append({'user': user_word, 'correct': ''})


    pronunciations = []
    for word in incorrect_words:
        if word['correct']:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_path = temp_file.name
            engine.save_to_file(f" {word['correct']}", temp_path)
            engine.runAndWait()
            with open(temp_path, 'rb') as f:
                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
            os.remove(temp_path)
            pronunciations.append({
                'word': word['correct'],
                'audio': f'data:audio/wav;base64,{audio_base64}'
            })

    return incorrect_words, pronunciations


@app.route('/check_text', methods=['POST'])
def check_text():
    user_id = session.get('user_id', 'guest')
    user_text = request.json.get('text', '')

    practice_paragraph = session.get('practice_paragraph', '')
    incorrect_words, pronunciations = compare_texts(user_text, practice_paragraph)
    # print(pronunciations)
    completed = len(incorrect_words) == 0

    save_progress(user_id,  practice_paragraph, incorrect_words, text_done=completed, audio_done=False)
    update_user_capability(user_id, practice_paragraph, incorrect_words)

    return jsonify({
        'incorrect': incorrect_words,
        'pronunciations': pronunciations,
        'completed': completed,
        'points': 10 if completed else 0
    })


@app.before_request
def load_user():
    if 'user_id' not in session:
        session['user_id'] = 'guest'

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/sort')
def sort():
    return render_template('sort.html')

@app.route('/match')
def match():
    return render_template('match.html')

@app.route('/context')
def context():
    return render_template('context_exercise.html')


@app.route('/exercise/<exercise_type>')
def exercise(exercise_type):
    sample_words = [
        {"user": "recieve", "correct": "receive"},
        {"user": "definately", "correct": "definitely"},
        {"user": "seperate", "correct": "separate"},
        {"user": "occurence", "correct": "occurrence"},
        {"user": "goverment", "correct": "government"}
    ]
    user_id = session.get('user_id', 'guest')
    user_documents = progress_collection.find({"user_id": user_id})

    all_incorrect_words = []
    for doc in user_documents:
        incorrects = doc.get("incorrect_words", [])
        all_incorrect_words.extend(incorrects)
    print(all_incorrect_words)

    if exercise_type == "spelling":
        return render_template("spelling_exercise.html", words=all_incorrect_words)
    elif exercise_type == "fillblank":
        sentences = [
            {"text": f"The ___ of the event was unexpected.", "answer": word['correct']} for word in sample_words
        ]
        return render_template("fill_blank_exercise.html", sentences=sentences)
    elif exercise_type == "multiplechoice":
        options = [
            {
                "question": word['user'],
                "choices": random.sample([word['correct'], word['user'], word['correct'][::-1], 'random'], k=4),
                "answer": word['correct']
            }
            for word in sample_words
        ]
        return render_template("multiple_choice.html", options=options)
    else:
        return redirect(url_for('home'))

@app.route('/submit/<exercise_type>', methods=['POST'])
def submit(exercise_type):
    user_id = session['user_id']
    answers = request.form.to_dict()
    result = {
        "user_id": user_id,
        "exercise_type": exercise_type,
        "answers": answers
    }
    mongo_db.exercise_logs.insert_one(result)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

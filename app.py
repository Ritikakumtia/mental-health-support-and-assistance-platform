from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO
from datetime import datetime
import google.generativeai as genai


app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'your_secret_key_here'  # Change this in production

USERS_FILE = 'users.json'
STATS_FILE = 'stats.json'

CRISIS_KEYWORDS = [
    'suicide', 'kill myself', 'hurt myself', 'self-harm', 'self harm',
    'end my life', 'want to die', 'emergency', 'panic attack', 'hospital',
    'kill myself', 'die', 'dying'
]


def is_crisis_message(text):
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRISIS_KEYWORDS)

API_KEY = os.getenv('GEMINI_API_KEY', '')

SYSTEM_PROMPT = """You are a friendly empathetic mental health companion and counsellor.
Listen carefully, detect emotional tone, respond kindly with motivational support and to turn the user to positivity and fuel with motivation.
Keep responses concise (3-5 sentences always replying in cefr c2 level english).
Automatically detect and respond in the user's language."""

NEGATIVE_KEYWORDS = [
    'sad', 'depressed', 'angry', 'upset', 'hurt', 'afraid', 'scared', 'hopeless', 'overwhelmed'
]
POSITIVE_KEYWORDS = [
    'happy', 'good', 'great', 'hopeful', 'excited', 'relieved', 'calm', 'better', 'okay', 'optimistic'
]
STRESS_KEYWORDS = ['stress', 'stressed', 'pressure', 'overwhelmed', 'burnout']
ANXIETY_KEYWORDS = ['anxious', 'anxiety', 'panic', 'nervous', 'worried']
LONELY_KEYWORDS = ['lonely', 'loneliness', 'isolated', 'alone']
HAPPY_KEYWORDS = POSITIVE_KEYWORDS


def get_sentiment_label(text):
    if not text:
        return 'neutral'
    lowered = text.lower()
    if any(keyword in lowered for keyword in STRESS_KEYWORDS):
        return 'stressed'
    if any(keyword in lowered for keyword in ANXIETY_KEYWORDS):
        return 'anxious'
    if any(keyword in lowered for keyword in LONELY_KEYWORDS):
        return 'lonely'
    positive_matches = sum(1 for keyword in HAPPY_KEYWORDS if keyword in lowered)
    negative_matches = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in lowered)
    if positive_matches > negative_matches:
        return 'happy'
    if negative_matches > positive_matches:
        return 'sad'
    return 'neutral'


def ai_reply(user_input, sentiment, history=None):
    if not API_KEY:
        return (
            "⚠️ I cannot connect to the AI service because the GEMINI_API_KEY environment variable is not set. "
            "Please set GEMINI_API_KEY and restart the server."
        )

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"{SYSTEM_PROMPT}\nUser mood: {sentiment}\nUser: {user_input}"
        if history:
            history_text = '\n'.join(
                f"User: {item['content']}" if item['role'] == 'user' else f"Assistant: {item['content']}"
                for item in history[-5:]
                if item.get('role') in {'user', 'assistant'} and item.get('content')
            )
            if history_text:
                prompt = f"{SYSTEM_PROMPT}\nConversation history:\n{history_text}\nUser mood: {sentiment}\nUser: {user_input}"

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f'Gemini API error: {e}')
        return "⚠️ I'm having trouble connecting right now. Please try again in a moment."


def generate_bot_response(user_message, history=None):
    if is_crisis_message(user_message):
        return (
            'I am sorry that you are feeling this way. If you are in immediate danger or thinking about harming yourself, '
            'please contact local emergency services or a trusted person right away. You are not alone.'
        )

    sentiment = get_sentiment_label(user_message)
    return ai_reply(user_message, sentiment, history)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {'total_logins': 0, 'total_quiz_completions': 0, 'total_registrations': 0}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def load_mental_health_data():
    data_file = 'mental_health_data_summary.json'
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'national': {}, 'state_prevalence': []}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)


def build_dashboard_recommendations(chat_history):
    text = ' '.join(chat.get('user_message', '').lower() for chat in chat_history)
    found_stress = any(keyword in text for keyword in STRESS_KEYWORDS)
    found_anxiety = any(keyword in text for keyword in ANXIETY_KEYWORDS)
    found_lonely = any(keyword in text for keyword in LONELY_KEYWORDS)
    found_sad = any(keyword in text for keyword in ['sad', 'depressed', 'hopeless', 'down', 'unhappy'])
    found_happy = any(keyword in text for keyword in HAPPY_KEYWORDS)

    course_map = {
        'Stress Management': '/courses/stress-management',
        'Understanding Anxiety and Depression': '/courses/understanding-anxiety',
        'Mindfulness': '/courses/mindfulness-meditation',
        'Emotional Intelligence': '/courses/emotional-intelligence',
        'Building Resilience': '/courses/building-resilience',
        'Introduction to Psychology': '/courses/introduction-to-psychology'
    }

    professionals = []
    activities = []
    courses = []

    if found_stress or found_anxiety:
        courses += ['Stress Management', 'Understanding Anxiety and Depression', 'Mindfulness']
        professionals += [
            {'label': 'Dr. Anjali Verma (Stress & Anxiety)', 'url': '/counselors#request-counseling'},
            {'label': 'Dr. Rajesh Kumar (Emotional Support)', 'url': '/counselors#request-counseling'}
        ]
        activities += [
            'Practice 5 minutes of deep breathing each day',
            'Take a short mindful walk outside',
            'Use a grounding exercise when you feel overwhelmed'
        ]

    if found_lonely or found_sad:
        courses += ['Emotional Intelligence', 'Building Resilience', 'Mindfulness']
        professionals += [
            {'label': 'Dr. Priya Sharma (Relationship Support)', 'url': '/counselors#request-counseling'},
            {'label': 'Dr. Rajesh Kumar (Mental Health Support)', 'url': '/counselors#request-counseling'}
        ]
        activities += [
            'Reach out to a friend or family member',
            'Write down three positive moments from today',
            'Set a gentle self-care goal'
        ]

    if found_happy and not (found_stress or found_anxiety or found_lonely or found_sad):
        courses += ['Emotional Intelligence', 'Mindfulness', 'Building Resilience']
        professionals += [
            {'label': 'Dr. Anjali Verma (Wellness Coach)', 'url': '/counselors#request-counseling'},
            {'label': 'Dr. Priya Sharma (Positive Psychology)', 'url': '/counselors#request-counseling'}
        ]
        activities += [
            'Keep tracking what makes you feel good',
            'Share your progress with someone who supports you',
            'Continue the habits that keep you balanced'
        ]

    if not (found_stress or found_anxiety or found_lonely or found_sad or found_happy):
        courses += ['Mindfulness', 'Emotional Intelligence', 'Building Resilience']
        professionals += [
            {'label': 'Dr. Anjali Verma (General Wellness)', 'url': '/counselors#request-counseling'},
            {'label': 'Dr. Rajesh Kumar (Emotional Support)', 'url': '/counselors#request-counseling'}
        ]
        activities += [
            'Try a short mindfulness or breathing practice',
            'Spend 10 minutes in a calming activity like walking or reading',
            'Reflect on one thing you are grateful for today'
        ]

    course_suggestions = []
    for course_name in list(dict.fromkeys(courses))[:4]:
        course_suggestions.append({'name': course_name, 'url': course_map.get(course_name, '/courses')})

    professionals = list({item['label']: item for item in professionals}.values())[:4]
    if not professionals:
        professionals = [
            {'label': 'Currently we do not have the exact counselor you need. Please explore our available professionals or speak with another qualified expert.', 'url': '/counselors#request-counseling'}
        ]

    suggestions = {
        'courses': course_suggestions,
        'professionals': professionals,
        'activities': list(dict.fromkeys(activities))[:5]
    }
    return suggestions


def record_user_activity(page_name):
    username = session.get('user')
    if not username:
        return
    users = load_users()
    if username not in users:
        return
    recent_activity = users[username].get('recent_activity', [])
    if recent_activity and recent_activity[-1].get('page') == page_name:
        return
    recent_activity.append({
        'page': page_name,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
    })
    users[username]['recent_activity'] = recent_activity[-8:]
    save_users(users)


@app.before_request
def track_page_visits():
    if request.method != 'GET':
        return
    if request.path.startswith('/static') or request.path.startswith('/api'):
        return
    if request.path in ['/login', '/register', '/logout']:
        return
    page_names = {
        '/': 'Home',
        '/about': 'About',
        '/chatbot': 'AI Chatbot',
        '/contact': 'Contact',
        '/counselors': 'Counselors',
        '/courses': 'Courses',
        '/doctors': 'Doctors',
        '/hospitals': 'Hospitals'
    }
    record_user_activity(page_names.get(request.path, request.path))

def send_registration_email(email, first_name, last_name):
    try:
        msg = MIMEMultipart()
        msg['From'] = ''
        msg['To'] = email
        msg['Subject'] = 'Welcome to MindSarthi AI - Account Created Successfully'
        
        body = f"""
        Dear {first_name} {last_name},

        Welcome to MindSarthi AI! Your account has been created successfully.

        You can now log in to access our psychology-based courses and earn certificates.

        Best regards,
        MindSarthi AI Team
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        
        print(f"Registration email sent to {email}")
    except Exception as e:
        print(f"Failed to send registration email: {e}")

def generate_certificate_pdf(first_name, last_name, course_name, score, total, date):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    story = []
    story.append(Paragraph("Certificate of Completion", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"This certifies that {first_name} {last_name} has successfully completed the {course_name} course.", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Score: {score}/{total}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Issued on: {date}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("MindSarthi AI", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def send_certificate_email(email, first_name, last_name, course_name, score, total, date):
    try:
        msg = MIMEMultipart()
        msg['From'] = ''
        msg['To'] = email
        msg['Subject'] = f'MindSarthi AI - Certificate for {course_name}'
        
        body = f"""
        Dear {first_name} {last_name},

        Congratulations! You have successfully completed the {course_name} course.

        Your certificate is attached to this email.

        Best regards,
        MindSarthi AI Team
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Generate PDF
        pdf_buffer = generate_certificate_pdf(first_name, last_name, course_name, score, total, date)
        
        # Attach PDF
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_buffer.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=MindSarthi_Certificate_{course_name.replace(" ", "_")}.pdf')
        msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        
        print(f"Certificate email sent to {email} for {course_name}")
    except Exception as e:
        print(f"Failed to send certificate email: {e}")

def send_counseling_confirmation_email(email, name, counselor, reasons, message):
    try:
        msg = MIMEMultipart()
        msg['From'] = ''
        msg['To'] = email
        msg['Subject'] = 'MindSarthi AI - Counseling Session Scheduled'
        
        reasons_str = ', '.join(reasons) if reasons else 'Not specified'
        
        body = f"""
        Dear {name},

        Thank you for requesting counseling with MindSarthi AI.

        Your session has been scheduled with {counselor}.

        Reasons for counseling: {reasons_str}
        Additional message: {message}

        Our team will contact you at {email} or your provided contact number within 24 hours to confirm the appointment time.

        We look forward to supporting you on your mental health journey.

        Best regards,
        MindSarthi AI Team
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        
        print(f"Counseling confirmation email sent to {email}")
    except Exception as e:
        print(f"Failed to send counseling confirmation email: {e}")

def send_contact_confirmation_email(email, name, subject):
    try:
        msg = MIMEMultipart()
        msg['From'] = ''
        msg['To'] = email
        msg['Subject'] = 'MindSarthi AI - Contact Request Received'
        
        body = f"""
        Dear {name},

        Thank you for contacting MindSarthi AI!

        We have received your request for "{subject}" and our team will contact you as soon as possible.

        We appreciate you using our platform and are here to support your mental health journey.

        Best regards,
        MindSarthi AI Team
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        
        print(f"Contact confirmation email sent to {email}")
    except Exception as e:
        print(f"Failed to send contact confirmation email: {e}")

def get_current_user():
    if 'user' in session:
        users = load_users()
        user = users.get(session['user'])
        if user:
            user_with_username = user.copy()
            user_with_username['username'] = session['user']
            return user_with_username
    return None

@app.context_processor
def inject_user():
    return {'current_user': get_current_user()}

@app.route('/')
def index():
    mental_health_data = load_mental_health_data()
    state_prevalence = mental_health_data.get('state_prevalence', [])
    national_prevalence = mental_health_data.get('national', {})
    return render_template('index.html', state_prevalence=state_prevalence, national_prevalence=national_prevalence)

@app.route('/login', methods=['GET', 'POST'])
def login():
    stats = load_stats()
    stats['total_logins'] += 1
    save_stats(stats)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        if username in users and users[username]['password'] == password:
            session['user'] = username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Validate password
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            flash('Password must be at least 8 characters long and include uppercase, lowercase, number, and special character.', 'error')
            return render_template('register.html')
        
        users = load_users()
        if username in users:
            flash('Username already exists!', 'error')
            return render_template('register.html')
        
        users[username] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
            'quizzes': {}
        }
        save_users(users)
        stats = load_stats()
        stats['total_registrations'] += 1
        save_stats(stats)
        send_registration_email(email, first_name, last_name)
        flash('Account created successfully! Please check your email for confirmation.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    # Course progress and quiz scores
    quizzes = user.get('quizzes', {})
    course_names = {
        'intro': 'Introduction to Psychology',
        'stress': 'Stress Management',
        'anxiety': 'Understanding Anxiety and Depression',
        'ei': 'Emotional Intelligence',
        'resilience': 'Building Resilience',
        'mindfulness': 'Mindfulness'
    }
    progress = []
    for course_key, data in quizzes.items():
        progress.append({
            'course': course_names.get(course_key, course_key),
            'score': data.get('score', 0),
            'total': data.get('total', 10),
            'passed': data.get('passed', False),
            'date': data.get('date', 'N/A')
        })
    
    # Mood trends (placeholder for now)
    mood_trends = "Mood tracking coming soon!"
    
    # Recent activities (placeholder)
    recent_activities = []
    recent_activity_entries = user.get('recent_activity', [])
    for entry in recent_activity_entries[-4:][::-1]:
        recent_activities.append(f"{entry['timestamp']} — Visited {entry['page']}")

    if not recent_activities:
        recent_activities = [
            "Login successful",
            "Viewed course catalog",
            "Opened dashboard"
        ]

    chat_history = user.get('chat_history', [])
    mood_counts = {
        'happy': 0,
        'stressed': 0,
        'anxious': 0,
        'lonely': 0,
        'sad': 0,
        'neutral': 0
    }
    if chat_history:
        for chat in chat_history:
            sentiment = chat.get('sentiment', 'neutral')
            if sentiment not in mood_counts:
                sentiment = 'neutral'
            mood_counts[sentiment] += 1

    total_moods = sum(mood_counts.values())
    if total_moods > 0:
        labels = {
            'happy': 'Happy',
            'stressed': 'Stressed',
            'anxious': 'Anxious',
            'lonely': 'Lonely',
            'sad': 'Sad',
            'neutral': 'Neutral'
        }
        trend_parts = []
        for key in ['happy', 'stressed', 'anxious', 'lonely', 'sad', 'neutral']:
            if mood_counts[key] > 0:
                percent = round(mood_counts[key] / total_moods * 100)
                trend_parts.append(f"{percent}% {labels[key]}")
        mood_trends = ' | '.join(trend_parts)
    else:
        mood_trends = 'Chat with the AI to start tracking your mood trends.'

    recommendations = build_dashboard_recommendations(chat_history)

    # Analytics
    stats = load_stats()
    analytics = {
        'total_logins': stats['total_logins'],
        'total_quiz_completions': stats['total_quiz_completions'],
        'total_registrations': stats['total_registrations']
    }

    mental_health_data = load_mental_health_data()
    state_prevalence = mental_health_data.get('state_prevalence', [])
    national_prevalence = mental_health_data.get('national', {})
    
    return render_template(
        'dashboard.html',
        user=user,
        progress=progress,
        mood_trends=mood_trends,
        recent_activities=recent_activities,
        analytics=analytics,
        mood_counts=mood_counts,
        recommendations=recommendations,
        state_prevalence=state_prevalence,
        national_prevalence=national_prevalence
    )

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/chatbot')
def chatbot():
    user = get_current_user()
    if not user:
        flash('Please login to access the AI chatbot and maintain your conversation history.', 'error')
        return redirect(url_for('login'))
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    user = get_current_user()
    if not user:
        return jsonify({'reply': 'Please login to use the chatbot feature.'}), 401

    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({'reply': 'Please enter a message so I can assist you.'}), 400

    if is_crisis_message(user_message):
        return jsonify({'reply': (
            'I am sorry that you are feeling this way. If you are in immediate danger or thinking about harming yourself, '
            'please contact local emergency services or a trusted person right away. You are not alone.'
        )})

    reply = generate_bot_response(user_message, history)

    # Store chat history for the user
    users = load_users()
    username = session.get('user')
    if username and username in users:
        if 'chat_history' not in users[username]:
            users[username]['chat_history'] = []
        users[username]['chat_history'].append({
            'timestamp': '2024-01-01',  # Simplified timestamp
            'user_message': user_message,
            'bot_reply': reply,
            'sentiment': get_sentiment_label(user_message)
        })
        # Keep only last 50 messages to prevent file from growing too large
        users[username]['chat_history'] = users[username]['chat_history'][-50:]
        save_users(users)

    return jsonify({'reply': reply})

@app.route('/api/chatbot/history')
def get_chat_history():
    user = get_current_user()
    if not user:
        return jsonify({'history': []}), 401

    chat_history = user.get('chat_history', [])
    return jsonify({'history': chat_history})

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    print("Contact route called - Method:", request.method)
    if request.method == 'POST':
        print("POST request received to /contact")
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        print(f"Form data - Name: {name}, Email: {email}, Subject: {subject}")
        
        # Log the contact message
        print(f"New contact message from {name} ({email}): Subject: {subject}, Message: {message}")
        
        # Send confirmation email to the user
        try:
            send_contact_confirmation_email(email, name, subject)
            print("Email sent successfully")
        except Exception as e:
            print(f"Email sending failed: {e}")
            flash('Thank you for your message! We will get back to you soon.', 'success')
            return redirect(url_for('contact'))
        
        flash('Thank you for contacting us! We have received your message and will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/counselors')
def counselors():
    return render_template('counselors.html')
@app.route('/counselors/request', methods=['POST'])
def counselors_request():
    name = request.form.get('name')
    contact = request.form.get('contact')
    email = request.form.get('email')
    counselor = request.form.get('counselor')
    reasons = request.form.getlist('reasons')
    message = request.form.get('message', '')
    
    # Process the request (log it or save to DB)
    print(f"New counseling request: {name}, {email}, {contact}, Counselor: {counselor}, Reasons: {', '.join(reasons)}, Message: {message}")
    
    # Send confirmation email
    send_counseling_confirmation_email(email, name, counselor, reasons, message)
    
    flash('Your counseling request has been submitted successfully! You will receive a confirmation email shortly.', 'success')
    return redirect(url_for('counselors'))
@app.route('/courses')
def courses():
    return render_template('courses.html')

@app.route('/doctors')
def doctors():
    return render_template('doctors.html')

@app.route('/hospitals')
def hospitals():
    return render_template('hospitals.html')

@app.route('/api/search/hospitals')
def search_hospitals():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter q is required'}), 400
    
    # First, get bbox for the location in India using Nominatim
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    nominatim_params = {
        'q': f'{query}, India',
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'MindSarthiAI/1.0'}
    try:
        nom_response = requests.get(nominatim_url, params=nominatim_params, headers=headers, timeout=10)
        nom_response.raise_for_status()
        nom_data = nom_response.json()
        if not nom_data:
            return jsonify({'error': 'Location not found in India'}), 404
        
        bbox = nom_data[0]['boundingbox']
        south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        
        # Now query Overpass with the bbox
        overpass_url = "http://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json];
        (
          node["amenity"="hospital"]({south},{west},{north},{east});
          way["amenity"="hospital"]({south},{west},{north},{east});
          relation["amenity"="hospital"]({south},{west},{north},{east});
        );
        out center;
        """
        response = requests.get(overpass_url, params={'data': overpass_query}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        hospitals = []
        for element in data['elements']:
            tags = element.get('tags', {})
            name = tags.get('name', 'Unknown')
            lat = element.get('lat', element.get('center', {}).get('lat'))
            lon = element.get('lon', element.get('center', {}).get('lon'))
            address = tags.get('addr:full', '')
            phone = tags.get('phone', '')
            if lat and lon and address:  # Only include hospitals with address
                hospitals.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'address': address,
                    'phone': phone
                })
        return jsonify(hospitals)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/doctors')
def search_doctors():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter q is required'}), 400
    
    # First, get bbox for the location in India using Nominatim
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    nominatim_params = {
        'q': f'{query}, India',
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'MindSarthiAI/1.0'}
    try:
        nom_response = requests.get(nominatim_url, params=nominatim_params, headers=headers, timeout=10)
        nom_response.raise_for_status()
        nom_data = nom_response.json()
        if not nom_data:
            return jsonify({'error': 'Location not found in India'}), 404
        
        bbox = nom_data[0]['boundingbox']
        south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        
        # Now query Overpass with the bbox
        overpass_url = "http://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json];
        (
          node["amenity"="doctors"]({south},{west},{north},{east});
          way["amenity"="doctors"]({south},{west},{north},{east});
          relation["amenity"="doctors"]({south},{west},{north},{east});
        );
        out center;
        """
        response = requests.get(overpass_url, params={'data': overpass_query}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        doctors = []
        for element in data['elements']:
            tags = element.get('tags', {})
            name = tags.get('name', 'Unknown')
            lat = element.get('lat', element.get('center', {}).get('lat'))
            lon = element.get('lon', element.get('center', {}).get('lon'))
            if lat and lon:
                doctors.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'specialty': tags.get('healthcare:speciality', ''),
                    'phone': tags.get('phone', '')
                })
        return jsonify(doctors)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/courses/introduction-to-psychology')
def course_intro():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-intro.html')

@app.route('/courses/stress-management')
def course_stress():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-stress.html')

@app.route('/courses/understanding-anxiety')
def course_anxiety():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-anxiety.html')

@app.route('/courses/emotional-intelligence')
def course_ei():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-ei.html')

@app.route('/courses/building-resilience')
def course_resilience():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-resilience.html')

@app.route('/courses/mindfulness-meditation')
def course_mindfulness():
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template('course-mindfulness.html')

@app.route('/quiz/<course>')
def quiz(course):
    if not get_current_user():
        return redirect(url_for('login'))
    return render_template(f'course-{course}-quiz.html')

@app.route('/quiz_result/<course>', methods=['POST'])
def quiz_result(course):
    if not get_current_user():
        return redirect(url_for('login'))
    answers = request.form
    correct_answers = {
        'intro': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'},
        'stress': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'},
        'anxiety': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'},
        'ei': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'},
        'resilience': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'},
        'mindfulness': {'q1': 'b', 'q2': 'a', 'q3': 'b', 'q4': 'a', 'q5': 'b', 'q6': 'a', 'q7': 'b', 'q8': 'a', 'q9': 'b', 'q10': 'a'}
    }
    correct = correct_answers.get(course, {})
    score = 0
    for q, ans in answers.items():
        if ans == correct.get(q):
            score += 1
    passed = score >= 5
    course_names = {
        'intro': 'Introduction to Psychology',
        'stress': 'Stress Management',
        'anxiety': 'Understanding Anxiety and Depression',
        'ei': 'Emotional Intelligence',
        'resilience': 'Building Resilience',
        'mindfulness': 'Mindfulness'
    }
    
    # Store quiz result for user
    user = get_current_user()
    if user:
        users = load_users()
        if 'quizzes' not in users[session['user']]:
            stats = load_stats()
            stats['total_quiz_completions'] += 1
            save_stats(stats)
            users[session['user']]['quizzes'] = {}
        users[session['user']]['quizzes'][course] = {
            'score': score,
            'total': 10,
            'passed': passed,
            'date': '2024-01-01'  # Simplified date
        }
        save_users(users)
        
        if passed:
            # Send certificate email
            send_certificate_email(user['email'], user['first_name'], user['last_name'], course_names.get(course, ''), score, 10, '2024-01-01')
    
    return render_template('quiz_result.html', course=course, course_name=course_names.get(course, ''), passed=passed, score=score, total=10, user=session.get('user'))

if __name__ == '__main__':
    app.run(debug=True)
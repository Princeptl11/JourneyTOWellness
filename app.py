import os
import csv
import io
import random
import re
import string
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, make_response, session

load_dotenv()
import dns.resolver
from email_validator import validate_email, EmailNotValidError
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///journal.db?timeout=20'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    privacy_mode = db.Column(db.Boolean, default=False)
    onboarding_completed = db.Column(db.Boolean, default=False)
    stress_triggers = db.Column(db.String(255), default="")
    entries = db.relationship('JournalEntry', backref='author', lazy=True)

    def get_id(self):
        return str(self.user_id)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class JournalEntry(db.Model):
    __tablename__ = 'journal_entry'
    entry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(100), nullable=False)
    sentiment_score = db.Column(db.Float)
    tips = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Tip(db.Model):
    __tablename__ = 'tip'
    tip_id = db.Column(db.Integer, primary_key=True)
    mood_type = db.Column(db.String(50), nullable=False)
    tip_text = db.Column(db.Text, nullable=False)

# Optional Models
class MoodLog(db.Model):
    __tablename__ = 'mood_log'
    mood_id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.entry_id'))
    mood_type = db.Column(db.String(50))
    intensity = db.Column(db.Integer)

class WeeklyReport(db.Model):
    __tablename__ = 'weekly_report'
    report_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    week_range = db.Column(db.String(50))
    total_entries = db.Column(db.Integer)
    positive_moods = db.Column(db.Integer)
    neutral_moods = db.Column(db.Integer)
    negative_moods = db.Column(db.Integer)

class SleepLog(db.Model):
    __tablename__ = 'sleep_log'
    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    hours_slept = db.Column(db.Float, nullable=False)
    sleep_quality = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---
def seed_tips():
    if Tip.query.first():
        return
    tips_data = [
        ('Happy', 'Share your joy with a friend! Happiness multiplies when shared.'),
        ('Happy', 'Write down three things you are grateful for right now.'),
        ('Calm', 'Take a moment to enjoy this peace. Close your eyes and breathe deeply.'),
        ('Calm', 'Great time for some light reading or a gentle walk.'),
        ('Neutral', 'A balanced state is a great foundation. What is one small goal you can achieve today?'),
        ('Neutral', 'Try something new today—a new song, a new route, or a new recipe.'),
        ('Anxious', 'Focus on your breath. Inhale for 4 seconds, hold for 7, exhale for 8.'),
        ('Anxious', 'Ground yourself: Name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste.'),
        ('Sad', 'It is okay to not be okay. Be gentle with yourself.'),
        ('Sad', 'Try to get some fresh air, even if it is just opening a window.'),
        ('Sad', 'Listen to some comforting music or watch a favorite movie.'),
        ('Excited', 'Channel that energy! Start a creative project or try something adventurous.'),
        ('Excited', 'Write down what is exciting you—capture this moment of enthusiasm!'),
        ('Grateful', 'Send a thank-you message to someone who has made a difference in your life.'),
        ('Grateful', 'Gratitude is powerful. Take a moment to savor what you appreciate.'),
        ('Tired', 'Rest is not laziness. Give yourself permission to recharge.'),
        ('Tired', 'Try a short 20-minute power nap or some gentle stretching.'),
        ('Angry', 'Take a few deep breaths before reacting. Your feelings are valid.'),
        ('Angry', 'Try physical activity to release the tension—go for a walk or do some exercise.'),
        ('Hopeful', 'Hold onto that hope! Write down one step you can take toward your goal today.'),
        ('Hopeful', 'Hope is the fuel for change. Visualize the positive outcome you are working toward.'),
        ('Stressed', 'Break your tasks into smaller, manageable steps. One thing at a time.'),
        ('Stressed', 'Take a 5-minute break. Step away, stretch, and clear your mind.'),
        ('Loved', 'Cherish this feeling! Share it with someone who matters to you.'),
        ('Loved', 'Love is a gift. Take a moment to appreciate the connections in your life.')
    ]
    for mood, text in tips_data:
        db.session.add(Tip(mood_type=mood, tip_text=text))
    db.session.commit()

    if not Tip.query.filter_by(mood_type='Work').first():
        stress_tips = [
            ('Work', 'Consider time-blocking your day to ensure you have dedicated focus periods and regular breaks.'),
            ('Work', 'Remember to step away from your desk. A 5-minute walk can hit the reset button on your work stress.'),
            ('Relationships', 'Communication is key. Try expressing your feelings using "I" statements rather than "You" statements.'),
            ('Relationships', 'Set healthy boundaries. It is okay to say yes to yourself and no to things that drain your peace of mind.'),
            ('Health', 'Listen to your body. Sometimes the best thing you can do for your health is to rest and recover.'),
            ('Health', 'Try drinking a glass of water and taking five deep breaths right now. Small health habits add up.'),
            ('Finances', 'Focus on what you can control. Track your necessary expenses versus wants to regain a sense of clarity.'),
            ('Finances', 'Financial stress is tough. Try breaking down your money concerns into small, actionable steps.'),
            ('Sleep', 'Create a wind-down routine. Disconnect from screens 30 minutes before bed to signal your brain it is time to sleep.'),
            ('Sleep', 'Keep your bedroom cool, dark, and quiet. Your sleep environment plays a huge role in your sleep quality.')
        ]
        for mood, text in stress_tips:
            db.session.add(Tip(mood_type=mood, tip_text=text))
        db.session.commit()

def get_daily_prompt():
    prompts = [
        "What is one thing that made you smile today?",
        "What is a challenge you overcame recently?",
        "List three things you are grateful for.",
        "How are you feeling right now, really?",
        "What is one small goal for tomorrow?",
        "Who is someone you appreciate and why?",
        "Describe a peaceful moment you had today.",
        "What is a lesson you learned this week?",
        "What does 'self-care' mean to you today?",
        "Write about a positive habit you want to build."
    ]
    return random.choice(prompts)

MINDFUL_FACTS = [
    "Stress is a natural physical and mental reaction to life experiences, not a personal failing.",
    "Practicing mindfulness for just 10 minutes a day can lower stress hormones like cortisol.",
    "Sleep is crucial for mental health; deep sleep helps the brain process emotional information.",
    "Physical activity releases endorphins, which act as natural mood lifters and painkillers.",
    "Taking slow, deep breaths activates the parasympathetic nervous system, inducing a state of calm."
]

def calculate_streak(user):
    entries = db.session.query(JournalEntry.entry_date).filter_by(user_id=user.user_id).order_by(JournalEntry.entry_date.desc()).all()
    if not entries: return 0
    unique_dates = sorted(list(set(entry.entry_date.date() for entry in entries)), reverse=True)
    if not unique_dates: return 0
    
    streak = 0
    today = datetime.utcnow().date()
    
    # Check if latest is today or yesterday
    if unique_dates[0] != today and unique_dates[0] != today - timedelta(days=1):
        return 0
        
    current_consecutive = unique_dates[0]
    streak = 1
    for i in range(1, len(unique_dates)):
        if unique_dates[i] == current_consecutive - timedelta(days=1):
            streak += 1
            current_consecutive = unique_dates[i]
        else:
            break
    return streak







# Remove manual helper function
# def validate_email_domain(email): ... 

# --- Routes ---

# --- Routes ---

@app.before_request
def check_onboarding():
    if current_user.is_authenticated:
        if not getattr(current_user, 'onboarding_completed', True):
            if request.endpoint and request.endpoint not in ['onboarding', 'logout', 'static']:
                return redirect(url_for('onboarding'))

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    if getattr(current_user, 'onboarding_completed', False):
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        triggers = request.form.getlist('stress_triggers')
        current_user.stress_triggers = ','.join(triggers)
        current_user.onboarding_completed = True
        db.session.commit()
        flash("Welcome! Your personalized experience is ready.", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('onboarding.html')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/zen_room')
@login_required
def zen_room():
    return render_template('zen_room.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not email or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('register.html', username=username, email=email)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html', username=username, email=email)
        
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('register.html', username=username, email=email)

        # Validate email with email_validator
        try:
            v = validate_email(email, check_deliverability=True)
            email = v.normalized
        except EmailNotValidError as e:
            flash(str(e), 'error')
            return render_template('register.html', username=username, email=email)

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html', username=username, email=email)
            
        if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"\d", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
             flash('Password must contain uppercase, lowercase, number, and special character.', 'error')
             return render_template('register.html', username=username, email=email)

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('register.html', username=username, email=email)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html', username=username, email=email)
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('All fields are required.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('mindful_fact', None)
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('No account found with that email address.', 'error')
            return render_template('forgot_password.html', email=email)

        # Directly proceed to password reset without OTP
        session['reset_email'] = email
        session['otp_verified'] = True
        flash('Please set your new password.', 'success')
        return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    email = session.get('reset_email')
    otp_verified = session.get('otp_verified')
    if not email or not otp_verified:
        flash('Please complete the verification process first.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')

        if len(new_password) < 8 or \
           not re.search(r"[A-Z]", new_password) or \
           not re.search(r"[a-z]", new_password) or \
           not re.search(r"\d", new_password) or \
           not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            flash('Password must be 8+ chars with uppercase, lowercase, number, and special char.', 'error')
            return render_template('reset_password.html')

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            db.session.commit()

        # Clear session data
        session.pop('reset_email', None)
        session.pop('otp_verified', None)

        flash('Password reset successfully! Please log in with your new password.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        content = request.form.get('content')
        moods = request.form.getlist('mood')
        title = request.form.get('title') or "My Journal Entry"
        mood = ', '.join(moods)

        if content and mood:
            # Fetch a random tip for the first selected mood
            tips = Tip.query.filter_by(mood_type=moods[0]).all()
            if tips:
                selected_tip = random.choice(tips).tip_text
            else:
                selected_tip = "Keep going, you're doing great."

            entry = JournalEntry(
                content=content, mood=mood, title=title,
                author=current_user, entry_date=datetime.utcnow(),
                tips=selected_tip
            )
            db.session.add(entry)
            db.session.commit()
            flash('Journal entry added!')
            return redirect(url_for('dashboard') + '#recent-entries')
            
    entries = JournalEntry.query.filter_by(user_id=current_user.user_id).order_by(JournalEntry.entry_date.desc()).all()
    is_new_user = len(entries) == 0
    streak = calculate_streak(current_user)
    daily_prompt = get_daily_prompt()

    # Personalized tips
    personalized_tip = None
    if getattr(current_user, 'stress_triggers', None):
        triggers = [t for t in current_user.stress_triggers.split(',') if t.strip()]
        if triggers:
            trigger = random.choice(triggers)
            tips = Tip.query.filter_by(mood_type=trigger).all()
            if tips:
                personalized_tip = {
                    'trigger': trigger,
                    'text': random.choice(tips).tip_text
                }

    if 'mindful_fact' not in session:
        session['mindful_fact'] = random.choice(MINDFUL_FACTS)
    mindful_fact = session['mindful_fact']

    return render_template('dashboard.html', entries=entries, streak=streak, daily_prompt=daily_prompt, is_new_user=is_new_user, personalized_tip=personalized_tip, mindful_fact=mindful_fact)

@app.route('/entry/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.user_id:
        flash('You do not have permission to view this entry.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        entry.title = request.form.get('title')
        entry.content = request.form.get('content')
        moods = request.form.getlist('mood')
        entry.mood = ', '.join(moods)
        
        db.session.commit()
        flash('Journal entry updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('entry.html', entry=entry)

@app.route('/entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.user_id:
        flash('You do not have permission to delete this entry.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(entry)
    db.session.commit()
    flash('Journal entry deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/sleep', methods=['GET', 'POST'])
@login_required
def sleep():
    if request.method == 'POST':
        date_str = request.form.get('date')
        hours = request.form.get('hours')
        quality = request.form.get('quality')
        notes = request.form.get('notes')

        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
            hours_slept = float(hours) if hours else 0.0

            if hours_slept > 24:
                flash('Sleep hours cannot be more than 24.', 'error')
            elif hours_slept > 0 and quality:
                log = SleepLog(
                    user_id=current_user.user_id,
                    date=log_date,
                    hours_slept=hours_slept,
                    sleep_quality=quality,
                    notes=notes
                )
                db.session.add(log)
                db.session.commit()
                flash('Sleep log recorded successfully!', 'success')
            else:
                flash('Please provide hours slept and sleep quality.', 'error')
        except ValueError:
             flash('Invalid input. Please check your data.', 'error')
        
        return redirect(request.referrer or url_for('sleep'))

    logs = SleepLog.query.filter_by(user_id=current_user.user_id).order_by(SleepLog.date.desc()).all()
    today_str = datetime.utcnow().date().strftime('%Y-%m-%d')
    return render_template('sleep.html', logs=logs, today=today_str)

@app.route('/trends')
@login_required
def trends():
    # 1. Average Mood Calculation
    entries = JournalEntry.query.filter_by(user_id=current_user.user_id).all()
    mood_map = {'Happy': 5, 'Calm': 4, 'Neutral': 3, 'Anxious': 2, 'Sad': 1, 'Excited': 5, 'Grateful': 5, 'Tired': 2, 'Angry': 1, 'Hopeful': 4, 'Stressed': 2, 'Loved': 5}
    avg_mood_label = "No Data"
    
    if entries:
        total_score = 0
        mood_count = 0
        for entry in entries:
            entry_moods = [m.strip() for m in entry.mood.split(',')]
            for m in entry_moods:
                total_score += mood_map.get(m, 3)
                mood_count += 1
        avg_score = total_score / mood_count if mood_count else 3
        
        if avg_score >= 4.5: avg_mood_label = "Happy"
        elif avg_score >= 3.5: avg_mood_label = "Calm"
        elif avg_score >= 2.5: avg_mood_label = "Neutral"
        elif avg_score >= 1.5: avg_mood_label = "Anxious"
        else: avg_mood_label = "Sad"

    # 2. Consistency Calendar (Last 30 Days)
    today = datetime.utcnow().date()
    current_month_year = today.strftime('%B %Y')
    calendar_data = []
    
    # Get set of all entry dates (just the date part)
    entry_dates = set(entry.entry_date.date() for entry in entries)
    
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        has_entry = day in entry_dates
        calendar_data.append({
            'date': day,
            'has_entry': has_entry,
            'day_label': day.strftime('%b %d'),
            'day_number': day.day
        })

    return render_template('trends.html', avg_mood=avg_mood_label, calendar_data=calendar_data, current_month_year=current_month_year)

@app.route('/api/trends_data')
@login_required
def trends_data():
    entries = JournalEntry.query.filter_by(user_id=current_user.user_id).order_by(JournalEntry.entry_date.asc()).all()
    mood_scores = {'Happy': 5, 'Calm': 4, 'Neutral': 3, 'Anxious': 2, 'Sad': 1}
    data = {
        'dates': [entry.entry_date.strftime('%Y-%m-%d') for entry in entries],
        'scores': [round(sum(mood_scores.get(m.strip(), 3) for m in entry.mood.split(',')) / len(entry.mood.split(',')), 1) for entry in entries]
    }
    return jsonify(data)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            flash('All fields are required.', 'error')
            return redirect(url_for('profile'))

        if not current_user.check_password(old_password):
            flash('Incorrect current password.', 'error')
            return redirect(url_for('profile'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('profile'))

        if len(new_password) < 8 or \
           not re.search(r"[A-Z]", new_password) or \
           not re.search(r"[a-z]", new_password) or \
           not re.search(r"\d", new_password) or \
           not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            flash('Password must be 8+ chars and contain uppercase, lowercase, number, and special char.', 'error')
            return redirect(url_for('profile'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    # delete all journal entries
    JournalEntry.query.filter_by(user_id=current_user.user_id).delete()
    
    # delete user
    user = User.query.get(current_user.user_id)
    db.session.delete(user)
    db.session.commit()
    
    logout_user()
    flash('Your account has been successfully deleted.', 'success')
    return redirect(url_for('index'))

# --- Export Routes ---

@app.route('/export/weekly-report/csv')
@login_required
def export_weekly_report_csv():
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    entries = JournalEntry.query.filter(
        JournalEntry.user_id == current_user.user_id,
        JournalEntry.entry_date >= datetime.combine(week_ago, datetime.min.time())
    ).order_by(JournalEntry.entry_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Title', 'Mood(s)', 'Content', 'Tip'])
    for e in entries:
        writer.writerow([
            e.entry_date.strftime('%Y-%m-%d'),
            e.title or '',
            e.mood,
            e.content,
            e.tips or ''
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=weekly_report_{today}.csv'
    return response


@app.route('/export/weekly-report/pdf')
@login_required
def export_weekly_report_pdf():
    from fpdf import FPDF

    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    entries = JournalEntry.query.filter(
        JournalEntry.user_id == current_user.user_id,
        JournalEntry.entry_date >= datetime.combine(week_ago, datetime.min.time())
    ).order_by(JournalEntry.entry_date.desc()).all()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 12, 'Weekly Wellness Report', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, f'{week_ago.strftime("%b %d, %Y")} - {today.strftime("%b %d, %Y")}  |  {current_user.username}', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Compassionate Framing
    pdf.set_font('Helvetica', 'I', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, "Thank you for taking the time to check in with yourself this week. Remember that all feelings are valid, and tracking your journey is a wonderful act of self-care. Here is a reflection of your week.", align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # Summary
    mood_map = {'Happy': 5, 'Calm': 4, 'Neutral': 3, 'Anxious': 2, 'Sad': 1, 'Excited': 5, 'Grateful': 5, 'Tired': 2, 'Angry': 1, 'Hopeful': 4, 'Stressed': 2, 'Loved': 5}
    positive = negative = neutral = 0
    for e in entries:
        for m in [x.strip() for x in e.mood.split(',')]:
            score = mood_map.get(m, 3)
            if score >= 4: positive += 1
            elif score <= 2: negative += 1
            else: neutral += 1

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Summary', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Total Entries: {len(entries)}    |    Positive: {positive}    |    Neutral: {neutral}    |    Negative: {negative}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)

    # Entries
    if entries:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Journal Entries', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        for e in entries:
            pdf.set_font('Helvetica', 'B', 10)
            title_text = e.title or 'Untitled'
            pdf.cell(0, 7, f'{e.entry_date.strftime("%b %d, %Y")}  -  {title_text}', new_x='LMARGIN', new_y='NEXT')
            pdf.set_font('Helvetica', 'I', 9)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 5, f'Mood: {e.mood}', new_x='LMARGIN', new_y='NEXT')
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 9)
            # Wrap long content
            pdf.multi_cell(0, 5, e.content[:500])
            if e.tips:
                pdf.set_font('Helvetica', 'I', 8)
                pdf.set_text_color(60, 100, 60)
                pdf.multi_cell(0, 5, f'Tip: {e.tips}')
                pdf.set_text_color(0, 0, 0)
            pdf.ln(4)
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 8, 'No entries found for this week.', new_x='LMARGIN', new_y='NEXT')

    pdf_output = pdf.output()
    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=weekly_report_{today}.pdf'
    return response


@app.route('/export/mood-chart/csv')
@login_required
def export_mood_chart_csv():
    entries = JournalEntry.query.filter_by(user_id=current_user.user_id).order_by(JournalEntry.entry_date.asc()).all()
    mood_scores = {'Happy': 5, 'Calm': 4, 'Neutral': 3, 'Anxious': 2, 'Sad': 1, 'Excited': 5, 'Grateful': 5, 'Tired': 2, 'Angry': 1, 'Hopeful': 4, 'Stressed': 2, 'Loved': 5}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Mood(s)', 'Mood Score'])
    for e in entries:
        moods = [m.strip() for m in e.mood.split(',')]
        score = round(sum(mood_scores.get(m, 3) for m in moods) / len(moods), 1)
        writer.writerow([e.entry_date.strftime('%Y-%m-%d'), e.mood, score])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=mood_chart_data_{datetime.utcnow().date()}.csv'
    return response


@app.route('/export/mood-chart/pdf')
@login_required
def export_mood_chart_pdf():
    from fpdf import FPDF

    entries = JournalEntry.query.filter_by(user_id=current_user.user_id).order_by(JournalEntry.entry_date.asc()).all()
    mood_scores = {'Happy': 5, 'Calm': 4, 'Neutral': 3, 'Anxious': 2, 'Sad': 1, 'Excited': 5, 'Grateful': 5, 'Tired': 2, 'Angry': 1, 'Hopeful': 4, 'Stressed': 2, 'Loved': 5}
    today = datetime.utcnow().date()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 12, 'Mood Chart Report', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, f'Generated on {today.strftime("%b %d, %Y")}  |  {current_user.username}', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Compassionate Framing
    pdf.set_font('Helvetica', 'I', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, "Your emotional landscape is unique and ever-changing. Looking back at your mood trends can provide valuable insights and help you nurture your well-being with kindness.", align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    if entries:
        # Mood distribution
        mood_count = {}
        total_score = 0
        total_moods = 0
        for e in entries:
            moods = [m.strip() for m in e.mood.split(',')]
            for m in moods:
                mood_count[m] = mood_count.get(m, 0) + 1
                total_score += mood_scores.get(m, 3)
                total_moods += 1
        avg_score = round(total_score / total_moods, 1) if total_moods else 0

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Overview', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, f'Total Entries: {len(entries)}    |    Average Mood Score: {avg_score} / 5', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)

        # Distribution table
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'Mood Distribution', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(60, 7, 'Mood', border=1)
        pdf.cell(30, 7, 'Count', border=1)
        pdf.cell(40, 7, 'Percentage', border=1, new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        for mood, count in sorted(mood_count.items(), key=lambda x: -x[1]):
            pct = round(count / total_moods * 100, 1)
            pdf.cell(60, 6, mood, border=1)
            pdf.cell(30, 6, str(count), border=1)
            pdf.cell(40, 6, f'{pct}%', border=1, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(6)

        # Timeline table
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'Mood Timeline', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(40, 7, 'Date', border=1)
        pdf.cell(80, 7, 'Mood(s)', border=1)
        pdf.cell(30, 7, 'Score', border=1, new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        for e in entries:
            moods = [m.strip() for m in e.mood.split(',')]
            score = round(sum(mood_scores.get(m, 3) for m in moods) / len(moods), 1)
            pdf.cell(40, 6, e.entry_date.strftime('%Y-%m-%d'), border=1)
            pdf.cell(80, 6, e.mood[:40], border=1)
            pdf.cell(30, 6, str(score), border=1, new_x='LMARGIN', new_y='NEXT')
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 8, 'No mood data available yet.', new_x='LMARGIN', new_y='NEXT')

    pdf_output = pdf.output()
    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=mood_chart_{today}.pdf'
    return response


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Safe migration for adding new columns to existing sqlite db
        try:
            db.session.execute(db.text('SELECT onboarding_completed FROM user LIMIT 1'))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text('ALTER TABLE user ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0'))
                db.session.execute(db.text('ALTER TABLE user ADD COLUMN stress_triggers VARCHAR(255) DEFAULT ""'))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Migration error: {e}")
        seed_tips()
    app.run(host='0.0.0.0', port=5000, debug=True)

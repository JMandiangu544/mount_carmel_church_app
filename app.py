from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from collections import defaultdict
import stripe, calendar

app = Flask(__name__)
app.secret_key = 'sk_test_51SIgmNKM6PVTDCPTS7HuSnaWrazQojY45Fy4LwiID3MeHXpUlQvb63fsFV36zNCMkY4DjEtnS9khzOWN3EVnRKUt00iq1Z9I8f'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# --- Email setup ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'joberthymambu@gmail.com'   # Change this
app.config['MAIL_PASSWORD'] = 'Espoir1*'           # App password recommended
mail = Mail(app)

# --- Stripe setup (optional) ---
stripe.api_key = "sk_test_YOUR_SECRET_KEY"

# --- Database Models ---
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    contributions = db.relationship('Contribution', backref='member')

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'))

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(200))
    sent_date = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.Text)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

# --- Default Data ---
def add_sample_data():
    if not Member.query.first():
        m1 = Member(name="John Doe", email="john@example.com", password="1234")
        m2 = Member(name="Jane Smith", email="jane@example.com", password="1234")
        m3 = Member(name="Michael Brown", email="michael@example.com", password="1234")
        db.session.add_all([m1, m2, m3])
        db.session.commit()
        c1 = Contribution(type="Tithes", amount=100, member_id=m1.id, date=datetime(2025,9,28))
        c2 = Contribution(type="Offering", amount=50, member_id=m1.id, date=datetime(2025,10,2))
        c3 = Contribution(type="Rent", amount=200, member_id=m2.id, date=datetime(2025,10,5))
        db.session.add_all([c1, c2, c3])
        db.session.commit()

def add_admin_account():
    if not Admin.query.first():
        admin = Admin(username="admin", password="church123")
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin account created — username: admin | password: church123")

# --- Reminder Logic ---
def send_rent_reminders():
    current_month = datetime.now().month
    current_year = datetime.now().year
    members = Member.query.all()
    reminded = []

    for m in members:
        rent_this_month = Contribution.query.filter_by(member_id=m.id, type='Rent').filter(
            db.extract('month', Contribution.date)==current_month,
            db.extract('year', Contribution.date)==current_year
        ).first()

        if not rent_this_month:
            subject = "Mount Carmel Church Rent Contribution Reminder"
            message_body = f"""Dear {m.name},

This is a kind reminder from Mount Carmel Church to make your rent contribution for {calendar.month_name[current_month]}.

Thank you for your continued faithfulness and generosity.

Blessings,
Mount Carmel Church Team
"""
            msg = Message(subject=subject, sender=app.config['MAIL_USERNAME'], recipients=[m.email], body=message_body)
            mail.send(msg)
            reminded.append(m.email)
            log_entry = EmailLog(recipient=m.email, subject=subject, message=message_body)
            db.session.add(log_entry)
            db.session.commit()

    print(f"📧 Rent reminders sent to: {', '.join(reminded) if reminded else 'All members have paid'}")

# --- Public Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name, email, password = request.form['name'], request.form['email'], request.form['password']
        if Member.query.filter_by(email=email).first():
            flash('Email already registered','danger')
            return redirect('/register')
        member = Member(name=name, email=email, password=password)
        db.session.add(member)
        db.session.commit()
        flash('Registration successful!','success')
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email, password = request.form['email'], request.form['password']
        member = Member.query.filter_by(email=email, password=password).first()
        if member:
            session['member_id'], session['member_name'] = member.id, member.name
            return redirect('/dashboard')
        flash('Invalid credentials','danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'member_id' not in session: return redirect('/login')
    member = Member.query.get(session['member_id'])
    return render_template('dashboard.html', member=member, contributions=member.contributions)

@app.route('/pay', methods=['POST'])
def pay():
    if 'member_id' not in session: return redirect('/login')
    amount, ctype = float(request.form['amount']), request.form['type']
    contribution = Contribution(type=ctype, amount=amount, member_id=session['member_id'])
    db.session.add(contribution)
    db.session.commit()
    flash(f'Thank you for your {ctype} of ${amount:.2f}','success')
    return redirect('/dashboard')

# --- Admin Authentication ---
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['admin_logged_in'] = True
            flash('Welcome, Admin!', 'success')
            return redirect('/admin')
        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully.', 'info')
    return redirect('/')

# --- Admin Routes ---
@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    contributions = Contribution.query.all()
    totals = defaultdict(float)
    for c in contributions: totals[c.type] += c.amount
    chart_labels, chart_values = list(totals.keys()), list(totals.values())
    return render_template('admin.html', chart_labels=chart_labels, chart_values=chart_values)

@app.route('/admin/email_logs')
def email_logs():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    logs = EmailLog.query.order_by(EmailLog.sent_date.desc()).all()
    return render_template('email_logs.html', logs=logs)

@app.route('/admin/summary')
def admin_summary():
    current_month = datetime.now().month
    current_year = datetime.now().year
    total_members = Member.query.count()
    paid_members = (
        Contribution.query.filter_by(type='Rent')
        .filter(db.extract('month', Contribution.date)==current_month,
                db.extract('year', Contribution.date)==current_year)
        .distinct(Contribution.member_id).count()
    )
    reminded_members = (
        EmailLog.query.filter(EmailLog.subject.contains('Rent'))
        .filter(db.extract('month', EmailLog.sent_date)==current_month,
                db.extract('year', EmailLog.sent_date)==current_year)
        .distinct(EmailLog.recipient).count()
    )
    return {"total_members": total_members, "paid_members": paid_members, "reminded_members": reminded_members}

@app.route('/send_reminders')
def send_reminders():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    send_rent_reminders()
    flash("Manual rent reminders sent successfully!", "info")
    return redirect('/admin')

# --- Scheduler (auto monthly reminders) ---
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(send_rent_reminders, 'cron', day=1, hour=8, minute=0)
scheduler.start()

if __name__ == "__main__":
    db.create_all()
    add_sample_data()
    add_admin_account()
    print("⏰ Scheduler active — automatic rent reminders enabled.")
    app.run(debug=True)

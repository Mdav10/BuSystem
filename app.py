import os
import json
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func, extract
import pandas as pd
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import xlsxwriter

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
CORS(app)

# ============================
# DATABASE MODELS
# ============================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    currency = db.Column(db.String(10), default='FCFA')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    investments = db.relationship('Investment', backref='user', lazy=True)
    livestock = db.relationship('Livestock', backref='user', lazy=True)
    assets = db.relationship('Asset', backref='user', lazy=True)
    goals = db.relationship('Goal', backref='user', lazy=True)
    budgets = db.relationship('Budget', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    rules = db.relationship('FinancialRule', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # income, expense, transfer, investment
    category = db.Column(db.String(50), nullable=False)
    sub_category = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    reference = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'category': self.category,
            'sub_category': self.sub_category,
            'amount': self.amount,
            'description': self.description,
            'date': self.date.strftime('%Y-%m-%d %H:%M'),
            'reference': self.reference
        }

class Investment(db.Model):
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    investment_id = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # Animal, Crop, Business, Stock
    sub_type = db.Column(db.String(50))
    capital = db.Column(db.Float, nullable=False)
    expected_roi = db.Column(db.Float)
    current_value = db.Column(db.Float)
    expected_exit_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Running')  # Running, Sold, Lost, Completed
    sell_price = db.Column(db.Float, default=0)
    profit = db.Column(db.Float, default=0)
    roi_actual = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    sell_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    def calculate_roi(self):
        if self.sell_price > 0 and self.capital > 0:
            self.profit = self.sell_price - self.capital
            self.roi_actual = (self.profit / self.capital) * 100
        return self.roi_actual
    
    def to_dict(self):
        return {
            'id': self.id,
            'investment_id': self.investment_id,
            'type': self.type,
            'sub_type': self.sub_type,
            'capital': self.capital,
            'expected_roi': self.expected_roi,
            'current_value': self.current_value,
            'status': self.status,
            'sell_price': self.sell_price,
            'profit': self.profit,
            'roi_actual': self.roi_actual,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d'),
            'expected_exit_date': self.expected_exit_date.strftime('%Y-%m-%d') if self.expected_exit_date else None
        }

class Livestock(db.Model):
    __tablename__ = 'livestock'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tag = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    breed = db.Column(db.String(50))
    purchase_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    current_value = db.Column(db.Float)
    food_cost = db.Column(db.Float, default=0)
    medicine_cost = db.Column(db.Float, default=0)
    other_cost = db.Column(db.Float, default=0)
    expected_sell_price = db.Column(db.Float)
    expected_sell_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Active')  # Active, Sold, Dead, Ready
    actual_sell_price = db.Column(db.Float, default=0)
    profit = db.Column(db.Float, default=0)
    birth_date = db.Column(db.DateTime)
    death_date = db.Column(db.DateTime)
    last_vaccination = db.Column(db.DateTime)
    next_vaccination = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    def calculate_profit(self):
        if self.actual_sell_price > 0:
            total_cost = self.purchase_price + self.food_cost + self.medicine_cost + self.other_cost
            self.profit = self.actual_sell_price - total_cost
        return self.profit
    
    def to_dict(self):
        return {
            'id': self.id,
            'tag': self.tag,
            'type': self.type,
            'breed': self.breed,
            'purchase_price': self.purchase_price,
            'current_value': self.current_value,
            'status': self.status,
            'expected_sell_date': self.expected_sell_date.strftime('%Y-%m-%d') if self.expected_sell_date else None,
            'profit': self.profit
        }

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    sub_category = db.Column(db.String(50))
    purchase_price = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, nullable=False)
    depreciation_rate = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(100))
    owner = db.Column(db.String(50))
    condition = db.Column(db.String(20), default='Good')  # Excellent, Good, Fair, Poor
    notes = db.Column(db.Text)
    
    def calculate_depreciation(self):
        if self.depreciation_rate > 0:
            years_held = (datetime.utcnow() - self.purchase_date).days / 365
            self.current_value = self.purchase_price * (1 - self.depreciation_rate * years_held)
            if self.current_value < 0:
                self.current_value = 0
        return self.current_value

class Goal(db.Model):
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    deadline = db.Column(db.DateTime)
    category = db.Column(db.String(50))
    priority = db.Column(db.Integer, default=1)  # 1=High, 2=Medium, 3=Low
    status = db.Column(db.String(20), default='Active')
    progress = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def update_progress(self):
        if self.target_amount > 0:
            self.progress = min((self.current_amount / self.target_amount) * 100, 100)
            if self.progress >= 100:
                self.status = 'Completed'
                self.completed_at = datetime.utcnow()
        return self.progress

class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    expected_amount = db.Column(db.Float, nullable=False)
    actual_amount = db.Column(db.Float, default=0)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    difference = db.Column(db.Float, default=0)
    
    def calculate_difference(self):
        self.difference = self.actual_amount - self.expected_amount
        return self.difference

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')
    is_read = db.Column(db.Boolean, default=False)
    is_urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

class FinancialRule(db.Model):
    __tablename__ = 'financial_rules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # investment, spending, savings, emergency
    condition_type = db.Column(db.String(50))  # percentage, amount, date
    condition_value = db.Column(db.Float)
    condition_operator = db.Column(db.String(10))  # >, <, >=, <=, ==
    action_type = db.Column(db.String(50))  # warn, block, auto_adjust
    action_message = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    triggered_at = db.Column(db.DateTime)

class FinancialRatio(db.Model):
    __tablename__ = 'financial_ratios'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    target = db.Column(db.Float)
    status = db.Column(db.String(20))
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    period = db.Column(db.String(20))  # daily, weekly, monthly, yearly

# ============================
# AUTHENTICATION
# ============================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# ============================
# DASHBOARD
# ============================

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id
    today = datetime.now()
    
    # Cash & Assets
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income'
    ).scalar() or 0
    
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense'
    ).scalar() or 0
    
    current_cash = total_income - total_expenses
    
    total_assets_value = db.session.query(func.sum(Asset.current_value)).filter(
        Asset.user_id == user_id
    ).scalar() or 0
    
    total_investments = db.session.query(func.sum(Investment.capital)).filter(
        Investment.user_id == user_id,
        Investment.status == 'Running'
    ).scalar() or 0
    
    net_worth = current_cash + total_assets_value + total_investments
    
    # Monthly
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income',
        extract('month', Transaction.date) == today.month,
        extract('year', Transaction.date) == today.year
    ).scalar() or 0
    
    monthly_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        extract('month', Transaction.date) == today.month,
        extract('year', Transaction.date) == today.year
    ).scalar() or 0
    
    # ROI
    sold_investments = Investment.query.filter_by(user_id=user_id, status='Sold').all()
    total_roi = 0
    if sold_investments:
        total_profit = sum(i.profit for i in sold_investments)
        total_capital = sum(i.capital for i in sold_investments)
        if total_capital > 0:
            total_roi = (total_profit / total_capital) * 100
    
    # Livestock
    active_livestock = Livestock.query.filter_by(user_id=user_id, status='Active').count()
    ready_livestock = Livestock.query.filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Active',
        Livestock.expected_sell_date <= today
    ).count()
    
    # Goals
    active_goals = Goal.query.filter_by(user_id=user_id, status='Active').all()
    avg_goal_progress = sum(g.progress for g in active_goals) / len(active_goals) if active_goals else 0
    
    # Emergency Fund (3 months expenses)
    avg_monthly_expense = db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense'
    ).scalar() or 0
    emergency_fund_ratio = (current_cash / (avg_monthly_expense * 3)) * 100 if avg_monthly_expense > 0 else 0
    emergency_fund_ratio = min(emergency_fund_ratio, 100)
    
    # Alerts
    alerts = []
    
    # Ready to sell livestock
    for animal in Livestock.query.filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Active',
        Livestock.expected_sell_date <= today
    ).limit(5).all():
        alerts.append(f"🐄 {animal.tag} ({animal.type}) is ready to sell!")
    
    # Budget alerts
    budgets = Budget.query.filter_by(user_id=user_id, month=today.month, year=today.year).all()
    for budget in budgets:
        if budget.actual_amount > budget.expected_amount * 1.1:
            alerts.append(f"⚠️ {budget.category} budget exceeded by {budget.actual_amount - budget.expected_amount:,.0f} {current_user.currency}")
    
    # Investment alerts
    overdue_investments = Investment.query.filter(
        Investment.user_id == user_id,
        Investment.status == 'Running',
        Investment.expected_exit_date <= today
    ).limit(3).all()
    for inv in overdue_investments:
        alerts.append(f"📊 Investment {inv.investment_id} ({inv.type}) is overdue!")
    
    # Vaccination alerts
    next_week = today + timedelta(days=7)
    vaccination_due = Livestock.query.filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Active',
        Livestock.next_vaccination <= next_week,
        Livestock.next_vaccination >= today
    ).limit(3).all()
    for animal in vaccination_due:
        alerts.append(f"💉 {animal.tag} ({animal.type}) vaccination due on {animal.next_vaccination.strftime('%Y-%m-%d')}")
    
    return render_template('dashboard.html',
        current_cash=current_cash,
        total_assets=total_assets_value,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        total_investments=total_investments,
        active_livestock=active_livestock,
        ready_livestock=ready_livestock,
        roi=total_roi,
        goal_progress=avg_goal_progress,
        emergency_fund=emergency_fund_ratio,
        alerts=alerts[:10],
        user=current_user
    )

# ============================
# MODULE 2: CASH FLOW MANAGER
# ============================

@app.route('/cashflow')
@login_required
def cashflow():
    return render_template('cashflow.html', user=current_user)

@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(100).all()
    return jsonify([t.to_dict() for t in transactions])

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    data = request.json
    transaction = Transaction(
        user_id=current_user.id,
        type=data.get('type'),
        category=data.get('category'),
        sub_category=data.get('sub_category'),
        amount=float(data.get('amount')),
        description=data.get('description'),
        date=datetime.strptime(data.get('date'), '%Y-%m-%d') if data.get('date') else datetime.utcnow(),
        reference=data.get('reference')
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'status': 'success', 'id': transaction.id})

@app.route('/api/transactions/<int:id>', methods=['DELETE'])
@login_required
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'status': 'success'})

# ============================
# MODULE 3: INVESTMENT MANAGER
# ============================

@app.route('/investments')
@login_required
def investments():
    return render_template('investments.html', user=current_user)

@app.route('/api/investments', methods=['GET'])
@login_required
def get_investments():
    investments = Investment.query.filter_by(user_id=current_user.id).order_by(Investment.purchase_date.desc()).all()
    return jsonify([inv.to_dict() for inv in investments])

@app.route('/api/investments', methods=['POST'])
@login_required
def add_investment():
    data = request.json
    import random
    investment_id = f"{data.get('type')[:3].upper()}{random.randint(100, 999)}"
    
    investment = Investment(
        user_id=current_user.id,
        investment_id=investment_id,
        type=data.get('type'),
        sub_type=data.get('sub_type'),
        capital=float(data.get('capital')),
        expected_roi=float(data.get('expected_roi', 0)),
        current_value=float(data.get('capital')),
        expected_exit_date=datetime.strptime(data.get('expected_exit_date'), '%Y-%m-%d') if data.get('expected_exit_date') else None,
        purchase_date=datetime.strptime(data.get('purchase_date'), '%Y-%m-%d') if data.get('purchase_date') else datetime.utcnow(),
        notes=data.get('notes')
    )
    db.session.add(investment)
    db.session.commit()
    return jsonify({'status': 'success', 'id': investment.id, 'investment_id': investment_id})

@app.route('/api/investments/<int:id>/sell', methods=['POST'])
@login_required
def sell_investment(id):
    investment = Investment.query.get_or_404(id)
    if investment.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    investment.sell_price = float(data.get('sell_price'))
    investment.sell_date = datetime.utcnow()
    investment.status = 'Sold'
    investment.calculate_roi()
    
    db.session.commit()
    return jsonify({'status': 'success', 'roi': investment.roi_actual})

# ============================
# MODULE 4: LIVESTOCK MANAGER
# ============================

@app.route('/livestock')
@login_required
def livestock():
    return render_template('livestock.html', user=current_user)

@app.route('/api/livestock', methods=['GET'])
@login_required
def get_livestock():
    livestock = Livestock.query.filter_by(user_id=current_user.id).order_by(Livestock.purchase_date.desc()).all()
    return jsonify([l.to_dict() for l in livestock])

@app.route('/api/livestock', methods=['POST'])
@login_required
def add_livestock():
    data = request.json
    animal = Livestock(
        user_id=current_user.id,
        tag=data.get('tag'),
        type=data.get('type'),
        breed=data.get('breed'),
        purchase_price=float(data.get('purchase_price')),
        current_value=float(data.get('purchase_price')),
        expected_sell_price=float(data.get('expected_sell_price', 0)),
        expected_sell_date=datetime.strptime(data.get('expected_sell_date'), '%Y-%m-%d') if data.get('expected_sell_date') else None,
        notes=data.get('notes')
    )
    db.session.add(animal)
    db.session.commit()
    return jsonify({'status': 'success', 'id': animal.id})

@app.route('/api/livestock/<int:id>', methods=['PUT'])
@login_required
def update_livestock(id):
    animal = Livestock.query.get_or_404(id)
    if animal.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    if 'food_cost' in data:
        animal.food_cost = float(data['food_cost'])
    if 'medicine_cost' in data:
        animal.medicine_cost = float(data['medicine_cost'])
    if 'current_value' in data:
        animal.current_value = float(data['current_value'])
    if 'status' in data:
        animal.status = data['status']
        if data['status'] == 'Sold' and 'actual_sell_price' in data:
            animal.actual_sell_price = float(data['actual_sell_price'])
            animal.calculate_profit()
    
    db.session.commit()
    return jsonify({'status': 'success'})

# ============================
# MODULE 5: ASSET MANAGER
# ============================

@app.route('/assets')
@login_required
def assets():
    return render_template('assets.html', user=current_user)

@app.route('/api/assets', methods=['GET'])
@login_required
def get_assets():
    assets = Asset.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': a.id,
        'name': a.name,
        'category': a.category,
        'purchase_price': a.purchase_price,
        'current_value': a.current_value,
        'location': a.location,
        'condition': a.condition
    } for a in assets])

@app.route('/api/assets', methods=['POST'])
@login_required
def add_asset():
    data = request.json
    asset = Asset(
        user_id=current_user.id,
        name=data.get('name'),
        category=data.get('category'),
        sub_category=data.get('sub_category'),
        purchase_price=float(data.get('purchase_price')),
        current_value=float(data.get('purchase_price')),
        depreciation_rate=float(data.get('depreciation_rate', 0)),
        location=data.get('location'),
        owner=data.get('owner'),
        condition=data.get('condition', 'Good')
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify({'status': 'success', 'id': asset.id})

# ============================
# MODULE 6: GOAL PLANNER
# ============================

@app.route('/goals')
@login_required
def goals():
    return render_template('goals.html', user=current_user)

@app.route('/api/goals', methods=['GET'])
@login_required
def get_goals():
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': g.id,
        'name': g.name,
        'target_amount': g.target_amount,
        'current_amount': g.current_amount,
        'deadline': g.deadline.strftime('%Y-%m-%d') if g.deadline else None,
        'progress': g.progress,
        'status': g.status
    } for g in goals])

@app.route('/api/goals', methods=['POST'])
@login_required
def add_goal():
    data = request.json
    goal = Goal(
        user_id=current_user.id,
        name=data.get('name'),
        target_amount=float(data.get('target_amount')),
        deadline=datetime.strptime(data.get('deadline'), '%Y-%m-%d') if data.get('deadline') else None,
        category=data.get('category'),
        priority=int(data.get('priority', 1))
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify({'status': 'success', 'id': goal.id})

@app.route('/api/goals/<int:id>/update', methods=['POST'])
@login_required
def update_goal_progress(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    goal.current_amount = float(data.get('current_amount'))
    goal.update_progress()
    db.session.commit()
    return jsonify({'status': 'success', 'progress': goal.progress})

# ============================
# MODULE 7: BUDGET MANAGER
# ============================

@app.route('/budget')
@login_required
def budget():
    return render_template('budget.html', user=current_user)

@app.route('/api/budget', methods=['GET'])
@login_required
def get_budget():
    today = datetime.now()
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=today.month,
        year=today.year
    ).all()
    return jsonify([{
        'id': b.id,
        'category': b.category,
        'type': b.type,
        'expected_amount': b.expected_amount,
        'actual_amount': b.actual_amount,
        'difference': b.difference
    } for b in budgets])

@app.route('/api/budget', methods=['POST'])
@login_required
def set_budget():
    data = request.json
    today = datetime.now()
    
    budget = Budget.query.filter_by(
        user_id=current_user.id,
        category=data.get('category'),
        month=today.month,
        year=today.year
    ).first()
    
    if budget:
        budget.expected_amount = float(data.get('expected_amount'))
    else:
        budget = Budget(
            user_id=current_user.id,
            category=data.get('category'),
            type=data.get('type'),
            expected_amount=float(data.get('expected_amount')),
            month=today.month,
            year=today.year
        )
        db.session.add(budget)
    
    db.session.commit()
    return jsonify({'status': 'success'})

# ============================
# MODULE 8: ACCOUNTING & REPORTS
# ============================

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html', user=current_user)

@app.route('/api/reports/<report_type>')
@login_required
def get_report_data(report_type):
    user_id = current_user.id
    
    if report_type == 'income_statement':
        income = db.session.query(
            func.sum(Transaction.amount).label('total'),
            Transaction.category
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'income'
        ).group_by(Transaction.category).all()
        
        expenses = db.session.query(
            func.sum(Transaction.amount).label('total'),
            Transaction.category
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense'
        ).group_by(Transaction.category).all()
        
        return jsonify({
            'income': [{'category': i[1], 'total': i[0]} for i in income],
            'expenses': [{'category': i[1], 'total': i[0]} for i in expenses]
        })
    
    elif report_type == 'balance_sheet':
        total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        net_worth = total_assets + total_income - total_expenses
        
        return jsonify({
            'total_assets': total_assets,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_worth': net_worth
        })
    
    elif report_type == 'cash_flow':
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date).all()
        return jsonify([t.to_dict() for t in transactions])
    
    return jsonify({'error': 'Invalid report type'}), 400

@app.route('/api/reports/export/<report_type>/<format>')
@login_required
def export_report(report_type, format):
    user_id = current_user.id
    
    if format == 'pdf':
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1)
        story.append(Paragraph(f"{report_type.replace('_', ' ').title()} Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Get data
        if report_type == 'transactions':
            transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(100).all()
            data = [['Date', 'Type', 'Category', 'Amount', 'Description']]
            for t in transactions:
                data.append([
                    t.date.strftime('%Y-%m-%d'),
                    t.type,
                    t.category,
                    f"{t.amount:,.0f}",
                    t.description or ''
                ])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf", mimetype='application/pdf')
    
    elif format == 'excel':
        if report_type == 'transactions':
            transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
            data = []
            for t in transactions:
                data.append({
                    'Date': t.date.strftime('%Y-%m-%d'),
                    'Type': t.type,
                    'Category': t.category,
                    'Amount': t.amount,
                    'Description': t.description or ''
                })
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Transactions', index=False)
            output.seek(0)
            return send_file(output, as_attachment=True, download_name=f"{report_type}_{datetime.now().strftime('%Y%m%d')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    return jsonify({'error': 'Invalid format'}), 400

# ============================
# MODULE 9: FINANCIAL RATIOS
# ============================

@app.route('/ratios')
@login_required
def ratios():
    return render_template('ratios.html', user=current_user)

@app.route('/api/ratios')
@login_required
def calculate_ratios():
    user_id = current_user.id
    
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 1
    
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
    
    total_investments = db.session.query(func.sum(Investment.capital)).filter(
        Investment.user_id == user_id, Investment.status == 'Running'
    ).scalar() or 0
    
    sold_investments = Investment.query.filter_by(user_id=user_id, status='Sold').all()
    total_profit = sum(i.profit for i in sold_investments)
    total_capital = sum(i.capital for i in sold_investments) or 1
    
    savings = total_income - total_expenses
    
    ratios = {
        'roi': (total_profit / total_capital) * 100,
        'profit_margin': (savings / total_income) * 100 if total_income > 0 else 0,
        'savings_ratio': (savings / total_income) * 100 if total_income > 0 else 0,
        'debt_ratio': 0,  # Would need debt tracking
        'asset_growth': 0,  # Would need historical data
        'capital_turnover': (total_income / total_assets) if total_assets > 0 else 0,
        'net_worth_growth': 0,
        'investment_success_rate': (len([i for i in sold_investments if i.profit > 0]) / len(sold_investments) * 100) if sold_investments else 0
    }
    
    return jsonify(ratios)

# ============================
# MODULE 10: ANALYTICS
# ============================

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html', user=current_user)

@app.route('/api/analytics/<chart_type>')
@login_required
def get_analytics(chart_type):
    user_id = current_user.id
    
    if chart_type == 'monthly_income':
        data = db.session.query(
            extract('month', Transaction.date).label('month'),
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'income',
            extract('year', Transaction.date) == datetime.now().year
        ).group_by('month').order_by('month').all()
        return jsonify([{'month': int(i[0]), 'total': float(i[1])} for i in data])
    
    elif chart_type == 'asset_distribution':
        data = db.session.query(
            Asset.category,
            func.sum(Asset.current_value).label('total')
        ).filter(Asset.user_id == user_id).group_by(Asset.category).all()
        return jsonify([{'category': i[0], 'total': float(i[1])} for i in data])
    
    elif chart_type == 'goal_progress':
        goals = Goal.query.filter_by(user_id=user_id).all()
        return jsonify([{'name': g.name, 'progress': g.progress} for g in goals])
    
    return jsonify([])

# ============================
# MODULE 11: NOTIFICATIONS
# ============================

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html', user=current_user)

@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@app.route('/api/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success'})

# ============================
# MODULE 12: DECISION ENGINE (AI)
# ============================

@app.route('/decisions')
@login_required
def decisions():
    return render_template('decisions.html', user=current_user)

@app.route('/api/decisions')
@login_required
def get_decisions():
    user_id = current_user.id
    
    recommendations = []
    
    # Check livestock ROI
    livestock_data = Livestock.query.filter_by(user_id=user_id).all()
    if livestock_data:
        avg_profit = sum(l.profit for l in livestock_data if l.status == 'Sold') / max(1, len([l for l in livestock_data if l.status == 'Sold']))
        if avg_profit > 0:
            best_type = db.session.query(
                Livestock.type,
                func.avg(Livestock.profit).label('avg_profit')
            ).filter(
                Livestock.user_id == user_id,
                Livestock.status == 'Sold'
            ).group_by(Livestock.type).order_by(func.avg(Livestock.profit).desc()).first()
            if best_type:
                recommendations.append({
                    'title': f'📈 Focus on {best_type[0]}',
                    'message': f'Your {best_type[0]} investments show the highest average profit. Consider expanding this area.',
                    'type': 'opportunity'
                })
    
    # Check budget overruns
    today = datetime.now()
    over_budget = Budget.query.filter(
        Budget.user_id == user_id,
        Budget.month == today.month,
        Budget.year == today.year,
        Budget.actual_amount > Budget.expected_amount
    ).all()
    if over_budget:
        for b in over_budget[:3]:
            recommendations.append({
                'title': f'⚠️ Reduce {b.category} spending',
                'message': f'You\'ve exceeded {b.category} budget by {b.actual_amount - b.expected_amount:,.0f} {current_user.currency}. Consider cutting back.',
                'type': 'warning'
            })
    
    # Investment opportunities
    investments = Investment.query.filter_by(user_id=user_id, status='Running').all()
    if investments:
        avg_roi = sum(i.expected_roi or 0 for i in investments) / len(investments)
        if avg_roi > 30:
            recommendations.append({
                'title': '🚀 Investment Opportunity',
                'message': f'Your current investments average {avg_roi:.1f}% ROI. Consider reinvesting profits.',
                'type': 'opportunity'
            })
    
    # Emergency fund check
    total_cash = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    monthly_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        extract('month', Transaction.date) == today.month
    ).scalar() or 0
    emergency_months = total_cash / monthly_expenses if monthly_expenses > 0 else 0
    if emergency_months < 3:
        recommendations.append({
            'title': '🛡️ Build Emergency Fund',
            'message': f'You only have {emergency_months:.1f} months of expenses saved. Aim for 3-6 months.',
            'type': 'warning'
        })
    
    return jsonify(recommendations[:5])

# ============================
# MODULE 13: RISK MANAGER
# ============================

@app.route('/risk')
@login_required
def risk():
    return render_template('risk.html', user=current_user)

@app.route('/api/risk')
@login_required
def get_risk_analysis():
    user_id = current_user.id
    
    # Calculate risk metrics
    total_investments = Investment.query.filter_by(user_id=user_id).count()
    running_investments = Investment.query.filter_by(user_id=user_id, status='Running').count()
    
    if total_investments > 0:
        high_risk = len([i for i in Investment.query.filter_by(user_id=user_id).all() if i.type in ['Stock', 'Crop']])
        medium_risk = len([i for i in Investment.query.filter_by(user_id=user_id).all() if i.type == 'Business'])
        low_risk = len([i for i in Investment.query.filter_by(user_id=user_id).all() if i.type == 'Animal'])
    else:
        high_risk = medium_risk = low_risk = 0
    
    # Livestock health risk
    livestock = Livestock.query.filter_by(user_id=user_id).all()
    disease_risk = len([l for l in livestock if l.status == 'Active' and l.notes and 'sick' in l.notes.lower()])
    
    # Cash reserve
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    
    risk_analysis = {
        'high_risk_investments': high_risk,
        'medium_risk_investments': medium_risk,
        'low_risk_investments': low_risk,
        'disease_risk': disease_risk,
        'cash_reserve': total_income * 0.2,  # 20% of income as reserve
        'diversification_score': min((len(set(i.type for i in Investment.query.filter_by(user_id=user_id).all())) / 4) * 100, 100),
        'overall_risk': 'Low' if high_risk < 2 else 'Medium' if high_risk < 5 else 'High'
    }
    
    return jsonify(risk_analysis)

# ============================
# MODULE 14: TIMELINE
# ============================

@app.route('/timeline')
@login_required
def timeline():
    return render_template('timeline.html', user=current_user)

@app.route('/api/timeline')
@login_required
def get_timeline():
    user_id = current_user.id
    
    events = []
    
    # Transactions
    for t in Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(50).all():
        events.append({
            'date': t.date.strftime('%Y-%m-%d'),
            'type': 'transaction',
            'title': f"{t.type.capitalize()}: {t.category}",
            'description': f"{t.amount:,.0f} {current_user.currency} - {t.description or ''}",
            'icon': '💰'
        })
    
    # Investments
    for i in Investment.query.filter_by(user_id=user_id).order_by(Investment.purchase_date.desc()).limit(30).all():
        events.append({
            'date': i.purchase_date.strftime('%Y-%m-%d'),
            'type': 'investment',
            'title': f"Investment: {i.investment_id}",
            'description': f"{i.type} - {i.capital:,.0f} {current_user.currency}",
            'icon': '📊'
        })
    
    # Livestock
    for l in Livestock.query.filter_by(user_id=user_id).order_by(Livestock.purchase_date.desc()).limit(30).all():
        events.append({
            'date': l.purchase_date.strftime('%Y-%m-%d'),
            'type': 'livestock',
            'title': f"Added: {l.type} - {l.tag}",
            'description': f"Purchased for {l.purchase_price:,.0f} {current_user.currency}",
            'icon': '🐄'
        })
    
    # Goals
    for g in Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).limit(20).all():
        events.append({
            'date': g.created_at.strftime('%Y-%m-%d'),
            'type': 'goal',
            'title': f"Goal: {g.name}",
            'description': f"Target: {g.target_amount:,.0f} {current_user.currency}",
            'icon': '🎯'
        })
    
    events.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(events[:100])

# ============================
# MODULE 15: EXPORT OPTIONS
# ============================

@app.route('/exports')
@login_required
def exports():
    return render_template('exports.html', user=current_user)

# ============================
# FINANCIAL RULES ENGINE (FOR)
# ============================

@app.route('/rules')
@login_required
def rules():
    return render_template('rules.html', user=current_user)

@app.route('/api/rules', methods=['GET'])
@login_required
def get_rules():
    rules = FinancialRule.query.filter_by(user_id=current_user.id, is_active=True).all()
    return jsonify([{
        'id': r.id,
        'name': r.name,
        'category': r.category,
        'condition_type': r.condition_type,
        'condition_value': r.condition_value,
        'condition_operator': r.condition_operator,
        'action_message': r.action_message
    } for r in rules])

@app.route('/api/rules', methods=['POST'])
@login_required
def add_rule():
    data = request.json
    rule = FinancialRule(
        user_id=current_user.id,
        name=data.get('name'),
        category=data.get('category'),
        condition_type=data.get('condition_type'),
        condition_value=float(data.get('condition_value')),
        condition_operator=data.get('condition_operator'),
        action_type=data.get('action_type', 'warn'),
        action_message=data.get('action_message')
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({'status': 'success', 'id': rule.id})

@app.route('/api/rules/check')
@login_required
def check_rules():
    user_id = current_user.id
    alerts = []
    
    rules = FinancialRule.query.filter_by(user_id=user_id, is_active=True).all()
    
    for rule in rules:
        # Check different conditions
        if rule.category == 'investment':
            investments = Investment.query.filter_by(user_id=user_id, status='Running').all()
            if rule.condition_type == 'percentage':
                total_capital = sum(i.capital for i in investments)
                if total_capital > 0:
                    for inv in investments:
                        percentage = (inv.capital / total_capital) * 100
                        if rule.condition_operator == '>' and percentage > rule.condition_value:
                            alerts.append(f"⚠️ {rule.name}: {inv.type} exceeds {rule.condition_value}% of total investments")
        
        elif rule.category == 'spending':
            today = datetime.now()
            monthly_expenses = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense',
                extract('month', Transaction.date) == today.month
            ).scalar() or 0
            
            monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'income',
                extract('month', Transaction.date) == today.month
            ).scalar() or 1
            
            spending_ratio = (monthly_expenses / monthly_income) * 100
            if rule.condition_operator == '>' and spending_ratio > rule.condition_value:
                alerts.append(f"⚠️ {rule.name}: Spending ratio at {spending_ratio:.1f}% exceeds {rule.condition_value}%")
        
        elif rule.category == 'emergency':
            total_cash = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'income'
            ).scalar() or 0
            monthly_avg = db.session.query(func.avg(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense'
            ).scalar() or 1
            emergency_months = total_cash / monthly_avg if monthly_avg > 0 else 0
            
            if rule.condition_operator == '<' and emergency_months < rule.condition_value:
                alerts.append(f"⚠️ {rule.name}: Emergency fund only covers {emergency_months:.1f} months (target: {rule.condition_value})")
    
    return jsonify(alerts)

# ============================
# INITIALIZE DATABASE
# ============================

@app.cli.command('init-db')
def init_db():
    """Initialize database with default user"""
    db.create_all()
    if not User.query.filter_by(username='MCM').first():
        user = User(
            username='MCM',
            full_name='System Administrator',
            currency='FCFA'
        )
        user.set_password('0880Mcm+_+')
        db.session.add(user)
        db.session.commit()
        print("✅ Default user 'MCM' created successfully!")
    
    # Add default financial rules
    if FinancialRule.query.count() == 0:
        rules = [
            FinancialRule(
                user_id=1,
                name='Investment Diversification',
                category='investment',
                condition_type='percentage',
                condition_value=40,
                condition_operator='>',
                action_type='warn',
                action_message='Do not invest more than 40% in one type'
            ),
            FinancialRule(
                user_id=1,
                name='Emergency Fund Minimum',
                category='emergency',
                condition_type='months',
                condition_value=3,
                condition_operator='<',
                action_type='warn',
                action_message='Keep at least 3 months of expenses as emergency fund'
            ),
            FinancialRule(
                user_id=1,
                name='Monthly Spending Limit',
                category='spending',
                condition_type='percentage',
                condition_value=80,
                condition_operator='>',
                action_type='warn',
                action_message='Do not spend more than 80% of monthly income'
            )
        ]
        for rule in rules:
            db.session.add(rule)
        db.session.commit()
        print("✅ Default financial rules created!")
    
    print("🎉 Database initialized successfully!")

# ============================
# RUN APP
# ============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

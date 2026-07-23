import os
import io
import csv
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, send_from_directory, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func, extract, text
import json
import random

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
CORS(app)

# ============================
# DATABASE MODELS
# ============================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    currency = db.Column(db.String(10), default='FCFA')
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='admin')  # superadmin, admin, viewer
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'category': self.category,
            'amount': self.amount,
            'description': self.description,
            'date': self.date.strftime('%Y-%m-%d %H:%M')
        }

class Investment(db.Model):
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    investment_id = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    sub_type = db.Column(db.String(50))
    capital = db.Column(db.Float, nullable=False)
    expected_roi = db.Column(db.Float)
    current_value = db.Column(db.Float)
    expected_exit_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Running')
    sell_price = db.Column(db.Float, default=0)
    profit = db.Column(db.Float, default=0)
    roi_actual = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    sell_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
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
    expected_sell_price = db.Column(db.Float)
    expected_sell_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Active')
    actual_sell_price = db.Column(db.Float, default=0)
    profit = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    
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
    condition = db.Column(db.String(20), default='Good')
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'purchase_price': self.purchase_price,
            'current_value': self.current_value,
            'location': self.location,
            'condition': self.condition
        }

class Goal(db.Model):
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    deadline = db.Column(db.DateTime)
    category = db.Column(db.String(50))
    priority = db.Column(db.Integer, default=1)
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
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'deadline': self.deadline.strftime('%Y-%m-%d') if self.deadline else None,
            'progress': self.progress,
            'status': self.status,
            'category': self.category,
            'priority': self.priority
        }

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
    status = db.Column(db.String(20), default='pending')
    status_updated_at = db.Column(db.DateTime)
    
    def calculate_difference(self):
        self.difference = self.actual_amount - self.expected_amount
        return self.difference
    
    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'type': self.type,
            'expected_amount': self.expected_amount,
            'actual_amount': self.actual_amount,
            'difference': self.difference,
            'month': self.month,
            'year': self.year,
            'status': self.status,
            'status_updated_at': self.status_updated_at.strftime('%Y-%m-%d %H:%M') if self.status_updated_at else None
        }

class Liability(db.Model):
    __tablename__ = 'liabilities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'amount': self.amount,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'paid_at': self.paid_at.strftime('%Y-%m-%d') if self.paid_at else None,
            'notes': self.notes
        }

class FinancialRule(db.Model):
    __tablename__ = 'financial_rules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    condition_type = db.Column(db.String(50))
    condition_value = db.Column(db.Float)
    condition_operator = db.Column(db.String(10))
    action_type = db.Column(db.String(50), default='warn')
    action_message = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'condition_type': self.condition_type,
            'condition_value': self.condition_value,
            'condition_operator': self.condition_operator,
            'action_message': self.action_message
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

# ============================
# NEW TABLES: PRODUCTS, CLIENTS, SALES
# ============================

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, default=0)
    category = db.Column(db.String(50))
    stock_quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), default='piece')
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'cost_price': self.cost_price,
            'category': self.category,
            'stock_quantity': self.stock_quantity,
            'min_stock_level': self.min_stock_level,
            'unit': self.unit,
            'admin_id': self.admin_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_active': self.is_active
        }

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    location = db.Column(db.String(200))
    total_purchases = db.Column(db.Float, default=0)
    purchase_count = db.Column(db.Integer, default=0)
    last_purchase_date = db.Column(db.DateTime)
    is_trusted = db.Column(db.Boolean, default=False)
    trust_score = db.Column(db.Integer, default=0)
    reported_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'location': self.location,
            'total_purchases': self.total_purchases,
            'purchase_count': self.purchase_count,
            'last_purchase_date': self.last_purchase_date.strftime('%Y-%m-%d') if self.last_purchase_date else None,
            'is_trusted': self.is_trusted,
            'trust_score': self.trust_score,
            'reported_count': self.reported_count,
            'created_by': self.created_by,
            'notes': self.notes
        }

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    final_amount = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), default='Cash')
    payment_status = db.Column(db.String(20), default='Paid')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'client_id': self.client_id,
            'admin_id': self.admin_id,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_amount': self.total_amount,
            'discount': self.discount,
            'final_amount': self.final_amount,
            'sale_date': self.sale_date.strftime('%Y-%m-%d %H:%M'),
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'notes': self.notes,
            'product_name': Product.query.get(self.product_id).name if Product.query.get(self.product_id) else None,
            'client_name': Client.query.get(self.client_id).name if Client.query.get(self.client_id) else None
        }

class TrustedClientsLog(db.Model):
    __tablename__ = 'trusted_clients_log'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    reason = db.Column(db.String(200))
    reported_count = db.Column(db.Integer, default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    superadmin_action = db.Column(db.String(20), default='pending')  # pending, trusted, blocked, ignored
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SalesHistory(db.Model):
    __tablename__ = 'sales_history'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    action = db.Column(db.String(20), default='created')
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    changes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ============================
# INITIALIZE DATABASE
# ============================

with app.app_context():
    db.create_all()
    
    # Add budget status columns if not exist
    try:
        db.session.execute(text("ALTER TABLE budgets ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending'"))
        db.session.execute(text("ALTER TABLE budgets ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP"))
        db.session.commit()
        print("✅ Budget status columns added")
    except Exception as e:
        print(f"⚠️ Budget status columns already exist: {e}")
    
    # Create SuperAdmin (MCM) if not exists
    if not User.query.filter_by(username='MCM').first():
        user = User(
            username='MCM', 
            currency='FCFA', 
            email='admin@busystem.com',
            role='superadmin'
        )
        user.set_password('0880Mcm+_+')
        db.session.add(user)
        db.session.commit()
        print("✅ SuperAdmin 'MCM' created")
    
    # Create sample admin account
    if not User.query.filter_by(username='admin1').first():
        admin = User(
            username='admin1',
            currency='FCFA',
            email='admin1@busystem.com',
            role='admin',
            created_by=1
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Sample Admin 'admin1' created")
    
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
                action_message='Keep at least 3 months of expenses'
            ),
            FinancialRule(
                user_id=1,
                name='Monthly Spending Limit',
                category='spending',
                condition_type='percentage',
                condition_value=80,
                condition_operator='>',
                action_type='warn',
                action_message='Do not spend more than 80% of income'
            )
        ]
        for rule in rules:
            db.session.add(rule)
        db.session.commit()
        print("✅ Default rules created")
    
    # Create sample notifications if none exist
    if Notification.query.count() == 0:
        notifications = [
            Notification(
                user_id=1,
                title='Welcome to BuSystem! 🎉',
                message='Start tracking your finances by adding your first transaction.',
                type='info'
            ),
            Notification(
                user_id=1,
                title='💡 Tip: Set Your Goals',
                message='Setting financial goals helps you stay focused. Click Goals to get started.',
                type='success'
            ),
            Notification(
                user_id=1,
                title='📊 Dashboard Overview',
                message='Your dashboard shows all your key financial metrics at a glance.',
                type='info'
            )
        ]
        for n in notifications:
            db.session.add(n)
        db.session.commit()
        print("✅ Sample notifications created")
    
    print("🎉 Database ready!")

# ============================
# SERVE STATIC FILES
# ============================

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/manifest.json')
def serve_manifest():
    manifest = {
        "name": "BuSystem",
        "short_name": "BuSys",
        "description": "Personal Finance OS",
        "start_url": "/dashboard",
        "display": "standalone",
        "background_color": "#0a0e17",
        "theme_color": "#00d4ff",
        "orientation": "portrait",
        "scope": "/",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return Response(json.dumps(manifest), mimetype='application/json')

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
        if current_user.role == 'superadmin':
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            if user.role == 'superadmin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ============================
# SUPERADMIN DASHBOARD
# ============================

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'superadmin':
        return redirect(url_for('admin_dashboard'))
    
    user_id = current_user.id
    today = datetime.now()
    
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income'
    ).scalar() or 0
    
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense'
    ).scalar() or 0
    
    current_cash = total_income - total_expenses
    
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(
        Asset.user_id == user_id
    ).scalar() or 0
    
    total_investments = db.session.query(func.sum(Investment.capital)).filter(
        Investment.user_id == user_id,
        Investment.status == 'Running'
    ).scalar() or 0
    
    net_worth = current_cash + total_assets + total_investments
    
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
    
    sold_investments = Investment.query.filter_by(user_id=user_id, status='Sold').all()
    total_roi = 0
    if sold_investments:
        total_profit = sum(i.profit for i in sold_investments)
        total_capital = sum(i.capital for i in sold_investments)
        if total_capital > 0:
            total_roi = (total_profit / total_capital) * 100
    
    active_livestock = Livestock.query.filter_by(user_id=user_id, status='Active').count()
    
    active_goals = Goal.query.filter_by(user_id=user_id, status='Active').all()
    avg_goal_progress = sum(g.progress for g in active_goals) / len(active_goals) if active_goals else 0
    
    avg_monthly_expense = db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense'
    ).scalar() or 0
    emergency_fund_ratio = (current_cash / (avg_monthly_expense * 3)) * 100 if avg_monthly_expense > 0 else 0
    emergency_fund_ratio = min(emergency_fund_ratio, 100)
    
    # ===== NEW: Business Stats =====
    total_sales = db.session.query(func.sum(Sale.final_amount)).filter(
        Sale.admin_id == user_id
    ).scalar() or 0
    
    total_products_sold = db.session.query(func.sum(Sale.quantity)).filter(
        Sale.admin_id == user_id
    ).scalar() or 0
    
    total_clients = Client.query.filter_by(created_by=user_id).count()
    trusted_clients = Client.query.filter_by(created_by=user_id, is_trusted=True).count()
    
    total_admins = User.query.filter_by(role='admin', is_active=True).count()
    
    # Low stock alerts
    low_stock_products = Product.query.filter(
        Product.admin_id == user_id,
        Product.is_active == True,
        Product.stock_quantity <= Product.min_stock_level
    ).count()
    
    # Alerts
    alerts = []
    
    ready_animals = Livestock.query.filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Active',
        Livestock.expected_sell_date <= today
    ).limit(5).all()
    for animal in ready_animals:
        alerts.append(f"🐄 {animal.tag} ({animal.type}) is ready to sell!")
    
    budgets = Budget.query.filter_by(user_id=user_id, month=today.month, year=today.year).all()
    for budget in budgets:
        if budget.actual_amount > budget.expected_amount:
            alerts.append(f"⚠️ {budget.category} budget exceeded by {budget.actual_amount - budget.expected_amount:,.0f} FCFA")
    
    overdue_investments = Investment.query.filter(
        Investment.user_id == user_id,
        Investment.status == 'Running',
        Investment.expected_exit_date <= today
    ).limit(3).all()
    for inv in overdue_investments:
        alerts.append(f"📊 Investment {inv.investment_id} ({inv.type}) is overdue!")
    
    if emergency_fund_ratio < 30:
        alerts.append(f"🛡️ Emergency fund is low ({emergency_fund_ratio:.0f}%)")
    
    # Stock alerts
    if low_stock_products > 0:
        alerts.append(f"📦 {low_stock_products} product(s) are low in stock!")
    
    return render_template('dashboard.html',
        current_cash=current_cash,
        total_assets=total_assets,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        total_investments=total_investments,
        active_livestock=active_livestock,
        roi=total_roi,
        goal_progress=avg_goal_progress,
        emergency_fund=emergency_fund_ratio,
        alerts=alerts[:10],
        user=current_user,
        total_sales=total_sales,
        total_products_sold=total_products_sold,
        total_clients=total_clients,
        trusted_clients=trusted_clients,
        total_admins=total_admins,
        low_stock_products=low_stock_products
    )

# ============================
# ADMIN DASHBOARD
# ============================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role not in ['admin', 'superadmin']:
        flash('Access denied.')
        return redirect(url_for('login'))
    
    user_id = current_user.id
    today = datetime.now()
    
    # Admin-specific stats
    total_products = Product.query.filter_by(admin_id=user_id, is_active=True).count()
    total_clients = Client.query.filter_by(created_by=user_id).count()
    total_sales = Sale.query.filter_by(admin_id=user_id).count()
    total_revenue = db.session.query(func.sum(Sale.final_amount)).filter(
        Sale.admin_id == user_id
    ).scalar() or 0
    
    # Recent sales
    recent_sales = Sale.query.filter_by(admin_id=user_id).order_by(Sale.sale_date.desc()).limit(10).all()
    
    # Low stock
    low_stock = Product.query.filter(
        Product.admin_id == user_id,
        Product.is_active == True,
        Product.stock_quantity <= Product.min_stock_level
    ).count()
    
    # Top client
    top_client = db.session.query(
        Client.name,
        func.sum(Sale.final_amount).label('total')
    ).join(Sale, Sale.client_id == Client.id).filter(
        Sale.admin_id == user_id
    ).group_by(Client.id).order_by(func.sum(Sale.final_amount).desc()).first()
    
    return render_template('admin_dashboard.html',
        user=current_user,
        total_products=total_products,
        total_clients=total_clients,
        total_sales=total_sales,
        total_revenue=total_revenue,
        low_stock=low_stock,
        top_client=top_client,
        recent_sales=recent_sales
    )

# ============================
# PRODUCTS API
# ============================

@app.route('/api/products', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_products():
    if current_user.role not in ['admin', 'superadmin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        if current_user.role == 'superadmin':
            products = Product.query.filter_by(is_active=True).all()
        else:
            products = Product.query.filter_by(admin_id=current_user.id, is_active=True).all()
        return jsonify([p.to_dict() for p in products])
    
    elif request.method == 'POST':
        data = request.json
        product = Product(
            admin_id=current_user.id if current_user.role == 'admin' else 1,
            name=data.get('name'),
            description=data.get('description'),
            price=float(data.get('price', 0)),
            cost_price=float(data.get('cost_price', 0)),
            category=data.get('category'),
            stock_quantity=int(data.get('stock_quantity', 0)),
            min_stock_level=int(data.get('min_stock_level', 0)),
            unit=data.get('unit', 'piece')
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'status': 'success', 'id': product.id})
    
    elif request.method == 'DELETE':
        data = request.json
        product = Product.query.get_or_404(data.get('id'))
        if current_user.role != 'superadmin' and product.admin_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        product.is_active = False
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/products/<int:id>', methods=['PUT'])
@login_required
def update_product(id):
    product = Product.query.get_or_404(id)
    if current_user.role != 'superadmin' and product.admin_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    if 'stock_quantity' in data:
        product.stock_quantity = int(data['stock_quantity'])
    if 'price' in data:
        product.price = float(data['price'])
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    
    db.session.commit()
    return jsonify({'status': 'success'})

# ============================
# CLIENTS API
# ============================

@app.route('/api/clients', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_clients():
    if current_user.role not in ['admin', 'superadmin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        if current_user.role == 'superadmin':
            clients = Client.query.all()
        else:
            clients = Client.query.filter_by(created_by=current_user.id).all()
        return jsonify([c.to_dict() for c in clients])
    
    elif request.method == 'POST':
        data = request.json
        client = Client(
            created_by=current_user.id if current_user.role == 'admin' else 1,
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email'),
            location=data.get('location'),
            notes=data.get('notes')
        )
        db.session.add(client)
        db.session.commit()
        return jsonify({'status': 'success', 'id': client.id})
    
    elif request.method == 'DELETE':
        data = request.json
        client = Client.query.get_or_404(data.get('id'))
        if current_user.role != 'superadmin' and client.created_by != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(client)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/clients/<int:id>/trust', methods=['POST'])
@login_required
def mark_client_trusted(id):
    if current_user.role != 'superadmin':
        return jsonify({'error': 'Only SuperAdmin can mark trusted'}), 403
    
    client = Client.query.get_or_404(id)
    data = request.json
    
    client.is_trusted = data.get('is_trusted', True)
    if client.is_trusted:
        client.trust_score = 100
    
    # Log the action
    log = TrustedClientsLog(
        client_id=client.id,
        reason=data.get('reason', 'Marked as trusted by SuperAdmin'),
        admin_id=current_user.id,
        superadmin_action='trusted'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'status': 'success', 'is_trusted': client.is_trusted})

# ============================
# SALES API
# ============================

@app.route('/api/sales', methods=['GET', 'POST'])
@login_required
def api_sales():
    if current_user.role not in ['admin', 'superadmin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        if current_user.role == 'superadmin':
            sales = Sale.query.order_by(Sale.sale_date.desc()).limit(100).all()
        else:
            sales = Sale.query.filter_by(admin_id=current_user.id).order_by(Sale.sale_date.desc()).limit(100).all()
        return jsonify([s.to_dict() for s in sales])
    
    elif request.method == 'POST':
        data = request.json
        
        product = Product.query.get_or_404(data.get('product_id'))
        client = Client.query.get_or_404(data.get('client_id'))
        
        quantity = int(data.get('quantity', 1))
        unit_price = float(product.price)
        total_amount = quantity * unit_price
        discount = float(data.get('discount', 0))
        final_amount = total_amount - discount
        
        # Create sale
        sale = Sale(
            product_id=product.id,
            client_id=client.id,
            admin_id=current_user.id if current_user.role == 'admin' else 1,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            discount=discount,
            final_amount=final_amount,
            payment_method=data.get('payment_method', 'Cash'),
            payment_status=data.get('payment_status', 'Paid'),
            notes=data.get('notes')
        )
        db.session.add(sale)
        
        # Update product stock
        product.stock_quantity -= quantity
        
        # Update client stats
        client.total_purchases += final_amount
        client.purchase_count += 1
        client.last_purchase_date = datetime.utcnow()
        
        # Update client trust score
        if client.purchase_count >= 10:
            client.trust_score = min(client.trust_score + 10, 100)
        
        # Create income transaction (for SuperAdmin)
        transaction = Transaction(
            user_id=1,  # SuperAdmin
            type='income',
            category='Product Sales',
            amount=final_amount,
            description=f"Sale of {product.name} x{quantity} to {client.name}"
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'id': sale.id,
            'final_amount': final_amount,
            'product_name': product.name,
            'client_name': client.name
        })

@app.route('/api/sales/report')
@login_required
def get_sales_report():
    user_id = current_user.id
    is_superadmin = current_user.role == 'superadmin'
    
    # Get sales by product
    product_sales = db.session.query(
        Product.name,
        func.sum(Sale.quantity).label('total_quantity'),
        func.sum(Sale.final_amount).label('total_revenue')
    ).join(Sale, Sale.product_id == Product.id).filter(
        Sale.admin_id == user_id if not is_superadmin else True
    ).group_by(Product.id).order_by(func.sum(Sale.final_amount).desc()).all()
    
    # Get sales by client
    client_sales = db.session.query(
        Client.name,
        func.sum(Sale.final_amount).label('total_spent'),
        func.count(Sale.id).label('purchase_count')
    ).join(Sale, Sale.client_id == Client.id).filter(
        Sale.admin_id == user_id if not is_superadmin else True
    ).group_by(Client.id).order_by(func.sum(Sale.final_amount).desc()).limit(10).all()
    
    return jsonify({
        'product_sales': [{
            'name': p[0],
            'quantity': int(p[1]),
            'revenue': float(p[2])
        } for p in product_sales],
        'client_sales': [{
            'name': c[0],
            'total_spent': float(c[1]),
            'purchases': int(c[2])
        } for c in client_sales]
    })

# ============================
# AI DECISIONS - ENHANCED WITH CLIENT TRUST
# ============================

@app.route('/api/decisions')
@login_required
def get_decisions():
    recommendations = []
    user_id = current_user.id
    today = datetime.now()
    is_superadmin = current_user.role == 'superadmin'
    
    # 1. Best livestock type (for all users)
    best_type = db.session.query(
        Livestock.type,
        func.avg(Livestock.profit).label('avg_profit')
    ).filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Sold'
    ).group_by(Livestock.type).order_by(func.avg(Livestock.profit).desc()).first()
    if best_type and best_type[1] > 0:
        recommendations.append({
            'title': f'📈 Focus on {best_type[0]}',
            'message': f'Your {best_type[0]} investments show the highest average profit.',
            'type': 'opportunity'
        })
    
    # 2. Budget overruns
    over_budget = Budget.query.filter(
        Budget.user_id == user_id,
        Budget.month == today.month,
        Budget.year == today.year,
        Budget.actual_amount > Budget.expected_amount
    ).all()
    for b in over_budget[:3]:
        recommendations.append({
            'title': f'⚠️ Reduce {b.category} spending',
            'message': f'Exceeded by {b.actual_amount - b.expected_amount:,.0f} FCFA.',
            'type': 'warning'
        })
    
    # 3. Investment opportunity
    total_cash = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    if total_cash > 500000:
        recommendations.append({
            'title': '💰 Investment Opportunity',
            'message': f'You have {total_cash:,.0f} FCFA in cash. Consider investing.',
            'type': 'opportunity'
        })
    
    # ===== NEW: SuperAdmin AI Decisions (Client Trust) =====
    if is_superadmin:
        # Find top clients with high trust score
        top_clients = Client.query.filter(
            Client.is_trusted == True,
            Client.trust_score >= 70
        ).order_by(Client.total_purchases.desc()).limit(5).all()
        
        for client in top_clients:
            recommendations.append({
                'title': f'⭐ {client.name} is a TRUSTED CLIENT',
                'message': f'They have made {client.purchase_count} purchases totaling {client.total_purchases:,.0f} FCFA. Trust Score: {client.trust_score}%. Focus on maintaining this relationship.',
                'type': 'opportunity'
            })
        
        # Find clients who need review (reported multiple times)
        reported_clients = Client.query.filter(
            Client.reported_count >= 3,
            Client.is_trusted == False
        ).all()
        
        for client in reported_clients[:3]:
            recommendations.append({
                'title': f'⚠️ Review {client.name}',
                'message': f'This client has been reported {client.reported_count} times. Consider adding them to trusted list or investigating.',
                'type': 'warning'
            })
        
        # Find clients who buy specific products most
        product_analysis = db.session.query(
            Client.name,
            Product.name.label('product_name'),
            func.sum(Sale.quantity).label('total_quantity')
        ).join(Sale, Sale.client_id == Client.id).join(Product, Sale.product_id == Product.id).group_by(
            Client.id, Product.id
        ).order_by(func.sum(Sale.quantity).desc()).limit(3).all()
        
        for pa in product_analysis:
            recommendations.append({
                'title': f'📊 {pa[0]} buys {pa[1]}',
                'message': f'{pa[0]} has bought {pa[1]} {pa[2]} times. Keep this product in stock for them.',
                'type': 'opportunity'
            })
    
    return jsonify(recommendations[:8])

# ============================
# NEW PAGE ROUTES
# ============================

@app.route('/admin/products')
@login_required
def admin_products():
    if current_user.role not in ['admin', 'superadmin']:
        flash('Access denied.')
        return redirect(url_for('login'))
    return render_template('admin_products.html', user=current_user)

@app.route('/admin/clients')
@login_required
def admin_clients():
    if current_user.role not in ['admin', 'superadmin']:
        flash('Access denied.')
        return redirect(url_for('login'))
    return render_template('admin_clients.html', user=current_user)

@app.route('/admin/sales')
@login_required
def admin_sales():
    if current_user.role not in ['admin', 'superadmin']:
        flash('Access denied.')
        return redirect(url_for('login'))
    return render_template('admin_sales.html', user=current_user)

@app.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role not in ['admin', 'superadmin']:
        flash('Access denied.')
        return redirect(url_for('login'))
    return render_template('admin_reports.html', user=current_user)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'superadmin':
        flash('Access denied.')
        return redirect(url_for('login'))
    return render_template('admin_users.html', user=current_user)







# ============================
# USER MANAGEMENT API (SuperAdmin only)
# ============================

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_users():
    if current_user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else None
        } for u in users])
    
    elif request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        role = data.get('role', 'admin')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        user = User(
            username=username,
            email=email,
            role=role,
            created_by=current_user.id
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'status': 'success', 'id': user.id})
    
    elif request.method == 'DELETE':
        data = request.json
        user = User.query.get_or_404(data.get('id'))
        
        if user.username == 'MCM':
            return jsonify({'error': 'Cannot delete SuperAdmin'}), 400
        
        db.session.delete(user)
        db.session.commit()
        return jsonify({'status': 'success'})

# ============================
# ADMIN SALES PDF REPORT
# ============================

@app.route('/api/reports/export/sales/pdf')
@login_required
def export_sales_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    
    user_id = current_user.id
    is_superadmin = current_user.role == 'superadmin'
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#00d4ff'))
    story.append(Paragraph("BuSystem - Sales Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Paragraph(f"User: {current_user.username} ({current_user.role})", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Get sales data
    if is_superadmin:
        sales = Sale.query.order_by(Sale.sale_date.desc()).limit(200).all()
    else:
        sales = Sale.query.filter_by(admin_id=user_id).order_by(Sale.sale_date.desc()).limit(200).all()
    
    if sales:
        data = [['Date', 'Product', 'Client', 'Quantity', 'Unit Price', 'Total']]
        for s in sales:
            data.append([
                s.sale_date.strftime('%Y-%m-%d'),
                s.product.name if s.product else 'N/A',
                s.client.name if s.client else 'N/A',
                str(s.quantity),
                f"{s.unit_price:,.0f}",
                f"{s.final_amount:,.0f}"
            ])
        
        table = Table(data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 0.8*inch, 1*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No sales found.", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.pdf")

@app.route('/api/reports/export/sales/excel')
@login_required
def export_sales_excel():
    import xlsxwriter
    user_id = current_user.id
    is_superadmin = current_user.role == 'superadmin'
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Sales')
    
    headers = ['Date', 'Product', 'Client', 'Quantity', 'Unit Price', 'Total']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    if is_superadmin:
        sales = Sale.query.order_by(Sale.sale_date.desc()).limit(500).all()
    else:
        sales = Sale.query.filter_by(admin_id=user_id).order_by(Sale.sale_date.desc()).limit(500).all()
    
    for row, s in enumerate(sales, 1):
        worksheet.write(row, 0, s.sale_date.strftime('%Y-%m-%d'))
        worksheet.write(row, 1, s.product.name if s.product else 'N/A')
        worksheet.write(row, 2, s.client.name if s.client else 'N/A')
        worksheet.write(row, 3, s.quantity)
        worksheet.write(row, 4, s.unit_price)
        worksheet.write(row, 5, s.final_amount)
    
    workbook.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')




# ============================
# EXISTING PAGE ROUTES (Unchanged)
# ============================

@app.route('/cashflow')
@login_required
def cashflow():
    return render_template('cashflow.html', user=current_user)

@app.route('/investments')
@login_required
def investments():
    return render_template('investments.html', user=current_user)

@app.route('/livestock')
@login_required
def livestock():
    return render_template('livestock.html', user=current_user)

@app.route('/assets')
@login_required
def assets():
    return render_template('assets.html', user=current_user)

@app.route('/goals')
@login_required
def goals():
    return render_template('goals.html', user=current_user)

@app.route('/budget')
@login_required
def budget():
    return render_template('budget.html', user=current_user)

@app.route('/liability')
@login_required
def liability():
    return render_template('liability.html', user=current_user)

@app.route('/rules')
@login_required
def rules():
    return render_template('rules.html', user=current_user)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html', user=current_user)

@app.route('/ratios')
@login_required
def ratios():
    return render_template('ratios.html', user=current_user)

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html', user=current_user)

@app.route('/risk')
@login_required
def risk():
    return render_template('risk.html', user=current_user)

@app.route('/timeline')
@login_required
def timeline():
    return render_template('timeline.html', user=current_user)

@app.route('/decisions')
@login_required
def decisions():
    return render_template('decisions.html', user=current_user)

@app.route('/exports')
@login_required
def exports():
    return render_template('exports.html', user=current_user)

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html', user=current_user)

# ============================
# RUN APP
# ============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

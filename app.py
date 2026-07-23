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
    role = db.Column(db.String(20), default='admin')
    created_by = db.Column(db.Integer, nullable=True)
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
    superadmin_action = db.Column(db.String(20), default='pending')
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
# FIX DATABASE SCHEMA ON STARTUP
# ============================

def fix_database_schema():
    """Add missing columns to existing tables"""
    with app.app_context():
        try:
            # Check if users table exists
            db.session.execute(text("SELECT 1 FROM users LIMIT 1"))
            
            # Add missing columns to users table
            columns_to_add = [
                ("currency", "VARCHAR(10) DEFAULT 'FCFA'"),
                ("email", "VARCHAR(120)"),
                ("role", "VARCHAR(20) DEFAULT 'admin'"),
                ("created_by", "INTEGER"),
                ("is_active", "BOOLEAN DEFAULT TRUE"),
                ("last_login", "TIMESTAMP")
            ]
            
            for col_name, col_type in columns_to_add:
                try:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    print(f"✅ Added column: {col_name}")
                except Exception as e:
                    print(f"⚠️ Could not add {col_name}: {e}")
            
            db.session.commit()
            
            # Check if budgets table has status columns
            try:
                db.session.execute(text("ALTER TABLE budgets ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending'"))
                db.session.execute(text("ALTER TABLE budgets ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP"))
                db.session.commit()
                print("✅ Budget status columns added")
            except Exception as e:
                print(f"⚠️ Budget status columns: {e}")
            
            print("✅ Database schema fix completed")
        except Exception as e:
            print(f"⚠️ Database schema fix: {e}")

# ============================
# INITIALIZE DATABASE
# ============================

with app.app_context():
    db.create_all()
    fix_database_schema()
    
    # Create SuperAdmin (MCM) if not exists
    if not User.query.filter_by(username='MCM').first():
        user = User(
            username='MCM', 
            currency='FCFA', 
            email='admin@busystem.com',
            role='superadmin',
            is_active=True
        )
        user.set_password('0880Mcm+_+')
        db.session.add(user)
        db.session.commit()
        print("✅ SuperAdmin 'MCM' created")
    
    # Update existing MCM to superadmin if role is missing
    mcm = User.query.filter_by(username='MCM').first()
    if mcm and mcm.role != 'superadmin':
        mcm.role = 'superadmin'
        mcm.is_active = True
        db.session.commit()
        print("✅ MCM updated to SuperAdmin")
    
    # Create sample admin account
    if not User.query.filter_by(username='admin1').first():
        admin = User(
            username='admin1',
            currency='FCFA',
            email='admin1@busystem.com',
            role='admin',
            created_by=1,
            is_active=True
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
    
    # Business Stats
    total_sales = db.session.query(func.sum(Sale.final_amount)).scalar() or 0
    total_products_sold = db.session.query(func.sum(Sale.quantity)).scalar() or 0
    total_clients = Client.query.count()
    trusted_clients = Client.query.filter_by(is_trusted=True).count()
    total_admins = User.query.filter_by(role='admin', is_active=True).count()
    low_stock_products = Product.query.filter(Product.is_active == True, Product.stock_quantity <= Product.min_stock_level).count()
    
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
    
    total_products = Product.query.filter_by(admin_id=user_id, is_active=True).count()
    total_clients = Client.query.filter_by(created_by=user_id).count()
    total_sales = Sale.query.filter_by(admin_id=user_id).count()
    total_revenue = db.session.query(func.sum(Sale.final_amount)).filter(Sale.admin_id == user_id).scalar() or 0
    recent_sales = Sale.query.filter_by(admin_id=user_id).order_by(Sale.sale_date.desc()).limit(10).all()
    low_stock = Product.query.filter(Product.admin_id == user_id, Product.is_active == True, Product.stock_quantity <= Product.min_stock_level).count()
    
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
        
        product.stock_quantity -= quantity
        
        client.total_purchases += final_amount
        client.purchase_count += 1
        client.last_purchase_date = datetime.utcnow()
        
        if client.purchase_count >= 10:
            client.trust_score = min(client.trust_score + 10, 100)
        
        transaction = Transaction(
            user_id=1,
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
    
    product_sales = db.session.query(
        Product.name,
        func.sum(Sale.quantity).label('total_quantity'),
        func.sum(Sale.final_amount).label('total_revenue')
    ).join(Sale, Sale.product_id == Product.id).filter(
        Sale.admin_id == user_id if not is_superadmin else True
    ).group_by(Product.id).order_by(func.sum(Sale.final_amount).desc()).all()
    
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
# RULES API
# ============================

@app.route('/api/rules', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_rules():
    if request.method == 'GET':
        rules = FinancialRule.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        return jsonify([r.to_dict() for r in rules])
    elif request.method == 'POST':
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
    elif request.method == 'DELETE':
        data = request.json
        rule = FinancialRule.query.get_or_404(data.get('id'))
        if rule.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(rule)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/rules/check')
@login_required
def check_rules():
    alerts = []
    user_id = current_user.id
    today = datetime.now()
    rules = FinancialRule.query.filter_by(user_id=user_id, is_active=True).all()
    for rule in rules:
        if rule.category == 'investment':
            investments = Investment.query.filter_by(user_id=user_id, status='Running').all()
            total_capital = sum(i.capital for i in investments)
            if total_capital > 0:
                for inv in investments:
                    percentage = (inv.capital / total_capital) * 100
                    if rule.condition_operator == '>' and percentage > rule.condition_value:
                        alerts.append(f"⚠️ {rule.name}: {inv.type} ({inv.investment_id}) exceeds {rule.condition_value}%")
        elif rule.category == 'spending':
            monthly_expenses = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'expense',
                extract('month', Transaction.date) == today.month
            ).scalar() or 0
            monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'income',
                extract('month', Transaction.date) == today.month
            ).scalar() or 1
            spending_ratio = (monthly_expenses / monthly_income) * 100
            if rule.condition_operator == '>' and spending_ratio > rule.condition_value:
                alerts.append(f"⚠️ {rule.name}: Spending at {spending_ratio:.1f}% (limit: {rule.condition_value}%)")
        elif rule.category == 'emergency':
            total_cash = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'income'
            ).scalar() or 0
            avg_monthly = db.session.query(func.avg(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'expense'
            ).scalar() or 1
            emergency_months = total_cash / (avg_monthly * 3) if avg_monthly > 0 else 0
            if rule.condition_operator == '<' and emergency_months < rule.condition_value:
                alerts.append(f"⚠️ {rule.name}: Emergency fund covers {emergency_months:.1f} months")
    return jsonify(alerts)

# ============================
# RATIOS API
# ============================

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
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(
        Asset.user_id == user_id
    ).scalar() or 0
    sold_investments = Investment.query.filter_by(user_id=user_id, status='Sold').all()
    total_profit = sum(i.profit for i in sold_investments)
    total_capital = sum(i.capital for i in sold_investments) or 1
    savings = total_income - total_expenses
    return jsonify({
        'roi': (total_profit / total_capital) * 100,
        'profit_margin': (savings / total_income) * 100 if total_income > 0 else 0,
        'savings_ratio': (savings / total_income) * 100 if total_income > 0 else 0,
        'capital_turnover': (total_income / total_assets) if total_assets > 0 else 0
    })

# ============================
# RISK API
# ============================

@app.route('/api/risk')
@login_required
def get_risk_analysis():
    user_id = current_user.id
    investments = Investment.query.filter_by(user_id=user_id).all()
    high_risk = len([i for i in investments if i.type in ['Stock', 'Crop']])
    medium_risk = len([i for i in investments if i.type == 'Business'])
    low_risk = len([i for i in investments if i.type == 'Animal'])
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    cash_reserve = total_income - total_expenses
    return jsonify({
        'high_risk_investments': high_risk,
        'medium_risk_investments': medium_risk,
        'low_risk_investments': low_risk,
        'cash_reserve': cash_reserve,
        'diversification_score': min((len(set(i.type for i in investments)) / 4) * 100, 100) if investments else 0,
        'overall_risk': 'Low' if high_risk < 2 else 'Medium' if high_risk < 5 else 'High'
    })

# ============================
# ANALYTICS API
# ============================

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
    return jsonify([])

# ============================
# TIMELINE API
# ============================

@app.route('/api/timeline')
@login_required
def get_timeline():
    user_id = current_user.id
    events = []
    for t in Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(50).all():
        events.append({
            'date': t.date.strftime('%Y-%m-%d'),
            'type': 'transaction',
            'title': f"{t.type.capitalize()}: {t.category}",
            'description': f"{t.amount:,.0f} FCFA",
            'icon': '💰'
        })
    for i in Investment.query.filter_by(user_id=user_id).order_by(Investment.purchase_date.desc()).limit(30).all():
        events.append({
            'date': i.purchase_date.strftime('%Y-%m-%d'),
            'type': 'investment',
            'title': f"Investment: {i.investment_id}",
            'description': f"{i.capital:,.0f} FCFA - {i.type}",
            'icon': '📊'
        })
    for l in Livestock.query.filter_by(user_id=user_id).order_by(Livestock.purchase_date.desc()).limit(30).all():
        events.append({
            'date': l.purchase_date.strftime('%Y-%m-%d'),
            'type': 'livestock',
            'title': f"Added: {l.type} - {l.tag}",
            'description': f"Purchased for {l.purchase_price:,.0f} FCFA",
            'icon': '🐄'
        })
    for g in Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).limit(20).all():
        events.append({
            'date': g.created_at.strftime('%Y-%m-%d'),
            'type': 'goal',
            'title': f"Goal: {g.name}",
            'description': f"Target: {g.target_amount:,.0f} FCFA ({g.progress:.0f}%)",
            'icon': '🎯'
        })
    events.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(events[:100])

# ============================
# DECISIONS API
# ============================

@app.route('/api/decisions')
@login_required
def get_decisions():
    recommendations = []
    user_id = current_user.id
    today = datetime.now()
    is_superadmin = current_user.role == 'superadmin'
    
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
    
    total_cash = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    if total_cash > 500000:
        recommendations.append({
            'title': '💰 Investment Opportunity',
            'message': f'You have {total_cash:,.0f} FCFA in cash.',
            'type': 'opportunity'
        })
    
    # SuperAdmin: Client Trust Recommendations
    if is_superadmin:
        top_clients = Client.query.filter(
            Client.is_trusted == True,
            Client.trust_score >= 70
        ).order_by(Client.total_purchases.desc()).limit(5).all()
        
        for client in top_clients:
            recommendations.append({
                'title': f'⭐ {client.name} is a TRUSTED CLIENT',
                'message': f'They have made {client.purchase_count} purchases totaling {client.total_purchases:,.0f} FCFA. Trust Score: {client.trust_score}%.',
                'type': 'opportunity'
            })
        
        reported_clients = Client.query.filter(
            Client.reported_count >= 3,
            Client.is_trusted == False
        ).all()
        
        for client in reported_clients[:3]:
            recommendations.append({
                'title': f'⚠️ Review {client.name}',
                'message': f'This client has been reported {client.reported_count} times.',
                'type': 'warning'
            })
        
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
                'message': f'{pa[0]} has bought {pa[1]} {pa[2]} times.',
                'type': 'opportunity'
            })
    
    return jsonify(recommendations[:8])

# ============================
# NOTIFICATIONS API
# ============================

@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([n.to_dict() for n in notifications])

# ============================
# LIABILITIES API
# ============================

@app.route('/api/liabilities', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_liabilities():
    if request.method == 'GET':
        liabilities = Liability.query.filter_by(
            user_id=current_user.id
        ).order_by(Liability.created_at.desc()).all()
        return jsonify([l.to_dict() for l in liabilities])
    elif request.method == 'POST':
        data = request.json
        liability = Liability(
            user_id=current_user.id,
            type=data.get('type'),
            name=data.get('name'),
            description=data.get('description'),
            amount=float(data.get('amount')),
            due_date=datetime.strptime(data.get('due_date'), '%Y-%m-%d') if data.get('due_date') else None,
            status=data.get('status', 'Pending'),
            notes=data.get('notes')
        )
        db.session.add(liability)
        db.session.commit()
        return jsonify({'status': 'success', 'id': liability.id})
    elif request.method == 'DELETE':
        data = request.json
        liability = Liability.query.get_or_404(data.get('id'))
        if liability.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(liability)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/liabilities/<int:id>/paid', methods=['POST'])
@login_required
def mark_liability_paid(id):
    liability = Liability.query.get_or_404(id)
    if liability.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    liability.status = 'Paid'
    liability.paid_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success', 'new_status': liability.status})

@app.route('/api/liabilities/summary')
@login_required
def get_liability_summary():
    user_id = current_user.id
    total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id,
        Liability.type == 'owes_me',
        Liability.status != 'Paid'
    ).scalar() or 0
    total_i_owe = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id,
        Liability.type == 'i_owe',
        Liability.status != 'Paid'
    ).scalar() or 0
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(
        Asset.user_id == user_id
    ).scalar() or 0
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    total_cash = total_income - total_expenses
    total_equity = total_assets + total_cash - total_i_owe + total_owed_to_me
    return jsonify({
        'total_owed_to_me': total_owed_to_me,
        'total_i_owe': total_i_owe,
        'total_assets': total_assets,
        'total_cash': total_cash,
        'total_equity': total_equity,
        'net_position': total_owed_to_me - total_i_owe
    })

# ============================
# BUDGET API
# ============================

@app.route('/api/budget', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_budget():
    if request.method == 'GET':
        today = datetime.now()
        budgets = Budget.query.filter_by(
            user_id=current_user.id,
            month=today.month,
            year=today.year
        ).all()
        return jsonify([b.to_dict() for b in budgets])
    elif request.method == 'POST':
        data = request.json
        budget = Budget.query.filter_by(
            user_id=current_user.id,
            category=data.get('category'),
            month=data.get('month'),
            year=data.get('year')
        ).first()
        if budget:
            budget.expected_amount = float(data.get('expected_amount'))
        else:
            budget = Budget(
                user_id=current_user.id,
                category=data.get('category'),
                type=data.get('type'),
                expected_amount=float(data.get('expected_amount')),
                month=data.get('month'),
                year=data.get('year')
            )
            db.session.add(budget)
        db.session.commit()
        return jsonify({'status': 'success'})
    elif request.method == 'DELETE':
        data = request.json
        budget = Budget.query.get_or_404(data.get('id'))
        if budget.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(budget)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/budget/<int:id>/status', methods=['POST'])
@login_required
def update_budget_status(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    status = data.get('status')
    if status not in ['done', 'not_done', 'pending']:
        return jsonify({'error': 'Invalid status'}), 400
    budget.status = status
    budget.status_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success', 'new_status': status})

# ============================
# REPORTS API
# ============================

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
            'income': [{'category': i[1], 'total': float(i[0])} for i in income],
            'expenses': [{'category': i[1], 'total': float(i[0])} for i in expenses]
        })
    elif report_type == 'balance_sheet':
        total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        return jsonify({
            'total_assets': total_assets,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_worth': total_assets + total_income - total_expenses
        })
    return jsonify({'error': 'Invalid report type'}), 400

@app.route('/api/reports/export/<report_type>/<format>')
@login_required
def export_report(report_type, format):
    user_id = current_user.id
    if format == 'pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, alignment=1, textColor=colors.HexColor('#00d4ff'))
        story.append(Paragraph("💰 BuSystem - Complete Financial Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"User: {current_user.username}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Summary
        story.append(Paragraph("<b>📊 EXECUTIVE SUMMARY</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
        total_investments = db.session.query(func.sum(Investment.capital)).filter(
            Investment.user_id == user_id, Investment.status == 'Running'
        ).scalar() or 0
        total_livestock = Livestock.query.filter_by(user_id=user_id).count()
        active_goals = Goal.query.filter_by(user_id=user_id, status='Active').count()
        
        total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id,
            Liability.type == 'owes_me',
            Liability.status != 'Paid'
        ).scalar() or 0
        total_i_owe = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id,
            Liability.type == 'i_owe',
            Liability.status != 'Paid'
        ).scalar() or 0
        
        summary_data = [
            ['Metric', 'Amount (FCFA)'],
            ['Total Income', f"{total_income:,.0f}"],
            ['Total Expenses', f"{total_expenses:,.0f}"],
            ['Net Cash', f"{total_income - total_expenses:,.0f}"],
            ['Total Assets', f"{total_assets:,.0f}"],
            ['Total Investments', f"{total_investments:,.0f}"],
            ['Owed to Me', f"{total_owed_to_me:,.0f}"],
            ['I Owe', f"{total_i_owe:,.0f}"],
            ['Net Worth', f"{total_assets + total_income - total_expenses:,.0f}"],
            ['Total Livestock', f"{total_livestock}"],
            ['Active Goals', f"{active_goals}"]
        ]
        summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Transactions
        story.append(PageBreak())
        story.append(Paragraph("<b>💰 TRANSACTIONS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(200).all()
        if transactions:
            tx_data = [['Date', 'Type', 'Category', 'Amount', 'Description']]
            for t in transactions:
                tx_data.append([
                    t.date.strftime('%Y-%m-%d'),
                    t.type.capitalize(),
                    t.category,
                    f"{t.amount:,.0f}",
                    t.description or ''
                ])
            tx_table = Table(tx_data, colWidths=[1.2*inch, 1*inch, 1.5*inch, 1.2*inch, 2*inch])
            tx_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(tx_table)
        else:
            story.append(Paragraph("No transactions found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Investments
        story.append(PageBreak())
        story.append(Paragraph("<b>📈 INVESTMENTS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        investments = Investment.query.filter_by(user_id=user_id).all()
        if investments:
            inv_data = [['ID', 'Type', 'Capital', 'Status', 'Profit', 'ROI']]
            for i in investments:
                inv_data.append([
                    i.investment_id,
                    f"{i.type}{' ('+i.sub_type+')' if i.sub_type else ''}",
                    f"{i.capital:,.0f}",
                    i.status,
                    f"{i.profit:,.0f}",
                    f"{i.roi_actual:.1f}%" if i.roi_actual else '-'
                ])
            inv_table = Table(inv_data, colWidths=[1*inch, 1.5*inch, 1.2*inch, 1*inch, 1.2*inch, 1*inch])
            inv_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(inv_table)
        else:
            story.append(Paragraph("No investments found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Livestock
        story.append(PageBreak())
        story.append(Paragraph("<b>🐄 LIVESTOCK</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        livestock = Livestock.query.filter_by(user_id=user_id).all()
        if livestock:
            ls_data = [['Tag', 'Type', 'Breed', 'Purchase Price', 'Status', 'Profit']]
            for l in livestock:
                ls_data.append([
                    l.tag,
                    l.type,
                    l.breed or '-',
                    f"{l.purchase_price:,.0f}",
                    l.status,
                    f"{l.profit:,.0f}" if l.profit else '-'
                ])
            ls_table = Table(ls_data, colWidths=[0.8*inch, 1*inch, 1*inch, 1.2*inch, 1*inch, 1.2*inch])
            ls_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(ls_table)
        else:
            story.append(Paragraph("No livestock found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Assets
        story.append(PageBreak())
        story.append(Paragraph("<b>🏦 ASSETS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        assets = Asset.query.filter_by(user_id=user_id).all()
        if assets:
            asset_data = [['Name', 'Category', 'Purchase Price', 'Current Value', 'Condition']]
            for a in assets:
                asset_data.append([
                    a.name,
                    a.category,
                    f"{a.purchase_price:,.0f}",
                    f"{a.current_value:,.0f}",
                    a.condition
                ])
            asset_table = Table(asset_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
            asset_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(asset_table)
        else:
            story.append(Paragraph("No assets found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Goals
        story.append(PageBreak())
        story.append(Paragraph("<b>🎯 GOALS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        goals = Goal.query.filter_by(user_id=user_id).all()
        if goals:
            goal_data = [['Name', 'Target', 'Current', 'Progress', 'Status']]
            for g in goals:
                goal_data.append([
                    g.name,
                    f"{g.target_amount:,.0f}",
                    f"{g.current_amount:,.0f}",
                    f"{g.progress:.0f}%",
                    g.status
                ])
            goal_table = Table(goal_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1*inch, 1.2*inch])
            goal_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(goal_table)
        else:
            story.append(Paragraph("No goals found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Budgets
        story.append(PageBreak())
        story.append(Paragraph("<b>📋 BUDGETS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        all_budgets = Budget.query.filter_by(user_id=user_id).order_by(Budget.year.desc(), Budget.month.desc()).all()
        if all_budgets:
            budget_data = [['Category', 'Type', 'Month/Year', 'Expected', 'Actual', 'Difference', 'Status']]
            for b in all_budgets:
                month_name = datetime(b.year, b.month, 1).strftime('%B %Y')
                budget_data.append([
                    b.category,
                    b.type,
                    month_name,
                    f"{b.expected_amount:,.0f}",
                    f"{b.actual_amount:,.0f}",
                    f"{b.difference:+,.0f}",
                    b.status or 'pending'
                ])
            budget_table = Table(budget_data, colWidths=[1.2*inch, 1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
            budget_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(budget_table)
        else:
            story.append(Paragraph("No budgets found.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Liabilities
        story.append(PageBreak())
        story.append(Paragraph("<b>📋 LIABILITIES</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        liabilities = Liability.query.filter_by(user_id=user_id).all()
        if liabilities:
            liability_data = [['Type', 'Name', 'Description', 'Amount', 'Due Date', 'Status']]
            for l in liabilities:
                liability_data.append([
                    'Owed to Me' if l.type == 'owes_me' else 'I Owe',
                    l.name,
                    l.description or '-',
                    f"{l.amount:,.0f}",
                    l.due_date.strftime('%Y-%m-%d') if l.due_date else '-',
                    l.status
                ])
            liability_table = Table(liability_data, colWidths=[1.2*inch, 1.2*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1*inch])
            liability_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(liability_table)
        else:
            story.append(Paragraph("No liabilities found.", styles['Normal']))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle('Footer', fontSize=10, alignment=1, textColor=colors.HexColor('#4a5a6f'))
        story.append(Paragraph("BuSystem v1.0 • Every Franc Must Have a Job", footer_style))
        story.append(Paragraph(f"Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}", footer_style))
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"BuSystem_Full_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    elif format == 'excel':
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        worksheet1 = workbook.add_worksheet('Transactions')
        headers = ['Date', 'Type', 'Category', 'Amount', 'Description']
        for col, header in enumerate(headers):
            worksheet1.write(0, col, header)
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
        for row, t in enumerate(transactions, 1):
            worksheet1.write(row, 0, t.date.strftime('%Y-%m-%d'))
            worksheet1.write(row, 1, t.type)
            worksheet1.write(row, 2, t.category)
            worksheet1.write(row, 3, t.amount)
            worksheet1.write(row, 4, t.description or '')
        
        worksheet2 = workbook.add_worksheet('Investments')
        headers2 = ['ID', 'Type', 'Sub Type', 'Capital', 'Status', 'Profit', 'ROI']
        for col, header in enumerate(headers2):
            worksheet2.write(0, col, header)
        investments = Investment.query.filter_by(user_id=user_id).all()
        for row, i in enumerate(investments, 1):
            worksheet2.write(row, 0, i.investment_id)
            worksheet2.write(row, 1, i.type)
            worksheet2.write(row, 2, i.sub_type or '')
            worksheet2.write(row, 3, i.capital)
            worksheet2.write(row, 4, i.status)
            worksheet2.write(row, 5, i.profit)
            worksheet2.write(row, 6, i.roi_actual)
        
        worksheet3 = workbook.add_worksheet('Livestock')
        headers3 = ['Tag', 'Type', 'Breed', 'Purchase Price', 'Status', 'Profit']
        for col, header in enumerate(headers3):
            worksheet3.write(0, col, header)
        livestock = Livestock.query.filter_by(user_id=user_id).all()
        for row, l in enumerate(livestock, 1):
            worksheet3.write(row, 0, l.tag)
            worksheet3.write(row, 1, l.type)
            worksheet3.write(row, 2, l.breed or '')
            worksheet3.write(row, 3, l.purchase_price)
            worksheet3.write(row, 4, l.status)
            worksheet3.write(row, 5, l.profit or 0)
        
        worksheet4 = workbook.add_worksheet('Assets')
        headers4 = ['Name', 'Category', 'Purchase Price', 'Current Value', 'Condition']
        for col, header in enumerate(headers4):
            worksheet4.write(0, col, header)
        assets = Asset.query.filter_by(user_id=user_id).all()
        for row, a in enumerate(assets, 1):
            worksheet4.write(row, 0, a.name)
            worksheet4.write(row, 1, a.category)
            worksheet4.write(row, 2, a.purchase_price)
            worksheet4.write(row, 3, a.current_value)
            worksheet4.write(row, 4, a.condition)
        
        worksheet5 = workbook.add_worksheet('Goals')
        headers5 = ['Name', 'Target', 'Current', 'Progress', 'Status']
        for col, header in enumerate(headers5):
            worksheet5.write(0, col, header)
        goals = Goal.query.filter_by(user_id=user_id).all()
        for row, g in enumerate(goals, 1):
            worksheet5.write(row, 0, g.name)
            worksheet5.write(row, 1, g.target_amount)
            worksheet5.write(row, 2, g.current_amount)
            worksheet5.write(row, 3, g.progress)
            worksheet5.write(row, 4, g.status)
        
        worksheet6 = workbook.add_worksheet('Budgets')
        headers6 = ['Category', 'Type', 'Month', 'Year', 'Expected', 'Actual', 'Difference', 'Status']
        for col, header in enumerate(headers6):
            worksheet6.write(0, col, header)
        budgets = Budget.query.filter_by(user_id=user_id).all()
        for row, b in enumerate(budgets, 1):
            worksheet6.write(row, 0, b.category)
            worksheet6.write(row, 1, b.type)
            worksheet6.write(row, 2, b.month)
            worksheet6.write(row, 3, b.year)
            worksheet6.write(row, 4, b.expected_amount)
            worksheet6.write(row, 5, b.actual_amount)
            worksheet6.write(row, 6, b.difference)
            worksheet6.write(row, 7, b.status or 'pending')
        
        worksheet7 = workbook.add_worksheet('Liabilities')
        headers7 = ['Type', 'Name', 'Description', 'Amount', 'Due Date', 'Status']
        for col, header in enumerate(headers7):
            worksheet7.write(0, col, header)
        liabilities = Liability.query.filter_by(user_id=user_id).all()
        for row, l in enumerate(liabilities, 1):
            worksheet7.write(row, 0, 'Owed to Me' if l.type == 'owes_me' else 'I Owe')
            worksheet7.write(row, 1, l.name)
            worksheet7.write(row, 2, l.description or '')
            worksheet7.write(row, 3, l.amount)
            worksheet7.write(row, 4, l.due_date.strftime('%Y-%m-%d') if l.due_date else '')
            worksheet7.write(row, 5, l.status)
        
        workbook.close()
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"BuSystem_Full_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    
    return jsonify({'error': 'Invalid format'}), 400

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
# PAGE ROUTES
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
# ADMIN PAGE ROUTES
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
# RUN APP
# ============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

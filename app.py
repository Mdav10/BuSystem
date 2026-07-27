import os
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, send_from_directory, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func, extract, text, and_, or_
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
    currency = db.Column(db.String(10), default='BIF')
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role in ['superadmin', 'admin']
    
    def is_superadmin(self):
        return self.role == 'superadmin'


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
# ADMIN MODELS
# ============================

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    min_stock = db.Column(db.Integer, default=5)
    unit = db.Column(db.String(20), default='unit')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'cost_price': self.cost_price,
            'stock': self.stock,
            'min_stock': self.min_stock,
            'unit': self.unit,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }


class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    trust_score = db.Column(db.Integer, default=0)
    is_trusted = db.Column(db.Boolean, default=False)
    total_purchases = db.Column(db.Float, default=0)
    purchase_count = db.Column(db.Integer, default=0)
    last_purchase = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'location': self.location,
            'trust_score': self.trust_score,
            'is_trusted': self.is_trusted,
            'total_purchases': self.total_purchases,
            'purchase_count': self.purchase_count,
            'last_purchase': self.last_purchase.strftime('%Y-%m-%d') if self.last_purchase else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }


class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    final_total = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, default=0)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    
    def to_dict(self):
        product = Product.query.get(self.product_id)
        client = Client.query.get(self.client_id) if self.client_id else None
        return {
            'id': self.id,
            'product_name': product.name if product else 'Unknown',
            'client_name': client.name if client else 'Walk-in',
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total': self.total,
            'discount': self.discount,
            'final_total': self.final_total,
            'profit': self.profit,
            'sale_date': self.sale_date.strftime('%Y-%m-%d %H:%M'),
            'created_by': self.created_by
        }


# ============================
# DECORATORS
# ============================

def superadmin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.')
            return redirect(url_for('login'))
        if not current_user.is_superadmin():
            flash('Access denied. SuperAdmin only.')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.')
            return redirect(url_for('login'))
        if not current_user.is_admin():
            flash('Access denied. Admin only.')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def login_required_redirect(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================
# INITIALIZE DATABASE
# ============================

with app.app_context():
    db.create_all()
    print("✅ Database tables created/verified")
    
    # Create SuperAdmin with BIF currency
    if not User.query.filter_by(username='MCM').first():
        user = User(username='MCM', currency='BIF', email='admin@busystem.com', role='superadmin')
        user.set_password('0880Mcm+_+')
        db.session.add(user)
        db.session.commit()
        print("✅ SuperAdmin 'MCM' created")
    else:
        user = User.query.filter_by(username='MCM').first()
        if user.role != 'superadmin':
            user.role = 'superadmin'
            db.session.commit()
            print("✅ MCM upgraded to SuperAdmin")
        if user.currency != 'BIF':
            user.currency = 'BIF'
            db.session.commit()
            print("✅ Currency updated to BIF")
    
    # Create default rules
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
    
    # Create sample notifications
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
        "start_url": "/login",
        "display": "standalone",
        "background_color": "#0a0e17",
        "theme_color": "#00d4ff",
        "orientation": "portrait",
        "scope": "/",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
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
    if current_user.is_authenticated:
        if current_user.is_superadmin():
            return redirect(url_for('superadmin_dashboard'))
        elif current_user.is_admin():
            return redirect(url_for('admin_panel'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_superadmin():
            return redirect(url_for('superadmin_dashboard'))
        elif current_user.is_admin():
            return redirect(url_for('admin_panel'))
        else:
            return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            if user.is_superadmin():
                return redirect(url_for('superadmin_dashboard'))
            elif user.is_admin():
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('user_dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))


# ============================
# USER ROUTES
# ============================

@app.route('/user/dashboard')
@login_required_redirect
def user_dashboard():
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
    
    return render_template('user_dashboard.html',
        current_cash=current_cash,
        total_assets=total_assets,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        total_investments=total_investments,
        user=current_user
    )


@app.route('/user/cashflow')
@login_required_redirect
def user_cashflow():
    return render_template('user_cashflow.html', user=current_user)


@app.route('/api/user/transactions', methods=['GET', 'POST', 'DELETE'])
@login_required_redirect
def user_api_transactions():
    if request.method == 'GET':
        transactions = Transaction.query.filter_by(
            user_id=current_user.id
        ).order_by(Transaction.date.desc()).limit(100).all()
        return jsonify([t.to_dict() for t in transactions])
    elif request.method == 'POST':
        data = request.json
        transaction = Transaction(
            user_id=current_user.id,
            type=data.get('type'),
            category=data.get('category'),
            amount=float(data.get('amount')),
            description=data.get('description'),
            date=datetime.strptime(data.get('date'), '%Y-%m-%d') if data.get('date') else datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'status': 'success', 'id': transaction.id})
    elif request.method == 'DELETE':
        data = request.json
        transaction = Transaction.query.get_or_404(data.get('id'))
        if transaction.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(transaction)
        db.session.commit()
        return jsonify({'status': 'success'})


# ============================
# SUPERADMIN DASHBOARD
# ============================

@app.route('/dashboard')
@login_required
@superadmin_required
def superadmin_dashboard():
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
            alerts.append(f"⚠️ {budget.category} budget exceeded by {budget.actual_amount - budget.expected_amount:,.0f} BIF")
    
    overdue_investments = Investment.query.filter(
        Investment.user_id == user_id,
        Investment.status == 'Running',
        Investment.expected_exit_date <= today
    ).limit(3).all()
    for inv in overdue_investments:
        alerts.append(f"📊 Investment {inv.investment_id} ({inv.type}) is overdue!")
    
    if emergency_fund_ratio < 30:
        alerts.append(f"🛡️ Emergency fund is low ({emergency_fund_ratio:.0f}%)")
    
    total_products = Product.query.count()
    total_clients = Client.query.count()
    total_sales = Sale.query.count()
    total_revenue = db.session.query(func.sum(Sale.final_total)).scalar() or 0
    
    return render_template('superadmin_dashboard.html',
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
        total_products=total_products,
        total_clients=total_clients,
        total_sales=total_sales,
        total_revenue=total_revenue,
        user=current_user
    )


# ============================
# ALL ORIGINAL API ROUTES
# ============================

@app.route('/api/transactions', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
def api_transactions():
    if request.method == 'GET':
        transactions = Transaction.query.filter_by(
            user_id=current_user.id
        ).order_by(Transaction.date.desc()).limit(100).all()
        return jsonify([t.to_dict() for t in transactions])
    elif request.method == 'POST':
        data = request.json
        transaction = Transaction(
            user_id=current_user.id,
            type=data.get('type'),
            category=data.get('category'),
            amount=float(data.get('amount')),
            description=data.get('description'),
            date=datetime.strptime(data.get('date'), '%Y-%m-%d') if data.get('date') else datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        
        today = datetime.now()
        budget = Budget.query.filter_by(
            user_id=current_user.id,
            category=data.get('category'),
            month=today.month,
            year=today.year
        ).first()
        if budget:
            if data.get('type') == 'income':
                budget.actual_amount += float(data.get('amount'))
            elif data.get('type') == 'expense':
                budget.actual_amount += float(data.get('amount'))
            budget.calculate_difference()
            db.session.commit()
        
        return jsonify({'status': 'success', 'id': transaction.id})
    elif request.method == 'DELETE':
        data = request.json
        transaction = Transaction.query.get_or_404(data.get('id'))
        if transaction.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(transaction)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/investments', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
def api_investments():
    if request.method == 'GET':
        investments = Investment.query.filter_by(
            user_id=current_user.id
        ).order_by(Investment.purchase_date.desc()).all()
        return jsonify([i.to_dict() for i in investments])
    elif request.method == 'POST':
        data = request.json
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
        return jsonify({'status': 'success', 'investment_id': investment_id})
    elif request.method == 'DELETE':
        data = request.json
        investment = Investment.query.get_or_404(data.get('id'))
        if investment.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(investment)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/investments/<int:id>/sell', methods=['POST'])
@login_required
@superadmin_required
def sell_investment(id):
    investment = Investment.query.get_or_404(id)
    if investment.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    sell_price = float(data.get('sell_price', 0))
    
    if sell_price <= 0:
        return jsonify({'error': 'Sell price must be greater than 0'}), 400
    
    investment.sell_price = sell_price
    investment.sell_date = datetime.utcnow()
    investment.status = 'Sold'
    investment.profit = sell_price - investment.capital
    investment.roi_actual = (investment.profit / investment.capital) * 100 if investment.capital > 0 else 0
    
    db.session.commit()
    return jsonify({
        'status': 'success', 
        'roi': investment.roi_actual,
        'profit': investment.profit,
        'sell_price': investment.sell_price
    })


@app.route('/api/livestock', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
def api_livestock():
    if request.method == 'GET':
        livestock = Livestock.query.filter_by(
            user_id=current_user.id
        ).order_by(Livestock.purchase_date.desc()).all()
        return jsonify([l.to_dict() for l in livestock])
    elif request.method == 'POST':
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
    elif request.method == 'DELETE':
        data = request.json
        animal = Livestock.query.get_or_404(data.get('id'))
        if animal.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(animal)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/livestock/<int:id>/sell', methods=['POST'])
@login_required
@superadmin_required
def sell_livestock(id):
    animal = Livestock.query.get_or_404(id)
    if animal.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    sell_price = float(data.get('sell_price', 0))
    
    if sell_price <= 0:
        return jsonify({'error': 'Sell price must be greater than 0'}), 400
    
    animal.actual_sell_price = sell_price
    animal.status = 'Sold'
    animal.profit = sell_price - animal.purchase_price
    
    db.session.commit()
    return jsonify({
        'status': 'success',
        'profit': animal.profit,
        'sell_price': animal.actual_sell_price
    })


@app.route('/api/assets', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
def api_assets():
    if request.method == 'GET':
        assets = Asset.query.filter_by(user_id=current_user.id).all()
        return jsonify([a.to_dict() for a in assets])
    elif request.method == 'POST':
        data = request.json
        current_value = float(data.get('current_value', data.get('purchase_price', 0)))
        asset = Asset(
            user_id=current_user.id,
            name=data.get('name'),
            category=data.get('category'),
            sub_category=data.get('sub_category'),
            purchase_price=float(data.get('purchase_price')),
            current_value=current_value,
            depreciation_rate=float(data.get('depreciation_rate', 0)),
            location=data.get('location'),
            condition=data.get('condition', 'Good'),
            notes=data.get('notes')
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify({'status': 'success', 'id': asset.id})
    elif request.method == 'DELETE':
        data = request.json
        asset = Asset.query.get_or_404(data.get('id'))
        if asset.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(asset)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/goals', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@superadmin_required
def api_goals():
    if request.method == 'GET':
        goals = Goal.query.filter_by(user_id=current_user.id).all()
        return jsonify([g.to_dict() for g in goals])
    elif request.method == 'POST':
        data = request.json
        goal = Goal(
            user_id=current_user.id,
            name=data.get('name'),
            target_amount=float(data.get('target_amount')),
            current_amount=float(data.get('current_amount', 0)),
            deadline=datetime.strptime(data.get('deadline'), '%Y-%m-%d') if data.get('deadline') else None,
            category=data.get('category'),
            priority=int(data.get('priority', 1))
        )
        goal.update_progress()
        db.session.add(goal)
        db.session.commit()
        return jsonify({'status': 'success', 'id': goal.id})
    elif request.method == 'PUT':
        data = request.json
        goal = Goal.query.get_or_404(data.get('id'))
        if goal.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        if 'current_amount' in data:
            goal.current_amount = float(data['current_amount'])
            goal.update_progress()
            db.session.commit()
            return jsonify({'status': 'success', 'progress': goal.progress})
        return jsonify({'error': 'No update data'}), 400
    elif request.method == 'DELETE':
        data = request.json
        goal = Goal.query.get_or_404(data.get('id'))
        if goal.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(goal)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/goals/<int:id>/add', methods=['POST'])
@login_required
@superadmin_required
def add_goal_amount(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    
    goal.current_amount += amount
    goal.update_progress()
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'current_amount': goal.current_amount,
        'progress': goal.progress,
        'remaining': goal.target_amount - goal.current_amount
    })


@app.route('/api/budget', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
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
@superadmin_required
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
    
    return jsonify({
        'status': 'success',
        'new_status': status,
        'updated_at': budget.status_updated_at.strftime('%Y-%m-%d %H:%M')
    })


@app.route('/api/liabilities', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
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
@superadmin_required
def mark_liability_paid(id):
    liability = Liability.query.get_or_404(id)
    if liability.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    liability.status = 'Paid'
    liability.paid_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Marked as paid',
        'id': liability.id,
        'new_status': liability.status
    })


@app.route('/api/liabilities/summary')
@login_required
@superadmin_required
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
        Transaction.user_id == user_id,
        Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense'
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


@app.route('/api/rules', methods=['GET', 'POST', 'DELETE'])
@login_required
@superadmin_required
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
@superadmin_required
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
@superadmin_required
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
# ENHANCED RISK API - PROFESSIONAL LEVEL
# ============================

@app.route('/api/risk')
@login_required
@superadmin_required
def get_risk_analysis():
    user_id = current_user.id
    today = datetime.now()
    
    # Investment Risk Analysis
    investments = Investment.query.filter_by(user_id=user_id).all()
    running_investments = [i for i in investments if i.status == 'Running']
    sold_investments = [i for i in investments if i.status == 'Sold']
    
    # Risk classification by type
    high_risk_types = ['Stock', 'Crop', 'Cryptocurrency']
    medium_risk_types = ['Business', 'Real Estate']
    low_risk_types = ['Animal', 'Bonds', 'Savings']
    
    high_risk = len([i for i in running_investments if i.type in high_risk_types])
    medium_risk = len([i for i in running_investments if i.type in medium_risk_types])
    low_risk = len([i for i in running_investments if i.type in low_risk_types])
    
    # Calculate risk exposure (capital at risk)
    high_risk_capital = sum(i.capital for i in running_investments if i.type in high_risk_types)
    medium_risk_capital = sum(i.capital for i in running_investments if i.type in medium_risk_types)
    low_risk_capital = sum(i.capital for i in running_investments if i.type in low_risk_types)
    total_invested = high_risk_capital + medium_risk_capital + low_risk_capital
    
    # Risk concentration (max single investment)
    max_investment = max(running_investments, key=lambda x: x.capital) if running_investments else None
    concentration_risk = (max_investment.capital / total_invested * 100) if total_invested > 0 and max_investment else 0
    
    # Diversification score
    unique_types = set(i.type for i in running_investments)
    diversification_score = min((len(unique_types) / 4) * 100, 100) if running_investments else 0
    
    # Financial Health Risk
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    cash_reserve = total_income - total_expenses
    
    # Monthly burn rate (average monthly expenses)
    monthly_expenses = db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    months_of_runway = cash_reserve / monthly_expenses if monthly_expenses > 0 else 999
    
    # Debt-to-equity ratio
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
    total_liabilities = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id, Liability.type == 'i_owe', Liability.status != 'Paid'
    ).scalar() or 0
    debt_to_equity = total_liabilities / total_assets if total_assets > 0 else 0
    
    # Liquidity risk (cash vs short-term obligations)
    total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id, Liability.type == 'owes_me', Liability.status != 'Paid'
    ).scalar() or 0
    
    # Overall risk level calculation
    risk_score = 0
    risk_factors = []
    
    if high_risk > 2:
        risk_score += 30
        risk_factors.append(f"High risk investments: {high_risk} investments")
    elif high_risk > 0:
        risk_score += 15
        risk_factors.append(f"Some high risk investments: {high_risk}")
    
    if concentration_risk > 50:
        risk_score += 25
        risk_factors.append(f"High concentration risk: {concentration_risk:.1f}% in single investment")
    elif concentration_risk > 30:
        risk_score += 10
        risk_factors.append(f"Moderate concentration risk: {concentration_risk:.1f}%")
    
    if debt_to_equity > 1:
        risk_score += 20
        risk_factors.append(f"High debt-to-equity ratio: {debt_to_equity:.2f}")
    elif debt_to_equity > 0.5:
        risk_score += 10
        risk_factors.append(f"Moderate debt-to-equity ratio: {debt_to_equity:.2f}")
    
    if months_of_runway < 3:
        risk_score += 25
        risk_factors.append(f"Low cash runway: {months_of_runway:.1f} months")
    elif months_of_runway < 6:
        risk_score += 10
        risk_factors.append(f"Limited cash runway: {months_of_runway:.1f} months")
    
    if diversification_score < 40:
        risk_score += 15
        risk_factors.append(f"Low diversification: {diversification_score:.0f}%")
    
    # Determine overall risk level
    if risk_score >= 60:
        overall_risk = 'Critical'
        risk_color = '#ff4757'
    elif risk_score >= 40:
        overall_risk = 'High'
        risk_color = '#ff6b6b'
    elif risk_score >= 25:
        overall_risk = 'Medium'
        risk_color = '#f39c12'
    elif risk_score >= 10:
        overall_risk = 'Low'
        risk_color = '#2ecc71'
    else:
        overall_risk = 'Very Low'
        risk_color = '#00d4ff'
    
    # Risk recommendations
    recommendations = []
    if high_risk > 0:
        recommendations.append(f"Consider reducing high-risk investments ({high_risk}) by diversifying into lower-risk assets.")
    if concentration_risk > 40:
        recommendations.append(f"Reduce concentration risk - no single investment should exceed 40% of your portfolio.")
    if debt_to_equity > 0.7:
        recommendations.append(f"Pay down debt to improve your debt-to-equity ratio of {debt_to_equity:.2f}.")
    if months_of_runway < 6:
        recommendations.append(f"Build more cash reserves - you have {months_of_runway:.1f} months of runway.")
    if diversification_score < 50:
        recommendations.append(f"Improve diversification - invest in at least 3 different investment types.")
    
    return jsonify({
        'high_risk_investments': high_risk,
        'medium_risk_investments': medium_risk,
        'low_risk_investments': low_risk,
        'high_risk_capital': high_risk_capital,
        'medium_risk_capital': medium_risk_capital,
        'low_risk_capital': low_risk_capital,
        'total_invested': total_invested,
        'concentration_risk': round(concentration_risk, 1),
        'diversification_score': round(diversification_score, 1),
        'cash_reserve': cash_reserve,
        'months_of_runway': round(months_of_runway, 1),
        'debt_to_equity': round(debt_to_equity, 3),
        'total_owed_to_me': total_owed_to_me,
        'total_liabilities': total_liabilities,
        'risk_score': risk_score,
        'overall_risk': overall_risk,
        'risk_color': risk_color,
        'risk_factors': risk_factors,
        'recommendations': recommendations[:5],
        'risk_breakdown': {
            'Investment Risk': min(high_risk * 10, 100),
            'Concentration Risk': min(concentration_risk * 2, 100),
            'Debt Risk': min(debt_to_equity * 50, 100),
            'Liquidity Risk': max(0, 100 - min(months_of_runway * 15, 100)),
            'Diversification Risk': max(0, 100 - diversification_score)
        }
    })


# ============================
# ANALYTICS API
# ============================

@app.route('/api/analytics/<chart_type>')
@login_required
@superadmin_required
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
@superadmin_required
def get_timeline():
    user_id = current_user.id
    events = []
    for t in Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(50).all():
        events.append({
            'date': t.date.strftime('%Y-%m-%d'),
            'type': 'transaction',
            'title': f"{t.type.capitalize()}: {t.category}",
            'description': f"{t.amount:,.0f} BIF",
            'icon': '💰'
        })
    for i in Investment.query.filter_by(user_id=user_id).order_by(Investment.purchase_date.desc()).limit(30).all():
        events.append({
            'date': i.purchase_date.strftime('%Y-%m-%d'),
            'type': 'investment',
            'title': f"Investment: {i.investment_id}",
            'description': f"{i.capital:,.0f} BIF - {i.type}",
            'icon': '📊'
        })
    for l in Livestock.query.filter_by(user_id=user_id).order_by(Livestock.purchase_date.desc()).limit(30).all():
        events.append({
            'date': l.purchase_date.strftime('%Y-%m-%d'),
            'type': 'livestock',
            'title': f"Added: {l.type} - {l.tag}",
            'description': f"Purchased for {l.purchase_price:,.0f} BIF",
            'icon': '🐄'
        })
    for g in Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).limit(20).all():
        events.append({
            'date': g.created_at.strftime('%Y-%m-%d'),
            'type': 'goal',
            'title': f"Goal: {g.name}",
            'description': f"Target: {g.target_amount:,.0f} BIF ({g.progress:.0f}%)",
            'icon': '🎯'
        })
    events.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(events[:100])


# ============================
# ENHANCED AI DECISIONS - FIXED
# ============================

@app.route('/api/decisions')
@login_required
@superadmin_required
def get_decisions():
    recommendations = []
    user_id = current_user.id
    today = datetime.now()
    
    # 1. FINANCIAL HEALTH ANALYSIS
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    net_cash = total_income - total_expenses
    
    # Monthly averages
    monthly_income = total_income / 12 if total_income > 0 else 0
    monthly_expenses = total_expenses / 12 if total_expenses > 0 else 0
    
    # Savings rate
    savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
    
    if savings_rate < 10:
        recommendations.append({
            'title': '⚠️ Low Savings Rate',
            'message': f'You save only {savings_rate:.1f}% of your income. Aim for at least 20%.',
            'type': 'warning',
            'priority': 'high',
            'action': 'Review your expenses and cut unnecessary spending.'
        })
    elif savings_rate < 20:
        recommendations.append({
            'title': '📈 Improve Savings Rate',
            'message': f'Your savings rate is {savings_rate:.1f}%. Consider increasing to 20%+ for better financial security.',
            'type': 'opportunity',
            'priority': 'medium',
            'action': 'Look for areas to reduce expenses or increase income.'
        })
    else:
        recommendations.append({
            'title': '✅ Excellent Savings Rate',
            'message': f'You save {savings_rate:.1f}% of your income. Keep up the great work!',
            'type': 'success',
            'priority': 'low',
            'action': 'Consider investing your savings for better returns.'
        })
    
    # 2. EMERGENCY FUND ANALYSIS
    avg_monthly_expense = db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 1
    emergency_fund_months = net_cash / (avg_monthly_expense * 3) if avg_monthly_expense > 0 else 0
    
    if emergency_fund_months < 3:
        recommendations.append({
            'title': '🚨 Emergency Fund Critical',
            'message': f'Your emergency fund covers only {emergency_fund_months:.1f} months. Need at least 3-6 months.',
            'type': 'critical',
            'priority': 'high',
            'action': f'Build emergency fund to {avg_monthly_expense * 3:,.0f} BIF minimum.'
        })
    elif emergency_fund_months < 6:
        recommendations.append({
            'title': '🛡️ Build Emergency Fund',
            'message': f'You have {emergency_fund_months:.1f} months of expenses saved. Aim for 6 months.',
            'type': 'warning',
            'priority': 'medium',
            'action': f'Target: {avg_monthly_expense * 6:,.0f} BIF for full emergency fund.'
        })
    else:
        recommendations.append({
            'title': '✅ Strong Emergency Fund',
            'message': f'You have {emergency_fund_months:.1f} months of expenses saved. Well prepared!',
            'type': 'success',
            'priority': 'low',
            'action': 'Consider investing excess cash for better returns.'
        })
    
    # 3. INVESTMENT OPPORTUNITIES
    investments = Investment.query.filter_by(user_id=user_id, status='Running').all()
    total_invested = sum(i.capital for i in investments)
    
    # SAFE: Best performing investment type - only if there are sold investments
    sold_investments = Investment.query.filter_by(user_id=user_id, status='Sold').all()
    if sold_investments:
        try:
            best_type = db.session.query(
                Investment.type,
                func.avg(Investment.roi_actual).label('avg_roi'),
                func.count(Investment.id).label('count')
            ).filter(
                Investment.user_id == user_id,
                Investment.status == 'Sold'
            ).group_by(Investment.type).order_by(func.avg(Investment.roi_actual).desc()).first()
            
            if best_type and best_type[1] is not None and best_type[1] > 0:
                recommendations.append({
                    'title': f'📈 Best Investment: {best_type[0]}',
                    'message': f'Your {best_type[0]} investments averaged {best_type[1]:.1f}% ROI from {best_type[2]} investments.',
                    'type': 'opportunity',
                    'priority': 'medium',
                    'action': f'Consider allocating more capital to {best_type[0]} investments.'
                })
        except Exception as e:
            print(f"Error calculating best investment: {e}")
    
    # SAFE: Underperforming investments - only if there are running investments
    if investments:
        try:
            # Calculate ROI for each investment
            for inv in investments:
                # If investment has been sold, use actual ROI, otherwise estimate
                if inv.roi_actual and inv.roi_actual < 5:
                    recommendations.append({
                        'title': f'⚠️ Underperforming: {inv.investment_id}',
                        'message': f'{inv.type} investment with ROI of {inv.roi_actual:.1f}%. Consider reviewing.',
                        'type': 'warning',
                        'priority': 'medium',
                        'action': f'Review {inv.type} investment strategy or consider selling.'
                    })
        except Exception as e:
            print(f"Error checking underperforming investments: {e}")
    
    # Investment diversification
    if total_invested > 0:
        try:
            type_count = len(set(i.type for i in investments))
            if type_count < 3:
                recommendations.append({
                    'title': '📊 Improve Diversification',
                    'message': f'You have investments in only {type_count} type(s). Diversify for better risk management.',
                    'type': 'opportunity',
                    'priority': 'medium',
                    'action': 'Consider investing in different asset classes like Livestock, Business, or Stocks.'
                })
        except Exception as e:
            print(f"Error checking diversification: {e}")
    
    # 4. BUDGET ANALYSIS
    budgets = Budget.query.filter_by(user_id=user_id, month=today.month, year=today.year).all()
    over_budget = [b for b in budgets if b.actual_amount > b.expected_amount]
    under_budget = [b for b in budgets if b.actual_amount < b.expected_amount]
    
    if over_budget:
        for b in over_budget[:3]:
            try:
                pct_used = (b.actual_amount / b.expected_amount * 100) if b.expected_amount > 0 else 0
                recommendations.append({
                    'title': f'⚠️ Over Budget: {b.category}',
                    'message': f'Spent {b.actual_amount - b.expected_amount:,.0f} BIF over budget ({pct_used:.0f}% of budget).',
                    'type': 'warning',
                    'priority': 'high',
                    'action': f'Reduce {b.category} spending by setting stricter limits.'
                })
            except Exception as e:
                print(f"Error processing over budget: {e}")
    
    if under_budget and len(under_budget) > 0:
        try:
            best_saver = sorted(under_budget, key=lambda x: x.expected_amount - x.actual_amount, reverse=True)[0]
            if best_saver:
                recommendations.append({
                    'title': f'✅ Under Budget: {best_saver.category}',
                    'message': f'You saved {best_saver.expected_amount - best_saver.actual_amount:,.0f} BIF on {best_saver.category}.',
                    'type': 'success',
                    'priority': 'low',
                    'action': 'Consider allocating savings to investments or debt repayment.'
                })
        except Exception as e:
            print(f"Error processing under budget: {e}")
    
    # 5. GOAL PROGRESS
    goals = Goal.query.filter_by(user_id=user_id, status='Active').all()
    if goals:
        try:
            # Goals with best progress
            best_goal = max(goals, key=lambda x: x.progress) if goals else None
            if best_goal and best_goal.progress > 0:
                recommendations.append({
                    'title': f'🎯 Best Goal: {best_goal.name}',
                    'message': f'Progress: {best_goal.progress:.0f}% toward {best_goal.target_amount:,.0f} BIF target.',
                    'type': 'success',
                    'priority': 'low',
                    'action': 'Keep the momentum going!'
                })
            
            # Goals with poor progress
            slow_goals = [g for g in goals if g.progress < 20 and g.created_at < (datetime.now() - timedelta(days=30))]
            for g in slow_goals[:2]:
                days_old = (today - g.created_at).days
                recommendations.append({
                    'title': f'⚠️ Slow Progress: {g.name}',
                    'message': f'Only {g.progress:.0f}% progress after {days_old} days. Need more focus.',
                    'type': 'warning',
                    'priority': 'medium',
                    'action': f'Increase contributions to {g.name} goal.'
                })
        except Exception as e:
            print(f"Error processing goals: {e}")
    
    # 6. LIVESTOCK OPPORTUNITIES
    livestock = Livestock.query.filter_by(user_id=user_id, status='Active').all()
    ready_to_sell = [l for l in livestock if l.expected_sell_date and l.expected_sell_date <= today]
    
    if ready_to_sell:
        recommendations.append({
            'title': f'🐄 {len(ready_to_sell)} Animals Ready to Sell',
            'message': 'These animals have reached their expected sell date. Time to cash in!',
            'type': 'opportunity',
            'priority': 'high',
            'action': 'Go to Livestock section and sell these animals for profit.'
        })
    
    # SAFE: Best livestock type for profit - only if there are sold livestock
    sold_livestock = Livestock.query.filter_by(user_id=user_id, status='Sold').all()
    if sold_livestock:
        try:
            best_livestock = db.session.query(
                Livestock.type,
                func.avg(Livestock.profit).label('avg_profit')
            ).filter(
                Livestock.user_id == user_id,
                Livestock.status == 'Sold'
            ).group_by(Livestock.type).order_by(func.avg(Livestock.profit).desc()).first()
            
            if best_livestock and best_livestock[1] is not None and best_livestock[1] > 0:
                recommendations.append({
                    'title': f'🐄 Best Livestock: {best_livestock[0]}',
                    'message': f'Average profit of {best_livestock[1]:,.0f} BIF per animal. Focus on this type!',
                    'type': 'opportunity',
                    'priority': 'medium',
                    'action': f'Consider expanding your {best_livestock[0]} operation.'
                })
        except Exception as e:
            print(f"Error calculating best livestock: {e}")
    
    # 7. LIABILITIES MANAGEMENT
    total_owed = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id,
        Liability.type == 'i_owe',
        Liability.status != 'Paid'
    ).scalar() or 0
    
    total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
        Liability.user_id == user_id,
        Liability.type == 'owes_me',
        Liability.status != 'Paid'
    ).scalar() or 0
    
    if total_owed > 0:
        # Check for overdue liabilities
        overdue = Liability.query.filter(
            Liability.user_id == user_id,
            Liability.type == 'i_owe',
            Liability.status == 'Pending',
            Liability.due_date < today
        ).all()
        
        if overdue:
            for l in overdue[:3]:
                try:
                    days_overdue = (today - l.due_date).days
                    recommendations.append({
                        'title': f'⚠️ Overdue Debt: {l.name}',
                        'message': f'{l.amount:,.0f} BIF is {days_overdue} days overdue.',
                        'type': 'critical',
                        'priority': 'high',
                        'action': f'Pay {l.name} immediately to avoid penalties.'
                    })
                except Exception as e:
                    print(f"Error processing overdue: {e}")
    
    # 8. ASSET UTILIZATION
    total_asset_value = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
    if total_asset_value > 0:
        try:
            # Check for deprecated assets (older than 5 years)
            five_years_ago = today - timedelta(days=365*5)
            old_assets = Asset.query.filter(
                Asset.user_id == user_id,
                Asset.purchase_date < five_years_ago,
                Asset.current_value < Asset.purchase_price * 0.5
            ).all()
            
            if old_assets:
                for a in old_assets[:2]:
                    depreciation = (1 - (a.current_value / a.purchase_price)) * 100
                    recommendations.append({
                        'title': f'⚠️ Depreciating Asset: {a.name}',
                        'message': f'Value dropped {depreciation:.0f}% since purchase. Consider replacing or selling.',
                        'type': 'warning',
                        'priority': 'medium',
                        'action': f'Review if {a.name} still provides value or should be replaced.'
                    })
        except Exception as e:
            print(f"Error processing assets: {e}")
    
    # 9. CASH FLOW OPPORTUNITIES
    if net_cash > 0 and total_income > 0:
        try:
            extra_cash = net_cash * 0.1  # 10% of net cash
            recommendations.append({
                'title': '💰 Cash Available for Investment',
                'message': f'You have {net_cash:,.0f} BIF in net cash. Consider allocating {extra_cash:,.0f} BIF to investments.',
                'type': 'opportunity',
                'priority': 'medium',
                'action': 'Check investment opportunities in the Investments section.'
            })
        except Exception as e:
            print(f"Error processing cash flow: {e}")
    
    # 10. OVERALL FINANCIAL SCORE
    try:
        # Calculate overall financial health score
        score = 0
        score += min(savings_rate * 2, 40)  # Max 40 points for savings rate
        score += min(emergency_fund_months * 5, 25)  # Max 25 points for emergency fund
        if investments:
            type_count = len(set(i.type for i in investments))
            score += min(type_count * 8, 20)  # Max 20 for diversification
        score += 15 if total_owed == 0 else max(0, 15 - (total_owed / (total_income + 1) * 10))  # Debt management
        
        financial_health = 'Excellent' if score >= 80 else 'Good' if score >= 60 else 'Fair' if score >= 40 else 'Needs Improvement'
        
        recommendations.append({
            'title': f'📊 Financial Health Score: {score:.0f}/100',
            'message': f'Your financial health is {financial_health}. Score based on savings, emergency fund, diversification, and debt management.',
            'type': 'info' if score >= 60 else 'warning',
            'priority': 'low',
            'action': 'Check the detailed recommendations above to improve your score.'
        })
    except Exception as e:
        print(f"Error calculating financial score: {e}")
    
    # Sort recommendations by priority
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4, 'success': 5, 'warning': 2, 'opportunity': 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))
    
    return jsonify(recommendations[:15])


# ============================
# ENHANCED NOTIFICATIONS - ADVANCED & DATA-DRIVEN
# ============================

@app.route('/api/notifications')
@login_required
@superadmin_required
def get_notifications():
    user_id = current_user.id
    today = datetime.now()
    notifications = []
    
    # 1. Check unread notifications from database
    db_notifications = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    for n in db_notifications:
        notifications.append(n.to_dict())
    
    # 2. SYSTEM ALERTS - Critical issues
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    net_cash = total_income - total_expenses
    
    # Emergency fund alert
    avg_monthly_expense = db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 1
    emergency_months = net_cash / (avg_monthly_expense * 3) if avg_monthly_expense > 0 else 0
    
    if emergency_months < 3:
        notifications.append({
            'title': '🚨 Emergency Fund Critical',
            'message': f'Your emergency fund covers only {emergency_months:.1f} months. Need at least 3-6 months of expenses.',
            'type': 'critical',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # Overdue liabilities
    overdue_liabilities = Liability.query.filter(
        Liability.user_id == user_id,
        Liability.type == 'i_owe',
        Liability.status == 'Pending',
        Liability.due_date < today
    ).all()
    
    if overdue_liabilities:
        total_overdue = sum(l.amount for l in overdue_liabilities)
        notifications.append({
            'title': f'⚠️ {len(overdue_liabilities)} Overdue Payments',
            'message': f'Total overdue: {total_overdue:,.0f} BIF. Pay immediately to avoid penalties.',
            'type': 'critical',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # 3. FINANCIAL ALERTS
    
    # Budget overruns
    budgets = Budget.query.filter_by(user_id=user_id, month=today.month, year=today.year).all()
    over_budget = [b for b in budgets if b.actual_amount > b.expected_amount]
    
    if over_budget:
        for b in over_budget[:3]:
            notifications.append({
                'title': f'⚠️ Budget Overrun: {b.category}',
                'message': f'Spent {b.actual_amount - b.expected_amount:,.0f} BIF over budget ({b.actual_amount/b.expected_amount*100:.0f}% used).',
                'type': 'warning',
                'is_read': False,
                'created_at': today.strftime('%Y-%m-%d %H:%M')
            })
    
    # 4. INVESTMENT ALERTS
    
    # Investments nearing exit date (within 30 days)
    thirty_days_later = today + timedelta(days=30)
    nearing_exit = Investment.query.filter(
        Investment.user_id == user_id,
        Investment.status == 'Running',
        Investment.expected_exit_date <= thirty_days_later,
        Investment.expected_exit_date >= today
    ).all()
    
    if nearing_exit:
        for inv in nearing_exit[:3]:
            days_left = (inv.expected_exit_date - today).days
            notifications.append({
                'title': f'📊 Investment: {inv.investment_id}',
                'message': f'Exit date in {days_left} days. Capital: {inv.capital:,.0f} BIF. Start planning your exit strategy.',
                'type': 'info',
                'is_read': False,
                'created_at': today.strftime('%Y-%m-%d %H:%M')
            })
    
    # 5. LIVESTOCK ALERTS
    
    # Animals ready to sell
    ready_to_sell = Livestock.query.filter(
        Livestock.user_id == user_id,
        Livestock.status == 'Active',
        Livestock.expected_sell_date <= today
    ).all()
    
    if ready_to_sell:
        notifications.append({
            'title': f'🐄 {len(ready_to_sell)} Animals Ready to Sell',
            'message': 'These animals have reached their expected sell date. Sell them to realize profit!',
            'type': 'opportunity',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # 6. GOAL ALERTS
    
    # Goals near completion (90%+)
    near_completion = Goal.query.filter(
        Goal.user_id == user_id,
        Goal.status == 'Active',
        Goal.progress >= 90
    ).all()
    
    if near_completion:
        for g in near_completion[:3]:
            notifications.append({
                'title': f'🎯 Goal Near Completion: {g.name}',
                'message': f'Progress: {g.progress:.0f}% - only {g.target_amount - g.current_amount:,.0f} BIF remaining!',
                'type': 'success',
                'is_read': False,
                'created_at': today.strftime('%Y-%m-%d %H:%M')
            })
    
    # Goals behind schedule (created > 30 days, progress < 10%)
    thirty_days_ago = today - timedelta(days=30)
    behind_schedule = Goal.query.filter(
        Goal.user_id == user_id,
        Goal.status == 'Active',
        Goal.created_at <= thirty_days_ago,
        Goal.progress < 10
    ).all()
    
    if behind_schedule:
        for g in behind_schedule[:3]:
            notifications.append({
                'title': f'⚠️ Goal Behind Schedule: {g.name}',
                'message': f'Only {g.progress:.0f}% progress after {(today - g.created_at).days} days. Need more focus!',
                'type': 'warning',
                'is_read': False,
                'created_at': today.strftime('%Y-%m-%d %H:%M')
            })
    
    # 7. ASSET ALERTS
    
    # Assets with high depreciation (value drop > 30%)
    high_depreciation = Asset.query.filter(
        Asset.user_id == user_id,
        Asset.purchase_price > 0,
        Asset.current_value < Asset.purchase_price * 0.7
    ).all()
    
    if high_depreciation:
        for a in high_depreciation[:3]:
            depreciation_pct = (1 - (a.current_value / a.purchase_price)) * 100
            notifications.append({
                'title': f'⚠️ Asset Depreciation: {a.name}',
                'message': f'Value dropped {depreciation_pct:.0f}% to {a.current_value:,.0f} BIF. Consider reviewing.',
                'type': 'warning',
                'is_read': False,
                'created_at': today.strftime('%Y-%m-%d %H:%M')
            })
    
    # 8. CASH FLOW ALERTS
    
    # Negative cash flow alert
    if net_cash < 0:
        notifications.append({
            'title': '💸 Negative Cash Flow',
            'message': f'Your expenses ({total_expenses:,.0f} BIF) exceed income ({total_income:,.0f} BIF). Reduce spending!',
            'type': 'critical',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # 9. DAILY/PERIODIC REMINDERS
    
    # Check if there are unread notifications
    unread_count = len([n for n in notifications if not n.get('is_read', True)])
    if unread_count > 5:
        notifications.append({
            'title': f'📬 {unread_count} Unread Notifications',
            'message': 'You have important notifications waiting. Review them to stay on top of your finances.',
            'type': 'info',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # 10. OPPORTUNITY ALERTS
    
    # Cash available for investment
    if net_cash > 100000:
        notifications.append({
            'title': '💰 Cash Available for Investment',
            'message': f'You have {net_cash:,.0f} BIF in cash. Consider investing to grow your wealth.',
            'type': 'opportunity',
            'is_read': False,
            'created_at': today.strftime('%Y-%m-%d %H:%M')
        })
    
    # Sort notifications by type (critical first, then warnings, then info)
    type_order = {'critical': 0, 'warning': 1, 'opportunity': 2, 'info': 3, 'success': 4}
    notifications.sort(key=lambda x: type_order.get(x.get('type', 'info'), 5))
    
    return jsonify(notifications[:20])


# ============================
# COMPLETE REPORTS API - FULLY WORKING
# ============================

@app.route('/api/reports/<report_type>')
@login_required
@superadmin_required
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
        
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        
        return jsonify({
            'income': [{'category': i[1], 'total': float(i[0])} for i in income],
            'expenses': [{'category': i[1], 'total': float(i[0])} for i in expenses],
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_income': total_income - total_expenses
        })
    elif report_type == 'balance_sheet':
        total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        total_investments = db.session.query(func.sum(Investment.capital)).filter(
            Investment.user_id == user_id, Investment.status == 'Running'
        ).scalar() or 0
        total_liabilities = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id, Liability.type == 'i_owe', Liability.status != 'Paid'
        ).scalar() or 0
        total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id, Liability.type == 'owes_me', Liability.status != 'Paid'
        ).scalar() or 0
        
        return jsonify({
            'total_assets': total_assets,
            'total_investments': total_investments,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'total_liabilities': total_liabilities,
            'total_owed_to_me': total_owed_to_me,
            'net_worth': total_assets + total_income - total_expenses + total_owed_to_me - total_liabilities
        })
    return jsonify({'error': 'Invalid report type'}), 400


@app.route('/api/reports/export/transactions/<format>')
@login_required
@superadmin_required
def export_transactions(format):
    user_id = current_user.id
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
    
    if format == 'pdf':
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#00d4ff'))
        story.append(Paragraph("📊 Transactions Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"User: {current_user.username}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
        
        summary_data = [
            ['Metric', 'Amount (BIF)'],
            ['Total Income', f"{total_income:,.0f}"],
            ['Total Expenses', f"{total_expenses:,.0f}"],
            ['Net Cash', f"{total_income - total_expenses:,.0f}"]
        ]
        summary_table = Table(summary_data, colWidths=[2*inch, 2.5*inch])
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
        
        if transactions:
            data = [['Date', 'Type', 'Category', 'Amount (BIF)', 'Description']]
            for t in transactions:
                data.append([
                    t.date.strftime('%Y-%m-%d %H:%M'),
                    t.type.capitalize(),
                    t.category,
                    f"{t.amount:,.0f}",
                    t.description or ''
                ])
            
            table = Table(data, colWidths=[1.2*inch, 0.8*inch, 1.2*inch, 1.0*inch, 2.0*inch])
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
            story.append(Paragraph("No transactions found.", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Transactions_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    elif format == 'excel':
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Transactions')
        
        headers = ['Date', 'Type', 'Category', 'Amount (BIF)', 'Description']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        for row, t in enumerate(transactions, 1):
            worksheet.write(row, 0, t.date.strftime('%Y-%m-%d %H:%M'))
            worksheet.write(row, 1, t.type)
            worksheet.write(row, 2, t.category)
            worksheet.write(row, 3, t.amount)
            worksheet.write(row, 4, t.description or '')
        
        workbook.close()
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"Transactions_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    
    return jsonify({'error': 'Invalid format'}), 400


@app.route('/api/reports/export/<report_type>/<format>')
@login_required
@superadmin_required
def export_report(report_type, format):
    user_id = current_user.id
    
    # Handle transactions export separately
    if report_type == 'transactions':
        return export_transactions(format)
    
    # Handle income_statement PDF
    if report_type == 'income_statement' and format == 'pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#00d4ff'))
        story.append(Paragraph("📊 Income Statement", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"User: {current_user.username}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        income_data = db.session.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'income'
        ).group_by(Transaction.category).all()
        
        expense_data = db.session.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense'
        ).group_by(Transaction.category).all()
        
        total_income = sum(i[1] for i in income_data)
        total_expenses = sum(i[1] for i in expense_data)
        
        # Income table
        story.append(Paragraph("<b>💰 INCOME</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        income_table_data = [['Category', 'Amount (BIF)']]
        for cat, amt in income_data:
            income_table_data.append([cat, f"{amt:,.0f}"])
        income_table_data.append(['TOTAL', f"{total_income:,.0f}"])
        
        income_table = Table(income_table_data, colWidths=[2.5*inch, 2.5*inch])
        income_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
            ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#111a2b')),
            ('TEXTCOLOR', (0, 1), (-1, -2), colors.whitesmoke),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1a3a2f')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(income_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Expenses table
        story.append(Paragraph("<b>💸 EXPENSES</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        expense_table_data = [['Category', 'Amount (BIF)']]
        for cat, amt in expense_data:
            expense_table_data.append([cat, f"{amt:,.0f}"])
        expense_table_data.append(['TOTAL', f"{total_expenses:,.0f}"])
        
        expense_table = Table(expense_table_data, colWidths=[2.5*inch, 2.5*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
            ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#111a2b')),
            ('TEXTCOLOR', (0, 1), (-1, -2), colors.whitesmoke),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1a3a2f')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(expense_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Summary
        story.append(Paragraph("<b>📊 SUMMARY</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        summary_data = [
            ['Metric', 'Amount (BIF)'],
            ['Total Income', f"{total_income:,.0f}"],
            ['Total Expenses', f"{total_expenses:,.0f}"],
            ['Net Income', f"{total_income - total_expenses:,.0f}"]
        ]
        summary_table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
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
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Income_Statement_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    # Handle balance_sheet PDF
    if report_type == 'balance_sheet' and format == 'pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#00d4ff'))
        story.append(Paragraph("📊 Balance Sheet", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"User: {current_user.username}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
        total_investments = db.session.query(func.sum(Investment.capital)).filter(
            Investment.user_id == user_id, Investment.status == 'Running'
        ).scalar() or 0
        total_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income'
        ).scalar() or 0
        total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense'
        ).scalar() or 0
        total_liabilities = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id, Liability.type == 'i_owe', Liability.status != 'Paid'
        ).scalar() or 0
        total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
            Liability.user_id == user_id, Liability.type == 'owes_me', Liability.status != 'Paid'
        ).scalar() or 0
        
        data = [
            ['ASSETS', 'Amount (BIF)'],
            ['Total Assets', f"{total_assets:,.0f}"],
            ['Total Investments', f"{total_investments:,.0f}"],
            ['', ''],
            ['INCOME & EXPENSES', ''],
            ['Total Income', f"{total_income:,.0f}"],
            ['Total Expenses', f"{total_expenses:,.0f}"],
            ['Net Cash', f"{total_income - total_expenses:,.0f}"],
            ['', ''],
            ['LIABILITIES', ''],
            ['Total Liabilities', f"{total_liabilities:,.0f}"],
            ['Owed to Me', f"{total_owed_to_me:,.0f}"],
            ['', ''],
            ['NET WORTH', ''],
            ['Net Worth', f"{total_assets + total_income - total_expenses + total_owed_to_me - total_liabilities:,.0f}"]
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a3f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1a2332')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#111a2b')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#1a2a3f')),
            ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#1a2a3f')),
            ('BACKGROUND', (0, 11), (-1, 11), colors.HexColor('#1a2a3f')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1a3a2f')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(table)
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Balance_Sheet_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    # Handle Excel exports for income_statement and balance_sheet
    if format == 'excel':
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        if report_type == 'income_statement':
            worksheet = workbook.add_worksheet('Income Statement')
            income_data = db.session.query(
                Transaction.category,
                func.sum(Transaction.amount).label('total')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'income'
            ).group_by(Transaction.category).all()
            
            expense_data = db.session.query(
                Transaction.category,
                func.sum(Transaction.amount).label('total')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense'
            ).group_by(Transaction.category).all()
            
            total_income = sum(i[1] for i in income_data)
            total_expenses = sum(i[1] for i in expense_data)
            
            worksheet.write(0, 0, 'INCOME')
            worksheet.write(1, 0, 'Category')
            worksheet.write(1, 1, 'Amount (BIF)')
            row = 2
            for cat, amt in income_data:
                worksheet.write(row, 0, cat)
                worksheet.write(row, 1, amt)
                row += 1
            worksheet.write(row, 0, 'TOTAL')
            worksheet.write(row, 1, total_income)
            row += 2
            
            worksheet.write(row, 0, 'EXPENSES')
            row += 1
            worksheet.write(row, 0, 'Category')
            worksheet.write(row, 1, 'Amount (BIF)')
            row += 1
            for cat, amt in expense_data:
                worksheet.write(row, 0, cat)
                worksheet.write(row, 1, amt)
                row += 1
            worksheet.write(row, 0, 'TOTAL')
            worksheet.write(row, 1, total_expenses)
            row += 2
            worksheet.write(row, 0, 'NET INCOME')
            worksheet.write(row, 1, total_income - total_expenses)
            
        elif report_type == 'balance_sheet':
            worksheet = workbook.add_worksheet('Balance Sheet')
            total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
            total_investments = db.session.query(func.sum(Investment.capital)).filter(
                Investment.user_id == user_id, Investment.status == 'Running'
            ).scalar() or 0
            total_income = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'income'
            ).scalar() or 0
            total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'expense'
            ).scalar() or 0
            total_liabilities = db.session.query(func.sum(Liability.amount)).filter(
                Liability.user_id == user_id, Liability.type == 'i_owe', Liability.status != 'Paid'
            ).scalar() or 0
            total_owed_to_me = db.session.query(func.sum(Liability.amount)).filter(
                Liability.user_id == user_id, Liability.type == 'owes_me', Liability.status != 'Paid'
            ).scalar() or 0
            
            row = 0
            worksheet.write(row, 0, 'ASSETS')
            row += 1
            worksheet.write(row, 0, 'Total Assets')
            worksheet.write(row, 1, total_assets)
            row += 1
            worksheet.write(row, 0, 'Total Investments')
            worksheet.write(row, 1, total_investments)
            row += 2
            
            worksheet.write(row, 0, 'INCOME & EXPENSES')
            row += 1
            worksheet.write(row, 0, 'Total Income')
            worksheet.write(row, 1, total_income)
            row += 1
            worksheet.write(row, 0, 'Total Expenses')
            worksheet.write(row, 1, total_expenses)
            row += 1
            worksheet.write(row, 0, 'Net Cash')
            worksheet.write(row, 1, total_income - total_expenses)
            row += 2
            
            worksheet.write(row, 0, 'LIABILITIES')
            row += 1
            worksheet.write(row, 0, 'Total Liabilities')
            worksheet.write(row, 1, total_liabilities)
            row += 1
            worksheet.write(row, 0, 'Owed to Me')
            worksheet.write(row, 1, total_owed_to_me)
            row += 2
            
            worksheet.write(row, 0, 'NET WORTH')
            row += 1
            worksheet.write(row, 0, 'Net Worth')
            worksheet.write(row, 1, total_assets + total_income - total_expenses + total_owed_to_me - total_liabilities)
        
        workbook.close()
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"{report_type.replace('_', '_').capitalize()}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    
    return jsonify({'error': 'Invalid format'}), 400


# ============================
# FULL REPORT EXPORT (All Data)
# ============================

@app.route('/api/reports/export/full/<format>')
@login_required
@superadmin_required
def export_full_report(format):
    user_id = current_user.id
    all_transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
    investments = Investment.query.filter_by(user_id=user_id).all()
    livestock = Livestock.query.filter_by(user_id=user_id).all()
    assets = Asset.query.filter_by(user_id=user_id).all()
    goals = Goal.query.filter_by(user_id=user_id).all()
    budgets = Budget.query.filter_by(user_id=user_id).all()
    liabilities = Liability.query.filter_by(user_id=user_id).all()
    rules = FinancialRule.query.filter_by(user_id=user_id, is_active=True).all()
    
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
        story.append(Paragraph("💰 BuSystem - Full Financial Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"User: {current_user.username}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Executive Summary
        story.append(Paragraph("<b>📊 EXECUTIVE SUMMARY</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        total_income = sum(t.amount for t in all_transactions if t.type == 'income')
        total_expenses = sum(t.amount for t in all_transactions if t.type == 'expense')
        total_assets_val = sum(a.current_value for a in assets)
        total_investments_val = sum(i.capital for i in investments if i.status == 'Running')
        
        summary_data = [
            ['Metric', 'Amount (BIF)'],
            ['Total Income', f"{total_income:,.0f}"],
            ['Total Expenses', f"{total_expenses:,.0f}"],
            ['Net Cash', f"{total_income - total_expenses:,.0f}"],
            ['Total Assets', f"{total_assets_val:,.0f}"],
            ['Total Investments', f"{total_investments_val:,.0f}"],
            ['Total Livestock', f"{len(livestock)}"],
            ['Active Goals', f"{len([g for g in goals if g.status == 'Active'])}"]
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
        
        if all_transactions:
            tx_data = [['Date', 'Type', 'Category', 'Amount', 'Description']]
            for t in all_transactions[:200]:
                tx_data.append([
                    t.date.strftime('%Y-%m-%d'),
                    t.type.capitalize(),
                    t.category,
                    f"{t.amount:,.0f}",
                    t.description or ''
                ])
            tx_table = Table(tx_data, colWidths=[1.0*inch, 0.8*inch, 1.2*inch, 1.0*inch, 1.5*inch])
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
        
        # Investments
        story.append(PageBreak())
        story.append(Paragraph("<b>📈 INVESTMENTS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
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
            inv_table = Table(inv_data, colWidths=[0.8*inch, 1.2*inch, 1.0*inch, 0.8*inch, 1.0*inch, 0.8*inch])
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
        
        # Livestock
        story.append(PageBreak())
        story.append(Paragraph("<b>🐄 LIVESTOCK</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
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
            ls_table = Table(ls_data, colWidths=[0.8*inch, 0.8*inch, 0.8*inch, 1.0*inch, 0.8*inch, 1.0*inch])
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
        
        # Assets
        story.append(PageBreak())
        story.append(Paragraph("<b>🏦 ASSETS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
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
            asset_table = Table(asset_data, colWidths=[1.2*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.8*inch])
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
        
        # Goals
        story.append(PageBreak())
        story.append(Paragraph("<b>🎯 GOALS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
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
            goal_table = Table(goal_data, colWidths=[1.2*inch, 1.0*inch, 1.0*inch, 0.8*inch, 0.8*inch])
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
        
        # Budgets
        story.append(PageBreak())
        story.append(Paragraph("<b>📋 BUDGETS</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        if budgets:
            budget_data = [['Category', 'Type', 'Month/Year', 'Expected', 'Actual', 'Difference']]
            for b in budgets:
                month_name = datetime(b.year, b.month, 1).strftime('%B %Y')
                budget_data.append([
                    b.category,
                    b.type,
                    month_name,
                    f"{b.expected_amount:,.0f}",
                    f"{b.actual_amount:,.0f}",
                    f"{b.difference:+,.0f}"
                ])
            budget_table = Table(budget_data, colWidths=[1.0*inch, 0.8*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch])
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
        
        story.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle('Footer', fontSize=10, alignment=1, textColor=colors.HexColor('#4a5a6f'))
        story.append(Paragraph("BuSystem v1.0 • Every Franc Must Have a Job", footer_style))
        story.append(Paragraph(f"Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}", footer_style))
        story.append(Paragraph(f"User: {current_user.username} • Currency: BIF", footer_style))
        
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Full_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    return jsonify({'error': 'Invalid format'}), 400





# ============================
# SUPERADMIN PAGE ROUTES
# ============================

@app.route('/cashflow')
@login_required
@superadmin_required
def cashflow():
    return render_template('cashflow.html', user=current_user)


@app.route('/investments')
@login_required
@superadmin_required
def investments():
    return render_template('investments.html', user=current_user)


@app.route('/livestock')
@login_required
@superadmin_required
def livestock():
    return render_template('livestock.html', user=current_user)


@app.route('/assets')
@login_required
@superadmin_required
def assets():
    return render_template('assets.html', user=current_user)


@app.route('/goals')
@login_required
@superadmin_required
def goals():
    return render_template('goals.html', user=current_user)


@app.route('/budget')
@login_required
@superadmin_required
def budget():
    return render_template('budget.html', user=current_user)


@app.route('/liability')
@login_required
@superadmin_required
def liability():
    return render_template('liability.html', user=current_user)


@app.route('/rules')
@login_required
@superadmin_required
def rules():
    return render_template('rules.html', user=current_user)


@app.route('/reports')
@login_required
@superadmin_required
def reports():
    return render_template('reports.html', user=current_user)


@app.route('/ratios')
@login_required
@superadmin_required
def ratios():
    return render_template('ratios.html', user=current_user)


@app.route('/analytics')
@login_required
@superadmin_required
def analytics():
    return render_template('analytics.html', user=current_user)


@app.route('/risk')
@login_required
@superadmin_required
def risk():
    return render_template('risk.html', user=current_user)


@app.route('/timeline')
@login_required
@superadmin_required
def timeline():
    return render_template('timeline.html', user=current_user)


@app.route('/decisions')
@login_required
@superadmin_required
def decisions():
    return render_template('decisions.html', user=current_user)


@app.route('/exports')
@login_required
@superadmin_required
def exports():
    return render_template('exports.html', user=current_user)


@app.route('/notifications')
@login_required
@superadmin_required
def notifications():
    return render_template('notifications.html', user=current_user)


# ============================
# ADMIN ROUTES
# ============================

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    total_products = Product.query.count()
    total_clients = Client.query.count()
    total_sales = Sale.query.count()
    total_revenue = db.session.query(func.sum(Sale.final_total)).scalar() or 0
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(10).all()
    for sale in recent_sales:
        sale.product = Product.query.get(sale.product_id)
        sale.client = Client.query.get(sale.client_id) if sale.client_id else None
        sale.final_amount = sale.final_total
    return render_template('admin_dashboard.html',
        user=current_user,
        total_products=total_products,
        total_clients=total_clients,
        total_sales=total_sales,
        total_revenue=total_revenue,
        recent_sales=recent_sales
    )


@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    return render_template('admin_products.html', user=current_user)


@app.route('/admin/clients')
@login_required
@admin_required
def admin_clients():
    return render_template('admin_clients.html', user=current_user)


@app.route('/admin/sales')
@login_required
@admin_required
def admin_sales():
    return render_template('admin_sales.html', user=current_user)


@app.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    return render_template('admin_reports.html', user=current_user)


@app.route('/admin/users')
@login_required
@superadmin_required
def admin_users():
    return render_template('admin_users.html', user=current_user)


# ============================
# ADMIN API ROUTES
# ============================

@app.route('/api/admin/products', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def api_admin_products():
    if request.method == 'GET':
        products = Product.query.all()
        return jsonify([p.to_dict() for p in products])
    elif request.method == 'POST':
        data = request.json
        product = Product(
            name=data.get('name'),
            category=data.get('category'),
            price=float(data.get('price')),
            cost_price=float(data.get('cost_price', 0)),
            stock=int(data.get('stock', 0)),
            min_stock=int(data.get('min_stock', 5)),
            unit=data.get('unit', 'unit'),
            created_by=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'status': 'success', 'id': product.id})
    elif request.method == 'PUT':
        data = request.json
        product = Product.query.get_or_404(data.get('id'))
        if 'name' in data: product.name = data['name']
        if 'category' in data: product.category = data['category']
        if 'price' in data: product.price = float(data['price'])
        if 'cost_price' in data: product.cost_price = float(data['cost_price'])
        if 'stock' in data: product.stock = int(data['stock'])
        if 'min_stock' in data: product.min_stock = int(data['min_stock'])
        if 'unit' in data: product.unit = data['unit']
        db.session.commit()
        return jsonify({'status': 'success'})
    elif request.method == 'DELETE':
        data = request.json
        product = Product.query.get_or_404(data.get('id'))
        Sale.query.filter_by(product_id=product.id).delete()
        db.session.commit()
        db.session.delete(product)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/admin/clients', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def api_admin_clients():
    if request.method == 'GET':
        clients = Client.query.all()
        return jsonify([c.to_dict() for c in clients])
    elif request.method == 'POST':
        data = request.json
        client = Client(
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email'),
            location=data.get('location'),
            notes=data.get('notes'),
            created_by=current_user.id
        )
        db.session.add(client)
        db.session.commit()
        return jsonify({'status': 'success', 'id': client.id})
    elif request.method == 'PUT':
        data = request.json
        client = Client.query.get_or_404(data.get('id'))
        if 'name' in data: client.name = data['name']
        if 'phone' in data: client.phone = data['phone']
        if 'email' in data: client.email = data['email']
        if 'location' in data: client.location = data['location']
        if 'notes' in data: client.notes = data['notes']
        if 'is_trusted' in data: client.is_trusted = data['is_trusted']
        db.session.commit()
        return jsonify({'status': 'success'})
    elif request.method == 'DELETE':
        data = request.json
        client = Client.query.get_or_404(data.get('id'))
        Sale.query.filter_by(client_id=client.id).update({'client_id': None})
        db.session.commit()
        db.session.delete(client)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/admin/sales', methods=['GET', 'POST', 'DELETE'])
@login_required
@admin_required
def api_admin_sales():
    if request.method == 'GET':
        sales = Sale.query.order_by(Sale.sale_date.desc()).all()
        return jsonify([s.to_dict() for s in sales])
    elif request.method == 'POST':
        data = request.json
        product = Product.query.get_or_404(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        unit_price = float(data.get('unit_price', product.price))
        total = quantity * unit_price
        discount = float(data.get('discount', 0))
        final_total = total - discount
        cost_total = quantity * product.cost_price
        profit = final_total - cost_total
        if product.stock < quantity:
            return jsonify({'error': 'Insufficient stock'}), 400
        product.stock -= quantity
        sale = Sale(
            product_id=product.id,
            client_id=data.get('client_id') if data.get('client_id') else None,
            quantity=quantity,
            unit_price=unit_price,
            total=total,
            discount=discount,
            final_total=final_total,
            profit=profit,
            created_by=current_user.id,
            notes=data.get('notes')
        )
        db.session.add(sale)
        db.session.commit()
        if data.get('client_id'):
            client = Client.query.get(data.get('client_id'))
            if client:
                client.total_purchases += final_total
                client.purchase_count += 1
                client.last_purchase = datetime.utcnow()
                client.trust_score = min(client.trust_score + 1, 100)
                if client.trust_score >= 80 and not client.is_trusted:
                    client.is_trusted = True
                db.session.commit()
        superadmin = User.query.filter_by(role='superadmin').first()
        if superadmin:
            transaction = Transaction(
                user_id=superadmin.id,
                type='income',
                category='Sales',
                amount=final_total,
                description=f"Sale: {product.name} x{quantity} (by {current_user.username})",
                date=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
        return jsonify({'status': 'success', 'id': sale.id, 'profit': profit})
    elif request.method == 'DELETE':
        data = request.json
        sale = Sale.query.get_or_404(data.get('id'))
        product = Product.query.get(sale.product_id)
        if product:
            product.stock += sale.quantity
            db.session.commit()
        db.session.delete(sale)
        db.session.commit()
        return jsonify({'status': 'success'})


@app.route('/api/admin/sales/stats')
@login_required
@admin_required
def admin_sales_stats():
    total_revenue = db.session.query(func.sum(Sale.final_total)).scalar() or 0
    total_profit = db.session.query(func.sum(Sale.profit)).scalar() or 0
    total_sales = Sale.query.count()
    total_products = Product.query.count()
    total_clients = Client.query.count()
    return jsonify({
        'total_revenue': total_revenue,
        'total_profit': total_profit,
        'total_sales': total_sales,
        'total_products': total_products,
        'total_clients': total_clients
    })


@app.route('/api/admin/users')
@login_required
@superadmin_required
def admin_get_users():
    users = User.query.all()
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email or '',
            'currency': user.currency,
            'role': user.role,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else None
        })
    return jsonify(result)


@app.route('/api/admin/users', methods=['POST'])
@login_required
@superadmin_required
def admin_create_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    currency = data.get('currency', 'BIF')
    role = data.get('role', 'admin')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if role not in ['admin', 'user']:
        return jsonify({'error': 'Invalid role'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    user = User(username=username, email=email, currency=currency, role=role, created_by=current_user.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'status': 'success', 'id': user.id, 'username': user.username, 'role': user.role})


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@superadmin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'superadmin':
        return jsonify({'error': 'Cannot delete SuperAdmin'}), 403
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 403
    Transaction.query.filter_by(user_id=user_id).delete()
    Investment.query.filter_by(user_id=user_id).delete()
    Livestock.query.filter_by(user_id=user_id).delete()
    Asset.query.filter_by(user_id=user_id).delete()
    Goal.query.filter_by(user_id=user_id).delete()
    Budget.query.filter_by(user_id=user_id).delete()
    Liability.query.filter_by(user_id=user_id).delete()
    FinancialRule.query.filter_by(user_id=user_id).delete()
    Notification.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'User {user.username} deleted'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

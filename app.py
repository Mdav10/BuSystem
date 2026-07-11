import os
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func, extract, text

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
CORS(app)

# ============================
# DATABASE MODELS (Simplified)
# ============================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    currency = db.Column(db.String(10), default='FCFA')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.String(20))
    category = db.Column(db.String(50))
    amount = db.Column(db.Float)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Investment(db.Model):
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    investment_id = db.Column(db.String(50), unique=True)
    type = db.Column(db.String(50))
    capital = db.Column(db.Float)
    status = db.Column(db.String(20), default='Running')
    profit = db.Column(db.Float, default=0)
    roi_actual = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)

class Livestock(db.Model):
    __tablename__ = 'livestock'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    tag = db.Column(db.String(50), unique=True)
    type = db.Column(db.String(50))
    purchase_price = db.Column(db.Float)
    status = db.Column(db.String(20), default='Active')

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    purchase_price = db.Column(db.Float)
    current_value = db.Column(db.Float)

class Goal(db.Model):
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(100))
    target_amount = db.Column(db.Float)
    current_amount = db.Column(db.Float, default=0)
    progress = db.Column(db.Float, default=0)

class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    category = db.Column(db.String(50))
    expected_amount = db.Column(db.Float)
    actual_amount = db.Column(db.Float, default=0)
    month = db.Column(db.Integer)
    year = db.Column(db.Integer)

class FinancialRule(db.Model):
    __tablename__ = 'financial_rules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    condition_value = db.Column(db.Float)
    condition_operator = db.Column(db.String(10))
    action_message = db.Column(db.Text)

# ============================
# CREATE TABLES
# ============================

with app.app_context():
    db.create_all()
    
    # Create default user
    if not User.query.filter_by(username='MCM').first():
        user = User(username='MCM', currency='FCFA')
        user.set_password('0880Mcm+_+')
        db.session.add(user)
        db.session.commit()
        print("✅ User MCM created")
    
    # Create default rules
    if FinancialRule.query.count() == 0:
        rules = [
            FinancialRule(
                user_id=1,
                name='Investment Diversification',
                category='investment',
                condition_value=40,
                condition_operator='>',
                action_message='Do not invest more than 40% in one type'
            )
        ]
        for rule in rules:
            db.session.add(rule)
        db.session.commit()
        print("✅ Default rules created")

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
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ============================
# DASHBOARD
# ============================

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id
    today = datetime.now()
    
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    
    total_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0
    
    current_cash = total_income - total_expenses
    total_assets = db.session.query(func.sum(Asset.current_value)).filter(Asset.user_id == user_id).scalar() or 0
    total_investments = db.session.query(func.sum(Investment.capital)).filter(
        Investment.user_id == user_id, Investment.status == 'Running'
    ).scalar() or 0
    net_worth = current_cash + total_assets + total_investments
    
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income',
        extract('month', Transaction.date) == today.month
    ).scalar() or 0
    
    monthly_expenses = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        extract('month', Transaction.date) == today.month
    ).scalar() or 0
    
    active_livestock = Livestock.query.filter_by(user_id=user_id, status='Active').count()
    
    return render_template('dashboard.html',
        current_cash=current_cash,
        total_assets=total_assets,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        total_investments=total_investments,
        active_livestock=active_livestock,
        user=current_user
    )

# ============================
# API ENDPOINTS
# ============================

@app.route('/api/transactions', methods=['GET', 'POST'])
@login_required
def api_transactions():
    if request.method == 'GET':
        transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(100).all()
        return jsonify([{
            'id': t.id,
            'type': t.type,
            'category': t.category,
            'amount': t.amount,
            'description': t.description,
            'date': t.date.strftime('%Y-%m-%d')
        } for t in transactions])
    
    elif request.method == 'POST':
        data = request.json
        transaction = Transaction(
            user_id=current_user.id,
            type=data.get('type'),
            category=data.get('category'),
            amount=float(data.get('amount')),
            description=data.get('description')
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'status': 'success', 'id': transaction.id})

@app.route('/api/investments', methods=['GET', 'POST'])
@login_required
def api_investments():
    if request.method == 'GET':
        investments = Investment.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'investment_id': i.investment_id,
            'type': i.type,
            'capital': i.capital,
            'status': i.status,
            'profit': i.profit,
            'roi_actual': i.roi_actual
        } for i in investments])
    
    elif request.method == 'POST':
        data = request.json
        import random
        investment_id = f"{data.get('type', 'INV')[:3].upper()}{random.randint(100, 999)}"
        investment = Investment(
            user_id=current_user.id,
            investment_id=investment_id,
            type=data.get('type'),
            capital=float(data.get('capital'))
        )
        db.session.add(investment)
        db.session.commit()
        return jsonify({'status': 'success', 'investment_id': investment_id})

@app.route('/api/livestock', methods=['GET', 'POST'])
@login_required
def api_livestock():
    if request.method == 'GET':
        livestock = Livestock.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': l.id,
            'tag': l.tag,
            'type': l.type,
            'purchase_price': l.purchase_price,
            'status': l.status
        } for l in livestock])
    
    elif request.method == 'POST':
        data = request.json
        animal = Livestock(
            user_id=current_user.id,
            tag=data.get('tag'),
            type=data.get('type'),
            purchase_price=float(data.get('purchase_price'))
        )
        db.session.add(animal)
        db.session.commit()
        return jsonify({'status': 'success', 'id': animal.id})

@app.route('/api/assets', methods=['GET', 'POST'])
@login_required
def api_assets():
    if request.method == 'GET':
        assets = Asset.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': a.id,
            'name': a.name,
            'category': a.category,
            'purchase_price': a.purchase_price,
            'current_value': a.current_value
        } for a in assets])
    
    elif request.method == 'POST':
        data = request.json
        asset = Asset(
            user_id=current_user.id,
            name=data.get('name'),
            category=data.get('category'),
            purchase_price=float(data.get('purchase_price')),
            current_value=float(data.get('purchase_price'))
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify({'status': 'success', 'id': asset.id})

@app.route('/api/goals', methods=['GET', 'POST'])
@login_required
def api_goals():
    if request.method == 'GET':
        goals = Goal.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': g.id,
            'name': g.name,
            'target_amount': g.target_amount,
            'current_amount': g.current_amount,
            'progress': g.progress
        } for g in goals])
    
    elif request.method == 'POST':
        data = request.json
        goal = Goal(
            user_id=current_user.id,
            name=data.get('name'),
            target_amount=float(data.get('target_amount'))
        )
        db.session.add(goal)
        db.session.commit()
        return jsonify({'status': 'success', 'id': goal.id})

@app.route('/api/budget', methods=['GET', 'POST'])
@login_required
def api_budget():
    today = datetime.now()
    if request.method == 'GET':
        budgets = Budget.query.filter_by(
            user_id=current_user.id,
            month=today.month,
            year=today.year
        ).all()
        return jsonify([{
            'id': b.id,
            'category': b.category,
            'expected_amount': b.expected_amount,
            'actual_amount': b.actual_amount
        } for b in budgets])
    
    elif request.method == 'POST':
        data = request.json
        budget = Budget(
            user_id=current_user.id,
            category=data.get('category'),
            expected_amount=float(data.get('expected_amount')),
            month=today.month,
            year=today.year
        )
        db.session.add(budget)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/reports/export/<format>')
@login_required
def export_report(format):
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    
    if format == 'pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, alignment=1)
        story.append(Paragraph("Transaction Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        data = [['Date', 'Type', 'Category', 'Amount', 'Description']]
        for t in transactions[:100]:
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
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"report_{datetime.now().strftime('%Y%m%d')}.pdf")
    
    elif format == 'excel':
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        headers = ['Date', 'Type', 'Category', 'Amount', 'Description']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        for row, t in enumerate(transactions, 1):
            worksheet.write(row, 0, t.date.strftime('%Y-%m-%d'))
            worksheet.write(row, 1, t.type)
            worksheet.write(row, 2, t.category)
            worksheet.write(row, 3, t.amount)
            worksheet.write(row, 4, t.description or '')
        
        workbook.close()
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"report_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    return jsonify({'error': 'Invalid format'}), 400

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

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html', user=current_user)

@app.route('/decisions')
@login_required
def decisions():
    return render_template('decisions.html', user=current_user)

@app.route('/risk')
@login_required
def risk():
    return render_template('risk.html', user=current_user)

@app.route('/timeline')
@login_required
def timeline():
    return render_template('timeline.html', user=current_user)

@app.route('/exports')
@login_required
def exports():
    return render_template('exports.html', user=current_user)

@app.route('/rules')
@login_required
def rules():
    return render_template('rules.html', user=current_user)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

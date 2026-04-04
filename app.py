import os
import sqlite3
import json
import requests
from flask import Flask, render_template, request, jsonify, g
from datetime import datetime, date

app = Flask(__name__)

DATABASE = os.path.join(os.path.dirname(__file__), 'finance.db')
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('expense', 'income')),
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        db.commit()


def get_balance():
    db = get_db()
    income = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='income'").fetchone()[0]
    expense = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='expense'").fetchone()[0]
    return income - expense, income, expense


@app.route('/')
def dashboard():
    db = get_db()
    balance, total_income, total_expense = get_balance()
    transactions = db.execute(
        "SELECT * FROM transactions ORDER BY date DESC, created_at DESC LIMIT 10"
    ).fetchall()
    category_expenses = db.execute(
        "SELECT category, SUM(amount) as total FROM transactions WHERE type='expense' GROUP BY category ORDER BY total DESC"
    ).fetchall()
    return render_template('dashboard.html',
                           balance=balance,
                           total_income=total_income,
                           total_expense=total_expense,
                           transactions=transactions,
                           category_expenses=category_expenses)


@app.route('/add')
def add_transaction():
    return render_template('add.html')


@app.route('/history')
def history():
    db = get_db()
    type_filter = request.args.get('type', '')
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '')
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    if type_filter:
        query += " AND type=?"
        params.append(type_filter)
    if category_filter:
        query += " AND category=?"
        params.append(category_filter)
    if search:
        query += " AND (description LIKE ? OR category LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    query += " ORDER BY date DESC, created_at DESC"
    transactions = db.execute(query, params).fetchall()
    balance, total_income, total_expense = get_balance()
    return render_template('history.html',
                           transactions=transactions,
                           balance=balance,
                           total_income=total_income,
                           total_expense=total_expense)


@app.route('/api/transactions', methods=['POST'])
def add_transaction_api():
    data = request.json
    db = get_db()
    amount = float(data.get('amount', 0))
    type_ = data.get('type', 'expense')
    category = data.get('category', 'أخرى')
    description = data.get('description', '')
    trans_date = data.get('date', date.today().isoformat())
    if amount <= 0:
        return jsonify({'success': False, 'error': 'المبلغ يجب أن يكون أكبر من صفر'}), 400
    db.execute(
        "INSERT INTO transactions (date, type, category, description, amount) VALUES (?, ?, ?, ?, ?)",
        (trans_date, type_, category, description, amount)
    )
    db.commit()
    balance, _, _ = get_balance()
    return jsonify({'success': True, 'balance': balance})


@app.route('/api/transactions/<int:trans_id>', methods=['DELETE'])
def delete_transaction(trans_id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id=?", (trans_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/analyze-voice', methods=['POST'])
def analyze_voice():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'success': False, 'error': 'النص فارغ'}), 400
    prompt = f"""أنت مساعد مالي. حلل هذه الجملة: "{text}"
أرجع JSON فقط:
{{"amount": <رقم>, "type": "<expense أو income>", "category": "<فئة>", "description": "<وصف>"}}
فئات المصروفات: مأكولات، مواصلات، ترفيه، ملابس، صحة، تعليم، فواتير، أخرى
فئات الدخل: راتب، هدية، مكافأة، بيع، أخرى"""
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "user", "content": prompt}], "max_tokens": 200},
            timeout=15
        )
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            content = content.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(content)
            return jsonify({'success': True, 'data': parsed})
        else:
            return jsonify({'success': False, 'error': 'خطأ في الذكاء الاصطناعي'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'خطأ في الخادم'}), 500


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

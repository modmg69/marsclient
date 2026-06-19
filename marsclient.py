from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import sqlite3
import os
import re
import time
import threading
import secrets
import requests
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'marsclient_secret_key_v9')
DB_FILE = 'marsclient_downloads.db'
BASE_COSMETIC_FOLDER = 'static/cosmetics'
TEAM_FOLDER = 'static/team'
ALLOWED_EXTENSIONS = {'png', 'gif', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'}

# ========== ایجاد فولدر تیم ==========
def create_team_folder():
    os.makedirs(TEAM_FOLDER, exist_ok=True)
    team_members = [
        {'name': 'پارسا', 'role': 'بنیان‌گذار و توسعه‌دهنده ارشد', 'username': 'modmg69', 'badge': 'بنیان‌گذار', 'icon': '🚀', 'file': 'پارسا_بنیان_گذار.png', 'status': 'online'},
        {'name': 'حسین', 'role': 'مدیریت تیم', 'username': 'seet', 'badge': 'مدیر تیم', 'icon': '📊', 'file': 'حسین_مدیر_تیم.png', 'status': 'online'},
        {'name': 'محمد رضا', 'role': 'پشتیبانی', 'username': 'MohammadReza23', 'badge': 'پشتیبانی', 'icon': '🛡️', 'file': 'محمد_رضا_پشتیبانی.png', 'status': 'online'},
        {'name': 'محمد صادق', 'role': 'پشتیبانی', 'username': 'MohammadSadiq', 'badge': 'پشتیبانی', 'icon': '🎧', 'file': 'محمد_صادق_پشتیبانی.png', 'status': 'online'},
        {'name': 'پارسا', 'role': 'طراح لانچر', 'username': 'Parsa__6780393', 'badge': 'طراح لانچر', 'icon': '🎨', 'file': 'پارسا_طراح_لانچر.png', 'status': 'online'},
        {'name': 'سامان', 'role': 'دیزاین کلاینت', 'username': 'saman_design', 'badge': 'دیزاینر', 'icon': '✨', 'file': 'سامان_دیزاین_کلاینت.png', 'status': 'online'}
    ]
    info_path = os.path.join(TEAM_FOLDER, 'team_info.json')
    if not os.path.exists(info_path):
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(team_members, f, ensure_ascii=False, indent=2)
    for member in team_members:
        file_path = os.path.join(TEAM_FOLDER, member['file'])
        if not os.path.exists(file_path):
            with open(file_path, 'wb') as f:
                f.write(b'')
    return team_members

TEAM_MEMBERS = create_team_folder()

# ---------- Online Players ----------
active_sessions = {}
sessions_lock = threading.Lock()
SESSION_TIMEOUT = 60
CLEANUP_INTERVAL = 30

def generate_session_id():
    return secrets.token_hex(16)

def cleanup_inactive_sessions():
    now = time.time()
    with sessions_lock:
        to_remove = [sid for sid, last_seen in active_sessions.items() if now - last_seen > SESSION_TIMEOUT]
        for sid in to_remove:
            del active_sessions[sid]
    threading.Timer(CLEANUP_INTERVAL, cleanup_inactive_sessions).start()

cleanup_inactive_sessions()

@app.route('/api/online_count')
def online_count():
    with sessions_lock:
        return jsonify({'count': len(active_sessions)})

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        with sessions_lock:
            if session_id in active_sessions:
                active_sessions[session_id] = time.time()
            else:
                active_sessions[session_id] = time.time()
        return jsonify({'online_count': len(active_sessions)})
    return jsonify({'error': 'no session'}), 400

@app.route('/api/leave', methods=['POST'])
def leave():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        with sessions_lock:
            active_sessions.pop(session_id, None)
    return jsonify({'success': True})

# ---------- Zarinpal ----------
MERCHANT_ID = "11111111-1111-1111-1111-111111111111"
ZARINPAL_REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_GATEWAY_URL = "https://sandbox.zarinpal.com/pg/StartPay/"
CALLBACK_URL = "http://localhost:8000/api/payment/verify_custom"

CATEGORIES = {
    'pets': 'حیوانات خانگی',
    'glasses': 'عینک',
    'hats': 'کلاه',
    'masks': 'ماسک',
    'wings': 'بال',
    'capes': 'شنل',
    'bag': 'کیف',
    'necklace': 'گردنبند'
}

BASE_PRICES = {
    'pets': 267000,
    'glasses': 130000,
    'hats': 180000,
    'masks': 200000,
    'wings': 200000,
    'capes': 200000,
    'bag': 260000,
    'necklace': 250000
}

def get_item_price(category_key, item_name):
    if category_key == 'hats' and ('luxury' in item_name.lower() or 'special' in item_name.lower()):
        return 200000
    if category_key == 'capes' and ('legendary' in item_name.lower() or 'epic' in item_name.lower()):
        return 300000
    return BASE_PRICES.get(category_key, 30000)

os.makedirs(BASE_COSMETIC_FOLDER, exist_ok=True)
for cat in CATEGORIES.keys():
    os.makedirs(os.path.join(BASE_COSMETIC_FOLDER, cat), exist_ok=True)
app.config['UPLOAD_FOLDER'] = BASE_COSMETIC_FOLDER

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'unauthorized', 'message': 'لطفاً ابتدا وارد شوید'}), 401
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, items TEXT NOT NULL, total_price INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, minecraft_username TEXT UNIQUE NOT NULL, email TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS coin_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount INTEGER NOT NULL, authority TEXT, status TEXT DEFAULT "pending", created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS support_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT, question TEXT NOT NULL, answer TEXT, status TEXT DEFAULT "pending", created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

def is_valid_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

# Shopping Cart
def get_cart():
    return session.get('cart', {})
def save_cart(cart):
    session['cart'] = cart
    session.modified = True
def get_cart_total(cart):
    return sum(item['price'] * item['quantity'] for item in cart.values())

@app.route('/api/cart')
@login_required
def api_cart():
    cart = get_cart()
    items_list = list(cart.values())
    total = get_cart_total(cart)
    return jsonify({'items': items_list, 'total': total, 'item_count': sum(i['quantity'] for i in items_list)})

@app.route('/api/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    data = request.get_json()
    if not all(k in data for k in ['category_key', 'name', 'image', 'price']):
        return jsonify({'success': False, 'error': 'Missing fields'}), 400
    key = f"{data['category_key']}:{data['name']}"
    cart = get_cart()
    if key in cart:
        cart[key]['quantity'] += 1
    else:
        cart[key] = {'id': key, 'category': data['category_key'], 'name': data['name'], 'image': data['image'], 'price': data['price'], 'quantity': 1}
    save_cart(cart)
    return jsonify({'success': True})

@app.route('/api/cart/remove', methods=['POST'])
@login_required
def remove_from_cart():
    data = request.get_json()
    item_id = data.get('item_id')
    cart = get_cart()
    if item_id in cart:
        del cart[item_id]
        save_cart(cart)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.route('/api/cart/update', methods=['POST'])
@login_required
def update_cart_quantity():
    data = request.get_json()
    item_id, qty = data.get('item_id'), data.get('quantity')
    if not item_id or not isinstance(qty, int) or qty < 1:
        return jsonify({'success': False, 'error': 'Invalid quantity'}), 400
    cart = get_cart()
    if item_id in cart:
        cart[item_id]['quantity'] = qty
        save_cart(cart)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.route('/api/payment/initiate_custom', methods=['POST'])
@login_required
def initiate_custom_payment():
    data = request.get_json()
    amount_toman = data.get('amount')
    if not isinstance(amount_toman, int) or amount_toman <= 0 or amount_toman >= 1500000:
        return jsonify({'success': False, 'error': 'مبلغ باید کمتر از ۱,۵۰۰,۰۰۰ تومان و بیشتر از صفر باشد'}), 400
    amount_rial = amount_toman * 10
    payload = {
        "merchant_id": MERCHANT_ID,
        "amount": amount_rial,
        "description": f"شارژ کیف پول - {session.get('username')}",
        "callback_url": CALLBACK_URL,
        "metadata": {"email": session.get('username', '')}
    }
    try:
        resp = requests.post(ZARINPAL_REQUEST_URL, json=payload, timeout=10)
        result = resp.json()
        if result.get("data") and result["data"].get("authority"):
            auth = result["data"]["authority"]
            session['pending_coin_amount'] = amount_toman
            session['pending_coin_authority'] = auth
            conn = sqlite3.connect(DB_FILE)
            conn.execute('INSERT INTO coin_transactions (user_id, amount, authority) VALUES (?, ?, ?)', (session['user_id'], amount_toman, auth))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'gateway_url': ZARINPAL_GATEWAY_URL + auth})
        return jsonify({'success': False, 'error': result.get("errors", {}).get("message", "خطا")}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payment/verify_custom', methods=['GET'])
def verify_custom_payment():
    auth = request.args.get('Authority')
    status = request.args.get('Status')
    if not auth or status != 'OK':
        return "پرداخت لغو یا نامعتبر", 400
    amount_toman = session.pop('pending_coin_amount', None)
    if not amount_toman:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute('SELECT amount FROM coin_transactions WHERE authority = ? AND status = "pending"', (auth,)).fetchone()
        amount_toman = row[0] if row else None
        conn.close()
        if not amount_toman:
            return "تراکنش یافت نشد", 400
    amount_rial = amount_toman * 10
    verify_payload = {"merchant_id": MERCHANT_ID, "authority": auth, "amount": amount_rial}
    try:
        resp = requests.post(ZARINPAL_VERIFY_URL, json=verify_payload, timeout=10)
        result = resp.json()
        if result.get("data") and result["data"].get("code") == 100:
            conn = sqlite3.connect(DB_FILE)
            conn.execute('UPDATE coin_transactions SET status = "success" WHERE authority = ?', (auth,))
            conn.commit()
            conn.close()
            return "پرداخت موفق. مبلغ به کیف پول اضافه شد."
        else:
            return f"پرداخت ناموفق: {result.get('errors',{}).get('message','')}", 400
    except Exception as e:
        return f"خطا: {str(e)}", 500

@app.route('/api/cosmetics')
def get_cosmetics():
    result = {}
    for cat_key, cat_name in CATEGORIES.items():
        cat_path = os.path.join(BASE_COSMETIC_FOLDER, cat_key)
        files = []
        if os.path.exists(cat_path):
            for filename in os.listdir(cat_path):
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                if ext in ALLOWED_EXTENSIONS:
                    name = filename.rsplit('.', 1)[0]
                    price = get_item_price(cat_key, name)
                    img = f'/static/cosmetics/{cat_key}/{filename}'
                    files.append({'name': name, 'image': img, 'category_key': cat_key, 'category_name': cat_name, 'price': price})
        result[cat_key] = files
    return jsonify(result)

@app.route('/api/team_members')
def get_team_members():
    info_path = os.path.join(TEAM_FOLDER, 'team_info.json')
    if os.path.exists(info_path):
        with open(info_path, 'r', encoding='utf-8') as f:
            members = json.load(f)
    else:
        members = TEAM_MEMBERS
    for member in members:
        file_path = os.path.join(TEAM_FOLDER, member['file'])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            member['avatar'] = f'/static/team/{member["file"]}'
        else:
            member['avatar'] = f'https://ui-avatars.com/api/?name={member["name"]}&background=f97316&color=fff&size=120'
    return jsonify(members)

# ========== API ثبت سوال پشتیبانی ==========
@app.route('/api/support/question', methods=['POST'])
def submit_support_question():
    data = request.get_json()
    question = data.get('question', '').strip()
    user_name = data.get('user_name', 'کاربر مهمان').strip()
    
    if not question or len(question) < 5:
        return jsonify({'success': False, 'message': 'سوال باید حداقل ۵ کاراکتر باشد'}), 400
    
    conn = sqlite3.connect(DB_FILE)
    conn.execute('INSERT INTO support_questions (user_name, question) VALUES (?, ?)', (user_name, question))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'سوال شما ثبت شد. به زودی پاسخ داده می‌شود.'})

# ========== پنل مدیریت آپلود عکس ==========
@app.route('/admin/team', methods=['GET', 'POST'])
def admin_team():
    if request.method == 'POST':
        if request.form.get('password') != 'admin123':
            return "رمز عبور اشتباه است", 403
        member_name = request.form.get('member_name')
        file = request.files.get('file')
        
        if not member_name or not file or file.filename == '':
            return "لطفاً نام عضو و فایل را انتخاب کنید", 400
        
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
        if ext not in ALLOWED_EXTENSIONS:
            return "فرمت فایل مجاز نیست. فقط PNG, JPG, GIF, WEBP, BMP, TIFF", 400
        
        info_path = os.path.join(TEAM_FOLDER, 'team_info.json')
        with open(info_path, 'r', encoding='utf-8') as f:
            members = json.load(f)
        
        target_member = None
        for m in members:
            if m['name'] == member_name:
                target_member = m
                break
        
        if not target_member:
            return f"عضو با نام '{member_name}' یافت نشد", 400
        
        try:
            img = Image.open(file.stream)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img_io = io.BytesIO()
            img.save(img_io, format='PNG', optimize=True, quality=95)
            img_io.seek(0)
            
            filename = target_member['file']
            file_path = os.path.join(TEAM_FOLDER, filename)
            with open(file_path, 'wb') as f:
                f.write(img_io.getvalue())
            
            return redirect(url_for('admin_team'))
            
        except Exception as e:
            return f"خطا در پردازش عکس: {str(e)}", 400
    
    info_path = os.path.join(TEAM_FOLDER, 'team_info.json')
    with open(info_path, 'r', encoding='utf-8') as f:
        members = json.load(f)
    
    html = '''<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مدیریت عکس تیم</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { 
            font-family: 'Vazirmatn', system-ui, sans-serif;
            background: #0a0a0f;
            color: #fff;
            padding: 30px;
            direction: rtl;
            min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h2 { color: #f97316; margin-bottom: 20px; font-size: 2rem; }
        .subtitle { color: #8899aa; margin-bottom: 30px; }
        
        .card {
            background: #1a1a2e;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid #2a2a3e;
            transition: all 0.3s;
        }
        .card:hover { border-color: #f97316; }
        
        .member-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .member-item {
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 15px;
            background: #12121f;
            border-radius: 16px;
            border: 1px solid #2a2a3e;
            transition: all 0.3s;
        }
        .member-item:hover { border-color: #f97316; }
        
        .member-avatar {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
            background: #f97316;
            border: 3px solid #f97316;
            transition: all 0.3s;
        }
        .member-avatar:hover { transform: scale(1.05); }
        
        .member-info { flex: 1; }
        .member-name { font-weight: bold; font-size: 1.1rem; }
        .member-role { color: #8899aa; font-size: 0.85rem; }
        .member-file { font-size: 0.7rem; color: #556; margin-top: 4px; }
        .member-status { 
            font-size: 0.7rem;
            padding: 3px 10px;
            border-radius: 20px;
            display: inline-block;
        }
        .status-exists { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .status-missing { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        
        .upload-area {
            border: 2px dashed #2a2a3e;
            border-radius: 16px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: #f97316;
            background: rgba(249, 115, 22, 0.05);
        }
        .upload-area .icon { font-size: 3rem; margin-bottom: 10px; }
        .upload-area .text { color: #8899aa; }
        .upload-area .highlight { color: #f97316; font-weight: bold; }
        
        .upload-form {
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin-top: 20px;
        }
        .upload-form select,
        .upload-form input[type="password"] {
            padding: 12px;
            border-radius: 12px;
            border: 1px solid #2a2a3e;
            background: #12121f;
            color: #fff;
            font-size: 1rem;
            transition: all 0.3s;
        }
        .upload-form select:focus,
        .upload-form input:focus {
            outline: none;
            border-color: #f97316;
        }
        .upload-form select option { background: #1a1a2e; }
        
        .upload-btn {
            background: linear-gradient(135deg, #f97316, #ea580c);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(249, 115, 22, 0.3);
        }
        
        .preview-area {
            display: none;
            margin-top: 15px;
            padding: 20px;
            background: #12121f;
            border-radius: 16px;
            text-align: center;
        }
        .preview-area img {
            max-width: 200px;
            max-height: 200px;
            border-radius: 50%;
            border: 3px solid #f97316;
        }
        .preview-area .file-name {
            color: #8899aa;
            margin-top: 10px;
        }
        
        .back-link {
            color: #f97316;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
            transition: all 0.3s;
        }
        .back-link:hover { color: #ea580c; text-decoration: underline; }
        
        #previewImg {
            max-width: 200px;
            max-height: 200px;
            object-fit: contain;
            border-radius: 50%;
        }
        
        @media (max-width: 768px) {
            .member-grid { grid-template-columns: 1fr; }
            .container { padding: 0 10px; }
        }
    </style>
</head>
<body>
<div class="container">
    <h2>📸 مدیریت عکس تیم توسعه‌دهندگان</h2>
    <p class="subtitle">عکس‌ها با سایز اصلی خود ذخیره می‌شوند و کیفیت آن‌ها حفظ می‌گردد</p>
    
    <div class="card">
        <h3 style="margin-bottom:15px;">👥 اعضای تیم</h3>
        <div class="member-grid">
            {% for member in members %}
            <div class="member-item">
                <img class="member-avatar" 
                     src="/static/team/{{ member.file }}?t={{ range(1, 999) | random }}" 
                     alt="{{ member.name }}"
                     onerror="this.src='https://ui-avatars.com/api/?name={{ member.name }}&background=f97316&color=fff&size=120'">
                <div class="member-info">
                    <div class="member-name">{{ member.name }}</div>
                    <div class="member-role">{{ member.role }}</div>
                    <div class="member-file">📁 {{ member.file }}</div>
                    <span class="member-status {% if member.file in files %}status-exists{% else %}status-missing{% endif %}">
                        {% if member.file in files %}✅ عکس موجود{% else %}❌ بدون عکس{% endif %}
                    </span>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <div class="card">
        <h3 style="margin-bottom:15px;">📤 آپلود عکس جدید</h3>
        <form method="post" enctype="multipart/form-data" class="upload-form" id="uploadForm">
            <input type="password" name="password" placeholder="رمز عبور (admin123)" required>
            <select name="member_name" id="memberSelect" required>
                <option value="">انتخاب عضو...</option>
                {% for member in members %}
                <option value="{{ member.name }}">{{ member.name }} - {{ member.role }}</option>
                {% endfor %}
            </select>
            
            <div class="upload-area" id="dropArea">
                <div class="icon">🖼️</div>
                <div class="text">
                    <span class="highlight">فایل را اینجا بکشید و رها کنید</span><br>
                    یا کلیک کنید تا انتخاب کنید<br>
                    <span style="font-size:0.8rem;color:#556;">فرمت‌های مجاز: PNG, JPG, GIF, WEBP, BMP, TIFF</span>
                </div>
                <input type="file" name="file" id="fileInput" accept="image/*" style="display:none;" required>
            </div>
            
            <div class="preview-area" id="previewArea">
                <img id="previewImg" src="" alt="پیش‌نمایش">
                <div class="file-name" id="fileName">فایل انتخاب شد</div>
            </div>
            
            <button type="submit" class="upload-btn">📤 آپلود عکس</button>
        </form>
    </div>
    
    <a href="/" class="back-link">← بازگشت به صفحه اصلی</a>
</div>

<script>
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInput');
const previewArea = document.getElementById('previewArea');
const previewImg = document.getElementById('previewImg');
const fileName = document.getElementById('fileName');

dropArea.addEventListener('click', () => fileInput.click());

dropArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropArea.classList.add('dragover');
});
dropArea.addEventListener('dragleave', () => {
    dropArea.classList.remove('dragover');
});
dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dropArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', function() {
    if (this.files.length) {
        handleFile(this.files[0]);
    }
});

function handleFile(file) {
    const validTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(png|jpg|jpeg|gif|webp|bmp|tiff)$/i)) {
        alert('فرمت فایل مجاز نیست. فقط PNG, JPG, GIF, WEBP, BMP, TIFF');
        fileInput.value = '';
        previewArea.style.display = 'none';
        return;
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        previewImg.src = e.target.result;
        previewArea.style.display = 'block';
        fileName.textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
    };
    reader.readAsDataURL(file);
}

document.getElementById('uploadForm').addEventListener('submit', function(e) {
    const password = document.querySelector('input[name="password"]').value;
    const member = document.getElementById('memberSelect').value;
    const file = fileInput.files[0];
    
    if (!password || password !== 'admin123') {
        e.preventDefault();
        alert('رمز عبور اشتباه است');
        return;
    }
    if (!member) {
        e.preventDefault();
        alert('لطفاً یک عضو را انتخاب کنید');
        return;
    }
    if (!file) {
        e.preventDefault();
        alert('لطفاً یک فایل انتخاب کنید');
        return;
    }
});
</script>
</body>
</html>'''
    files = os.listdir(TEAM_FOLDER) if os.path.exists(TEAM_FOLDER) else []
    return render_template_string(html, members=members, files=files)

# ========== پنل مدیریت پشتیبانی ==========
@app.route('/admin/support', methods=['GET', 'POST'])
def admin_support():
    if request.method == 'POST' and 'password' in request.form:
        if request.form.get('password') == 'parsa1901':
            session['support_admin'] = True
            return redirect(url_for('admin_support'))
        else:
            return "رمز عبور اشتباه است", 403
    
    if not session.get('support_admin'):
        return '''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ورود به پنل پشتیبانی</title>
            <style>
                * { margin:0; padding:0; box-sizing:border-box; }
                body { 
                    font-family: 'Vazirmatn', system-ui, sans-serif;
                    background: #0a0a0f;
                    color: #fff;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .login-box {
                    background: #1a1a2e;
                    padding: 40px;
                    border-radius: 24px;
                    border: 1px solid #2a2a3e;
                    text-align: center;
                    max-width: 400px;
                    width: 90%;
                }
                .login-box h2 { color: #f97316; margin-bottom: 10px; font-size: 1.8rem; }
                .login-box .sub { color: #8899aa; margin-bottom: 25px; font-size: 0.9rem; }
                .login-box form { display: flex; flex-direction: column; gap: 15px; }
                .login-box input {
                    padding: 14px;
                    border-radius: 12px;
                    border: 1px solid #2a2a3e;
                    background: #12121f;
                    color: #fff;
                    font-size: 1rem;
                    transition: all 0.3s;
                }
                .login-box input:focus { outline: none; border-color: #f97316; }
                .login-box button {
                    background: linear-gradient(135deg, #f97316, #ea580c);
                    color: white;
                    border: none;
                    padding: 14px;
                    border-radius: 12px;
                    font-weight: bold;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: all 0.3s;
                }
                .login-box button:hover { transform: scale(1.02); box-shadow: 0 8px 25px rgba(249, 115, 22, 0.3); }
                .login-box .back-link {
                    color: #8899aa;
                    text-decoration: none;
                    font-size: 0.85rem;
                    margin-top: 15px;
                    display: inline-block;
                    transition: all 0.3s;
                }
                .login-box .back-link:hover { color: #f97316; }
            </style>
        </head>
        <body>
        <div class="login-box">
            <h2>🔐 پنل پشتیبانی</h2>
            <p class="sub">برای مدیریت سوالات کاربران، رمز عبور را وارد کنید</p>
            <form method="post">
                <input type="password" name="password" placeholder="رمز عبور را وارد کنید" required>
                <button type="submit">ورود به پنل</button>
            </form>
            <a href="/" class="back-link">← بازگشت به صفحه اصلی</a>
        </div>
        </body>
        </html>
        '''
    
    if request.method == 'POST':
        action = request.form.get('action')
        q_id = request.form.get('q_id')
        
        if action == 'answer':
            answer = request.form.get('answer', '').strip()
            if answer and q_id:
                conn = sqlite3.connect(DB_FILE)
                conn.execute('UPDATE support_questions SET answer = ?, status = "answered" WHERE id = ?', (answer, q_id))
                conn.commit()
                conn.close()
                return redirect(url_for('admin_support'))
        
        elif action == 'delete':
            if q_id:
                conn = sqlite3.connect(DB_FILE)
                conn.execute('DELETE FROM support_questions WHERE id = ?', (q_id,))
                conn.commit()
                conn.close()
                return redirect(url_for('admin_support'))
    
    conn = sqlite3.connect(DB_FILE)
    questions = conn.execute('SELECT * FROM support_questions ORDER BY created_at DESC').fetchall()
    conn.close()
    
    html = '''<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مدیریت پشتیبانی</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { 
            font-family: 'Vazirmatn', system-ui, sans-serif;
            background: #0a0a0f;
            color: #fff;
            padding: 30px;
            direction: rtl;
            min-height: 100vh;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        h2 { color: #f97316; margin-bottom: 10px; font-size: 2rem; }
        .subtitle { color: #8899aa; margin-bottom: 30px; }
        
        .card {
            background: #1a1a2e;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid #2a2a3e;
            transition: all 0.3s;
        }
        .card:hover { border-color: #f97316; }
        
        .question-grid {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .question-item {
            background: #12121f;
            border-radius: 16px;
            padding: 20px;
            border: 1px solid #2a2a3e;
            transition: all 0.3s;
        }
        .question-item:hover { border-color: #f97316; }
        
        .q-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .q-user {
            font-weight: bold;
            font-size: 1.1rem;
            color: #f97316;
        }
        .q-date {
            color: #8899aa;
            font-size: 0.8rem;
        }
        .q-status {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .status-pending { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .status-answered { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        
        .q-text {
            background: #0a0a0f;
            padding: 14px;
            border-radius: 12px;
            margin: 10px 0;
            color: #ddd;
            line-height: 1.7;
        }
        
        .q-answer {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 14px;
            border-radius: 12px;
            margin: 10px 0;
            color: #10b981;
            line-height: 1.7;
        }
        .q-answer-label {
            color: #8899aa;
            font-size: 0.8rem;
            display: block;
            margin-bottom: 5px;
        }
        
        .answer-form {
            display: flex;
            gap: 10px;
            margin-top: 12px;
            flex-wrap: wrap;
        }
        .answer-form input[type="text"] {
            flex: 1;
            padding: 10px;
            border-radius: 12px;
            border: 1px solid #2a2a3e;
            background: #0a0a0f;
            color: #fff;
            font-size: 0.95rem;
            min-width: 200px;
            transition: all 0.3s;
        }
        .answer-form input[type="text"]:focus {
            outline: none;
            border-color: #f97316;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 12px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover { transform: scale(1.02); }
        .btn-answer { background: linear-gradient(135deg, #f97316, #ea580c); color: white; }
        .btn-delete { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .btn-delete:hover { background: rgba(239, 68, 68, 0.4); }
        
        .empty-state {
            text-align: center;
            padding: 50px 20px;
            color: #8899aa;
        }
        .empty-state .icon { font-size: 4rem; margin-bottom: 15px; }
        
        .admin-links {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .admin-links a {
            color: #f97316;
            text-decoration: none;
            transition: all 0.3s;
            padding: 8px 16px;
            background: rgba(249, 115, 22, 0.1);
            border-radius: 10px;
            border: 1px solid rgba(249, 115, 22, 0.2);
        }
        .admin-links a:hover { background: rgba(249, 115, 22, 0.2); }
        
        .back-link {
            color: #f97316;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
            transition: all 0.3s;
        }
        .back-link:hover { color: #ea580c; text-decoration: underline; }
        
        @media (max-width: 768px) {
            .q-header { flex-direction: column; align-items: flex-start; }
            .answer-form { flex-direction: column; }
            .answer-form input[type="text"] { width: 100%; }
        }
    </style>
</head>
<body>
<div class="container">
    <h2>💬 مدیریت پشتیبانی</h2>
    <p class="subtitle">سوالات کاربران را مشاهده و پاسخ دهید</p>
    
    <div class="admin-links">
        <a href="/admin/team">📸 مدیریت تیم</a>
        <a href="/admin/cosmetics">🎨 مدیریت کازمتیک</a>
        <a href="/">🏠 صفحه اصلی</a>
    </div>
    
    <div class="card">
        <h3 style="margin-bottom:15px;">📋 لیست سوالات</h3>
        
        {% if questions %}
        <div class="question-grid">
            {% for q in questions %}
            <div class="question-item">
                <div class="q-header">
                    <div>
                        <span class="q-user">👤 {{ q[1] or 'کاربر مهمان' }}</span>
                        <span class="q-date">📅 {{ q[5] }}</span>
                    </div>
                    <span class="q-status {% if q[4] == 'answered' %}status-answered{% else %}status-pending{% endif %}">
                        {% if q[4] == 'answered' %}✅ پاسخ داده شده{% else %}⏳ در انتظار پاسخ{% endif %}
                    </span>
                </div>
                
                <div class="q-text">
                    <strong>سوال:</strong> {{ q[2] }}
                </div>
                
                {% if q[3] %}
                <div class="q-answer">
                    <span class="q-answer-label">💬 پاسخ:</span>
                    {{ q[3] }}
                </div>
                {% endif %}
                
                <form method="post" class="answer-form">
                    <input type="hidden" name="q_id" value="{{ q[0] }}">
                    <input type="text" name="answer" placeholder="پاسخ خود را بنویسید..." {% if q[3] %}value="{{ q[3] }}"{% endif %}>
                    <button type="submit" name="action" value="answer" class="btn btn-answer">📤 ارسال پاسخ</button>
                    <button type="submit" name="action" value="delete" class="btn btn-delete" onclick="return confirm('آیا مطمئن هستید؟')">🗑️ حذف</button>
                </form>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="icon">📭</div>
            <p>هیچ سوالی ثبت نشده است</p>
            <p style="font-size:0.85rem;margin-top:5px;">کاربران از طریق چت‌بات پشتیبانی سوال می‌پرسند</p>
        </div>
        {% endif %}
    </div>
    
    <a href="/" class="back-link">← بازگشت به صفحه اصلی</a>
</div>
</body>
</html>'''
    
    return render_template_string(html, questions=questions)

@app.route('/login')
def login_page():
    return render_template_string(LOGIN_TEMPLATE, styles=STYLES)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email, username, password, confirm = data.get('email',''), data.get('username',''), data.get('password',''), data.get('confirm_password','')
    if not is_valid_email(email):
        return jsonify({'success': False, 'message': 'ایمیل نامعتبر است'}), 400
    if len(username) < 3:
        return jsonify({'success': False, 'message': 'نام کاربری باید حداقل ۳ کاراکتر باشد'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'رمز عبور باید حداقل ۶ کاراکتر باشد'}), 400
    if password != confirm:
        return jsonify({'success': False, 'message': 'رمز عبور و تکرار آن مطابقت ندارند'}), 400
    conn = sqlite3.connect(DB_FILE)
    if conn.execute('SELECT id FROM users WHERE minecraft_username = ?', (username,)).fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'این نام کاربری قبلاً ثبت شده است'}), 400
    if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'این ایمیل قبلاً ثبت شده است'}), 400
    hashed = generate_password_hash(password)
    try:
        cur = conn.execute('INSERT INTO users (minecraft_username, email, password_hash) VALUES (?, ?, ?)', (username, email, hashed))
        conn.commit()
        user_id = cur.lastrowid
        session['user_id'] = user_id
        session['username'] = username
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'خطا در ثبت نام: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username, password = data.get('username',''), data.get('password','')
    conn = sqlite3.connect(DB_FILE)
    user = conn.execute('SELECT id, minecraft_username, password_hash FROM users WHERE minecraft_username = ?', (username,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user[2], password):
        return jsonify({'success': False, 'message': 'نام کاربری یا رمز عبور اشتباه است'}), 401
    session['user_id'] = user[0]
    session['username'] = user[1]
    return jsonify({'success': True})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/me')
def me():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session.get('username')})
    return jsonify({'logged_in': False})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/cosmetics', methods=['GET', 'POST'])
def admin_cosmetics():
    if request.method == 'POST':
        if request.form.get('password') != 'admin123':
            return "رمز عبور اشتباه است", 403
        cat = request.form.get('category')
        if cat not in CATEGORIES:
            return "دسته‌بندی نامعتبر است", 400
        file = request.files.get('file')
        if not file or file.filename == '':
            return "لطفاً فایل را انتخاب کنید", 400
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(BASE_COSMETIC_FOLDER, cat, filename))
            return redirect(url_for('admin_cosmetics'))
        return "فقط فایل‌های PNG و GIF مجاز هستند", 400
    cosmetics_dict = {cat: os.listdir(os.path.join(BASE_COSMETIC_FOLDER, cat)) if os.path.exists(os.path.join(BASE_COSMETIC_FOLDER, cat)) else [] for cat in CATEGORIES}
    html = '''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>مدیریت کازمتیک</title></head><body style="background:#111;color:#fff;padding:20px;font-family:Vazirmatn;"><h2>آپلود کازمتیک (PNG یا GIF)</h2><form method="post" enctype="multipart/form-data"><input type="password" name="password" placeholder="رمز عبور" required><br><br><select name="category">{% for key,name in categories.items() %}<option value="{{ key }}">{{ name }}</option>{% endfor %}</select><br><br><input type="file" name="file" accept="image/png,image/gif" required><br><br><button type="submit">آپلود</button></form><h3>کازمتیک‌های موجود</h3>{% for key,name in categories.items() %}<h4>{{ name }}</h4><ul>{% for file in cosmetics[key] %}<li>{{ file }} - <a href="/static/cosmetics/{{ key }}/{{ file }}" target="_blank">مشاهده</a></li>{% endfor %}</ul>{% endfor %}<a href="/shop">بازگشت به فروشگاه</a></body></html>'''
    return render_template_string(html, categories=CATEGORIES, cosmetics=cosmetics_dict)

# ===================== STYLES =====================
STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap');

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Vazirmatn', 'Poppins', system-ui, sans-serif;
    background: linear-gradient(145deg, #fffaf5 0%, #ffffff 100%);
    color: #1a1a1a;
    line-height: 1.6;
    overflow-x: hidden;
}

:root {
    --orange-primary: #f97316;
    --orange-dark: #ea580c;
    --orange-light: #ffedd5;
    --orange-soft: #fff7ed;
    --white-pure: #ffffff;
    --text-dark: #1e293b;
    --text-soft: #334155;
    --shadow-sm: 0 10px 25px -5px rgba(249, 115, 22, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.02);
    --shadow-md: 0 20px 25px -12px rgba(249, 115, 22, 0.12);
    --shadow-lg: 0 25px 50px -12px rgba(249, 115, 22, 0.25);
    --gradient: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    --gradient-glow: linear-gradient(135deg, #f97316 0%, #fbbf24 50%, #ea580c 100%);
    --success: #10b981;
    --danger: #ef4444;
    --online-green: #22c55e;
    --offline-red: #ef4444;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(50px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInScale {
    from { opacity: 0; transform: scale(0.9); }
    to { opacity: 1; transform: scale(1); }
}
@keyframes slideInRight {
    from { opacity: 0; transform: translateX(50px); }
    to { opacity: 1; transform: translateX(0); }
}
@keyframes slideInLeft {
    from { opacity: 0; transform: translateX(-50px); }
    to { opacity: 1; transform: translateX(0); }
}
@keyframes glowPulse {
    0% { text-shadow: 0 0 0px rgba(249, 115, 22, 0); }
    50% { text-shadow: 0 0 20px rgba(249, 115, 22, 0.6), 0 0 5px rgba(249, 115, 22, 0.3); }
    100% { text-shadow: 0 0 0px rgba(249, 115, 22, 0); }
}
@keyframes float {
    0% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-15px) rotate(2deg); }
    100% { transform: translateY(0px) rotate(0deg); }
}
@keyframes floatReverse {
    0% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(10px) rotate(-2deg); }
    100% { transform: translateY(0px) rotate(0deg); }
}
@keyframes borderPulse {
    0% { border-color: rgba(249, 115, 22, 0.3); box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.2); }
    50% { border-color: rgba(249, 115, 22, 0.8); box-shadow: 0 0 0 12px rgba(249, 115, 22, 0); }
    100% { border-color: rgba(249, 115, 22, 0.3); box-shadow: 0 0 0 0 rgba(249, 115, 22, 0); }
}
@keyframes rotateIn {
    from { opacity: 0; transform: rotate(-10deg) scale(0.9); }
    to { opacity: 1; transform: rotate(0deg) scale(1); }
}
@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}
@keyframes zoomIn {
    from { opacity: 0; transform: scale(0.5); }
    to { opacity: 1; transform: scale(1); }
}
@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
@keyframes wave {
    0%, 100% { transform: translateY(0); }
    25% { transform: translateY(-5px); }
    75% { transform: translateY(5px); }
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
@keyframes blinkRed {
    0%, 100% { opacity: 1; border-color: var(--offline-red); color: var(--offline-red); }
    50% { opacity: 0.3; border-color: #ff6b6b; color: #ff6b6b; }
}
@keyframes countUp {
    0% { opacity: 0; transform: scale(0.8); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes onlineFlash {
    0% { background-color: var(--online-green); border-color: var(--online-green); }
    30% { background-color: var(--offline-red); border-color: var(--offline-red); }
    60% { background-color: var(--offline-red); border-color: var(--offline-red); }
    100% { background-color: var(--online-green); border-color: var(--online-green); }
}
@keyframes offlinePulse {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
@keyframes slideDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes slideUp {
    from { opacity: 1; transform: translateY(0); }
    to { opacity: 0; transform: translateY(-20px); }
}
@keyframes menuBounce {
    0% { transform: scale(0.8) translateY(-10px); opacity: 0; }
    50% { transform: scale(1.05) translateY(0); opacity: 1; }
    100% { transform: scale(1) translateY(0); opacity: 1; }
}

.animate-fade-up { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.9, 0.4, 1.1) forwards; }
.animate-fade-scale { animation: fadeInScale 0.6s ease-out forwards; }
.animate-slide-right { animation: slideInRight 0.7s ease forwards; }
.animate-slide-left { animation: slideInLeft 0.7s ease forwards; }
.animate-float { animation: float 4s ease-in-out infinite; }
.animate-float-reverse { animation: floatReverse 4s ease-in-out infinite; }
.animate-glow { animation: glowPulse 3s infinite; }
.animate-rotate { animation: rotateIn 0.6s ease forwards; }
.animate-bounce { animation: bounce 0.5s ease; }
.animate-border-pulse { animation: borderPulse 2s infinite; }
.animate-zoom { animation: zoomIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }
.animate-pulse { animation: pulse 2s ease-in-out infinite; }
.animate-wave { animation: wave 2s ease-in-out infinite; }
.animate-blink { animation: blink 1.5s ease-in-out infinite; }
.animate-blink-red { animation: blinkRed 1.2s ease-in-out infinite; }
.animate-count { animation: countUp 0.3s ease forwards; }
.animate-online-flash { animation: onlineFlash 1s ease forwards; }
.animate-offline-pulse { animation: offlinePulse 1.5s ease-in-out infinite; }
.animate-slide-down { animation: slideDown 0.3s ease forwards; }
.animate-slide-up { animation: slideUp 0.3s ease forwards; }
.animate-menu-bounce { animation: menuBounce 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }

.scroll-animate {
    opacity: 0;
    transform: translateY(50px);
    transition: all 0.8s cubic-bezier(0.2, 0.9, 0.4, 1.1);
}
.scroll-animate.visible {
    opacity: 1;
    transform: translateY(0);
}
.delay-1 { animation-delay: 0.1s; }
.delay-2 { animation-delay: 0.2s; }
.delay-3 { animation-delay: 0.3s; }
.delay-4 { animation-delay: 0.4s; }
.delay-5 { animation-delay: 0.5s; }

/* ===== نوار ناوبری ===== */
.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.8rem 5%;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(12px);
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
    border-bottom: 1px solid var(--orange-light);
}

.nav-left {
    display: flex;
    align-items: center;
    gap: 20px;
}

.nav-right {
    display: flex;
    align-items: center;
    gap: 15px;
}

/* ===== منوی همبرگری ===== */
.hamburger-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}

.hamburger {
    display: flex;
    flex-direction: column;
    gap: 5px;
    cursor: pointer;
    padding: 8px;
    background: transparent;
    border: none;
    transition: all 0.3s ease;
}

.hamburger span {
    display: block;
    width: 28px;
    height: 3px;
    background: var(--orange-primary);
    border-radius: 4px;
    transition: all 0.3s ease;
}

.hamburger:hover span {
    background: var(--orange-dark);
}

.hamburger.active span:nth-child(1) {
    transform: rotate(45deg) translate(5px, 6px);
}
.hamburger.active span:nth-child(2) {
    opacity: 0;
}
.hamburger.active span:nth-child(3) {
    transform: rotate(-45deg) translate(5px, -6px);
}

.mobile-menu {
    display: none;
    position: absolute;
    top: 50px;
    right: 0;
    background: var(--white-pure);
    border-radius: 20px;
    padding: 15px 10px;
    min-width: 200px;
    border: 1px solid var(--orange-light);
    box-shadow: var(--shadow-lg);
    flex-direction: column;
    gap: 8px;
    z-index: 999;
    animation: menuBounce 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

.mobile-menu.active {
    display: flex;
}

.mobile-menu a {
    text-decoration: none;
    color: var(--text-dark);
    font-weight: 600;
    padding: 10px 16px;
    border-radius: 12px;
    transition: all 0.2s ease;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 12px;
}

.mobile-menu a:hover {
    background: var(--orange-soft);
    color: var(--orange-primary);
}

.mobile-menu a.support-link {
    color: #ff4757;
}
.mobile-menu a.support-link:hover {
    background: rgba(255, 71, 87, 0.1);
}

.logo {
    font-size: 2rem;
    font-weight: 800;
    font-family: 'Poppins', 'Vazirmatn', sans-serif;
    background: var(--gradient-glow);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
    text-decoration: none;
    transition: all 0.3s ease;
}

.online-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    padding: 5px 12px;
    border-radius: 50px;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--online-green);
    transition: all 0.3s ease;
    white-space: nowrap;
}
.online-badge.offline-flash {
    background: rgba(239, 68, 68, 0.15);
    border-color: var(--offline-red);
    color: var(--offline-red);
    animation: offlinePulse 0.6s ease-out;
}
.online-number {
    font-weight: 800;
    font-size: 1rem;
    margin: 0 2px;
    transition: all 0.3s ease;
}
.online-dot {
    width: 8px;
    height: 8px;
    background-color: var(--online-green);
    border-radius: 50%;
    animation: blink 1.5s ease-in-out infinite;
    box-shadow: 0 0 5px var(--online-green);
    transition: all 0.3s ease;
}
.online-dot.offline {
    background-color: var(--offline-red);
    animation: blinkRed 1.2s ease-in-out infinite;
    box-shadow: 0 0 5px var(--offline-red);
}

.cart-icon {
    color: var(--text-dark);
    text-decoration: none;
    font-size: 1.2rem;
    position: relative;
    transition: all 0.3s ease;
}
.cart-icon:hover {
    transform: scale(1.1);
    color: var(--orange-primary);
}
.cart-icon span {
    background: var(--orange-primary);
    border-radius: 50%;
    padding: 2px 6px;
    font-size: 0.7rem;
    margin-right: 4px;
    color: white;
    font-weight: bold;
}

.hero h1, .section-title, .cosmetic-name, .developer-name {
    font-family: 'Poppins', 'Vazirmatn', sans-serif;
    font-weight: 800;
    letter-spacing: -0.3px;
}
.hero h1 {
    font-size: 4.5rem;
    background: var(--gradient-glow);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 1rem;
    animation: fadeInUp 0.6s ease, glowPulse 3s infinite;
}

.hero {
    min-height: 90vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 8rem 20px 4rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(249,115,22,0.08) 0%, transparent 60%);
    animation: float 20s ease-in-out infinite;
    pointer-events: none;
}
.beta-tag {
    display: inline-block;
    background: var(--orange-light);
    padding: 0.5rem 1.5rem;
    border-radius: 40px;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--orange-dark);
    margin-bottom: 1.5rem;
    animation: fadeInUp 0.5s ease, borderPulse 2s infinite;
}
.hero .description {
    font-size: 1.2rem;
    max-width: 700px;
    margin: 0 auto 2rem auto;
    color: var(--text-soft);
    font-weight: 500;
}
.btn {
    background: var(--gradient);
    color: white;
    padding: 14px 36px;
    border-radius: 50px;
    font-weight: 700;
    font-size: 1rem;
    display: inline-block;
    border: none;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
    text-decoration: none;
}
.btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    transition: left 0.5s ease;
}
.btn:hover::before {
    left: 100%;
}
.btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(249, 115, 22, 0.35);
}
.btn-outline {
    background: transparent;
    border: 2px solid var(--orange-primary);
    color: var(--orange-primary);
    margin-left: 15px;
}
.btn-outline:hover {
    background: var(--orange-primary);
    color: white;
    transform: translateY(-3px);
}
.section {
    padding: 80px 5%;
}
.section-title {
    text-align: center;
    font-size: 2.5rem;
    font-weight: 800;
    margin-bottom: 3rem;
    color: var(--text-dark);
    position: relative;
}
.section-title span {
    color: var(--orange-primary);
    position: relative;
    display: inline-block;
}
.section-title span::after {
    content: '';
    position: absolute;
    bottom: -8px;
    left: 0;
    width: 100%;
    height: 3px;
    background: var(--gradient);
    transform: scaleX(0);
    transition: transform 0.5s ease;
    transform-origin: right;
}
.section-title:hover span::after {
    transform: scaleX(1);
    transform-origin: left;
}
.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 2rem;
    max-width: 1300px;
    margin: 0 auto;
}
.feature-card {
    background: var(--white-pure);
    border-radius: 28px;
    padding: 2rem;
    text-align: center;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    border: 1px solid var(--orange-light);
}
.feature-card:hover {
    transform: translateY(-12px) scale(1.02);
    border-color: var(--orange-primary);
    box-shadow: var(--shadow-lg);
}
.feature-icon {
    font-size: 3.5rem;
    margin-bottom: 1rem;
    display: inline-block;
    animation: float 3s ease-in-out infinite;
}
.feature-card h3 {
    font-size: 1.4rem;
    margin-bottom: 0.8rem;
    font-weight: 700;
}
.feature-card p {
    color: var(--text-soft);
    line-height: 1.6;
}
.team-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}
.team-card {
    background: var(--white-pure);
    border-radius: 28px;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    border: 1px solid var(--orange-light);
    text-align: center;
    position: relative;
}
.team-card:hover {
    transform: translateY(-12px);
    border-color: var(--orange-primary);
    box-shadow: var(--shadow-lg);
}
.team-avatar {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 30px auto 20px;
    font-size: 3rem;
    color: white;
    transition: all 0.3s ease;
    background: var(--gradient);
    overflow: hidden;
}
.team-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.team-card:hover .team-avatar {
    transform: scale(1.05);
    box-shadow: 0 0 30px rgba(249, 115, 22, 0.5);
}
.team-name {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text-dark);
    margin-bottom: 5px;
}
.team-role {
    font-size: 0.9rem;
    color: var(--orange-primary);
    font-weight: 600;
    margin-bottom: 8px;
}
.team-username {
    font-size: 0.85rem;
    color: var(--text-soft);
    background: var(--orange-soft);
    display: inline-block;
    padding: 5px 12px;
    border-radius: 50px;
    margin: 10px auto;
}
.team-badge {
    position: absolute;
    top: 15px;
    right: 15px;
    background: var(--gradient);
    color: white;
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 0.7rem;
    font-weight: 700;
}
.team-status {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.7rem;
    margin-top: 5px;
    padding: 2px 8px;
    border-radius: 20px;
}
.team-status.online {
    color: var(--online-green);
    background: rgba(34, 197, 94, 0.1);
}
.status-dot-online {
    width: 6px;
    height: 6px;
    background-color: var(--online-green);
    border-radius: 50%;
    animation: blink 1.5s ease-in-out infinite;
}

.stats-section {
    background: linear-gradient(135deg, var(--orange-soft) 0%, #fff5eb 100%);
    border-radius: 48px;
    margin: 20px 5%;
    padding: 3rem 2rem;
}
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 2rem;
    text-align: center;
}
.stat-item {
    transition: all 0.3s ease;
}
.stat-item:hover {
    transform: translateY(-5px);
}
.stat-number {
    font-size: 3rem;
    font-weight: 800;
    font-family: 'Poppins', monospace;
    color: var(--orange-primary);
    margin-bottom: 0.5rem;
    animation: glowPulse 2s infinite;
}
.stat-label {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-soft);
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}
.cosmetic-card {
    background: var(--white-pure);
    border-radius: 28px;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    border: 1px solid var(--orange-light);
    box-shadow: var(--shadow-sm);
}
.cosmetic-card:hover {
    transform: translateY(-12px) scale(1.02);
    border-color: var(--orange-primary);
    box-shadow: var(--shadow-lg);
}
.cosmetic-img {
    padding: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 200px;
    background: var(--orange-soft);
    transition: all 0.3s ease;
}
.cosmetic-card:hover .cosmetic-img {
    background: var(--orange-light);
}
.cosmetic-img img {
    max-width: 100%;
    max-height: 160px;
    border-radius: 16px;
    transition: transform 0.4s ease;
}
.cosmetic-card:hover .cosmetic-img img {
    transform: scale(1.1);
}
.cosmetic-info {
    padding: 20px;
    text-align: center;
}
.cosmetic-name {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 8px;
}
.cosmetic-price {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--orange-primary);
    margin: 12px 0;
}
.old-price {
    font-size: 0.85rem;
    text-decoration: line-through;
    color: var(--text-soft);
    margin-left: 8px;
}
.buy-btn {
    background: var(--gradient);
    border: none;
    color: white;
    padding: 12px 24px;
    border-radius: 40px;
    font-weight: 700;
    cursor: pointer;
    width: 100%;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.buy-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    transition: left 0.5s ease;
}
.buy-btn:hover::before {
    left: 100%;
}
.buy-btn:hover {
    transform: scale(0.98);
    box-shadow: 0 8px 20px rgba(249, 115, 22, 0.4);
}
.category-menu {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
    margin-bottom: 50px;
}
.category-btn {
    background: var(--white-pure);
    border: 1px solid var(--orange-light);
    color: var(--text-dark);
    padding: 10px 28px;
    border-radius: 50px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.category-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(249,115,22,0.15), transparent);
    transition: left 0.5s ease;
}
.category-btn:hover::before {
    left: 100%;
}
.category-btn:hover, .category-btn.active {
    background: var(--gradient);
    border-color: transparent;
    color: white;
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(249, 115, 22, 0.3);
}
/* ===== مودال دانلود ===== */
.download-modal {
    max-width: 500px !important;
    padding: 30px !important;
}

.download-options {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 15px;
    margin: 20px 0;
}

.download-option {
    background: var(--orange-soft);
    border-radius: 20px;
    padding: 20px 15px;
    text-align: center;
    transition: all 0.3s ease;
    border: 2px solid transparent;
}

.download-option:hover {
    transform: translateY(-5px);
    border-color: var(--orange-primary);
    box-shadow: var(--shadow-md);
}

.download-icon {
    font-size: 2.5rem;
    margin-bottom: 8px;
}

.download-name {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--text-dark);
}

.download-version {
    font-size: 0.75rem;
    color: var(--text-soft);
    margin: 4px 0 12px 0;
}

.download-btn {
    background: var(--gradient);
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 50px;
    font-weight: 700;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.3s ease;
    width: 100%;
}

.download-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 8px 20px rgba(249, 115, 22, 0.4);
}

.download-btn:active {
    transform: scale(0.95);
}

@media (max-width: 480px) {
    .download-options {
        grid-template-columns: 1fr;
        gap: 10px;
    }
    .download-option {
        padding: 15px;
    }
}

.modal {
    display: none;
    position: fixed;
    z-index: 2000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.6);
    backdrop-filter: blur(8px);
    animation: fadeInUp 0.3s ease;
}
.modal-content {
    background: var(--white-pure);
    margin: 10% auto;
    padding: 30px;
    width: 90%;
    max-width: 400px;
    border-radius: 28px;
    text-align: center;
    position: relative;
    border: 1px solid var(--orange-light);
    animation: zoomIn 0.4s ease;
}
.modal-content .close {
    position: absolute;
    left: 15px;
    top: 10px;
    font-size: 28px;
    cursor: pointer;
    color: var(--text-soft);
    transition: all 0.3s ease;
}
.modal-content .close:hover {
    transform: rotate(90deg);
    color: var(--orange-primary);
}
.download-modal-icon {
    font-size: 3rem;
    margin-bottom: 15px;
    animation: float 2s ease-in-out infinite;
}
.download-modal-text {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--orange-primary);
    margin-bottom: 10px;
}
.download-modal-sub {
    font-size: 0.9rem;
    color: var(--text-soft);
}
footer {
    text-align: center;
    padding: 3rem;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #8899aa;
    margin-top: 3rem;
}
.footer-content {
    max-width: 1200px;
    margin: 0 auto;
}
.footer-stats {
    display: flex;
    justify-content: center;
    gap: 3rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
}
.footer-stat {
    text-align: center;
}
.footer-stat-value {
    font-size: 2rem;
    font-weight: 800;
    font-family: 'Poppins', monospace;
    color: var(--orange-primary);
}
.footer-stat-label {
    font-size: 0.85rem;
    color: #8899aa;
}
.footer-copyright {
    font-size: 0.85rem;
    border-top: 1px solid rgba(255,255,255,0.1);
    padding-top: 1.5rem;
}

.faq-widget {
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 9999;
}
.faq-button {
    width: 55px;
    height: 55px;
    border-radius: 50%;
    background: var(--gradient);
    box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    border: none;
    color: white;
    font-size: 28px;
    animation: float 3s ease-in-out infinite;
}
.faq-button:hover {
    transform: scale(1.1);
    box-shadow: 0 10px 30px rgba(249, 115, 22, 0.5);
}
.faq-panel {
    position: absolute;
    bottom: 70px;
    left: 0;
    width: 340px;
    max-height: 480px;
    background: var(--white-pure);
    border-radius: 24px;
    border: 1px solid var(--orange-light);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    display: none;
    flex-direction: column;
    animation: fadeInUp 0.3s ease;
}
.faq-panel.active {
    display: flex;
}
.faq-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 15px;
    background: linear-gradient(135deg, var(--orange-light), var(--orange-soft));
    border-bottom: 1px solid var(--orange-light);
    gap: 8px;
}
.faq-tab {
    background: transparent;
    border: none;
    padding: 8px 12px;
    border-radius: 30px;
    font-weight: 600;
    cursor: pointer;
    color: var(--text-soft);
    transition: all 0.2s;
    font-size: 0.85rem;
}
.faq-tab.active {
    background: var(--orange-primary);
    color: white;
}
.faq-tab:hover:not(.active) {
    background: var(--orange-soft);
    color: var(--orange-primary);
}
.faq-close {
    background: transparent;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: var(--text-soft);
    transition: transform 0.2s;
    margin-right: auto;
}
.faq-close:hover {
    transform: rotate(90deg);
    color: var(--orange-primary);
}
.faq-content {
    padding: 15px;
    max-height: 380px;
    overflow-y: auto;
}
.faq-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.faq-list li {
    padding: 10px;
    border-bottom: 1px solid var(--orange-light);
    cursor: pointer;
    transition: 0.2s;
    font-size: 0.9rem;
}
.faq-list li:hover {
    background: var(--orange-soft);
    color: var(--orange-primary);
    transform: translateX(-5px);
}
.faq-answer {
    margin-top: 15px;
    padding: 12px;
    background: var(--orange-soft);
    border-radius: 16px;
    font-size: 0.85rem;
    display: none;
}
.faq-answer.show {
    display: block;
}
.support-init {
    display: flex;
    flex-direction: column;
    gap: 15px;
}
.support-init input {
    padding: 12px;
    border: 1px solid var(--orange-light);
    border-radius: 28px;
    font-size: 0.9rem;
    background: var(--white-pure);
}
.support-init button {
    background: var(--gradient);
    color: white;
    border: none;
    padding: 10px;
    border-radius: 40px;
    font-weight: 700;
    cursor: pointer;
}
.chat-container {
    display: flex;
    flex-direction: column;
    height: 350px;
}
.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    background: #f9f9f9;
    border-radius: 16px;
    margin-bottom: 10px;
}
.message {
    margin-bottom: 12px;
    display: flex;
    flex-direction: column;
}
.message.user {
    align-items: flex-end;
}
.message.bot {
    align-items: flex-start;
}
.message-bubble {
    max-width: 85%;
    padding: 8px 12px;
    border-radius: 18px;
    font-size: 0.85rem;
    word-break: break-word;
}
.message.user .message-bubble {
    background: var(--orange-primary);
    color: white;
    border-bottom-right-radius: 4px;
}
.message.bot .message-bubble {
    background: #e9ecef;
    color: #1e293b;
    border-bottom-left-radius: 4px;
}
.message-time {
    font-size: 0.65rem;
    color: #888;
    margin-top: 4px;
    margin-left: 8px;
    margin-right: 8px;
}
.chat-input-area {
    display: flex;
    gap: 8px;
}
.chat-input-area input {
    flex: 1;
    padding: 10px;
    border: 1px solid var(--orange-light);
    border-radius: 40px;
    font-size: 0.85rem;
}
.chat-input-area button {
    background: var(--gradient);
    border: none;
    padding: 8px 16px;
    border-radius: 40px;
    color: white;
    font-weight: bold;
    cursor: pointer;
}
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-track {
    background: var(--orange-light);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb {
    background: var(--gradient);
    border-radius: 10px;
}

/* ===== واکنش‌گرا ===== */
@media (max-width: 768px) {
    .hero h1 { font-size: 2.8rem; }
    .navbar { padding: 0.5rem 4%; gap: 8px; }
    .logo { font-size: 1.5rem; }
    .online-badge { font-size: 0.7rem; padding: 3px 8px; }
    .online-number { font-size: 0.8rem; }
    .hamburger span { width: 24px; height: 2.5px; }
    .mobile-menu { min-width: 160px; right: -10px; top: 45px; }
    .section { padding: 50px 20px; }
    .category-menu { gap: 8px; }
    .category-btn { padding: 8px 18px; font-size: 0.85rem; }
    .stats-grid { gap: 1.5rem; }
    .stat-number { font-size: 2rem; }
    .footer-stats { gap: 1.5rem; }
    .team-grid { gap: 1.5rem; }
    .features-grid { grid-template-columns: 1fr; }
    .faq-panel { width: 300px; left: -10px; }
}
"""
# ===================== LOGIN_TEMPLATE =====================
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ورود / ثبت نام | MarsClient</title><style>{{ styles | safe }}</style></head>
<body>
<nav class="navbar">
    <div class="nav-left">
        <a href="/" class="logo animate-float">MarsClient</a>
    </div>
    <div class="nav-right">
        <div class="online-badge" id="onlineBadge">
            <span class="online-dot" id="onlineDot"></span>
            آنلاین: <span class="online-number" id="onlineCount">0</span> نفر
        </div>
        <div class="hamburger-wrapper">
            <button class="hamburger" id="hamburgerBtn" onclick="toggleMobileMenu()" aria-label="منو">
                <span></span><span></span><span></span>
            </button>
            <div class="mobile-menu" id="mobileMenu">
                <a href="/">🏠 خانه</a>
                <a href="/shop">🛒 فروشگاه</a>
                <a href="/login">🔑 ورود / ثبت‌نام</a>
                <a href="https://reymit.ir/marsclient" target="_blank" class="support-link">❤️ حمایت</a>
            </div>
        </div>
    </div>
</nav>

<div id="downloadModal" class="modal">
    <div class="modal-content download-modal">
        <span class="close" onclick="closeDownloadModal()">&times;</span>
        <div class="download-modal-icon">🚀</div>
        <h2 style="color:var(--orange-primary); margin-bottom:5px;">MarsClient Download</h2>
        <p style="color:var(--text-soft); margin-bottom:20px;">کلاینت ماینکرفت نسل بعدی</p>
        
        <div class="download-options">
            <div class="download-option">
                <div class="download-icon">🪟</div>
                <div class="download-name">ویندوز</div>
                <div class="download-version">Windows 10/11</div>
                <button class="download-btn" onclick="showComingSoon('ویندوز')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🐧</div>
                <div class="download-name">لینوکس</div>
                <div class="download-version">Ubuntu / Debian</div>
                <button class="download-btn" onclick="showComingSoon('لینوکس')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🍎</div>
                <div class="download-name">مک</div>
                <div class="download-version">macOS</div>
                <button class="download-btn" onclick="showComingSoon('مک')">به زودی ⏳</button>
            </div>
        </div>
        
        <p style="color:#8899aa; font-size:0.8rem; margin-top:15px;">🔹 نسخه بتا v1.0 - به زودی منتشر می‌شود</p>
    </div>
</div>

<div id="comingSoonModal" class="modal">
    <div class="modal-content" style="max-width:350px;">
        <span class="close" onclick="closeComingSoon()">&times;</span>
        <div style="text-align:center; padding:10px;">
            <div style="font-size:4rem; margin-bottom:10px;">🔧</div>
            <h3 style="color:var(--orange-primary);">در حال ساخت!</h3>
            <p id="comingSoonText" style="color:var(--text-soft); margin:10px 0;">نسخه ویندوز به زودی منتشر می‌شود</p>
            <button onclick="closeComingSoon()" class="btn" style="padding:10px 30px;">متوجه شدم</button>
        </div>
    </div>
</div>

<section class="section" style="min-height:80vh; padding-top:120px;">
<div style="max-width:500px; margin:0 auto; background:var(--white-pure); border-radius:32px; padding:35px; border:1px solid var(--orange-light); box-shadow:var(--shadow-md);">
    <div style="display:flex; gap:20px; margin-bottom:30px; border-bottom:2px solid var(--orange-light);">
        <button id="loginTabBtn" class="category-btn active" style="flex:1;">ورود</button>
        <button id="registerTabBtn" class="category-btn" style="flex:1;">ثبت نام</button>
    </div>
    <div id="loginForm">
        <div class="input-group"><label>نام کاربری</label><div class="input-wrapper"><i>👤</i><input type="text" id="loginUsername" placeholder="نام کاربری خود را وارد کنید"></div></div>
        <div class="input-group"><label>رمز عبور</label><div class="input-wrapper"><i>🔒</i><input type="password" id="loginPassword" placeholder="رمز عبور"><button type="button" class="toggle-password" onclick="togglePassword('loginPassword')">👁️</button></div></div>
        <div id="loginError" style="color:var(--danger); margin:10px 0; font-size:0.85rem;"></div>
        <button id="doLoginBtn" class="btn" style="width:100%;">ورود</button>
    </div>
    <div id="registerForm" style="display:none;">
        <div class="input-group"><label>ایمیل</label><div class="input-wrapper"><i>📧</i><input type="email" id="regEmail" placeholder="example@gmail.com"></div><div class="input-helper" id="emailHelper">ایمیل معتبر وارد کنید</div></div>
        <div class="input-group"><label>نام کاربری</label><div class="input-wrapper"><i>👤</i><input type="text" id="regUsername" placeholder="حداقل 3 کاراکتر"></div><div class="input-helper" id="usernameHelper">فقط حروف انگلیسی، اعداد و زیرخط</div></div>
        <div class="input-group"><label>رمز عبور</label><div class="input-wrapper"><i>🔒</i><input type="password" id="regPassword" placeholder="حداقل 6 کاراکتر"><button type="button" class="toggle-password" onclick="togglePassword('regPassword')">👁️</button></div><div class="password-strength"><div class="password-strength-bar" id="passwordStrengthBar"></div></div><div class="input-helper" id="passwordHelper">حداقل ۶ کاراکتر (حروف و اعداد)</div></div>
        <div class="input-group"><label>تکرار رمز عبور</label><div class="input-wrapper"><i>🔒</i><input type="password" id="regConfirm" placeholder="رمز را دوباره وارد کنید"><button type="button" class="toggle-password" onclick="togglePassword('regConfirm')">👁️</button></div><div class="input-helper" id="confirmHelper">رمز عبور را تکرار کنید</div></div>
        <div id="regError" style="color:var(--danger); margin:10px 0; font-size:0.85rem;"></div>
        <button id="doRegisterBtn" class="btn" style="width:100%;">ثبت نام</button>
    </div>
</div>
</section>

<footer><div class="footer-content"><div class="footer-stats"><div class="footer-stat"><div class="footer-stat-value animate-glow">۴.۹</div><div class="footer-stat-label">امتیاز کاربران</div></div><div class="footer-stat"><div class="footer-stat-value">۴۰+</div><div class="footer-stat-label">ماژول داخلی</div></div></div><div class="footer-copyright">© ۲۰۲۶ MarsClient — نسل بعدی موتور ماینکرفت</div></div></footer>

<div class="faq-widget">
    <button class="faq-button" onclick="toggleFaq()">❓</button>
    <div class="faq-panel" id="faqPanel">
        <div class="faq-header">
            <button id="faqTabBtn" class="faq-tab active">❓ سوالات متداول</button>
            <button id="supportTabBtn" class="faq-tab">📞 پشتیبانی</button>
            <button class="faq-close" onclick="toggleFaq()">✖</button>
        </div>
        <div id="faqContent" class="faq-content"></div>
    </div>
</div>

<script>
// ===== منوی همبرگری =====
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    menu.classList.toggle('active');
    btn.classList.toggle('active');
}
document.addEventListener('click', function(event) {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    if (!menu.contains(event.target) && !btn.contains(event.target)) {
        menu.classList.remove('active');
        btn.classList.remove('active');
    }
});

// ===== مودال دانلود =====
function showDownloadModal() { 
    document.getElementById('downloadModal').style.display='block'; 
}

function closeDownloadModal() { 
    document.getElementById('downloadModal').style.display='none'; 
}

// ===== مودال "به زودی" =====
function showComingSoon(os) {
    const modal = document.getElementById('comingSoonModal');
    const text = document.getElementById('comingSoonText');
    const osNames = {
        'ویندوز': 'ویندوز (Windows 10/11)',
        'لینوکس': 'لینوکس (Ubuntu / Debian)',
        'مک': 'مک (macOS)'
    };
    text.textContent = `نسخه ${osNames[os] || os} به زودی منتشر می‌شود`;
    modal.style.display = 'block';
}

function closeComingSoon() {
    document.getElementById('comingSoonModal').style.display='none';
}

// بستن مودال با کلیک خارج از آن
window.onclick = function(event) {
    const modal1 = document.getElementById('downloadModal');
    const modal2 = document.getElementById('comingSoonModal');
    if (event.target == modal1) modal1.style.display = 'none';
    if (event.target == modal2) modal2.style.display = 'none';
}

// ===== آنلاین =====
let sessionId = localStorage.getItem('marsclient_session');
if (!sessionId) { sessionId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36); localStorage.setItem('marsclient_session', sessionId); }
let onlineCount = 0;

function sendHeartbeat() { 
    fetch('/api/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId}) })
    .then(r=>r.json())
    .then(data=>{ 
        if(data.online_count !== undefined) {
            const oldCount = onlineCount;
            onlineCount = data.online_count;
            document.getElementById('onlineCount').innerText = onlineCount;
            if(onlineCount < oldCount || onlineCount === 0) {
                flashOffline();
            }
        }
    })
    .catch(e=>console.warn); 
}

function flashOffline() {
    const badge = document.getElementById('onlineBadge');
    const dot = document.getElementById('onlineDot');
    badge.classList.add('offline-flash');
    dot.classList.add('offline');
    setTimeout(() => {
        badge.classList.remove('offline-flash');
        dot.classList.remove('offline');
    }, 1200);
}

function sendLeave() { 
    navigator.sendBeacon('/api/leave', JSON.stringify({session_id:sessionId}));
    flashOffline();
}

window.addEventListener('beforeunload', sendLeave);
sendHeartbeat(); 
setInterval(sendHeartbeat, 20000);

window.addEventListener('load', function() {
    const badge = document.getElementById('onlineBadge');
    badge.style.animation = 'onlineFlash 0.8s ease';
    setTimeout(() => {
        badge.style.animation = '';
    }, 1000);
});

function togglePassword(id) { const input = document.getElementById(id); input.type = input.type === 'password' ? 'text' : 'password'; }
function validateEmail(email) { return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email); }
function validateUsername(username) { return username.length >= 3 && /^[a-zA-Z0-9_]+$/.test(username); }
function checkPasswordStrength(password) {
    let strength = 0;
    if (password.length >= 6) strength++;
    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (strength <= 1) return 'weak';
    if (strength <= 3) return 'medium';
    return 'strong';
}
function updateRegisterFormValidity() {
    const email = document.getElementById('regEmail').value;
    const username = document.getElementById('regUsername').value;
    const password = document.getElementById('regPassword').value;
    const confirm = document.getElementById('regConfirm').value;
    let isValid = true;
    const emailValid = validateEmail(email);
    const emailHelper = document.getElementById('emailHelper');
    if (!email) { emailHelper.textContent = 'ایمیل الزامی است'; emailHelper.classList.add('error'); isValid = false; }
    else if (!emailValid) { emailHelper.textContent = 'ایمیل نامعتبر است'; emailHelper.classList.add('error'); isValid = false; }
    else { emailHelper.textContent = '✅ ایمیل معتبر'; emailHelper.classList.remove('error'); emailHelper.classList.add('success'); }
    const usernameValid = validateUsername(username);
    const usernameHelper = document.getElementById('usernameHelper');
    if (!username) { usernameHelper.textContent = 'نام کاربری الزامی است'; usernameHelper.classList.add('error'); isValid = false; }
    else if (!usernameValid) { usernameHelper.textContent = 'حداقل ۳ کاراکتر (حروف/اعداد/زیرخط)'; usernameHelper.classList.add('error'); isValid = false; }
    else { usernameHelper.textContent = '✅ نام کاربری مناسب'; usernameHelper.classList.remove('error'); usernameHelper.classList.add('success'); }
    const strength = checkPasswordStrength(password);
    const bar = document.getElementById('passwordStrengthBar');
    bar.className = 'password-strength-bar';
    if (password.length === 0) bar.style.width = '0%';
    else if (strength === 'weak') { bar.classList.add('strength-weak'); bar.style.width = '33%'; }
    else if (strength === 'medium') { bar.classList.add('strength-medium'); bar.style.width = '66%'; }
    else { bar.classList.add('strength-strong'); bar.style.width = '100%'; }
    const passwordHelper = document.getElementById('passwordHelper');
    if (password.length > 0 && password.length < 6) { passwordHelper.textContent = 'رمز حداقل ۶ کاراکتر'; passwordHelper.classList.add('error'); isValid = false; }
    else if (password.length >= 6) { passwordHelper.textContent = '✅ رمز قابل قبول'; passwordHelper.classList.remove('error'); passwordHelper.classList.add('success'); }
    else { passwordHelper.textContent = 'حداقل ۶ کاراکتر (حروف و اعداد)'; passwordHelper.classList.remove('error','success'); }
    const confirmHelper = document.getElementById('confirmHelper');
    if (confirm.length > 0 && password !== confirm) { confirmHelper.textContent = 'رمزها مطابقت ندارند'; confirmHelper.classList.add('error'); isValid = false; }
    else if (confirm.length > 0 && password === confirm) { confirmHelper.textContent = '✅ رمزها مطابقت دارند'; confirmHelper.classList.remove('error'); confirmHelper.classList.add('success'); }
    else { confirmHelper.textContent = 'رمز عبور را تکرار کنید'; confirmHelper.classList.remove('error','success'); }
    return isValid;
}
document.getElementById('regEmail').addEventListener('input', updateRegisterFormValidity);
document.getElementById('regUsername').addEventListener('input', updateRegisterFormValidity);
document.getElementById('regPassword').addEventListener('input', updateRegisterFormValidity);
document.getElementById('regConfirm').addEventListener('input', updateRegisterFormValidity);

document.getElementById('doLoginBtn').addEventListener('click', async ()=>{
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const res = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username,password})});
    const data = await res.json();
    if(data.success) window.location.href='/';
    else document.getElementById('loginError').innerText = data.message;
});
document.getElementById('doRegisterBtn').addEventListener('click', async ()=>{
    const email = document.getElementById('regEmail').value.trim();
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    const confirm = document.getElementById('regConfirm').value;
    if(!validateEmail(email)) { document.getElementById('regError').innerText = 'ایمیل نامعتبر است'; return; }
    if(!validateUsername(username)) { document.getElementById('regError').innerText = 'نام کاربری باید حداقل ۳ کاراکتر و فقط شامل حروف، اعداد و زیرخط باشد'; return; }
    if(password.length < 6) { document.getElementById('regError').innerText = 'رمز عبور باید حداقل ۶ کاراکتر باشد'; return; }
    if(password !== confirm) { document.getElementById('regError').innerText = 'رمز عبور و تکرار آن مطابقت ندارند'; return; }
    const res = await fetch('/api/register', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email,username,password,confirm_password:confirm})});
    const data = await res.json();
    if(data.success) window.location.href='/';
    else document.getElementById('regError').innerText = data.message;
});
document.getElementById('loginTabBtn').onclick = () => { document.getElementById('loginForm').style.display='block'; document.getElementById('registerForm').style.display='none'; document.getElementById('loginTabBtn').classList.add('active'); document.getElementById('registerTabBtn').classList.remove('active'); };
document.getElementById('registerTabBtn').onclick = () => { document.getElementById('loginForm').style.display='none'; document.getElementById('registerForm').style.display='block'; document.getElementById('registerTabBtn').classList.add('active'); document.getElementById('loginTabBtn').classList.remove('active'); updateRegisterFormValidity(); };

const faqData = [
    { q: "چگونه MarsClient را نصب کنم؟", a: "فایل نصاب را از دکمه دانلود دریافت کرده و اجرا کنید. مسیر نصب ماینکرفت را انتخاب کنید و پس از اتمام، لانچر را اجرا کنید." },
    { q: "آیا با همه نسخه‌های ماینکرفت سازگار است؟", a: "بله! MarsClient از نسخه ۱.۷ تا آخرین نسخه ماینکرفت را پشتیبانی می‌کند." },
    { q: "لانچر اختصاصی MarsClient چه قابلیت‌هایی دارد؟", a: "مدیریت مادها، دانلود خودکار نسخه‌ها، پشتیبانی از چند پروفایل، آپدیت خودکار و رابط کاربری زیبا." },
    { q: "چگونه FPS را افزایش دهم؟", a: "در تنظیمات گرافیکی کلاینت، گزینه‌های Performance Mode و Smooth FPS را فعال کنید." },
    { q: "آیا کلاینت رایگان است؟", a: "بله، کلاینت اصلی رایگان است. کازمتیک‌های فروشگاه دارای هزینه نمادین هستند." },
    { q: "چگونه ماد اضافه کنم؟", a: "از طریق لانچر اختصاصی MarsClient می‌توانید مادها را به راحتی مدیریت و نصب کنید." },
    { q: "گزارش باگ؟", a: "از طریق تیکت پشتیبانی در وبسایت یا دیسکورد." }
];
let currentTab = 'faq';
let supportUserName = '';
let supportUserPhone = '';
let chatHistory = [];

function renderFaqContent() {
    const container = document.getElementById('faqContent');
    if (currentTab === 'faq') {
        let html = '<ul class="faq-list">';
        faqData.forEach(item => { html += `<li onclick="showAnswer(this, '${item.a.replace(/'/g, "\\'")}')">${item.q}</li>`; });
        html += '</ul><div id="faqAnswer" class="faq-answer"></div>';
        container.innerHTML = html;
    } else {
        if (!supportUserName || !supportUserPhone) {
            container.innerHTML = `<div class="support-init"><input type="text" id="supportName" placeholder="نام و نام خانوادگی"><input type="tel" id="supportPhone" placeholder="شماره تماس"><button onclick="startSupportChat()">شروع گفتگو</button></div>`;
        } else {
            renderChat();
        }
    }
}

function startSupportChat() {
    const name = document.getElementById('supportName')?.value.trim();
    const phone = document.getElementById('supportPhone')?.value.trim();
    if (!name || !phone) { alert('لطفاً نام و شماره تماس را وارد کنید'); return; }
    supportUserName = name; supportUserPhone = phone; chatHistory = [];
    setTimeout(() => { addBotMessage("سلام! به پشتیبانی MarsClient خوش آمدید. لطفاً مشکل خود را مطرح کنید."); renderChat(); }, 500);
    renderFaqContent();
}

function renderChat() {
    const container = document.getElementById('faqContent');
    let messagesHtml = '<div class="chat-container"><div class="chat-messages" id="chatMessages">';
    chatHistory.forEach(msg => { const time = new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); messagesHtml += `<div class="message ${msg.sender}"><div class="message-bubble">${msg.text}</div><div class="message-time">${time}</div></div>`; });
    messagesHtml += `</div><div class="chat-input-area"><input type="text" id="chatInput" placeholder="پیام خود را بنویسید..."><button onclick="sendMessage()">ارسال</button></div></div>`;
    container.innerHTML = messagesHtml;
    const msgDiv = document.getElementById('chatMessages'); if (msgDiv) msgDiv.scrollTop = msgDiv.scrollHeight;
    const input = document.getElementById('chatInput'); if (input) input.focus();
}

function addUserMessage(text) { chatHistory.push({ sender: 'user', text: text, timestamp: Date.now() }); renderChat(); }
function addBotMessage(text) { chatHistory.push({ sender: 'bot', text: text, timestamp: Date.now() }); renderChat(); }

function sendMessage() {
    const input = document.getElementById('chatInput'); const message = input.value.trim();
    if (!message) return;
    addUserMessage(message); input.value = '';
    const lowerMsg = message.toLowerCase();
    let reply = "";
    if (lowerMsg.includes('نصب') || lowerMsg.includes('install')) { reply = "برای نصب MarsClient، فایل نصاب را از دکمه دانلود دریافت کنید. پس از اجرا، مسیر ماینکرفت را انتخاب کنید."; }
    else if (lowerMsg.includes('خرید') || lowerMsg.includes('price') || lowerMsg.includes('قیمت')) { reply = "برای خرید آیتم‌های فروشگاه، ابتدا وارد حساب شوید، سپس محصول را به سبد خرید اضافه کرده و پرداخت را انجام دهید."; }
    else if (lowerMsg.includes('fps') || lowerMsg.includes('کاهش') || lowerMsg.includes('lag')) { reply = "برای افزایش FPS، در تنظیمات گرافیکی Performance Mode را فعال کنید و از مادهای اضافی کم استفاده کنید."; }
    else if (lowerMsg.includes('مشکل') || lowerMsg.includes('error') || lowerMsg.includes('خطا')) { reply = "مشکل خود را دقیق‌تر توضیح دهید تا بتوانیم راهنمایی بهتری ارائه دهیم. در صورت نیاز، با شماره ۰۹۱۲۳۴۵۶۷۸۹ تماس بگیرید."; }
    else if (lowerMsg.includes('تشکر') || lowerMsg.includes('ممنون')) { reply = "خواهش می‌کنم! خوشحالیم که می‌توانیم کمک کنیم."; }
    else { reply = "درخواست شما ثبت شد. همکاران ما به زودی پاسخ می‌دهند. (پاسخ خودکار: لطفاً موضوع را دقیق‌تر بگویید)"; }
    setTimeout(() => addBotMessage(reply), 800);
}

function showAnswer(el, answer) { const answerDiv = document.getElementById('faqAnswer'); if (!answerDiv) return; answerDiv.innerHTML = answer; answerDiv.classList.add('show'); answerDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
function toggleFaq() { const panel = document.getElementById('faqPanel'); panel.classList.toggle('active'); if (panel.classList.contains('active')) { renderFaqContent(); const faqTabBtn = document.getElementById('faqTabBtn'); const supportTabBtn = document.getElementById('supportTabBtn'); faqTabBtn.onclick = () => { currentTab = 'faq'; renderFaqContent(); faqTabBtn.classList.add('active'); supportTabBtn.classList.remove('active'); }; supportTabBtn.onclick = () => { currentTab = 'support'; renderFaqContent(); supportTabBtn.classList.add('active'); faqTabBtn.classList.remove('active'); }; if (currentTab === 'support' && supportUserName && supportUserPhone) { renderChat(); } } }
</script>
</body>
</html>"""

# ===================== HOME_TEMPLATE =====================
HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>MarsClient | صفحه اصلی</title><style>{{ styles | safe }}</style></head>
<body>
<nav class="navbar">
    <div class="nav-left">
        <a href="/" class="logo animate-float">MarsClient</a>
    </div>
    <div class="nav-right">
        <div class="online-badge" id="onlineBadge">
            <span class="online-dot" id="onlineDot"></span>
            آنلاین: <span class="online-number" id="onlineCount">0</span> نفر
        </div>
        <div class="hamburger-wrapper">
            <button class="hamburger" id="hamburgerBtn" onclick="toggleMobileMenu()" aria-label="منو">
                <span></span><span></span><span></span>
            </button>
            <div class="mobile-menu" id="mobileMenu">
                <a href="/">🏠 خانه</a>
                <a href="/shop">🛒 فروشگاه</a>
                <a href="/login">🔑 ورود / ثبت‌نام</a>
                <a href="https://reymit.ir/marsclient" target="_blank" class="support-link">❤️ حمایت</a>
            </div>
        </div>
        <a href="/cart" class="cart-icon" id="cartLink" style="display: none;">🛒 <span id="cartCount">0</span></a>
        <div id="authSection" style="display: flex; gap: 12px;"></div>
    </div>
</nav>

<div id="downloadModal" class="modal">
    <div class="modal-content download-modal">
        <span class="close" onclick="closeDownloadModal()">&times;</span>
        <div class="download-modal-icon">🚀</div>
        <h2 style="color:var(--orange-primary); margin-bottom:5px;">MarsClient Download</h2>
        <p style="color:var(--text-soft); margin-bottom:20px;">کلاینت ماینکرفت نسل بعدی</p>
        
        <div class="download-options">
            <div class="download-option">
                <div class="download-icon">🪟</div>
                <div class="download-name">ویندوز</div>
                <div class="download-version">Windows 10/11</div>
                <button class="download-btn" onclick="showComingSoon('ویندوز')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🐧</div>
                <div class="download-name">لینوکس</div>
                <div class="download-version">Ubuntu / Debian</div>
                <button class="download-btn" onclick="showComingSoon('لینوکس')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🍎</div>
                <div class="download-name">مک</div>
                <div class="download-version">macOS</div>
                <button class="download-btn" onclick="showComingSoon('مک')">به زودی ⏳</button>
            </div>
        </div>
        
        <p style="color:#8899aa; font-size:0.8rem; margin-top:15px;">🔹 نسخه بتا v1.0 - به زودی منتشر می‌شود</p>
    </div>
</div>

<div id="comingSoonModal" class="modal">
    <div class="modal-content" style="max-width:350px;">
        <span class="close" onclick="closeComingSoon()">&times;</span>
        <div style="text-align:center; padding:10px;">
            <div style="font-size:4rem; margin-bottom:10px;">🔧</div>
            <h3 style="color:var(--orange-primary);">در حال ساخت!</h3>
            <p id="comingSoonText" style="color:var(--text-soft); margin:10px 0;">نسخه ویندوز به زودی منتشر می‌شود</p>
            <button onclick="closeComingSoon()" class="btn" style="padding:10px 30px;">متوجه شدم</button>
        </div>
    </div>
</div>

<section class="hero">
    <div class="beta-tag animate-fade-up">🔸 نسخه بتا v1.0 منتشر شد 🔸</div>
    <h1 class="animate-fade-up delay-1">MarsClient</h1>
    <div class="description animate-fade-up delay-2">موتور نسل بعدی ماینکرفت · مهندسی‌شده برای عملکرد فوق‌العاده، تأخیر حداقلی و گیم‌پلی بدون لگ</div>
    <div class="animate-fade-up delay-3" style="display:flex;gap:20px; flex-wrap:wrap; justify-content:center;">
        <button class="btn" onclick="showDownloadModal()">📥 دریافت MarsClient</button>
        <a href="/shop" class="btn btn-outline">🛒 فروشگاه</a>
    </div>
</section>

<section class="section" id="features">
    <h2 class="section-title scroll-animate"><span>چرا MarsClient</span> ؟</h2>
    <div class="features-grid">
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float">⚡</div><h3>عملکرد افراطی</h3><p>رندرینگ بهینه و شبکه فوق سریع برای حداکثر FPS، کاهش تأخیر و گیم‌پلی نرم‌تر حتی روی سیستم‌های ضعیف.</p></div>
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float-reverse">🧩</div><h3>ماژول‌های پیشرفته</h3><p>بیش از ۳۵ ماژول داخلی شامل نمایش کی‌استروک، ToggleSprint و ویرایشگر HUD شخصی‌سازی‌شده.</p></div>
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float">🎨</div><h3>تم نارنجی زنده</h3><p>طراحی مینیمال اما پر انرژی با رنگ‌های نارنجی و سفید، تجربه بصری لذت‌بخش و حرفه‌ای.</p></div>
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float-reverse">🛡️</div><h3>بهینه‌سازی JVM</h3><p>تنظیمات سفارشی ماشین مجاز جاوا، مدیریت حافظه هوشمند و لانچر قدرتمند برای رقابت‌پذیری بالا.</p></div>
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float">🚀</div><h3>لانچر اختصاصی MarsClient</h3><p>لانچر قدرتمند با مدیریت آسان مادها، نسخه‌ها و پروفایل‌های مختلف. رابط کاربری زیبا و سریع با قابلیت آپدیت خودکار.</p></div>
        <div class="feature-card scroll-animate"><div class="feature-icon animate-float-reverse">🎮</div><h3>پشتیبانی از همه نسخه‌ها</h3><p>از نسخه ۱.۷ تا آخرین نسخه ماینکرفت! کاملاً سازگار با لانچرهای معروف و قابلیت اجرای همزمان چند نسخه.</p></div>
    </div>
</section>

<section class="section" id="developers">
    <h2 class="section-title scroll-animate"><span>تیم توسعه‌دهندگان</span> MarsClient</h2>
    <div class="team-grid" id="teamGrid">
        <div style="text-align:center;width:100%;">در حال بارگذاری اطلاعات تیم...</div>
    </div>
</section>

<section class="stats-section">
    <div class="stats-grid">
        <div class="stat-item scroll-animate">
            <div class="stat-number" id="fpsCounter">0</div>
            <div class="stat-label">حداکثر FPS</div>
        </div>
        <div class="stat-item scroll-animate">
            <div class="stat-number" id="ratingCounter">0</div>
            <div class="stat-label">امتیاز کاربران</div>
        </div>
        <div class="stat-item scroll-animate">
            <div class="stat-number" id="modulesCounter">0</div>
            <div class="stat-label">ماژول داخلی</div>
        </div>
    </div>
</section>

<footer>
    <div class="footer-content">
        <div class="footer-stats">
            <div class="footer-stat"><div class="footer-stat-value">۴.۹</div><div class="footer-stat-label">امتیاز کاربران</div></div>
            <div class="footer-stat"><div class="footer-stat-value">۴۰+</div><div class="footer-stat-label">ماژول داخلی</div></div>
        </div>
        <div class="footer-copyright">© ۲۰۲۶ MarsClient — نسل بعدی موتور ماینکرفت</div>
    </div>
</footer>

<div class="faq-widget">
    <button class="faq-button" onclick="toggleFaq()">❓</button>
    <div class="faq-panel" id="faqPanel">
        <div class="faq-header">
            <button id="faqTabBtn" class="faq-tab active">❓ سوالات متداول</button>
            <button id="supportTabBtn" class="faq-tab">📞 پشتیبانی</button>
            <button class="faq-close" onclick="toggleFaq()">✖</button>
        </div>
        <div id="faqContent" class="faq-content"></div>
    </div>
</div>

<script>
// ===== منوی همبرگری =====
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    menu.classList.toggle('active');
    btn.classList.toggle('active');
}
document.addEventListener('click', function(event) {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    if (!menu.contains(event.target) && !btn.contains(event.target)) {
        menu.classList.remove('active');
        btn.classList.remove('active');
    }
});

// ===== مودال دانلود =====
function showDownloadModal() { 
    document.getElementById('downloadModal').style.display='block'; 
}

function closeDownloadModal() { 
    document.getElementById('downloadModal').style.display='none'; 
}

// ===== مودال "به زودی" =====
function showComingSoon(os) {
    const modal = document.getElementById('comingSoonModal');
    const text = document.getElementById('comingSoonText');
    const osNames = {
        'ویندوز': 'ویندوز (Windows 10/11)',
        'لینوکس': 'لینوکس (Ubuntu / Debian)',
        'مک': 'مک (macOS)'
    };
    text.textContent = `نسخه ${osNames[os] || os} به زودی منتشر می‌شود`;
    modal.style.display = 'block';
}

function closeComingSoon() {
    document.getElementById('comingSoonModal').style.display='none';
}

// بستن مودال با کلیک خارج از آن
window.onclick = function(event) {
    const modal1 = document.getElementById('downloadModal');
    const modal2 = document.getElementById('comingSoonModal');
    if (event.target == modal1) modal1.style.display = 'none';
    if (event.target == modal2) modal2.style.display = 'none';
}

// ===== آنلاین =====
let sessionId = localStorage.getItem('marsclient_session');
if (!sessionId) { sessionId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36); localStorage.setItem('marsclient_session', sessionId); }
let onlineCount = 0;

function sendHeartbeat() { 
    fetch('/api/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId}) })
    .then(r=>r.json())
    .then(data=>{ 
        if(data.online_count !== undefined) {
            const oldCount = onlineCount;
            onlineCount = data.online_count;
            document.getElementById('onlineCount').innerText = onlineCount;
            if(onlineCount < oldCount || onlineCount === 0) {
                flashOffline();
            }
        }
    })
    .catch(e=>console.warn); 
}

function flashOffline() {
    const badge = document.getElementById('onlineBadge');
    const dot = document.getElementById('onlineDot');
    badge.classList.add('offline-flash');
    dot.classList.add('offline');
    setTimeout(() => {
        badge.classList.remove('offline-flash');
        dot.classList.remove('offline');
    }, 1200);
}

function sendLeave() { 
    navigator.sendBeacon('/api/leave', JSON.stringify({session_id:sessionId}));
    flashOffline();
}

window.addEventListener('beforeunload', sendLeave);
sendHeartbeat(); 
setInterval(sendHeartbeat, 20000);

window.addEventListener('load', function() {
    const badge = document.getElementById('onlineBadge');
    badge.style.animation = 'onlineFlash 0.8s ease';
    setTimeout(() => {
        badge.style.animation = '';
    }, 1000);
});

async function refreshAuthUI() {
    const res = await fetch('/api/me'); const data = await res.json(); const authDiv = document.getElementById('authSection'); const cartLink = document.getElementById('cartLink');
    if(data.logged_in) { authDiv.innerHTML = `<span style="color:var(--orange-primary); font-weight:600;">${data.username}</span> <button id="logoutBtn" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; border:none; cursor:pointer; font-weight:600;">خروج</button>`; document.getElementById('logoutBtn')?.addEventListener('click', async () => { await fetch('/api/logout', {method:'POST'}); window.location.reload(); }); cartLink.style.display = 'inline-block'; updateCartUI(); }
    else { authDiv.innerHTML = `<a href="/login" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; text-decoration:none; font-weight:600;">ورود</a>`; cartLink.style.display = 'none'; }
}
async function updateCartUI() { const res = await fetch('/api/cart').catch(()=>{}); if(res && res.ok) { const data = await res.json(); document.getElementById('cartCount').innerText = data.item_count || 0; } }
refreshAuthUI();

async function loadTeamMembers() {
    try {
        const res = await fetch('/api/team_members');
        const members = await res.json();
        const container = document.getElementById('teamGrid');
        let html = '';
        members.forEach((member, index) => {
            html += `
                <div class="team-card scroll-animate" style="animation-delay: ${index * 0.1}s">
                    <div class="team-badge">${member.badge}</div>
                    <div class="team-avatar">
                        <img src="${member.avatar}" alt="${member.name}" onerror="this.src='https://ui-avatars.com/api/?name=${member.name}&background=f97316&color=fff&size=120'">
                    </div>
                    <div class="team-name">${member.name}</div>
                    <div class="team-role">${member.role}</div>
                    <div class="team-username">${member.username}</div>
                    <div class="team-status online">
                        <span class="status-dot-online"></span>
                        آنلاین
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
        const teamObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });
        document.querySelectorAll('.team-card').forEach(card => teamObserver.observe(card));
    } catch(e) {
        console.error('خطا در بارگذاری تیم:', e);
        document.getElementById('teamGrid').innerHTML = '<div style="text-align:center;color:red;">خطا در بارگذاری اطلاعات تیم</div>';
    }
}
loadTeamMembers();

function animateCounter(elementId, target, suffix = '') {
    const counter = document.getElementById(elementId);
    if (!counter) return;
    const duration = 2000;
    const startTime = performance.now();
    let current = 0;
    function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 1.5);
        current = Math.floor(eased * target);
        if (target === 4.9) {
            counter.textContent = (current / 10).toFixed(1);
        } else {
            counter.textContent = current.toLocaleString('en-US');
        }
        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            if (target === 4.9) {
                counter.textContent = '4.9';
            } else {
                counter.textContent = target.toLocaleString('en-US') + suffix;
            }
        }
    }
    setTimeout(() => {
        requestAnimationFrame(updateCounter);
    }, 300);
}

const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateCounter('fpsCounter', 3000, '+');
            animateCounter('ratingCounter', 4.9);
            animateCounter('modulesCounter', 40, '+');
            statsObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.3 });
document.querySelectorAll('.stats-section').forEach(el => statsObserver.observe(el));

const observerOptions = { threshold: 0.2, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        } else {
            entry.target.classList.remove('visible');
        }
    });
}, observerOptions);
document.querySelectorAll('.scroll-animate').forEach(el => observer.observe(el));

const faqDataHome = [
    { q: "چگونه MarsClient را نصب کنم؟", a: "فایل نصاب را از دکمه دانلود دریافت کرده و اجرا کنید. مسیر نصب ماینکرفت را انتخاب کنید و پس از اتمام، لانچر را اجرا کنید." },
    { q: "آیا با همه نسخه‌های ماینکرفت سازگار است؟", a: "بله! MarsClient از نسخه ۱.۷ تا آخرین نسخه ماینکرفت را پشتیبانی می‌کند." },
    { q: "لانچر اختصاصی MarsClient چه قابلیت‌هایی دارد؟", a: "مدیریت مادها، دانلود خودکار نسخه‌ها، پشتیبانی از چند پروفایل، آپدیت خودکار و رابط کاربری زیبا." },
    { q: "چگونه FPS را افزایش دهم؟", a: "در تنظیمات گرافیکی کلاینت، گزینه‌های Performance Mode و Smooth FPS را فعال کنید." },
    { q: "آیا کلاینت رایگان است؟", a: "بله، کلاینت اصلی رایگان است. کازمتیک‌های فروشگاه دارای هزینه نمادین هستند." },
    { q: "چگونه ماد اضافه کنم؟", a: "از طریق لانچر اختصاصی MarsClient می‌توانید مادها را به راحتی مدیریت و نصب کنید." },
    { q: "گزارش باگ؟", a: "از طریق تیکت پشتیبانی در وبسایت یا دیسکورد." }
];
let currentTabHome = 'faq';
let supportUserNameHome = '';
let supportUserPhoneHome = '';
let chatHistoryHome = [];

function renderFaqContentHome() {
    const container = document.getElementById('faqContent');
    if (currentTabHome === 'faq') {
        let html = '<ul class="faq-list">';
        faqDataHome.forEach(item => { html += `<li onclick="showAnswerHome(this, '${item.a.replace(/'/g, "\\'")}')">${item.q}</li>`; });
        html += '</ul><div id="faqAnswer" class="faq-answer"></div>';
        container.innerHTML = html;
    } else {
        if (!supportUserNameHome || !supportUserPhoneHome) {
            container.innerHTML = `<div class="support-init"><input type="text" id="supportName" placeholder="نام و نام خانوادگی"><input type="tel" id="supportPhone" placeholder="شماره تماس"><button onclick="startSupportChatHome()">شروع گفتگو</button></div>`;
        } else {
            renderChatHome();
        }
    }
}

function startSupportChatHome() {
    const name = document.getElementById('supportName')?.value.trim();
    const phone = document.getElementById('supportPhone')?.value.trim();
    if (!name || !phone) { alert('لطفاً نام و شماره تماس را وارد کنید'); return; }
    supportUserNameHome = name; supportUserPhoneHome = phone; chatHistoryHome = [];
    setTimeout(() => { addBotMessageHome("سلام! به پشتیبانی MarsClient خوش آمدید. لطفاً مشکل خود را مطرح کنید."); renderChatHome(); }, 500);
    renderFaqContentHome();
}

function renderChatHome() {
    const container = document.getElementById('faqContent');
    let messagesHtml = '<div class="chat-container"><div class="chat-messages" id="chatMessages">';
    chatHistoryHome.forEach(msg => { const time = new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); messagesHtml += `<div class="message ${msg.sender}"><div class="message-bubble">${msg.text}</div><div class="message-time">${time}</div></div>`; });
    messagesHtml += `</div><div class="chat-input-area"><input type="text" id="chatInput" placeholder="پیام خود را بنویسید..."><button onclick="sendMessageHome()">ارسال</button></div></div>`;
    container.innerHTML = messagesHtml;
    const msgDiv = document.getElementById('chatMessages'); if (msgDiv) msgDiv.scrollTop = msgDiv.scrollHeight;
    const input = document.getElementById('chatInput'); if (input) input.focus();
}

function addUserMessageHome(text) { chatHistoryHome.push({ sender: 'user', text: text, timestamp: Date.now() }); renderChatHome(); }
function addBotMessageHome(text) { chatHistoryHome.push({ sender: 'bot', text: text, timestamp: Date.now() }); renderChatHome(); }

function sendMessageHome() {
    const input = document.getElementById('chatInput'); const message = input.value.trim();
    if (!message) return;
    addUserMessageHome(message); input.value = '';
    const lowerMsg = message.toLowerCase();
    let reply = "";
    if (lowerMsg.includes('نصب') || lowerMsg.includes('install')) { reply = "برای نصب MarsClient، فایل نصاب را از دکمه دانلود دریافت کنید. پس از اجرا، مسیر ماینکرفت را انتخاب کنید."; }
    else if (lowerMsg.includes('خرید') || lowerMsg.includes('price') || lowerMsg.includes('قیمت')) { reply = "برای خرید آیتم‌های فروشگاه، ابتدا وارد حساب شوید، سپس محصول را به سبد خرید اضافه کرده و پرداخت را انجام دهید."; }
    else if (lowerMsg.includes('fps') || lowerMsg.includes('کاهش') || lowerMsg.includes('lag')) { reply = "برای افزایش FPS، در تنظیمات گرافیکی Performance Mode را فعال کنید."; }
    else if (lowerMsg.includes('تشکر') || lowerMsg.includes('ممنون')) { reply = "خواهش می‌کنم! خوشحالیم که می‌توانیم کمک کنیم."; }
    else { reply = "درخواست شما ثبت شد. همکاران ما به زودی پاسخ می‌دهند."; }
    setTimeout(() => addBotMessageHome(reply), 800);
}

function showAnswerHome(el, answer) { const answerDiv = document.getElementById('faqAnswer'); if (!answerDiv) return; answerDiv.innerHTML = answer; answerDiv.classList.add('show'); }
function toggleFaq() { const panel = document.getElementById('faqPanel'); panel.classList.toggle('active'); if (panel.classList.contains('active')) { renderFaqContentHome(); const faqTabBtn = document.getElementById('faqTabBtn'); const supportTabBtn = document.getElementById('supportTabBtn'); faqTabBtn.onclick = () => { currentTabHome = 'faq'; renderFaqContentHome(); faqTabBtn.classList.add('active'); supportTabBtn.classList.remove('active'); }; supportTabBtn.onclick = () => { currentTabHome = 'support'; renderFaqContentHome(); supportTabBtn.classList.add('active'); faqTabBtn.classList.remove('active'); }; if (currentTabHome === 'support' && supportUserNameHome && supportUserPhoneHome) { renderChatHome(); } } }
</script>
</body>
</html>"""

# ===================== SHOP_TEMPLATE =====================
SHOP_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>فروشگاه | MarsClient</title><style>{{ styles | safe }}</style></head>
<body>
<nav class="navbar">
    <div class="nav-left">
        <a href="/" class="logo animate-float">MarsClient</a>
    </div>
    <div class="nav-right">
        <div class="online-badge" id="onlineBadge">
            <span class="online-dot" id="onlineDot"></span>
            آنلاین: <span class="online-number" id="onlineCount">0</span> نفر
        </div>
        <div class="hamburger-wrapper">
            <button class="hamburger" id="hamburgerBtn" onclick="toggleMobileMenu()" aria-label="منو">
                <span></span><span></span><span></span>
            </button>
            <div class="mobile-menu" id="mobileMenu">
                <a href="/">🏠 خانه</a>
                <a href="/shop">🛒 فروشگاه</a>
                <a href="/login">🔑 ورود / ثبت‌نام</a>
                <a href="https://reymit.ir/marsclient" target="_blank" class="support-link">❤️ حمایت</a>
            </div>
        </div>
        <a href="/cart" class="cart-icon" id="cartLink" style="display: none;">🛒 <span id="cartCount">0</span></a>
        <div id="authSection" style="display: flex; gap: 12px;"></div>
    </div>
</nav>

<div id="downloadModal" class="modal">
    <div class="modal-content download-modal">
        <span class="close" onclick="closeDownloadModal()">&times;</span>
        <div class="download-modal-icon">🚀</div>
        <h2 style="color:var(--orange-primary); margin-bottom:5px;">MarsClient Download</h2>
        <p style="color:var(--text-soft); margin-bottom:20px;">کلاینت ماینکرفت نسل بعدی</p>
        
        <div class="download-options">
            <div class="download-option">
                <div class="download-icon">🪟</div>
                <div class="download-name">ویندوز</div>
                <div class="download-version">Windows 10/11</div>
                <button class="download-btn" onclick="showComingSoon('ویندوز')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🐧</div>
                <div class="download-name">لینوکس</div>
                <div class="download-version">Ubuntu / Debian</div>
                <button class="download-btn" onclick="showComingSoon('لینوکس')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🍎</div>
                <div class="download-name">مک</div>
                <div class="download-version">macOS</div>
                <button class="download-btn" onclick="showComingSoon('مک')">به زودی ⏳</button>
            </div>
        </div>
        
        <p style="color:#8899aa; font-size:0.8rem; margin-top:15px;">🔹 نسخه بتا v1.0 - به زودی منتشر می‌شود</p>
    </div>
</div>

<div id="comingSoonModal" class="modal">
    <div class="modal-content" style="max-width:350px;">
        <span class="close" onclick="closeComingSoon()">&times;</span>
        <div style="text-align:center; padding:10px;">
            <div style="font-size:4rem; margin-bottom:10px;">🔧</div>
            <h3 style="color:var(--orange-primary);">در حال ساخت!</h3>
            <p id="comingSoonText" style="color:var(--text-soft); margin:10px 0;">نسخه ویندوز به زودی منتشر می‌شود</p>
            <button onclick="closeComingSoon()" class="btn" style="padding:10px 30px;">متوجه شدم</button>
        </div>
    </div>
</div>

<section class="section" style="padding-top: 120px;">
    <div style="text-align:center; margin-bottom:30px;">
        <h1 style="font-size:2.8rem; background:var(--gradient); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:800;">فروشگاه MarsClient</h1>
        <p style="color:var(--text-soft); margin-top:10px;">کازمتیک‌های اختصاصی برای شخصی‌سازی تجربه بازی شما</p>
    </div>
    <div class="category-menu" id="categoryMenu"></div>
    <div id="cosmeticsContainer" class="grid" style="margin-top:30px;">
        <div style="text-align:center;width:100%;">در حال بارگذاری محصولات...</div>
    </div>
</section>

<footer>
    <div class="footer-content">
        <div class="footer-stats">
            <div class="footer-stat"><div class="footer-stat-value">۴.۹</div><div class="footer-stat-label">امتیاز کاربران</div></div>
            <div class="footer-stat"><div class="footer-stat-value">۴۰+</div><div class="footer-stat-label">ماژول داخلی</div></div>
        </div>
        <div class="footer-copyright">© ۲۰۲۶ MarsClient — نسل بعدی موتور ماینکرفت</div>
    </div>
</footer>

<div class="faq-widget">
    <button class="faq-button" onclick="toggleFaq()">❓</button>
    <div class="faq-panel" id="faqPanel">
        <div class="faq-header">
            <button id="faqTabBtn" class="faq-tab active">❓ سوالات متداول</button>
            <button id="supportTabBtn" class="faq-tab">📞 پشتیبانی</button>
            <button class="faq-close" onclick="toggleFaq()">✖</button>
        </div>
        <div id="faqContent" class="faq-content"></div>
    </div>
</div>

<script>
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    menu.classList.toggle('active');
    btn.classList.toggle('active');
}
document.addEventListener('click', function(event) {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    if (!menu.contains(event.target) && !btn.contains(event.target)) {
        menu.classList.remove('active');
        btn.classList.remove('active');
    }
});

// ===== مودال دانلود =====
function showDownloadModal() { 
    document.getElementById('downloadModal').style.display='block'; 
}

function closeDownloadModal() { 
    document.getElementById('downloadModal').style.display='none'; 
}

// ===== مودال "به زودی" =====
function showComingSoon(os) {
    const modal = document.getElementById('comingSoonModal');
    const text = document.getElementById('comingSoonText');
    const osNames = {
        'ویندوز': 'ویندوز (Windows 10/11)',
        'لینوکس': 'لینوکس (Ubuntu / Debian)',
        'مک': 'مک (macOS)'
    };
    text.textContent = `نسخه ${osNames[os] || os} به زودی منتشر می‌شود`;
    modal.style.display = 'block';
}

function closeComingSoon() {
    document.getElementById('comingSoonModal').style.display='none';
}

// بستن مودال با کلیک خارج از آن
window.onclick = function(event) {
    const modal1 = document.getElementById('downloadModal');
    const modal2 = document.getElementById('comingSoonModal');
    if (event.target == modal1) modal1.style.display = 'none';
    if (event.target == modal2) modal2.style.display = 'none';
}

let sessionId = localStorage.getItem('marsclient_session');
if (!sessionId) { sessionId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36); localStorage.setItem('marsclient_session', sessionId); }
let onlineCount = 0;

function sendHeartbeat() { 
    fetch('/api/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId}) })
    .then(r=>r.json())
    .then(data=>{ 
        if(data.online_count !== undefined) {
            const oldCount = onlineCount;
            onlineCount = data.online_count;
            document.getElementById('onlineCount').innerText = onlineCount;
            if(onlineCount < oldCount || onlineCount === 0) {
                flashOffline();
            }
        }
    })
    .catch(e=>console.warn); 
}

function flashOffline() {
    const badge = document.getElementById('onlineBadge');
    const dot = document.getElementById('onlineDot');
    badge.classList.add('offline-flash');
    dot.classList.add('offline');
    setTimeout(() => {
        badge.classList.remove('offline-flash');
        dot.classList.remove('offline');
    }, 1200);
}

function sendLeave() { 
    navigator.sendBeacon('/api/leave', JSON.stringify({session_id:sessionId}));
    flashOffline();
}

window.addEventListener('beforeunload', sendLeave);
sendHeartbeat(); 
setInterval(sendHeartbeat, 20000);

window.addEventListener('load', function() {
    const badge = document.getElementById('onlineBadge');
    badge.style.animation = 'onlineFlash 0.8s ease';
    setTimeout(() => {
        badge.style.animation = '';
    }, 1000);
});

async function refreshAuthUI() {
    const res = await fetch('/api/me'); const data = await res.json(); const authDiv = document.getElementById('authSection'); const cartLink = document.getElementById('cartLink');
    if(data.logged_in) { authDiv.innerHTML = `<span style="color:var(--orange-primary); font-weight:600;">${data.username}</span> <button id="logoutBtn" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; border:none; cursor:pointer; font-weight:600;">خروج</button>`; document.getElementById('logoutBtn')?.addEventListener('click', async () => { await fetch('/api/logout', {method:'POST'}); window.location.reload(); }); cartLink.style.display = 'inline-block'; updateCartUI(); }
    else { authDiv.innerHTML = `<a href="/login" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; text-decoration:none; font-weight:600;">ورود</a>`; cartLink.style.display = 'none'; }
}
async function updateCartUI() { const res = await fetch('/api/cart').catch(()=>{}); if(res && res.ok) { const data = await res.json(); document.getElementById('cartCount').innerText = data.item_count || 0; } }
refreshAuthUI();

function addToCart(item) {
    fetch('/api/cart/add', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(item) })
    .then(r=>{ if(r.status===401) { alert('لطفاً وارد شوید'); window.location.href='/login'; return; } return r.json(); })
    .then(data => { if(data && data.success) { updateCartUI(); alert(`${item.name} به سبد خرید اضافه شد`); } })
    .catch(err=>console.error);
}

let allCosmetics = {};
async function loadCosmetics() {
    try {
        const res = await fetch('/api/cosmetics');
        allCosmetics = await res.json();
        buildCategoryMenu();
        let firstCat = Object.keys(allCosmetics).find(key => allCosmetics[key].length > 0);
        if (firstCat) showCategory(firstCat);
        else document.getElementById('cosmeticsContainer').innerHTML = '<div style="text-align:center;">هیچ محصولی یافت نشد</div>';
    } catch(e) { console.error(e); }
}

function buildCategoryMenu() {
    const menuDiv = document.getElementById('categoryMenu');
    let html = '';
    for (const [key, items] of Object.entries(allCosmetics)) {
        if (items.length === 0) continue;
        html += `<button class="category-btn" data-cat="${key}">${getCategoryPersianName(key)}</button>`;
    }
    menuDiv.innerHTML = html;
    document.querySelectorAll('.category-btn').forEach(btn => btn.addEventListener('click', () => {
        document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        showCategory(btn.dataset.cat);
    }));
}

function getCategoryPersianName(key) {
    const names = { 'pets':'حیوانات خانگی', 'glasses':'عینک', 'hats':'کلاه', 'masks':'ماسک', 'wings':'بال', 'capes':'شنل', 'bag':'کیف', 'necklace':'گردنبند' };
    return names[key] || key;
}

function showCategory(categoryKey) {
    let items = allCosmetics[categoryKey] || [];
    const container = document.getElementById('cosmeticsContainer');
    if (!items.length) { container.innerHTML = '<div style="text-align:center;">هیچ آیتمی در این دسته وجود ندارد</div>'; return; }
    let html = '';
    for (const item of items) {
        let priceFormatted = item.price.toLocaleString();
        let oldPrice = (item.price * 1.5).toLocaleString();
        html += `<div class="cosmetic-card">
            <div class="cosmetic-img"><img src="${item.image}" alt="${item.name}" onerror="this.src='https://placehold.co/200x200/f97316/white?text=🔸'"></div>
            <div class="cosmetic-info">
                <div class="cosmetic-name">${item.name}</div>
                <div class="cosmetic-price"><span class="old-price">${oldPrice} تومان</span> ${priceFormatted} تومان</div>
                <button class="buy-btn" onclick="addToCart({category_key:'${categoryKey}', name:'${item.name.replace(/'/g, "\\'")}', image:'${item.image}', price:${item.price}})">خرید</button>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}
loadCosmetics();

const faqDataShop = [
    { q: "چگونه MarsClient را نصب کنم؟", a: "فایل نصاب را از دکمه دانلود دریافت کرده و اجرا کنید. مسیر نصب ماینکرفت را انتخاب کنید و پس از اتمام، لانچر را اجرا کنید." },
    { q: "آیا با همه نسخه‌های ماینکرفت سازگار است؟", a: "بله! MarsClient از نسخه ۱.۷ تا آخرین نسخه ماینکرفت را پشتیبانی می‌کند." },
    { q: "لانچر اختصاصی MarsClient چه قابلیت‌هایی دارد؟", a: "مدیریت مادها، دانلود خودکار نسخه‌ها، پشتیبانی از چند پروفایل، آپدیت خودکار و رابط کاربری زیبا." },
    { q: "چگونه FPS را افزایش دهم؟", a: "در تنظیمات گرافیکی کلاینت، گزینه‌های Performance Mode و Smooth FPS را فعال کنید." },
    { q: "آیا کلاینت رایگان است؟", a: "بله، کلاینت اصلی رایگان است. کازمتیک‌های فروشگاه دارای هزینه نمادین هستند." }
];
let currentTabShop = 'faq';
let supportUserNameShop = '';
let supportUserPhoneShop = '';
let chatHistoryShop = [];

function renderFaqContentShop() {
    const container = document.getElementById('faqContent');
    if (currentTabShop === 'faq') {
        let html = '<ul class="faq-list">';
        faqDataShop.forEach(item => { html += `<li onclick="showAnswerShop(this, '${item.a.replace(/'/g, "\\'")}')">${item.q}</li>`; });
        html += '</ul><div id="faqAnswer" class="faq-answer"></div>';
        container.innerHTML = html;
    } else {
        if (!supportUserNameShop || !supportUserPhoneShop) {
            container.innerHTML = `<div class="support-init"><input type="text" id="supportName" placeholder="نام و نام خانوادگی"><input type="tel" id="supportPhone" placeholder="شماره تماس"><button onclick="startSupportChatShop()">شروع گفتگو</button></div>`;
        } else {
            renderChatShop();
        }
    }
}

function startSupportChatShop() {
    const name = document.getElementById('supportName')?.value.trim();
    const phone = document.getElementById('supportPhone')?.value.trim();
    if (!name || !phone) { alert('لطفاً نام و شماره تماس را وارد کنید'); return; }
    supportUserNameShop = name; supportUserPhoneShop = phone; chatHistoryShop = [];
    setTimeout(() => { addBotMessageShop("سلام! به پشتیبانی MarsClient خوش آمدید. لطفاً مشکل خود را مطرح کنید."); renderChatShop(); }, 500);
    renderFaqContentShop();
}

function renderChatShop() {
    const container = document.getElementById('faqContent');
    let messagesHtml = '<div class="chat-container"><div class="chat-messages" id="chatMessages">';
    chatHistoryShop.forEach(msg => { const time = new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); messagesHtml += `<div class="message ${msg.sender}"><div class="message-bubble">${msg.text}</div><div class="message-time">${time}</div></div>`; });
    messagesHtml += `</div><div class="chat-input-area"><input type="text" id="chatInput" placeholder="پیام خود را بنویسید..."><button onclick="sendMessageShop()">ارسال</button></div></div>`;
    container.innerHTML = messagesHtml;
    const msgDiv = document.getElementById('chatMessages'); if (msgDiv) msgDiv.scrollTop = msgDiv.scrollHeight;
    const input = document.getElementById('chatInput'); if (input) input.focus();
}

function addUserMessageShop(text) { chatHistoryShop.push({ sender: 'user', text: text, timestamp: Date.now() }); renderChatShop(); }
function addBotMessageShop(text) { chatHistoryShop.push({ sender: 'bot', text: text, timestamp: Date.now() }); renderChatShop(); }

function sendMessageShop() {
    const input = document.getElementById('chatInput'); const message = input.value.trim();
    if (!message) return;
    addUserMessageShop(message); input.value = '';
    const lowerMsg = message.toLowerCase();
    let reply = "";
    if (lowerMsg.includes('نصب') || lowerMsg.includes('install')) { reply = "برای نصب MarsClient، فایل نصاب را از دکمه دانلود دریافت کنید. پس از اجرا، مسیر ماینکرفت را انتخاب کنید."; }
    else if (lowerMsg.includes('خرید') || lowerMsg.includes('price') || lowerMsg.includes('قیمت')) { reply = "برای خرید آیتم‌های فروشگاه، ابتدا وارد حساب شوید، سپس محصول را به سبد خرید اضافه کرده و پرداخت را انجام دهید."; }
    else if (lowerMsg.includes('fps') || lowerMsg.includes('کاهش') || lowerMsg.includes('lag')) { reply = "برای افزایش FPS، در تنظیمات گرافیکی Performance Mode را فعال کنید."; }
    else if (lowerMsg.includes('تشکر') || lowerMsg.includes('ممنون')) { reply = "خواهش می‌کنم! خوشحالیم که می‌توانیم کمک کنیم."; }
    else { reply = "درخواست شما ثبت شد. همکاران ما به زودی پاسخ می‌دهند."; }
    setTimeout(() => addBotMessageShop(reply), 800);
}

function showAnswerShop(el, answer) { const answerDiv = document.getElementById('faqAnswer'); if (!answerDiv) return; answerDiv.innerHTML = answer; answerDiv.classList.add('show'); }
function toggleFaq() { const panel = document.getElementById('faqPanel'); panel.classList.toggle('active'); if (panel.classList.contains('active')) { renderFaqContentShop(); const faqTabBtn = document.getElementById('faqTabBtn'); const supportTabBtn = document.getElementById('supportTabBtn'); faqTabBtn.onclick = () => { currentTabShop = 'faq'; renderFaqContentShop(); faqTabBtn.classList.add('active'); supportTabBtn.classList.remove('active'); }; supportTabBtn.onclick = () => { currentTabShop = 'support'; renderFaqContentShop(); supportTabBtn.classList.add('active'); faqTabBtn.classList.remove('active'); }; if (currentTabShop === 'support' && supportUserNameShop && supportUserPhoneShop) { renderChatShop(); } } }
</script>
</body>
</html>"""

# ===================== CART_TEMPLATE =====================
CART_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سبد خرید | MarsClient</title><style>{{ styles | safe }}</style></head>
<body>
<nav class="navbar">
    <div class="nav-left">
        <a href="/" class="logo animate-float">MarsClient</a>
    </div>
    <div class="nav-right">
        <div class="online-badge" id="onlineBadge">
            <span class="online-dot" id="onlineDot"></span>
            آنلاین: <span class="online-number" id="onlineCount">0</span> نفر
        </div>
        <div class="hamburger-wrapper">
            <button class="hamburger" id="hamburgerBtn" onclick="toggleMobileMenu()" aria-label="منو">
                <span></span><span></span><span></span>
            </button>
            <div class="mobile-menu" id="mobileMenu">
                <a href="/">🏠 خانه</a>
                <a href="/shop">🛒 فروشگاه</a>
                <a href="/login">🔑 ورود / ثبت‌نام</a>
                <a href="https://reymit.ir/marsclient" target="_blank" class="support-link">❤️ حمایت</a>
            </div>
        </div>
        <a href="/cart" class="cart-icon">🛒 <span id="cartCount">0</span></a>
        <div id="authSection" style="display: flex; gap: 12px;"></div>
    </div>
</nav>

<div id="downloadModal" class="modal">
    <div class="modal-content download-modal">
        <span class="close" onclick="closeDownloadModal()">&times;</span>
        <div class="download-modal-icon">🚀</div>
        <h2 style="color:var(--orange-primary); margin-bottom:5px;">MarsClient Download</h2>
        <p style="color:var(--text-soft); margin-bottom:20px;">کلاینت ماینکرفت نسل بعدی</p>
        
        <div class="download-options">
            <div class="download-option">
                <div class="download-icon">🪟</div>
                <div class="download-name">ویندوز</div>
                <div class="download-version">Windows 10/11</div>
                <button class="download-btn" onclick="showComingSoon('ویندوز')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🐧</div>
                <div class="download-name">لینوکس</div>
                <div class="download-version">Ubuntu / Debian</div>
                <button class="download-btn" onclick="showComingSoon('لینوکس')">به زودی ⏳</button>
            </div>
            
            <div class="download-option">
                <div class="download-icon">🍎</div>
                <div class="download-name">مک</div>
                <div class="download-version">macOS</div>
                <button class="download-btn" onclick="showComingSoon('مک')">به زودی ⏳</button>
            </div>
        </div>
        
        <p style="color:#8899aa; font-size:0.8rem; margin-top:15px;">🔹 نسخه بتا v1.0 - به زودی منتشر می‌شود</p>
    </div>
</div>

<div id="comingSoonModal" class="modal">
    <div class="modal-content" style="max-width:350px;">
        <span class="close" onclick="closeComingSoon()">&times;</span>
        <div style="text-align:center; padding:10px;">
            <div style="font-size:4rem; margin-bottom:10px;">🔧</div>
            <h3 style="color:var(--orange-primary);">در حال ساخت!</h3>
            <p id="comingSoonText" style="color:var(--text-soft); margin:10px 0;">نسخه ویندوز به زودی منتشر می‌شود</p>
            <button onclick="closeComingSoon()" class="btn" style="padding:10px 30px;">متوجه شدم</button>
        </div>
    </div>
</div>

<section class="section" style="padding-top: 120px;">
    <div style="text-align:center; margin-bottom:30px;"><h1 style="font-size:2.8rem; background:var(--gradient); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:800;">سبد خرید</h1></div>
    <div id="cartItemsContainer" style="max-width:800px; margin:0 auto;"></div>
    <div id="cartTotal" style="text-align:center; margin-top:30px; font-size:1.3rem; font-weight:700;"></div>
</section>

<footer>
    <div class="footer-content">
        <div class="footer-stats">
            <div class="footer-stat"><div class="footer-stat-value">۴.۹</div><div class="footer-stat-label">امتیاز کاربران</div></div>
            <div class="footer-stat"><div class="footer-stat-value">۴۰+</div><div class="footer-stat-label">ماژول داخلی</div></div>
        </div>
        <div class="footer-copyright">© ۲۰۲۶ MarsClient — نسل بعدی موتور ماینکرفت</div>
    </div>
</footer>

<script>
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    menu.classList.toggle('active');
    btn.classList.toggle('active');
}
document.addEventListener('click', function(event) {
    const menu = document.getElementById('mobileMenu');
    const btn = document.getElementById('hamburgerBtn');
    if (!menu.contains(event.target) && !btn.contains(event.target)) {
        menu.classList.remove('active');
        btn.classList.remove('active');
    }
});

// ===== مودال دانلود =====
function showDownloadModal() { 
    document.getElementById('downloadModal').style.display='block'; 
}

function closeDownloadModal() { 
    document.getElementById('downloadModal').style.display='none'; 
}

// ===== مودال "به زودی" =====
function showComingSoon(os) {
    const modal = document.getElementById('comingSoonModal');
    const text = document.getElementById('comingSoonText');
    const osNames = {
        'ویندوز': 'ویندوز (Windows 10/11)',
        'لینوکس': 'لینوکس (Ubuntu / Debian)',
        'مک': 'مک (macOS)'
    };
    text.textContent = `نسخه ${osNames[os] || os} به زودی منتشر می‌شود`;
    modal.style.display = 'block';
}

function closeComingSoon() {
    document.getElementById('comingSoonModal').style.display='none';
}

// بستن مودال با کلیک خارج از آن
window.onclick = function(event) {
    const modal1 = document.getElementById('downloadModal');
    const modal2 = document.getElementById('comingSoonModal');
    if (event.target == modal1) modal1.style.display = 'none';
    if (event.target == modal2) modal2.style.display = 'none';
}

let sessionId = localStorage.getItem('marsclient_session');
if (!sessionId) { sessionId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36); localStorage.setItem('marsclient_session', sessionId); }
let onlineCount = 0;

function sendHeartbeat() { 
    fetch('/api/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId}) })
    .then(r=>r.json())
    .then(data=>{ 
        if(data.online_count !== undefined) {
            const oldCount = onlineCount;
            onlineCount = data.online_count;
            document.getElementById('onlineCount').innerText = onlineCount;
            if(onlineCount < oldCount || onlineCount === 0) {
                flashOffline();
            }
        }
    })
    .catch(e=>console.warn); 
}

function flashOffline() {
    const badge = document.getElementById('onlineBadge');
    const dot = document.getElementById('onlineDot');
    badge.classList.add('offline-flash');
    dot.classList.add('offline');
    setTimeout(() => {
        badge.classList.remove('offline-flash');
        dot.classList.remove('offline');
    }, 1200);
}

function sendLeave() { 
    navigator.sendBeacon('/api/leave', JSON.stringify({session_id:sessionId}));
    flashOffline();
}

window.addEventListener('beforeunload', sendLeave);
sendHeartbeat(); 
setInterval(sendHeartbeat, 20000);

window.addEventListener('load', function() {
    const badge = document.getElementById('onlineBadge');
    badge.style.animation = 'onlineFlash 0.8s ease';
    setTimeout(() => {
        badge.style.animation = '';
    }, 1000);
});

let cartData = { items: [], total: 0 };
async function loadCart() { 
    const res = await fetch('/api/cart'); 
    if(res.status === 401) { window.location.href = '/login?next=/cart'; return; } 
    const data = await res.json(); 
    cartData = data; 
    renderCart(); 
    document.getElementById('cartCount').innerText = data.item_count || 0; 
}
function renderCart() { 
    const container = document.getElementById('cartItemsContainer'); 
    const totalDiv = document.getElementById('cartTotal'); 
    if (!cartData.items.length) { 
        container.innerHTML = '<div style="text-align:center; padding:40px;">سبد خرید شما خالی است. <a href="/shop" style="color:var(--orange-primary);">بازگشت به فروشگاه</a></div>'; 
        totalDiv.innerHTML = ''; 
        return; 
    } 
    let html = '<div style="display:flex; flex-direction:column; gap:20px;">'; 
    for (let item of cartData.items) { 
        html += `<div style="display:flex; align-items:center; gap:20px; background:var(--white-pure); padding:18px; border-radius:24px; border:1px solid var(--orange-light); box-shadow:var(--shadow-sm);">
            <img src="${item.image}" style="width:70px; height:70px; object-fit:contain; border-radius:16px;">
            <div style="flex:1;"><div><strong style="font-size:1.1rem;">${item.name}</strong></div><div style="color:var(--orange-primary); font-weight:700;">${item.price.toLocaleString()} تومان</div></div>
            <div>
                <button onclick="updateQuantity('${item.id}', ${item.quantity-1})" style="background:var(--orange-light); border:1px solid var(--orange-light); padding:6px 14px; border-radius:50px; cursor:pointer; font-weight:700;">-</button>
                <span style="margin:0 12px; font-weight:700;">${item.quantity}</span>
                <button onclick="updateQuantity('${item.id}', ${item.quantity+1})" style="background:var(--orange-light); border:1px solid var(--orange-light); padding:6px 14px; border-radius:50px; cursor:pointer; font-weight:700;">+</button>
                <button onclick="removeItem('${item.id}')" style="background:var(--danger); border:none; padding:6px 14px; border-radius:50px; color:white; margin-left:12px; cursor:pointer;">حذف</button>
            </div>
        </div>`; 
    } 
    html += '</div>'; 
    container.innerHTML = html; 
    totalDiv.innerHTML = `مجموع سبد خرید: <span style="color:var(--orange-primary); font-size:1.8rem;">${cartData.total.toLocaleString()}</span> تومان`; 
}
async function updateQuantity(itemId, newQty) { 
    if (newQty < 1) { await removeItem(itemId); return; } 
    await fetch('/api/cart/update', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ item_id: itemId, quantity: newQty }) }); 
    loadCart(); 
}
async function removeItem(itemId) { 
    await fetch('/api/cart/remove', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ item_id: itemId }) }); 
    loadCart(); 
}
async function refreshAuthUI() { 
    const res = await fetch('/api/me'); const data = await res.json(); const authDiv = document.getElementById('authSection'); 
    if(data.logged_in) { authDiv.innerHTML = `<span style="color:var(--orange-primary); font-weight:600;">${data.username}</span> <button id="logoutBtn" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; border:none; cursor:pointer; font-weight:600;">خروج</button>`; document.getElementById('logoutBtn')?.addEventListener('click', async () => { await fetch('/api/logout', {method:'POST'}); window.location.href = '/'; }); } 
    else { authDiv.innerHTML = `<a href="/login" style="background:var(--orange-light); color:var(--orange-dark); padding:4px 12px; border-radius:40px; text-decoration:none; font-weight:600;">ورود</a>`; } 
}
refreshAuthUI(); 
loadCart();
</script>
</body>
</html>"""

# Routes
@app.route('/')
def home():
    return render_template_string(HOME_TEMPLATE, styles=STYLES)

@app.route('/shop')
def shop():
    return render_template_string(SHOP_TEMPLATE, styles=STYLES)

@app.route('/cart')
@login_required
def cart():
    return render_template_string(CART_TEMPLATE, styles=STYLES)

@app.route('/api/download', methods=['POST'])
def api_download():
    return jsonify({'success': True, 'message': 'در حال ساخت'})

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=8000)

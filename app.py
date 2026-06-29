import os
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pizza.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# =========================
# Models
# =========================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(200))
    address = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pizza_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200))
    promo_code = db.Column(db.String(50))
    discount = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='قيد التحضير')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

PROMO_CODES = {'PIZZA10': 10, 'WELCOME20': 20, 'SAVE15': 15}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_globals():
    count = 0
    if current_user.is_authenticated:
        count = CartItem.query.filter_by(user_id=current_user.id).count()
    return dict(cart_count=count, now=datetime.now().strftime('%A, %d %B %Y'))

# =========================
# Public
# =========================

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/menu')
def menu():
    return render_template("menu.html")

@app.route('/chatbot')
def chatbot():
    return render_template("chatbot.html")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        import google.generativeai as genai
        data = request.get_json()
        messages = data.get('messages', [])

        SYSTEM_PROMPT = """
You are Chef Marco 👨‍🍳, the official AI pizza expert of Smart Pizza — a premium pizza restaurant in Cairo, Egypt.

## Identity & Role
- Name: Chef Marco
- Role: Head Pizza Chef & Customer Assistant at Smart Pizza
- Background: Trained in Naples, Italy for 15 years before founding Smart Pizza Cairo
- Personality: Warm, professional, passionate about pizza, knowledgeable

## Language Rules (CRITICAL)
- DEFAULT language is ENGLISH — always start and respond in English
- ONLY switch to Arabic if the user writes in Arabic
- If the user writes in Arabic, respond fully in Arabic
- If the user writes in English or any other language, respond in English
- Never mix languages unless the user does first

## Smart Pizza Menu
- 🍅 Margherita Pizza — 105 EGP | Tomato sauce, fresh mozzarella, fresh basil
- 🌶️ Pepperoni Pizza — 115 EGP | Spicy pepperoni, mozzarella, tomato sauce
- 🥦 Veggie Supreme — 100 EGP | Mushrooms, olives, bell peppers, onions, tomatoes
- 🍗 BBQ Chicken Pizza — 110 EGP | Grilled chicken, smoky BBQ sauce, red onions, cheese
- 🧀 Four Cheese Pizza — 100 EGP | Mozzarella, cheddar, parmesan, blue cheese
- 🦐 Seafood Pizza — 120 EGP | Shrimp, calamari, garlic cream sauce, mozzarella

## Promo Codes
- PIZZA10 → 10% off your order
- WELCOME20 → 20% off (new customers)
- SAVE15 → 15% off

## What You Can Help With
1. Smart Pizza menu, prices, and personalized recommendations
2. Pizza history — from ancient Naples to modern styles (NY, Roman, Detroit, etc.)
3. How to make pizza at home — dough recipes, sauce tips, baking techniques
4. Pizza ingredients — what makes each topping special, cheese types, sauce varieties
5. Dietary info — vegetarian options, cheese alternatives
6. How to order — add to cart, checkout, delivery info for Cairo
7. Pairing suggestions — drinks and sides that go well with each pizza

## Conversation Style
- Be professional yet warm and conversational
- Use emojis naturally (1-2 per message max)
- Give concise but complete answers
- Always end with a helpful question or call to action
- If asked about non-food topics: "I'm Chef Marco — a pizza specialist! 🍕 I can only help with pizza and food-related questions. What pizza can I help you with today?"
"""

        genai.configure(api_key="")
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)

        history = []
        for m in messages[:-1]:
            history.append({
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [m["content"]]
            })

        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(messages[-1]["content"])
        return {"reply": response.text}

    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        password = request.form.get('password', '')

        if not all([full_name, email, phone, address, password]):
            flash("All fields are required.", "error")
            return redirect(url_for('register'))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "error")
            return redirect(url_for('register'))

        db.session.add(User(
            full_name=full_name, email=email, phone=phone,
            password=generate_password_hash(password), address=address
        ))
        db.session.commit()
        flash("Account created successfully! Please login.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# =========================
# Profile
# =========================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("profile.html", orders=orders)

# =========================
# Cart
# =========================

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    pizza_name = request.form.get('pizza_name')
    price = request.form.get('price', type=float)
    if not pizza_name or price is None:
        flash("Something went wrong.", "error")
        return redirect(url_for('menu'))
    existing = CartItem.query.filter_by(user_id=current_user.id, pizza_name=pizza_name).first()
    if existing:
        existing.quantity += 1
    else:
        db.session.add(CartItem(user_id=current_user.id, pizza_name=pizza_name, price=price))
    db.session.commit()
    flash(f"{pizza_name} added to cart!", "success")
    return redirect(url_for('menu'))

@app.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum(i.price * i.quantity for i in items)
    discount_pct = session.get('discount', 0)
    promo_code = session.get('promo_code', '')
    discount_amount = subtotal * discount_pct / 100
    total = subtotal - discount_amount
    return render_template("cart.html", items=items, subtotal=subtotal,
                           discount_amount=discount_amount, total=total,
                           promo_code=promo_code, discount_pct=discount_pct)

@app.route('/update_cart/<int:item_id>/<action>')
@login_required
def update_cart(item_id, action):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        return redirect(url_for('cart'))
    if action == 'increase':
        item.quantity += 1
    elif action == 'decrease':
        if item.quantity > 1:
            item.quantity -= 1
        else:
            db.session.delete(item)
    elif action == 'remove':
        db.session.delete(item)
    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/apply_promo', methods=['POST'])
@login_required
def apply_promo():
    code = request.form.get('promo_code', '').strip().upper()
    if code in PROMO_CODES:
        session['promo_code'] = code
        session['discount'] = PROMO_CODES[code]
        flash(f"Promo code applied! {PROMO_CODES[code]}% discount.", "success")
    else:
        flash("Invalid promo code.", "error")
    return redirect(url_for('cart'))

# =========================
# Checkout & Orders
# =========================

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for('cart'))
    address = request.form.get('address', current_user.address).strip()
    promo_code = session.get('promo_code', '')
    discount_pct = session.get('discount', 0)
    subtotal = sum(i.price * i.quantity for i in items)
    discount_amount = subtotal * discount_pct / 100
    total = round(subtotal - discount_amount, 2)
    items_summary = ', '.join([f"{i.pizza_name} x{i.quantity}" for i in items])
    order = Order(user_id=current_user.id, items=items_summary, total=total,
                  address=address, promo_code=promo_code, discount=discount_amount)
    db.session.add(order)
    for item in items:
        db.session.delete(item)
    session.pop('promo_code', None)
    session.pop('discount', None)
    db.session.commit()
    flash(f"Order placed successfully! Order #{order.id}", "success")
    return redirect(url_for('order_status', order_id=order.id))

@app.route('/order/<int:order_id>')
@login_required
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('home'))
    return render_template("order_status.html", order=order)

# =========================
# Admin
# =========================

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for('home'))

    orders = Order.query.order_by(Order.created_at.desc()).all()
    users_count = User.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    avg_order = (total_revenue / len(orders)) if orders else 0

    # Status counts
    status_counts = defaultdict(int)
    for o in orders:
        status_counts[o.status] += 1

    # Revenue by pizza type
    pizza_revenue = defaultdict(float)
    for o in orders:
        for part in o.items.split(','):
            part = part.strip()
            if ' x' in part:
                name, qty_str = part.rsplit(' x', 1)
                try:
                    qty = int(qty_str)
                    # find price from a cart or estimate from known prices
                    prices = {
                        'Margherita Pizza': 105, 'Pepperoni Pizza': 115,
                        'Veggie Supreme': 100, 'BBQ Chicken Pizza': 110,
                        'Four Cheese Pizza': 100, 'Seafood Pizza': 120
                    }
                    pizza_revenue[name.strip()] += prices.get(name.strip(), 100) * qty
                except:
                    pass

    # Daily orders (last 7 days)
    daily_orders = defaultdict(int)
    for o in orders:
        day = o.created_at.strftime('%d %b')
        daily_orders[day] += 1

    return render_template("admin.html",
        orders=orders,
        users_count=users_count,
        total_revenue=total_revenue,
        avg_order=avg_order,
        status_counts=dict(status_counts),
        pizza_revenue=dict(pizza_revenue),
        daily_orders=dict(daily_orders)
    )

@app.route('/admin/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status in ['قيد التحضير', 'في الطريق', 'تم التوصيل', 'ملغي']:
        order.status = new_status
        db.session.commit()
        flash(f"Order #{order_id} updated.", "success")
    return redirect(url_for('admin'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@pizza.com').first():
            db.session.add(User(
                full_name='Admin', email='admin@pizza.com', phone='01000000000',
                password=generate_password_hash('admin123'), address='HQ', is_admin=True
            ))
            db.session.commit()
            print("Admin created: admin@pizza.com / admin123")
    app.run(debug=os.environ.get('DEBUG', 'false').lower() == 'true')

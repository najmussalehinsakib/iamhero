import os
import time
import sqlite3
import threading
import telebot
from telebot import types
from selenium import webdriver
from selenium.webdriver.common.by import By

# --- ১. হোস্টিং সার্ভার এনভায়রনমেন্ট ভ্যারিয়েবল কনফিগারেশন ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

bot = telebot.TeleBot(BOT_TOKEN)
DB_NAME = "ivasms_bot.db"

# --- ২. ডাটাবেজ ইনিশিয়ালাইজেশন ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS numbers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, phone_number TEXT UNIQUE, country TEXT, service TEXT, price REAL, status TEXT DEFAULT 'available')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, phone_number TEXT, country TEXT, service TEXT, price REAL, otp_code TEXT DEFAULT 'WAITING', status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

init_db()

automation_running = False
automation_thread = None
ivasms_config = {"cookie_or_session": "None Set", "target_xpath": ".latest-message-box", "refresh_interval": 10}
user_states = {}

# ---------------- KEYBOARDS ----------------
def get_user_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📱 GET NUMBER"), types.KeyboardButton("📊 TRAFFIC SERVER"))
    markup.add(types.KeyboardButton("👤 PROFILE & WALLET"), types.KeyboardButton("🏆 LEADERBOARD"))
    markup.add(types.KeyboardButton("🎧 SUPPORT & HELP"), types.KeyboardButton("🔐 2FA ONLINE"))
    return markup

def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔴 MAINTENANCE: OFF", callback_data="admin_maintenance"),
               types.InlineKeyboardButton("➕ ADD NEW NUMBER", callback_data="admin_add_number"))
    markup.add(types.InlineKeyboardButton("💰 ADD USER BALANCE", callback_data="admin_add_balance"),
               types.InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("📥 EXPORT ALL DATA", callback_data="admin_export"),
               types.InlineKeyboardButton("🤖 IVASMS DASHBOARD", callback_data="ivasms_dashboard"))
    return markup

def get_ivasms_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    status_text = "🟢 STOP AUTOMATION" if automation_running else "🔴 START AUTOMATION"
    markup.add(types.InlineKeyboardButton(status_text, callback_data="toggle_script"),
               types.InlineKeyboardButton("📝 SET COOKIE / PROFILE", callback_data="set_cookie"),
               types.InlineKeyboardButton("🎯 SET TARGET XPATH", callback_data="set_xpath"),
               types.InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="back_to_admin"))
    return markup

# ---------------- IVASMS AUTOMATION ENGINE ----------------
def ivasms_scraping_loop():
    global automation_running
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://example-ivasms.com/dashboard")
        last_otp = ""
        while automation_running:
            try:
                element = driver.find_element(By.XPATH, ivasms_config["target_xpath"])
                current_otp = element.text
                if current_otp and current_otp != last_otp:
                    last_otp = current_otp
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT order_id, user_id, phone_number FROM orders WHERE status='pending' ORDER BY order_id DESC LIMIT 1")
                    pending_order = cursor.fetchone()
                    if pending_order:
                        order_id, user_id, phone_number = pending_order
                        cursor.execute("UPDATE orders SET otp_code=?, status='completed' WHERE order_id=?", (current_otp, order_id))
                        cursor.execute("UPDATE numbers SET status='used' WHERE phone_number=?", (phone_number,))
                        conn.commit()
                        bot.send_message(user_id, f"✅ **YOUR OTP CODE RECEIVED!**\n\n📱 Number: `{phone_number}`\n💬 Code: `{current_otp}`", parse_mode="Markdown")
                        bot.send_message(ADMIN_ID, f"🔔 OTP Forwarded to User {user_id} for number {phone_number}")
                    conn.close()
            except:
                pass
            time.sleep(ivasms_config["refresh_interval"])
            driver.refresh()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Automation Stopped: {str(e)}")
    finally:
        automation_running = False

# ---------------- BOT HANDLERS ----------------
@bot.message_handler(commands=['start'])
def start_command(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "👋 Welcome to NHBD NUMBER BOT!\nUse the menu below to navigate.", reply_markup=get_user_keyboard())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM numbers WHERE status='available'")
        avail = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
        otps = cursor.fetchone()[0]
        conn.close()
        metrics = f"📊 **LIVE BOT METRICS:**\n\n📦 Available Numbers: `{avail}`\n🔏 Total Successful OTPs: `{otps}`"
        bot.send_message(message.chat.id, metrics, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") or call.data in ["ivasms_dashboard", "toggle_script", "set_cookie", "set_xpath", "back_to_admin"])
def handle_admin_callbacks(call):
    global automation_running, automation_thread
    if call.from_user.id != ADMIN_ID: return
    
    if call.data == "admin_add_number":
        msg = bot.send_message(call.message.chat.id, "📝 নতুন নাম্বার এই ফরম্যাটে দিন:\n`Number,Country,Service,Price`\n\nউদাহরণ:\n`+8801700000000,BANGLADESH,FACEBOOK,25`")
        bot.register_next_step_handler(msg, process_add_number)
    elif call.data == "admin_add_balance":
        msg = bot.send_message(call.message.chat.id, "💰 ব্যালেন্স অ্যাড করতে দিন:\n`User_ID,Amount`\n\nউদাহরণ:\n`123456789,100`")
        bot.register_next_step_handler(msg, process_add_balance)
    elif call.data == "ivasms_dashboard":
        status = "RUNNING 🟢" if automation_running else "STOPPED 🔴"
        dashboard_msg = f"🤖 **IVASMS SCRIPT CONTROL**\n----------------------------------------\n📈 Status: {status}\n🎯 Target XPath: `{ivasms_config['target_xpath']}`\n⏱️ Interval: {ivasms_config['refresh_interval']}s\n----------------------------------------"
        bot.edit_message_text(dashboard_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_ivasms_keyboard())
    elif call.data == "toggle_script":
        if not automation_running:
            automation_running = True
            automation_thread = threading.Thread(target=ivasms_scraping_loop)
            automation_thread.daemon = True
            automation_thread.start()
        else:
            automation_running = False
        handle_admin_callbacks(types.CallbackQuery(call.id, call.from_user, call.message, "ivasms_dashboard", call.chat_instance))
    elif call.data == "back_to_admin":
        admin_command(call.message)

def process_add_number(message):
    try:
        parts = message.text.split(",")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO numbers (phone_number, country, service, price) VALUES (?, ?, ?, ?)", (parts[0].strip(), parts[1].strip().upper(), parts[2].strip().upper(), float(parts[3].strip())))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ নাম্বার স্টকে যোগ হয়েছে!")
    except:
        bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট!")

def process_add_balance(message):
    try:
        parts = message.text.split(",")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(parts[1].strip()), int(parts[0].strip())))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ ব্যালেন্স সফলভাবে যোগ হয়েছে!")
    except:
        bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট!")

# ---------------- USER WORKFLOW (COUNTRY -> SERVICE -> NUMBER) ----------------
@bot.message_handler(func=lambda message: True)
def handle_user_text(message):
    if message.text == "📱 GET NUMBER":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🇧🇩 BANGLADESH", callback_data="country_BANGLADESH"),
                   types.InlineKeyboardButton("🇮🇳 INDIA", callback_data="country_INDIA"),
                   types.InlineKeyboardButton("🇺🇸 USA", callback_data="country_USA"))
        bot.send_message(message.chat.id, "⬇️ SELECT COUNTRY:", reply_markup=markup)
    elif message.text == "👤 PROFILE & WALLET":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
        bal = cursor.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"👤 **PROFILE INFO**\n\n🆔 User ID: `{message.from_user.id}`\n💰 Balance: `{bal:.2f} BDT`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def handle_country_select(call):
    country = call.data.replace("country_", "")
    user_states[call.from_user.id] = {"country": country}
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔵 FACEBOOK", callback_data="service_FACEBOOK"),
               types.InlineKeyboardButton("🟣 INSTAGRAM", callback_data="service_INSTAGRAM"),
               types.InlineKeyboardButton("🟢 WHATSAPP", callback_data="service_WHATSAPP"))
    bot.edit_message_text(f"🌍 Country: **{country}**\n\n⬇️ SELECT SERVICE:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def handle_service_select(call):
    service = call.data.replace("service_", "")
    user_data = user_states.get(call.from_user.id)
    if not user_data: return

    country = user_data["country"]
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
    user_balance = cursor.fetchone()[0]
    
    cursor.execute("SELECT id, phone_number, price FROM numbers WHERE country=? AND service=? AND status='available' LIMIT 1", (country, service))
    num_data = cursor.fetchone()
    
    if num_data:
        num_id, phone, price = num_data
        if user_balance >= price:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (price, call.from_user.id))
            cursor.execute("UPDATE numbers SET status='active' WHERE id=?", (num_id,))
            cursor.execute("INSERT INTO orders (user_id, phone_number, country, service, price) VALUES (?, ?, ?, ?, ?)", (call.from_user.id, phone, country, service, price))
            conn.commit()
            bot.edit_message_text(f"📱 **NUMBER READY!**\n\n🌍 Country: `{country}`\n🛠 Service: `{service}`\n📞 Number: `{phone}`\n💰 Cost: `{price} BDT`\n\nনাম্বারটি ব্যবহার করে ওটিপি রিকোয়েস্ট পাঠান। ওটিপি আসা মাত্র এখানে চলে আসবে। ⏳", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text(f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! নাম্বারটির মূল্য `{price} BDT`। আপনার বর্তমান ব্যালেন্স `{user_balance} BDT`।", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text(f"❌ দুঃখিত, এই মুহূর্তে **{country}** এর **{service}** সার্ভিসের কোনো নাম্বার স্টকে নেই।", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    conn.close()

if __name__ == "__main__":
    print("[+] NHBD BOT IS FULLY OPERATIONAL...")
    bot.infinity_polling()
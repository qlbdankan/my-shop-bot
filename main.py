"""
ربات فروشگاه اکانت پرمیوم - نسخه با پرداخت
کارت به کارت ایرانی + استارز تلگرام + شارژ دستی ادمین

نصب:
    pip install python-telegram-bot
اجرا:
    python bunny_shop_bot.py
"""

import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, MessageEntity
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
)

# ================= تنظیمات - حتماً عوض کن =================
TOKEN = os.environ.get("TOKEN", "توکن_ربات_اینجا")
ADMIN_ID = 1068451122  # آیدی عددی خودت از @userinfobot
SUPPORT_USERNAME = "PackageCom_Admin"  # بدون @
CURRENCY = "تومان"

# --- کارت به کارت ---
CARD_NUMBER = "6037-9911-1234-5678"  # شماره کارت خودت
CARD_HOLDER = "نام صاحب کارت"  # به نام کی؟

# --- استارز ---
# هر 1 استارز = چند تومان؟ این نرخ را خودت تنظیم کن
# مثال: 1 استارز = 2000 تومان
STAR_TO_TOMAN = 2000

# --- آیکون‌های پرمیوم ---
# آیدی ایموجی پرمیومی که خودت فرستادی: 5206607081334906820
# برای آیکون‌های مختلف، ایموجی پرمیوم مختلف بفرست به ربات،
# آیدی‌ش را بگیر و اینجا جایگزین کن. فعلاً همه از همین یکی استفاده می‌کنند.
PREMIUM_ICONS = {
    "shop": "5406683434124859552",
    "wallet": "6325416826100519483",
    "buy": "5440841102871517055",
    "profile": "5461117441612462242",
    "support": "5958416857114350105",
    "orders": "5282843764451195532",
    "star": "5406683434124859552",
}

DEFAULT_PRODUCTS = [
    (1, "Spotify Premium - 3 Months", 350000, "اکانت اسپاتیفای پرمیوم ۳ ماهه - تحویل آنی"),
    (2, "CapCut Pro - 1 Year", 550000, "کپ‌کات پرو ۱ ساله"),
    (3, "ChatGPT Plus - 1 Month", 1200000, "چت‌جی‌پی‌تی پلاس ۱ ماهه"),
    (4, "Gemini Plus - 12 Months", 450000, "جمینای پلاس ۱۲ ماهه"),
    (5, "GitHub Student - 2 Years", 850000, "گیت‌هاب استیودنت ۲ ساله"),
    (6, "Windows 10/11 Pro Key", 250000, "لایسنس ویندوز پرو"),
    (7, "Canva Pro - 1 Month", 180000, "کانوا پرو ۱ ماهه"),
    (8, "Netflix Premium - 1 Month", 320000, "نتفلیکس پرمیوم ۱ ماهه"),
    (9, "Telegram Premium - 3 Months", 650000, "تلگرام پرمیوم ۳ ماهه"),
    (10, "Duolingo Super - 1 Year", 400000, "دولینگو سوپر ۱ ساله"),
]

DEFAULT_STOCK = [
    (1, "spotify_user1@gmail.com | pass: 123456"),
    (1, "spotify_user2@gmail.com | pass: 654321"),
    (2, "capcut_account_1 | code: CAP-1234"),
    (3, "chatgpt_user1@gmail.com | pass: gpt123"),
    (4, "gemini_link: https://example.com/redeem/abc"),
    (6, "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"),
]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
DB = "shop.db"

# ================= دیتابیس =================
def init_db():
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, description TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock(
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, item TEXT,
        is_sold INTEGER DEFAULT 0, sold_to INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER,
        item TEXT, price INTEGER)""")
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO products(id,name,price,description) VALUES(?,?,?,?)", DEFAULT_PRODUCTS)
        cur.executemany("INSERT INTO stock(product_id,item) VALUES(?,?)", DEFAULT_STOCK)
    con.commit(); con.close()

def get_balance(user_id):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id,balance) VALUES(?,0)", (user_id,))
    cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cur.fetchone()[0]; con.commit(); con.close()
    return bal

def add_balance(user_id, amount):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id,balance) VALUES(?,0)", (user_id,))
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    con.commit(); con.close()

def get_products():
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT id,name,price,description FROM products ORDER BY id")
    rows = cur.fetchall(); con.close(); return rows

def get_product(pid):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT id,name,price,description FROM products WHERE id=?", (pid,))
    row = cur.fetchone(); con.close(); return row

def stock_count(pid):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM stock WHERE product_id=? AND is_sold=0", (pid,))
    n = cur.fetchone()[0]; con.close(); return n

def take_stock(pid, user_id):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT id,item FROM stock WHERE product_id=? AND is_sold=0 LIMIT 1", (pid,))
    row = cur.fetchone()
    if not row:
        con.close(); return None
    cur.execute("UPDATE stock SET is_sold=1, sold_to=? WHERE id=?", (user_id, row[0]))
    con.commit(); con.close(); return row[1]

# ================= منوها =================
def main_menu():
    # دکمه‌ها با آیکون پرمیوم - Bot API 9.4: icon_custom_emoji_id
    # متن دکمه بدون ایموجی معمولی باشد، آیکون پرمیوم خودش نمایش داده می‌شود
    # برای این قابلیت، صاحب ربات باید تلگرام پرمیوم داشته باشد
    # و python-telegram-bot باید به‌روز باشد: pip install -U python-telegram-bot
    kb = [
        [InlineKeyboardButton("فروشگاه", callback_data="shop",
                              icon_custom_emoji_id=PREMIUM_ICONS["shop"], style="success")],
        [InlineKeyboardButton("کیف پول من", callback_data="wallet",
                              icon_custom_emoji_id=PREMIUM_ICONS["wallet"], style="primary"),
         InlineKeyboardButton("سفارش‌های من", callback_data="orders",
                              icon_custom_emoji_id=PREMIUM_ICONS["orders"], style="primary")],
        [InlineKeyboardButton("پشتیبانی", url=f"https://t.me/{SUPPORT_USERNAME}",
                              icon_custom_emoji_id=PREMIUM_ICONS["support"])],
    ]
    return InlineKeyboardMarkup(kb)

def shop_keyboard():
    kb = []
    for pid, name, price, desc in get_products():
        count = stock_count(pid)
        status = f"{count} موجود" if count > 0 else "ناموجود"
        kb.append([InlineKeyboardButton(f"{name} - {price:,} {CURRENCY} | {status}",
                                        callback_data=f"product_{pid}",
                                        icon_custom_emoji_id=PREMIUM_ICONS["buy"])])
    kb.append([InlineKeyboardButton("بازگشت", callback_data="back_main",
                                    icon_custom_emoji_id=PREMIUM_ICONS["shop"])])
    return InlineKeyboardMarkup(kb)

def wallet_keyboard():
    kb = [
        [InlineKeyboardButton("شارژ با کارت به کارت", callback_data="charge_card",
                              icon_custom_emoji_id=PREMIUM_ICONS["wallet"])],
        [InlineKeyboardButton("شارژ با استارز تلگرام", callback_data="charge_stars",
                              icon_custom_emoji_id=PREMIUM_ICONS["star"])],
        [InlineKeyboardButton("بازگشت", callback_data="back_main",
                              icon_custom_emoji_id=PREMIUM_ICONS["shop"])],
    ]
    return InlineKeyboardMarkup(kb)

# ================= شروع و فروشگاه =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_balance(user.id)
    # متن با جایگیر ⭐ - هر ⭐ با یک ایموجی پرمیوم جایگزین می‌شود
    text = (
        f"⭐ سلام {user.first_name}\n\n"
        "⭐ به فروشگاه اکانت پرمیوم خوش اومدی\n\n"
        "⭐ از فروشگاه محصول رو انتخاب کن، با کیف پولت بخر و آنی تحویل بگیر."
    )
    entities = [
        MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=0, length=1, custom_emoji_id=PREMIUM_ICONS["star"]),
        MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=len(f"⭐ سلام {user.first_name}\n\n"), length=1, custom_emoji_id=PREMIUM_ICONS["shop"]),
        MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=len(f"⭐ سلام {user.first_name}\n\n⭐ به فروشگاه اکانت پرمیوم خوش اومدی\n\n"), length=1, custom_emoji_id=PREMIUM_ICONS["wallet"]),
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu(), entities=entities)
    else:
        # برای edit_message_text هم entities لازم است
        try:
            await update.callback_query.edit_message_text(text, reply_markup=main_menu(), entities=entities)
        except Exception:
            await update.callback_query.edit_message_text(text, reply_markup=main_menu())

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    bal = get_balance(q.from_user.id)
    text = f"💰 موجودی کیف پول شما:\n\n**{bal:,} {CURRENCY}**\n\nروش شارژ را انتخاب کن:"
    await q.edit_message_text(text, reply_markup=wallet_keyboard(), parse_mode="Markdown")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT product_id,item,price FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (q.from_user.id,))
    rows = cur.fetchall(); con.close()
    if not rows:
        text = "📦 هنوز سفارشی نداری."
    else:
        text = "📦 سفارش‌های اخیر شما:\n\n"
        for pid, item, price in rows:
            prod = get_product(pid)
            name = prod[1] if prod else f"محصول {pid}"
            text += f"• {name} - {price:,} {CURRENCY}\n  `{item}`\n\n"
    kb = [[InlineKeyboardButton("بازگشت", callback_data="back_main", icon_custom_emoji_id=PREMIUM_ICONS["shop"])]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("🛍 فروشگاه - محصول را انتخاب کن:", reply_markup=shop_keyboard())

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pid = int(q.data.split("_")[1])
    prod = get_product(pid)
    if not prod:
        await q.edit_message_text("محصول پیدا نشد.", reply_markup=shop_keyboard()); return
    _, name, price, desc = prod
    count = stock_count(pid); bal = get_balance(q.from_user.id)
    text = f"📦 **{name}**\n\n{desc}\n\n💵 قیمت: **{price:,} {CURRENCY}**\n📊 موجودی: {count}\n💰 کیف پول شما: {bal:,} {CURRENCY}\n"
    kb = [
        [InlineKeyboardButton(f"خرید - {price:,} {CURRENCY}", callback_data=f"buy_{pid}",
                              icon_custom_emoji_id=PREMIUM_ICONS["buy"], style="success")],
        [InlineKeyboardButton("بازگشت به فروشگاه", callback_data="shop",
                              icon_custom_emoji_id=PREMIUM_ICONS["shop"])],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pid = int(q.data.split("_")[1])
    prod = get_product(pid)
    if not prod: return
    _, name, price, desc = prod
    user_id = q.from_user.id; bal = get_balance(user_id)
    if stock_count(pid) == 0:
        await q.edit_message_text("❌ متاسفانه این محصول ناموجود است.", reply_markup=shop_keyboard()); return
    if bal < price:
        await q.edit_message_text(f"❌ موجودی کافی نیست!\n\nقیمت: {price:,} {CURRENCY}\nموجودی شما: {bal:,} {CURRENCY}\n\nاول کیف پولت را شارژ کن.", reply_markup=wallet_keyboard()); return
    add_balance(user_id, -price)
    item = take_stock(pid, user_id)
    if not item:
        add_balance(user_id, price)
        await q.edit_message_text("خطا در تحویل، به پشتیبانی پیام بده."); return
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("INSERT INTO orders(user_id,product_id,item,price) VALUES(?,?,?,?)", (user_id, pid, item, price))
    con.commit(); con.close()
    text = f"✅ خرید با موفقیت انجام شد!\n\n📦 محصول: **{name}**\n💵 قیمت: {price:,} {CURRENCY}\n\n🔑 اطلاعات تحویل:\n`{item}`\n\nاین اطلاعات را جایی امن نگه دار."
    kb = [[InlineKeyboardButton("ادامه خرید", callback_data="shop", icon_custom_emoji_id=PREMIUM_ICONS["shop"], style="success")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await start(update, context)

# ================= پرداخت 1: کارت به کارت =================
async def charge_card_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = "💳 شارژ با کارت به کارت\n\nمبلغ را انتخاب کن:"
    kb = [
        [InlineKeyboardButton("100,000 تومان", callback_data="card_100000", icon_custom_emoji_id=PREMIUM_ICONS["wallet"]),
         InlineKeyboardButton("200,000 تومان", callback_data="card_200000", icon_custom_emoji_id=PREMIUM_ICONS["wallet"])],
        [InlineKeyboardButton("500,000 تومان", callback_data="card_500000", icon_custom_emoji_id=PREMIUM_ICONS["wallet"]),
         InlineKeyboardButton("1,000,000 تومان", callback_data="card_1000000", icon_custom_emoji_id=PREMIUM_ICONS["wallet"])],
        [InlineKeyboardButton("بازگشت", callback_data="wallet", icon_custom_emoji_id=PREMIUM_ICONS["wallet"])],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def card_amount_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    amount = int(q.data.split("_")[1])
    context.user_data["awaiting_receipt"] = amount
    text = (
        f"💳 شارژ {amount:,} {CURRENCY}\n\n"
        f"به این کارت واریز کن:\n"
        f"`{CARD_NUMBER}`\n"
        f"به نام: {CARD_HOLDER}\n\n"
        "بعد از واریز، اسکرین‌شات رسید یا شماره پیگیری را همینجا بفرست.\n"
        "ادمین تایید می‌کند و کیف پولت شارژ می‌شود."
    )
    kb = [[InlineKeyboardButton("بازگشت", callback_data="wallet", icon_custom_emoji_id=PREMIUM_ICONS["wallet"])]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگر ایموجی پرمیوم فرستاده شد، آیدی‌ش را برمی‌گرداند.
    اگر رسید شارژ فرستاده شد، برای ادمین فوروارد می‌شود"""
    # اول چک کن ایموجی پرمیوم هست یا نه
    if update.message.entities:
        found = []
        for ent in update.message.entities:
            if ent.type == "custom_emoji" and ent.custom_emoji_id:
                found.append(ent.custom_emoji_id)
        if found:
            ids_text = "\n".join(found)
            await update.message.reply_text(f"آیدی ایموجی پرمیوم:\n`{ids_text}`", parse_mode="Markdown")
            return
    amount = context.user_data.get("awaiting_receipt")
    if not amount:
        return  # پیام عادی است، کاری نکن
    user = update.effective_user
    context.user_data["awaiting_receipt"] = None

    caption = (
        f"💳 درخواست شارژ جدید\n\n"
        f"👤 کاربر: {user.first_name} (@{user.username}) - `{user.id}`\n"
        f"💰 مبلغ: {amount:,} {CURRENCY}\n\n"
        "تایید می‌کنی؟"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("تایید", callback_data=f"approve_{user.id}_{amount}", icon_custom_emoji_id=PREMIUM_ICONS["buy"], style="success"),
        InlineKeyboardButton("رد", callback_data=f"reject_{user.id}_{amount}", icon_custom_emoji_id=PREMIUM_ICONS["support"], style="danger"),
    ]])
    # اگر عکس فرستاده، عکس را با کپشن بفرست، اگر متن فرستاده، متن را بفرست
    if update.message.photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
    else:
        text = update.message.text or "(بدون متن)"
        await context.bot.send_message(chat_id=ADMIN_ID, text=caption + f"\n\nمتن رسید:\n{text}", reply_markup=kb, parse_mode="Markdown")
    await update.message.reply_text("✅ رسیدت برای ادمین فرستاده شد. بعد از تایید، کیف پولت شارژ می‌شود.")

async def approve_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("فقط ادمین می‌تواند تایید کند.", show_alert=True); return
    _, uid, amount = q.data.split("_")
    uid = int(uid); amount = int(amount)
    add_balance(uid, amount)
    await q.edit_message_text(f"✅ تایید شد. {amount:,} {CURRENCY} به کاربر {uid} اضافه شد.")
    try:
        await context.bot.send_message(chat_id=uid, text=f"✅ کیف پول شما {amount:,} {CURRENCY} شارژ شد!\nموجودی جدید: {get_balance(uid):,} {CURRENCY}")
    except Exception:
        pass

async def reject_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
    _, uid, amount = q.data.split("_")
    await q.edit_message_text(f"❌ درخواست شارژ کاربر {uid} رد شد.")
    try:
        await context.bot.send_message(chat_id=int(uid), text="❌ درخواست شارژ شما رد شد. به پشتیبانی پیام بده.")
    except Exception:
        pass

# ================= پرداخت 2: استارز تلگرام =================
async def charge_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = (
        "⭐ شارژ با استارز تلگرام\n\n"
        f"نرخ: هر 1 استارز = {STAR_TO_TOMAN:,} {CURRENCY}\n\n"
        "مقدار استارز را انتخاب کن:"
    )
    kb = [
        [InlineKeyboardButton("10", callback_data="stars_10", icon_custom_emoji_id=PREMIUM_ICONS["star"]),
         InlineKeyboardButton("25", callback_data="stars_25", icon_custom_emoji_id=PREMIUM_ICONS["star"])],
        [InlineKeyboardButton("50", callback_data="stars_50", icon_custom_emoji_id=PREMIUM_ICONS["star"]),
         InlineKeyboardButton("100", callback_data="stars_100", icon_custom_emoji_id=PREMIUM_ICONS["star"])],
        [InlineKeyboardButton("200", callback_data="stars_200", icon_custom_emoji_id=PREMIUM_ICONS["star"])],
        [InlineKeyboardButton("بازگشت", callback_data="wallet", icon_custom_emoji_id=PREMIUM_ICONS["wallet"])],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def stars_amount_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    stars = int(q.data.split("_")[1])
    toman = stars * STAR_TO_TOMAN
    # ارسال فاکتور استارز - currency باید XTR باشد
    await context.bot.send_invoice(
        chat_id=q.message.chat_id,
        title="شارژ کیف پول",
        description=f"شارژ {stars} استارز = {toman:,} {CURRENCY}",
        payload=f"stars_{stars}",
        provider_token="",  # برای استارز خالی می‌ماند
        currency="XTR",
        prices=[LabeledPrice("شارژ کیف پول", stars)],
    )
    await q.edit_message_text(f"⭐ فاکتور {stars} استارز ارسال شد. پرداخت را کامل کن.")

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay = update.message.successful_payment
    if not pay:
        return
    payload = pay.invoice_payload or ""
    user_id = update.effective_user.id
    if payload.startswith("stars_"):
        try:
            stars = int(payload.split("_")[1])
        except ValueError:
            stars = pay.total_amount  # total_amount برای XTR همان تعداد استارز است
        toman = stars * STAR_TO_TOMAN
        add_balance(user_id, toman)
        await update.message.reply_text(
            f"✅ پرداخت {stars} ⭐ با موفقیت انجام شد!\n"
            f"💰 {toman:,} {CURRENCY} به کیف پولت اضافه شد.\n"
            f"موجودی جدید: {get_balance(user_id):,} {CURRENCY}")
    else:
        await update.message.reply_text("✅ پرداخت با موفقیت انجام شد!")

# ================= ادمین =================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ شما دسترسی ادمین نداری."); return
    text = (
        "👑 پنل ادمین\n\n"
        "دستورات:\n"
        "`/addstock <id محصول> <متن کالا>`\n"
        "`/give <user_id> <مبلغ>`\n"
        "`/stats` - آمار فروش\n"
        "`/products` - لیست محصولات\n\n"
        f"💳 کارت: `{CARD_NUMBER}`\n"
        f"⭐ نرخ استارز: هر 1 ⭐ = {STAR_TO_TOMAN:,} {CURRENCY}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /addstock <id> <متن کالا>"); return
    try: pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("آیدی محصول باید عدد باشد."); return
    item = " ".join(context.args[1:])
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("INSERT INTO stock(product_id,item) VALUES(?,?)", (pid, item))
    con.commit(); con.close()
    await update.message.reply_text(f"✅ به موجودی محصول {pid} اضافه شد.")

async def give_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2:
        await update.message.reply_text("استفاده: /give <user_id> <مبلغ>"); return
    try: uid = int(context.args[0]); amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("عدد وارد کن."); return
    add_balance(uid, amount)
    await update.message.reply_text(f"✅ {amount:,} {CURRENCY} به کاربر {uid} اضافه شد.")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders"); orders, total = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM stock WHERE is_sold=0"); stock = cur.fetchone()[0]
    con.close()
    await update.message.reply_text(f"📊 آمار:\n\n👥 کاربران: {users}\n📦 سفارش‌ها: {orders}\n💰 فروش کل: {total:,} {CURRENCY}\n📦 موجودی: {stock}")

async def products_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📦 محصولات:\n\n"
    for pid, name, price, desc in get_products():
        text += f"{pid}. {name} - {price:,} {CURRENCY} | موجودی: {stock_count(pid)}\n"
    await update.message.reply_text(text)

# ================= اصلی =================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("addstock", add_stock_cmd))
    app.add_handler(CommandHandler("give", give_balance_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("products", products_cmd))

    app.add_handler(CallbackQueryHandler(show_shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(wallet, pattern="^wallet$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^orders$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(show_product, pattern="^product_"))
    app.add_handler(CallbackQueryHandler(buy_product, pattern="^buy_"))

    # پرداخت
    app.add_handler(CallbackQueryHandler(charge_card_menu, pattern="^charge_card$"))
    app.add_handler(CallbackQueryHandler(card_amount_chosen, pattern="^card_"))
    app.add_handler(CallbackQueryHandler(charge_stars_menu, pattern="^charge_stars$"))
    app.add_handler(CallbackQueryHandler(stars_amount_chosen, pattern="^stars_"))
    app.add_handler(CallbackQueryHandler(approve_charge, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(reject_charge, pattern="^reject_"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    # رسید کارت به کارت - عکس یا متن، بعد از انتخاب مبلغ
    app.add_handler(MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, handle_receipt))

    print("ربات فروشگاه روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
import asyncio
import easyocr
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, AIORateLimiter
from telegram.error import RetryAfter, TelegramError

# --- 1. LOGGING SETUP ---
# This saves every action to a file on your laptop so you have a backup of orders.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tibeb_production.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 2. CONFIGURATION ---
TOKEN = '8756275070:AAG3LV6lJKwzBK9bU9NTML-B4E78C-WMWHI'
ADMIN_GROUP_ID = -100XXXXXXXXXX # 👈 REPLACE WITH YOUR STAFF GROUP ID

# Initialize OCR (Vision)
print("⏳ Loading AI Vision... (Computer Science Project: Tibeb Leather)")
reader = easyocr.Reader(['en'])

# --- 3. THE "SAFETY SHIELD" (Prevents Account Freezes) ---
async def safe_send(context, method, **kwargs):
    """Sends messages with automatic wait-and-retry logic for flood protection."""
    try:
        return await method(**kwargs)
    except RetryAfter as e:
        logger.warning(f"⚠️ Flood limit hit! Waiting {e.retry_after} seconds...")
        await asyncio.sleep(e.retry_after + 1)
        return await method(**kwargs)
    except TelegramError as e:
        logger.error(f"❌ Telegram Error: {e}")

# --- 4. COMMAND HANDLERS (Compliance & UX) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Log the Chat ID to the console to help you find your Group ID
    print(f"DEBUG: Current Chat ID is {update.effective_chat.id}")
    
    kb = [['📍 Location', '💰 Price'], ['🕒 Hours', '✅ Verify Receipt']]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
    welcome_text = (
        "ሰላም! ወደ Tibeb Leather እንኳን ደህና መጡ። ✨\n"
        "Welcome! Use the menu or send a receipt photo.\n\n"
        "Need help? Type /support\n"
        "View our rules: /terms"
    )
    await safe_send(context, update.message.reply_text, text=welcome_text, reply_markup=markup)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_text = (
        "🛠 **Tibeb Leather Support**\n\n"
        "Issues with your order? Contact our team:\n"
        "📞 Phone: +251 9XX XXX XXX\n"
        "📍 Visit: Bole Atlas, Morning Star Mall\n"
        "💬 Admin: @YourAdminUsername"
    )
    await safe_send(context, update.message.reply_text, text=support_text)

async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    terms_text = (
        "📜 **Terms & Conditions**\n\n"
        "1. Payments must be verified via CBE/Telebirr screenshot.\n"
        "2. Orders are 'Approved' only after a staff call.\n"
        "3. Delivery: 24-48 hours within Addis Ababa.\n"
        "4. Phone numbers are used only for order confirmation."
    )
    await safe_send(context, update.message.reply_text, text=terms_text)

# --- 5. CORE LOGIC (Photo & Message) ---

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    status = await safe_send(context, update.message.reply_text, text="🔍 AI Vision is scanning your receipt...")
    
    file_path = f"temp_{user.id}.jpg"
    photo = await update.message.photo[-1].get_file()
    await photo.download_to_drive(file_path)

    try:
        # OCR Scan
        results = reader.readtext(file_path, detail=0)
        all_text = " ".join(results).upper()
        
        # Data Extraction
        amount = "Check Photo"
        trans_id = "Manual Entry"
        for word in results:
            if "." in word and any(c.isdigit() for c in word): amount = word
            if len(word) >= 8 and any(c.isdigit() for c in word): trans_id = word

        # Store in user_data for Phase 2
        context.user_data['order'] = {
            'id': trans_id, 'amount': amount, 'path': file_path, 'name': user.full_name
        }

        await asyncio.sleep(1.5) # Anti-ban delay
        await safe_send(context, status.edit_text, 
                       text=f"✅ Receipt ID: {trans_id}\n\n**Please type your Phone Number** so we can call you to confirm.")
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        if os.path.exists(file_path): os.remove(file_path)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_msg_lower = text.lower().strip()
    
    # Check if finalizing an order
    if 'order' in context.user_data:
        data = context.user_data['order']
        
        ticket = (
            f"🔔 **NEW ORDER RECEIVED**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Customer: {data['name']}\n"
            f"📞 Phone: {text}\n"
            f"💰 Amount: {data['amount']} ETB\n"
            f"🆔 ID: {data['id']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 *Action: Call customer to approve!*"
        )

        # Send to Staff Group
        await safe_send(context, context.bot.send_photo, chat_id=ADMIN_GROUP_ID, 
                       photo=open(data['path'], 'rb'), caption=ticket)
        
        await safe_send(context, update.message.reply_text, text="🙏 Thank you! Staff will call you shortly.")
        
        logger.info(f"ORDER SUCCESS: {data['name']} - {text}")
        
        if os.path.exists(data['path']): os.remove(data['path'])
        del context.user_data['order']
        return

    # Menu Responses
    if "location" in user_msg_lower or "አድራሻ" in user_msg_lower:
        await safe_send(context, update.message.reply_text, text="📍 አድራሻ፡ ቦሌ አትላስ ሞርኒንግ ስታር ሞል።")
    elif "price" in user_msg_lower or "ዋጋ" in user_msg_lower:
        await safe_send(context, update.message.reply_text, text="💰 ዋጋ ከ3,500 ብር ይጀምራል።")
    elif "hours" in user_msg_lower or "ሰዓት" in user_msg_lower:
        await safe_send(context, update.message.reply_text, text="🕒 Mon - Sat: 9:00 AM - 7:30 PM")
    else:
        await safe_send(context, update.message.reply_text, text="I didn't catch that. Please use the menu buttons.")

# --- 6. PRODUCTION ENGINE ---
if __name__ == '__main__':
    # AIORateLimiter protects against bursts
    app = ApplicationBuilder().token(TOKEN).rate_limiter(AIORateLimiter()).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("terms", terms))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 TIBEB BOT: SECURE PRODUCTION MODE ONLINE")
    app.run_polling(poll_interval=2.0, drop_pending_updates=True)

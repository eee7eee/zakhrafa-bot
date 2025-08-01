import os
import io
import qrcode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# --- User Persistence ---
def save_user(user_id: int):
    if not os.path.exists("users.txt"):
        with open("users.txt", "w") as f:
            pass
    with open("users.txt", "r+") as f:
        users = f.read().splitlines()
        if str(user_id) not in users:
            f.write(str(user_id) + "\n")

# --- User-facing handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    await update.message.reply_text("أهلاً بك! أرسل لي أي نص وسأقوم بتحويله إلى رمز QR.")

async def generate_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    text = update.message.text

    qr_img = qrcode.make(text)
    buf = io.BytesIO()
    qr_img.save(buf, 'PNG')
    buf.seek(0)

    await update.message.reply_photo(photo=buf, caption=f"رمز QR للنص:\n`{text}`")

# --- Admin handlers ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='stats')],
        [InlineKeyboardButton("📣 بث رسالة", callback_data='broadcast')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👑 لوحة تحكم المطور:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'stats':
        await show_stats(query, context)
    elif query.data == 'broadcast':
        await start_broadcast(query, context)

async def show_stats(query, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists("users.txt"):
        count = 0
    else:
        with open("users.txt") as f:
            count = len(f.read().splitlines())
    await query.message.reply_text(f"📊 عدد المستخدمين: {count}")

async def start_broadcast(query, context: ContextTypes.DEFAULT_TYPE):
    await query.message.reply_text("✍️ أرسل الآن الرسالة التي تريد بثها للمستخدمين.")
    context.user_data['is_broadcasting'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('is_broadcasting'):
        # Handle broadcast message
        message_text = update.message.text
        context.user_data['is_broadcasting'] = False # Exit broadcast mode

        if not os.path.exists("users.txt"):
            await update.message.reply_text("⚠️ لا يوجد مستخدمين لبث الرسالة.")
            return

        with open("users.txt") as f:
            users = f.read().splitlines()

        count = 0
        for user_id in users:
            try:
                await context.bot.send_message(chat_id=int(user_id), text=message_text)
                count += 1
            except Exception as e:
                print(f"Failed to send message to {user_id}: {e}")

        await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {count} من المستخدمين.")
    else:
        # If not in broadcast mode, treat as a normal message for QR code
        await generate_qr(update, context)


def main():
    if not BOT_TOKEN or not ADMIN_ID:
        print("Error: BOT_TOKEN or ADMIN_ID environment variables not set.")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


    print("Modern QR Code Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()

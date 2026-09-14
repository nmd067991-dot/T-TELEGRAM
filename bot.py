import os, json, random, string, logging
from dotenv import load_dotenv
from pyrogram import Client
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

load_dotenv()

BOT_TOKEN = os.getenv("8876530595:AAFDYyGG0Bq7aXoBlTC7NKG8c0clRzGfyTE")
API_ID = int(os.getenv("31024467"))
API_HASH = os.getenv("a09eadca532e14af757fa345c950532c")
ADMIN_IDS = [int(x) for x in os.getenv("8917082487", "").split(",")]
BASE_URL = os.getenv("telegram-bot-api-production-8080.up.railway.app")

UPLOAD_DIR = "uploads"
DB_FILE = "codes.json"
CODE_LENGTH = 6
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Pyrogram ক্লায়েন্ট (MTProto API — ২ জিবি পর্যন্ত) ──
pyro = Client(
    "filebot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ── ডাটাবেস ──
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

DB = load_db()

def generate_code():
    while True:
        code = "".join(random.choices(
            string.ascii_uppercase + string.digits, k=CODE_LENGTH
        ))
        if code not in DB:
            return code

# ── /start ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id in ADMIN_IDS:
        await update.message.reply_text(
            "👋 স্বাগতম, অ্যাডমিন!\n\n"
            "📎 যেকোনো ফাইল (২ জিবি পর্যন্ত) পাঠান — আমি কোড দেব।\n"
            "🔑 কোড যে কেউ পাঠালে ফাইল পাবে।\n\n"
            "📌 /mycodes — আপনার সব কোড"
        )
    else:
        await update.message.reply_text("🔑 আপনার কোডটি পাঠান")

# ── ফাইল রিসিভ (অ্যাডমিন) — Pyrogram দিয়ে ডাউনলোড ──
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id

    if user_id not in ADMIN_IDS:
        await msg.reply_text("🔑 আপনার কোডটি পাঠান")
        return

    # ফাইল সাইজ চেক (২ জিবি = 2 * 1024^3 বাইট)
    MAX_SIZE = 2 * 1024 * 1024 * 1024
    if msg.document and msg.document.file_size and msg.document.file_size > MAX_SIZE:
        await msg.reply_text("❌ ফাইলটি ২ জিবি-এর বেশি।")
        return
    if msg.video and msg.video.file_size and msg.video.file_size > MAX_SIZE:
        await msg.reply_text("❌ ভিডিওটি ২ জিবি-এর বেশি।")
        return

    code = generate_code()
    await msg.reply_text("⏳ ফাইল ডাউনলোড শুরু হচ্ছে (বড় ফাইলে সময় লাগবে)...")

    try:
        # Pyrogram দিয়ে ডাউনলোড (MTProto — ২০ MB সীমা নেই)
        file_path = await pyro.download_media(msg, file_name=f"{UPLOAD_DIR}/{code}_")

        # ফাইল নাম বের করা
        if msg.document:
            original_name = msg.document.file_name or "file"
        elif msg.video:
            original_name = msg.video.file_name or "video.mp4"
        elif msg.audio:
            original_name = msg.audio.file_name or "audio.mp3"
        else:
            original_name = "file"

        # ফাইলটি কোড-নামে রিনেম
        new_path = os.path.join(UPLOAD_DIR, f"{code}_{original_name}")
        if file_path != new_path:
            os.rename(file_path, new_path)

        DB[code] = {
            "path": new_path,
            "name": original_name,
            "owner": str(user_id),
            "used": 0
        }
        save_db(DB)

        await msg.reply_text(
            f"✅ ফাইল সংরক্ষিত!\n\n"
            f"🔑 কোড: `{code}`\n"
            f"📁 ফাইল: `{original_name}`\n\n"
            f"এই কোড যে কেউ পাঠালে ফাইল পাবে।",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"ডাউনলোড এরর: {e}")
        await msg.reply_text(f"❌ সমস্যা: `{str(e)[:200]}`", parse_mode="Markdown")

# ── টেক্সট → কোড চেক → ফাইল পাঠানো ──
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().upper()

    if text in DB:
        entry = DB[text]
        path = entry["path"]

        if not os.path.exists(path):
            await update.message.reply_text("❌ ফাইলটি আর নেই।")
            return

        await update.message.reply_text("📤 ফাইল পাঠানো হচ্ছে...")
        try:
            with open(path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=entry["name"],
                    caption=f"🔑 কোড: `{text}`",
                    parse_mode="Markdown"
                )
            entry["used"] = entry.get("used", 0) + 1
            save_db(DB)
        except Exception as e:
            logging.error(f"আপলোড এরর: {e}")
            await update.message.reply_text(f"❌ সমস্যা: `{str(e)[:200]}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ কোডটি সঠিক নয়।")

# ── /mycodes ──
async def my_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🔑 আপনার কোডটি পাঠান")
        return

    user_codes = {c: v for c, v in DB.items() if v["owner"] == str(user_id)}
    if not user_codes:
        await update.message.reply_text("📭 আপনার কোনো কোড নেই।")
        return

    lines = ["📋 আপনার কোডগুলো:\n"]
    for code, info in user_codes.items():
        lines.append(f"🔑 `{code}` → `{info['name']}` (ব্যবহার: {info.get('used', 0)})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── মেইন ──
def main():
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    # Pyrogram ক্লায়েন্ট স্টার্ট (MTProto সেশন)
    pyro.start()
    logging.info("✅ Pyrogram MTProto ক্লায়েন্ট চালু হয়েছে")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mycodes", my_codes))
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.PHOTO,
        handle_file
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text
    ))

    print("🤖 বট চালু হয়েছে... (২ জিবি পর্যন্ত ফাইল সাপোর্ট)")
    app.run_polling()

if __name__ == "__main__":
    main()
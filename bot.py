"""
Telegram Bot for downloading Terabox links and force subscribing users to a specific channel.

Features:
- Accept Terabox links from users.
- Download the file from the given Terabox link.
- Send back the downloaded file to the user.
- Force subscribe users to a Telegram channel before letting them use the bot.
- Provides "Join now" button linking to the required Telegram channel.
- Suitable for deployment on Koyeb or similar platforms.

Requirements:
- python-telegram-bot==20.x (latest)
- requests library

Usage:
Set environment variables:
- TELEGRAM_BOT_TOKEN: Your Telegram bot token
- CHANNEL_USERNAME: Telegram channel username (without @) for force subscribe

Deploy on Koyeb or run locally.

"""

import os
import re
import tempfile
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Environment variables
BOT_TOKEN = os.getenv("8043406036:AAHfFIEcS8IYs6wmem86IuJSMuCK3Oy3ytg")
CHANNEL_USERNAME = os.getenv("Joker_offical0")  # e.g. "mychannel"

# Terabox direct link pattern (simplified)
TERABOX_URL_REGEX = r"(https?://(?:www\.)?terabox\.com/s/[a-zA-Z0-9_-]+)"

# Max Telegram file upload size in bytes (approximately 2GB)
MAX_TELEGRAM_FILE_SIZE = 2 * 1024 * 1024 * 1024


async def force_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if the user is a member of the CHANNEL_USERNAME.
    If not, send a message with Join Now button and return False.
    Otherwise, return True.
    """
    if not CHANNEL_USERNAME:
        # If no channel username set, skip force subscribe
        return True
    try:
        user_id = update.effective_user.id
        member = await context.bot.get_chat_member(chat_id="@"+CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        else:
            # Not joined - send message
            join_button = InlineKeyboardButton(text="Join Now", url=f"https://t.me/{CHANNEL_USERNAME}")
            keyboard = InlineKeyboardMarkup([[join_button]])
            await update.message.reply_text(
                f"⚠️ You must join our channel @{CHANNEL_USERNAME} to use this bot.",
                reply_markup=keyboard,
            )
            return False
    except Exception as e:
        # Possibly user not a member
        join_button = InlineKeyboardButton(text="Join Now", url=f"https://t.me/{CHANNEL_USERNAME}")
        keyboard = InlineKeyboardMarkup([[join_button]])
        await update.message.reply_text(
            f"⚠️ Please join our channel @{CHANNEL_USERNAME} to use this bot.",
            reply_markup=keyboard,
        )
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Send me a Terabox link, and I will download the file for you.\n\n"
        "Note: You must join our channel first to use this bot."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Force subscribe check
    joined = await force_subscribe(update, context)
    if not joined:
        return

    # Extract Terabox link
    match = re.search(TERABOX_URL_REGEX, text)
    if not match:
        await update.message.reply_text("❌ Please send a valid Terabox link (e.g. https://terabox.com/s/xyz).")
        return

    terabox_link = match.group(1)
    await update.message.reply_text(f"🔍 Downloading file from: {terabox_link}\nPlease wait...")

    # Try to download the file
    try:
        file_path, file_name = await download_terabox_file(terabox_link)
        if file_path is None:
            await update.message.reply_text("❌ Failed to download the file. The link might be invalid or protected.")
            return

        file_size = os.path.getsize(file_path)
        if file_size > MAX_TELEGRAM_FILE_SIZE:
            await update.message.reply_text(
                "❌ Sorry, the file is too large to send via Telegram (max 2GB)."
            )
            os.remove(file_path)
            return

        await update.message.reply_document(document=open(file_path, "rb"), filename=file_name)
        os.remove(file_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error during download or upload: {str(e)}")


async def download_terabox_file(terabox_link: str):
    """
    Naive implementation: Try to extract direct download file URL from Terabox link.
    Terabox requires user auth for many files and complex APIs.
    Here we do best effort approach for public links.

    Returns tuple (file_path, file_name) if successful else (None, None)
    """
    # The direct download extraction method is not officially documented.
    # We'll try to get the page and find a download link in the page or use simple heuristics.

    try:
        # Fetch the link page
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)",
        }
        session = requests.Session()
        resp = session.get(terabox_link, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None, None

        html = resp.text

        # Look for a downloadable file info in HTML - this is heuristic and may fail
        # Example: look for file name in <title> or meta tags
        # Look for download URLs in the HTML
        file_name_match = re.search(r'<title>(.*?) - Terabox', html)
        file_name = file_name_match.group(1).strip() if file_name_match else "terabox_file"

        # Terabox links typically use service to generate temporary download URLs.
        # We try to extract json data containing download URLs from page scripts.
        # This is complex; here we do a naive search for 'download_url' or 'dlink'
        download_url_match = re.search(r'"download_url":"(https:\\/\\/[^"]+)"', html)
        if download_url_match:
            download_url = download_url_match.group(1).replace("\\/", "/")
        else:
            # fallback: can't find direct link
            return None, None

        # Download file from the direct URL
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        download_response = session.get(download_url, headers=headers, stream=True, timeout=60)
        if download_response.status_code != 200:
            temp_file.close()
            os.unlink(temp_file.name)
            return None, None

        for chunk in download_response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()

        return temp_file.name, file_name

    except Exception:
        return None, None


def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        return
    if not CHANNEL_USERNAME:
        print("Warning: CHANNEL_USERNAME is not set. Force subscribe will be disabled.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()


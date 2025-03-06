import os
import re
import glob
import logging
import asyncio
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import yt_dlp
from yt_dlp.utils import DownloadError

MAX_VIDEO_SIZE = 70 * 1024 * 1024  # байт

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def extract_video_url(text: str) -> str:
    urls = re.findall(r'(https?://\S+)', text)
    return urls[0] if urls else None

def download_video(url: str, output_pattern: str):
    ydl_opts = {
        'outtmpl': output_pattern,
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise DownloadError("Failed to retrieve video information.")
    except DownloadError as e:
        raise e

async def download_video_async(url: str, output_pattern: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_video, url, output_pattern)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi. Send me a link to the video or photo and I'll upload it."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    url = extract_video_url(text)
    if not url:
        return

    # Use a unique output filename based on chat_id and message_id
    chat_id = update.effective_chat.id
    message_id = update.effective_message.message_id
    output_pattern = f"downloaded_{chat_id}_{message_id}.%(ext)s"

    try:
        await download_video_async(url, output_pattern)

        # Use glob to find the file with the unique prefix
        matching_files = glob.glob(f"downloaded_{chat_id}_{message_id}.*")
        if not matching_files:
            await update.message.reply_text("Error: file not found after downloading.")
            return

        # Assuming only one file is downloaded per message
        file_path = matching_files[0]
        ext = file_path.split('.')[-1].lower()

        if ext == "mp4":
            file_size = os.path.getsize(file_path)
            if file_size > MAX_VIDEO_SIZE:
                os.remove(file_path)
                await update.message.reply_text("The downloaded video exceeds the maximum allowed size.")
                return
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(video=video_file)
        else:
            with open(file_path, 'rb') as photo_file:
                await update.message.reply_photo(photo=photo_file)

        os.remove(file_path)

    except DownloadError as de:
        logger.error("Download error: %s", de)
        await update.message.reply_text("Download error: video content not detected or resource unavailable.")
    except Exception as e:
        logger.error("Error: %s", e)
        await update.message.reply_text("There's been an error. Try again later.")

def main():
    TOKEN = 'YOUR_TOKEN'
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()

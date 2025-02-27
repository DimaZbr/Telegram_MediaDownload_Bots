import os
import re
import glob
import logging
import asyncio
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import yt_dlp
from yt_dlp.utils import DownloadError

# Максимально допустимый размер видео (70 МБ)
MAX_VIDEO_SIZE = 70 * 1024 * 1024  # байт

# Настройка логирования
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

    output_pattern = "downloaded_file.%(ext)s"
    try:
        await download_video_async(url, output_pattern)

        matching_files = glob.glob("downloaded_file.*")
        if not matching_files:
            await update.message.reply_text("Error: file not found after uploading.")
            return

        if len(matching_files) == 1:
            file_path = matching_files[0]
            ext = file_path.split('.')[-1].lower()
            if ext == "mp4":
                file_size = os.path.getsize(file_path)
                if file_size > MAX_VIDEO_SIZE:
                    os.remove(file_path)
                    return
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file)
            else:
                with open(file_path, 'rb') as photo_file:
                    await update.message.reply_photo(photo=photo_file)
            os.remove(file_path)
        else:
            file_objs = []
            media_group = []
            for file in matching_files:
                ext = file.split('.')[-1].lower()
                if ext in ["jpg", "jpeg", "png", "gif"]:
                    fp = open(file, 'rb')
                    file_objs.append(fp)
                    media_group.append(InputMediaPhoto(fp))
            if media_group:
                await update.message.reply_media_group(media=media_group)
            else:
                await update.message.reply_text("Failed to identify files to send.")
            for fp in file_objs:
                fp.close()
            for file in matching_files:
                os.remove(file)
    except DownloadError as de:
        logger.error("Download error: %s", de)
        await update.message.reply_text("Download error. video content not detected or resource unavailable")
    except Exception as e:
        logger.error("Ошибка: %s", e)
        await update.message.reply_text("There's been an error. Try again later.")

def main():
    TOKEN = 'YOUR_TOKEN'
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()

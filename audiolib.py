import os
import re
import glob
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import yt_dlp
from yt_dlp.utils import DownloadError

# Максимально допустимый размер аудио (100 МБ)
MAX_AUDIO_SIZE = 100 * 1024 * 1024  # байт

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def extract_url(text: str) -> str:

    urls = re.findall(r'(https?://\S+)', text)
    return urls[0] if urls else None

def download_audio(url: str, output_pattern: str):

    ydl_opts = {
        'outtmpl': output_pattern,
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise DownloadError("Failed to retrieve audio information.")
    except DownloadError as e:
        raise e

async def download_audio_async(url: str, output_pattern: str):
 
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_audio, url, output_pattern)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi. Send me the link to the audio and I'll upload it."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    url = extract_url(text)
    if not url:
        return

    output_pattern = "downloaded_audio.%(ext)s"
    try:
        await download_audio_async(url, output_pattern)

        matching_files = glob.glob("downloaded_audio.*")
        if not matching_files:
            await update.message.reply_text("Error: file not found after uploading.")
            return

        if len(matching_files) == 1:
            file_path = matching_files[0]
            ext = file_path.split('.')[-1].lower()
            if ext == "mp3":
                file_size = os.path.getsize(file_path)
                if file_size > MAX_AUDIO_SIZE:
                    os.remove(file_path)
                    await update.message.reply_text("The file is too large to send.")
                    return
                with open(file_path, 'rb') as audio_file:
                    await update.message.reply_audio(audio=audio_file)
            else:
                await update.message.reply_text("The file format is not supported.")
            os.remove(file_path)
        else:
            await update.message.reply_text("Failed to identify a file to send.")
            for file in matching_files:
                os.remove(file)
    except DownloadError as de:
        logger.error("Download Error: %s", de)
        await update.message.reply_text("Download error. The resource may not be supported.")
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
import os
import asyncio
import datetime
import threading
import requests
from flask import Flask
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode

# --- 1. FLASK WEB SERVER (To keep Render awake) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "HyperOS News Bot is running 24/7!"

def run_flask():
    # Render uses port 10000 by default
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. CONFIGURATION ---
# It is better to set these in Render's Environment Variables panel
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8338217561:AAGcuaSjphoHUSHXFAZW6YEoYS2BR-17D88")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@chroma12309")
TARGET_HOUR = 18  # 6:00 PM (24-hour format)

# Google News RSS for HyperOS (Last 24 hours)
RSS_URL = "https://news.google.com/rss/search?q=Xiaomi+HyperOS+when:1d&hl=en-US&gl=US&ceid=US:en"

# --- 3. UTILITY FUNCTIONS ---
def get_actual_url(google_link):
    """Follows the Google redirect to find the actual website URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.head(google_link, headers=headers, allow_redirects=True, timeout=10)
        return response.url
    except:
        return google_link

def is_published_today(rss_date_string):
    """Checks if the article was published on the current calendar day."""
    try:
        pub_dt = parsedate_to_datetime(rss_date_string)
        # Convert both to UTC to ensure consistency
        return pub_dt.date() == datetime.datetime.now(datetime.timezone.utc).date()
    except:
        return False

# --- 4. THE SCRAPER & POSTER ---
async def run_daily_job():
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.datetime.now()}] 🕒 Starting 6:00 PM check...")
    
    try:
        response = requests.get(RSS_URL, timeout=15)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        todays_news = [i for i in items if is_published_today(i.pubDate.text)]

        if not todays_news:
            print("ℹ️ No news found for today.")
            return

        print(f"✅ Found {len(todays_news)} articles. Posting...")

        for item in todays_news:
            title = item.title.text
            clean_title = title.rsplit(" - ", 1)[0] if " - " in title else title
            source_name = title.rsplit(" - ", 1)[1] if " - " in title else "News"
            
            real_link = get_actual_url(item.link.text)

            message = (
                f"<b>⚡ HyperOS Daily Digest</b>\n\n"
                f"📰 <b>{clean_title}</b>\n"
                f"🗞 <i>Source: {source_name}</i>\n\n"
                f"🔗 <a href='{real_link}'>View Full Article</a>\n"
                f"#Xiaomi #HyperOS #Update"
            )

            try:
                await bot.send_message(
                    chat_id=CHANNEL_ID, 
                    text=message, 
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                print(f"      -> Posted: {clean_title[:30]}...")
                await asyncio.sleep(5) # Delay to prevent spamming
            except Exception as e:
                print(f"      ❌ Telegram Error: {e}")

    except Exception as e:
        print(f"❌ Scraper Error: {e}")

# --- 5. SCHEDULER LOOP ---
async def scheduler_loop():
    print(f"🚀 Bot initialized. Targeting {TARGET_HOUR}:00 PM daily.")
    
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=TARGET_HOUR, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += datetime.timedelta(days=1)
            
        wait_seconds = (target - now).total_seconds()
        print(f"💤 Sleeping for {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m...")
        
        await asyncio.sleep(wait_seconds)
        await run_daily_job()
        await asyncio.sleep(60) # Prevent double runs

if __name__ == "__main__":
    # Start Flask on a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the Asyncio Bot loop
    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        print("Bot stopped.")
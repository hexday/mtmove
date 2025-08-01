import asyncio
import logging
import signal
import sys
import platform
from datetime import datetime

from telegram.ext import Application

from config import config
from database import db
from file_manager import FileManager
from download_manager import download_manager
from handlers import setup_handlers

# تنظیم logging
logger = logging.getLogger(__name__)

# تنظیم event loop برای ویندوز
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class MovieUploaderBot:
    """🎬 کلاس اصلی ربات آپلودر فیلم و سریال"""
    
    def __init__(self):
        self.application = None
        self.file_manager = None
        self.running = False
        
    async def initialize(self):
        """🚀 مقداردهی اولیه ربات"""
        try:
            logger.info("🚀 شروع مقداردهی ربات...")
            
            # اعتبارسنجی تنظیمات
            if not config.validate():
                logger.error("❌ تنظیمات نامعتبر است")
                return False
            
            # ایجاد دایرکتوری‌ها
            config.create_directories()
            
            # اتصال به پایگاه داده
            if not await db.connect():
                logger.error("❌ خطا در اتصال به پایگاه داده")
                return False
            
            # ایجاد اپلیکیشن تلگرام
            self.application = (
                Application.builder()
                .token(config.BOT_TOKEN)
                .concurrent_updates(True)
                .build()
            )
            logger.info("✅ اپلیکیشن تلگرام ایجاد شد")
            
            # ایجاد مدیر فایل
            self.file_manager = FileManager(self.application.bot)
            logger.info("✅ مدیر فایل ایجاد شد")
            
            # تنظیم هندلرها
            setup_handlers(self.application, self.file_manager)
            logger.info("✅ هندلرها تنظیم شدند")
            
            # ذخیره زمان شروع
            self.application.bot_data['start_time'] = datetime.now()
            
            logger.info("🎉 ربات آماده به کار است!")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطا در مقداردهی: {e}")
            return False
    
    async def start(self):
        """▶️ شروع ربات"""
        try:
            # مقداردهی
            if not await self.initialize():
                return False
            
            logger.info("🔄 شروع ربات...")
            self.running = True
            
            # شروع session دانلود
            await download_manager.start_session()
            
            # شروع ربات
            await self.application.initialize()
            await self.application.start()
            
            # شروع polling با پارامترهای صحیح
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                bootstrap_retries=3,
                drop_pending_updates=True
            )
            
            logger.info("✅ ربات شروع شد و منتظر پیام‌ها است")
            
            # انتظار برای Ctrl+C یا سیگنال توقف
            try:
                while self.running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            
            # توقف ربات
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("🛑 توقف توسط کاربر (Ctrl+C)")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در اجرای ربات: {e}")
            return False
        finally:
            await self.cleanup()
    
    async def stop(self):
        """🛑 توقف ربات"""
        if self.running:
            logger.info("🛑 درخواست توقف ربات...")
            self.running = False
    
    async def cleanup(self):
        """🧹 پاکسازی منابع"""
        try:
            logger.info("🧹 پاکسازی منابع...")
            
            # بستن session دانلود
            await download_manager.close_session()
            
            # پاکسازی فایل‌های موقت
            if self.file_manager:
                await self.file_manager.cleanup_temp_files()
            
            # قطع اتصال پایگاه داده
            await db.disconnect()
            
            logger.info("✅ پاکسازی تکمیل شد")
            
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی: {e}")

# نمونه global ربات
bot = MovieUploaderBot()

def signal_handler(signum, frame):
    """📶 مدیریت سیگنال‌های سیستم"""
    logger.info(f"دریافت سیگنال {signum}")
    asyncio.create_task(bot.stop())

async def main():
    """🎯 تابع اصلی"""
    try:
        logger.info("=" * 50)
        logger.info("🎬 ربات آپلودر فیلم و سریال")
        logger.info("=" * 50)
        
        # تنظیم سیگنال‌ها
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # شروع ربات
        success = await bot.start()
        
        if success:
            logger.info("✅ ربات با موفقیت متوقف شد")
        else:
            logger.error("❌ ربات با خطا متوقف شد")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 توقف توسط کاربر (Ctrl+C)")
        await bot.stop()
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 خداحافظ!")
    except Exception as e:
        print(f"❌ خطا در اجرای main: {e}")
        sys.exit(1)

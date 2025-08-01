import os
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیم لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """کلاس تنظیمات پروژه"""
    
    # تنظیمات ربات
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv('BOT_TOKEN', ''))
    BOT_USERNAME: str = field(default_factory=lambda: os.getenv('BOT_USERNAME', ''))
    
    # پایگاه داده
    MONGODB_URL: str = field(default_factory=lambda: os.getenv('MONGODB_URL', 'mongodb://localhost:27017'))
    DATABASE_NAME: str = field(default_factory=lambda: os.getenv('DATABASE_NAME', 'movie_uploader_bot'))
    
    # کانال خصوصی
    PRIVATE_CHANNEL_ID: int = field(default_factory=lambda: int(os.getenv('PRIVATE_CHANNEL_ID', '0')))
    
    # ادمین‌ها
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') 
        if x.strip() and x.strip().isdigit()
    ])
    
    # محدودیت‌ها
    MAX_FILE_SIZE: int = field(default_factory=lambda: int(os.getenv('MAX_FILE_SIZE', '4294967296')))  # 4GB
    DOWNLOAD_TIMEOUT: int = field(default_factory=lambda: int(os.getenv('DOWNLOAD_TIMEOUT', '3600')))  # 1 hour
    RATE_LIMIT: int = field(default_factory=lambda: int(os.getenv('RATE_LIMIT', '10')))
    
    # مسیرها
    TEMP_PATH: str = 'temp'
    DOWNLOADS_PATH: str = 'downloads'
    
    # امنیت
    SECRET_KEY: str = field(default_factory=lambda: os.getenv('SECRET_KEY', 'default-key'))
    
    # فرمت‌های پشتیبانی شده
    SUPPORTED_VIDEO_FORMATS: List[str] = field(default_factory=lambda: [
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'
    ])
    
    SUPPORTED_QUALITIES: List[str] = field(default_factory=lambda: [
        '480p', '720p', '1080p', '1440p', '4k'
    ])
    
    def validate(self) -> bool:
        """🔍 اعتبارسنجی تنظیمات"""
        required_fields = {
            'BOT_TOKEN': self.BOT_TOKEN,
            'MONGODB_URL': self.MONGODB_URL,
            'PRIVATE_CHANNEL_ID': self.PRIVATE_CHANNEL_ID,
            'ADMIN_IDS': self.ADMIN_IDS
        }
        
        missing_fields = [field for field, value in required_fields.items() 
                         if not value or (field == 'PRIVATE_CHANNEL_ID' and value == 0)]
        
        if missing_fields:
            logger.error(f"❌ فیلدهای ضروری موجود نیست: {', '.join(missing_fields)}")
            return False
        
        logger.info("✅ تنظیمات معتبر است")
        return True
    
    def create_directories(self):
        """📁 ایجاد دایرکتوری‌های ضروری"""
        directories = [self.TEMP_PATH, self.DOWNLOADS_PATH]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"📁 دایرکتوری ایجاد شد: {directory}")

# ایجاد نمونه global
config = Config()

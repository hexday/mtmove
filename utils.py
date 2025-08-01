import os
import re
import hashlib
import secrets
import string
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import validators
import mimetypes

logger = logging.getLogger(__name__)

class Utils:
    """🛠️ توابع کمکی"""
    
    @staticmethod
    def generate_unique_code(length: int = 9) -> str:
        """🎲 تولید کد یکتا"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """📊 فرمت‌دهی حجم فایل"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """⏱️ فرمت‌دهی مدت زمان"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """🧹 پاک‌سازی نام فایل"""
        # حذف کاراکترهای غیرمجاز
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\s+', ' ', filename)  # تبدیل چند فاصله به یک فاصله
        filename = filename.strip()
        
        # محدود کردن طول
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            max_name_length = 200 - len(ext)
            filename = name[:max_name_length] + ext
        
        return filename or "unnamed_file"
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """🔗 اعتبارسنجی URL"""
        try:
            return validators.url(url) is True
        except Exception:
            return False
    
    @staticmethod
    def extract_video_id_from_url(url: str) -> Optional[str]:
        """📹 استخراج ID ویدیو از URL یوتیوب"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com\/.*[?&]v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def generate_deeplink(unique_code: str, bot_username: str) -> str:
        """🔗 تولید دیپ‌لینک"""
        return f"https://t.me/{bot_username}?start=v_{unique_code}"
    
    @staticmethod
    def parse_deeplink(start_param: str) -> Optional[str]:
        """🔍 تجزیه دیپ‌لینک"""
        if start_param and start_param.startswith('v_'):
            return start_param[2:]
        return None
    
    @staticmethod
    def create_hash(text: str, algorithm: str = 'sha256') -> str:
        """🔐 ایجاد هش"""
        hash_func = getattr(hashlib, algorithm)
        return hash_func(text.encode()).hexdigest()
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """🔤 فرار از کاراکترهای مارک‌داون"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def get_file_type(file_path: str) -> str:
        """📁 تشخیص نوع فایل"""
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type or 'application/octet-stream'
        except Exception:
            return 'application/octet-stream'
    
    @staticmethod
    def is_video_file(file_path: str) -> bool:
        """🎬 بررسی ویدیو بودن فایل"""
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        return Path(file_path).suffix.lower() in video_extensions
    
    @staticmethod
    async def safe_delete_file(file_path: str) -> bool:
        """🗑️ حذف ایمن فایل"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ فایل حذف شد: {file_path}")
                return True
        except Exception as e:
            logger.error(f"❌ خطا در حذف فایل {file_path}: {e}")
        return False

class RateLimiter:
    """⚡ کنترل نرخ درخواست"""
    
    def __init__(self):
        self.requests: Dict[int, List[datetime]] = {}
        self.cleanup_interval = 300  # 5 دقیقه
        self.last_cleanup = datetime.now()
    
    def is_allowed(self, user_id: int, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """✅ بررسی مجاز بودن درخواست"""
        now = datetime.now()
        
        # پاک‌سازی دوره‌ای
        if (now - self.last_cleanup).seconds > self.cleanup_interval:
            self._cleanup_old_requests()
        
        # دریافت یا ایجاد لیست درخواست‌های کاربر
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        user_requests = self.requests[user_id]
        window_start = now - timedelta(seconds=window_seconds)
        
        # حذف درخواست‌های قدیمی
        user_requests[:] = [req_time for req_time in user_requests if req_time > window_start]
        
        # بررسی محدودیت
        if len(user_requests) >= max_requests:
            return False
        
        # اضافه کردن درخواست جدید
        user_requests.append(now)
        return True
    
    def _cleanup_old_requests(self):
        """🧹 پاک‌سازی درخواست‌های قدیمی"""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        for user_id in list(self.requests.keys()):
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id] 
                if req_time > cutoff
            ]
            
            # حذف کاربرانی که درخواستی ندارند
            if not self.requests[user_id]:
                del self.requests[user_id]
        
        self.last_cleanup = now

class ProgressTracker:
    """📊 ردیابی پیشرفت"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
    def start_task(self, task_id: str, description: str = "", total: int = 100):
        """🚀 شروع وظیفه جدید"""
        self.tasks[task_id] = {
            'description': description,
            'current': 0,
            'total': total,
            'percentage': 0.0,
            'status': 'running',
            'started_at': datetime.now(),
            'updated_at': datetime.now()
        }
    
    def update_task(self, task_id: str, current: int, status: str = "running"):
        """🔄 بروزرسانی وظیفه"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task['current'] = current
        task['status'] = status
        task['percentage'] = (current / task['total'] * 100) if task['total'] > 0 else 0
        task['updated_at'] = datetime.now()
    
    def complete_task(self, task_id: str, status: str = "completed"):
        """✅ تکمیل وظیفه"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task['status'] = status
            task['percentage'] = 100.0
            task['updated_at'] = datetime.now()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """📋 دریافت اطلاعات وظیفه"""
        return self.tasks.get(task_id)
    
    def remove_task(self, task_id: str):
        """🗑️ حذف وظیفه"""
        self.tasks.pop(task_id, None)

# نمونه‌های global
rate_limiter = RateLimiter()
progress_tracker = ProgressTracker()

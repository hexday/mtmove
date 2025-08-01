import os
import asyncio
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import tempfile
import cv2
from PIL import Image

from telegram import Bot
from telegram.error import TelegramError, NetworkError, TimedOut

from config import config
from utils import Utils

logger = logging.getLogger(__name__)

class FileManager:
    """📁 مدیریت فایل‌ها"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.temp_path = Path(config.TEMP_PATH)
        self.downloads_path = Path(config.DOWNLOADS_PATH)
        
        # ایجاد دایرکتوری‌ها
        self.temp_path.mkdir(exist_ok=True)
        self.downloads_path.mkdir(exist_ok=True)
        
        # تنظیمات آپلود
        self.max_retries = 3
        self.retry_delay = 2
    
    async def upload_to_telegram(self, file_path: str, caption: str = "", 
                               parse_mode: str = "HTML", 
                               progress_callback=None) -> Optional[int]:
        """⬆️ آپلود فایل به کانال خصوصی تلگرام"""
        if not os.path.exists(file_path):
            logger.error(f"❌ فایل وجود ندارد: {file_path}")
            return None
        
        file_size = os.path.getsize(file_path)
        
        if file_size > config.MAX_FILE_SIZE:
            logger.error(f"❌ فایل بیش از حد بزرگ است: {Utils.format_file_size(file_size)}")
            return None
        
        if file_size == 0:
            logger.error(f"❌ فایل خالی است: {file_path}")
            return None
        
        # تولید تامبنیل
        thumbnail_path = None
        if Utils.is_video_file(file_path):
            thumbnail_path = await self.generate_thumbnail(file_path)
        
        # تلاش برای آپلود با retry
        for attempt in range(self.max_retries):
            try:
                if progress_callback:
                    progress_callback(f"⬆️ آپلود فایل (تلاش {attempt + 1}/{self.max_retries})...")
                
                # انتخاب روش آپلود بر اساس حجم
                if file_size > 50 * 1024 * 1024:  # بیشتر از 50MB
                    message = await self._upload_as_document(file_path, caption, parse_mode, thumbnail_path)
                else:
                    message = await self._upload_as_video(file_path, caption, parse_mode, thumbnail_path)
                
                if message:
                    logger.info(f"✅ فایل آپلود شد: message_id={message.message_id}")
                    return message.message_id
                
            except (NetworkError, TimedOut) as e:
                logger.warning(f"⚠️ خطای شبکه در تلاش {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error("❌ همه تلاش‌ها ناکام بود")
                    
            except Exception as e:
                logger.error(f"❌ خطا در آپلود: {e}")
                break
            
            finally:
                # حذف تامبنیل موقت
                if thumbnail_path:
                    await Utils.safe_delete_file(thumbnail_path)
        
        return None
    
    async def _upload_as_document(self, file_path: str, caption: str, 
                                parse_mode: str, thumbnail_path: Optional[str]) -> Optional:
        """📄 آپلود به عنوان document"""
        with open(file_path, 'rb') as file:
            thumbnail_file = None
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumbnail_file = open(thumbnail_path, 'rb')
            
            try:
                message = await self.bot.send_document(
                    chat_id=config.PRIVATE_CHANNEL_ID,
                    document=file,
                    caption=caption[:1024],  # محدودیت تلگرام
                    parse_mode=parse_mode,
                    thumbnail=thumbnail_file,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
                return message
                
            finally:
                if thumbnail_file:
                    thumbnail_file.close()
    
    async def _upload_as_video(self, file_path: str, caption: str,
                             parse_mode: str, thumbnail_path: Optional[str]) -> Optional:
        """🎥 آپلود به عنوان video"""
        duration = await self.get_video_duration(file_path)
        width, height = await self.get_video_dimensions(file_path)
        
        with open(file_path, 'rb') as file:
            thumbnail_file = None
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumbnail_file = open(thumbnail_path, 'rb')
            
            try:
                message = await self.bot.send_video(
                    chat_id=config.PRIVATE_CHANNEL_ID,
                    video=file,
                    duration=duration,
                    width=width,
                    height=height,
                    caption=caption[:1024],
                    parse_mode=parse_mode,
                    thumbnail=thumbnail_file,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
                return message
                
            finally:
                if thumbnail_file:
                    thumbnail_file.close()
    
    async def generate_thumbnail(self, video_path: str, time_offset: int = 10) -> Optional[str]:
        """🖼️ تولید تامبنیل از ویدیو"""
        try:
            thumbnail_name = f"thumb_{Utils.generate_unique_code(8)}.jpg"
            thumbnail_path = self.temp_path / thumbnail_name
            
            # روش اول: FFmpeg
            if await self._generate_thumbnail_ffmpeg(video_path, str(thumbnail_path), time_offset):
                return str(thumbnail_path)
            
            # روش دوم: OpenCV
            if await self._generate_thumbnail_opencv(video_path, str(thumbnail_path), time_offset):
                return str(thumbnail_path)
            
            logger.warning("⚠️ نتوانست تامبنیل تولید کند")
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در تولید تامبنیل: {e}")
            return None
    
    async def _generate_thumbnail_ffmpeg(self, video_path: str, output_path: str, 
                                       time_offset: int) -> bool:
        """🎬 تولید تامبنیل با FFmpeg"""
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(time_offset),
                '-vframes', '1',
                '-vf', 'scale=320:240:force_original_aspect_ratio=decrease',
                '-q:v', '2',
                '-y',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            try:
                await asyncio.wait_for(process.communicate(), timeout=30)
            except asyncio.TimeoutError:
                process.kill()
                return False
            
            if process.returncode == 0 and os.path.exists(output_path):
                await self._optimize_thumbnail(output_path)
                return True
                
        except FileNotFoundError:
            logger.warning("⚠️ FFmpeg یافت نشد")
        except Exception as e:
            logger.warning(f"⚠️ خطا در FFmpeg: {e}")
        
        return False
    
    async def _generate_thumbnail_opencv(self, video_path: str, output_path: str,
                                       time_offset: int) -> bool:
        """📹 تولید تامبنیل با OpenCV"""
        try:
            def extract_frame():
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return False
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps > 0:
                    frame_number = int(fps * time_offset)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    # تغییر اندازه
                    height, width = frame.shape[:2]
                    if width > 320:
                        ratio = 320 / width
                        new_width = 320
                        new_height = int(height * ratio)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    return True
                
                return False
            
            # اجرا در thread pool
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, extract_frame)
            
            if success:
                await self._optimize_thumbnail(output_path)
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ خطا در OpenCV: {e}")
        
        return False
    
    async def _optimize_thumbnail(self, thumbnail_path: str):
        """✨ بهینه‌سازی تامبنیل"""
        try:
            with Image.open(thumbnail_path) as img:
                # تبدیل به RGB اگر ضروری باشد
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # تنظیم اندازه
                img.thumbnail((320, 240), Image.Resampling.LANCZOS)
                
                # ذخیره با کیفیت بهینه
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                
        except Exception as e:
            logger.warning(f"⚠️ خطا در بهینه‌سازی تامبنیل: {e}")
    
    async def get_video_duration(self, video_path: str) -> int:
        """⏱️ دریافت مدت زمان ویدیو"""
        try:
            # روش اول: FFmpeg
            duration = await self._get_duration_ffmpeg(video_path)
            if duration > 0:
                return duration
            
            # روش دوم: OpenCV
            return await self._get_duration_opencv(video_path)
            
        except Exception as e:
            logger.warning(f"⚠️ خطا در دریافت مدت زمان: {e}")
            return 0
    
    async def _get_duration_ffmpeg(self, video_path: str) -> int:
        """⏱️ دریافت مدت زمان با FFmpeg"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                duration_str = stdout.decode().strip()
                return int(float(duration_str))
                
        except Exception:
            pass
        
        return 0
    
    async def _get_duration_opencv(self, video_path: str) -> int:
        """⏱️ دریافت مدت زمان با OpenCV"""
        try:
            def get_duration():
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return 0
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                
                if fps > 0:
                    return int(frame_count / fps)
                return 0
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, get_duration)
            
        except Exception:
            return 0
    
    async def get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        """📐 دریافت ابعاد ویدیو"""
        try:
            def get_dimensions():
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return 0, 0
                
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                
                return width, height
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, get_dimensions)
            
        except Exception:
            return 0, 0
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """ℹ️ دریافت اطلاعات فایل"""
        try:
            file_stat = os.stat(file_path)
            
            return {
                'size': file_stat.st_size,
                'type': Utils.get_file_type(file_path),
                'extension': Path(file_path).suffix.lower(),
                'name': Path(file_path).name,
                'stem': Path(file_path).stem,
                'created': datetime.fromtimestamp(file_stat.st_ctime),
                'modified': datetime.fromtimestamp(file_stat.st_mtime),
                'is_video': Utils.is_video_file(file_path)
            }
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات فایل: {e}")
            return {}
    
    async def cleanup_temp_files(self, max_age_hours: int = 24):
        """🧹 پاک‌سازی فایل‌های موقت قدیمی"""
        try:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=max_age_hours)
            
            cleaned_count = 0
            
            for directory in [self.temp_path, self.downloads_path]:
                if not directory.exists():
                    continue
                
                for file_path in directory.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    try:
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug(f"🗑️ فایل قدیمی حذف شد: {file_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ خطا در حذف {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"🧹 {cleaned_count} فایل موقت پاک شد")
                
        except Exception as e:
            logger.error(f"❌ خطا در پاک‌سازی: {e}")
    
    async def get_temp_file_path(self, filename: str) -> str:
        """📁 دریافت مسیر فایل موقت"""
        clean_filename = Utils.clean_filename(filename)
        return str(self.temp_path / clean_filename)
    
    async def get_download_file_path(self, filename: str) -> str:
        """📁 دریافت مسیر فایل دانلود"""
        clean_filename = Utils.clean_filename(filename)
        return str(self.downloads_path / clean_filename)

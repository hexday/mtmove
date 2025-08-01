import os
import asyncio
import aiohttp
import aiofiles
import logging
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
import subprocess
import tempfile
import json
import re

import yt_dlp
from config import config
from utils import Utils, progress_tracker

logger = logging.getLogger(__name__)

class DownloadManager:
    """⬇️ مدیریت دانلود فایل‌ها"""
    
    def __init__(self):
        self.active_downloads: Dict[str, Dict] = {}
        self.download_semaphore = asyncio.Semaphore(3)  # حداکثر 3 دانلود همزمان
        self.session: Optional[aiohttp.ClientSession] = None
        self.yt_dlp_lock = asyncio.Lock()
        
        # تنظیمات دانلود
        self.chunk_size = 8192
        self.timeout = aiohttp.ClientTimeout(total=config.DOWNLOAD_TIMEOUT)
        self.max_retries = 3
        self.retry_delay = 5
    
    async def __aenter__(self):
        """🚪 ورود به context manager"""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """🚪 خروج از context manager"""
        await self.close_session()
    
    async def start_session(self):
        """🚀 شروع session HTTP"""
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=50,
                limit_per_host=10,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            logger.info("✅ HTTP session شروع شد")
    
    async def close_session(self):
        """🔒 بستن session HTTP"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 HTTP session بسته شد")
    
    async def download_video(self, url: str, output_dir: str, 
                           quality: str = "720p",
                           progress_callback: Optional[Callable] = None) -> Optional[str]:
        """📹 دانلود ویدیو با انتخاب بهترین روش"""
        
        if not Utils.validate_url(url):
            logger.error(f"❌ URL نامعتبر: {url}")
            return None
        
        download_id = Utils.generate_unique_code(8)
        
        async with self.download_semaphore:
            try:
                # ثبت دانلود فعال
                self.active_downloads[download_id] = {
                    'url': url,
                    'quality': quality,
                    'status': 'starting',
                    'progress': 0,
                    'started_at': asyncio.get_event_loop().time()
                }
                
                if progress_callback:
                    progress_callback("🔍 تشخیص نوع لینک...")
                
                # انتخاب روش دانلود
                if self._is_youtube_url(url):
                    result = await self._download_with_ytdlp(url, output_dir, quality, progress_callback)
                elif self._is_direct_video_url(url):
                    result = await self._download_direct(url, output_dir, progress_callback)
                else:
                    # تلاش با yt-dlp برای سایر پلتفرم‌ها
                    result = await self._download_with_ytdlp(url, output_dir, quality, progress_callback)
                
                if result:
                    self.active_downloads[download_id]['status'] = 'completed'
                    logger.info(f"✅ دانلود موفق: {result}")
                else:
                    self.active_downloads[download_id]['status'] = 'failed'
                    logger.error(f"❌ دانلود ناموفق: {url}")
                
                return result
                
            except Exception as e:
                self.active_downloads[download_id]['status'] = 'error'
                logger.error(f"❌ خطا در دانلود {url}: {e}")
                return None
            
            finally:
                # حذف از لیست دانلودهای فعال
                self.active_downloads.pop(download_id, None)
    
    def _is_youtube_url(self, url: str) -> bool:
        """📺 بررسی یوتیوب بودن URL"""
        youtube_domains = [
            'youtube.com', 'youtu.be', 'youtube-nocookie.com',
            'm.youtube.com', 'music.youtube.com'
        ]
        return any(domain in url.lower() for domain in youtube_domains)
    
    def _is_direct_video_url(self, url: str) -> bool:
        """🎬 بررسی لینک مستقیم ویدیو بودن"""
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        url_lower = url.lower()
        
        # بررسی پسوند در URL
        for ext in video_extensions:
            if ext in url_lower:
                return True
        
        return False
    
    async def _download_with_ytdlp(self, url: str, output_dir: str, 
                                  quality: str, progress_callback: Optional[Callable]) -> Optional[str]:
        """📺 دانلود با yt-dlp"""
        async with self.yt_dlp_lock:  # جلوگیری از تداخل
            try:
                if progress_callback:
                    progress_callback("⚙️ تنظیم yt-dlp...")
                
                # تنظیمات yt-dlp
                ydl_opts = {
                    'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
                    'format': self._get_ytdlp_format(quality),
                    'quiet': True,
                    'no_warnings': False,
                    'extractaudio': False,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['fa', 'en', 'ar'],
                    'ignoreerrors': True,
                    'no_check_certificate': True,
                    'socket_timeout': 60,
                    'retries': 3,
                }
                
                # پیشرفت callback
                if progress_callback:
                    ydl_opts['progress_hooks'] = [self._create_ytdlp_progress_hook(progress_callback)]
                
                # اجرای yt-dlp در executor
                loop = asyncio.get_event_loop()
                
                def download_sync():
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            # دریافت اطلاعات ابتدا
                            info = ydl.extract_info(url, download=False)
                            if not info:
                                return None
                            
                            # بررسی حجم فایل
                            filesize = info.get('filesize') or info.get('filesize_approx', 0)
                            if filesize > config.MAX_FILE_SIZE:
                                logger.error(f"❌ فایل بیش از حد بزرگ: {Utils.format_file_size(filesize)}")
                                return None
                            
                            # دانلود فایل
                            ydl.download([url])
                            
                            # پیدا کردن فایل دانلود شده
                            filename = ydl.prepare_filename(info)
                            
                            # بررسی فایل‌های موجود در صورت تغییر نام
                            if not os.path.exists(filename):
                                base_name = os.path.splitext(filename)[0]
                                for ext in ['.mp4', '.mkv', '.webm', '.flv']:
                                    test_file = base_name + ext
                                    if os.path.exists(test_file):
                                        filename = test_file
                                        break
                            
                            return filename if os.path.exists(filename) else None
                            
                    except Exception as e:
                        logger.error(f"❌ خطا در yt-dlp: {e}")
                        return None
                
                # اجرا با timeout
                filename = await asyncio.wait_for(
                    loop.run_in_executor(None, download_sync),
                    timeout=config.DOWNLOAD_TIMEOUT
                )
                
                if filename and os.path.exists(filename):
                    # تمیز کردن نام فایل
                    clean_filename = Utils.clean_filename(os.path.basename(filename))
                    clean_path = os.path.join(output_dir, clean_filename)
                    
                    if filename != clean_path:
                        os.rename(filename, clean_path)
                        filename = clean_path
                    
                    if progress_callback:
                        progress_callback("✅ دانلود تکمیل شد")
                    
                    return filename
                
                return None
                
            except asyncio.TimeoutError:
                logger.error("❌ timeout در دانلود با yt-dlp")
                return None
            except Exception as e:
                logger.error(f"❌ خطا در دانلود با yt-dlp: {e}")
                return None
    
    def _get_ytdlp_format(self, quality: str) -> str:
        """📊 تبدیل کیفیت به فرمت yt-dlp"""
        quality_map = {
            '480p': 'best[height<=480]/worst',
            '720p': 'best[height<=720]/best[height<=1080]/worst',
            '1080p': 'best[height<=1080]/best',
            '1440p': 'best[height<=1440]/best',
            '4k': 'best[height<=2160]/best'
        }
        return quality_map.get(quality, 'best[height<=720]/worst')
    
    def _create_ytdlp_progress_hook(self, callback: Callable):
        """📊 ایجاد hook پیشرفت برای yt-dlp"""
        def hook(d):
            try:
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    
                    if total > 0:
                        percentage = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        
                        if speed:
                            speed_str = Utils.format_file_size(speed) + "/s"
                            callback(f"⬇️ دانلود: {percentage:.1f}% ({speed_str})")
                        else:
                            callback(f"⬇️ دانلود: {percentage:.1f}%")
                
                elif d['status'] == 'finished':
                    callback("⚙️ پردازش نهایی...")
                    
            except Exception as e:
                logger.warning(f"⚠️ خطا در progress hook: {e}")
        
        return hook
    
    async def _download_direct(self, url: str, output_dir: str,
                             progress_callback: Optional[Callable]) -> Optional[str]:
        """🔗 دانلود مستقیم"""
        await self.start_session()
        
        try:
            if progress_callback:
                progress_callback("🚀 شروع دانلود مستقیم...")
            
            # دریافت نام فایل از URL
            filename = self._extract_filename_from_url(url)
            if not filename:
                filename = f"video_{Utils.generate_unique_code(6)}.mp4"
            
            filepath = os.path.join(output_dir, Utils.clean_filename(filename))
            
            # دانلود با retry mechanism
            for attempt in range(self.max_retries):
                try:
                    if attempt > 0:
                        if progress_callback:
                            progress_callback(f"🔄 تلاش مجدد {attempt + 1}/{self.max_retries}...")
                        await asyncio.sleep(self.retry_delay)
                    
                    async with self.session.get(url) as response:
                        if response.status != 200:
                            logger.warning(f"⚠️ HTTP {response.status} برای {url}")
                            continue
                        
                        total_size = int(response.headers.get('content-length', 0))
                        
                        if total_size > config.MAX_FILE_SIZE:
                            logger.error(f"❌ فایل بیش از حد بزرگ: {Utils.format_file_size(total_size)}")
                            return None
                        
                        downloaded = 0
                        
                        async with aiofiles.open(filepath, 'wb') as file:
                            async for chunk in response.content.iter_chunked(self.chunk_size):
                                await file.write(chunk)
                                downloaded += len(chunk)
                                
                                if progress_callback and total_size > 0:
                                    percentage = (downloaded / total_size) * 100
                                    progress_callback(f"⬇️ دانلود: {percentage:.1f}%")
                        
                        if progress_callback:
                            progress_callback("✅ دانلود تکمیل شد")
                        
                        return filepath
                        
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"⚠️ خطا در تلاش {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در دانلود مستقیم: {e}")
            return None
    
    def _extract_filename_from_url(self, url: str) -> Optional[str]:
        """📁 استخراج نام فایل از URL"""
        try:
            # حذف query parameters
            url_clean = url.split('?')[0].split('#')[0]
            
            # استخراج نام فایل
            filename = os.path.basename(url_clean)
            
            # بررسی وجود پسوند ویدیو
            if any(ext in filename.lower() for ext in config.SUPPORTED_VIDEO_FORMATS):
                return filename
            
            # اضافه کردن پسوند پیشفرض
            return filename + '.mp4' if filename else None
            
        except Exception:
            return None
    
    async def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """ℹ️ دریافت اطلاعات ویدیو بدون دانلود"""
        try:
            if not Utils.validate_url(url):
                return None
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
            }
            
            loop = asyncio.get_event_loop()
            
            def extract_info_sync():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)
                except Exception as e:
                    logger.warning(f"⚠️ خطا در استخراج اطلاعات: {e}")
                    return None
            
            info = await asyncio.wait_for(
                loop.run_in_executor(None, extract_info_sync),
                timeout=60
            )
            
            if not info:
                return None
            
            # پردازش اطلاعات
            processed_info = {
                'title': info.get('title', 'نامشخص'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date'),
                'formats': self._process_formats(info.get('formats', []))
            }
            
            return processed_info
            
        except asyncio.TimeoutError:
            logger.error("❌ timeout در دریافت اطلاعات ویدیو")
            return None
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات ویدیو: {e}")
            return None
    
    def _process_formats(self, formats: List[Dict]) -> Dict[str, Any]:
        """📊 پردازش فرمت‌های موجود"""
        available_qualities = {}
        
        for fmt in formats:
            if not fmt.get('vcodec') or fmt.get('vcodec') == 'none':
                continue  # صرفاً صوتی
            
            height = fmt.get('height', 0)
            filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
            
            # تعیین کیفیت
            quality = None
            if height <= 480:
                quality = '480p'
            elif height <= 720:
                quality = '720p'
            elif height <= 1080:
                quality = '1080p'
            elif height <= 1440:
                quality = '1440p'
            else:
                quality = '4k'
            
            if quality and (quality not in available_qualities or 
                          filesize > available_qualities[quality].get('filesize', 0)):
                available_qualities[quality] = {
                    'filesize': filesize,
                    'format_id': fmt.get('format_id'),
                    'ext': fmt.get('ext', 'mp4'),
                    'fps': fmt.get('fps', 0),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec')
                }
        
        return available_qualities
    
    async def download_thumbnail(self, url: str, output_dir: str) -> Optional[str]:
        """🖼️ دانلود تامبنیل"""
        await self.start_session()
        
        try:
            filename = f"thumb_{Utils.generate_unique_code(8)}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(filepath, 'wb') as file:
                        async for chunk in response.content.iter_chunked(self.chunk_size):
                            await file.write(chunk)
                    
                    return filepath
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در دانلود تامبنیل: {e}")
            return None
    
    def get_active_downloads(self) -> Dict[str, Dict]:
        """📊 دریافت لیست دانلودهای فعال"""
        return self.active_downloads.copy()
    
    def cancel_download(self, download_id: str) -> bool:
        """⏹️ لغو دانلود"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'cancelled'
            return True
        return False
    
    async def cleanup_partial_files(self, directory: str):
        """🧹 پاک‌سازی فایل‌های ناقص"""
        try:
            if not os.path.exists(directory):
                return
            
            partial_extensions = ['.part', '.tmp', '.ytdl']
            cleaned_count = 0
            
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                
                if any(filename.endswith(ext) for ext in partial_extensions):
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                        logger.debug(f"🗑️ فایل ناقص حذف شد: {filename}")
                    except Exception as e:
                        logger.warning(f"⚠️ خطا در حذف {filename}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"🧹 {cleaned_count} فایل ناقص پاک شد")
                
        except Exception as e:
            logger.error(f"❌ خطا در پاک‌سازی فایل‌های ناقص: {e}")

# نمونه global
download_manager = DownloadManager()

import asyncio
import logging
from typing import Optional, List
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import db
from models import Video, Collection, DownloadLog, User
from ui_manager import ui_manager
from utils import Utils, rate_limiter
from config import config

logger = logging.getLogger(__name__)

class UserPanel:
    """👤 پنل کاربری"""
    
    def __init__(self):
        self.ui = ui_manager
        self.search_cache = {}  # کش جستجو
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🚀 مدیریت دستور /start"""
        user_id = update.effective_user.id
        args = context.args
        
        # ثبت یا بروزرسانی کاربر
        await self._register_or_update_user(update.effective_user)
        
        # بررسی دیپ لینک
        if args and len(args) > 0:
            start_param = args[0]
            unique_code = Utils.parse_deeplink(start_param)
            
            if unique_code:
                await self.show_video_by_code(update, context, unique_code)
                return
        
        # تشخیص نوع کاربر و نمایش منوی مناسب
        if await db.is_admin(user_id):
            await self._show_admin_start_menu(update, context)
        else:
            await self.show_user_menu(update, context)
    
    async def _show_admin_start_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """👨‍💼 نمایش منوی شروع برای ادمین"""
        try:
            # وارد کردن admin_panel اینجا برای جلوگیری از circular import
            from handlers import admin_panel
            
            if admin_panel:
                await admin_panel.show_admin_panel(update, context)
            else:
                # fallback برای حالتی که admin_panel هنوز آماده نیست
                await self._show_admin_fallback_menu(update, context)
                
        except Exception as e:
            logger.error(f"خطا در نمایش منوی ادمین: {e}")
            await update.message.reply_text("خطا در بارگذاری پنل ادمین")
    
    async def _show_admin_fallback_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔄 منوی جایگزین برای ادمین"""
        keyboard = self.ui.get_admin_main_menu()
        
        welcome_text = f"""
🎬 <b>خوش آمدید ادمین عزیز</b>

━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ <b>وضعیت سیستم:</b>
🟡 در حال بارگذاری...

⏳ لطفاً چند لحظه صبر کنید تا تمام ماژول‌ها آماده شوند.

⚠️ <i>اگر مشکل ادامه داشت، ربات را ریستارت کنید.</i>

━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def show_user_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🏠 نمایش منوی کاربر"""
        user = update.effective_user
        name = user.first_name or user.username or "کاربر"
        
        welcome_text = f"""
🍿 <b>خوش آمدید {Utils.escape_markdown(name)}!</b>

━━━━━━━━━━━━━━━━━━━━━━━━

🎬 <b>به ربات فیلم و سریال خوش آمدید</b>

از منوی زیر می‌توانید:

🔍 <b>جستجو:</b> فیلم و سریال مورد نظرتان را پیدا کنید
🆕 <b>جدیدترین‌ها:</b> آخرین محتواهای اضافه شده را ببینید  
🎭 <b>دسته‌بندی:</b> فیلم‌ها و سریال‌های مختلف را مرور کنید

━━━━━━━━━━━━━━━━━━━━━━━━

💡 <b>نکته:</b> برای دریافت فایل‌ها روی لینک‌های ارسالی کلیک کنید

🎯 <i>محتوای جدید روزانه اضافه می‌شود!</i>
"""
        
        keyboard = self.ui.get_user_main_menu()
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    # === نمایش ویدیو با کد یکتا ===
    
    async def show_video_by_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               unique_code: str):
        """🎬 نمایش ویدیو با کد یکتا"""
        user_id = update.effective_user.id
        
        # بررسی rate limiting
        if not rate_limiter.is_allowed(user_id, config.RATE_LIMIT, 60):
            await update.message.reply_text(
                "⏳ <b>درخواست‌های زیاد</b>\n\n"
                "تعداد درخواست‌های شما در دقیقه گذشته زیاد بوده است.\n\n"
                "⏰ لطفاً یک دقیقه صبر کنید و دوباره تلاش کنید.",
                parse_mode="HTML"
            )
            return
        
        try:
            # جستجوی ویدیو
            video = await db.get_video_by_code(unique_code)
            if not video:
                await update.message.reply_text(
                    "❌ <b>ویدیو یافت نشد</b>\n\n"
                    "احتمالاً لینک منقضی شده یا حذف شده است.\n\n"
                    "💡 <b>راهکار:</b>\n"
                    "• از منوی اصلی جستجو کنید\n"
                    "• لیست جدیدترین‌ها را بررسی کنید",
                    parse_mode="HTML"
                )
                return
            
            # دریافت اطلاعات مجموعه
            collection = await db.get_collection(video.collection_id)
            if not collection or collection.status != "active":
                await update.message.reply_text(
                    "❌ <b>محتوا در دسترس نیست</b>\n\n"
                    "این محتوا در حال حاضر غیرفعال یا حذف شده است.\n\n"
                    "🔄 لطفاً بعداً تلاش کنید.",
                    parse_mode="HTML"
                )
                return
            
            # دریافت ویدیوهای دیگر همان کیفیت
            collection_videos = await db.get_collection_videos(video.collection_id)
            available_qualities = list(set([
                v.quality for v in collection_videos 
                if v.season == video.season and v.episode == video.episode
            ]))
            
            # افزایش تعداد بازدید
            await self._increment_view_count(video.collection_id)
            
            # فرمت کردن پیام
            message_text = self.ui.format_video_details(video, collection)
            keyboard = self.ui.get_video_detail_keyboard(unique_code, available_qualities)
            
            # ارسال پیام با کاور
            await self._send_video_details(update, collection, message_text, keyboard)
            
            # ارسال تریلر اگر موجود باشد
            if collection.trailer_file_id:
                try:
                    await update.message.reply_video(
                        video=collection.trailer_file_id,
                        caption="🎬 <b>تریلر</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"خطا در ارسال تریلر: {e}")
            
        except Exception as e:
            logger.error(f"خطا در نمایش ویدیو {unique_code}: {e}")
            await update.message.reply_text(
                "❌ <b>خطا در نمایش اطلاعات</b>\n\n"
                "متأسفانه مشکلی در بارگذاری اطلاعات رخ داده است.\n\n"
                "🔄 لطفاً بعداً تلاش کنید.",
                parse_mode="HTML"
            )
    
    async def _send_video_details(self, update: Update, collection: Collection, 
                                message_text: str, keyboard):
        """📤 ارسال جزئیات ویدیو"""
        try:
            if collection.cover_file_id:
                await update.message.reply_photo(
                    photo=collection.cover_file_id,
                    caption=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.warning(f"خطا در ارسال جزئیات ویدیو: {e}")
            # fallback به متن ساده
            await update.message.reply_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    
    async def _increment_view_count(self, collection_id: str):
        """👁️ افزایش تعداد بازدید"""
        try:
            await db.update_collection(collection_id, {
                "total_views": {"$inc": 1}
            })
        except Exception as e:
            logger.warning(f"خطا در افزایش بازدید: {e}")
    
    # === مدیریت درخواست دانلود ===
    
    async def handle_download_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """⬇️ مدیریت درخواست دانلود"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer("📥 در حال پردازش درخواست...")
        
        # بررسی rate limiting
        if not rate_limiter.is_allowed(user_id, config.RATE_LIMIT, 60):
            await query.answer(
                "⏳ تعداد درخواست‌های شما زیاد است",
                show_alert=True
            )
            return
        
        # تجزیه callback data
        try:
            parts = query.data.split("_")
            if len(parts) != 3 or parts[0] != "download":
                await query.answer("❌ درخواست نامعتبر", show_alert=True)
                return
            
            _, unique_code, quality = parts
            
        except Exception:
            await query.answer("❌ خطا در پردازش درخواست", show_alert=True)
            return
        
        # یافتن ویدیو
        try:
            video = await db.get_video_by_code(unique_code)
            if not video:
                await query.answer("❌ ویدیو یافت نشد", show_alert=True)
                return
            
            # یافتن ویدیو با کیفیت درخواستی
            collection_videos = await db.get_collection_videos(video.collection_id)
            requested_video = None
            
            for v in collection_videos:
                if (v.season == video.season and v.episode == video.episode and 
                    v.quality == quality):
                    requested_video = v
                    break
            
            if not requested_video:
                await query.answer("❌ کیفیت درخواستی موجود نیست", show_alert=True)
                return
            
            # ارسال فایل
            await self._send_video_file(query, user_id, requested_video, quality)
            
        except Exception as e:
            logger.error(f"خطا در پردازش دانلود: {e}")
            await query.answer("❌ خطا در پردازش درخواست", show_alert=True)
    
    async def _send_video_file(self, query, user_id: int, video: Video, quality: str):
        """📤 ارسال فایل ویدیو"""
        try:
            # پیام انتظار
            waiting_message = await query.message.reply_text(
                f"⬇️ <b>در حال ارسال فایل...</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 <b>کیفیت:</b> <code>{quality}</code>\n"
                f"💾 <b>حجم:</b> <code>{Utils.format_file_size(video.file_size)}</code>\n"
                f"⏱️ <b>مدت:</b> <code>{Utils.format_duration(video.duration)}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏳ <i>لطفاً صبر کنید، فایل در حال ارسال است...</i>",
                parse_mode="HTML"
            )
            
            # فوروارد فایل از کانال خصوصی
            forwarded_message = await query.bot.forward_message(
                chat_id=user_id,
                from_chat_id=config.PRIVATE_CHANNEL_ID,
                message_id=video.message_id
            )
            
            if forwarded_message:
                # موفقیت‌آمیز بود
                await self._log_successful_download(user_id, video, quality)
                
                # پیام موفقیت
                success_text = f"""
✅ <b>فایل با موفقیت ارسال شد!</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>مشخصات فایل:</b>
📱 <b>کیفیت:</b> <code>{quality}</code>
💾 <b>حجم:</b> <code>{Utils.format_file_size(video.file_size)}</code>
⏱️ <b>مدت زمان:</b> <code>{Utils.format_duration(video.duration)}</code>

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>نکات مفید:</b>
• فایل تا 48 ساعت قابل دانلود است
• برای کیفیت بهتر از WiFi استفاده کنید
• در صورت قطع شدن، مجدداً تلاش کنید

━━━━━━━━━━━━━━━━━━━━━━━━

🙏 <i>از استفاده از ربات سپاسگزاریم!</i>

💫 <b>محتوای بیشتری در راه است...</b>
"""
                
                await waiting_message.edit_text(
                    success_text,
                    parse_mode="HTML"
                )
                
            else:
                await waiting_message.edit_text(
                    "❌ <b>خطا در ارسال فایل</b>\n\n"
                    "متأسفانه مشکلی در ارسال فایل رخ داده است.\n\n"
                    "🔄 لطفاً دوباره تلاش کنید.",
                    parse_mode="HTML"
                )
                
        except Exception as e:
            logger.error(f"خطا در ارسال فایل: {e}")
            try:
                await query.message.reply_text(
                    "❌ <b>خطا در ارسال فایل</b>\n\n"
                    f"جزئیات: <code>{str(e)}</code>\n\n"
                    "🔄 لطفاً بعداً تلاش کنید.",
                    parse_mode="HTML"
                )
            except:
                pass
    
    async def _log_successful_download(self, user_id: int, video: Video, quality: str):
        """📝 ثبت دانلود موفق"""
        try:
            # افزایش تعداد دانلود ویدیو
            await db.increment_download_count(video._id)
            
            # افزایش تعداد دانلود مجموعه
            await db.update_collection(video.collection_id, {
                "total_downloads": {"$inc": 1}
            })
            
            # ثبت لاگ دانلود
            await db.log_download(DownloadLog(
                user_id=user_id,
                video_id=video._id,
                collection_id=video.collection_id,
                quality=quality,
                file_size=video.file_size
            ))
            
            # بروزرسانی آمار کاربر
            await db.update_user_stats(user_id)
            
        except Exception as e:
            logger.warning(f"خطا در ثبت لاگ دانلود: {e}")
    
    # === جستجو ===
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔍 شروع جستجو"""
        await update.message.reply_text(
            "🔍 <b>جستجو در فیلم‌ها و سریال‌ها</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 نام فیلم یا سریال مورد نظر خود را وارد کنید:\n\n"
            "💡 <b>راهنمای جستجو:</b>\n"
            "• از نام فارسی یا انگلیسی استفاده کنید\n"
            "• کلمات کلیدی وارد کنید\n"
            "• از قسمتی از نام نیز می‌توانید استفاده کنید\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>مثال: آواتار، بازی تاج و تخت، Breaking Bad</i>",
            parse_mode="HTML"
        )
        # TODO: پیاده‌سازی کامل جستجو
    
    # === نمایش محتوای دسته‌بندی شده ===
    
    async def handle_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🆕 نمایش جدیدترین محتوا"""
        user_id = update.effective_user.id
        
        # بررسی rate limiting
        if not rate_limiter.is_allowed(user_id, config.RATE_LIMIT // 2, 60):
            await update.message.reply_text(
                "⏳ لطفاً کمی صبر کنید...",
                parse_mode="HTML"
            )
            return
        
        try:
            collections = await db.get_collections(limit=10)
            
            if not collections:
                await update.message.reply_text(
                    "🆕 <b>جدیدترین محتواها</b>\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📚 هنوز محتوایی اضافه نشده است\n\n"
                    "⏰ به زودی فیلم‌ها و سریال‌های جدید اضافه خواهند شد.\n\n"
                    "🔔 برای اطلاع از جدیدترین‌ها در کانال ما عضو شوید.",
                    parse_mode="HTML"
                )
                return
            
            message_text = "🆕 <b>جدیدترین محتواها:</b>\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, collection in enumerate(collections, 1):
                type_emoji = self.ui._get_type_emoji(collection.type)
                
                line = f"{i}. {type_emoji} <b>{Utils.escape_markdown(collection.name)}</b>"
                
                # اضافه کردن سال
                if collection.year:
                    line += f" <code>({collection.year})</code>"
                
                # اضافه کردن امتیاز
                if collection.imdb_rating:
                    stars = "⭐" * min(int(collection.imdb_rating / 2), 5)
                    line += f" {stars} <code>{collection.imdb_rating}</code>"
                
                message_text += line + "\n\n"
            
            message_text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "<i>📱 برای دریافت فیلم‌ها از لینک‌های ارسالی استفاده کنید.</i>\n"
            message_text += "<i>🔄 این لیست روزانه بروزرسانی می‌شود.</i>"
            
            await update.message.reply_text(
                message_text,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"خطا در نمایش جدیدترین محتوا: {e}")
            await update.message.reply_text(
                "❌ <b>خطا در بارگذاری محتوا</b>\n\n"
                "متأسفانه مشکلی در بارگذاری اطلاعات رخ داده است.\n\n"
                "🔄 لطفاً بعداً تلاش کنید.",
                parse_mode="HTML"
            )
    
    async def handle_movies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎬 نمایش فیلم‌ها"""
        await self._show_content_by_type(update, "movie", "🎬 فیلم‌های موجود")
    
    async def handle_series(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📺 نمایش سریال‌ها"""
        await self._show_content_by_type(update, "series", "📺 سریال‌های موجود")
    
    async def handle_mini_series(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎭 نمایش مینی‌سریال‌ها"""
        await self._show_content_by_type(update, "mini_series", "🎭 مینی‌سریال‌های موجود")
    
    async def handle_documentaries(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎪 نمایش مستندات"""
        await self._show_content_by_type(update, "documentary", "🎪 مستندهای موجود")
    
    async def _show_content_by_type(self, update: Update, content_type: str, title: str):
        """📋 نمایش محتوا بر اساس نوع"""
        user_id = update.effective_user.id
        
        # بررسی rate limiting
        if not rate_limiter.is_allowed(user_id, config.RATE_LIMIT // 2, 60):
            await update.message.reply_text(
                "⏳ لطفاً کمی صبر کنید...",
                parse_mode="HTML"
            )
            return
        
        try:
            collections = await db.get_collections(content_type=content_type, limit=15)
            
            if not collections:
                await update.message.reply_text(
                    f"<b>{title}</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"❌ در این دسته محتوایی یافت نشد\n\n"
                    f"⏰ به زودی محتوای جدید اضافه خواهد شد.\n"
                    f"🔔 برای اطلاع از جدیدترین‌ها در کانال ما عضو شوید.",
                    parse_mode="HTML"
                )
                return
            
            message_text = f"<b>{title}:</b>\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, collection in enumerate(collections, 1):
                line = f"{i}. <b>{Utils.escape_markdown(collection.name)}</b>"
                
                # اطلاعات اضافی
                info_parts = []
                if collection.year:
                    info_parts.append(f"📅 {collection.year}")
                if collection.genre:
                    info_parts.append(f"🎭 {collection.genre}")
                if collection.imdb_rating:
                    info_parts.append(f"⭐ {collection.imdb_rating}")
                
                if info_parts:
                    line += f"\n   <i>{' | '.join(info_parts)}</i>"
                
                message_text += line + "\n\n"
            
            message_text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += f"📊 <b>تعداد:</b> <code>{len(collections)}</code> مورد\n\n"
            message_text += "<i>📱 برای دریافت فایل‌ها از لینک‌های ارسالی استفاده کنید.</i>"
            
            await update.message.reply_text(
                message_text,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"خطا در نمایش {content_type}: {e}")
            await update.message.reply_text(
                "❌ <b>خطا در بارگذاری محتوا</b>\n\n"
                "متأسفانه مشکلی در بارگذاری اطلاعات رخ داده است.\n\n"
                "🔄 لطفاً بعداً تلاش کنید.",
                parse_mode="HTML"
            )
    
    # === راهنما ===
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ℹ️ نمایش راهنما"""
        help_text = """
ℹ️ <b>راهنمای استفاده از ربات</b>

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>نحوه استفاده:</b>
<code>1️⃣</code> روی لینک ارسال شده کلیک کنید
<code>2️⃣</code> کیفیت دلخواه را انتخاب کنید  
<code>3️⃣</code> فایل برای شما ارسال می‌شود

━━━━━━━━━━━━━━━━━━━━━━━━

🔍 <b>جستجو:</b>
• از دکمه "جستجو" استفاده کنید
• نام فارسی یا انگلیسی فیلم را وارد کنید
• از قسمت‌هایی از نام نیز می‌توانید استفاده کنید

━━━━━━━━━━━━━━━━━━━━━━━━

📱 <b>کیفیت‌های موجود:</b>
• <b>480p</b> 📱 - مناسب موبایل (حجم کم)
• <b>720p</b> 🖥️ - کیفیت استاندارد (توصیه می‌شود)  
• <b>1080p</b> 🔥 - کیفیت بالا (حجم زیاد)
• <b>1440p</b> ⚡ - کیفیت خیلی بالا
• <b>4K</b> 👑 - بهترین کیفیت (حجم خیلی زیاد)

━━━━━━━━━━━━━━━━━━━━━━━━

💡 <b>نکات مهم:</b>
• کیفیت بالاتر = حجم بیشتر + سرعت کمتر
• برای موبایل از 720p یا کمتر استفاده کنید
• فایل‌ها تا 48 ساعت قابل دانلود هستند
• از WiFi برای دانلود فایل‌های بزرگ استفاده کنید

━━━━━━━━━━━━━━━━━━━━━━━━

🆘 <b>مشکل دارید؟</b>
از دکمه "پشتیبانی" استفاده کنید یا با ادمین تماس بگیرید.

━━━━━━━━━━━━━━━━━━━━━━━━

🙏 <b>از استفاده شما سپاسگزاریم!</b>
💫 <i>محتوای جدید روزانه اضافه می‌شود</i>
"""
        
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    # === پشتیبانی ===
    
    async def handle_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📞 پشتیبانی"""
        support_text = """
📞 <b>پشتیبانی و راهنمایی</b>

━━━━━━━━━━━━━━━━━━━━━━━━

🔗 <b>راه‌های ارتباط:</b>
• آیدی ادمین: <code>@admin_username</code>
• کانال اطلاع‌رسانی: <code>@channel_username</code>
• گروه پشتیبانی: <code>@support_group</code>

━━━━━━━━━━━━━━━━━━━━━━━━

⏰ <b>ساعت پاسخگویی:</b>
شنبه تا پنج‌شنبه: <code>9 صبح تا 21 شب</code>
جمعه: <code>14 تا 20</code>

━━━━━━━━━━━━━━━━━━━━━━━━

❓ <b>سوالات متداول:</b>

<b>Q:</b> چرا فایل دانلود نمی‌شود؟
<b>A:</b> اتصال اینترنت و فضای خالی دستگاه را بررسی کنید

<b>Q:</b> کیفیت مورد نظر موجود نیست؟
<b>A:</b> احتمالاً هنوز آپلود نشده است

<b>Q:</b> لینک کار نمی‌کند؟
<b>A:</b> ممکن است منقضی شده باشد

<b>Q:</b> چگونه درخواست فیلم دهم؟
<b>A:</b> از طریق پشتیبانی با ادمین در میان بگذارید

━━━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>مشارکت:</b>
اگر فیلم یا سریال خاصی می‌خواهید، از طریق پشتیبانی اطلاع دهید.

━━━━━━━━━━━━━━━━━━━━━━━━

📢 <b>کانال ما را دنبال کنید تا از جدیدترین فیلم‌ها باخبر شوید!</b>

💖 <i>نظرات و پیشنهادات شما برای ما ارزشمند است</i>
"""
        
        await update.message.reply_text(support_text, parse_mode="HTML")
    
    # === توابع کمکی ===
    
    async def _register_or_update_user(self, telegram_user):
        """👤 ثبت یا بروزرسانی کاربر"""
        try:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name or "",
                last_name=telegram_user.last_name or "",
                language_code=telegram_user.language_code or "fa"
            )
            
            await db.create_or_update_user(user)
            
        except Exception as e:
            logger.warning(f"خطا در ثبت کاربر {telegram_user.id}: {e}")

# نمونه global
user_panel = UserPanel()

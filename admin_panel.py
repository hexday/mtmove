import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError

from database import db
from models import Collection, Video, ContentType, AdminLog, UploadTask, Status
from ui_manager import ui_manager
from file_manager import FileManager
from download_manager import download_manager
from utils import Utils, progress_tracker
from config import config

logger = logging.getLogger(__name__)

class AdminPanel:
    """👨‍💼 پنل مدیریت ادمین"""
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.ui = ui_manager
        self.temp_data: Dict[int, Dict[str, Any]] = {}
        
        # وضعیت‌های مکالمه
        self.WAITING_COLLECTION_NAME = 0
        self.WAITING_COLLECTION_YEAR = 1
        self.WAITING_COLLECTION_GENRE = 2
        self.WAITING_COLLECTION_RATING = 3
        self.WAITING_COLLECTION_DESCRIPTION = 4
        self.WAITING_COLLECTION_COVER = 5
        self.WAITING_COLLECTION_TRAILER = 6
        self.WAITING_UPLOAD_URLS = 7
        self.WAITING_UPLOAD_QUALITY = 8
        self.WAITING_EPISODE_INFO = 9
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🏠 نمایش پنل اصلی ادمین"""
        user_id = update.effective_user.id
        
        if not await db.is_admin(user_id):
            await update.message.reply_text("❌ شما به این بخش دسترسی ندارید")
            return
        
        # بروزرسانی آخرین فعالیت
        await self._update_admin_activity(user_id, "access_admin_panel")
        
        keyboard = self.ui.get_admin_main_menu()
        welcome_message = self._get_admin_welcome_message(update.effective_user)
        
        try:
            await update.message.reply_text(
                welcome_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"خطا در نمایش پنل ادمین: {e}")
            await update.message.reply_text("خطا در بارگذاری پنل ادمین")
    
    def _get_admin_welcome_message(self, user) -> str:
        """💬 پیام خوشامدگویی ادمین"""
        name = user.first_name or user.username or "ادمین"
        current_time = datetime.now().strftime("%H:%M")
        
        return f"""
🎬 <b>خوش آمدید {Utils.escape_markdown(name)} عزیز</b>

⏰ زمان: <code>{current_time}</code>
🤖 وضعیت ربات: <b>✅ فعال و آماده</b>
💾 پایگاه داده: <b>🟢 متصل</b>

<i>از منوی زیر گزینه مورد نظر را انتخاب کنید:</i>

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # === مدیریت محتوا ===
    
    async def handle_content_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎬 مدیریت محتوا"""
        query = update.callback_query if update.callback_query else None
        user_id = update.effective_user.id
        
        if query:
            await query.answer()
        
        await self._update_admin_activity(user_id, "access_content_management")
        
        keyboard = self.ui.get_content_management_menu()
        message_text = """
🎬 <b>پنل مدیریت محتوا</b>

━━━━━━━━━━━━━━━━━━━━━━━━

از گزینه‌های زیر انتخاب کنید:

🎯 <b>عملیات اصلی:</b>
• <i>ایجاد مجموعه:</i> برای افزودن فیلم/سریال جدید
• <i>مجموعه‌های موجود:</i> مشاهده و مدیریت محتوای موجود
• <i>آپلود فایل:</i> آپلود مستقیم فایل‌ها

📊 <b>تحلیل و گزارش:</b>
• <i>آمار محتوا:</i> بررسی عملکرد و آمار
• <i>مدیریت وضعیت:</i> کنترل فعال/غیرفعال

━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        try:
            if query:
                await query.edit_message_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"خطا در نمایش مدیریت محتوا: {e}")
    
    # === ایجاد مجموعه ===
    
    async def start_create_collection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🚀 شروع ایجاد مجموعه جدید"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer("🎬 شروع ایجاد مجموعه...")
        await self._update_admin_activity(user_id, "start_create_collection")
        
        # پاک کردن داده‌های قبلی
        self.temp_data.pop(user_id, None)
        
        keyboard = self.ui.get_collection_type_keyboard()
        
        await query.edit_message_text(
            "🎬 <b>ایجاد مجموعه جدید</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎭 <b>مرحله ۱:</b> انتخاب نوع محتوا\n\n"
            "<i>لطفاً نوع محتوایی که می‌خواهید اضافه کنید را انتخاب کنید:</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_NAME
    
    async def handle_collection_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎭 انتخاب نوع مجموعه"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        if query.data == "cancel_operation":
            await self.handle_content_management(update, context)
            return ConversationHandler.END
        
        collection_type = query.data.replace("type_", "")
        
        # ذخیره در داده‌های موقت
        self.temp_data[user_id] = {
            "type": collection_type,
            "created_at": datetime.now()
        }
        
        type_names = {
            "movie": "🎬 فیلم سینمایی",
            "series": "📺 سریال", 
            "mini_series": "🎭 مینی‌سریال",
            "documentary": "🎪 مستند"
        }
        
        selected_type = type_names.get(collection_type, "نامشخص")
        
        await query.edit_message_text(
            f"✅ <b>نوع انتخاب شد:</b> {selected_type}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 <b>مرحله ۲:</b> تعیین نام مجموعه\n\n"
            f"<i>حالا نام {selected_type} را وارد کنید:</i>\n\n"
            f"💡 <b>نکته:</b> نام باید حداقل 2 کاراکتر و حداکثر 100 کاراکتر باشد",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_YEAR
    
    async def handle_collection_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📝 دریافت نام مجموعه"""
        user_id = update.effective_user.id
        collection_name = update.message.text.strip()
        
        # اعتبارسنجی
        if len(collection_name) < 2:
            await update.message.reply_text(
                "❌ <b>خطا:</b> نام مجموعه باید حداقل 2 کاراکتر باشد\n\n"
                "📝 لطفاً دوباره وارد کنید:",
                parse_mode="HTML"
            )
            return self.WAITING_COLLECTION_YEAR
        
        if len(collection_name) > 100:
            await update.message.reply_text(
                "❌ <b>خطا:</b> نام مجموعه نباید از 100 کاراکتر بیشتر باشد\n\n"
                "📝 لطفاً نام کوتاه‌تری وارد کنید:",
                parse_mode="HTML"
            )
            return self.WAITING_COLLECTION_YEAR
        
        self.temp_data[user_id]["name"] = collection_name
        
        await update.message.reply_text(
            f"✅ <b>نام ثبت شد:</b> {Utils.escape_markdown(collection_name)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 <b>مرحله ۳:</b> سال تولید (اختیاری)\n\n"
            f"لطفاً سال تولید را وارد کنید (مثال: <code>2023</code>)\n"
            f"یا <code>/skip</code> برای رد کردن:",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_GENRE
    
    async def handle_collection_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📅 دریافت سال تولید"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        year = None
        
        if text.lower() != "/skip":
            try:
                year = int(text)
                if year < 1900 or year > 2030:
                    await update.message.reply_text(
                        "❌ <b>خطا:</b> سال باید بین 1900 تا 2030 باشد\n\n"
                        "📅 لطفاً دوباره وارد کنید یا <code>/skip</code> بزنید:",
                        parse_mode="HTML"
                    )
                    return self.WAITING_COLLECTION_GENRE
            except ValueError:
                await update.message.reply_text(
                    "❌ <b>خطا:</b> سال باید عدد باشد (مثال: <code>2023</code>)\n\n"
                    "📅 لطفاً دوباره وارد کنید یا <code>/skip</code> بزنید:",
                    parse_mode="HTML"
                )
                return self.WAITING_COLLECTION_GENRE
        
        self.temp_data[user_id]["year"] = year
        
        year_display = f"<code>{year}</code>" if year else "<i>نامشخص</i>"
        
        await update.message.reply_text(
            f"✅ <b>سال ثبت شد:</b> {year_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎭 <b>مرحله ۴:</b> ژانر (اختیاری)\n\n"
            f"ژانر محتوا را وارد کنید (مثال: <code>اکشن، درام</code>)\n"
            f"یا <code>/skip</code> برای رد کردن:",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_RATING
    
    async def handle_collection_genre(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎭 دریافت ژانر"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        genre = None if text.lower() == "/skip" else text[:50]  # محدود به 50 کاراکتر
        self.temp_data[user_id]["genre"] = genre
        
        genre_display = f"<code>{Utils.escape_markdown(genre)}</code>" if genre else "<i>نامشخص</i>"
        
        await update.message.reply_text(
            f"✅ <b>ژانر ثبت شد:</b> {genre_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⭐ <b>مرحله ۵:</b> امتیاز IMDb (اختیاری)\n\n"
            f"امتیاز IMDb را وارد کنید (مثال: <code>8.5</code>)\n"
            f"یا <code>/skip</code> برای رد کردن:\n\n"
            f"💡 <b>نکته:</b> امتیاز باید بین 0 تا 10 باشد",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_DESCRIPTION
    
    async def handle_collection_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """⭐ دریافت امتیاز IMDb"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        rating = None
        
        if text.lower() != "/skip":
            try:
                rating = float(text)
                if rating < 0 or rating > 10:
                    await update.message.reply_text(
                        "❌ <b>خطا:</b> امتیاز باید بین 0 تا 10 باشد\n\n"
                        "⭐ لطفاً دوباره وارد کنید یا <code>/skip</code> بزنید:",
                        parse_mode="HTML"
                    )
                    return self.WAITING_COLLECTION_DESCRIPTION
            except ValueError:
                await update.message.reply_text(
                    "❌ <b>خطا:</b> امتیاز باید عدد باشد (مثال: <code>8.5</code>)\n\n"
                    "⭐ لطفاً دوباره وارد کنید یا <code>/skip</code> بزنید:",
                    parse_mode="HTML"
                )
                return self.WAITING_COLLECTION_DESCRIPTION
        
        self.temp_data[user_id]["imdb_rating"] = rating
        
        rating_display = f"<code>{rating}</code> ⭐" if rating else "<i>نامشخص</i>"
        
        await update.message.reply_text(
            f"✅ <b>امتیاز IMDb ثبت شد:</b> {rating_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 <b>مرحله ۶:</b> توضیحات و خلاصه (اختیاری)\n\n"
            f"توضیحات و خلاصه داستان را وارد کنید\n"
            f"یا <code>/skip</code> برای رد کردن:\n\n"
            f"💡 <b>نکته:</b> حداکثر 1000 کاراکتر",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_COVER
    
    async def handle_collection_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📝 دریافت توضیحات"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        description = None if text.lower() == "/skip" else text[:1000]  # محدود به 1000 کاراکتر
        self.temp_data[user_id]["description"] = description
        
        desc_status = "✅ ثبت شد" if description else "⏭️ رد شد"
        
        await update.message.reply_text(
            f"{desc_status} <b>توضیحات</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🖼️ <b>مرحله ۷:</b> عکس کاور (اختیاری)\n\n"
            f"عکس کاور را ارسال کنید\n"
            f"یا <code>/skip</code> برای رد کردن:\n\n"
            f"💡 <b>توصیه:</b> نسبت 16:9 و حداکثر 10MB",
            parse_mode="HTML"
        )
        
        return self.WAITING_COLLECTION_TRAILER
    
    async def handle_collection_cover(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🖼️ دریافت کاور"""
        user_id = update.effective_user.id
        
        cover_file_id = None
        
        if update.message.text and update.message.text.strip().lower() == "/skip":
            pass  # رد کردن کاور
        elif update.message.photo:
            # انتخاب بهترین کیفیت عکس
            photo = update.message.photo[-1]
            
            # بررسی حجم عکس
            if photo.file_size and photo.file_size > 10 * 1024 * 1024:  # 10MB
                await update.message.reply_text(
                    "❌ <b>خطا:</b> حجم عکس نباید از 10MB بیشتر باشد\n\n"
                    "🖼️ لطفاً عکس کوچک‌تری ارسال کنید یا <code>/skip</code> بزنید:",
                    parse_mode="HTML"
                )
                return self.WAITING_COLLECTION_TRAILER
            
            cover_file_id = photo.file_id
        else:
            await update.message.reply_text(
                "❌ <b>خطا:</b> لطفاً عکس ارسال کنید یا <code>/skip</code> بزنید",
                parse_mode="HTML"
            )
            return self.WAITING_COLLECTION_TRAILER
        
        self.temp_data[user_id]["cover_file_id"] = cover_file_id
        
        cover_status = "✅ ثبت شد" if cover_file_id else "⏭️ رد شد"
        
        await update.message.reply_text(
            f"{cover_status} <b>کاور</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎬 <b>مرحله ۸:</b> ویدیو تریلر (اختیاری)\n\n"
            f"ویدیو تریلر را ارسال کنید (حداکثر 50MB)\n"
            f"یا <code>/finish</code> برای تکمیل بدون تریلر:\n\n"
            f"💡 <b>نکته:</b> تریلر کوتاه و جذاب انتخاب کنید",
            parse_mode="HTML"
        )
        
        return ConversationHandler.END
    
    async def handle_collection_trailer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎬 دریافت تریلر و تکمیل ایجاد مجموعه"""
        user_id = update.effective_user.id
        
        trailer_file_id = None
        
        if update.message.text and update.message.text.strip().lower() == "/finish":
            pass  # تکمیل بدون تریلر
        elif update.message.video:
            video = update.message.video
            
            # بررسی حجم ویدیو
            if video.file_size and video.file_size > 50 * 1024 * 1024:  # 50MB
                await update.message.reply_text(
                    "❌ <b>خطا:</b> حجم تریلر نباید از 50MB بیشتر باشد\n\n"
                    "🎬 لطفاً ویدیو کوچک‌تری ارسال کنید یا <code>/finish</code> بزنید:",
                    parse_mode="HTML"
                )
                return ConversationHandler.END
            
            trailer_file_id = video.file_id
        else:
            await update.message.reply_text(
                "❌ <b>خطا:</b> لطفاً ویدیو ارسال کنید یا <code>/finish</code> برای تکمیل بزنید",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        self.temp_data[user_id]["trailer_file_id"] = trailer_file_id
        
        # ایجاد مجموعه
        await self._create_collection_from_temp_data(user_id, update)
        
        return ConversationHandler.END
    
    async def _create_collection_from_temp_data(self, user_id: int, update: Update):
        """💾 ایجاد مجموعه از داده‌های موقت"""
        try:
            if user_id not in self.temp_data:
                await update.message.reply_text("❌ داده‌های مجموعه یافت نشد")
                return
            
            data = self.temp_data[user_id]
            
            # نمایش پیام در حال پردازش
            processing_msg = await update.message.reply_text(
                "⏳ <b>در حال ایجاد مجموعه...</b>\n\n"
                "🔄 لطفاً صبر کنید...",
                parse_mode="HTML"
            )
            
            # ایجاد مجموعه
            collection = Collection(
                name=data["name"],
                type=ContentType(data["type"]),
                year=data.get("year"),
                genre=data.get("genre", ""),
                imdb_rating=data.get("imdb_rating"),
                description=data.get("description", ""),
                cover_file_id=data.get("cover_file_id"),
                trailer_file_id=data.get("trailer_file_id"),
                created_by=user_id,
                status=Status.ACTIVE
            )
            
            # ذخیره در پایگاه داده
            collection_id = await db.create_collection(collection)
            
            if collection_id:
                # ثبت لاگ ادمین
                await db.log_admin_action(AdminLog(
                    admin_id=user_id,
                    action="create_collection",
                    target_type="collection",
                    target_id=collection_id,
                    description=f"مجموعه '{collection.name}' ایجاد شد",
                    details={"type": collection.type.value, "year": collection.year}
                ))
                
                # پیام موفقیت
                success_message = f"""
✅ <b>مجموعه با موفقیت ایجاد شد!</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📛 <b>نام:</b> <code>{Utils.escape_markdown(collection.name)}</code>
🎬 <b>نوع:</b> {self._get_type_name(collection.type)}
🆔 <b>شناسه:</b> <code>{collection_id}</code>
📅 <b>تاریخ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M')}</code>

━━━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>مراحل بعدی:</b>
• آپلود فایل‌های ویدیو
• تنظیم کیفیت‌های مختلف
• بررسی و تأیید نهایی

<i>حالا می‌توانید فایل‌ها را به این مجموعه اضافه کنید.</i>
"""
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬆️ آپلود فایل", callback_data=f"upload_to_collection_{collection_id}")],
                    [InlineKeyboardButton("👀 مشاهده مجموعه", callback_data=f"collection_{collection_id}")],
                    [InlineKeyboardButton("➕ ایجاد مجموعه جدید", callback_data="create_collection")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="content_management")]
                ])
                
                await processing_msg.edit_text(
                    success_message,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await processing_msg.edit_text(
                    "❌ <b>خطا در ایجاد مجموعه</b>\n\n"
                    "متأسفانه مشکلی در ذخیره‌سازی رخ داده است.\n"
                    "لطفاً دوباره تلاش کنید."
                )
            
        except Exception as e:
            logger.error(f"خطا در ایجاد مجموعه: {e}")
            await update.message.reply_text(
                "❌ <b>خطا در ایجاد مجموعه</b>\n\n"
                f"جزئیات: <code>{str(e)}</code>\n\n"
                "لطفاً دوباره تلاش کنید.",
                parse_mode="HTML"
            )
        
        finally:
            # پاک کردن داده‌های موقت
            self.temp_data.pop(user_id, None)
    
    @staticmethod
    def _get_type_name(content_type: ContentType) -> str:
        """🎭 تبدیل نوع محتوا به نام فارسی"""
        type_names = {
            ContentType.MOVIE: "🎬 فیلم سینمایی",
            ContentType.SERIES: "📺 سریال",
            ContentType.MINI_SERIES: "🎭 مینی‌سریال",
            ContentType.DOCUMENTARY: "🎪 مستند"
        }
        return type_names.get(content_type, "❓ نامشخص")
    
    # === مشاهده مجموعه‌ها ===
    
    async def show_collections(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📚 نمایش مجموعه‌ها"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        await self._update_admin_activity(user_id, "view_collections")
        
        # تشخیص صفحه
        page = 0
        if query.data.startswith("collections_page_"):
            try:
                page = int(query.data.split("_")[-1])
            except (ValueError, IndexError):
                page = 0
        
        # دریافت مجموعه‌ها
        collections = await db.get_collections(skip=0, limit=100)  # همه مجموعه‌ها برای صفحه‌بندی
        
        if not collections:
            no_collections_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ایجاد اولین مجموعه", callback_data="create_collection")],
                [InlineKeyboardButton("📊 راهنمای شروع", callback_data="getting_started")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="content_management")]
            ])
            
            await query.edit_message_text(
                "📚 <b>مجموعه‌ای یافت نشد</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🎬 هنوز هیچ مجموعه‌ای ایجاد نشده است\n\n"
                "🚀 <b>برای شروع:</b>\n"
                "• اولین مجموعه خود را ایجاد کنید\n"
                "• راهنمای کامل را مطالعه کنید\n\n"
                "<i>با ایجاد مجموعه‌ها، کاربران می‌توانند محتوا دریافت کنند.</i>",
                reply_markup=no_collections_keyboard,
                parse_mode="HTML"
            )
            return
        
        # ایجاد کیبورد صفحه‌بندی شده
        keyboard = self.ui.get_collections_keyboard(collections, page)
        total_count = len(collections)
        
        message_text = f"""
📚 <b>مجموعه‌های موجود</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>آمار کلی:</b>
• تعداد کل: <code>{total_count}</code> مجموعه
• صفحه فعلی: <code>{page + 1}</code> از <code>{(total_count + 4) // 5}</code>
• آخرین بروزرسانی: <code>{datetime.now().strftime('%H:%M')}</code>

━━━━━━━━━━━━━━━━━━━━━━━━

<i>برای مشاهده جزئیات، روی مجموعه مورد نظر کلیک کنید:</i>
"""
        
        try:
            await query.edit_message_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"خطا در نمایش مجموعه‌ها: {e}")
    
    # === جزئیات مجموعه ===
    
    async def show_collection_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📋 نمایش جزئیات مجموعه"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        collection_id = query.data.split("_")[1]
        
        # دریافت مجموعه
        collection = await db.get_collection(collection_id)
        if not collection:
            await query.answer("❌ مجموعه یافت نشد", show_alert=True)
            return
        
        # دریافت ویدیوهای مجموعه
        videos = await db.get_collection_videos(collection_id)
        
        await self._update_admin_activity(user_id, "view_collection_detail", {"collection_id": collection_id})
        
        # فرمت کردن پیام
        message_text = self.ui.format_collection_details(collection, videos)
        keyboard = self.ui.get_collection_detail_keyboard(collection_id, collection)
        
        try:
            # ارسال کاور اگر موجود باشد
            if collection.cover_file_id:
                await query.message.reply_photo(
                    photo=collection.cover_file_id,
                    caption=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                # حذف پیام قبلی
                try:
                    await query.message.delete()
                except:
                    pass
            else:
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                
        except TelegramError as e:
            logger.error(f"خطا در نمایش جزئیات مجموعه: {e}")
            # fallback به متن ساده
            await query.edit_message_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    
    # === آمار و گزارش ===
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 نمایش آمار"""
        query = update.callback_query if update.callback_query else None
        user_id = update.effective_user.id
        
        if query:
            await query.answer("📊 در حال بارگذاری آمار...")
        
        await self._update_admin_activity(user_id, "view_statistics")
        
        try:
            # دریافت آمار از پایگاه داده
            stats = await db.get_statistics()
            
            # فرمت کردن پیام آمار
            stats_text = self.ui.format_statistics(stats)
            
            # کیبورد عملیات
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_statistics"),
                    InlineKeyboardButton("📈 آمار تفصیلی", callback_data="detailed_statistics")
                ],
                [
                    InlineKeyboardButton("📋 گزارش کامل", callback_data="full_report"),
                    InlineKeyboardButton("📊 نمودار", callback_data="statistics_chart")
                ],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
            ])
            
            if query:
                await query.edit_message_text(
                    stats_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    stats_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                
        except Exception as e:
            logger.error(f"خطا در نمایش آمار: {e}")
            error_text = "❌ <b>خطا در دریافت آمار</b>\n\n" \
                        "متأسفانه مشکلی در دریافت اطلاعات رخ داده است.\n" \
                        "لطفاً بعداً تلاش کنید."
            
            if query:
                await query.edit_message_text(error_text, parse_mode="HTML")
            else:
                await update.message.reply_text(error_text, parse_mode="HTML")
    
    # === توابع کمکی ===
    
    async def _update_admin_activity(self, admin_id: int, action: str, details: Dict[str, Any] = None):
        """📝 ثبت فعالیت ادمین"""
        try:
            await db.log_admin_action(AdminLog(
                admin_id=admin_id,
                action=action,
                target_type="system",
                target_id="",
                description=f"ادمین {admin_id} عملیات {action} را انجام داد",
                details=details or {}
            ))
        except Exception as e:
            logger.warning(f"خطا در ثبت فعالیت ادمین: {e}")
    
    async def handle_cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """❌ لغو عملیات"""
        user_id = update.effective_user.id
        
        # پاک کردن داده‌های موقت
        self.temp_data.pop(user_id, None)
        
        await self.handle_content_management(update, context)
        return ConversationHandler.END

# نمونه global
admin_panel = None  # خواهد شد در handlers مقداردهی شود

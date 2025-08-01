from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from typing import List, Dict, Any, Optional
import logging

from models import Collection, Video, ContentType, VideoQuality, Status
from utils import Utils

logger = logging.getLogger(__name__)

class UIManager:
    """🎨 مدیریت رابط کاربری"""
    
    def __init__(self):
        self.items_per_page = 5
        self.max_button_text_length = 30
    
    # === کیبوردهای اصلی ===
    
    @staticmethod
    def get_admin_main_menu() -> ReplyKeyboardMarkup:
        """👨‍💼 منوی اصلی ادمین"""
        keyboard = [
            [KeyboardButton("🎬 مدیریت محتوا"), KeyboardButton("📊 آمار و گزارش")],
            [KeyboardButton("⬆️ آپلود سریع"), KeyboardButton("👥 مدیریت کاربران")],
            [KeyboardButton("⚙️ تنظیمات"), KeyboardButton("📋 لاگ‌ها")]
        ]
        return ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder="🔧 گزینه مورد نظر را انتخاب کنید..."
        )
    
    @staticmethod
    def get_user_main_menu() -> ReplyKeyboardMarkup:
        """👤 منوی اصلی کاربر"""
        keyboard = [
            [KeyboardButton("🔍 جستجو"), KeyboardButton("🆕 جدیدترین‌ها")],
            [KeyboardButton("🎬 فیلم‌ها"), KeyboardButton("📺 سریال‌ها")],
            [KeyboardButton("🎭 مینی‌سریال"), KeyboardButton("🎪 مستندات")],
            [KeyboardButton("ℹ️ راهنما"), KeyboardButton("📞 پشتیبانی")]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder="🍿 چی دنبالش میگردی؟"
        )
    
    # === کیبوردهای مدیریت محتوا ===
    
    def get_content_management_menu(self) -> InlineKeyboardMarkup:
        """🎬 منوی مدیریت محتوا"""
        keyboard = [
            [InlineKeyboardButton("➕ ایجاد مجموعه جدید", callback_data="create_collection")],
            [InlineKeyboardButton("📚 مجموعه‌های موجود", callback_data="view_collections")],
            [InlineKeyboardButton("⬆️ آپلود فایل", callback_data="upload_menu")],
            [InlineKeyboardButton("📊 آمار محتوا", callback_data="content_stats")],
            [InlineKeyboardButton("🔄 مدیریت وضعیت", callback_data="manage_status")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_collection_type_keyboard(self) -> InlineKeyboardMarkup:
        """🎭 کیبورد انتخاب نوع مجموعه"""
        keyboard = [
            [InlineKeyboardButton("🎬 فیلم سینمایی", callback_data="type_movie")],
            [InlineKeyboardButton("📺 سریال", callback_data="type_series")],
            [InlineKeyboardButton("🎭 مینی‌سریال", callback_data="type_mini_series")],
            [InlineKeyboardButton("🎪 مستند", callback_data="type_documentary")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_operation")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_collections_keyboard(self, collections: List[Collection], 
                                page: int = 0, per_page: int = None) -> InlineKeyboardMarkup:
        """📚 کیبورد نمایش مجموعه‌ها با صفحه‌بندی"""
        if per_page is None:
            per_page = self.items_per_page
        
        keyboard = []
        
        # محاسبه محدوده صفحه
        start = page * per_page
        end = start + per_page
        page_collections = collections[start:end]
        
        # نمایش مجموعه‌ها
        for collection in page_collections:
            type_emoji = self._get_type_emoji(collection.type)
            status_emoji = self._get_status_emoji(collection.status)
            
            # محدود کردن طول متن دکمه
            name = collection.name
            if len(name) > self.max_button_text_length:
                name = name[:self.max_button_text_length-3] + "..."
            
            button_text = f"{type_emoji}{status_emoji} {name}"
            
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"collection_{collection._id}")
            ])
        
        # دکمه‌های ناوبری
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ قبلی", callback_data=f"collections_page_{page-1}")
            )
        
        page_count = (len(collections) + per_page - 1) // per_page
        if page_count > 1:
            nav_buttons.append(
                InlineKeyboardButton(f"📄 {page + 1}/{page_count}", callback_data="page_info")
            )
        
        if (page + 1) * per_page < len(collections):
            nav_buttons.append(
                InlineKeyboardButton("▶️ بعدی", callback_data=f"collections_page_{page+1}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # دکمه‌های عملیات
        keyboard.extend([
            [
                InlineKeyboardButton("🔍 جستجو", callback_data="search_collections"),
                InlineKeyboardButton("🔄 بارگذاری مجدد", callback_data="refresh_collections")
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="content_management")]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_collection_detail_keyboard(self, collection_id: str, 
                                     collection: Collection = None) -> InlineKeyboardMarkup:
        """📋 کیبورد جزئیات مجموعه"""
        keyboard = [
            [
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_collection_{collection_id}"),
                InlineKeyboardButton("📎 فایل‌ها", callback_data=f"manage_files_{collection_id}")
            ],
            [
                InlineKeyboardButton("📊 آمار", callback_data=f"collection_stats_{collection_id}"),
                InlineKeyboardButton("🔗 لینک‌ها", callback_data=f"collection_links_{collection_id}")
            ],
            [
                InlineKeyboardButton("⬆️ آپلود جدید", callback_data=f"upload_to_collection_{collection_id}"),
                InlineKeyboardButton("📋 کپی", callback_data=f"copy_collection_{collection_id}")
            ]
        ]
        
        # دکمه تغییر وضعیت
        if collection:
            if collection.status == Status.ACTIVE:
                keyboard.append([
                    InlineKeyboardButton("⏸️ غیرفعال کردن", callback_data=f"deactivate_collection_{collection_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("▶️ فعال کردن", callback_data=f"activate_collection_{collection_id}")
                ])
        
        keyboard.extend([
            [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_collection_{collection_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="view_collections")]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    # === کیبوردهای آپلود ===
    
    def get_upload_menu_keyboard(self, collections: List[Collection]) -> InlineKeyboardMarkup:
        """⬆️ منوی آپلود"""
        keyboard = []
        
        if collections:
            keyboard.append([
                InlineKeyboardButton("📁 انتخاب مجموعه موجود", callback_data="select_existing_collection")
            ])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ ایجاد مجموعه جدید", callback_data="create_collection_for_upload")],
            [InlineKeyboardButton("📋 آپلود دسته‌ای", callback_data="batch_upload")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="content_management")]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_quality_selection_keyboard(self, available_qualities: List[str], 
                                     allow_multiple: bool = True) -> InlineKeyboardMarkup:
        """📺 کیبورد انتخاب کیفیت"""
        keyboard = []
        
        quality_data = {
            '480p': {'emoji': '📱', 'desc': 'موبایل'},
            '720p': {'emoji': '🖥️', 'desc': 'استاندارد'},
            '1080p': {'emoji': '🔥', 'desc': 'بالا'},
            '1440p': {'emoji': '⚡', 'desc': 'خیلی بالا'},
            '4k': {'emoji': '👑', 'desc': 'بهترین'}
        }
        
        # نمایش کیفیت‌های موجود
        for quality in available_qualities:
            if quality in quality_data:
                data = quality_data[quality]
                button_text = f"{data['emoji']} {quality} - {data['desc']}"
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"quality_{quality}")
                ])
        
        # دکمه انتخاب همه (اگر مجاز باشد)
        if allow_multiple and len(available_qualities) > 1:
            keyboard.append([
                InlineKeyboardButton("✨ تمام کیفیت‌ها", callback_data="quality_all")
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ لغو", callback_data="cancel_operation")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    # === کیبوردهای کاربر ===
    
    def get_video_detail_keyboard(self, video_code: str, 
                                available_qualities: List[str]) -> InlineKeyboardMarkup:
        """🎬 کیبورد جزئیات ویدیو برای کاربر"""
        keyboard = []
        
        if len(available_qualities) == 1:
            # تنها یک کیفیت موجود است
            quality = available_qualities[0]
            emoji = self._get_quality_emoji(quality)
            keyboard.append([
                InlineKeyboardButton(
                    f"⬇️ دانلود {emoji} {quality}", 
                    callback_data=f"download_{video_code}_{quality}"
                )
            ])
        else:
            # چند کیفیت موجود است
            for quality in available_qualities:
                emoji = self._get_quality_emoji(quality)
                keyboard.append([
                    InlineKeyboardButton(
                        f"⬇️ {emoji} {quality}", 
                        callback_data=f"download_{video_code}_{quality}"
                    )
                ])
        
        # دکمه‌های اضافی
        keyboard.extend([
            [
                InlineKeyboardButton("📤 اشتراک‌گذاری", callback_data=f"share_{video_code}"),
                InlineKeyboardButton("⭐ علاقه‌مندی", callback_data=f"favorite_{video_code}")
            ],
            [InlineKeyboardButton("📊 اطلاعات بیشتر", callback_data=f"info_{video_code}")]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_search_results_keyboard(self, results: List[Collection], 
                                  query: str, page: int = 0) -> InlineKeyboardMarkup:
        """🔍 کیبورد نتایج جستجو"""
        keyboard = []
        
        start = page * self.items_per_page
        end = start + self.items_per_page
        page_results = results[start:end]
        
        for collection in page_results:
            type_emoji = self._get_type_emoji(collection.type)
            name = collection.name
            
            if len(name) > self.max_button_text_length:
                name = name[:self.max_button_text_length-3] + "..."
            
            if collection.year:
                name += f" ({collection.year})"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{type_emoji} {name}", 
                    callback_data=f"view_collection_{collection._id}"
                )
            ])
        
        # ناوبری
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ قبلی", callback_data=f"search_page_{query}_{page-1}")
            )
        if end < len(results):
            nav_buttons.append(
                InlineKeyboardButton("▶️ بعدی", callback_data=f"search_page_{query}_{page+1}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("🔍 جستجوی جدید", callback_data="new_search")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    # === کیبوردهای عمومی ===
    
    def get_confirm_keyboard(self, action: str, target_id: str, 
                           extra_data: str = "") -> InlineKeyboardMarkup:
        """✅ کیبورد تأیید عملیات"""
        confirm_data = f"confirm_{action}_{target_id}"
        cancel_data = f"cancel_{action}_{target_id}"
        
        if extra_data:
            confirm_data += f"_{extra_data}"
            cancel_data += f"_{extra_data}"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=confirm_data),
                InlineKeyboardButton("❌ لغو", callback_data=cancel_data)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_back_keyboard(self, target: str) -> InlineKeyboardMarkup:
        """🔙 کیبورد بازگشت ساده"""
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data=target)]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    # === متدهای کمکی ===
    
    @staticmethod
    def _get_type_emoji(content_type: str) -> str:
        """🎭 دریافت ایموجی نوع محتوا"""
        emoji_map = {
            ContentType.MOVIE: "🎬",
            ContentType.SERIES: "📺",
            ContentType.MINI_SERIES: "🎭",
            ContentType.DOCUMENTARY: "🎪"
        }
        return emoji_map.get(content_type, "📹")
    
    @staticmethod
    def _get_status_emoji(status: str) -> str:
        """📊 دریافت ایموجی وضعیت"""
        emoji_map = {
            Status.ACTIVE: "",
            Status.INACTIVE: "⏸️",
            Status.DELETED: "🗑️",
            Status.PENDING: "⏳"
        }
        return emoji_map.get(status, "")
    
    @staticmethod
    def _get_quality_emoji(quality: str) -> str:
        """📺 دریافت ایموجی کیفیت"""
        emoji_map = {
            '480p': '📱',
            '720p': '🖥️',
            '1080p': '🔥',
            '1440p': '⚡',
            '4k': '👑'
        }
        return emoji_map.get(quality, '📹')
    
    # === فرمت‌کننده‌های پیام ===
    
    def format_collection_details(self, collection: Collection, 
                                videos: List[Video]) -> str:
        """📋 فرمت‌دهی جزئیات مجموعه"""
        type_emoji = self._get_type_emoji(collection.type)
        status_emoji = self._get_status_emoji(collection.status)
        
        # عنوان اصلی
        title = f"{type_emoji}{status_emoji} <b>{Utils.escape_markdown(collection.name)}</b>"
        
        # اطلاعات کلی
        info_lines = []
        
        if collection.year:
            info_lines.append(f"📅 <b>سال:</b> {collection.year}")
        
        if collection.genre:
            info_lines.append(f"🎭 <b>ژانر:</b> {Utils.escape_markdown(collection.genre)}")
        
        if collection.imdb_rating:
            stars = "⭐" * min(int(collection.imdb_rating / 2), 5)
            info_lines.append(f"⭐ <b>امتیاز IMDb:</b> {collection.imdb_rating}/10 {stars}")
        
        if collection.age_rating:
            info_lines.append(f"🔞 <b>رده سنی:</b> {collection.age_rating}")
        
        # آمار
        stats_lines = [
            f"📊 <b>آمار:</b>",
            f"• تعداد ویدیوها: <code>{len(videos)}</code>",
            f"• تعداد بازدید: <code>{collection.total_views:,}</code>",
            f"• تعداد دانلود: <code>{collection.total_downloads:,}</code>"
        ]
        
        # توضیحات
        description = ""
        if collection.description:
            description = f"\n📝 <b>خلاصه داستان:</b>\n<i>{Utils.escape_markdown(collection.description[:500])}</i>"
            if len(collection.description) > 500:
                description += "..."
        
        # تگ‌ها
        tags = ""
        if collection.tags:
            tags = f"\n🏷️ <b>تگ‌ها:</b> <code>{', '.join(collection.tags[:5])}</code>"
            if len(collection.tags) > 5:
                tags += f" و {len(collection.tags) - 5} تگ دیگر"
        
        # ترکیب نهایی
        parts = [title, *info_lines, "", *stats_lines, description, tags]
        return "\n".join(filter(None, parts))
    
    def format_video_details(self, video: Video, collection: Collection) -> str:
        """🎥 فرمت‌دهی جزئیات ویدیو"""
        type_emoji = self._get_type_emoji(collection.type)
        quality_emoji = self._get_quality_emoji(video.quality)
        
        # عنوان
        if collection.type in [ContentType.SERIES, ContentType.MINI_SERIES]:
            title = f"{collection.name} - فصل {video.season} قسمت {video.episode}"
        else:
            title = collection.name
        
        header = f"{type_emoji} <b>{Utils.escape_markdown(title)}</b>"
        
        # مشخصات ویدیو
        video_info = [
            f"{quality_emoji} <b>کیفیت:</b> <code>{video.quality}</code>",
            f"💾 <b>حجم فایل:</b> <code>{Utils.format_file_size(video.file_size)}</code>",
        ]
        
        if video.duration > 0:
            video_info.append(f"⏱️ <b>مدت زمان:</b> <code>{Utils.format_duration(video.duration)}</code>")
        
        # آمار دانلود
        stats = f"📊 <b>آمار:</b> <code>{video.download_count:,}</code> دانلود"
        
        # اطلاعات مجموعه
        collection_info = []
        if collection.year:
            collection_info.append(f"📅 {collection.year}")
        if collection.imdb_rating:
            collection_info.append(f"⭐ {collection.imdb_rating}/10")
        if collection.genre:
            collection_info.append(f"🎭 {collection.genre}")
        
        # توضیحات
        description = ""
        if collection.description:
            description = f"\n📝 <b>خلاصه:</b>\n<i>{Utils.escape_markdown(collection.description[:300])}</i>"
            if len(collection.description) > 300:
                description += "..."
        
        # ترکیب
        parts = [header, "", *video_info, stats]
        if collection_info:
            parts.append(" | ".join(collection_info))
        parts.append(description)
        
        return "\n".join(filter(None, parts))
    
    def format_statistics(self, stats: Dict[str, Any]) -> str:
        """📊 فرمت‌دهی آمار کلی"""
        header = "📊 <b>آمار کلی ربات</b>\n"
        
        # آمار اصلی
        main_stats = [
            f"📚 مجموعه‌ها: <b>{stats.get('total_collections', 0):,}</b>",
            f"🎥 ویدیوها: <b>{stats.get('total_videos', 0):,}</b>",
            f"👥 کاربران: <b>{stats.get('total_users', 0):,}</b>",
            f"⬇️ دانلودهای امروز: <b>{stats.get('today_downloads', 0):,}</b>"
        ]
        
        # محبوب‌ترین محتوا
        popular_section = "\n🔥 <b>محبوب‌ترین محتوا:</b>\n"
        popular = stats.get('popular_collections', [])
        
        if popular:
            for i, item in enumerate(popular[:5], 1):
                popular_section += f"{i}. <code>{item['name']}</code> ({item['downloads']:,} دانلود)\n"
        else:
            popular_section += "<i>هنوز داده‌ای موجود نیست</i>\n"
        
        return header + "\n".join(main_stats) + popular_section
    
    def format_search_no_results(self, query: str) -> str:
        """🔍 پیام عدم وجود نتیجه جستجو"""
        return f"""
🔍 <b>نتیجه جستجو</b>

متأسفانه هیچ نتیجه‌ای برای <b>"{Utils.escape_markdown(query)}"</b> یافت نشد.

💡 <b>پیشنهادات:</b>
• از کلمات کلیدی مختلف استفاده کنید
• املا را بررسی کنید  
• از نام انگلیسی فیلم امتحان کنید
• فقط قسمتی از نام را جستجو کنید

🔄 <i>برای جستجوی جدید از دکمه زیر استفاده کنید</i>
"""
    
    def format_upload_progress(self, task_info: Dict[str, Any]) -> str:
        """⬆️ فرمت‌دهی پیشرفت آپلود"""
        status_emojis = {
            'pending': '⏳',
            'downloading': '⬇️',
            'processing': '⚙️',
            'uploading': '⬆️',
            'completed': '✅',
            'failed': '❌'
        }
        
        status = task_info.get('status', 'pending')
        progress = task_info.get('progress', 0)
        emoji = status_emojis.get(status, '⏳')
        
        header = f"{emoji} <b>آپلود در حال انجام</b>\n"
        
        # نوار پیشرفت
        filled = int(progress / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        info = [
            f"📊 پیشرفت: <code>{progress:.1f}%</code>",
            f"<code>[{progress_bar}]</code>",
            f"📁 وضعیت: <b>{self._get_status_persian(status)}</b>"
        ]
        
        if task_info.get('error_message'):
            info.append(f"❌ خطا: <code>{task_info['error_message']}</code>")
        
        return header + "\n".join(info)
    
    @staticmethod
    def _get_status_persian(status: str) -> str:
        """🔤 تبدیل وضعیت انگلیسی به فارسی"""
        status_map = {
            'pending': 'در انتظار',
            'downloading': 'در حال دانلود',
            'processing': 'در حال پردازش',
            'uploading': 'در حال آپلود',
            'completed': 'تکمیل شده',
            'failed': 'ناموفق'
        }
        return status_map.get(status, status)

# نمونه global
ui_manager = UIManager()

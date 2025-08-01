import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

from admin_panel import AdminPanel
from user_panel import user_panel
from database import db
from config import config

logger = logging.getLogger(__name__)

# متغیر global برای admin_panel
admin_panel = None

def setup_handlers(app: Application, file_manager):
    """⚙️ تنظیم تمام هندلرهای ربات"""
    global admin_panel
    
    try:
        # مقداردهی admin_panel
        admin_panel = AdminPanel(file_manager)
        logger.info("✅ AdminPanel مقداردهی شد")
        
        # === هندلرهای اصلی ===
        app.add_handler(CommandHandler("start", user_panel.handle_start))
        
        # === هندلرهای کاربری ===
        app.add_handler(MessageHandler(
            filters.Regex(r"^🔍 جستجو$"), 
            user_panel.handle_search
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^🆕 جدیدترین‌ها$"), 
            user_panel.handle_latest
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^🎬 فیلم‌ها$"), 
            user_panel.handle_movies
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^📺 سریال‌ها$"), 
            user_panel.handle_series
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^🎭 مینی‌سریال$"), 
            user_panel.handle_mini_series
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^🎪 مستندات$"), 
            user_panel.handle_documentaries
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^ℹ️ راهنما$"), 
            user_panel.handle_help
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"^📞 پشتیبانی$"), 
            user_panel.handle_support
        ))
        
        # === هندلرهای ادمین ===
        if admin_panel:
            # هندلرهای متنی
            app.add_handler(MessageHandler(
                filters.Regex(r"^🎬 مدیریت محتوا$"), 
                admin_panel.handle_content_management
            ))
            app.add_handler(MessageHandler(
                filters.Regex(r"^📊 آمار و گزارش$"), 
                admin_panel.show_statistics
            ))
            
            # هندلرهای callback query
            app.add_handler(CallbackQueryHandler(
                admin_panel.handle_content_management, 
                pattern=r"^content_management$"
            ))
            app.add_handler(CallbackQueryHandler(
                admin_panel.show_collections, 
                pattern=r"^(view_collections|collections_page_\d+)$"
            ))
            app.add_handler(CallbackQueryHandler(
                admin_panel.show_collection_detail, 
                pattern=r"^collection_[a-f0-9]{24}$"
            ))
            app.add_handler(CallbackQueryHandler(
                admin_panel.show_statistics, 
                pattern=r"^(refresh_statistics|detailed_statistics)$"
            ))
            
            # === مکالمه ایجاد مجموعه ===
            create_collection_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        admin_panel.start_create_collection, 
                        pattern=r"^create_collection$"
                    )
                ],
                states={
                    admin_panel.WAITING_COLLECTION_NAME: [
                        CallbackQueryHandler(
                            admin_panel.handle_collection_type, 
                            pattern=r"^(type_|cancel_operation)"
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_YEAR: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, 
                            admin_panel.handle_collection_name
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_GENRE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, 
                            admin_panel.handle_collection_year
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_RATING: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, 
                            admin_panel.handle_collection_genre
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_DESCRIPTION: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, 
                            admin_panel.handle_collection_rating
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_COVER: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, 
                            admin_panel.handle_collection_description
                        )
                    ],
                    admin_panel.WAITING_COLLECTION_TRAILER: [
                        MessageHandler(
                            filters.PHOTO | (filters.TEXT & ~filters.COMMAND), 
                            admin_panel.handle_collection_cover
                        )
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", admin_panel.handle_cancel_operation),
                    MessageHandler(
                        filters.VIDEO | (filters.TEXT & filters.Regex(r"^/finish$")), 
                        admin_panel.handle_collection_trailer
                    ),
                    CallbackQueryHandler(
                        admin_panel.handle_cancel_operation,
                        pattern=r"^cancel_operation$"
                    )
                ],
                per_message=False,
                per_chat=True,
                per_user=True,
                allow_reentry=True,
                conversation_timeout=600  # 10 دقیقه timeout
            )
            
            app.add_handler(create_collection_handler)
            logger.info("✅ مکالمه ایجاد مجموعه تنظیم شد")
        
        # === هندلر دانلود ===
        app.add_handler(CallbackQueryHandler(
            user_panel.handle_download_request, 
            pattern=r"^download_[A-Z0-9]{9}_\w+$"
        ))
        
        # === هندلرهای عمومی callback ===
        app.add_handler(CallbackQueryHandler(
            handle_general_callbacks,
            pattern=r"^(back_to_main|page_info)$"
        ))
        
        # === هندلر خطا ===
        app.add_error_handler(error_handler)
        
        logger.info("✅ تمام هندلرها تنظیم شدند")
        
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم هندلرها: {e}")
        raise

async def handle_general_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔄 مدیریت callback های عمومی"""
    query = update.callback_query
    
    if query.data == "back_to_main":
        user_id = update.effective_user.id
        if await db.is_admin(user_id):
            if admin_panel:
                await admin_panel.show_admin_panel(update, context)
            else:
                await query.answer("خطا در بارگذاری پنل ادمین")
        else:
            await user_panel.show_user_menu(update, context)
    
    elif query.data == "page_info":
        await query.answer("اطلاعات صفحه‌بندی")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚨 مدیریت خطاهای ربات"""
    error_msg = str(context.error)
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    
    # لاگ خطا
    logger.error(
        f"خطا برای کاربر {user_id}: {error_msg}\n"
        f"Update: {update}"
    )
    
    # پیام خطا برای کاربر
    try:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ <b>خطایی رخ داد</b>\n\n"
                "متأسفانه مشکل فنی کوتاهی رخ داده است.\n\n"
                "🔄 لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.\n\n"
                "🙏 از صبر شما متشکریم.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام خطا: {e}")
    
    # اطلاع‌رسانی به ادمین‌ها (در صورت نیاز)
    if "timeout" not in error_msg.lower():
        try:
            error_report = f"""
🚨 <b>گزارش خطای ربات</b>

━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>کاربر:</b> <code>{user_id}</code>
⏰ <b>زمان:</b> <code>{context.application.bot_data.get('start_time', 'Unknown')}</code>
❌ <b>خطا:</b> 
<pre>{error_msg[:500]}</pre>

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <i>این پیام خودکار ارسال شده است.</i>
"""
            # ارسال به ادمین اول
            if config.ADMIN_IDS:
                await context.bot.send_message(
                    chat_id=config.ADMIN_IDS[0],
                    text=error_report,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"خطا در ارسال گزارش خطا: {e}")

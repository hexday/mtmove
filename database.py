import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from bson import ObjectId

from config import config
from models import Collection, Video, User, DownloadLog, AdminLog, UploadTask

logger = logging.getLogger(__name__)

class Database:
    """🗄️ کلاس مدیریت پایگاه داده"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
        self._connection_lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """🔌 اتصال به MongoDB"""
        async with self._connection_lock:
            if self._connected:
                return True
            
            try:
                logger.info("🔌 در حال اتصال به MongoDB...")
                
                self.client = AsyncIOMotorClient(
                    config.MONGODB_URL,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    maxPoolSize=50
                )
                
                # تست اتصال
                await self.client.admin.command('ping')
                
                self.db = self.client[config.DATABASE_NAME]
                await self._create_indexes()
                
                self._connected = True
                logger.info("✅ اتصال به MongoDB برقرار شد")
                return True
                
            except Exception as e:
                logger.error(f"❌ خطا در اتصال به MongoDB: {e}")
                await self.disconnect()
                return False
    
    async def disconnect(self):
        """🔌 قطع اتصال از MongoDB"""
        async with self._connection_lock:
            if self.client:
                self.client.close()
                self.client = None
                self.db = None
                self._connected = False
                logger.info("🔌 اتصال MongoDB قطع شد")
    
    async def _create_indexes(self):
        """📊 ایجاد ایندکس‌های ضروری"""
        try:
            # Collections indexes
            await self.db.collections.create_index("name")
            await self.db.collections.create_index("type")
            await self.db.collections.create_index("status")
            await self.db.collections.create_index("created_at")
            
            # Videos indexes
            await self.db.videos.create_index("unique_code", unique=True)
            await self.db.videos.create_index("collection_id")
            await self.db.videos.create_index([("season", 1), ("episode", 1)])
            await self.db.videos.create_index("status")
            
            # Users indexes
            await self.db.users.create_index("telegram_id", unique=True)
            await self.db.users.create_index("is_admin")
            await self.db.users.create_index("last_activity")
            
            # Download logs indexes
            await self.db.download_logs.create_index("user_id")
            await self.db.download_logs.create_index("downloaded_at")
            await self.db.download_logs.create_index("collection_id")
            
            # Upload tasks indexes
            await self.db.upload_tasks.create_index("status")
            await self.db.upload_tasks.create_index("created_by")
            await self.db.upload_tasks.create_index("created_at")
            
            logger.info("✅ ایندکس‌ها ایجاد شدند")
            
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد ایندکس‌ها: {e}")
    
    async def _ensure_connection(self) -> bool:
        """🔍 اطمینان از وجود اتصال"""
        if not self._connected:
            return await self.connect()
        
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            logger.warning("⚠️ اتصال قطع شده، تلاش مجدد...")
            return await self.connect()
    
    # === Collection Methods ===
    
    async def create_collection(self, collection: Collection) -> Optional[str]:
        """➕ ایجاد مجموعه جدید"""
        if not await self._ensure_connection():
            return None
        
        try:
            if not collection.is_valid():
                logger.error("❌ داده‌های مجموعه نامعتبر است")
                return None
            
            collection.created_at = datetime.now()
            collection.updated_at = datetime.now()
            
            result = await self.db.collections.insert_one(collection.to_dict())
            collection_id = str(result.inserted_id)
            
            logger.info(f"✅ مجموعه '{collection.name}' ایجاد شد: {collection_id}")
            return collection_id
            
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد مجموعه: {e}")
            return None
    
    async def get_collection(self, collection_id: str) -> Optional[Collection]:
        """📋 دریافت مجموعه بر اساس ID"""
        if not await self._ensure_connection():
            return None
        
        try:
            if not ObjectId.is_valid(collection_id):
                return None
            
            result = await self.db.collections.find_one({"_id": ObjectId(collection_id)})
            if result:
                result['_id'] = str(result['_id'])
                return Collection.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت مجموعه: {e}")
            return None
    
    async def get_collections(self, skip: int = 0, limit: int = 20, 
                            content_type: Optional[str] = None,
                            status: str = "active") -> List[Collection]:
        """📚 دریافت لیست مجموعه‌ها"""
        if not await self._ensure_connection():
            return []
        
        try:
            query = {"status": status}
            if content_type:
                query["type"] = content_type
            
            cursor = self.db.collections.find(query).skip(skip).limit(limit).sort("created_at", -1)
            collections = []
            
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                try:
                    collections.append(Collection.from_dict(doc))
                except Exception as e:
                    logger.warning(f"⚠️ خطا در پردازش مجموعه {doc.get('_id')}: {e}")
            
            return collections
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت مجموعه‌ها: {e}")
            return []
    
    async def update_collection(self, collection_id: str, updates: Dict[str, Any]) -> bool:
        """🔄 بروزرسانی مجموعه"""
        if not await self._ensure_connection():
            return False
        
        try:
            if not ObjectId.is_valid(collection_id):
                return False
            
            updates['updated_at'] = datetime.now()
            
            result = await self.db.collections.update_one(
                {"_id": ObjectId(collection_id)},
                {"$set": updates}
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"✅ مجموعه {collection_id} بروزرسانی شد")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ خطا در بروزرسانی مجموعه: {e}")
            return False
    
    async def delete_collection(self, collection_id: str, soft_delete: bool = True) -> bool:
        """🗑️ حذف مجموعه"""
        if not await self._ensure_connection():
            return False
        
        try:
            if not ObjectId.is_valid(collection_id):
                return False
            
            if soft_delete:
                result = await self.db.collections.update_one(
                    {"_id": ObjectId(collection_id)},
                    {"$set": {"status": "deleted", "updated_at": datetime.now()}}
                )
            else:
                result = await self.db.collections.delete_one({"_id": ObjectId(collection_id)})
            
            success = result.modified_count > 0 if soft_delete else result.deleted_count > 0
            if success:
                action = "حذف شد" if not soft_delete else "غیرفعال شد"
                logger.info(f"✅ مجموعه {collection_id} {action}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ خطا در حذف مجموعه: {e}")
            return False
    
    # === Video Methods ===
    
    async def create_video(self, video: Video) -> Optional[str]:
        """🎥 ایجاد ویدیو جدید"""
        if not await self._ensure_connection():
            return None
        
        try:
            video.created_at = datetime.now()
            video.updated_at = datetime.now()
            
            result = await self.db.videos.insert_one(video.to_dict())
            video_id = str(result.inserted_id)
            
            logger.info(f"✅ ویدیو '{video.unique_code}' ایجاد شد: {video_id}")
            return video_id
            
        except DuplicateKeyError:
            logger.error(f"❌ کد یکتا '{video.unique_code}' تکراری است")
            return None
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد ویدیو: {e}")
            return None
    
    async def get_video_by_code(self, unique_code: str) -> Optional[Video]:
        """🔍 دریافت ویدیو بر اساس کد یکتا"""
        if not await self._ensure_connection():
            return None
        
        try:
            result = await self.db.videos.find_one({"unique_code": unique_code})
            if result:
                result['_id'] = str(result['_id'])
                return Video.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت ویدیو: {e}")
            return None
    
    async def get_collection_videos(self, collection_id: str) -> List[Video]:
        """📺 دریافت ویدیوهای یک مجموعه"""
        if not await self._ensure_connection():
            return []
        
        try:
            cursor = self.db.videos.find({
                "collection_id": collection_id,
                "status": "active"
            }).sort([("season", 1), ("episode", 1)])
            
            videos = []
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                try:
                    videos.append(Video.from_dict(doc))
                except Exception as e:
                    logger.warning(f"⚠️ خطا در پردازش ویدیو {doc.get('_id')}: {e}")
            
            return videos
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت ویدیوهای مجموعه: {e}")
            return []
    
    async def increment_download_count(self, video_id: str) -> bool:
        """📈 افزایش تعداد دانلود ویدیو"""
        if not await self._ensure_connection():
            return False
        
        try:
            if not ObjectId.is_valid(video_id):
                return False
            
            result = await self.db.videos.update_one(
                {"_id": ObjectId(video_id)},
                {"$inc": {"download_count": 1}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ خطا در افزایش تعداد دانلود: {e}")
            return False
    
    # === User Methods ===
    
    async def create_or_update_user(self, user: User) -> bool:
        """👤 ایجاد یا بروزرسانی کاربر"""
        if not await self._ensure_connection():
            return False
        
        try:
            existing_user = await self.db.users.find_one({"telegram_id": user.telegram_id})
            
            if existing_user:
                # بروزرسانی کاربر موجود
                updates = {
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code,
                    "last_activity": datetime.now(),
                    "updated_at": datetime.now()
                }
                
                result = await self.db.users.update_one(
                    {"telegram_id": user.telegram_id},
                    {"$set": updates}
                )
                return result.modified_count > 0
            else:
                # ایجاد کاربر جدید
                user.join_date = datetime.now()
                user.last_activity = datetime.now()
                user.created_at = datetime.now()
                user.updated_at = datetime.now()
                
                await self.db.users.insert_one(user.to_dict())
                logger.info(f"✅ کاربر جدید {user.telegram_id} ثبت شد")
                return True
                
        except Exception as e:
            logger.error(f"❌ خطا در مدیریت کاربر: {e}")
            return False
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """👤 دریافت کاربر بر اساس ID تلگرام"""
        if not await self._ensure_connection():
            return None
        
        try:
            result = await self.db.users.find_one({"telegram_id": telegram_id})
            if result:
                result['_id'] = str(result['_id'])
                return User.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت کاربر: {e}")
            return None
    
    async def is_admin(self, telegram_id: int) -> bool:
        """🔧 بررسی ادمین بودن کاربر"""
        # ابتدا از تنظیمات بررسی کن
        if telegram_id in config.ADMIN_IDS:
            return True
        
        # سپس از پایگاه داده
        user = await self.get_user(telegram_id)
        return user and user.is_admin
    
    async def update_user_stats(self, user_id: int) -> bool:
        """📊 بروزرسانی آمار کاربر"""
        if not await self._ensure_connection():
            return False
        
        try:
            result = await self.db.users.update_one(
                {"telegram_id": user_id},
                {"$inc": {"total_downloads": 1}, "$set": {"last_activity": datetime.now()}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ خطا در بروزرسانی آمار کاربر: {e}")
            return False
    
    # === Log Methods ===
    
    async def log_download(self, download_log: DownloadLog) -> bool:
        """📊 ثبت لاگ دانلود"""
        if not await self._ensure_connection():
            return False
        
        try:
            download_log.created_at = datetime.now()
            await self.db.download_logs.insert_one(download_log.to_dict())
            return True
            
        except Exception as e:
            logger.error(f"❌ خطا در ثبت لاگ دانلود: {e}")
            return False
    
    async def log_admin_action(self, admin_log: AdminLog) -> bool:
        """🔧 ثبت لاگ عملیات ادمین"""
        if not await self._ensure_connection():
            return False
        
        try:
            admin_log.created_at = datetime.now()
            await self.db.admin_logs.insert_one(admin_log.to_dict())
            return True
            
        except Exception as e:
            logger.error(f"❌ خطا در ثبت لاگ ادمین: {e}")
            return False
    
    # === Statistics ===
    
    async def get_statistics(self) -> Dict[str, Any]:
        """📊 دریافت آمار کلی"""
        if not await self._ensure_connection():
            return {}
        
        try:
            stats = {}
            
            # آمار کلی
            stats['total_collections'] = await self.db.collections.count_documents({"status": "active"})
            stats['total_videos'] = await self.db.videos.count_documents({"status": "active"})
            stats['total_users'] = await self.db.users.count_documents({})
            
            # آمار دانلود
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            stats['today_downloads'] = await self.db.download_logs.count_documents({
                "downloaded_at": {"$gte": today_start}
            })
            
            # محبوب‌ترین مجموعه‌ها
            popular_pipeline = [
                {"$match": {"status": "active"}},
                {"$sort": {"total_downloads": -1}},
                {"$limit": 5},
                {"$project": {"name": 1, "total_downloads": 1}}
            ]
            
            popular_collections = []
            async for doc in self.db.collections.aggregate(popular_pipeline):
                popular_collections.append({
                    "name": doc['name'],
                    "downloads": doc.get('total_downloads', 0)
                })
            
            stats['popular_collections'] = popular_collections
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت آمار: {e}")
            return {}
    
    # === Upload Tasks ===
    
    async def create_upload_task(self, task: UploadTask) -> Optional[str]:
        """⬆️ ایجاد وظیفه آپلود"""
        if not await self._ensure_connection():
            return None
        
        try:
            task.created_at = datetime.now()
            task.updated_at = datetime.now()
            
            result = await self.db.upload_tasks.insert_one(task.to_dict())
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد وظیفه آپلود: {e}")
            return None
    
    async def update_upload_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """🔄 بروزرسانی وظیفه آپلود"""
        if not await self._ensure_connection():
            return False
        
        try:
            if not ObjectId.is_valid(task_id):
                return False
            
            updates['updated_at'] = datetime.now()
            
            result = await self.db.upload_tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": updates}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ خطا در بروزرسانی وظیفه آپلود: {e}")
            return False

# ایجاد نمونه global
db = Database()

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import json

class ContentType(str, Enum):
    """🎭 نوع محتوا"""
    MOVIE = "movie"
    SERIES = "series"
    MINI_SERIES = "mini_series"
    DOCUMENTARY = "documentary"

class VideoQuality(str, Enum):
    """📺 کیفیت ویدیو"""
    Q480P = "480p"
    Q720P = "720p"
    Q1080P = "1080p"
    Q1440P = "1440p"
    Q4K = "4k"

class Status(str, Enum):
    """📊 وضعیت"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    PENDING = "pending"

@dataclass
class BaseModel:
    """🏗️ مدل پایه"""
    _id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """📋 تبدیل به دیکشنری"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value
            elif isinstance(value, Enum):
                result[key] = value.value
            elif isinstance(value, list):
                result[key] = value.copy()
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """🔄 ایجاد از دیکشنری"""
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

@dataclass
class Collection(BaseModel):
    """🎬 مدل مجموعه"""
    name: str = ""
    type: ContentType = ContentType.MOVIE
    year: Optional[int] = None
    genre: str = ""
    imdb_rating: Optional[float] = None
    description: str = ""
    cover_file_id: Optional[str] = None
    trailer_file_id: Optional[str] = None
    gallery_file_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    age_rating: str = "PG"
    subtitle_languages: List[str] = field(default_factory=list)
    status: Status = Status.ACTIVE
    created_by: int = 0
    total_views: int = 0
    total_downloads: int = 0
    
    def is_valid(self) -> bool:
        """✅ بررسی اعتبار داده‌ها"""
        if not self.name or len(self.name.strip()) < 2:
            return False
        if self.year and (self.year < 1900 or self.year > 2030):
            return False
        if self.imdb_rating and (self.imdb_rating < 0 or self.imdb_rating > 10):
            return False
        return True

@dataclass
class Video(BaseModel):
    """🎥 مدل ویدیو"""
    collection_id: str = ""
    unique_code: str = ""
    season: int = 1
    episode: int = 1
    quality: VideoQuality = VideoQuality.Q720P
    file_size: int = 0
    duration: int = 0  # ثانیه
    message_id: int = 0
    channel_id: int = 0
    thumbnail_file_id: Optional[str] = None
    download_count: int = 0
    file_name: str = ""
    original_url: str = ""
    status: Status = Status.ACTIVE
    
    def get_display_title(self, collection_name: str = "") -> str:
        """📺 عنوان نمایشی"""
        if self.season > 1 or self.episode > 1:
            return f"{collection_name} - S{self.season:02d}E{self.episode:02d}"
        return collection_name

@dataclass
class User(BaseModel):
    """👤 مدل کاربر"""
    telegram_id: int = 0
    username: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    is_admin: bool = False
    is_blocked: bool = False
    language_code: str = "fa"
    last_activity: datetime = field(default_factory=datetime.now)
    total_downloads: int = 0
    join_date: datetime = field(default_factory=datetime.now)
    
    @property
    def full_name(self) -> str:
        """📝 نام کامل"""
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)) or self.username or "کاربر"

@dataclass
class DownloadLog(BaseModel):
    """📊 لاگ دانلود"""
    user_id: int = 0
    video_id: str = ""
    collection_id: str = ""
    downloaded_at: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    quality: str = ""
    file_size: int = 0

@dataclass
class AdminLog(BaseModel):
    """🔧 لاگ عملیات ادمین"""
    admin_id: int = 0
    action: str = ""
    target_type: str = ""  # collection, video, user
    target_id: str = ""
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def add_detail(self, key: str, value: Any):
        """➕ اضافه کردن جزئیات"""
        self.details[key] = value

@dataclass
class UploadTask(BaseModel):
    """⬆️ وظیفه آپلود"""
    url: str = ""
    collection_id: str = ""
    quality: str = ""
    season: int = 1
    episode: int = 1
    status: str = "pending"  # pending, downloading, processing, completed, failed
    progress: float = 0.0
    error_message: str = ""
    file_path: Optional[str] = None
    created_by: int = 0
    
    def update_status(self, status: str, progress: float = None, error: str = None):
        """🔄 بروزرسانی وضعیت"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if error:
            self.error_message = error
        self.updated_at = datetime.now()

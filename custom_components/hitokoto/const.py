"""Constants for Hitokoto Daily."""

from __future__ import annotations

from datetime import time

DOMAIN = "hitokoto"
NAME = "Hitokoto Daily"
MANUFACTURER = "Hitokoto Daily"

CONF_API_ROUTE = "api_route"
CONF_TIMEOUT = "timeout"
CONF_RETRIES = "enable_retries"
CONF_CATEGORIES = "categories"
CONF_MIN_LENGTH = "min_length"
CONF_MAX_LENGTH = "max_length"
CONF_PREFER_AUTHOR = "prefer_author"
CONF_PREFER_SOURCE = "prefer_source"
CONF_AUTO_UPDATE = "auto_update"
CONF_UPDATE_TIME = "update_time"
CONF_SAVE_HISTORY = "save_history"
CONF_HISTORY_LIMIT = "history_limit"
CONF_ENABLE_FAVORITES = "enable_favorites"
CONF_ALLOW_DUPLICATE_FAVORITES = "allow_duplicate_favorites"
CONF_APPLY_NOW = "apply_now"

ROUTE_GLOBAL = "global"
ROUTE_INTERNATIONAL = "international"
API_URLS = {
    ROUTE_GLOBAL: "https://v1.hitokoto.cn/",
    ROUTE_INTERNATIONAL: "https://international.v1.hitokoto.cn/",
}

CATEGORY_NAMES = {
    "a": "动画",
    "b": "漫画",
    "c": "游戏",
    "d": "文学",
    "e": "原创",
    "f": "网络",
    "g": "其他",
    "h": "影视",
    "i": "诗词",
    "j": "网易云",
    "k": "哲学",
    "l": "抖机灵",
}

DEFAULT_CATEGORIES = ("d", "i", "k")
DEFAULT_TIMEOUT = 10
DEFAULT_MIN_LENGTH = 8
DEFAULT_MAX_LENGTH = 80
DEFAULT_UPDATE_TIME = time(hour=0, minute=5)
DEFAULT_HISTORY_LIMIT = 365
MAX_MANUAL_COOLDOWN = 5.0
REQUEST_SPACING = 0.6
RETRY_DELAYS = (15, 60, 300)

STATUS_NORMAL = "normal"
STATUS_STALE = "stale"
STATUS_ERROR = "error"
STATUS_UNAVAILABLE = "unavailable"
STATUS_OPTIONS = (STATUS_NORMAL, STATUS_STALE, STATUS_ERROR, STATUS_UNAVAILABLE)

PLATFORMS = ("sensor",)

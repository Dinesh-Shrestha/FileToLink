# Thunder/utils/file_properties.py

import asyncio
import re
from datetime import datetime as dt
from typing import Any, Optional

from pyrogram.client import Client
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId
from pyrogram.types import Message

from Thunder.server.exceptions import FileNotFound
from Thunder.utils.logger import logger


def get_media(message: Message) -> Optional[Any]:
    for attr in ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note"):
        media = getattr(message, attr, None)
        if media:
            return media
    return None


def get_uniqid(message: Message) -> Optional[str]:
    media = get_media(message)
    return getattr(media, 'file_unique_id', None)


def get_hash(media_msg: Message) -> str:
    uniq_id = get_uniqid(media_msg)
    return uniq_id[:6] if uniq_id else ''


def get_fsize(message: Message) -> int:
    media = get_media(message)
    return getattr(media, 'file_size', 0) if media else 0


def parse_fid(message: Message) -> Optional[FileId]:
    media = get_media(message)
    if media and hasattr(media, 'file_id'):
        try:
            return FileId.decode(media.file_id)
        except Exception:
            return None
    return None


def clean_fname(name: str) -> str:
    if not name:
        return ""
    # Take the first line and remove leading/trailing whitespace
    name = name.split('\n')[0].strip()
    # Remove Telegram @usernames, URLs, and common promotional suffixes
    name = re.sub(r'(@[a-zA-Z0-9_]+)', '', name)
    name = re.sub(r'https?://[^\s]+', '', name)
    # Remove problematic characters for filenames but keep dots/dashes
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    # Clean up double spaces or dots that might result from removals
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_fname(msg: Message) -> str:
    media = get_media(msg)
    if not media:
        return f"file_{dt.now().strftime('%Y%m%d%H%M%S')}.bin"

    # Try internal filename first
    internal_name = getattr(media, 'file_name', None)
    # Try caption as a fallback (often better for forwarded/leeched files)
    caption_name = clean_fname(msg.caption) if msg.caption else None

    # Use caption if internal name is missing or seems truncated/inferior
    if caption_name and (not internal_name or len(caption_name) > len(internal_name)):
        fname = caption_name
    else:
        fname = internal_name

    # Ensure we have a valid name or use a timestamp
    if not fname:
        ext = "bin"
        media_types = {
            "photo": "jpg",
            "audio": "mp3",
            "voice": "ogg",
            "video": "mp4",
            "animation": "mp4",
            "video_note": "mp4",
            "sticker": "webp"
        }
        for attr, extension in media_types.items():
            if getattr(msg, attr, None) is not None:
                ext = extension
                break
        fname = f"Thunder_{dt.now().strftime('%Y%m%d%H%M%S')}.{ext}"

    # Final check: if the name is from caption and missing extension, add it
    if "." not in fname[-5:]:
        media_type = type(media).__name__.lower()
        ext_map = {
            "photo": ".jpg",
            "audio": ".mp3",
            "voice": ".ogg",
            "video": ".mp4",
            "animation": ".mp4",
            "videonote": ".mp4",
            "sticker": ".webp"
        }
        ext = ext_map.get(media_type, "")
        if ext and not fname.lower().endswith(ext):
            fname += ext

    return fname


async def get_fids(client: Client, chat_id: int, message_id: int) -> FileId:
    try:
        try:
            msg = await client.get_messages(chat_id, message_id)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msg = await client.get_messages(chat_id, message_id)

        if not msg or getattr(msg, 'empty', False):
            raise FileNotFound("Message not found")

        media = get_media(msg)
        if media:
            if not hasattr(media, 'file_id') or not hasattr(media, 'file_unique_id'):
                raise FileNotFound("Media metadata incomplete")
            return FileId.decode(media.file_id)

        raise FileNotFound("No media in message")

    except Exception as e:
        logger.error(f"Error in get_fids: {e}", exc_info=True)
        raise FileNotFound(str(e))

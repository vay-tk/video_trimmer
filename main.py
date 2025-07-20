import logging
import os
import subprocess
import tempfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=getattr(logging, log_level)
)
logger = logging.getLogger(__name__)

# Get credentials from environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not all([BOT_TOKEN, API_ID, API_HASH]):
    logger.error("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")
    exit(1)

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE', 2000))  # 2GB default for Pyrogram
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# User states for tracking video trimming process
USER_STATES = {}
VIDEO_DATA = {}

# Initialize Pyrogram client
app = Client(
    "video_trimmer_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

async def progress_callback(current, total, message, action):
    """Show download/upload progress"""
    percent = (current / total) * 100
    if percent % 10 < 1:  # Update every 10%
        try:
            await message.edit(f"{action}... {percent:.1f}%")
        except Exception:
            pass  # Ignore edit errors

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    await message.reply_text(
        "🎬 **Professional Video Trimmer Bot**\n\n"
        "📁 **File Size Limit**: Up to 2GB\n"
        "⚡ **Features**: Progress tracking, fast processing\n\n"
        "Send me a video file and I'll help you trim it!\n"
        "Supported formats: MP4, AVI, MOV, MKV, etc."
    )

@app.on_message(filters.command("cancel"))
async def cancel_command(client: Client, message: Message):
    """Handle /cancel command"""
    user_id = message.from_user.id
    
    if user_id in USER_STATES:
        del USER_STATES[user_id]
    if user_id in VIDEO_DATA:
        del VIDEO_DATA[user_id]
    
    await message.reply_text("❌ Operation cancelled. Send a video to start again.")

@app.on_message(filters.video)
async def handle_video(client: Client, message: Message):
    """Handle video messages"""
    user_id = message.from_user.id
    video = message.video
    
    # Check file size
    if video.file_size > MAX_FILE_SIZE_BYTES:
        size_gb = video.file_size / (1024 * 1024 * 1024)
        await message.reply_text(
            f"❌ File too large ({size_gb:.2f}GB)\n"
            f"📏 Maximum allowed size: {MAX_FILE_SIZE_MB/1024:.1f}GB"
        )
        return
    
    # Store video data
    VIDEO_DATA[user_id] = {
        'message_id': message.id,
        'file_id': video.file_id,
        'duration': video.duration,
        'file_size': video.file_size,
        'file_name': video.file_name or "video.mp4"
    }
    
    USER_STATES[user_id] = 'waiting_for_start_time'
    
    # Format file info
    size_mb = video.file_size / (1024 * 1024)
    duration_text = f"⏱️ **Duration**: {video.duration}s" if video.duration else "⏱️ **Duration**: Unknown"
    size_text = f"📦 **Size**: {size_mb:.1f}MB"
    
    await message.reply_text(
        f"✅ **Video Received!**\n\n"
        f"{duration_text}\n"
        f"{size_text}\n\n"
        f"📝 **Step 1/2**: Send the **start time**\n"
        f"Examples: `10` (10 seconds) or `1:30` (1 min 30 sec)"
    )

@app.on_message(filters.text)
async def handle_text(client: Client, message: Message):
    """Handle text input for trimming parameters"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Skip if it's a command
    if text.startswith('/'):
        return
    
    if user_id not in USER_STATES:
        await message.reply_text("❌ Please send a video first using /start")
        return
    
    state = USER_STATES[user_id]
    
    if state == 'waiting_for_start_time':
        try:
            start_time = parse_time(text)
            VIDEO_DATA[user_id]['start_time'] = start_time
            USER_STATES[user_id] = 'waiting_for_end_time'
            
            await message.reply_text(
                f"✅ **Start time set**: {start_time}s\n\n"
                f"📝 **Step 2/2**: Send the **end time**\n"
                f"Examples: `60` (60 seconds) or `2:30` (2 min 30 sec)"
            )
        except ValueError:
            await message.reply_text(
                "❌ **Invalid time format**\n\n"
                "Please use:\n"
                "• Seconds: `10`\n"
                "• Minutes:Seconds: `1:30`"
            )
    
    elif state == 'waiting_for_end_time':
        try:
            end_time = parse_time(text)
            start_time = VIDEO_DATA[user_id]['start_time']
            
            if end_time <= start_time:
                await message.reply_text(
                    "❌ **End time must be greater than start time**\n"
                    "Please enter a valid end time:"
                )
                return
            
            VIDEO_DATA[user_id]['end_time'] = end_time
            USER_STATES[user_id] = 'processing'
            
            duration = end_time - start_time
            await message.reply_text(
                f"🚀 **Processing Video...**\n\n"
                f"⏱️ Trim: {start_time}s → {end_time}s\n"
                f"📏 Duration: {duration}s\n\n"
                f"Please wait, this may take a few minutes for large files..."
            )
            
            # Start trimming process
            await trim_and_send_video(client, message, user_id)
            
        except ValueError:
            await message.reply_text(
                "❌ **Invalid time format**\n\n"
                "Please use:\n"
                "• Seconds: `60`\n"
                "• Minutes:Seconds: `2:30`"
            )

def parse_time(time_str: str) -> float:
    """Parse time string to seconds"""
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        else:
            raise ValueError("Invalid time format")
    else:
        return float(time_str)

async def trim_and_send_video(client: Client, message: Message, user_id: int):
    """Download, trim and upload video with progress tracking"""
    input_path = None
    output_path = None
    progress_msg = None
    
    try:
        video_data = VIDEO_DATA[user_id]
        start_time = video_data['start_time']
        end_time = video_data['end_time']
        duration = end_time - start_time
        
        # Get original video message
        original_msg = await client.get_messages(
            message.chat.id, 
            video_data['message_id']
        )
        
        # Create temporary files
        input_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        input_path = input_file.name
        input_file.close()
        
        output_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        output_path = output_file.name
        output_file.close()
        
        # Download video with progress
        progress_msg = await message.reply_text("📥 Downloading video... 0%")
        
        await original_msg.download(
            file_name=input_path,
            progress=progress_callback,
            progress_args=(progress_msg, "📥 Downloading")
        )
        
        await progress_msg.edit("✂️ Trimming video...")
        
        # Trim video using ffmpeg
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            output_path,
            '-y'
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        # Check output file
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Output file was not created or is empty")
        
        # Get output file size
        output_size = os.path.getsize(output_path)
        output_size_mb = output_size / (1024 * 1024)
        
        await progress_msg.edit("📤 Uploading trimmed video... 0%")
        
        # Upload trimmed video with progress
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption=(
                f"✅ **Video Trimmed Successfully!**\n\n"
                f"⏱️ **Original**: {start_time}s → {end_time}s\n"
                f"📏 **Duration**: {duration}s\n"
                f"📦 **Size**: {output_size_mb:.1f}MB\n\n"
                f"Send another video to trim more!"
            ),
            progress=progress_callback,
            progress_args=(progress_msg, "📤 Uploading")
        )
        
        await progress_msg.delete()
        
    except Exception as e:
        logger.error(f"Error trimming video: {e}")
        error_msg = (
            f"❌ **Processing Error**\n\n"
            f"**Issue**: {str(e)}\n\n"
            f"**Common causes**:\n"
            f"• FFmpeg not installed\n"
            f"• Invalid time range\n"
            f"• Corrupted video file\n"
            f"• Insufficient disk space\n\n"
            f"Try again with different settings."
        )
        await message.reply_text(error_msg)
        
        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception:
                pass
    
    finally:
        # Cleanup temporary files
        for file_path in [input_path, output_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up: {file_path}")
                except Exception as e:
                    logger.warning(f"Cleanup failed for {file_path}: {e}")
        
        # Reset user state
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        if user_id in VIDEO_DATA:
            del VIDEO_DATA[user_id]

if __name__ == "__main__":
    logger.info("Starting Professional Video Trimmer Bot...")
    logger.info(f"File size limit: {MAX_FILE_SIZE_MB}MB")
    app.run()

import logging
import os
import subprocess
import tempfile
import asyncio
import shutil
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

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, f"FFmpeg found: {version_line}"
        else:
            return False, "FFmpeg not working properly"
    except FileNotFoundError:
        return False, "FFmpeg not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timeout"
    except Exception as e:
        return False, f"FFmpeg check failed: {e}"

def get_deployment_info():
    """Get deployment environment information"""
    env_info = {
        'platform': os.getenv('RAILWAY_ENVIRONMENT', 'local'),
        'service': os.getenv('RAILWAY_SERVICE_NAME', 'unknown'),
        'deployment_id': os.getenv('RAILWAY_DEPLOYMENT_ID', 'unknown')[:8]
    }
    return env_info

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
    # Check FFmpeg availability
    ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
    deployment_info = get_deployment_info()
    
    if not ffmpeg_ok:
        error_msg = (
            f"⚠️ **FFmpeg Not Available**\n\n"
            f"**Status**: {ffmpeg_msg}\n"
            f"**Platform**: {deployment_info['platform']}\n\n"
        )
        
        if deployment_info['platform'] != 'local':
            error_msg += (
                f"**Cloud Deployment Issue**:\n"
                f"FFmpeg is not installed in the deployment environment.\n\n"
                f"**Solutions**:\n"
                f"• Check if `nixpacks.toml` is properly configured\n"
                f"• Verify Railway build logs for FFmpeg installation\n"
                f"• Consider using Docker deployment with Dockerfile\n\n"
                f"**Current deployment**: {deployment_info['service']}-{deployment_info['deployment_id']}"
            )
        else:
            error_msg += (
                f"**Local Installation**:\n"
                f"1. Download from: https://ffmpeg.org/download.html\n"
                f"2. Extract to C:\\ffmpeg\n"
                f"3. Add C:\\ffmpeg\\bin to PATH\n"
                f"4. Restart command prompt\n\n"
                f"**Or use Chocolatey**: `choco install ffmpeg`\n\n"
                f"**Test installation**: `ffmpeg -version`"
            )
        
        await message.reply_text(error_msg)
        return
    
    await message.reply_text(
        f"🎬 **Professional Video Trimmer Bot**\n\n"
        f"📁 **File Size Limit**: Up to 2GB\n"
        f"⚡ **Features**: Progress tracking, fast processing\n"
        f"✅ **FFmpeg**: {ffmpeg_msg}\n"
        f"🚀 **Platform**: {deployment_info['platform']}\n\n"
        f"Send me a video file and I'll help you trim it!\n"
        f"Supported formats: MP4, AVI, MOV, MKV, etc."
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

@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    """Handle video messages and video documents"""
    user_id = message.from_user.id
    
    # Check if it's a video or video document
    if message.video:
        video = message.video
        file_name = video.file_name or "video.mp4"
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('video/'):
        video = message.document
        file_name = video.file_name or "video.mp4"
    elif message.document and message.document.file_name and any(ext in message.document.file_name.lower() for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']):
        video = message.document
        file_name = video.file_name
    else:
        await message.reply_text(
            "❌ **Not a video file**\n\n"
            "Please send a video file with one of these formats:\n"
            "• MP4, AVI, MOV, MKV\n"
            "• WEBM, FLV, WMV\n\n"
            "Make sure the file is sent as a video or document."
        )
        return
    
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
        'duration': getattr(video, 'duration', None),
        'file_size': video.file_size,
        'file_name': file_name,
        'is_document': message.document is not None
    }
    
    USER_STATES[user_id] = 'waiting_for_start_time'
    
    # Format file info
    size_mb = video.file_size / (1024 * 1024)
    duration_text = f"⏱️ **Duration**: {video.duration}s" if getattr(video, 'duration', None) else "⏱️ **Duration**: Unknown"
    size_text = f"📦 **Size**: {size_mb:.1f}MB"
    file_type = "📄 Document" if message.document else "🎬 Video"
    
    await message.reply_text(
        f"✅ **Video Received!** ({file_type})\n\n"
        f"📁 **File**: {file_name}\n"
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
        # Check FFmpeg before processing
        ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
        if not ffmpeg_ok:
            await message.reply_text(
                f"❌ **FFmpeg Error**\n\n"
                f"**Issue**: {ffmpeg_msg}\n\n"
                f"Please install FFmpeg and try again.\n"
                f"Use /start to see installation instructions."
            )
            return
        
        video_data = VIDEO_DATA[user_id]
        start_time = video_data['start_time']
        end_time = video_data['end_time']
        duration = end_time - start_time
        
        # Get original video message
        original_msg = await client.get_messages(
            message.chat.id, 
            video_data['message_id']
        )
        
        # Create temporary files with better naming
        temp_dir = tempfile.mkdtemp(prefix="video_trimmer_")
        
        # Use original file extension
        file_name = video_data['file_name']
        file_ext = os.path.splitext(file_name)[1] if file_name else '.mp4'
        
        input_path = os.path.join(temp_dir, f"input_{user_id}{file_ext}")
        output_path = os.path.join(temp_dir, f"output_{user_id}{file_ext}")
        
        # Download video with progress
        file_type = "document" if video_data['is_document'] else "video"
        progress_msg = await message.reply_text(f"📥 Downloading {file_type}... 0%")
        
        await original_msg.download(
            file_name=input_path,
            progress=progress_callback,
            progress_args=(progress_msg, f"📥 Downloading {file_type}")
        )
        
        # Verify downloaded file
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            raise Exception("Downloaded file is empty or missing")
        
        await progress_msg.edit("✂️ Trimming video...")
        
        # Build FFmpeg command with better error handling
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            '-y',  # Overwrite output file
            output_path
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        
        # Run FFmpeg with timeout
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr}")
            # Try to identify specific error
            if "Invalid data found" in result.stderr:
                raise Exception("Invalid video format or corrupted file")
            elif "No such file" in result.stderr:
                raise Exception("Input file not found")
            elif "Permission denied" in result.stderr:
                raise Exception("Permission denied - check file permissions")
            else:
                raise Exception(f"FFmpeg failed: {result.stderr}")
        
        # Check output file
        if not os.path.exists(output_path):
            raise Exception("Output file was not created")
        
        output_size = os.path.getsize(output_path)
        if output_size == 0:
            raise Exception("Output file is empty")
        
        output_size_mb = output_size / (1024 * 1024)
        
        await progress_msg.edit("📤 Uploading trimmed video... 0%")
        
        # Upload trimmed video with progress - always as video, not document
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption=(
                f"✅ **Video Trimmed Successfully!**\n\n"
                f"📁 **Original**: {video_data['file_name']}\n"
                f"⏱️ **Trimmed**: {start_time}s → {end_time}s\n"
                f"📏 **Duration**: {duration}s\n"
                f"📦 **Size**: {output_size_mb:.1f}MB\n\n"
                f"Send another video to trim more!"
            ),
            progress=progress_callback,
            progress_args=(progress_msg, "📤 Uploading")
        )
        
        await progress_msg.delete()
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        await message.reply_text(
            "❌ **Processing Timeout**\n\n"
            "The video is taking too long to process.\n"
            "Try with a shorter clip or smaller file."
        )
        
    except Exception as e:
        logger.error(f"Error trimming video: {e}")
        
        # Provide specific error messages
        if "No such file or directory: 'ffmpeg'" in str(e):
            error_msg = (
                "❌ **FFmpeg Not Found**\n\n"
                "Please install FFmpeg:\n"
                "• Windows: Download from ffmpeg.org\n"
                "• Or use: `choco install ffmpeg`\n"
                "• Add to PATH and restart\n\n"
                "Use /start for detailed instructions."
            )
        elif "Invalid video format" in str(e):
            error_msg = (
                "❌ **Invalid Video Format**\n\n"
                "The video file appears to be corrupted or in an unsupported format.\n"
                "Try with a different video file."
            )
        elif "Permission denied" in str(e):
            error_msg = (
                "❌ **Permission Error**\n\n"
                "Cannot access temporary files.\n"
                "Please check disk permissions and available space."
            )
        else:
            error_msg = (
                f"❌ **Processing Error**\n\n"
                f"**Issue**: {str(e)}\n\n"
                f"**Common solutions**:\n"
                f"• Check if FFmpeg is installed\n"
                f"• Verify time range is valid\n"
                f"• Ensure sufficient disk space\n"
                f"• Try with a different video\n\n"
                f"Use /start to check FFmpeg status."
            )
        
        await message.reply_text(error_msg)
        
        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception:
                pass
    
    finally:
        # Cleanup temporary files and directory
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
                logger.debug(f"Cleaned up: {input_path}")
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
                logger.debug(f"Cleaned up: {output_path}")
            # Remove temp directory if empty
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except OSError:
                    pass  # Directory not empty
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        
        # Reset user state
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        if user_id in VIDEO_DATA:
            del VIDEO_DATA[user_id]

if __name__ == "__main__":
    deployment_info = get_deployment_info()
    logger.info("Starting Professional Video Trimmer Bot...")
    logger.info(f"File size limit: {MAX_FILE_SIZE_MB}MB")
    logger.info(f"Platform: {deployment_info['platform']}")
    
    if deployment_info['platform'] != 'local':
        logger.info(f"Service: {deployment_info['service']}")
        logger.info(f"Deployment ID: {deployment_info['deployment_id']}")
    
    # Check FFmpeg on startup
    ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
    if ffmpeg_ok:
        logger.info(f"✅ {ffmpeg_msg}")
    else:
        logger.warning(f"⚠️ {ffmpeg_msg}")
        if deployment_info['platform'] != 'local':
            logger.error("🚨 FFmpeg missing in cloud deployment - video processing will fail!")
            logger.error("💡 Solution: Ensure nixpacks.toml includes FFmpeg or use Dockerfile")
        else:
            logger.warning("Bot will still start, but video processing will fail without FFmpeg")
    
    app.run()

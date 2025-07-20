# Video Trimmer Bot

A Telegram bot that allows users to trim videos by specifying start and end times.

## Features

- 🎬 Upload any video file to trim
- ⏱️ Flexible time input (seconds or MM:SS format)
- ✂️ Fast video trimming using FFmpeg
- 🤖 Interactive step-by-step process
- 🧹 Automatic cleanup of temporary files

## Prerequisites

- Python 3.7 or higher
- FFmpeg installed on your system
- Telegram Bot Token (from @BotFather)

## Installation

### 1. Install FFmpeg

**Windows:**
- Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
- Extract and add to PATH, or use chocolatey: `choco install ffmpeg`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. Choose Your Implementation

This project offers two approaches:

#### Option A: Bot API (Recommended for beginners)
- Uses `python-telegram-bot` library
- Only requires bot token from @BotFather
- 50MB file size limit
- Simpler setup and deployment

#### Option B: Client API (Professional/Advanced)
- Uses `pyrogram` library for Telegram client applications
- Requires api_id, api_hash, and bot token
- 2GB file size limit
- More features and flexibility
- Better for professional applications

### 3. Clone and Setup

```bash
git clone <your-repo-url>
cd video_trimerbot
```

### 4. Install Dependencies

**For Bot API (Option A):**
```bash
pip install python-telegram-bot==20.7 python-dotenv==1.0.0
```

**For Client API (Option B):**
```bash
pip install pyrogram==2.0.106 python-dotenv==1.0.0 tgcrypto==1.2.5
```

### 5. Get Telegram Credentials

#### For Bot API (Option A):
1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a chat and send `/newbot`
3. Follow the prompts to choose a name and username for your bot
4. Copy the **Bot Token** (it looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### For Client API (Option B):
1. Get Bot Token from @BotFather (same as above)
2. Go to [https://my.telegram.org/auth](https://my.telegram.org/auth)
3. Log in with your phone number
4. Go to "API Development Tools"
5. Create a new application and copy:
   - `api_id` (numeric)
   - `api_hash` (alphanumeric string)

### 6. Configure Environment

#### For Bot API (Option A):
Create `.env` file:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
LOG_LEVEL=INFO
MAX_FILE_SIZE=50
```

#### For Client API (Option B):
Create `.env` file:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
LOG_LEVEL=INFO
MAX_FILE_SIZE=2000
```

## Professional Features (Client API)

When using Pyrogram (Client API), you get additional capabilities:

### Advantages:
- **Larger Files**: Handle up to 2GB videos (vs 50MB with Bot API)
- **Faster Downloads**: Direct access to Telegram's servers
- **Progress Callbacks**: Real-time upload/download progress
- **Advanced Features**: Access to full Telegram API
- **Better Performance**: More efficient for large file operations

### Use Cases:
- Processing large video files (>50MB)
- High-volume video processing
- Professional video editing services
- Enterprise applications

### Example Pyrogram Implementation:

Create `bot_pyrogram.py` for professional features:

```python
import os
from pyrogram import Client, filters
from pyrogram.types import Message
import asyncio
from dotenv import load_dotenv

load_dotenv()

app = Client(
    "video_trimmer_bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

@app.on_message(filters.video)
async def handle_large_video(client: Client, message: Message):
    """Handle videos up to 2GB with progress tracking"""
    video = message.video
    
    if video.file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
        await message.reply("File too large. Maximum size is 2GB.")
        return
    
    progress_msg = await message.reply("Downloading video... 0%")
    
    # Download with progress callback
    file_path = await message.download(
        progress=progress_callback,
        progress_args=(progress_msg, "Downloading")
    )
    
    await progress_msg.edit("Video downloaded! Please send trim times...")
    # Continue with trimming logic...

async def progress_callback(current, total, message, action):
    """Show download/upload progress"""
    percent = (current / total) * 100
    await message.edit(f"{action}... {percent:.1f}%")

if __name__ == "__main__":
    app.run()
```

## Comparison Table

| Feature | Bot API | Client API (Pyrogram) |
|---------|---------|----------------------|
| File Size Limit | 50MB | 2GB |
| Setup Complexity | Simple | Moderate |
| Credentials Required | Bot Token only | Bot Token + API ID/Hash |
| Performance | Good | Excellent |
| Progress Tracking | Basic | Advanced |
| API Access | Limited | Full Telegram API |
| Best For | Small files, simple bots | Large files, professional apps |

## Usage

### Starting the Bot

```bash
python bot.py
```

### Using the Bot

1. Start a chat with your bot on Telegram
2. Send `/start` to begin
3. Upload a video file
4. Enter start time when prompted (e.g., `10` or `1:30`)
5. Enter end time when prompted (e.g., `60` or `2:45`)
6. Wait for processing and receive your trimmed video

### Commands

- `/start` - Start the bot and get instructions
- `/cancel` - Cancel current trimming operation

### Time Format Examples

- `10` - 10 seconds
- `1:30` - 1 minute 30 seconds
- `2:45` - 2 minutes 45 seconds
- `0:30` - 30 seconds

## File Structure

```
video_trimerbot/
├── bot.py              # Bot API implementation
├── bot_pyrogram.py     # Client API implementation (optional)
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (create this)
└── README.md          # This file
```

## Configuration

Edit `.env` file to customize:

- `BOT_TOKEN` - Your Telegram bot token from @BotFather (required)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `MAX_FILE_SIZE` - Maximum file size in MB (default: 50)

## Troubleshooting

### Common Issues

**"Invalid bot token"**
- Ensure you copied the complete token from @BotFather
- Check for extra spaces or missing characters in `.env`
- Token format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**"FFmpeg not found"**
- Ensure FFmpeg is installed and available in PATH
- Test with `ffmpeg -version` in terminal

**"File too large"**
- Telegram bots have a 50MB file size limit
- Try with smaller video files

**"Processing takes too long"**
- Large files or long durations take more time
- Consider trimming smaller segments

### Bot Token vs API Credentials

#### Bot API (Current Implementation)
This project uses the **Telegram Bot API** which only requires:
- ✅ Bot Token from @BotFather

It does NOT require:
- ❌ api_id (used for client applications)
- ❌ api_hash (used for client applications)
- ❌ Phone number verification

#### Client API (Professional Option)
For professional applications using **Pyrogram**, you need:
- ✅ Bot Token from @BotFather
- ✅ api_id from my.telegram.org
- ✅ api_hash from my.telegram.org

Benefits:
- Handle larger files (up to 2GB)
- Better performance and features
- Access to full Telegram API

### Logs

The bot logs important information to console. Set `LOG_LEVEL=DEBUG` in `.env` for detailed logs.

## Development

### Adding Features

The bot uses python-telegram-bot library. Key components:

- `handle_video()` - Processes incoming videos
- `handle_text()` - Manages user input for trim times
- `trim_and_send_video()` - Handles FFmpeg processing
- State management with `USER_STATES` and `VIDEO_DATA`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs for error details
3. Open an issue on GitHub

---

**Note:** This bot processes videos locally using the Telegram Bot API. Ensure you have sufficient disk space and processing power for video operations.

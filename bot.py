import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from PIL import Image
import tempfile
import shutil
from pathlib import Path

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")

# Store user images temporarily
user_images = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    welcome_text = (
        "👋 Hello! I'm an Image to PDF Converter Bot.\n\n"
        "Send me one or more images, and I'll convert them to a PDF file.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/convert - Convert collected images to PDF\n"
        "/clear - Clear all pending images\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    help_text = (
        "📚 How to use this bot:\n\n"
        "1. Send me images one by one\n"
        "2. After sending all images, use /convert to create PDF\n"
        "3. Use /clear to remove all pending images\n\n"
        "Each image will be added to a queue. The PDF will be created with images in the order you sent them."
    )
    await update.message.reply_text(help_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all pending images."""
    user_id = update.effective_user.id
    if user_id in user_images:
        # Clean up temp files
        for file_path in user_images[user_id]:
            try:
                os.remove(file_path)
            except:
                pass
        del user_images[user_id]
    await update.message.reply_text("✅ All pending images have been cleared!")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming images."""
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # Get the highest resolution image
    
    # Send processing message
    processing_msg = await update.message.reply_text("📥 Processing image...")
    
    try:
        # Download image
        file = await photo.get_file()
        
        # Create temp directory if not exists
        temp_dir = Path(tempfile.gettempdir()) / f"user_{user_id}"
        temp_dir.mkdir(exist_ok=True)
        
        # Save image with unique name
        file_extension = ".jpg"  # Telegram photos are JPEG
        temp_file = temp_dir / f"image_{len(user_images.get(user_id, []))}{file_extension}"
        
        await file.download_to_drive(temp_file)
        
        # Add to user's image list
        if user_id not in user_images:
            user_images[user_id] = []
        user_images[user_id].append(str(temp_file))
        
        image_count = len(user_images[user_id])
        await processing_msg.edit_text(
            f"✅ Image received!\n\n📸 Images in queue: {image_count}\n\n"
            f"Send more images or use /convert to create PDF"
        )
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await processing_msg.edit_text("❌ Failed to process image. Please try again.")

async def convert_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert collected images to PDF."""
    user_id = update.effective_user.id
    
    if user_id not in user_images or not user_images[user_id]:
        await update.message.reply_text("❌ No images found! Please send me some images first.")
        return
    
    processing_msg = await update.message.reply_text("🔄 Converting images to PDF... Please wait.")
    
    try:
        images = user_images[user_id]
        image_list = []
        
        # Open and convert each image to RGB (required for PDF)
        for img_path in images:
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            image_list.append(img)
        
        # Create PDF in temp directory
        output_dir = Path(tempfile.gettempdir())
        pdf_path = output_dir / f"converted_{user_id}.pdf"
        
        # Save first image and append rest
        if image_list:
            first_img = image_list[0]
            remaining_imgs = image_list[1:] if len(image_list) > 1 else []
            first_img.save(pdf_path, save_all=True, append_images=remaining_imgs)
        
        # Send PDF
        with open(pdf_path, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="converted_images.pdf",
                caption=f"✅ Successfully converted {len(image_list)} image(s) to PDF!"
            )
        
        # Clean up
        for img_path in images:
            try:
                os.remove(img_path)
            except:
                pass
        try:
            os.remove(pdf_path)
        except:
            pass
        del user_images[user_id]
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error converting to PDF: {e}")
        await processing_msg.edit_text(f"❌ Error converting to PDF: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_to_pdf))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

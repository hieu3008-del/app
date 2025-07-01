import os
import logging
import json # Added for JSON parsing
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Import browsing tool (assuming it's available in the environment)
# The `browsing` tool is assumed to be available globally in this environment.

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7780349144:AAF5v-ovOyxGhXho__sU983UqE6iNjmSdDw")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "-5347449833")

# NEW: URL for the FAQ document
# IMPORTANT: Replace this with the actual URL of your FAQ document/webpage.
# Ensure the URL is publicly accessible and can be browsed by the environment.
DOCUMENT_URL = os.getenv("FAQ_DOCUMENT_URL", "https://uquid.freshdesk.com/a/solutions")

# Global variable to store the fetched document content
document_content = ""

# --- FAQ Data (Simplified - now less critical as LLM will handle dynamic questions) ---
# These are still used for the explicit button-based FAQ answers.
FAQ_DATA = {
    "shipping_info": {
        "question": "What are your shipping options and delivery times?",
        "answer": "We offer standard and express shipping. Standard delivery takes 5-7 business days, while express takes 1-2 business days. Shipping costs vary by location and speed.",
    },
    "return_policy": {
        "question": "What is your return policy?",
        "answer": "You can return most items within 30 days of purchase, provided they are in their original condition. Please visit our website's 'Returns' section for detailed instructions.",
    },
    "payment_methods": {
        "question": "What payment methods do you accept?",
        "answer": "We accept major credit cards (Visa, MasterCard, American Express), PayPal, and bank transfers.",
    },
    "contact_support": {
        "question": "I need to speak to someone directly.",
        "answer": "Please describe your issue briefly, and we will connect you with a human agent.",
    },
}

# --- Document Loading Function ---
async def load_faq_document() -> None:
    """
    Fetches the content of the FAQ document from the specified URL.
    This function uses the `browsing` tool to get the content.
    """
    global document_content
    if not DOCUMENT_URL or DOCUMENT_URL == "https://uquid.freshdesk.com/a/solutions":
        logger.warning("FAQ_DOCUMENT_URL is not set or is still the default example URL. "
                       "Dynamic question answering from a document will not work.")
        return

    logger.info(f"Attempting to load FAQ document from: {DOCUMENT_URL}")
    try:
        # Use the browsing tool to fetch the content from the URL
        # The `browsing` tool expects a query and a URL.
        # For fetching a document, the query can be descriptive.
        document_content = browsing.browse(query="Fetch FAQ document content", url=DOCUMENT_URL)
        logger.info("FAQ document loaded successfully.")
        # logger.debug(f"Loaded content snippet: {document_content[:200]}...") # Uncomment for debugging
    except Exception as e:
        logger.error(f"Failed to load FAQ document from {DOCUMENT_URL}: {e}")
        document_content = "" # Ensure it's empty if loading fails

# --- Bot Commands and Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and the main menu with FAQ options."""
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) started the bot.")

    keyboard = [
        [InlineKeyboardButton("Shipping Information", callback_data="faq_shipping_info")],
        [InlineKeyboardButton("Return Policy", callback_data="faq_return_policy")],
        [InlineKeyboardButton("Payment Methods", callback_data="faq_payment_methods")],
        [InlineKeyboardButton("Speak to a Human", callback_data="request_human_support")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"Hi {user.mention_html()}! 👋\n"
        "Welcome to our customer service. How can I help you today?\n\n"
        "Please choose from the options below, or type your question.",
        reply_markup=reply_markup,
    )

async def handle_faq_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboard buttons for FAQs."""
    query = update.callback_query
    await query.answer()

    faq_key = query.data.replace("faq_", "")
    faq_item = FAQ_DATA.get(faq_key)

    if faq_item:
        await query.edit_message_text(
            text=f"*{faq_item['question']}*\n\n{faq_item['answer']}\n\n"
                 "Was this helpful? You can choose another option or request human support.",
            parse_mode="Markdown"
        )
        # Re-send the menu after answering an FAQ
        keyboard = [
            [InlineKeyboardButton("Shipping Information", callback_data="faq_shipping_info")],
            [InlineKeyboardButton("Return Policy", callback_data="faq_return_policy")],
            [InlineKeyboardButton("Payment Methods", callback_data="faq_payment_methods")],
            [InlineKeyboardButton("Speak to a Human", callback_data="request_human_support")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("What else can I help you with?", reply_markup=reply_markup)
    else:
        await query.edit_message_text("Sorry, I couldn't find information on that topic.")
        await start(update, context)

async def request_human_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the request to speak to a human."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    user_name = user.full_name
    user_username = user.username if user.username else "N/A"

    await query.edit_message_text(
        "Okay, I'm connecting you to a human agent. Please wait a moment."
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🚨 *Human Support Request!* 🚨\n\n"
                 f"User: [{user_name}](tg://user?id={user_id})\n"
                 f"User ID: `{user_id}`\n"
                 f"Username: @{user_username}\n\n"
                 f"Please assist this user.",
            parse_mode="Markdown"
        )
        await query.message.reply_text(
            "A human agent has been notified and will contact you shortly. Thank you for your patience!"
        )
    except Exception as e:
        logger.error(f"Failed to send human support request to admin chat: {e}")
        await query.message.reply_text(
            "Sorry, there was an issue connecting you to a human agent. "
            "Please try again later or visit our website for more contact options."
        )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Attempts to answer the user's question using an LLM based on the loaded document content.
    If the document content is not available or the LLM cannot answer, it falls back.
    """
    user_message = update.message.text
    logger.info(f"User {update.effective_user.full_name} asked: '{user_message}'")

    if not document_content:
        await update.message.reply_text(
            "I'm sorry, the FAQ document is not available right now. "
            "Please choose an option from the menu or type /start to see the options again."
        )
        await start(update, context)
        return

    await update.message.reply_text("Thinking... Please wait while I find the answer for you.")

    try:
        # Construct the prompt for the LLM
        prompt = (
            f"You are a helpful customer service bot. Answer the following question based ONLY on the provided document content. "
            f"If the answer is not found in the document, state that you cannot answer based on the provided information. "
            f"Do not make up information.\n\n"
            f"Document Content:\n{document_content}\n\n"
            f"User Question: {user_message}\n\n"
            f"Answer:"
        )

        # Prepare payload for the Gemini API call
        # Note: The `fetch` function is assumed to be available in this environment,
        # handling HTTP requests. In a standard Python environment, you'd use `httpx` or `aiohttp`.
        chatHistory = []
        chatHistory.append({ "role": "user", "parts": [{ "text": prompt }] })
        payload = { "contents": chatHistory }

        # The API key is handled by the environment for gemini-2.0-flash
        apiKey = "" # Leave as empty string for Canvas to provide
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}"

        response = await fetch(apiUrl, {
            "method": 'POST',
            "headers": { 'Content-Type': 'application/json' },
            "body": json.dumps(payload)
        })
        result = await response.json()

        if result.candidates and len(result.candidates) > 0 and \
           result.candidates[0].content and result.candidates[0].content.parts and \
           len(result.candidates[0].content.parts) > 0:
            llm_answer = result.candidates[0].content.parts[0].text
            await update.message.reply_text(llm_answer)
        else:
            logger.warning(f"LLM did not return a valid answer for query: '{user_message}'")
            await update.message.reply_text(
                "I'm sorry, I couldn't find a direct answer to your question in our FAQ document. "
                "Please try rephrasing your question, choose an option from the menu, or request human support."
            )
            await start(update, context) # Show the menu again

    except Exception as e:
        logger.error(f"Error calling LLM for query '{user_message}': {e}")
        await update.message.reply_text(
            "I'm sorry, I encountered an error while trying to answer your question. "
            "Please choose an option from the menu or request human support."
        )
        await start(update, context) # Show the menu again

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.warning(f"Update {update} caused error {context.error}")

async def main() -> None:
    """Starts the bot."""
    # Create the Application and pass your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Load the FAQ document content when the bot starts
    await load_faq_document()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_faq_query, pattern=r"^faq_"))
    application.add_handler(CallbackQueryHandler(request_human_support, pattern="^request_human_support$"))

    # Handle messages that are not commands or callbacks (e.g., user typing something)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Log all errors
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    # Use `run_polling` for local development. For production deployment, you might use `run_webhook`.
    await application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot stopped.")

if __name__ == "__main__":
    # This block ensures the async main function is run when the script is executed.
    import asyncio
    asyncio.run(main())


from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from translations import translations

user_languages = {}

def ask_language():
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")],
        [InlineKeyboardButton("🇰🇷 한국어", callback_data="lang_ko")],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr")],
        [InlineKeyboardButton("🇯🇵 日本語", callback_data="lang_ja")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, *, show_main_menu_fn):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    user_languages[query.from_user.id] = lang
    await query.edit_message_text(translations["language_selected"][lang])
    await show_main_menu_fn(query.message, lang)

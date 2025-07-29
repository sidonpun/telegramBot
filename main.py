import os
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import SUPPORT_CONTACTS
from translations import translations
from games import games
from language import ask_language, handle_language_selection, user_languages
from functools import partial

LOADER_URL = "http://desync.pro:5000/home/download_packed"

user_game_selection = {}

def get_lang(user_id):
    return user_languages.get(user_id, "en")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(translations["start"]["en"], reply_markup=ask_language())

async def show_main_menu(target, lang):
    keyboard = [
        [InlineKeyboardButton(translations["menu_website"][lang], url="https://desync.pro/")],
        [InlineKeyboardButton(translations["menu_game"][lang], callback_data="menu_choose_game")],
        [InlineKeyboardButton(translations["menu_loader"][lang], callback_data="download_loader")],
        [InlineKeyboardButton(translations["menu_status"][lang], url="https://desync.pro/statuses")],
        [InlineKeyboardButton(translations["menu_faq"][lang], callback_data="faq")],
        [InlineKeyboardButton(translations["menu_support"][lang], callback_data="support")],
        [InlineKeyboardButton(translations["menu_language"][lang], callback_data="change_language")]
    ]
    await target.reply_text(translations["menu_title"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    if query.data == "menu_choose_game":
        await show_games(query.message, uid)

async def game_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    gid = query.data.split("_")[1]
    user_game_selection[uid] = gid
    game = games[gid]
    keyboard = [[InlineKeyboardButton(f"{d} days", callback_data=f"sub_{d}")] for d in game["durations"]]
    keyboard.append([InlineKeyboardButton(translations["menu_instruction"][lang], callback_data="guide")])
    keyboard.append([InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")])
    await query.edit_message_text(translations["choose_subscription"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

async def subscription_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    days = query.data.split("_")[1]
    gid = user_game_selection.get(uid)
    game = games[gid]
    text = translations["subscription_result"][lang].format(
        title=game["title"], days=days, desc=game["description"][lang], link=game["links"][days]
    )
    await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=back_to_main_button(lang))

async def guide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    gid = user_game_selection.get(uid)
    url = games[gid]["guide"]
    text = f"{translations['menu_instruction'][lang]}\n{url}"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_to_main_button(lang))

async def send_loader_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    await query.message.reply_text(
        translations["loader_password"][lang].format(url=LOADER_URL),
        parse_mode="Markdown",
    )

async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    faq_titles = {
        "faq_1": {
            "en": "How to activate subscription?",
            "ru": "Как активировать подписку?",
            "zh": "如何激活订阅？",
            "ko": "구독을 어떻게 활성화하나요?",
            "tr": "Abonelik nasıl etkinleştirilir?",
            "ja": "サブスクリプションの有効化方法は？"
        },
        "faq_2": {
            "en": "Where to download the game?",
            "ru": "Где скачать игру?",
            "zh": "在哪里下载游戏？",
            "ko": "게임은 어디서 다운로드하나요?",
            "tr": "Oyunu nereden indiririm?",
            "ja": "ゲームはどこでダウンロードできますか？"
        },
        "faq_3": {
            "en": "What to do if something doesn't work?",
            "ru": "Что делать, если не работает?",
            "zh": "如果不能使用怎么办？",
            "ko": "작동하지 않을 경우 어떻게 해야 하나요?",
            "tr": "Bir şey çalışmazsa ne yapmalıyım?",
            "ja": "動作しない場合はどうすればいいですか？"
        }
    }
    keyboard = [[InlineKeyboardButton(title[lang], callback_data=faq_id)] for faq_id, title in faq_titles.items()]
    keyboard.append([InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")])
    await query.edit_message_text("❓ " + translations["menu_faq"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

async def send_faq_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    faq_links = {
        "faq_1": "https://docs.google.com/document/d/xxxx1",
        "faq_2": "https://docs.google.com/document/d/xxxx2",
        "faq_3": "https://docs.google.com/document/d/xxxx3"
    }
    doc_url = faq_links.get(query.data)
    if doc_url:
        await query.edit_message_text(f"📄 {doc_url}", reply_markup=back_to_main_button(lang))
    else:
        await query.edit_message_text("❌ Вопрос не найден.", reply_markup=back_to_main_button(lang))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    await show_main_menu(query.message, lang)

def back_to_main_button(lang):
    return InlineKeyboardMarkup([[InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")]])

async def show_games(message, user_id):
    lang = get_lang(user_id)
    keyboard = [[InlineKeyboardButton(g["title"], callback_data=f"choose_{gid}")] for gid, g in games.items()]
    keyboard.append([InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")])
    await message.reply_text(translations["choose_game"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    support_text = "💬 *Support contacts:*\n" + "\n".join(f"• {name}" for name in SUPPORT_CONTACTS)
    await query.edit_message_text(support_text, parse_mode="Markdown", reply_markup=back_to_main_button(lang))

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(translations["start"]["en"], reply_markup=ask_language())

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(partial(handle_language_selection, show_main_menu_fn=show_main_menu), pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(game_selected, pattern="^choose_"))
    app.add_handler(CallbackQueryHandler(subscription_selected, pattern="^sub_"))
    app.add_handler(CallbackQueryHandler(guide_handler, pattern="^guide$"))
    app.add_handler(CallbackQueryHandler(send_faq_link, pattern="^faq_"))
    app.add_handler(CallbackQueryHandler(show_faq, pattern="^faq$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(send_loader_info, pattern="^download_loader$"))
    app.add_handler(CallbackQueryHandler(change_language, pattern="^change_language$"))
    app.run_polling()

if __name__ == "__main__":
    main()

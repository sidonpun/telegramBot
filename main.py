import os
from functools import partial, wraps

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import SUPPORT_CONTACTS
from games import games
from language import ask_language, handle_language_selection, user_languages
from translations import translations

load_dotenv()

LOADER_URL = "http://desync.pro:5000/home/download_packed"

# After each user interaction we will return to the main menu if there is no
# activity for this amount of seconds. Initially 30 seconds for testing.
INACTIVITY_SECONDS = 30

JOBQUEUE_ERROR = (
    "JobQueue is required for inactivity tracking. "
    'Install extras via `pip install "python-telegram-bot[job-queue]"`.'
)

user_game_selection: dict[int, str] = {}
inactivity_jobs: dict[int, object] = {}


def escape_markdown(text: str) -> str:
    """Escape characters that have special meaning in Markdown."""
    return text.replace("_", "\\_")


def duration_label(days: str, lang: str) -> str:
    """Return label for subscription duration in the given language."""
    key = "day" if days == "1" else "days"
    word = translations[key][lang]
    return f"{days} {word}"

def get_lang(user_id):
    return user_languages.get(user_id, "en")


def build_main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(translations["menu_website"][lang], url="https://desync.pro/")],
        [InlineKeyboardButton(translations["menu_game"][lang], callback_data="menu_choose_game")],
        [InlineKeyboardButton(translations["menu_loader"][lang], callback_data="download_loader")],
        [InlineKeyboardButton(translations["menu_status"][lang], url="https://desync.pro/statuses")],
        [InlineKeyboardButton(translations["menu_faq"][lang], callback_data="faq")],
        [InlineKeyboardButton(translations["menu_support"][lang], callback_data="support")],
        [InlineKeyboardButton(translations["menu_language"][lang], callback_data="change_language")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _ensure_job_queue(context: ContextTypes.DEFAULT_TYPE):
    """Return a working job queue or raise a helpful error."""
    job_queue = getattr(context, "job_queue", None)
    if job_queue is None:
        raise RuntimeError(JOBQUEUE_ERROR)
    return job_queue


def reset_inactivity_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, lang: str) -> None:
    job = inactivity_jobs.pop(user_id, None)
    if job:
        job.schedule_removal()
    job_queue = _ensure_job_queue(context)
    inactivity_jobs[user_id] = job_queue.run_once(
        handle_inactivity,
        INACTIVITY_SECONDS,
        chat_id=chat_id,
        data={"user_id": user_id, "lang": lang},
        name=f"inactivity_{user_id}",
    )


async def handle_inactivity(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    lang = data["lang"]
    await context.bot.send_message(
        context.job.chat_id,
        translations["session_timeout"][lang],
        reply_markup=build_main_menu_keyboard(lang),
    )
    inactivity_jobs.pop(data["user_id"], None)


def track_activity(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        result = await func(update, context, *args, **kwargs)
        user = update.effective_user
        chat = update.effective_chat
        if user and chat:
            lang = get_lang(user.id)
            reset_inactivity_timer(context, chat.id, user.id, lang)
        return result

    return wrapper

@track_activity
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(translations["start"]["en"], reply_markup=ask_language())

async def show_main_menu(target, lang):
    await target.reply_text(
        translations["menu_title"][lang],
        reply_markup=build_main_menu_keyboard(lang),
    )

@track_activity
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    if query.data == "menu_choose_game":
        await show_games(query.message, uid)

@track_activity
async def game_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    gid = query.data.split("_")[1]
    user_game_selection[uid] = gid
    game = games[gid]
    keyboard = []
    for d in game["durations"]:
        label = duration_label(d, lang)
        keyboard.append([InlineKeyboardButton(label, callback_data=f"sub_{d}")])
    keyboard.append([InlineKeyboardButton(translations["menu_instruction"][lang], callback_data="guide")])
    keyboard.append([InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")])
    await query.edit_message_text(translations["choose_subscription"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

@track_activity
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

@track_activity
async def guide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    gid = user_game_selection.get(uid)
    url = games[gid]["guide"]
    text = f"{translations['menu_instruction'][lang]}\n{escape_markdown(url)}"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_to_main_button(lang))

@track_activity
async def send_loader_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    await query.message.reply_text(
        translations["loader_password"][lang].format(url=LOADER_URL),
        parse_mode="Markdown",
    )

@track_activity
async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    faq_titles = {
        "faq_1": {
            "en": "What to do after purchase?",
            "ru": "Что делать после покупки?",
            "zh": "购买后该怎么办？",
            "ko": "구매 후 무엇을 해야 하나요?",
            "tr": "Satın aldıktan sonra ne yapmalıyım?",
            "ja": "購入後はどうすればいいですか？",
        },
        "faq_2": {
            "en": "Secure boot & UEFI",
            "ru": "Secure boot & UEFI",
            "zh": "Secure boot 与 UEFI",
            "ko": "Secure boot & UEFI",
            "tr": "Secure boot & UEFI",
            "ja": "Secure boot と UEFI",
        },
        "faq_3": {
            "en": "Additional loader settings",
            "ru": "Дополнительные настройки лоадера",
            "zh": "Loader 的其他设置",
            "ko": "로더 추가 설정",
            "tr": "Loader ek ayarlar",
            "ja": "ローダーの追加設定",
        },
        "faq_4": {
            "en": "Bought cheat elsewhere, help",
            "ru": "Купил чит в другом месте, помогите",
            "zh": "在别处买了外挂，帮帮我",
            "ko": "다른 곳에서 핵을 샀습니다. 도와주세요",
            "tr": "Hileyi başka yerde aldım, yardım edin",
            "ja": "他でチートを買いました。助けて",
        },
        "faq_5": {
            "en": "Antivirus / anticheat settings",
            "ru": "Antivirus / anticheat settings",
            "zh": "杀毒 / 反作弊设置",
            "ko": "백신/안티치트 설정",
            "tr": "Antivirus/anticheat ayarları",
            "ja": "アンチウイルス/アンチチート設定",
        },
        "faq_6": {
            "en": "Problem with cheat or launch, what to do?",
            "ru": "Проблема с читом / запуском, что делать?",
            "zh": "外挂/启动问题怎么办？",
            "ko": "핵/실행 문제, 어떻게 해야 하나요?",
            "tr": "Hile/başlatma sorunu, ne yapmalıyım?",
            "ja": "チート/起動の問題、どうすれば？",
        },
        "faq_7": {
            "en": "24h bans PUBG",
            "ru": "24h bans PUBG",
            "zh": "24小时封禁 PUBG",
            "ko": "PUBG 24시간 정지",
            "tr": "PUBG 24 saat ban",
            "ja": "PUBGの24時間BAN",
        },
        "faq_8": {
            "en": "Sorry, this application cannot run under Virtual Machine",
            "ru": "Sorry, this application cannot run under Virtual Machine",
            "zh": "抱歉，此应用无法在虚拟机中运行",
            "ko": "죄송합니다. 이 프로그램은 가상 머신에서 실행될 수 없습니다",
            "tr": "Üzgünüz, bu uygulama sanal makinede çalışamaz",
            "ja": "申し訳ありませんが、このアプリは仮想マシンでは実行できません",
        },
        "faq_9": {
            "en": "ASLR windows defender",
            "ru": "ASLR windows defender",
            "zh": "ASLR windows defender",
            "ko": "ASLR windows defender",
            "tr": "ASLR windows defender",
            "ja": "ASLR windows defender",
        },
        "faq_10": {
            "en": "Payment questions",
            "ru": "Вопросы по оплате",
            "zh": "支付问题",
            "ko": "결제 관련 질문",
            "tr": "Ödeme soruları",
            "ja": "支払いに関する質問",
        },
        "faq_11": {
            "en": "Are there any discounts or coupons?",
            "ru": "Есть ли какие-то скидки / купоны?",
            "zh": "有折扣/优惠券吗？",
            "ko": "할인이나 쿠폰이 있나요?",
            "tr": "Herhangi bir indirim veya kupon var mı?",
            "ja": "割引やクーポンはありますか？",
        },
        "faq_12": {
            "en": "Where to get cryptocurrency",
            "ru": "Где взять криптовалюту",
            "zh": "哪里获取加密货币",
            "ko": "암호화폐는 어디서 구하나요?",
            "tr": "Kripto para nereden alabilirim",
            "ja": "暗号通貨はどこで入手できますか",
        },
        "faq_13": {
            "en": "Subscription freezing",
            "ru": "Заморозка подписки",
            "zh": "暂停订阅",
            "ko": "구독 일시 정지",
            "tr": "Aboneliği dondurma",
            "ja": "サブスクリプションの凍結",
        },
        "faq_14": {
            "en": "Subscription transfer",
            "ru": "Перенос подписки",
            "zh": "转移订阅",
            "ko": "구독 이전",
            "tr": "Aboneliği taşıma",
            "ja": "サブスクリプションの移行",
        },
        "faq_15": {
            "en": "When will the cheat be updated?",
            "ru": "Когда обновят чит?",
            "zh": "什么时候更新外挂？",
            "ko": "핵은 언제 업데이트되나요?",
            "tr": "Hile ne zaman güncellenecek?",
            "ja": "チートはいつ更新されますか？",
        },
        "faq_16": {
            "en": "How to enable spoofer?",
            "ru": "Как включить спуфер?",
            "zh": "如何开启欺骗器?",
            "ko": "스푸퍼를 켜려면?",
            "tr": "Spoofer nasıl açılır?",
            "ja": "スプーファーを有効にするには？",
        },
    }
    keyboard = [[InlineKeyboardButton(title[lang], callback_data=faq_id)] for faq_id, title in faq_titles.items()]
    keyboard.append([InlineKeyboardButton(translations["back"][lang], callback_data="back_to_main")])
    await query.edit_message_text("❓ " + translations["menu_faq"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

@track_activity
async def send_faq_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    faq_links = {
        "faq_1": "https://docs.google.com/document/d/1MfuO-0WRbwu6gXjv2VKfuZPU294_bEOeSczHQMWvtQI/edit?tab=t.0#heading=h.jpyqgkmaltcj",
        "faq_2": "https://docs.google.com/document/d/1gMyIKqeMjLwlnmtfeW3u9d7holGtamNAmtkSGmLXvPk/edit?tab=t.0#heading=h.lr6zthfd0myp",
        "faq_3": "https://docs.google.com/document/d/1zJkuqf6WRJsbhDw2pcuyo9qvFHL7qccRjTZu16_eO_U/edit?tab=t.0#heading=h.f14wq4uqpmlu",
        "faq_4": "https://docs.google.com/document/d/1Rh-7X6hl_qSEWLnMe0k1JZ0BRdhiGB74oFvml9xbOxM/edit?tab=t.0#heading=h.sxeylmtoyft",
        "faq_5": "https://docs.google.com/document/d/1P4H4KNaW3cTZM-COkU1Q673jDxIB-zSFtDAuNw7pV_8/edit?tab=t.0#heading=h.snl0ea7h39p9",
        "faq_6": "https://docs.google.com/document/d/1pj1ttxVbPbBwmv9ngmvL84YEP04QtgYhyPau_sZSEPk/edit?tab=t.0#heading=h.34jmecbadn9c",
        "faq_7": "https://docs.google.com/document/d/174uELSHPfE5n2ZBQSp6QRtEMs1l3XAxKZY2FqXJVAZQ/edit?tab=t.0#heading=h.n3aovjwsw5s2",
        "faq_8": "https://docs.google.com/document/d/1aJd6RNmjpJeTdOqEiVPyJk8H6g9gCFACpwUszdWsEgU/edit?tab=t.0",
        "faq_9": "https://docs.google.com/document/d/1ygELrYJPOtRkRMLV_OPS8NOqw28LhlOWRB3pNDyXGwE/edit?tab=t.0#heading=h.s7qc8wtl3l0q",
        "faq_10": "https://docs.google.com/document/d/1xdg75FQQazrgSa563Fadzp9lNLdcQUpFsK2rvSAnJKA/edit?tab=t.0#heading=h.mmu7ffux95z7",
        "faq_11": "https://docs.google.com/document/d/147zpS3DUUKZAwO8K18bn-sxGjjlKzLl_CLH-1tnohKw/edit?tab=t.0",
        "faq_12": "https://docs.google.com/document/d/13nTn03ziGMq-UDOtUhV0EpMIn8-s_AIOYeYCS2-HCPE/edit?tab=t.0#heading=h.lhjokw49jht7",
        "faq_13": "https://docs.google.com/document/d/11Hqj9LICiwNF7I6CreuB2PPB5fNUYzkLIWayH6z6Vfs/edit?tab=t.0#heading=h.abdlztxcnvgy",
        "faq_14": "https://docs.google.com/document/d/11bYA17l0Ed74a23d6-8BKYJ0lwLPKvP8QVFp-ePO0tA/edit?tab=t.0#heading=h.706a7uunpv3d",
        "faq_15": "https://docs.google.com/document/d/19yWs7tvSwmmk9Tm9dA8Y0Hr7Y-1_vR28_oYmilHcfe4/edit?tab=t.0#heading=h.b57i0xsait03",
        "faq_16": "https://docs.google.com/document/d/1KAwkU2oy9PS04zgn96Oe4jOIM8-uiLns7_BSQ_SwQCE/edit?tab=t.0#heading=h.yqdxjguk2tpn",
    }
    doc_url = faq_links.get(query.data)
    if doc_url:
        await query.edit_message_text(f"📄 {doc_url}", reply_markup=back_to_main_button(lang))
    else:
        await query.edit_message_text("❌ Вопрос не найден.", reply_markup=back_to_main_button(lang))

@track_activity
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

@track_activity
async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user.id)
    contacts = "\n".join(f"• {escape_markdown(name)}" for name in SUPPORT_CONTACTS)
    support_text = "💬 *Support contacts:*\n" + contacts
    await query.edit_message_text(support_text, parse_mode="Markdown", reply_markup=back_to_main_button(lang))

@track_activity
async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(translations["start"]["en"], reply_markup=ask_language())

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = Application.builder().token(token).build()
    if app.job_queue is None:
        raise RuntimeError(JOBQUEUE_ERROR)
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

import sys
import types
import importlib
from pathlib import Path

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Provide dummy telegram modules so main can be imported without dependency.
telegram = types.ModuleType('telegram')
telegram.InlineKeyboardButton = object
telegram.InlineKeyboardMarkup = object
telegram.Update = object

telegram_ext = types.ModuleType('telegram.ext')
telegram_ext.Application = object
telegram_ext.CommandHandler = object
telegram_ext.CallbackQueryHandler = object
telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)

sys.modules.setdefault('telegram', telegram)
sys.modules.setdefault('telegram.ext', telegram_ext)

main = importlib.import_module('main')


def test_get_lang_default_english():
    assert main.get_lang(999) == 'en'


def test_get_lang_after_selection(monkeypatch):
    monkeypatch.setitem(main.user_languages, 123, 'ru')
    assert main.get_lang(123) == 'ru'


def test_loader_password_contains_url():
    for lang in ('en', 'ru', 'zh', 'ko', 'tr', 'ja'):
        text = main.translations['loader_password'][lang].format(url=main.LOADER_URL)
        assert main.LOADER_URL in text


def test_tarkov_in_games():
    assert 'tarkov' in main.games
    game = main.games['tarkov']
    assert game['durations'] == ['1', '15', '30']

import os
from aiogram import Bot, types
from aiogram.types import Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils.emoji import emojize
from aiogram.utils.executor import start_webhook
import logging
import psycopg2
from urllib.parse import urlparse

# bot initialization
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# admin id define
admin = os.getenv('ADMIN_ID')

# webhook settings
APP_NAME = os.getenv('APP_NAME')
WEBHOOK_HOST = f'https://{APP_NAME}.herokuapp.com'
WEBHOOK_PATH = '/webhook/' + BOT_TOKEN
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv("PORT", default=8000))

# database setup
DB_URL = os.getenv('DATABASE_URL')
db_parse = urlparse(DB_URL)
db_username = db_parse.username
db_password = db_parse.password
db_name = db_parse.path[1:]
db_hostname = db_parse.hostname
db_port = db_parse.port
conn = psycopg2.connect(
    database=db_name,
    user=db_username,
    password=db_password,
    host=db_hostname,
    port=db_port
)
cur = conn.cursor()
'''
Database structure:
- "*" means preset value 
column(0): id; integer (default = -1)
*column(1): username; char(300)
*column(2): full_name; char(300)
*column(3): wallet_id; char(64) (contains lolcoin wallet id of len 64)
column(4): balance; integer (default = 0)
column(5): is_active; boolean (default = false)
'''


# states initialization
class SG(StatesGroup):
    ReportState = State()


# keyboard initialization
reportkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
reportkb.add(types.InlineKeyboardButton(text='Отменить ' + emojize(":x:")))


# main part with all bot commands
async def on_startup(dispatcher):
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(dispatcher):
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    conn.close()
    # await dp.storage.close()
    # await dp.storage.wait_closed()
    logging.warning('Bye!')


async def help_message(message: Message):
    await message.answer('Как пополнить баланс вы можете узнать при помощи команды /balance.\nПосмотреть '
                         'текущие товары и услуги можно командой /services.\nЕсли у вас остались вопросы, '
                         'возможно вы найдете ответы, введя команду /fag, в противном случае задайте '
                         'вопрос админу при помощи всё того же /report.\nЕсли вам понадобится перечитать это '
                         'сообщение, напишите /help.\nВы также можете использовать встроенную клавиатуру '
                         'вместо того, чтобы писать команды.')


@dp.message_handler(commands=['start'])
async def start(message: Message):
    username = '@' + message.from_user.username
    cur.execute(f"""SELECT * FROM users WHERE username = '{username}'""")
    result = cur.fetchone()
    if not result:
        username = message.from_user.first_name + ' ' + message.from_user.last_name
        cur.execute(f"""SELECT * FROM users WHERE username = '{username}'""")
        result = cur.fetchone()
    if result:
        if not result[5]:
            cur.execute(
                f"""UPDATE users SET is_active = true WHERE username = '{username}'"""
            )
            cur.execute(
                f"""UPDATE users SET id = {message.from_user.id} WHERE username = '{username}'"""
            )
            conn.commit()
            await message.answer(f'Приветствую, {result[1]}! Мы опредеили вас, как {result[2].strip()}. Если это не так'
                                 f', пожалуйста, напишите нам свои имя и фамилию при помощи команды /report. Если '
                                 f'этого не сделать, вы будете привязаны к чужому кошельку и не сможете пополнять ваш '
                                 f'баланс.')
            await help_message(message)
            await message.answer('Приятного пользования ' + emojize(':upside_down:'))
        else:
            if result[0] != message.from_user.id:
                await message.answer('Извините, кажется произошла какая-то накладка, видимо у вас совпал ник в '
                                     'телеграм-аккаунте с кем-то другим. Пожалуйста, напишите нам свои имя и '
                                     'фамилию при помощи команды /report, чтобы мы исправили эту ошибку.')
            else:
                await message.answer(f'Ещё раз приветствую вас, {result[1]}!')
    else:
        await message.answer('Извините, мы не смогли определить вас как ученика лагеря ЛОЛ. Увы, мы не смогли найти '
                             'телеграм-аккаунт каждого, пожалуйста, напишите нам свои имя и фамилию при помощи '
                             'команды /report')


@dp.message_handler(commands=['help'])
@dp.message_handler(content_types=['text'], text='Команды')
async def help_command(message: Message):
    await help_message(message)


@dp.message_handler(commands=['report'])
@dp.message_handler(content_types=['text'], text='Жалоба')
async def report_command(message: Message):
    await SG.ReportState.set()
    await message.answer('Следующим сообщением напишите текст вашего обращения. Если вы передумали, напишите команду '
                         '/cancel, или выберете соответствующую опцию в вашей встроенной клавиатуре.', reply_markup=reportkb)


@dp.message_handler(state=SG.ReportState)
async def report_send(message: Message, state: FSMContext):
    if message.text == '/cancel' or message.text == 'Отменить ' + emojize(":x:"):
        await message.answer('Действие успешно отменено ' + emojize(":white_check_mark:"))
        await state.finish()
    else:
        await bot.send_message(admin, message.text)
        await message.answer('Репорт успешно отправлен ' + emojize(":white_check_mark:"))


@dp.message_handler()
async def echo(message: Message):
    await message.answer(message.text)


# bot start
if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )

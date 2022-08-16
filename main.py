import os
from aiogram import Bot, types
from aiogram.types import Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.utils.executor import start_webhook
import logging

# bot initialization
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# webhook settings
APP_NAME = os.getenv('APP_NAME')
WEBHOOK_HOST = f'https://{APP_NAME}.herokuapp.com'
WEBHOOK_PATH = '/webhook/' + BOT_TOKEN
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv("PORT", default=8000))


# main part with all bot commands
async def on_startup(dispatcher):
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(dispatcher):
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    # await dp.storage.close()
    # await dp.storage.wait_closed()
    logging.warning('Bye!')


@dp.message_handler(commands=['start'])
async def start(message: Message):
    await message.answer('Oh, hello there!')


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

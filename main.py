import os
from aiogram import Bot, types, executor
from aiogram.types import Message
from aiogram.types.message import ContentTypes, ParseMode
import aiogram.utils.markdown as md
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import logging
import psycopg2
from urllib.parse import urlparse
from transactions_parser import parsing
from sending_script import send_lolcoin
import asyncio

# Bot initialization
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Admin id define
admin = os.getenv('ADMIN_ID')

# Database setup
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


# States initialization
class SG(StatesGroup):
    BasicState = State()
    ReportState = State()
    ServicesList = State()
    WithdrawState = State()
    BuyingState = State()
    SelectStatus = State()
    StatusState = State()
    FinishStatus = State()
    DeleteStatus = State()
    CancelStatus = State()
    ReportNoState = State()


class SellSG(StatesGroup):
    Header = State()
    Description = State()
    DefType = State()
    DefContact = State()
    InMessage = State()
    InFile = State()
    Cost = State()
    Count = State()


class AdminSG(StatesGroup):
    DeleteServiceAS = State()


# Keyboards initialization
cancelkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
cancelbutton = types.InlineKeyboardButton(text='Отменить ❌')
cancelkb.add(cancelbutton)

skipkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
skipkb.add(types.InlineKeyboardButton(text='Пропустить ⏩'))
skipkb.add(cancelbutton)

dskb = types.ReplyKeyboardMarkup(resize_keyboard=True)
dskb.add(types.InlineKeyboardButton(text='DEFAULT')).add(types.InlineKeyboardButton(text='SPECIAL')).add(cancelbutton)

contactkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
contactkb.add(types.InlineKeyboardButton('Отправить свой контакт ☎', request_contact=True)).add(cancelbutton)

backkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
backkb.add(types.InlineKeyboardButton('Вернуться в меню ⏪'))

basekb = types.ReplyKeyboardMarkup(resize_keyboard=True)
button1 = types.InlineKeyboardButton(text='Баланс 💸')
button2 = types.InlineKeyboardButton(text="Жалоба ❗")
button3 = types.InlineKeyboardButton(text='Список товаров 📄')
button4 = types.InlineKeyboardButton(text='Заключить сделку 📝')
button5 = types.InlineKeyboardButton(text='Выставить на продажу 💰')
button6 = types.InlineKeyboardButton(text='Текущие сделки 💼')
button7 = types.InlineKeyboardButton(text="Вывести lolcoin 💳")
button8 = types.InlineKeyboardButton(text="Команды ❔")
button9 = types.InlineKeyboardButton(text="FAQ ❓")
basekb.row(button1, button2).row(button3, button4).row(button5, button6).add(button7).row(button8, button9)


# Switching state and keyboard to basic function
async def switch_to_base(message: Message):
    await SG.BasicState.set()
    await message.answer("Выберите дейсвтие:", reply_markup=basekb)


# Main part with all bot commands:


# Sending commands list function
async def help_message(message: Message):
    await message.answer('- Как пополнить баланс вы можете узнать при помощи команды /balance.\n'
                         '- Посмотреть текущие товары и услуги можно командой /services.\n'
                         '- Оформить заказ вы можете с помощью /buy.\n'
                         '- Чтобы выставить товар на продажу используйте /sell. \n'
                         '- Управлять статусом текущих сделок можно при помощи /status \n'
                         '- Вы можете снять деньги с платформы командой /withdraw\n'
                         '- Если у вас остались вопросы, возможно вы найдете ответы, введя команду /faq, в противном'
                         ' случае задайте вопрос админу при помощи всё того же /report.\n'
                         '- Если вам понадобится перечитать это сообщение, напишите /help.\n'
                         'Вы также можете использовать встроенную клавиатуру вместо того, чтобы писать команды.')


@dp.message_handler(content_types=['text'], text=['/report'])
async def report_command_no_state(message: Message):
    await message.answer('Следующим сообщением напишите текст вашего обращения.')
    await SG.ReportNoState.set()


@dp.message_handler(state=SG.ReportNoState)
async def report_send_no_state(message: Message, state: FSMContext):
    await bot.forward_message(admin, message.chat.id, message.message_id)
    await bot.send_message(admin, md.text(str(message.from_user.username), message.from_user.first_name,
                                          str(message.from_user.last_name), sep='\n'))
    await message.answer('Репорт успешно отправлен ✅')
    await state.finish()

# Checking if user is in db when starting using bot. If he is not,
# he won't be able to use bot commands until admin add him to users table.
@dp.message_handler(state=None)
async def start(message: Message):
    username = '@' + str(message.from_user.username)
    cur.execute(f"""SELECT * FROM users WHERE username = %s""", (username,))
    result = cur.fetchone()
    if not result:
        surname = message.from_user.last_name
        if not surname:
            username = message.from_user.first_name
        else:
            username = message.from_user.first_name + ' ' + message.from_user.last_name
        cur.execute(f"""SELECT * FROM users WHERE username = %s""", (username,))
        result = cur.fetchone()
    if result:
        if not result[5]:
            cur.execute(
                f"""UPDATE users SET is_active = true WHERE username = %s""",
                (username,)
            )
            cur.execute(
                f"""UPDATE users SET id = %s WHERE username = %s""",
                (message.from_user.id, username,)
            )
            conn.commit()
            await message.answer(f'Приветствую, {result[1]}! Мы опредеили вас, как {result[2].strip()}. Если это не так'
                                 f', пожалуйста, напишите нам свои имя и фамилию при помощи команды /report. Если '
                                 f'этого не сделать, вы будете привязаны к чужому кошельку и не сможете пополнять ваш '
                                 f'баланс.')
            await help_message(message)
            await message.answer('Приятного пользования 🙃')
            await switch_to_base(message)
        else:
            if result[0] != message.from_user.id:
                await message.answer('Извините, кажется произошла какая-то накладка, видимо у вас совпал ник в '
                                     'телеграм-аккаунте с кем-то другим. Пожалуйста, напишите нам свои имя и '
                                     'фамилию при помощи команды /report, чтобы мы исправили эту ошибку.')
            else:
                await message.answer(f'Ещё раз приветствую вас, {result[1]}! Бот был перезапущен и ваша сессия была '
                                     f'оборвана, перенаправляем вас обрано...')
                await switch_to_base(message)
    else:
        await message.answer('Извините, мы не смогли определить вас как ученика лагеря ЛОЛ. Увы, мы не смогли найти '
                             'телеграм-аккаунт каждого, пожалуйста, напишите нам свои имя и фамилию при помощи '
                             'команды /report')


@dp.message_handler(state='*', content_types=['text'], text=['Отменить ❌', '/cancel'])
async def cancel_command(message: Message, state=FSMContext):
    current_state = await state.get_state()
    if current_state is None or current_state == SG.BasicState.state or current_state == SG.ServicesList.state \
            or current_state == SG.SelectStatus.state:
        return
    await message.answer('Действие успешно отменено ✅')
    await switch_to_base(message)


@dp.message_handler(state=[SG.ServicesList, SG.SelectStatus], content_types=['text'],
                    text=['Вернуться в меню ⏪', '/back'])
async def back(message: Message, state=FSMContext):
    await switch_to_base(message)


# Checking balance command
@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Баланс 💸', '/balance'])
async def balance_command(message: Message):
    cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (message.from_user.id,))
    user_balance = float(cur.fetchone()[0]) / 100
    await bot.send_photo(message.chat.id, "https://i.imgur.com/haJcqm1.png",
                         f'<b>На вашем счету {user_balance} lolcoin</b>\nЧтобы пополнить счет переведите от 2 lolcoin '
                         f'на lolcoin_platform.near. При любом переводе 1 lolcoin будет взят в качестве комиссии, '
                         f'а остальное будет зачислено на ваш баланс. После перевода в течении следующей минуты '
                         f'система прочитает ваш перевод и вам придёт сообщение о успешном пополнении баланса. Если '
                         f'же этого не произошло, убедитесь что вы перевели не менее 2 lolcoin в период после того, '
                         f'как начали работать с ботом и напишите о проблеме "/report".',
                         parse_mode=ParseMode.HTML
                         )


# Report command
@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Жалоба ❗', '/report'])
async def report_command(message: Message):
    await SG.ReportState.set()
    await message.answer('Следующим сообщением напишите текст вашего обращения. Если вы передумали, напишите команду '
                         '/cancel, или выберете соответствующую опцию в вашей встроенной клавиатуре.',
                         reply_markup=cancelkb)


@dp.message_handler(state=SG.ReportState)
async def report_send(message: Message):
    await bot.forward_message(admin, message.chat.id, message.message_id)
    await bot.send_message(admin, md.text(str(message.from_user.username), message.from_user.first_name,
                                          str(message.from_user.last_name), sep='\n'))
    await message.answer('Репорт успешно отправлен ✅')
    await switch_to_base(message)


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Список товаров 📄', '/services',
                                                                       'Заключить сделку 📝', '/buy'])
async def services_command(message: Message, state: FSMContext):
    cur.execute("""SELECT * FROM products_list ORDER BY id""")
    answer_text = ''
    while True:
        result = cur.fetchone()
        if not result:
            break
        if result[8]:
            answer_text = f"{result[0]}) <i>Временно недоступно</i>\n"
        else:
            answer_text += f"{result[0]}) <b>{result[1]}</b> - {result[9]} ЛОЛ\n"
    if not answer_text:
        await message.answer('Сейчас на платформе нету доступный товаров, но вы можете это исправить, выставив на '
                             'продажу свой!')
        return
    await message.answer(answer_text, parse_mode="HTML")
    await SG.ServicesList.set()
    async with state.proxy() as data:
        data["is_buying"] = message.text == 'Заключить сделку 📝' or message.text == '/buy'
        if not data["is_buying"]:
            await message.answer(
                'Напишите айди (число перед названием) интересующего вас товара, чтобы посмотреть подробную '
                'информацию о нём, или напишите "/back", чтобы вернуться в меню.', reply_markup=backkb)
        else:
            await message.answer(
                'Напишите айди (число перед названием) заинтересовавшего вас товара, или напишите "/back", чтобы '
                'вернуться в меню.', reply_markup=backkb)


@dp.message_handler(lambda message: message.text.isdigit(), state=SG.ServicesList)
async def service_desc(message: types.Message, state=FSMContext):
    cur.execute(f"""SELECT * FROM products_list WHERE id = %s AND buyer = 0""", (message.text,))
    result = cur.fetchone()
    if not result:
        await message.answer("Некоректный айди, попробуйте ещё раз.")
        return
    if result[10]:
        service_type = "SPECIAL"
    else:
        service_type = "DEFAULT"
    if result[2]:
        service_description = result[2]
    else:
        service_description = 'Описание не прилагается.'
    await message.answer(md.text(
        md.hbold(result[1]), md.text(service_description), md.hcode('Тип товара —', service_type), sep='\n\n'
        ), parse_mode="HTML"
    )
    async with state.proxy() as data:
        if data["is_buying"]:
            await state.update_data(service_id=int(message.text))
            await message.answer('Чтобы подтвердить покупку, напишите "Подтвердить". Если вы не хотите покупать этот '
                                 'товар, напишите что-либо другое, или воспользуйтесь командой отмены.',
                                 reply_markup=cancelkb)
            await SG.BuyingState.set()
        else:
            await message.answer('Напишите айди (число перед названием) интересующего вас товара, чтобы посмотреть '
                                 'подробную информацию о нём, или напишите "/back", чтобы вернуться в меню.')


@dp.message_handler(state=SG.BuyingState, content_types=['text'])
async def buying_finish(message: Message, state: FSMContext):
    if message.text != "Подтвердить":
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        async with state.proxy() as data:
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (message.from_user.id,))
            user_result = cur.fetchone()
            cur.execute(f"""SELECT * FROM products_list WHERE id = %s""", (data['service_id'],))
            product_result = cur.fetchone()
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (product_result[3],))
            seller_result = cur.fetchone()
            user_balance = float(user_result[0]) / 100
            if message.from_user.id == product_result[3]:
                await message.answer("Вы не можете купить свой товар, каким бы заманчивым он ни был.")
                await switch_to_base(message)
                return
            if int(product_result[9]) <= user_balance:
                if not product_result[10]:
                    await bot.send_message(product_result[3], f'{message.from_user.first_name} купил ваш товар с '
                                                              f'названием "{product_result[1]}"!')
                    cur.execute(
                        """UPDATE users SET balance = %s WHERE id = %s""",
                        (user_result[0] - product_result[9] * 100, message.from_user.id,)
                    )
                    cur.execute(
                        """UPDATE users SET balance = %s WHERE id = %s""",
                        (seller_result[0] + product_result[9] * 100, product_result[3],)
                    )
                    if product_result[7] > 1:
                        cur.execute("""UPDATE products_list SET count = %s WHERE id = %s""",
                                    (product_result[7] - 1, product_result[0],))
                    elif product_result[7] == 1:
                        cur.execute("""DELETE FROM products_list WHERE id = %s""", (product_result[0],))
                        cur.execute("""UPDATE products_list SET id = id - 1 WHERE id > %s""", (product_result[0],))
                        await bot.send_message(product_result[3], 'Товар распродан!!')
                    conn.commit()
                    await message.answer("Готово!")
                    await bot.forward_message(message.chat.id, product_result[4], product_result[5])
                    if product_result[6]:
                        await bot.forward_message(message.chat.id, product_result[4], product_result[6])
                    if product_result[11]:
                        await bot.forward_message(message.chat.id, product_result[4], product_result[11])
                    await switch_to_base(message)
                else:
                    await bot.send_message(product_result[3], f'{message.from_user.first_name} купил ваш SPECIAL товар '
                                                              f'с названием "{product_result[1]}"! Готовьтесь '
                                                              'принимать покупателя в личных сообшениях! В случае '
                                                              'если с передачей возникнут проблемы, вы сможете '
                                                              'отменить сделку в соответствующем меню.')
                    cur.execute(
                        """UPDATE users SET balance = %s WHERE id = %s""",
                        (user_result[0] - product_result[9] * 100, message.from_user.id,)
                    )
                    cur.execute("""UPDATE products_list SET buyer = %s WHERE id = %s""",
                                (message.from_user.id, product_result[0],))
                    conn.commit()
                    await message.answer("Готово! Напишите в личные сообщения продавцу, чтобы он передал вам товар. "
                                         "После окончания сделки, не поленитесь зайти в меню текущих сделок и "
                                         "подтвердить покупку, чтобы продавцу пришли списанные с вашего баланса "
                                         "деньги.")
                    await bot.forward_message(message.chat.id, product_result[4], product_result[5])
                    if product_result[6]:
                        await bot.forward_message(message.chat.id, product_result[4], product_result[6])
                    if product_result[11]:
                        await bot.forward_message(message.chat.id, product_result[4], product_result[11])
                    await switch_to_base(message)
            else:
                await message.answer('У вас недостаточно ЛОЛ на балансе!')
                await switch_to_base(message)


# Adding product command


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Выставить на продажу 💰', '/sell'])
async def sell_command(message: Message, state: FSMContext):
    await SellSG.Header.set()
    await state.update_data(seller=message.from_user.id)
    await state.update_data(chat_id=message.chat.id)
    await message.answer('Чтобы выставить свой товар на продажу, для начала укажите название (запрещены символы: < _ '
                         '\ *)', reply_markup=cancelkb)


@dp.message_handler(state=SellSG.Header, content_types=['text'])
async def header_def(message: Message, state=FSMContext):
    if len(message.text) > 20:
        await message.answer("Название слишком длиное, вам  нужно уложиться в 20 символов. Всю дополнительную "
                             "информацию можно будет добавить в описание товара.")
    else:
        if '*' in message.text or chr(92) in message.text or '<' in message.text or '_' in message.text:
            await message.answer('Обноружен запрещенный символ. Отправьте название без символов < _ \ *')
            return
        async with state.proxy() as data:
            data['name'] = message.text
        await message.answer('Готово! Теперь укажите описание, или пропустите этот пункт с помошью /skip (запрещены '
                             'символы: < _ \ *)',
                             reply_markup=skipkb)
        await SellSG.next()


@dp.message_handler(state=SellSG.Description, content_types=['text'])
async def description_def(message: Message, state=FSMContext):
    if len(message.text) > 1000:
        await message.answer("Описание слишком длиное, вам  нужно уложиться в 1000 символов.")
        return
    elif message.text == '/skip' or message.text == 'Пропустить ⏩':
        async with state.proxy() as data:
            data['description'] = ''
    else:
        if '*' in message.text or chr(92) in message.text or '<' in message.text or '_' in message.text:
            await message.answer('Обноружен запрещенный символ. Отправьте описание без символов < _ \ *')
            return
        async with state.proxy() as data:
            data['description'] = message.text
    await message.answer('Принято! Перейдём к определению товара. Если ваш товар можно представить как файл, '
                         'текст, или картинку, нажмите DEFAULT. Иначе нажмите SPECIAL', reply_markup=dskb)
    await SellSG.next()


@dp.message_handler(state=SellSG.DefType, content_types=['text'])
async def type_def(message: Message, state=FSMContext):
    if message.text == 'DEFAULT':
        async with state.proxy() as data:
            data['is_special'] = False
        await state.update_data(contact_id=0)
        await message.answer('Теперь отправьте сообщение, который увидит человек после покупки. Это могут быть как '
                             'выражение благодарности, или просто какое-то обращение, так и сам товар. Сообщение может '
                             'быть любым, однако учтите, что отправляя любым способом больше одного медиафайла, '
                             'это будет уже не одно сообщение, и будет прикреплен лишь один из них. Учтите, что '
                             'возможность добавить файл еще будет вам предоставлена в отдельном пункте.',
                             reply_markup=cancelkb)
        await SellSG.InMessage.set()
    elif message.text == 'SPECIAL':
        async with state.proxy() as data:
            data['is_special'] = True
        await message.answer('Особенные товары отличаются от обычных тем, что не могут быть переданы посредством '
                             'telegram. Когда кто-то решает купить такой товар, у него с баланса списываются деньги, '
                             'но при этом переведены продавцу они будут только когда покупатель с помощю интерфейса '
                             'бота подтвердит, что товар был успешно пердан. Таким образом при обмане ни одна сторона '
                             'не получит выгоды. Поэтому вы должны передать нам свой контакт, чтобы мы могли '
                             'отправить его купившему. Вы можете это сделать с помошью кнопки на клавиатуре.',
                             reply_markup=contactkb)
        await SellSG.next()
    else:
        await message.answer('Не удалось определить ввод, повоторите попытку, используя клавиатуру бота')
        return


@dp.message_handler(state=SellSG.DefContact, content_types=['contact'])
async def contact_def(message: Message, state=FSMContext):
    await state.update_data(contact_id=int(message.message_id))
    await message.answer('Теперь отправьте сообщение, который увидит человек после покупки. Это могут быть как '
                         'выражение благодарности, или просто какое-то обращение, так и сам товар. Сообшение может '
                         'быть любым. Учтите, что возможность добавить файл еще будет вам предоставлена в '
                         'отдельном пункте.', reply_markup=cancelkb)
    await SellSG.next()


@dp.message_handler(state=SellSG.InMessage, content_types=types.ContentType.ANY)
async def in_message(message: Message, state=FSMContext):
    await state.update_data(message_id=int(message.message_id))
    await message.answer('В случае, если ваш товар включает в себя файл, отправьте его. Иначе пропусктите пункт.',
                         reply_markup=skipkb)
    await SellSG.next()


@dp.message_handler(state=SellSG.InFile, content_types=['text'], text=['/skip', 'Пропустить ⏩'])
async def in_file_skip(message: Message, state=FSMContext):
    await state.update_data(file_id=0)
    await message.answer('Перейдем к финансовой части. Укажите цену товара. В силу соображений простоты и удобного '
                         'отображения, цена может быть от 2 ЛОЛкоинов и является целым числом.', reply_markup=cancelkb)
    await SellSG.next()


@dp.message_handler(state=SellSG.InFile, content_types=['document'])
async def in_file_def(message: types.Message, state=FSMContext):
    await state.update_data(file_id=message.message_id)
    await message.answer('Перейдем к финансовой части. Укажите цену товара. В силу соображений простоты и удобного '
                         'отображения, цена может быть от 2 ЛОЛкоинов и является целым числом.', reply_markup=cancelkb)
    await SellSG.next()


@dp.message_handler(lambda message: message.text.isdigit(), state=SellSG.Cost)
async def cost_def(message: types.Message, state=FSMContext):
    if int(message.text) > 5000:
        await message.answer('Это слишком много для цены одного товара, введите реальные значения.')
        return
    if int(message.text) >= 2:
        await state.update_data(cost=int(message.text))
    else:
        await message.answer('Цена должна быть от 2 ЛОЛкоинов')
        return
    await message.answer('Последний вопрос - скольким людям вы продадите товар? По умолчанию - неограниченое число '
                         'покупателей.', reply_markup=skipkb)
    await SellSG.next()


async def add_product(state, message):
    async with state.proxy() as data:
        cur.execute("""SELECT COUNT(*) FROM products_list""")
        if cur.fetchone()[0]:
            cur.execute("""SELECT id FROM products_list ORDER BY id DESC LIMIT 1""")
            product_id = cur.fetchone()[0] + 1
        else:
            product_id = 1
        cur.execute(f"""INSERT INTO products_list (id, product_name, description, seller, chat_id, message_id, file_id, 
        count, cost, is_special, contact_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
                    (product_id, data['name'], data['description'], data['seller'], data['chat_id'], data['message_id'],
                     data['file_id'], data['count'], data['cost'], data['is_special'],
                     data['contact_id'],))
        conn.commit()
        await message.answer('Готово! Можете проверить, появился ли ваш товар в общем списке 👍')
    await switch_to_base(message)


@dp.message_handler(lambda message: message.text.isdigit(), state=SellSG.Count)
async def count_def(message: types.Message, state=FSMContext):
    if int(message.text) > 150:
        await message.answer('У нас всего на платформе менее 150 человек, пожалуйста, введите реальные значения.')
        return
    if int(message.text) >= 1:
        await state.update_data(count=int(message.text))
    else:
        await message.answer('Количество должно быть больше нуля')
        return
    await add_product(state, message)


@dp.message_handler(state=SellSG.Count, content_types=['text'], text=['/skip', 'Пропустить ⏩'])
async def count_skip(message: types.Message, state=FSMContext):
    await state.update_data(count=0)
    await add_product(state, message)


@dp.message_handler(state=SellSG, content_types=types.ContentType.ANY)
async def sell_unknown(message: types.Message):
    await message.answer('Не удалось определить ввод, следуйте данным инструкциям.')


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['/status', 'Текущие сделки 💼'])
async def status_command(message: types.Message):
    cur.execute("""SELECT * FROM products_list WHERE seller = %s ORDER BY id""", (message.from_user.id,))
    answer_text = '<b>Ваши товары, выставленные на продажу:</b>\n'
    sell_products = ''
    while True:
        result = cur.fetchone()
        if not result:
            break
        sell_products += f"{result[0]}) <b>{result[1]}</b> - {result[9]} ЛОЛ\n"
    if not sell_products:
        sell_products = "У вас нет продаваемых товаров."
    await message.answer(answer_text + sell_products, parse_mode="HTML")
    cur.execute("""SELECT * FROM products_list WHERE buyer = %s ORDER BY id""", (message.from_user.id,))
    answer_text = '<b>Оплаченные товары:</b>\n'
    buy_products = ''
    while True:
        result = cur.fetchone()
        if not result:
            break
        buy_products += f"{result[0]}) <b>{result[1]}</b> - {result[9]} ЛОЛ\n"
    if not buy_products:
        buy_products = "У вас нет купленных SPECIAL товаров."
    await message.answer(answer_text + buy_products, parse_mode="HTML")
    await message.answer(
        'Напишите айди (число перед названием) интересующего вас товара, чтобы посмотреть подробную '
        'информацию о нём, илм изменить статус. Напишите "/back", чтобы вернуться в меню.', reply_markup=backkb)
    await SG.SelectStatus.set()


@dp.message_handler(lambda message: message.text.isdigit(), state=SG.SelectStatus)
async def status_select(message: types.Message, state: FSMContext):
    cur.execute(f"""SELECT * FROM products_list WHERE (seller = %s OR buyer = %s) AND id = %s""",
                (message.from_user.id, message.from_user.id, int(message.text)))
    result = cur.fetchone()
    await state.update_data(product_id=result[0])
    if not result:
        await message.answer("Некоректный айди, попробуйте ещё раз.")
        return
    if result[10]:
        service_type = "SPECIAL"
    else:
        service_type = "DEFAULT"
    if result[2]:
        service_description = result[2]
    else:
        service_description = 'Описание не прилагается.'
    if result[3] == message.from_user.id:
        if result[8]:
            service_status = "В процессе передачи товара покупателю."
        else:
            service_status = "Ожидает покупателя."
        await message.answer(md.text(
            md.hbold(result[1]), md.text(service_description), md.hcode('Тип товара —', service_type),
            md.text('Осталось:', result[7]), md.text('Статус:', service_status), sep='\n\n'
        ), parse_mode="HTML"
        )
        if result[8]:
            await message.answer(
                'Хотите ли вы отменить передачу товара покупателю? Если вы не хотите совершать это '
                'действие, отмените его, или просто напишите что-либо кроме "Подтвердить".',
                reply_markup=cancelkb)
            await SG.CancelStatus.set()
        else:
            await message.answer(
                'Хотите ли вы удалить товар? Если вы не хотите совершать это '
                'действие, отмените его, или просто напишите что-либо кроме "Подтвердить".',
                reply_markup=cancelkb)
            await SG.DeleteStatus.set()
    else:
        service_status = "В ожидании подтверждения успешного завершения передачи."
        await message.answer(md.text(
            md.hbold({result[1]}), md.text(service_description), md.hcode('Тип товара —', service_type),
            md.text('Статус:', service_status), sep='\n\n'
            ), parse_mode="HTML"
        )
        await message.answer('Хотите ли вы изменить статус на "Товар передан"? Делайте это только в том случае, если '
                             'получили товар, иначе мы не сможем гарантировать, что ваши деньги не удут в никуда. '
                             'Чтобы подвтердить действие, напишите "Подтвердить". Если вы не хотите совершать это '
                             'действие, отмените его, или просто напишите что-либо кроме "Подтвердить".',
                             reply_markup=cancelkb)
        await SG.FinishStatus.set()


@dp.message_handler(state=SG.DeleteStatus, content_types=['text'])
async def delete_product_command(message: types.Message, state: FSMContext):
    if message.text != 'Подтвердить':
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        async with state.proxy() as data:
            cur.execute("""DELETE FROM products_list WHERE id = %s""", (data["product_id"],))
            cur.execute("""UPDATE products_list SET id = id - 1 WHERE id > %s""", (data["product_id"],))
            conn.commit()
        await message.answer("Готово!")
        await switch_to_base(message)


@dp.message_handler(state=SG.FinishStatus, content_types=['text'])
async def finish_product_command(message: types.Message, state: FSMContext):
    if message.text != 'Подтвердить':
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        async with state.proxy() as data:
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (message.from_user.id,))
            user_result = cur.fetchone()
            cur.execute(f"""SELECT * FROM products_list WHERE id = %s""", (data['product_id'],))
            product_result = cur.fetchone()
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (product_result[3],))
            seller_result = cur.fetchone()
        cur.execute(
            """UPDATE users SET balance = %s WHERE id = %s""",
            (seller_result[0] + product_result[9] * 100, product_result[3],)
        )
        cur.execute("""UPDATE products_list SET buyer = 0""")
        await bot.send_message(product_result[3], f'Сделка продажи товара {product_result[1]} закрыта! Вам было '
                                                  f'переведено {product_result[9]} ЛОЛ на баланс.')
        if product_result[7] > 1:
            cur.execute("""UPDATE products_list SET count = %s WHERE id = %s""",
                        (product_result[7] - 1, product_result[0],))
        elif product_result[7] == 1:
            cur.execute("""DELETE FROM products_list WHERE id = %s""", (product_result[0],))
            cur.execute("""UPDATE products_list SET id = id - 1 WHERE id > %s""", (product_result[0],))
            await bot.send_message(product_result[3], 'Товар распродан!!')
        conn.commit()
        await message.answer("Готово!")
        await switch_to_base(message)


@dp.message_handler(state=SG.CancelStatus, content_types=['text'])
async def cancel_product_command(message: types.Message, state: FSMContext):
    if message.text != 'Подтвердить':
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        async with state.proxy() as data:
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (message.from_user.id,))
            user_result = cur.fetchone()
            cur.execute(f"""SELECT * FROM products_list WHERE id = %s""", (data['product_id'],))
            product_result = cur.fetchone()
            cur.execute(f"""SELECT balance FROM users WHERE id = %s""", (product_result[8],))
            buyer_result = cur.fetchone()
            cur.execute(
                """UPDATE users SET balance = %s WHERE id = %s""",
                (buyer_result[0] + product_result[9] * 100, product_result[8],)
            )
            await bot.send_message(product_result[8], f'Сделка по покупке товара {product_result[1]} была отменена, '
                                                      f'а средства возвращены.')
            cur.execute("""UPDATE products_list SET buyer = 0 WHERE id = %s""",
                        (product_result[0],))
            conn.commit()
            await message.answer('Готово!')
            await switch_to_base(message)


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['/withdraw', 'Вывести lolcoin 💳'])
async def withdraw_command(message: types.Message):
    cur.execute(f"""SELECT balance FROM users WHERE id = '{message.from_user.id}'""")
    user_balance = float(cur.fetchone()[0]) / 100
    await message.answer("Сколько ЛОЛ вы хотите вывести? Сумма вывода — целое положительное число. (У вас на балансе "
                         f"{user_balance} lolcoin)", reply_markup=cancelkb)
    await SG.WithdrawState.set()


@dp.message_handler(lambda message: message.text.isdigit(), state=SG.WithdrawState)
async def withdraw_transfer(message: types.Message):
    cur.execute(f"""SELECT balance, wallet_id FROM users WHERE id = '{message.from_user.id}'""")
    result = cur.fetchone()
    user_balance = float(result[0]) / 100
    user_wallet = str(result[1])
    if not int(message.text):
        await message.answer('Вы не можете вывести 0 ЛОЛкоинов!')
    elif int(message.text) <= user_balance:
        await message.answer("Переводим lolcoin вам на кошелёк. Это может занять немного времени. Пожалуйста, "
                             "подождите...")
        post = await send_lolcoin(user_wallet, int(message.text) * 100)
        print(post.text, user_wallet, int(message.text), sep='\n')
        cur.execute(
            f"""UPDATE users SET balance = %s WHERE id = %s""",
            (int(result[0]) - int(message.text) * 100, message.from_user.id)
        )
        conn.commit()
        await message.answer("Готово!")
        await switch_to_base(message)
    else:
        await message.answer('У вас недостаточно ЛОЛ на балансе!')


@dp.message_handler(state=SG.WithdrawState, content_types=types.ContentType.ANY)
async def withdraw_unknown(message: types.Message):
    await message.answer('Введите коректное значение, или отмените операцию')


# Help command sending list of commands
@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Команды ❔', '/help'])
async def help_command(message: Message):
    await help_message(message)


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['FAQ ❓', '/faq'])
async def faq_command(message: Message):
    await message.answer('*Вопрос:* Почему мы можем вам доверять?\n'
                         '*Ответ:* Наша платформа направлена на крайне малую в масштабах интернета аудиторию, '
                         'которая умещается в один телеграм-чат. Любой обман повлияет на нашу репутацию достаточко '
                         'сильно, чтобы та самая небольшая аудитория полностью потеряла доверия, что, по сути, '
                         'будет означать конец для платформы. Помимо того, мы не требуем никаких ваших данных, '
                         'вы решаете сколько нам доверить  а мы в свою очередь обещаем,  что все деньги на вашем '
                         'балансе останутся в вашем распоряжениии.\n\n'
                         '*Вопрос:* Что такое тип товара?\n'
                         '*Ответ:* Обычные (DEFAULT) товары это те, которые будут вам отправлены сразу после оплаты '
                         'одним, или несколькими сообщениями. \n'
                         'Особенные товары отличаются от обычных тем, что не могут быть переданы посредством '
                         'telegram. Когда кто-то решает купить такой товар, у него с баланса списываются деньги, '
                         'но при этом переведены продавцу они будут только когда покупатель с помощю интерфейса '
                         'бота подтвердит, что товар был успешно передан. Таким образом при обмане ни одна сторона '
                         'не получит выгоды. Поэтому вы должны передать нам свой контакт, чтобы мы могли '
                         'отправить его купившему. Вы можете это сделать с помошью кнопки на клавиатуре.\n\n'
                         '*Вопрос:* Политика конфиденциальности?\n'
                         '*Ответ:* После покупки покупатель увидит имя продавца, а продавец покупателя, так что '
                         'платформу считать анонимной нельзя. Однако никакой сторонний человек не сможет получить '
                         'доступ к платформе, так что всё, что на ней находится остается между участниками ЛОЛ-2022\n\n'
                         '*Вопрос:* Могут ли меня исключить из платформы?\n'
                         '*Ответ:* Да. Вы можете быть забанены за эксплуатирование возможных уязвимостей бота, '
                         'шуточные ордеры на продажу, товар, не соответствующий названию, или за любое неподобающее в '
                         'нашем понимание поведение.',
                         parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands="del", state=SG.BasicState)
async def delete_command_as(message: types.Message):
    if message.from_user.id != int(admin):
        await message.answer("Сообщение не было опознано.")
        return
    await message.answer("Введите айди удаляемого товара:")
    await AdminSG.DeleteServiceAS.set()


@dp.message_handler(lambda message: message.text.isdigit(), state=SG.SelectStatus)
async def delete_index_as(message: Message):
    if message.text == 0:
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        cur.execute("""DELETE FROM products_list WHERE id = %s""", (int(message.text),))
        cur.execute("""UPDATE products_list SET id = id - 1 WHERE id > %s""", (int(message.text),))
        conn.commit()
        await message.answer("Готово!")
        await switch_to_base(message)


@dp.message_handler(state='*', content_types=types.ContentType.ANY)
async def unknown_command(message: Message):
    await message.answer("Сообщение не было опознано.")


# Checking for new transfer every "wait_for" seconds
async def check(wait_for):
    print("Debug: check is awaited")
    while True:
        print("Debug: inside while")
        await asyncio.sleep(wait_for)
        print("after sleep")
        transactions = await parsing()
        if transactions:
            for transaction in transactions:
                logging.warning(transaction["amount"])
                cur.execute(f"""SELECT * FROM users WHERE wallet_id = %s""", (transaction["sender"],))
                result = cur.fetchone()
                if result and transaction["amount"] >= 200:
                    result = [result[0], result[4]]
                    cur.execute(
                        f"""UPDATE users SET balance = %s WHERE id = %s""",
                        (result[1] + transaction["amount"] - 100, result[0],)
                    )
                    await bot.send_message(result[0], f"✅ Вы перевели на платформу {transaction['amount'] / 100}"
                                                      f" lolcoin, из которых {transaction['amount'] / 100 - 1} были"
                                                      " зачислены на баланс, а оставшийся 1 ЛОЛкоин взят в качестве"
                                                      " комиссии.")
            conn.commit()


# Bot start
if __name__ == '__main__':
    future = asyncio.ensure_future(check(60))
    executor.start_polling(dp, skip_updates=True)

import os
import logging
from textwrap import dedent

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import ChatNotFound
from dotenv import load_dotenv

from api_tools import (
    get_weather, convert_currency, currencies, get_random_pet_url
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
bot = Bot(token=os.getenv('TG_BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class UserState(StatesGroup):
    start = State()
    location = State()
    base_currency = State()
    target_currency = State()
    currency_amount = State()
    poll_chat_id = State()
    poll_question = State()
    poll_answer = State()
    poll_options = State()


def get_currency_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(text=name, callback_data=code)
        for code, name in currencies.items()
    ]
    keyboard.add(*buttons)
    return keyboard


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    user_name = message.from_user.first_name
    if user_name:
        reply_text = f'Привет, {user_name}!'
    else:
        reply_text = 'Привет!'
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(text='Погода', callback_data='weather')
    )
    keyboard.add(
        types.InlineKeyboardButton(
            text='Конвертор валют', callback_data='currency'
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text='Котики', callback_data='pet')
    )
    keyboard.add(
        types.InlineKeyboardButton(text='Создать опрос', callback_data='poll')
    )
    await message.answer(reply_text, reply_markup=keyboard)
    await UserState.start.set()


@dp.message_handler(content_types=['text'], state=UserState.start)
async def return_to_start(message: types.Message):
    await process_start_command(message)


@dp.callback_query_handler(lambda callback_query: True, state=UserState.start)
async def handle_main_menu(callback_query: types.CallbackQuery):
    user_reply = callback_query.data
    chat_id = callback_query.message.chat.id
    if user_reply == 'weather':
        keyboard = types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True
        )
        buttons = [
            types.KeyboardButton(
                text="Отправить геолокацию", request_location=True
            ),
            types.KeyboardButton('Отмена'),
        ]
        keyboard.add(*buttons)
        await callback_query.message.answer(
            'Пришлите вашу геолокацию',
            reply_markup=keyboard,
        )
        await UserState.location.set()

    elif user_reply == 'currency':
        await callback_query.message.answer(
            'Выберите базовую валюту',
            reply_markup=get_currency_keyboard(),
        )
        await UserState.base_currency.set()

    elif user_reply == 'pet':
        pet_url = await get_random_pet_url()
        await callback_query.message.answer_photo(photo=pet_url)

    elif user_reply == 'poll':
        reply_text = dedent(
            """
            Введите id чата, в который нужно добавить опрос.
            Учтите, что бот должен быть предварительно добавлен в указанный чат!
            Чтобы узнать id группового чата, добавьте в него бот @RawDataBot и найдите
            "chat": {
                "id": ...
            в присланном сообщении. 
            Не забудьте удалить бота @RawDataBot после получения id!
            """
        )
        await callback_query.message.answer(reply_text)
        await UserState.poll_chat_id.set()

    await bot.delete_message(chat_id, callback_query.message.message_id)


@dp.message_handler(
    content_types=['text', 'location'], state=UserState.location
)
async def process_location(message: types.Message):
    if message.text == 'Отмена':
        await UserState.start.set()
        await process_start_command(message)
    elif message.location:
        weather = await get_weather(
            message.location.latitude,
            message.location.longitude,
            os.getenv('OPENWEATHERMAP_API_KEY')
        )
        await message.answer(weather, reply_markup=types.ReplyKeyboardRemove())
    else:
        return
    await UserState.start.set()


@dp.callback_query_handler(
    lambda callback_query: True,
    state=UserState.base_currency
)
async def process_base_currency(
        callback_query: types.CallbackQuery, state: FSMContext
):
    chat_id = callback_query.message.chat.id
    await state.update_data(base_currency=callback_query.data)
    await callback_query.message.answer(
        'Выберите целевую валюту',
        reply_markup=get_currency_keyboard(),
    )
    await UserState.target_currency.set()
    await bot.delete_message(chat_id, callback_query.message.message_id)


@dp.callback_query_handler(
    lambda callback_query: True,
    state=UserState.target_currency
)
async def process_target_currency(
        callback_query: types.CallbackQuery, state: FSMContext
):
    chat_id = callback_query.message.chat.id
    await state.update_data(target_currency=callback_query.data)
    await callback_query.message.answer('Введите сумму в базовой валюте')
    await UserState.currency_amount.set()
    await bot.delete_message(chat_id, callback_query.message.message_id)


@dp.message_handler(content_types=['text'], state=UserState.currency_amount)
async def process_currency_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        user_data = await state.get_data()
        conversion_result = await convert_currency(
            user_data['base_currency'],
            user_data['target_currency'],
            amount,
            os.getenv('EXCANGERATES_API_KEY')
        )
        await message.answer(conversion_result)
        await UserState.start.set()
    except ValueError:
        await message.answer(
            'Некорректный ввод! Введите сумму в базовой валюте',
        )


@dp.message_handler(content_types=['text'], state=UserState.poll_chat_id)
async def process_poll_chat_id(message: types.Message, state: FSMContext):
    await state.update_data(poll_chat_id=message.text)
    await message.answer('Введите вопрос')
    await UserState.poll_question.set()


@dp.message_handler(content_types=['text'], state=UserState.poll_question)
async def process_poll_question(message: types.Message, state: FSMContext):
    await state.update_data(poll_question=message.text)
    await state.update_data(poll_is_anonymous=True)
    await state.update_data(poll_allows_multiple_answers=False)
    await state.update_data(poll_answers=[])
    await message.answer('Введите вариант ответа')
    await UserState.poll_answer.set()


@dp.message_handler(content_types=['text'], state=UserState.poll_answer)
async def process_poll_answers(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    if message.text == 'Перейти к опциям':
        await UserState.poll_options.set()
        await show_poll_options_menu(chat_id, state)
        return
    user_data = await state.get_data()
    poll_answers = user_data['poll_answers']
    poll_answers.append(message.text)
    await state.update_data(poll_answers=poll_answers)
    if len(poll_answers) >= 10:
        await UserState.poll_options.set()
        await show_poll_options_menu(chat_id, state)
        return
    if len(poll_answers) > 1:
        keyboard = types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True
        )
        keyboard.add(types.KeyboardButton('Перейти к опциям'))
        await message.answer(
            'Добавьте вариант ответа или нажмите Перейти к опциям',
            reply_markup=keyboard,
        )
    else:
        await message.answer('Добавьте вариант ответа')


async def show_poll_options_menu(chat_id, state: FSMContext):
    user_data = await state.get_data()
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton(
            text=f"{'[X]' if user_data['poll_is_anonymous'] else '[ ]'} Анонимное голосование",
            callback_data='poll_is_anonymous'
        ),
        types.InlineKeyboardButton(
            text=f"{'[X]' if user_data['poll_allows_multiple_answers'] else '[ ]'} Выбор нескольких ответов",
            callback_data='poll_allows_multiple_answers'
        ),
        types.InlineKeyboardButton(
            text='Создать опрос',
            callback_data='create_poll'
        ),
    ]
    keyboard.add(*buttons)
    await bot.send_message(
        chat_id,
        'Измените опции или завершите создание опроса',
        reply_markup=keyboard,
    )


@dp.callback_query_handler(
    lambda callback_query: True,
    state=UserState.poll_options,
)
async def process_poll_options(
        callback_query: types.CallbackQuery, state: FSMContext
):
    chat_id = callback_query.message.chat.id
    user_reply = callback_query.data
    user_data = await state.get_data()
    if user_reply == 'poll_is_anonymous':
        await state.update_data(
            poll_is_anonymous=not user_data['poll_is_anonymous']
        )
        await show_poll_options_menu(chat_id, state)
    elif user_reply == 'poll_allows_multiple_answers':
        await state.update_data(
            poll_allows_multiple_answers=not user_data[
                'poll_allows_multiple_answers'
            ]
        )
        await show_poll_options_menu(chat_id, state)
    elif user_reply == 'create_poll':
        try:
            await bot.send_poll(
                chat_id=user_data['poll_chat_id'],
                question=user_data['poll_question'],
                options=user_data['poll_answers'],
                is_anonymous=user_data['poll_is_anonymous'],
                allows_multiple_answers=user_data[
                    'poll_allows_multiple_answers'
                ],
            )
            await callback_query.message.answer('Опрос создан успешно')
            await UserState.start.set()
        except ChatNotFound:
            await callback_query.message.answer('Ошибка. Чат не существует, или бот в него не добавлен.')
            await UserState.start.set()

    await bot.delete_message(chat_id, callback_query.message.message_id)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

import telebot
from telebot import types
import sqlite3
import re
import os
import traceback
import argparse

from speechkit import model_repository, configure_credentials, creds
from speechkit.stt import AudioProcessingType


parser = argparse.ArgumentParser(
                    prog='TODObot',
                    description='Starts backend for telegram TODObot')
parser.add_argument('-tt', '--telegram_token')
parser.add_argument('-yk', '--yandex_speechkit_api_key')

args = parser.parse_args()
print(args)

bot = telebot.TeleBot(args.telegram_token)

configure_credentials(
   yandex_credentials=creds.YandexCredentials(
      api_key=args.yandex_speechkit_api_key
   )
)

db_name = 'task_bot.db'

add_task_msg = 'Добавить задачу'
get_tasks_msg = 'Мои задачи'
get_stat_msg = 'Статистика'

status_new = 'new'
status_in_progress = 'in_progress'
status_done = 'done'

status_dict = {
    status_new: 'Новая задача',
    status_in_progress: 'Задача в работе',
    status_done: 'Задача сделана',
}

to_work = 'to_work'
done = 'done'

def format_task_count(count):
    if count==0 or count > 4:
        return str(count) + ' задач'
    elif count == 1:
        return str(count) + ' задачa'
    else:
        return str(count) + ' задачи'

def recognize(audio):
   model = model_repository.recognition_model()

   # Задайте настройки распознавания.
   model.model = 'general'
   model.language = 'ru-RU'
   model.audio_processing_type = AudioProcessingType.Full

   # Распознавание речи в указанном аудиофайле и вывод результатов в консоль.
   result = model.transcribe_file(audio)
   data = ''
   for c, res in enumerate(result):
      data += res.raw_text
   print(data)
   return data

def format_task(task, print_id=True):
    data = '-'
    if print_id:
        data += ' /' + str(task[1])
    status = status_dict[task[3]]
    data += ' ' + task[2] + ' [' + status + ']'
    return data


def get_stat(user_id):
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    cursor.execute("""
    SELECT
        status,
        count(*)
    FROM tasks WHERE
        user_id=?
    GROUP BY status
    ORDER BY status
    """, (user_id,))
    stat = cursor.fetchall()
    connection.close()
    return stat


def add_task(user_id, task):
    if task == None or task == '':
        return 'Не могу добавить пустую задачу'
    res = 'Записал'
    with sqlite3.connect(db_name) as connection:
        cursor = connection.cursor()

        try:
            with connection:
                cursor.execute("""
                SELECT
                    *
                FROM tasks WHERE
                    user_id=?
                """, (user_id,))

                tasks = cursor.fetchall()
                count = len(tasks)
                print(count)

                cursor.execute("""
                INSERT INTO tasks
                (user_id, task_id, task)
                VALUES (?, ?, ?)
                """, (user_id, count+1, task))
        except Exception:
            print("AAAA")
            print(Exception)
            traceback.print_exc()
            res = 'Случилась ошибка, попробуй еще раз'
    connection.close()
    return res

def get_tasks(user_id):
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    cursor.execute("""
    SELECT
        *
    FROM tasks WHERE
        user_id=?
        AND status != 'done'
    ORDER BY STATUS
    """, (user_id,))
    tasks = cursor.fetchall()
    connection.close()
    return tasks

def get_task(user_id, task_id):
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    cursor.execute("""
    SELECT
        *
    FROM tasks WHERE
        user_id=?
        AND task_id=?
    ORDER BY STATUS
    """, (user_id, task_id))
    tasks = cursor.fetchone()
    connection.close()
    return tasks

def get_default_keyboard():
    markup=types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton(add_task_msg)
    btn2 = types.KeyboardButton(get_tasks_msg)
    btn3 = types.KeyboardButton(get_stat_msg)
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['start'])
def start_message(message):
    print(message)
    output = 'Привет, {0.first_name}! Я твой TODO-бот. Я помогу тебе сохранять списки твоих дел и задач. Чтобы начать, используй кнопки меню, и да пребудет с тобой сила переделать все дела.'
    bot.send_message(message.chat.id, text=output.format(message.from_user), reply_markup=get_default_keyboard())


def get_data_from_audio_messages(message):
    print(message)
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    filename = 'user_voice' + str(message.message_id) + '.mp3'
    with open(filename, 'wb') as new_file:
        new_file.write(downloaded_file)
    res = recognize(filename)
    os.remove(filename)
    return res

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    print(message)
    if message.text == add_task_msg:
        bot.send_message(message.from_user.id, "Опиши задачу. Я понимаю текст и голосовые.", reply_markup=get_default_keyboard())
        bot.register_next_step_handler(message, add_task_from_msg)
    elif message.text == get_tasks_msg:
        tasks = get_tasks(message.from_user.id)
        print(tasks)
        if tasks == []:
           bot.send_message(message.from_user.id, "У тебя пока нет нерешенных задач, счастливчик!", reply_markup=get_default_keyboard())
        else:
            data = ''
            for task in tasks:
               data += format_task(task) + '\n'
            bot.send_message(message.from_user.id, data, reply_markup=get_default_keyboard())
    elif message.text == get_stat_msg:
        count = 0
        data = ''
        stats = get_stat(message.from_user.id)
        for stat in stats:
            count += stat[1]
            status = status_dict[stat[0]]
            data += 'В статусе [' + status + '] у тебя ' + format_task_count(stat[1]) + '\n'
        data = 'Всего задач ' + str(count) + '.\n' + data
        bot.send_message(message.from_user.id, data, reply_markup=get_default_keyboard())
    elif re.fullmatch('/\d+', message.text):
        task_id = int(message.text[1:])
        task = get_task(user_id=message.from_user.id, task_id=task_id)
        print(task)
        if task != None:
            status = status_dict[task[3]]
            if task[3] == status_done:
                msg = 'Ура, ты уже сделал задачу ' + str(task[1]) + '!\n' + format_task(task, False)
                bot.send_message(message.from_user.id, text=msg, reply_markup=get_default_keyboard())
            else:
                msg = 'Что хочешь сделать с задачей ' + str(task[1]) +'?\n' + format_task(task, False)
                keyboard = types.InlineKeyboardMarkup()
                key_to_work = types.InlineKeyboardButton(text='В работу!', callback_data=to_work)
                key_done= types.InlineKeyboardButton(text='Сделал!', callback_data=done)
                keyboard.add(key_to_work, key_done)
                bot.send_message(message.from_user.id, text=msg, reply_markup=keyboard)
        else:
            bot.send_message(message.from_user.id, 'Не нашел такой задачи', reply_markup=get_default_keyboard())
    else:
        bot.send_message(message.from_user.id, 'Не знаю такую команду :( Воспользуйся меню', reply_markup=get_default_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    result = re.search(r'\d+', call.message.text)
    task_id = int(result.group(0))
    if call.data == to_work:
        set_status(call.from_user.id, task_id, 'in_progress')
    elif call.data == done:
        set_status(call.from_user.id, task_id, 'done')
    bot.send_message(call.from_user.id, 'Обновил статус!', reply_markup=get_default_keyboard())

def add_task_from_msg(message):
    user_id = message.from_user.id
    if message.content_type == 'text':
        data = add_task(user_id, message.text)
        bot.send_message(message.from_user.id, data, reply_markup=get_default_keyboard())
    elif message.content_type in {'voice', 'audio'}:
        task = get_data_from_audio_messages(message)
        bot.send_message(message.from_user.id, 'Распознал задачу: "' + task + '"', reply_markup=get_default_keyboard())
        data = add_task(user_id, task)
        bot.send_message(message.from_user.id, data, reply_markup=get_default_keyboard())
    else:
        bot.send_message(message.from_user.id, 'Не понимаю тебя. Повтори попытку заново и пришли описание задачи текстом или голосовым.', reply_markup=get_default_keyboard())


def set_status(user_id, task_id, status):
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE tasks
    SET status=?
    WHERE user_id=? AND task_id=?
    """, (status, user_id, task_id))
    connection.commit()
    connection.close()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        user_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        task TEXT NOT NULL,
        status TEXT CHECK( status IN ('new','in_progress','done') )   NOT NULL DEFAULT 'new',
    PRIMARY KEY (user_id, task_id)
    )
    """)
    connection.commit()
    connection.close()

    bot.polling(none_stop=True, interval=0)

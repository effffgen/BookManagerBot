# -*- coding: utf-8 -*-
from distutils.command.config import config

import config
import state
import telebot
import cf_deployment_tracker
from config import book_db
from config import user_state_db
from cloudant.view import View
from cloudant.design_document import DesignDocument
cf_deployment_tracker.track()

bot = telebot.TeleBot(config.token)
desdoc = DesignDocument(database=book_db,document_id='getByOwner')


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_state = user_state_db.get(str(message.from_user.id))
    if user_state is None:
        print("we' re here")
        user_data = {
            '_id': str(message.from_user.id),
            'firstname': message.from_user.first_name,
            'state': config.STATE_START,
            'editing_book': 'none'
        }
        user_state = user_state_db.create_document(user_data)
    else:
        user_state['editing_book'] = 'none'
    bot.send_message(chat_id=message.chat.id, text='Hello, how can I help you, ' + user_state['firstname']+'?')
    user_state['state'] = state.STATE_START
    user_state.save()


@bot.message_handler(commands=['add'])
def handle_adding(message):
    user_state = user_state_db.get(str(message.from_user.id))
    user_state['state'] = state.STATE_ADDING
    user_state.save()
    bot.send_message(chat_id=message.chat.id, text='I am ready to get your book, just upload or forward it here!')


@bot.message_handler(commands=['show'])
def show_book(message):
    text = message.text.split(' ')
    if len(text)>1:
        pass
    else:
        view = View(ddoc=desdoc,view_name='get-book-by-owner')
        with view.custom_result(key=message.from_user.id) as result:
            for row in result:
                book_data = get_book_info_message(row['id'])
                #Do I really have to query a database that much?
                bot.send_message(chat_id=message.chat.id, text=book_data)
                #Huyak inline keys


@bot.message_handler(content_types=['text'])
def answer_text(message):
    book_id = user_state_db.get(str(message.from_user.id))['']
    book = book_db.get(book_id)
    user_state = user_state_db.get(str(message.from_user.id))
    if user_state['state'] == state.STATE_TITLE:
        if message.text == 'skip':
            message.text = state.STATE_COMPLETE
            return
            #What to do next?
        elif message.text == 'no':
            pass
    #bot.send_message(chat_id=message.chat.id, text='Sorry, but at the moment I can not answer to your text.')
    #bot.send_message(chat_id=message.chat.id, text='Please, try again later')


"""
Handles file recieving
We assume that the file is always a book, maybe we need to perform a check
TODO: consider the fact that we can get another type of file, e. g. an exe file
TODO: read about the Telegram file_id property to store only unique books
TODO: book can have multiple owners, handle this
Maybe I forgot something else
TODO: write down the book adding sequence
"""


@bot.message_handler(content_types=['document'])
def handle_file(message):
    book_info = book_db.get(message.document.file_id)
    if book_info is None:
        #Add this book
        book_data = {
            '_id': message.document.file_id,
            'owners': [message.from_user.id],
            'title': None,
            'tags': [],
            'cover': None,
            'description': None
        }
        book_info = book_db.create_document(book_data)
    elif message.from_user.id not in book_info['owners']:
        book_info['owners'].append(message.from_user.id)
        #The book properties might be already set, what to do? TODO: todo todo todo todo todododoooooo
        book_info.save()
    else:
        bot.send_message(chat_id=message.chat.id, text="Welp, you have already added that book, don't try to fool me!")
        return
    #Consider using inline buttons
    bot.send_message(chat_id=message.chat.id,
                     text="Now you need to enter title of the book"
                          " (or just write 'no', we'll take the file name as title.)")
    bot.send_message(chat_id=message.chat.id,
                     text="If you want to skip all next steps, write 'skip'.")
    user_state=user_state_db.get(str(message.from_user.id))['state'] = state.STATE_TITLE
    user_state.save()


def get_book_info_message(id):
    book_info = book_db.get(id)
    if book_info is None:
        raise Exception('There is no book with id ' + id)
    message = 'id: ' + book_info['_id'] +'\n'
    if book_info['title'] is not None:
        message += 'name: ' + book_info['title'] + '\n'
    return message


if __name__ == '__main__':
    bot.polling(none_stop=True)




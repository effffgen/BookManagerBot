# -*- coding: utf-8 -*-
import config
import telebot
import cf_deployment_tracker
import telebot.types
from config import book_db
from config import user_state_db
from cloudant.view import View
from cloudant.design_document import DesignDocument
from state import State

cf_deployment_tracker.track()

bot = telebot.TeleBot(config.token)

design_document = DesignDocument(database=book_db, document_id='getByOwner')


@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    Handles the 'start' command
    Serves as initializer and as the ending point after working with book
    """
    user_state = user_state_db.get(str(message.from_user.id))
    if user_state is None:
        user_data = {
            '_id': str(message.from_user.id),
            'firstname': message.from_user.first_name,
            'state': State.STATE_START,
            'editing_book': 'none'
        }
        user_state = user_state_db.create_document(user_data)
        bot.send_message(chat_id=message.chat.id, text='Hello!')
    user_state['state'] = State.STATE_START
    user_state.save()
    process_state(message.chat.id, message.from_user.id)


@bot.message_handler(commands=['add'])
def handle_adding(message):
    user_state = user_state_db.get(str(message.from_user.id))
    user_state['state'] = State.STATE_ADDING
    user_state.save()
    bot.send_message(chat_id=message.chat.id, text='I am ready to get your book, just upload or forward it here!')


@bot.message_handler(commands=['show'])
def show_book(message):
    """
    Handles 'show' command.
    If no arguments passed, shows details about all books.
    If one argument passed (book's id), show this book info.
    Command is for development purposes and is to be replaced by suggestions.
    TODO: add necessary suggestion functions
    """
    text = message.text.split(' ')
    if len(text) > 1:
        book_data = get_book_info_message(text[1])
        keyboard = get_book_info_keyboard(text[1], str(message.from_user.id))
        bot.send_message(chat_id=message.chat.id, text=book_data, reply_markup=keyboard)
    else:
        view = View(ddoc=design_document, view_name='get-book-by-owner')
        from_user = str(message.from_user.id)
        with view.custom_result(key=from_user) as result:
            empty = True
            for row in result:
                print('got book ' + str(row))
                book_data = get_book_info_message(row['id'])
                # Do I really have to query a database that much?
                keyboard = get_book_info_keyboard(row['id'], from_user)
                bot.send_message(chat_id=message.chat.id, text=book_data, reply_markup=keyboard)
                empty = False
            if empty:
                bot.send_message(message.chat.id, "Your book list is empty. Add something!")


@bot.message_handler(content_types=['document'])
def handle_file(message):
    """
    Handles file recieving
    We assume that the file is always a book, maybe we need to perform a check
    TODO: MIME-types!
    TODO: what if there would be several same books with different types (pdf, djvu)?
    Maybe I forgot something else
    TODO: write down the book adding sequence
    """
    book_info = book_db.get(message.document.file_id)
    if book_info is None:
        # Add this book
        book_data = {
            '_id': message.document.file_id,
            'owners': [str(message.from_user.id)],
            'title': message.document.file_name,
            'tags': [],
            'cover': None,
            'description': None,
            'authors': []
        }
        book_db.create_document(book_data)
        book_info = book_data
    elif message.from_user.id not in book_info['owners']:
        book_info['owners'].append(message.from_user.id)
        # The book properties might be already set, what to do? TODO: todo todo todo todo todododoooooo
        book_info.save()
    else:
        bot.send_message(chat_id=message.chat.id, text="Welp, you have already added that book, don't try to fool me!")
        return
    # Consider using inline buttons
    user = user_state_db.get(str(message.from_user.id))
    user['state'] = State.STATE_TITLE
    user['editing_book'] = book_info['_id']
    user.save()
    process_state(message.chat.id, user['_id'])


@bot.message_handler(content_types=['text'])
def answer_text(message):
    """
    Handles all text messages from user, that are not subject to the handlers above.
    That include: title, description and tags of the book, texts of the keyboard buttons
    TODO: find what else
    TODO: authors
    """
    user_state = user_state_db.get(str(message.from_user.id))
    book_id = user_state['editing_book']
    book = book_db.get(book_id)
    if user_state['state'] not in (State.STATE_START, State.STATE_ADDING, State.STATE_COMPLETE) and not handle_skip(user_state, message):
        if user_state['state'] == State.STATE_TITLE:
            book['title'] = message.text
            user_state['state'] = user_state['state'] + 1
        elif user_state['state'] == State.STATE_DESCRIPTION:
            book['description'] = message.text
            user_state['state'] = user_state['state'] + 1
        elif user_state['state'] == State.STATE_AUTHORS:
            book['authors'] = message.text.split(',')
            user_state['state'] = user_state['state'] + 1
        elif user_state['state'] == State.STATE_TAGS:
            book['tags'] = message.text.split(',')
            user_state['state'] = user_state['state'] + 1
        user_state.save()
        book.save()
    process_state(message.chat.id, message.from_user.id)


def get_book_info_message(book_id):
    """
    Gets all data about the book with given id from the database and returns it in the human-readable form
    :param book_id: Id of the book
    :return: text of the detailed description
    TODO: markdown!
    """
    book_info = book_db.get(book_id)
    if book_info is None:
        raise Exception('There is no book with id ' + book_id)
    message = 'id: ' + book_info['_id'] + '\n'
    if book_info['title'] is not None:
        message += 'name: ' + book_info['title'] + '\n'
    return message


@bot.callback_query_handler(func=lambda call: True)
def get_callback(call):
    """
    Handler for all callback buttons
    Every callback button has its own command and id, so that we know what to change
    TODO: confirmation for deletion?
    TODO: change one particular parameter?
    """

    if call.message:
        command, book_id, user_from = call.data.split(' ')
        print(call.data)
        if command == 'download':
            bot.send_document(chat_id=call.message.chat.id, data=book_id)
        if command == 'delete':
            delete_book(user_from, book_id)
            bot.send_message(chat_id=call.message.chat.id, text='Done!')
        if command == 'change':
            pass


def delete_book(from_user, book_id):
    """
    Deletes book from the database.
    I LIED.
    In fact, it removes this user from the list of owners, so that other users won't need to write so much when
    adding new book
    :param from_user: User who requested deletion
    :param book_id: Book that is to be delete
    """
    book = book_db[book_id]
    if book is None:
        raise Exception('There is no such book')
    book['owners'].remove(from_user)
    book.save()


def process_state(chat_id, user_id):
    """
    Sends appropriate prompt message to the user depending on current input state.
    :param chat_id: id of chat where we need to send message
    :param user_id: id of user
    """

    user_data = user_state_db.get(str(user_id))
    print(user_data)
    if user_data['state'] == State.STATE_TITLE:
        keyboard = get_skip_keyboard()
        bot.send_message(chat_id=chat_id,
                         text="Ok, now you can set title of the book."
                              " If you press 'skip', title would be set to the file name.\n "
                              "You can also skip all next steps by pressing the corresponding button.",
                         reply_markup=keyboard)
    elif user_data['state'] == State.STATE_START:
        bot.send_message(chat_id=chat_id, text='How can I help you, ' + user_data['firstname'] + '?')
    elif user_data['state'] == State.STATE_DESCRIPTION:
        keyboard = get_skip_keyboard()
        bot.send_message(chat_id=chat_id,
                         text="Now enter the book's description",  reply_markup=keyboard)


def handle_skip(user_data, message):
    """
    Checks whether this step was skipped or not.
    If skipped, appropriate changes in user's state are necessary.
    :return if the step has been skipped
    """
    print(message)
    if message.text == 'Skip':
        user_data['state'] = user_data['state'] + 1
        user_data.save()
        return True
    if message.text == 'Skip all steps':
        print('Kek')
        user_data['state'] = State.STATE_START
        user_data['editing_book'] = None
        user_data.save()
        return True
    return False


def get_book_info_keyboard(book_id, from_user):
    keyboard = telebot.types.InlineKeyboardMarkup()
    download_button = telebot.types.InlineKeyboardButton(
        text='Download book', callback_data='download ' + book_id + ' ' + from_user)
    change_button = telebot.types.InlineKeyboardButton(
        text='Change book info', callback_data='edit ' + book_id + ' ' + from_user)
    delete_button = telebot.types.InlineKeyboardButton(
        text='Delete book', callback_data='delete ' + book_id + ' ' + from_user)
    # Inline keys has been huyak'd
    keyboard.add(download_button, change_button, delete_button)
    return keyboard


def get_skip_keyboard():
    skip_button = telebot.types.KeyboardButton('Skip')
    skip_all_button = telebot.types.KeyboardButton('Skip all steps')
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(skip_button, skip_all_button)
    return keyboard


if __name__ == '__main__':
    bot.polling(none_stop=True)

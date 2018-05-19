# -*- coding: utf-8 -*-
import config
import cf_deployment_tracker
import telebot.types
import gettext
import random
from config import book_db
from config import user_state_db
from cloudant.view import View
from cloudant.design_document import DesignDocument
from cloudant.query import Query
from state import State
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, \
    ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
cf_deployment_tracker.track()

bot = telebot.TeleBot(config.token)

dd_owner = DesignDocument(database=book_db, document_id='getByOwner')
dd_tag = DesignDocument(database=book_db, document_id='getByTag')
dd_lang = DesignDocument(database=book_db, document_id='getByLang')

random.seed()


def get_by_tag(tag, user_id):
    return Query(database=book_db, selector={"_id": {"$gt": None},
                                             'tags': {'$elemMatch': {'$eq': tag}},
                                             'owners': {'$elemMatch': {'$eq': user_id}}})


translations = {
    'ru': gettext.translation('base', 'locales', ['ru']),
    'en': gettext.translation('base', 'locales', ['en'])
}


def _(text, lang):
    return translations[lang].gettext(text)


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
            'single_state': False,
            'editing_book': None,
            'lang': 'en'
        }
        user_state = user_state_db.create_document(user_data)
        user_state['state'] = State.STATE_USERLANG
    else:
        user_state['state'] = State.STATE_START
    user_state.save()
    send_state_prompt(message.chat.id, message.from_user.id)


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """
    Handles photo upload.
    Photo can be uploaded only as a cover, all photos uploaded during other stages should be discarded
    :param message:
    :return:
    """
    user_state = user_state_db.get(str(message.from_user.id))
    if user_state['state'] == State.STATE_COVER:
        book = book_db.get(user_state['editing_book'])
        book['cover'] = message.photo[0].file_id
        book.save()
        user_state['state'] = change_status(user_state['state'], user_state['single_state'])
        user_state.save()
        send_state_prompt(message.chat.id, message.from_user.id)


@bot.message_handler(content_types=['document'])
def handle_file(message):
    """
    Handles file recieving
    We assume that the file is always a book, maybe we need to perform a check
    TODO: MIME-types!
    TODO: what if there would be several same books with different types (pdf, djvu)?
    Maybe I forgot something else
    """
    from_user = str(message.from_user.id)
    user = user_state_db.get(from_user)
    book_info = book_db.get(message.document.file_id)
    if book_info is None:
        # Add this book
        book_data = {
            '_id': message.document.file_id,
            'owners': [from_user],
            'title': message.document.file_name,
            'tags': [],
            'cover': None,
            'description': None,
            'authors': [],
            'lang': 'ru',
            'genre': None
        }
        book_db.create_document(book_data)
        book_info = book_data
    elif from_user not in book_info['owners']:
        book_info['owners'].append(from_user)
        # The book properties might be already set, what to do? TODO: todo todo todo todo todododoooooo
        bot.send_message(chat_id=message.chat.id, text=_("Ok, I already know something about this book, but you can"
                                                         " change information if you want.", user['lang']))
        book_info.save()
        user['state'] = State.STATE_START
        user['editing_book'] = None
        user['single_state'] = False
        user.save()
        return
    else:
        bot.send_message(chat_id=message.chat.id,
                         text=_("Welp, you have already added that book, don't try to fool me!", user['lang']))
        return
    user['state'] = State.STATE_TITLE
    user['editing_book'] = book_info['_id']
    user['single_state'] = False
    user.save()
    send_state_prompt(message.chat.id, user['_id'])


@bot.message_handler(content_types=['text'])
def answer_text(message):
    """
    Handles all text messages from user, that are not subject to the handlers above.
    That include: title, description and tags of the book, texts of the keyboard buttons
    TODO: decopmose this method
    """
    user_state = user_state_db.get(str(message.from_user.id))
    book_id = user_state['editing_book']
    book = book_db.get(book_id)

    if user_state['state'] not in (State.STATE_START, State.STATE_COMPLETE, State.STATE_FIND, State.STATE_USERLANG) \
            and not (is_skip(user_state, message) or is_skipall(user_state, message)):
        if user_state['state'] == State.STATE_TITLE:
            book['title'] = message.text
        elif user_state['state'] == State.STATE_DESCRIPTION:
            book['description'] = message.text
        elif user_state['state'] == State.STATE_AUTHORS:
            book['authors'] = message.text.split(', ')
        elif user_state['state'] == State.STATE_TAGS:
            book['tags'] = message.text.split(', ')
        elif user_state['state'] == State.STATE_LANG:
            book['lang'] = message.text.lower()

        user_state['state'] = change_status(user_state['state'], user_state['single_state'])
        user_state.save()
        if book is not None:
            print(book)
            book.save()
    elif user_state['state'] == State.STATE_USERLANG:
        lang = message.text.lower()
        if lang in ('ru', 'en'):
            user_state['lang'] = message.text.lower()
        else:
            user_state['lang'] = 'en'
        user_state['state'] = State.STATE_START
        user_state.save()
    elif user_state['state'] == State.STATE_START:
        if message.text == _('Add new book', user_state['lang']):
            bot.send_message(chat_id=message.chat.id, text=_('Just forward book here!', user_state['lang']))
        elif message.text == _('Find book', user_state['lang']):
            user_state['state'] = State.STATE_FIND
            user_state.save()
            send_state_prompt(message.chat.id, message.from_user.id)
        elif message.text == _("I'm feeling lucky!", user_state['lang']):
            get_random_book(user_state, message.chat.id)
        elif message.text == _('Show all books', user_state['lang']):
            show_all_books(user_state, message.chat.id)
        return
    elif user_state['state'] == State.STATE_FIND:
        search_for_books(user_state, chat_id=message.chat.id, criteria=message.text)
        user_state['state'] = State.STATE_START
        user_state.save()
    elif is_skip(user_state, message):
        user_state['state'] = change_status(user_state['state'], user_state['single_state'])
        user_state.save()
    elif is_skipall(user_state, message):
        user_state['state'] = State.STATE_COMPLETE
        user_state.save()
    else:
        return
    send_state_prompt(message.chat.id, message.from_user.id)


def get_book_info_message(book_info, language):
    """
    Gets all data about the book with given id from the database and returns it in the human-readable form
    :param book_info: Row from the database with info about the book
    :param language: language of the constructed message
    :return: text of the detailed description
    TODO: additional info
    """
    if book_info is None:
        raise Exception('There is no book with id ' + book_info['_id'])
    message = ['*', book_info['title'], '*\n']
    if book_info['authors']:
        message.append(_('_Authors_: ', language))
        for author in book_info['authors']:
            message.append(author)
            message.append(', ')
        del message[-1]
        message.append('\n')
    if book_info['tags']:
        message.append(_('_Tags_: ', language))
        for tag in book_info['tags']:
            message.append(tag)
            message.append(', ')
        del message[-1]
        message.append('\n')
    message.append(_('_Language_: ', language))
    message.append(book_info['lang'])
    if book_info['description'] is not None:
        message.append('\n')
        message.append(book_info['description'])
    return ''.join(message), book_info['cover']


@bot.callback_query_handler(func=lambda call: True)
def get_callback(call):
    """
    Handler for all callback buttons
    Every callback button has its own command and id, so that we know what to change
    TODO: confirmation for deletion?
    """
    if call.message:
        command, book_id, user_from = call.data.split(' ')
        user_data = user_state_db.get(user_from)
        # Global commands for book manipulating
        if command == 'download':
            bot.send_document(chat_id=call.message.chat.id, data=book_id)
        elif command == 'delete':
            delete_book(user_from, book_id)
            bot.send_message(chat_id=call.message.chat.id, text=_('Done!', user_data['lang']))
        elif command == 'edit':
            start_change(book_id=book_id, chat_id=call.message.chat.id, from_user=user_from)

        # Changing one certain parameter of the book
        # Proceed with caution!
        elif command in ('title', 'cover', 'lang', 'desc', 'tags', 'authors'):
            user_data['single_state'] = True
            user_data['editing_book'] = book_id

            if command == 'title':
                user_data['state'] = State.STATE_TITLE
            elif command == 'cover':
                user_data['state'] = State.STATE_COVER
            elif command == 'lang':
                user_data['state'] = State.STATE_LANG
            elif command == 'desc':
                user_data['state'] = State.STATE_DESCRIPTION
            elif command == 'tags':
                user_data['state'] = State.STATE_TAGS
            elif command == 'authors':
                user_data['state'] = State.STATE_AUTHORS
            user_data.save()
            send_state_prompt(call.message.chat.id, call.from_user.id)


def get_options_keyboard(book_id, from_user):
    user = user_state_db.get(from_user)
    keyboard = InlineKeyboardMarkup()
    set_title = InlineKeyboardButton(text=_("Change title", user['lang']),
                                     callback_data="title " + book_id + ' ' + from_user)
    set_cover = InlineKeyboardButton(text=_("Set cover", user['lang']),
                                     callback_data="cover " + book_id + ' ' + from_user)
    keyboard.row(set_title, set_cover)
    set_lang = InlineKeyboardButton(text=_("Set book's language", user['lang']),
                                    callback_data="lang " + book_id + ' ' + from_user)
    set_tags = InlineKeyboardButton(text=_("Set the tag list", user['lang']),
                                    callback_data="tags " + book_id + ' ' + from_user)
    keyboard.row(set_lang, set_tags)
    set_desc = InlineKeyboardButton(text=_("Set description", user['lang']),
                                    callback_data="desc " + book_id + ' ' + from_user)
    set_authors = InlineKeyboardButton(text=_("Set list of authors", user['lang']),
                                       callback_data="authors " + book_id + ' ' + from_user)
    keyboard.row(set_desc, set_authors)
    return keyboard


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
    if from_user in book['owners']:
        book['owners'].remove(from_user)
    book.save()


def send_state_prompt(chat_id, user_id):
    """
    Sends appropriate prompt message to the user depending on current input state.
    :param chat_id: id of chat where we need to send message
    :param user_id: id of user
    """
    user_data = user_state_db.get(str(user_id))
    skip_needed = not user_data['single_state']
    if user_data['state'] == State.STATE_TITLE:
        keyboard = get_skip_keyboard(user_data['lang'], skip_needed)
        bot.send_message(chat_id=chat_id,
                         text=_("Ok, now you can set title of the book.",
                                user_data['lang']),
                         reply_markup=keyboard)
        if not user_data['single_state']:
            bot.send_message(chat_id=chat_id,
                             text=_("If you press 'skip', title would be set to the file name.\n "
                                    "You can also skip all next steps by pressing the corresponding button.",
                                    user_data['lang']))
    elif user_data['state'] == State.STATE_START:
        keyboard = get_main_menu_keyboard(user_data['lang'])
        bot.send_message(chat_id=chat_id, text=_('How can I help you, ',
                                                 user_data['lang']) + user_data['firstname'] + '?',
                         reply_markup=keyboard)
        # TODO: main menu!
    elif user_data['state'] == State.STATE_DESCRIPTION:
        keyboard = get_skip_keyboard(user_data['lang'], skip_needed)
        bot.send_message(chat_id=chat_id,
                         text=_("Please enter the book's description", user_data['lang']),  reply_markup=keyboard)
    elif user_data['state'] == State.STATE_AUTHORS:
        keyboard = get_skip_keyboard(user_data['lang'], skip_needed)
        bot.send_message(chat_id=chat_id,
                         text=_("Please enter the authors names, separated by commas.",
                                user_data['lang']), reply_markup=keyboard)
    elif user_data['state'] == State.STATE_TAGS:
        keyboard = get_skip_keyboard(user_data['lang'], skip_needed)
        bot.send_message(chat_id=chat_id,
                         text=_("Please enter the tags you want, separated by commas.",
                                user_data['lang']), reply_markup=keyboard)
    elif user_data['state'] == State.STATE_COVER:
        keyboard = get_skip_keyboard(user_data['lang'], skip_needed)
        bot.send_message(chat_id=chat_id,
                         text=_("If you have the book cover, please upload it,"
                                " so that you can easily recognize the book",
                                user_data['lang']), reply_markup=keyboard)
    elif user_data['state'] == State.STATE_LANG:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        en = KeyboardButton('En')
        ru = KeyboardButton('Ru')
        keyboard.add(en, ru)
        bot.send_message(chat_id=chat_id,
                         text=_("Please choose the book language", user_data['lang']), reply_markup=keyboard)
    elif user_data['state'] == State.STATE_USERLANG:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        en = KeyboardButton('En')
        ru = KeyboardButton('Ru')
        keyboard.add(en, ru)
        bot.send_message(chat_id=chat_id, text='Hello! Please, choose your language!')
        bot.send_message(chat_id=chat_id, text='Здравствуйте! Выберите язык!', reply_markup=keyboard)
    elif user_data['state'] == State.STATE_COMPLETE:
        keyboard = ReplyKeyboardRemove()
        if user_data['editing_book'] is not None:
            bot.send_message(chat_id, _('Okay, everything is done!', user_data['lang']), reply_markup=keyboard)
        user_data['editing_book'] = None
        user_data['single_state'] = False
        user_data['state'] = State.STATE_START
        user_data.save()
        send_state_prompt(chat_id, user_data['_id'])
    elif user_data['state'] == State.STATE_FIND:
        bot.send_message(chat_id=chat_id, text=_('Please enter the tag', user_data['lang']))


def is_skip(user_data, message):
    if message.text == _('Skip', user_data['lang']):
        return True
    return False


def is_skipall(user_data, message):
    if message.text == _('Skip all steps', user_data['lang']):
        return True
    return False


def get_book_info_keyboard(book_id, from_user):
    user_state = user_state_db.get(from_user)
    keyboard = InlineKeyboardMarkup()
    download_button = InlineKeyboardButton(
        text=_('Download', user_state['lang']), callback_data='download ' + book_id + ' ' + from_user)
    change_button = InlineKeyboardButton(
        text=_('Change info', user_state['lang']), callback_data='edit ' + book_id + ' ' + from_user)
    delete_button = InlineKeyboardButton(
        text=_('Delete', user_state['lang']), callback_data='delete ' + book_id + ' ' + from_user)
    keyboard.add(download_button, change_button, delete_button)
    return keyboard


def get_skip_keyboard(user_language, skip_needed=True):
    if skip_needed:
        skip_button = KeyboardButton(_('Skip', user_language))
        skip_all_button = KeyboardButton(_('Skip all steps', user_language))
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(skip_button, skip_all_button)
        return keyboard
    else:
        return ReplyKeyboardRemove()


def start_change(book_id, chat_id, from_user):
    user_data = user_state_db.get(from_user)
    keyboard = get_options_keyboard(book_id, from_user)
    bot.send_message(chat_id=chat_id, text=_('What do you want to change?', user_data['lang']), reply_markup=keyboard)


def change_status(state, one_time=False):
    if one_time:
        return State.STATE_START
    else:
        return state + 1


def get_main_menu_keyboard(language):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    add_book_button = KeyboardButton(_('Add new book', language))
    search_by_tag_button = KeyboardButton(_('Find book', language))
    keyboard.row(add_book_button, search_by_tag_button)
    feeling_lucky_button = KeyboardButton(_("I'm feeling lucky!", language))
    show_all_button = KeyboardButton(_('Show all books', language))
    keyboard.row(feeling_lucky_button, show_all_button)
    return keyboard


def show_all_books(user_state, chat_id):
    view = View(ddoc=dd_owner, view_name='get-book-by-owner')
    with view.custom_result(key=user_state['_id']) as result:
        empty = True
        for row in result:
            print_book(row['value'], user_state, chat_id)
            empty = False
        if empty:
            bot.send_message(chat_id, _("Your book list is empty. Add something!", user_state['lang']))
    send_state_prompt(chat_id, user_state['_id'])


def get_random_book(user_state, chat_id):
    view = View(ddoc=dd_owner, view_name='get-book-by-owner')
    with view.custom_result(key=user_state['_id']) as result:
        res = list(result)
        book = res[random.randint(0, len(res) - 1)]
        print_book(book['value'], user_state, chat_id)


def print_book(book, user_state, chat_id):
    book_data, cover = get_book_info_message(book, user_state['lang'])
    # Do I really have to query a database that much?
    keyboard = get_book_info_keyboard(book['_id'], user_state['_id'])
    if cover is not None:
        bot.send_photo(chat_id=chat_id, photo=cover,
                       parse_mode='Markdown')
    bot.send_message(chat_id=chat_id, text=book_data, reply_markup=keyboard,
                     parse_mode='Markdown')


def search_for_books(user_state, chat_id, criteria):
    query = get_by_tag(criteria, user_state['_id'])
    result = query.result
    empty = True
    for row in result:
        print_book(row, user_state, chat_id)
        empty = False
    if empty:
        bot.send_message(chat_id=chat_id,
                         text=_('I found nothing. Please, check if the tag you are searching is correct',
                                user_state['lang']))


if __name__ == '__main__':
    bot.polling(none_stop=True)

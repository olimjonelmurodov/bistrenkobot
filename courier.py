#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging, threading, base64, config, json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)
from telegram.utils.request import Request
import psycopg2
db = psycopg2.connect(**config.dbcfg)
cursor = db.cursor()
logging.basicConfig(filename=config.logfile, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
main_updater = Updater(config.main_token, use_context=True)
server_updater=Updater(config.server_token, use_context=True)
def remove_exponent(d):
    if d:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None

sql = "SELECT * from words"
cursor.execute(sql)
words = cursor.fetchall()

LANGUAGE_CHOICE, PASS_CHOICE, PHONE_CHOICE, MAIN_CHOICE, SETTINGS_CHOICE, \
SAVING_PHONE_SETTINGS, SAVING_LANGUAGE_SETTINGS  = range(7)
start_keyboard = [['🇺🇿 O\'zbekcha'],['🇷🇺 Русский']]
start_markup = ReplyKeyboardMarkup(start_keyboard, one_time_keyboard=True,  resize_keyboard=True)


def location(update, context):
    message = None
    if update.edited_message:
        message = update.edited_message
    else:
        message = update.message
    sql = "UPDATE couriers SET latitude=%s, longitude=%s WHERE userid=%s"
    data = (message.location.latitude, message.location.longitude, update.message.from_user.id)
    cursor.execute(sql, data)
    db.commit()

def do_nothing(update, context):
    pass
    
def tr(s, context):
    for word in words:
        if word[1]==s:
            if russian(context):
                return word[3]
            elif uzbek(context):
                return word[2]
    return s.replace('_', ' ').title()
    
def uzbek(context):
    if context.user_data['lang']==0:
        return True
    return False

def russian(context):
    if context.user_data['lang']==1:
        return True
    return False
    
def echo(update, context):
    conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, start), None), context)
    return LANGUAGE_CHOICE
    
def start(update, context):
    update.message.reply_text(
        "Tilni tanlang:\nВыберите язык:",
        reply_markup=start_markup)
    return LANGUAGE_CHOICE

def uzbek_choice(update, context):
    context.user_data['lang']=0
    return request_pass(update, context)

def russian_choice(update, context):
    context.user_data['lang']=1
    return request_pass(update, context)

def request_pass(update, context):
    update.message.reply_text('Operator tomonidan berilgan kodni tering (hozir 123):')
    return PASS_CHOICE

def verify_pass(update, context):
    if update.message.text=="123":
        return request_phone(update, context)
    else:
        update.message.reply_text('Xato parol')

def request_phone(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('Raqamni kiritish', request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text('Raqamni kiritish tugmasini bosing', reply_markup=reply_markup)
    return PHONE_CHOICE

def save_phone(update, context):
    context.user_data['phone']=update.message.contact.phone_number
    return save_init_data(update, context)

def save_init_data(update, context):
    context.user_data['status']=0
    cursor.execute('INSERT INTO couriers (userid, phone) SELECT %s, %s WHERE NOT EXISTS(SELECT userid FROM couriers WHERE userid = %s)', (update.message.from_user.id, context.user_data['phone'], update.message.from_user.id))
    db.commit()
    return main_choice(update, context)

def main_choice(update, context):
    choice_keyboard = [['Buyurtma olish'],['Mening buyurtmalarim'],['⚙️ ' + tr('options', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(tr('how_to_help', context), reply_markup=choice_markup)
    return MAIN_CHOICE

def start_sending_location(update, context):
    context.user_data['status']=1-context.user_data['status']
    if context.user_data['status']==1:
        update.message.reply_text('Buyurtma olish: Yoqildi')
    else:
        update.message.reply_text('Buyurtma olish: O\'chirildi')
    return main_choice(update, context)

def my_orders(update, context):
    update.message.reply_text('Hali qilinmadi')

def settings_choice(update, context):
    show_status(update, context)
    return SETTINGS_CHOICE

def show_status(update, context):
    sql = "SELECT id, phone FROM couriers WHERE userid=(%s)"
    data = (update.message.from_user.id, )
    cursor.execute(sql, data)
    res = cursor.fetchall()
    s=""
    if (res[0][1]):
        s += tr('your_phone', context)+' '+res[0][1]
    else:
        s += tr('your_phone', context)+' '+tr('not_entered', context)
    s+='\n'
    s+='\n'
    s+=tr('change_info', context)
    choice_keyboard = [['⬅️ '+tr('back', context)], [tr('phone_change', context)], [tr('language_change', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.message.reply_text(s, reply_markup=choice_markup)

def phone_settings_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(tr('phone_entering', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_PHONE_SETTINGS

def language_settings_choice(update, context):
    update.message.reply_text(tr('choose_lang', context), reply_markup=start_markup)
    return SAVING_LANGUAGE_SETTINGS

def set_user_uzbek(update, context):
    context.user_data['lang']=0
    sql="UPDATE couriers SET lang=0 WHERE userid=%s"
    data=(update.message.from_user.id, )
    cursor.execute(sql, data)
    db.commit()
    return settings_choice(update, context)    

def set_user_russian(update, context):
    context.user_data['lang']=1
    sql="UPDATE couriers SET lang=1 WHERE userid=%s"
    data=(update.message.from_user.id, )
    cursor.execute(sql, data)
    db.commit()
    return settings_choice(update, context)

def set_user_phone(update, context):
    sql = "UPDATE couriers SET phone = %s WHERE userid = %s"
    data = (update.message.contact.phone_number, update.message.from_user.id)
    cursor.execute(sql, data)
    db.commit()
    update.message.reply_text(tr('info_saved', context));
    return settings_choice(update, context)


def manage(update, context):
    query = update.callback_query
    query.answer()
    d = json.loads(query.data)
    if d['action']=='iconfirm':
        data={}
        data['action']='ready'
        data['id'] = d['id']
        data['uid'] = query.from_user.id
        s="Kuryer "+str(d['id'])+"-buyurtmani tasdiqladi"
        sql = "SELECT userid from servers"
        cursor.execute(sql)
        res = cursor.fetchall()
        if res:
            for i in res:
                inline = InlineKeyboardMarkup([[InlineKeyboardButton("🖂 Kuryerga berildi", callback_data=json.dumps(data))]])
                server_updater.bot.send_message(i[0], s, reply_markup=inline)
        query.edit_message_reply_markup(None)
    elif d['action']=='cancel':
        s="Kuryer "+str(d['id'])+"-buyurtmani bekor qildi"
        sql = "SELECT userid from servers"
        cursor.execute(sql)
        res = cursor.fetchall()
        if res:
            for i in res:
                server_updater.bot.send_message(i[0], s)
        query.edit_message_reply_text("Bekor qilindi")

    elif d['action']=='deliver':
        reply_markup = ReplyKeyboardMarkup([["⏮️ Boshiga qaytish"]],  resize_keyboard=True)                 
        s="Buyurtmangiz manzilingizga yetkazildi, bog'lanish uchun operator raqami  +998(90) 123-45-67"
        cursor.execute("SELECT userid from customers where id IN (SELECT customerid from orders where id=%s)", (d['id'], ))
        uid = cursor.fetchone()[0]
        main_updater.bot.send_message(uid, s, reply_markup=reply_markup)
        query.edit_message_reply_markup(None)
        
        
def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    print(list(context))
    try:
        update.effective_message.reply_text('Tizimdagi xato. Iltimos keyinroq urinib ko\'ring')
    except:
        pass

def cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

updater = Updater(config.courier_token, use_context=True)

dp = updater.dispatcher

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', start)
    ],
    states={
        LANGUAGE_CHOICE: [
                   MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
                            uzbek_choice),
                   MessageHandler(Filters.regex('^🇷🇺 Русский$'),
                            russian_choice),
                   MessageHandler(Filters.all, do_nothing)
        ],
        PASS_CHOICE:[
                   MessageHandler(Filters.text,
                            verify_pass),
                   MessageHandler(Filters.all, do_nothing)
        
        ],
        PHONE_CHOICE:[MessageHandler(Filters.contact,
                            save_phone),
                   MessageHandler(Filters.all, do_nothing)        
        ],
        MAIN_CHOICE: [
                   MessageHandler(Filters.regex('^Buyurtma olish$'),
                        start_sending_location),
                   MessageHandler(Filters.regex('^Mening buyurtmalarim$'),
                        my_orders),
                   MessageHandler(Filters.regex('^⚙️ Sozlanmalar$'),
                        settings_choice),
                   MessageHandler(Filters.regex('^⚙️ Настройки$'),
                        settings_choice),
                   MessageHandler(Filters.all, do_nothing)
        ],
        SETTINGS_CHOICE:[
                   MessageHandler(Filters.regex('^Telefon raqamini o\'zgartirish$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^Изменить номер телефона$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^Tilni o\'zgartirish$'),
                                  language_settings_choice),
                   MessageHandler(Filters.regex('^Изменить язык$'),
                                  language_settings_choice),
                   MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  main_choice),
                   MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  main_choice),
                   MessageHandler(Filters.all, do_nothing)
        ],
        SAVING_PHONE_SETTINGS: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      settings_choice),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      settings_choice),
           MessageHandler(Filters.contact, set_user_phone),
           MessageHandler(Filters.all, do_nothing)
        ],
        SAVING_LANGUAGE_SETTINGS: [
            MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
                                  set_user_uzbek),
            MessageHandler(Filters.regex('^🇷🇺 Русский'),
                            set_user_russian),
            MessageHandler(Filters.all, do_nothing)
        ]
    },
    fallbacks=[MessageHandler(Filters.regex('^Done$'), cancel)],
    allow_reentry = True)
dp.add_handler(MessageHandler(Filters.location, location))
dp.add_handler(conv_handler)
dp.add_handler(CallbackQueryHandler(manage))
dp.add_handler(MessageHandler(Filters.all, echo))
dp.add_error_handler(error)
#dp.add_handler(MessageHandler(Filters.text, verify))

updater.start_polling()
updater.idle()

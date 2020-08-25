#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging, threading, base64, config, json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (Updater, Defaults, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)
from telegram.utils.request import Request
import psycopg2
db = psycopg2.connect(**config.dbcfg)
cursor = db.cursor()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
defaults = Defaults(parse_mode=ParseMode.HTML)
main_updater = Updater(config.main_token, use_context=True)
courier_updater = Updater(config.courier_token, use_context=True)
def remove_exponent(d):
    if d:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None

sql = "SELECT * from words"
cursor.execute(sql)
words = cursor.fetchall()

LANGUAGE_CHOICE, PASS_CHOICE, PHONE_CHOICE, MAIN_CHOICE, SETTINGS_CHOICE, HELP_CHOICE, \
SAVING_PHONE_SETTINGS, SAVING_LANGUAGE_SETTINGS, HELP_FEEDBACK_CHOICE  = range(9)
start_keyboard = [['🇺🇿 O\'zbekcha'],['🇷🇺 Русский']]
start_markup = ReplyKeyboardMarkup(start_keyboard, one_time_keyboard=True,  resize_keyboard=True)


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
    cursor.execute('INSERT INTO servers (userid, phone) SELECT %s, %s WHERE NOT EXISTS(SELECT userid FROM servers WHERE userid = %s)', (update.message.from_user.id, context.user_data['phone'], update.message.from_user.id))
    db.commit()
    return main_choice(update, context)

def main_choice(update, context):
    choice_keyboard = [['Buyurtma olish'],['Mahsulotlar statusi', 'Mening buyurtmalarim'],['⚙️ ' + tr('options', context)], [tr('help', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(tr('how_to_help', context), reply_markup=choice_markup)
    return MAIN_CHOICE

def receive_orders(update, context):
    context.user_data['status']=1-context.user_data['status']
    if context.user_data['status']==1:
        update.message.reply_text('Buyurtma olish: Yoqildi')
    else:
        update.message.reply_text('Buyurtma olish: O\'chirildi')

def products_status(update, context):
    update.message.reply_text('Hali qilinmadi')

def my_orders(update, context):
    update.message.reply_text('Hali qilinmadi')

def settings_choice(update, context):
    show_status(update, context)
    return SETTINGS_CHOICE

def show_status(update, context):
    sql = "SELECT id, phone FROM servers WHERE userid=(%s)"
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

def name_settings_choice(update, context):
    update.message.reply_text(tr('name_enter', context))
    return SAVING_NAME_SETTINGS

def second_phone_settings_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(tr('phone_entering', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_SECOND_PHONE_SETTINGS

def set_user_uzbek(update, context):
    context.user_data['lang']=0
    sql="UPDATE servers SET lang=0 WHERE userid=%s"
    data=(update.message.from_user.id, )
    cursor.execute(sql, data)
    db.commit()
    return settings_choice(update, context)    

def set_user_russian(update, context):
    context.user_data['lang']=1
    sql="UPDATE servers SET lang=1 WHERE userid=%s"
    data=(update.message.from_user.id, )
    cursor.execute(sql, data)
    db.commit()
    return settings_choice(update, context)

def set_user_phone(update, context):
    sql = "UPDATE servers SET phone = %s WHERE userid = %s"
    data = (update.message.contact.phone_number, update.message.from_user.id)
    cursor.execute(sql, data)
    db.commit()
    update.message.reply_text(tr('info_saved', context));
    return settings_choice(update, context)

def help_choice(update, context):
    keyboard = [[tr('manual', context), tr('feedback', context)], ['⬅️ '+tr('back', context)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(tr('how_to_help', context), reply_markup=reply_markup)
    return HELP_CHOICE

def help_manual_choice(update, context):
    update.message.reply_text("GIF")
    return help_choice(update, context)

def help_feedback_choice(update, context):
    update.message.reply_text(tr('feedback_enter', context))
    return HELP_FEEDBACK_CHOICE

def send_to_admin(update, context):
    sql = "SELECT id, phone FROM servers WHERE userid=(%s)"
    cursor.execute(sql, (update.message.from_user.id, ))
    res = cursor.fetchall()
    s=""
    if (res[0][1]):
        s += 'Telefon raqami: '+res[0][1]
    else:
        s += 'Telefon raqami: '+ 'kiritilmagan'
    s+='\n'
    if update.message.from_user.username:
        s+="Logini: @"+update.message.from_user.username    
        s+='\n'    
    s+='Taklif: ' +update.message.text
    sql = "SELECT userid from admins"
    cursor.execute(sql)
    res = cursor.fetchall()
    for i in res:
        updater.bot.send_message(i[0], s)
    update.message.reply_text(tr('feedback_received', context))
    return help_choice(update, context)


def manage(update, context):
    query = update.callback_query
    query.answer()
    data = json.loads(query.data)
    if data['action']=='ready':
        rdata={}
        rdata['action']='deliver'
        rdata['id'] = data['id']
        inline=[]
        inlinekeys = []
        inlinekeys.append(InlineKeyboardButton("🆗 Yetkazildi", callback_data=json.dumps(rdata)))
        inline.append([inlinekeys[0]])
        inlinemarkup=InlineKeyboardMarkup(inline)
        courier_updater.bot.send_message(data['uid'], str(data['id'])+'-buyurtma kuryerga berilgani tasdiqlandi', reply_markup=inlinemarkup)   
        cursor.execute("SELECT userid from customers where id IN (SELECT customerid from orders where id=%s)", (data['id'], ))
        uid = cursor.fetchone()[0]
#        reply_markup = ReplyKeyboardMarkup([["🚗 Joylashuv"]],  resize_keyboard=True)
#        main_updater.bot.send_message(uid, "Buyurtmangiz tayyor, yetkazish uchun kuryerga berildi", reply_markup=reply_markup)
        main_updater.bot.send_message(uid, "Buyurtmangiz tayyor, yetkazish uchun kuryerga berildi")
        query.edit_message_reply_markup(None)

    elif data['action']=='icancel':
        cursor.execute('UPDATE orders SET initial_confirmation=0 where id=%s', (data['id'], ))
        db.commit()
        reply_markup = ReplyKeyboardMarkup([["⏮️ Boshiga qaytish"]],  resize_keyboard=True)
        main_updater.bot.send_message(data['userid'], "Buyurtmangiz bekor qilindi", reply_markup=reply_markup)
    elif data['action']=='iconfirm':
        query.edit_message_reply_markup(None)
        cursor.execute('UPDATE orders SET initial_confirmation=1 where id=%s', (data['id'], ))
        db.commit()
#        reply_markup = ReplyKeyboardMarkup([["💾 Tasdiqlash", "❌ Bekor qilish"]],  resize_keyboard=True)
        main_updater.bot.send_message(data['userid'], "Buyurtmangiz tasdiqlandi ({}-raqam). Buyurtmangiz tayyorlanishini kuting.".format(str(data['id'])))
    elif data['action']=='fcancel':
        cursor.execute('UPDATE orders SET final_confirmation=0 where id=%s', (data['id'], ))
        db.commit()
        reply_markup = ReplyKeyboardMarkup([["Boshiga qaytish"]],  resize_keyboard=True)
        main_updater.bot.send_message(data['userid'], "Buyurtmangiz bekor qilindi", reply_markup=reply_markup)
    elif data['action']=='fconfirm':
        oid=data['id']
        uid=data['userid']
        cursor.execute('UPDATE orders SET final_confirmation=1 where id=%s', (oid, ))
        db.commit()
        sql="SELECT userid from couriers"
        cursor.execute(sql)
        res=cursor.fetchall()
        if res:
            s="Sizga yetkazish uchun buyurtma keldi"
            s+='\n'
            s+="Buyurtma raqami: "+str(data['id'])
            for i in res:
                inline=[]
                inlinekeys = []
                data={}
                data['action']='cancel'
                data['id'] = oid
                inlinekeys.append(InlineKeyboardButton("❌ "+tr('cancel', context), callback_data=json.dumps(data)))
                data={}
                data['action']='confirm'
                data['id'] = oid
                inlinekeys.append(InlineKeyboardButton("Tasdiqlash", callback_data=json.dumps(data)))
                inline.append([inlinekeys[0], inlinekeys[1]])
                inlinemarkup=InlineKeyboardMarkup(inline)
                courier_updater.bot.send_message(i[0], s, reply_markup=inlinemarkup)                
        reply_markup = ReplyKeyboardMarkup([["Davom etish"]],  resize_keyboard=True)        
        main_updater.bot.send_message(uid, "Buyurtmangiz to'lov usuli tasdiqlandi", reply_markup=reply_markup)

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

updater = Updater(config.server_token, use_context=True, defaults=defaults)

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
        MAIN_CHOICE: [MessageHandler(Filters.regex('^Buyurtma olish$'),
                            receive_orders),
                      MessageHandler(Filters.regex('^Mahsulotlar statusi$'),
                            products_status),
                      MessageHandler(Filters.regex('^Mening buyurtmalarim$'),
                            my_orders),
                      MessageHandler(Filters.regex('^⚙️ Sozlanmalar$'),
                            settings_choice),
                      MessageHandler(Filters.regex('^⚙️ Настройки$'),
                            settings_choice),
                      MessageHandler(Filters.regex('^Yordam$'),
                            help_choice),
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
        ],
        HELP_CHOICE: [MessageHandler(Filters.regex('^Qo\'llanma$'),
                                      help_manual_choice),
                       MessageHandler(Filters.regex('^Руководство$'),
                                      help_manual_choice),
                       MessageHandler(Filters.regex('^Admin bilan bog\'lanish$'),
                                      help_feedback_choice),
                       MessageHandler(Filters.regex('^Связаться с администратором$'),
                                      help_feedback_choice),
                       MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                      main_choice),
                       MessageHandler(Filters.regex('^⬅️ Назад$'),
                                      main_choice),
                       MessageHandler(Filters.all, do_nothing)
        ],
        HELP_FEEDBACK_CHOICE: [
                       MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                      help_choice),
                       MessageHandler(Filters.regex('^⬅️ Назад$'),
                                      help_choice),
                       MessageHandler(Filters.text,
                                      send_to_admin)
        ],
    },
    fallbacks=[MessageHandler(Filters.regex('^Done$'), cancel)],
    allow_reentry = True)
dp.add_handler(conv_handler)
dp.add_handler(CallbackQueryHandler(manage))
dp.add_handler(MessageHandler(Filters.all, echo))
dp.add_error_handler(error)
#dp.add_handler(MessageHandler(Filters.text, verify))

updater.start_polling()
updater.idle()

import logging, threading, base64, config, threading
import geopy.distance
from geopy.geocoders import Nominatim
from decimal import Decimal
import urllib.request, json, time
from io import BytesIO
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ParseMode
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, Defaults,
                          ConversationHandler, CallbackQueryHandler)
from telegram.utils.request import Request
import psycopg2
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
token = config.main_token
defaults = Defaults(parse_mode=ParseMode.HTML)
updater = Updater(token, use_context=True, defaults=defaults)
courier_updater = Updater(config.courier_token, use_context=True)
server_updater=Updater(config.server_token, use_context=True, defaults=defaults)
logger = logging.getLogger(__name__)

db = psycopg2.connect(**config.dbcfg)
cursor = db.cursor()


def printnum(val):
    return '{:,}'.format(val).replace(',', ' ')

def remove_exponent(d):
    if d:
        d=Decimal(d/100)
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None

sql = "SELECT * from words"
cursor.execute(sql)
words = cursor.fetchall()

LANGUAGE_CHOICE, NAME_CHOICE, PHONE_CHOICE, VERIFY_PHONE_CHOICE, SECOND_PHONE_CHOICE, MAIN_CHOICE, SETTINGS_CHOICE, HELP_CHOICE, \
ORDER_START_CHOICE, ORDER_LOCATION_MANUAL_CHOICE, ORDER_MENU_CHOICE, ORDER_PLACE_CHOICE, ORDER_CATEGORIES_CHOICE, ORDER_PRODUCTS_CHOICE, ORDER_PRODUCT_NUMBERS_CHOICE, \
ORDER_CART_CHOICE, ORDER_CART_CONFIRM_CHOICE, ORDER_WAITING_INIT, ORDER_PAY_METHOD_CHOICE, ORDER_PAYME_CHOICE, ORDER_WAITING_FINAL, ORDER_IN_WAY, ORDER_DELIVERED, \
SAVING_PHONE_SETTINGS, SAVING_NAME_SETTINGS, SAVING_SECOND_PHONE_SETTINGS, SAVING_LANGUAGE_SETTINGS, HELP_FEEDBACK_CHOICE  = range(28)

start_keyboard = [['🇺🇿 O\'zbekcha'],['🇷🇺 Русский']]
start_markup = ReplyKeyboardMarkup(start_keyboard, one_time_keyboard=True,  resize_keyboard=True)


def db_execute_get_more(sql, data=None, commit=False):
    if data:
        cursor.execute(sql, data)
    else:
        cursor.execute(sql)        
    if commit:
        db.commit()
    return cursor.fetchall()

def db_execute_multi(sql, datas):
    for i in range(len(datas)):
        cursor.execute(sql, datas[i])
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
    show_start_message(update, context)
    return LANGUAGE_CHOICE

def show_start_message(update, context):
    update.message.reply_text(
        "Bistrenko onlayn xizmatiga xush kelibsiz. Tilni tanlang:\nДобро пожаловать в онлайн сервис Бистренко. Выберите язык:",
        reply_markup=start_markup)

def uzbek_choice(update, context):
    context.user_data['lang']=0
    return request_phone(update, context)

def russian_choice(update, context):
    update.message.reply_text("Hali ruscha qilinmadi")
    context.user_data['lang']=1
#    return request_phone(update, context)

def request_name(update, context):
    update.message.reply_text('Sizni kim deb chaqiraylik?')
    return NAME_CHOICE

def save_name(update, context):
    context.user_data['name']=update.message.text
    return request_phone(update, context)

def request_phone(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📱 Raqamni kiritish', request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text('"Raqamni kiritish" tugmasini bosing yoki qo\'lda kiriting (+998XXYYYYYYY shaklida), bu raqamga SMS yuboriladi.', reply_markup=reply_markup)
    return PHONE_CHOICE

def request_verify_phone_auto(update, context):
    context.user_data['phone']=update.message.contact.phone_number
    return request_verify_phone(update, context)

def request_verify_phone_manual(update, context):
    context.user_data['phone']=update.message.text
    return request_verify_phone(update, context)
    
def request_verify_phone(update, context):
    reply_markup = ReplyKeyboardMarkup([['⬅️ '+tr('back', context)]],  resize_keyboard=True)
    update.message.reply_text('Sizning kiritgan telefon raqamingizga SMS yuborildi. Unda berilgan kodni kiriting (hozir 123):', reply_markup=reply_markup)
    return VERIFY_PHONE_CHOICE   

def verify_phone(update, context):
    if update.message.text=="123":
        update.message.reply_text('Kod tasdiqlandi')
        return save_phone(update, context)
    else:
        update.message.reply_text('Kod xato')        

def save_phone(update, context):
    return save_init_data(update, context)

def request_second_phone(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📱 Raqamni kiritish', request_contact=True), '⏭️ O\'tkazib yuborish']],  resize_keyboard=True)
    update.message.reply_text('Ikkinchi telefon: "Raqamni kiritish" tugmasini bosing yoki qo\'lda kiriting (+998XXYYYYYYY shaklida) yoki o\'tkazib yuborish tugmasini bosing', reply_markup=reply_markup)
    return SECOND_PHONE_CHOICE

def save_second_phone_auto(update, context):
    context.user_data['second_phone']=update.message.contact.phone_number
    return save_init_data(update, context)

def save_second_phone_manual(update, context):
    context.user_data['second_phone']=update.message.text
    return save_init_data(update, context)
    
def save_init_data(update, context):
    if 'second_phone' not in context.user_data:
        context.user_data['second_phone'] = None
    sql = "INSERT INTO customers (name, phone, userid, phone2, lang) SELECT %s, %s, %s, %s, %s WHERE NOT EXISTS(SELECT userid FROM customers WHERE userid = %s)"
    data = (update.message.from_user.full_name, context.user_data['phone'], update.message.from_user.id, context.user_data['second_phone'], context.user_data['lang'], update.message.from_user.id)
    cursor.execute(sql, data)
    db.commit()
    return main_choice(update, context)

def main_choice(update, context):

    choice_keyboard = [['🛎 '+tr('order', context)],['⚙️ ' + tr('options', context)], ['ℹ️ '+tr('help', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(tr('make_order', context), reply_markup=choice_markup)
    return MAIN_CHOICE
    
def request_location(update, context):
    context.user_data['address'] = ""
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📍 Joylashuvni yuborish', request_location=True), '✍️ Joylashuvni qo\'lda ko\'rsatish'], ['⬅️ '+tr('back', context)]], one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(tr('location_entering', context), reply_markup=reply_markup)
    return ORDER_START_CHOICE
    
def request_manual_location(update, context):
    reply_markup = ReplyKeyboardMarkup([['⬅️ '+tr('back', context)]], one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(tr('orientation_entering', context), reply_markup=reply_markup)
    return ORDER_LOCATION_MANUAL_CHOICE

def save_location(update, context):
    loc = update.message.location
    destlat = loc.latitude
    destlong = loc.longitude
    context.user_data['latitude']=loc.latitude
    context.user_data['longitude']=loc.longitude
    startfee = 5000
    unitfee = 1000
    startdist = 0
    srclat = 41.259495
    srclong = 69.189271
    src = (srclat, srclong)
    dest = (destlat, destlong)
    distance = geopy.distance.distance(src, dest).km
    locator = Nominatim(user_agent='myGeocoder')
    context.user_data['address'] = locator.reverse(str(destlat)+', '+str(destlong)).address
    if distance > startdist:
        context.user_data['deliveryfee'] = round(float(startfee)+float(unitfee)*round((distance-startdist), 1))
    else:
        context.user_data['deliveryfee'] = round(float(startfee))
    s=tr('your_address', context)+' '+context.user_data['address']
#    s+='\n'
#    s+="Boshlang'ich narx: "+ str(startfee)+' '+tr('som', context)
#    s+='\n'
#    s+="Har km uchun narx: "+ str(unitfee)+' '+tr('som', context)
#    s+='\n'
#    s+="Masofa: "+ str(round(distance, 1))+" km"    
#    s+='\n'
#    s+=tr('approximate_delivery_fee', context)+' '+str(context.user_data['deliveryfee'])+' '+tr('som', context)
    update.message.reply_text(s)
    return request_menu(update, context)

def save_manual_location(update, context):
    text = update.message.text
    if len(text)>=1000:
        update.message.reply_text(tr('too_long', context))
        return request_manual_location(update, context)
    context.user_data['orientation']=text
    return request_menu(update, context)

def request_menu(update, context):
    if uzbek(context):
        sql = "SELECT uzbek from menus"
    elif russian(context):
        sql = "SELECT russian from menus"
    keys = []
    keyboard = []
    cursor.execute(sql)
    result = cursor.fetchall()
    if result:
        for i in range(len(result)):
            keys.append(str(result[i][0]))
        keyboard.append(['⬅️ '+tr('back', context)])
        for i in range(0, len(keys), 2):
            try:
                keyboard.append([keys[i], keys[i+1]])
            except:
                keyboard.append([keys[i]])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('choose_service', context), reply_markup=markup)
        return ORDER_MENU_CHOICE
    else:
        update.message.reply_text(tr('no_service', context))
    
def save_menu(update, context):
    context.user_data['menu']=update.message.text
    return request_place(update, context)

def request_place(update, context):
    if uzbek(context):
        sql = "SELECT uzbek from places WHERE places.menuid IN (select id from menus where uzbek=%s)"
    elif russian(context):
        sql = "SELECT russian from places WHERE places.menuid IN (select id from menus where russian=%s)"        
    keys = []
    keyboard = []
    cursor.execute(sql, (context.user_data['menu'], ))
    result = cursor.fetchall()
    if result:
        for i in range(len(result)):
            keys.append(str(result[i][0]))
        keyboard.append(['⬅️ '+tr('back', context)])
        for i in range(0, len(keys), 2):
            try:
                keyboard.append([keys[i], keys[i+1]])
            except:
                keyboard.append([keys[i]])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('choose_place', context), reply_markup=markup)
        return ORDER_PLACE_CHOICE
    else:
        update.message.reply_text(tr('no_place', context))

def save_place(update, context):
    context.user_data['place']=update.message.text
    context.user_data['acquired']=[]
    context.user_data['deliveryfee'] = 0
    if uzbek(context):
        sql = "SELECT menu from places where uzbek = %s"
    elif russian(context):
        sql = "SELECT menu from places where russian = %s"        
    data = (context.user_data['place'], )
    cursor.execute(sql, data)
    res = cursor.fetchone()
    if res:
        if res[0]:
            update.message.reply_text(res[0])
    return request_category(update, context)

def request_category(update, context):
    context.user_data['cancel_order']=True
    if uzbek(context):
        sql = "SELECT uzbek from categories WHERE categories.placeid IN (select id from places where uzbek=%s)"
    elif russian(context):
        sql = "SELECT russian from categories WHERE categories.placeid IN (select id from places where russian=%s)"        
    keys = []
    keyboard = []
    cursor.execute(sql, (context.user_data['place'], ))
    result = cursor.fetchall()
    if result:
        for i in range(len(result)):
            keys.append(str(result[i][0]))
        keyboard.append(['⬅️ '+tr('back', context), '📥 '+tr('basket', context)])
        for i in range(0, len(keys), 2):
            try:
                keyboard.append([keys[i], keys[i+1]])
            except:
                keyboard.append([keys[i]])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('choose_category', context), reply_markup=markup)
        return ORDER_CATEGORIES_CHOICE
    else:
        update.message.reply_text(tr('no_category', context))

def save_category(update, context):
    context.user_data['category']=update.message.text
    return request_product(update, context)

def request_product(update, context):
    if uzbek(context):
        sql = "SELECT uzbek from products WHERE products.categoryid IN (select id from categories where uzbek=%s)"
    elif russian(context):
        sql = "SELECT russian from products WHERE products.categoryid IN (select id from categories where russian=%s)"        
    keys = []
    keyboard = []
    cursor.execute(sql, (context.user_data['category'], ))
    result = cursor.fetchall()
    if result:
        for i in range(len(result)):
            keys.append(str(result[i][0]))
        keyboard.append(['⬅️ '+tr('back', context)])
        for i in range(0, len(keys), 2):
            try:
                keyboard.append([keys[i], keys[i+1]])
            except:
                keyboard.append([keys[i]])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('choose_product', context), reply_markup=markup)
        return ORDER_PRODUCTS_CHOICE
    else:
        update.message.reply_text(tr('no_product', context))

def save_product(update, context):
    context.user_data['product']=update.message.text
    return request_product_number(update, context)

def request_product_number(update, context):
    keyboard=[['⬅️ '+tr('back', context)], ['1', '2', '3'],['4', '5', '6'],['7', '8', '9']]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    s=get_product_text_and_photo(update.message.text, update, context, True)
    if s:
        update.message.reply_html(s)
        s=tr('enter_quantity', context)
        update.message.reply_html(s, reply_markup=markup)
        return ORDER_PRODUCT_NUMBERS_CHOICE    

def get_product_text_and_photo(text, update, context, getmaxcount=False):
    if uzbek(context):
        sql = "SELECT uzbek, desc_uz, image, price, maxcount from products where uzbek=%s"
    elif russian(context):
        sql = "SELECT russian, desc_ru, image, price, maxcount from products where russian=%s"
    data = (text, )
    cursor.execute(sql, data)
    results = cursor.fetchall()
    if results:
        result = results[0]
        s='<b>'+result[0]+'</b>'+':\n\n'
        if result[1]:
            s+=result[1]+'\n'
        s+='\n'
        if result[3]:
            s+=tr('price', context)+' '+str(printnum(remove_exponent(result[3])))+' '+tr('som', context)
            context.user_data['lastfee'] = result[3]
        if result[2]:
            photo = result[2]
            update.effective_message.reply_photo(BytesIO(photo))
        if getmaxcount:
            if result[4]:
                context.user_data['maxcount'] = int(result[4])
            else:
                context.user_data['maxcount'] = 100
        return s
    else:
        return None

def save_product_number(update, context):
    if int(update.message.text)>context.user_data['maxcount']:
        update.message.reply_text(tr('product_overflow', context)+str(context.user_data['maxcount']))
    else:
        for i in context.user_data['acquired']:
            if i[0] == context.user_data['product']:
                i[1] += int(update.message.text)
                update.message.reply_text(tr('product_added', context))
                return request_category(update, context)
        context.user_data['acquired'].append([context.user_data['product'], int(update.message.text), context.user_data['lastfee'], context.user_data['maxcount']])
        update.message.reply_text(tr('product_added', context))
        return request_category(update, context)

def order_cart(update, context):
    inlinekeys = []
    keyboard = []
    inline = []
    t=""
    keyboard.append(['🚀 '+tr('doing_order', context), '❌ '+tr('delete', context)])
    keyboard.append(['⬅️ '+tr('back', context)])
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    acquired = context.user_data['acquired']
    if acquired:
        total = 0
        for i in range(len(acquired)):
            key = acquired[i][0]
            value = acquired[i][1]
            price = acquired[i][2]
            maxcount = acquired[i][3]
            total+=value*price
            t+='<b>'+key+'</b>'+'\n'
            t+=str(value)+' x '+str(printnum(remove_exponent(price)))+' = '+str(printnum(remove_exponent(value*price))) +' '+tr('som', context)+'\n'
            data={}
            data['action']='view'
            data['id'] = i
            inlinekeys.append(InlineKeyboardButton(key+": "+str(value), callback_data=json.dumps(data)))
            data={}
            data['action']='add'
            data['id'] = i
            inlinekeys.append(InlineKeyboardButton("➕", callback_data=json.dumps(data)))
            data={}
            data['action']='reduce'
            data['id'] = i
            inlinekeys.append(InlineKeyboardButton("➖", callback_data=json.dumps(data)))
            data={}
            data['action']='delete'
            data['id'] = i
            inlinekeys.append(InlineKeyboardButton("❌", callback_data=json.dumps(data)))
        for i in range(0, len(inlinekeys), 4):
            inline.append([inlinekeys[i]])
            inline.append([inlinekeys[i+1], inlinekeys[i+2], inlinekeys[i+3]])
        inlinemarkup=InlineKeyboardMarkup(inline)
        s=""
        if context.user_data['address']:
            s+=tr('your_address', context)+' '+str(context.user_data['address'])+'\n'
            s+=tr('approximate_delivery_fee', context)+' '+str(context.user_data['deliveryfee'])+' '+tr('som', context)
        else:
            if 'orientation' in context.user_data:
                s+=tr('your_address', context)+' '+str(context.user_data['orientation'])
        s+='\n\n'

        s+=tr('spendings', context)+'\n' + t
        s+='\n'
        s+='<b>'+tr('overall', context)+' ' + str(printnum(remove_exponent(total))) +' '+tr('som', context) + '</b>'
        update.effective_message.reply_html(s, reply_markup=markup)
        s=tr('your_basket', context)
        update.effective_message.reply_text(s, reply_markup=inlinemarkup)
    else:
        update.effective_message.reply_text(tr('no_product', context), reply_markup=markup)
    return ORDER_CART_CHOICE

def manage_acquired(update, context):
    query = update.callback_query
    query.answer()
    data = json.loads(query.data)
    try:
        if data['action']=='view':
            s = get_product_text_and_photo(context.user_data['acquired'][int(data['id'])][0], update, context)
            update.effective_message.reply_html(s)
        elif data['action']=='reduce':
            product = context.user_data['acquired'][int(data['id'])]
            product[1]-=1
            if product[1]==0:
                context.user_data['acquired'].pop(int(data['id']))
        elif data['action']=='delete':
            context.user_data['acquired'].pop(int(data['id']))
        elif data['action']=='add':
            product = context.user_data['acquired'][int(data['id'])]
            if product[1]>=product[3]:
                update.effective_message.reply_text(tr('product_overflow', context)+str(product[3]))
            else:
                product[1]+=1
    except IndexError:
        pass
    return order_cart(update, context)

def order_clear_cart(update, context):
    if context.user_data['acquired']:
        context.user_data['acquired']=[]
        update.message.reply_text(tr('basket_emptied', context))
    return order_cart(update, context)

def request_order_pay_method(update, context):
    if context.user_data['acquired']:
        reply_markup = ReplyKeyboardMarkup([["💳 PayMe", "💰 Naqd"]],  resize_keyboard=True)
        update.message.reply_text("To'lov usulini tanlang:", reply_markup=reply_markup)    
        return ORDER_PAY_METHOD_CHOICE
    else:
        return order_cart(update, context)


def order_payme_choice(update, context):
    update.message.reply_text("Sizga SMS yuborilishi kerak. Ushbu SMSdagi havola orqali to'lovni amalga oshiring.\n(Shartnoma yo'qligi sababli ayni paytda ishlamaydi.)")    
#    return payme_waiting_phase(update, context)

def order_cash_choice(update, context):
    return order_cart_confirm(update, context)
    s="Buyurtma raqami: <b>"+str(context.user_data['orderid'])+"</b>"
    s+='\n'
    s+="To'lov usuli: <b>Naqd</b>"
    sql = "SELECT userid from servers"
    users_to_send = db_execute_get_more(sql)
    for i in users_to_send:
        inline=[]
        inlinekeys = []
        data={}
        data['action']='fcancel'
        data['id'] = context.user_data['orderid']
        data['userid'] = update.message.from_user.id
        inlinekeys.append(InlineKeyboardButton("❌ "+tr('cancel', context), callback_data=json.dumps(data)))
        data={}
        data['action']='fconfirm'
        data['id'] = context.user_data['orderid']
        data['userid'] = update.message.from_user.id
        inlinekeys.append(InlineKeyboardButton("💾 Kuryerga yuborish", callback_data=json.dumps(data)))
        inline.append([inlinekeys[0], inlinekeys[1]])
        inlinemarkup=InlineKeyboardMarkup(inline)
        server_updater.bot.send_message(i[0], s, parse_mode='HTML', reply_markup=inlinemarkup)
    return final_waiting_phase(update, context)


def order_cart_confirm(update, context):
    s=tr('choose_action', context)
    keyboard=[]
    keyboard.append(["❌ "+tr('cancel', context), "💾 "+tr('save', context)])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(s, reply_markup=reply_markup)
    return ORDER_CART_CONFIRM_CHOICE



def getorder(update, order, ordered_products):
    s = ""
    if order[0]:
        s += 'Buyurtma raqami: ' + str(order[0]) +'\n'
    if order[1]:
        s += 'Buyurtmachining nomi: ' + str(order[1]) +'\n'
    if order[2]:
        s += 'Buyurtma sanasi: ' + str(order[2]) +'\n'
    if order[3]:
        s += 'Buyurtmachining telefon raqami: <b>' + order[3] +'</b>\n'
    if order[6]:
        s += 'Buyurtmachining manzili: <b>' + str(order[6]) +'</b>\n'
    s += '\n\n'
    s += 'Xarajatlar:\n'
    overall = 0
    for i in ordered_products:
        overall +=i[1]*i[2]
        s+=i[0]+': '+str(i[1])+' x '+str(remove_exponent(i[2]))+' = '+ str(remove_exponent(i[1]*i[2])) +' so\'m\n'
    s+='\n'
    s+="<b>Jami: "+str(remove_exponent(overall))+" so\'m</b>"
    return s    

def initial_waiting_phase(update, context):
    t=15
    s="Siz {} sekund ichida buyurtmani bekor qilishingiz mumkin.".format(str(t))
    s+='\n'
    context.user_data['cancel_order']=False
    mins, secs = divmod(t, 60)
    timeformat = '<b>{:02d}:{:02d}</b>'.format(mins, secs)
    oldtext = timeformat
    keyboard=[['❌ Bekor qilish']]
    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    kbdmsg = update.message.reply_text(s, reply_markup=reply_markup)
    msg = update.message.reply_html(timeformat)
    context.user_data['freeze_cancel_order']=False
    t1 = threading.Thread(target=countdown, args=(update, context, msg, t, oldtext, kbdmsg)) 
    t1.start()
    return ORDER_WAITING_INIT

    
def countdown(update, context, msg, t, oldtext, kbdmsg):
    while t:
        if context.user_data['cancel_order']:
            conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, request_category), None), context)
            return ORDER_CATEGORIES_CHOICE
        mins, secs = divmod(t-1, 60)
        timeformat = '<b>{:02d}:{:02d}</b>'.format(mins, secs)
        if timeformat!=oldtext:            
            msg.edit_text(timeformat)
            oldtext = timeformat
        time.sleep(1)
        t -= 1
    update.message.reply_text("Sizga uch daqiqa ichida xabar keladi.", reply_markup=ReplyKeyboardRemove())
    context.user_data['freeze_cancel_order']=True
    return save_order(update, context)
    #conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, save_order), None), context)
    return ORDER_WAITING_INIT
    

def stop_countdown(update, context):
    if context.user_data['freeze_cancel_order']:
        update.message.reply_text("Bekor qilish uchun kech bo'ldi")
    else:
        context.user_data['cancel_order']=True
        update.message.reply_text('Bekor qilindi')

def save_order(update, context):
    if context.user_data['acquired']:
        sql = "SELECT id from customers where userid=%s"
        data = (update.message.from_user.id, )
        result = db_execute_get_more(sql, data)
        if ('latitude' in context.user_data) and ('longitude' in context.user_data):
            sql = "INSERT into orders (customerid, longitude, latitude, orientation) VALUES (%s, %s, %s, %s)"
            data = (result[0][0], context.user_data['longitude'], context.user_data['latitude'], context.user_data['address'])
        elif ('orientation' in context.user_data):
            sql = "INSERT into orders (customerid, orientation) VALUES (%s, %s)"
            data = (result[0][0], context.user_data['orientation'])
        else:
            sql = "INSERT into orders (customerid) VALUES (%s)"
            data = (result[0][0])
        sql+=" RETURNING id"
        result = db_execute_get_more(sql, data, True)[0][0]
        if uzbek(context):
            sql = "INSERT into ordered_products (productid, value, orderid) VALUES ((SELECT id from products WHERE uzbek = %s), %s, %s)"
        elif russian(context):
            sql = "INSERT into ordered_products (productid, value, orderid) VALUES ((SELECT id from products WHERE russian = %s), %s, %s)"
        datas=[]
        for i in context.user_data['acquired']:
            data=(i[0], i[1], result)
            datas.append(data)
        db_execute_multi(sql, datas)
        sql = "SELECT orders.id as id, name, date, phone, longitude, latitude, orientation from orders \
left join customers on orders.customerid=customers.id \
WHERE orders.id=%s"
        data = (result, )
        order = db_execute_get_more(sql, data)[0]
        sql = "select (select uzbek from products where products.id = productid) as uzbek, value, (select price from products where products.id = productid) as price \
from ordered_products where orderid = %s"
        data = (result, )
        ordered_products = db_execute_get_more(sql, data)
        context.user_data['orderid']=order[0]
        s = getorder(update, order, ordered_products)
        sql = "SELECT userid from servers"
        users_to_send = db_execute_get_more(sql)
        inline=[]
        inlinekeys = []
        msg = []
        msg_countdown=[]
        locmsg = []
        data={}
        data['action']='iconfirm'
        data['id'] = order[0]
        data['userid'] = update.message.from_user.id
        inlinekeys.append(InlineKeyboardButton("💾 "+tr('save', context), callback_data=json.dumps(data)))
        data={}
        data['action']='icancel'
        data['id'] = order[0]
        data['userid'] = update.message.from_user.id
        inlinekeys.append(InlineKeyboardButton("❌ "+tr('cancel', context), callback_data=json.dumps(data)))
        inline.append([inlinekeys[0], inlinekeys[1]])
        inlinemarkup=InlineKeyboardMarkup(inline)
        context.user_data['freeze_go_main']=True
        l = len(users_to_send)
        for i in range(len(users_to_send)):
            user = users_to_send[i]
            if order[4] and order[5]:
                try:
                    locmsg.append(server_updater.bot.send_location(user[0], order[5], order[4]))
                except:
                    pass

            try:
                msg.append(server_updater.bot.send_message(user[0], s, parse_mode='HTML', reply_markup=inlinemarkup))
            except:
                l-=1
            t=25
            s="Sizda tasdiqlash uchun uch daqiqa vaqt bor:\n"
            mins, secs = divmod(t, 60)
            timeformat = '<b>{:02d}:{:02d}</b>'.format(mins, secs)
            oldtext = s+timeformat
            try:
                msg_countdown.append(server_updater.bot.send_message(user[0], oldtext, parse_mode='HTML'))
            except:
                pass
        t1 = threading.Thread(target=server_countdown, args=(update, context, msg_countdown, t, oldtext, msg, l, order[0])) 
        t1.start()
        return ORDER_WAITING_INIT
        
def server_countdown(update, context, msg_countdown, t, oldtext, msg, l, oid):
    while t:
        if (t%3==0 or t==1):
            initconf = int(db_execute_get_more('SELECT initial_confirmation from orders WHERE id=%s', (oid, ))[0][0])
            if initconf==0:
                conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, final_waiting_phase), None), context)
                return ORDER_WAITING_FINAL
            elif initconf==1:
                conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, continue_ordering), None), context)
                return ORDER_IN_WAY
        s="Sizda tasdiqlash uchun uch daqiqa vaqt bor:\n"
        mins, secs = divmod(t-1, 60)
        timeformat = '<b>{:02d}:{:02d}</b>'.format(mins, secs)
        if s+timeformat!=oldtext:
            for i in range(l):
                server_updater.bot.edit_message_text(message_id=msg_countdown[i].message_id, chat_id=msg_countdown[i].chat_id, text=s+timeformat)
                oldtext = s+timeformat
        time.sleep(1)
        t -= 1
    context.user_data['freeze_go_main']=False
    keyboard = [["⏮️ Boshiga qaytish"]]
    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("Buyurtmangiz bekor qilindi", reply_markup=reply_markup)
    server_updater.bot.edit_message_reply_markup(message_id=msg[i].message_id, chat_id=msg[i].chat_id)
    server_updater.bot.send_message(chat_id=msg[i].chat_id, text="{}-buyurtma bekor qilindi".format(str(oid)))
    return False
    
def stop_server_countdown(update, context):
    
    if 'freeze_go_main' in context.user_data:
        if context.user_data['freeze_go_main']:
            update.message.reply_text("Boshiga qayta olmaysiz")
        else:
            return main_choice(update, context)
    else:
        update.message.reply_text("Boshiga qayta olmaysiz")
        
    
def continue_ordering(update, context):
    sql = "SELECT orders.id as id, name, date, phone, longitude, latitude, orientation from orders \
left join customers on orders.customerid=customers.id \
WHERE orders.id=%s"
    data = (context.user_data['orderid'], )
    order = db_execute_get_more(sql, data)[0]
    sql = "select (select uzbek from products where products.id = productid) as uzbek, value, (select price from products where products.id = productid) as price \
from ordered_products where orderid = %s"
    data = (context.user_data['orderid'], )
    ordered_products = db_execute_get_more(sql, data)
    s = getorder(update, order, ordered_products)
    data={}
    data['action']='iconfirm'
    data['id'] = order[0]
    data['userid'] = update.message.from_user.id
    sql = "SELECT userid from couriers"
    users_to_send = db_execute_get_more(sql)
    for i in users_to_send:
        if order[4] and order[5]:
            courier_updater.bot.send_location(i[0], order[5], order[4])
        inline=[]
        inlinekeys = []
#        data={}
#        data['action']='icancel'
#        data['id'] = order[0]
#        data['userid'] = update.message.from_user.id
#        inlinekeys.append(InlineKeyboardButton("❌ "+tr('cancel', context), callback_data=json.dumps(data)))
        data={}
        data['action']='iconfirm'
        data['id'] = order[0]
        data['userid'] = update.message.from_user.id
        inlinekeys.append(InlineKeyboardButton("💾 "+tr('save', context), callback_data=json.dumps(data)))
#        inline.append([inlinekeys[0], inlinekeys[1]])
        inline.append([inlinekeys[0]])
        inlinemarkup=InlineKeyboardMarkup(inline)
        courier_updater.bot.send_message(i[0], s, parse_mode='HTML', reply_markup=inlinemarkup)
    return final_waiting_phase(update, context)


def cancel_ordering(update, context):
    sql = "SELECT userid from servers"
    users_to_send = db_execute_get_more(sql)
    s="Mijoz {}-buyurtmani bekor qildi".format(context.user_data['orderid'])
    for i in users_to_send:
        inline=[]
        inlinekeys = []
        inlinemarkup=InlineKeyboardMarkup(inline)
        server_updater.bot.send_message(i[0], s, parse_mode='HTML')
    update.message.reply_text("Bekor qilindi")    
    return main_choice(update, context)


    
def payme_waiting_phase(update, context):
    return ORDER_PAYME_CHOICE

def final_waiting_phase(update, context):
#    reply_markup = ReplyKeyboardMarkup([[tr('cancel', context)]],  resize_keyboard=True)
    return ORDER_IN_WAY

def continue_final_ordering(update, context):
    reply_markup = ReplyKeyboardMarkup([["Joylashuv", "Yetkazildi"]],  resize_keyboard=True)
    update.message.reply_text("Sizga mahsulotni yetkazish uchun xodimimiz yo'lga chiqmoqda, mahsulot joylashuvini tekshirish uchun 'Joylashuv' tugmasini bosing.\n\
Mahsulot yetkazilgandan so'ng, 'Yetkazildi' tugmasini bosing", reply_markup=reply_markup)        
    return ORDER_IN_WAY
    
def cancel_final_ordering(update, context):
    update.message.reply_text("Bekor qilindi")    
    return main_choice(update, context)

def send_courier_location(update, context):
    update.message.reply_location(41.3325132, 69.3047404)

def order_set_delivered(update, context):
    reply_markup = ReplyKeyboardMarkup([["⏮️ Boshiga qaytish"]],  resize_keyboard=True)
    update.message.reply_text("Xizmatimizdan foydalanganingiz uchun rahmat. Xizmatimiz haqida biror taklif-mulohazangiz bo'lsa, shu yerda qoldiring:", reply_markup=reply_markup)
    return ORDER_DELIVERED

def send_feedback(update, context):
    sql = "SELECT id, phone, name FROM customers WHERE userid=(%s)"
    cursor.execute(sql, (update.message.from_user.id, ))
    res = cursor.fetchall()
    s=""
    if (res[0][1]):
        s += 'Telefon raqami: '+res[0][1]
    else:
        s += 'Telefon raqami: '+ 'kiritilmagan'
    s+='\n'
    if (res[0][2]):
        s += 'Ismi: '+res[0][2]
    else:
        s += 'Ismi: '+'kiritilmagan'
    s+='\n'
    if update.message.from_user.username:
        s+="Logini: @"+update.message.from_user.username    
        s+='\n'    
    s+='Mulohaza: ' +update.message.text
    sql = "SELECT userid from admins"
    cursor.execute(sql)
    res = cursor.fetchall()
    for i in res:
        updater.bot.send_message(i[0], s)
    update.message.reply_text(tr('feedback_received', context))
    return main_choice(update, context)

def settings_choice(update, context):
    show_status(update, context)
    return SETTINGS_CHOICE

def show_status(update, context):
    sql = "SELECT id, phone, name, phone2 FROM customers WHERE userid=(%s)"
    data = (update.message.from_user.id, )
    cursor.execute(sql, data)
    res = cursor.fetchall()
    s=""
    if (res[0][1]):
        s += tr('your_phone', context)+' '+res[0][1]
    else:
        s += tr('your_phone', context)+' '+tr('not_entered', context)
    s+='\n'
    if (res[0][2]):
        s += tr('your_name', context)+' '+res[0][2]
    else:
        s += tr('your_name', context)+' '+tr('not_entered', context)
    s+='\n'
    if (res[0][3]):
        s += tr('your_second_phone', context)+' '+res[0][3]
    else:
        s += tr('your_second_phone', context)+' '+tr('not_entered', context)
    s+='\n'
    s+='\n'
    s+=tr('change_info', context)
    choice_keyboard = [['⬅️ '+tr('back', context)], ['📱 '+tr('phone_change', context)], ['📋 '+tr('name_change', context)], ['📱 '+tr('second_phone_change', context)], ['🌐 '+tr('language_change', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.message.reply_text(s, reply_markup=choice_markup)

def phone_settings_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📱 '+tr('phone_entering', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_PHONE_SETTINGS

def language_settings_choice(update, context):
    update.message.reply_text(tr('choose_lang', context), reply_markup=start_markup)
    return SAVING_LANGUAGE_SETTINGS

def name_settings_choice(update, context):
    update.message.reply_text(tr('name_enter', context))
    return SAVING_NAME_SETTINGS

def second_phone_settings_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📱 '+tr('phone_entering_no_sms', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_SECOND_PHONE_SETTINGS

def set_user_uzbek(update, context):
    context.user_data['lang']=0
    sql="UPDATE customers SET lang=0 WHERE userid=%s"
    data=(update.message.from_user.id, )
    cursor.execute(sql, data)
    return settings_choice(update, context)    

def set_user_russian(update, context):
    update.message.reply_text("Hali ruscha qilinmadi")
#    context.user_data['lang']=1
#    sql="UPDATE customers SET lang=1 WHERE userid=%s"
#    data=(update.message.from_user.id, )
#    cursor.execute(sql, data)
#    return settings_choice(update, context)

def set_user_name(update, context):
    text = update.message.text
    if len(text)>=256:
        update.message.reply_text(tr('too_long', context))
    else:
        sql = "UPDATE customers SET name = %s WHERE userid = %s"
        data = (text, update.message.from_user.id)
        cursor.execute(sql, data)
        return settings_choice(update, context)

def set_user_phone_auto(update, context):
    context.user_data['phone']=update.message.contact.phone_number
    return set_user_phone(update, context)

def set_user_phone_manual(update, context):
    context.user_data['phone']=update.message.text
    return set_user_phone(update, context)

def set_user_phone(update, context):
    sql = "UPDATE customers SET phone = %s WHERE userid = %s"
    data = (context.user_data['phone'], update.message.from_user.id)
    cursor.execute(sql, data)
    update.message.reply_text(tr('info_saved', context));
    return settings_choice(update, context)

def set_user_second_phone_auto(update, context):
    context.user_data['phone2']=update.message.contact.phone_number
    return set_user_second_phone(update, context)

def set_user_second_phone_manual(update, context):
    context.user_data['phone2']=update.message.text
    return set_user_second_phone(update, context)

def set_user_second_phone(update, context):
    sql = "UPDATE customers SET phone2 = %s WHERE userid = %s"
    data = (context.user_data['phone2'], update.message.from_user.id)
    cursor.execute(sql, data)
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
    sql = "SELECT id, phone, name FROM customers WHERE userid=(%s)"
    cursor.execute(sql, (update.message.from_user.id, ))
    res = cursor.fetchall()
    s=""
    if (res[0][1]):
        s += 'Telefon raqami: '+res[0][1]
    else:
        s += 'Telefon raqami: '+ 'kiritilmagan'
    s+='\n'
    if (res[0][2]):
        s += 'Ismi: '+res[0][2]
    else:
        s += 'Ismi: '+'kiritilmagan'
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
        NAME_CHOICE: [MessageHandler(Filters.text,
                            save_name),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            start),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            start),
                      MessageHandler(Filters.all, do_nothing)
                            ],
        PHONE_CHOICE: [MessageHandler(Filters.contact,
                            request_verify_phone_auto),
                      MessageHandler(Filters.regex('^\+998\d{9}$'),
                            request_verify_phone_manual),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            start),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            start),
                      MessageHandler(Filters.all, do_nothing)
                      ],
        VERIFY_PHONE_CHOICE: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            start),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            start),
                      MessageHandler(Filters.text,
                            verify_phone),
                      MessageHandler(Filters.all, do_nothing),
                            ],
        SECOND_PHONE_CHOICE: [MessageHandler(Filters.contact,
                            save_second_phone_auto),
                      MessageHandler(Filters.regex('^\+998\d{9}$'),
                            save_second_phone_manual),                            
                      MessageHandler(Filters.regex('^⏭️ O\'tkazib yuborish$'),
                            save_init_data),
                      MessageHandler(Filters.all, do_nothing)
        ],
        MAIN_CHOICE: [MessageHandler(Filters.regex('^🛎 Buyurtma$'),
                            request_location),
                      MessageHandler(Filters.regex('^⚙️ Sozlanmalar$'),
                            settings_choice),
                      MessageHandler(Filters.regex('^⚙️ Настройки$'),
                            settings_choice),
                      MessageHandler(Filters.regex('^ℹ️ Yordam$'),
                            help_choice),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            main_choice),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            main_choice),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_START_CHOICE:[
                      MessageHandler(Filters.location,
                            save_location),
                      MessageHandler(Filters.regex('^✍️ Joylashuvni qo\'lda ko\'rsatish$'),
                            request_manual_location),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            main_choice),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            main_choice),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_LOCATION_MANUAL_CHOICE: [
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  request_location),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  request_location),
                            MessageHandler(Filters.text,
                                  save_manual_location),
                            MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_MENU_CHOICE:[
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_location),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_location),
                      MessageHandler(Filters.text,
                            save_menu),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_PLACE_CHOICE:[
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_menu),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_menu),
                      MessageHandler(Filters.text,
                            save_place),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_CATEGORIES_CHOICE:[
                      MessageHandler(Filters.regex('^📥 Savatcha$'),
                            order_cart),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_place),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_place),
                      MessageHandler(Filters.text,
                            save_category),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_PRODUCTS_CHOICE:[
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_category),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_category),
                      MessageHandler(Filters.text,
                            save_product),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_PRODUCT_NUMBERS_CHOICE:[
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_product),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_product),
                      MessageHandler(Filters.text,
                            save_product_number),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_CART_CHOICE:[
                      CallbackQueryHandler(manage_acquired),        
                      MessageHandler(Filters.regex('^🚀 Buyurtma qilish$'),
                            request_order_pay_method),
                      MessageHandler(Filters.regex('^🚀 Сделать заказ$'),
                            request_order_pay_method),
                      MessageHandler(Filters.regex('^❌ O\'chirish$'),
                            order_clear_cart),
                      MessageHandler(Filters.regex('^❌ Очистить$'),
                            order_clear_cart),
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            request_category),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            request_category),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_PAY_METHOD_CHOICE:[
                      MessageHandler(Filters.regex('^💳 PayMe$'),
                            order_payme_choice),
                      MessageHandler(Filters.regex('^💰 Naqd$'),
                            order_cash_choice),
                      MessageHandler(Filters.all, do_nothing)
        ],       
        ORDER_PAYME_CHOICE:[
                      MessageHandler(Filters.text,
                            payme_waiting_phase),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_CART_CONFIRM_CHOICE:[
                      MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                            main_choice),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                            main_choice),
                      MessageHandler(Filters.regex("💾 Tasdiqlash"),
                            initial_waiting_phase),
                      MessageHandler(Filters.regex("❌ Bekor qilish"),
                            request_category),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_WAITING_INIT:[
                      MessageHandler(Filters.regex("❌ Bekor qilish"),
                            stop_countdown),
                      MessageHandler(Filters.regex('^⏮️ Boshiga qaytish$'),
                            stop_server_countdown),
                      MessageHandler(Filters.all, do_nothing)
        ],
        
        ORDER_WAITING_FINAL:[
 #                     MessageHandler(Filters.regex("^Davom etish$"),
 #                           continue_final_ordering),
 #                     MessageHandler(Filters.regex("^Bekor qilish$"),
#                            cancel_final_ordering),
                      MessageHandler(Filters.regex("^⏮️ Boshiga qaytish$"),
                            main_choice),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_IN_WAY:[
                      MessageHandler(Filters.regex("^🚗 Joylashuv$"),
                            send_courier_location),
#                      MessageHandler(Filters.regex("^Yetkazildi$"),
#                            order_set_delivered),
                      MessageHandler(Filters.regex('^⏮️ Boshiga qaytish$'),
                            main_choice),
                      MessageHandler(Filters.all, do_nothing)
        ],
        ORDER_DELIVERED:[
                      MessageHandler(Filters.text,
                            send_feedback),
                      MessageHandler(Filters.regex('^Boshiga qaytish$'),
                            main_choice),
                      MessageHandler(Filters.all, do_nothing)
        
        ],
        SETTINGS_CHOICE:[
                   MessageHandler(Filters.regex('^📱 Telefon raqamini o\'zgartirish$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^📱 Изменить номер телефона$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^📋 Ismni o\'zgartirish$'),
                                  name_settings_choice),
                   MessageHandler(Filters.regex('^📋 Изменить имя$'),
                                  name_settings_choice),
                   MessageHandler(Filters.regex('^📱 Ikkinchi telefonni o\'zgartirish$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^📱 Изменить второй телефон$'),
                                  phone_settings_choice),
                   MessageHandler(Filters.regex('^🌐 Tilni o\'zgartirish$'),
                                  language_settings_choice),
                   MessageHandler(Filters.regex('^🌐 Изменить язык$'),
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
           MessageHandler(Filters.contact, 
                      set_user_phone_auto),
           MessageHandler(Filters.regex('^\+998\d{9}$'),
                      set_user_phone_manual),
           MessageHandler(Filters.all, do_nothing)],
        SAVING_LANGUAGE_SETTINGS: [
            MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
                                  set_user_uzbek),
            MessageHandler(Filters.regex('^🇷🇺 Русский'),
                            set_user_russian),
            MessageHandler(Filters.all, do_nothing)
        ],
        SAVING_NAME_SETTINGS: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      settings_choice),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      settings_choice),
           MessageHandler(Filters.text, set_user_name),
           MessageHandler(Filters.all, do_nothing)
        ],
        SAVING_SECOND_PHONE_SETTINGS: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      settings_choice),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      settings_choice),
           MessageHandler(Filters.contact, 
                      set_user_second_phone_auto),
           MessageHandler(Filters.regex('^\+998\d{9}$'),
                      set_user_second_phone_manual),
           MessageHandler(Filters.all, 
                      do_nothing)
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
                                      send_to_admin),
                       MessageHandler(Filters.all, do_nothing)
        ],
    },
    fallbacks=[MessageHandler(Filters.regex('^Done$'), cancel)],
    allow_reentry = True)
dp.add_handler(conv_handler)
dp.add_handler(MessageHandler(Filters.all, echo))
dp.add_error_handler(error)
updater.start_polling()
updater.idle()

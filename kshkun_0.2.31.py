import asyncio, json, random, pycountry, os
from datetime import datetime, timedelta, timezone

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from pyrogram import Client
from pyrogram.enums import ChatType, MessageEntityType, PollType, ChatMembersFilter
from pyrogram.types import (CallbackQuery, InputMediaPhoto, Message, Chat, InlineQuery,
                            InlineKeyboardMarkup as InKeMark, InlineKeyboardButton as InKeBut, InlineQueryResultArticle as InQuResArt,
                            InputTextMessageContent as InpTxtMsgCont)
from pyrogram.raw.types import UpdateMessagePollVote

from io import BytesIO

from kshkun_modules.react_checker import ReactChecker
from kshkun_modules.logger import KshkunLogger as klog
from kshkun_modules.data_handler import SimpleDataHandler as sdhandler
from kshkun_modules.network_handler import NetworkHandler as nethandler
from kshkun_modules.database_handler import DatabaseHandler as dbhandler
from kshkun_modules.predator_handler import PredatorHandler as predhandler
from kshkun_modules.duzhocoin_handler import DuzhocoinHandler as dcoinhandler
from kshkun_modules.menstra_handler import MenstruationHandler as menstrhandler
from kshkun_modules.genai_files_handler import KshkunGenaiFilesHandler as kgfhandler

from kshkun_types.quiz import Quiz

class QuizHandler:
    def __init__(self):
        pass

class KshkunCommand:
    def __init__(self, keywords, func, args, condition):
        self.keywords = keywords
        self.func = func
        self.args = args
        self.condition = condition

class Kshkun:
    def __init__(self, app: Client, kshkun_username: str, base_sys_prompt: str):
        pass

KSHKUN_CREDENTIALS = {}
SERVICES_API = {}
ACCOUNT_IDS = {}

app = None
checker_app = None

KSHKUN_USERNAME = "duzhochatbot"

BASE_SYS_PROMPT = ''
BASE_CUSTOM_SYS_PROMPT = ''

REQUESTS_LAST_TIMESTAMP = datetime.now().replace(second=0, microsecond=0)
REQUESTS_THIS_MINUTE = 0
TOKENS_THIS_MINUTE = 0

WHITELIST = []
PENDING_GEN_UIDS = [] #image generation, currently unused due to the lack of API (closed down)
PENDING_VERIFICATION_CHANNEL_IDS = []
TEMPBAN_UIDS = [] #unused
QUIZZES_QUEUE = []
PERSONA_QUEUE = []

MOBYK_PENDING = []
MOBYK_WORKER_TASK = None
MOBYK_QUEUE = asyncio.Queue()

MAGAHAT_PENDING = []
MAGAHAT_WORKER_TASK = None
MAGAHAT_QUEUE = asyncio.Queue()

POLLS_DATA = {}
PENDING_DUZHOCOINS_SEND_FOR_CHANNELS = {}
LINKED_CHAT_BUFFER = {}
TRIGGER_GIFS = {}
PASKHALOCHKY = {}
LINKS = {}

ACCEPT_UNI_MEDIA = False
ACCEPT_PREDATOR_MESSAGES = False

MENSTRAHANDLER = menstrhandler("menstra_desc.json")

async def loadGlobals():
    await klog.log('Loading globals...')
    global KSHKUN_CREDENTIALS, SERVICES_API
    global INIT_CHAT_IDS
    global ACCOUNT_IDS
    global WHITELIST
    global BASE_SYS_PROMPT
    global BASE_CUSTOM_SYS_PROMPT
    global TRIGGER_GIFS
    global PASKHALOCHKY
    global LINKS
    global app, checker_app

    sdh = sdhandler()

    BASE_SYS_PROMPT = await sdh.handleData('base_sys_prompt.txt')
    TRIGGER_GIFS = await sdh.handleData('gifs.json')
    PASKHALOCHKY = await sdh.handleData('paskhalochky.json')
    BASE_CUSTOM_SYS_PROMPT = await sdh.handleData('base_custom_sys_prompt.txt')
    
    data = await sdh.handleData('init.json')
    if not data:
        return

    INIT_CHAT_IDS = data.get("CHAT_IDS", {})
    ACCOUNT_IDS = data.get("ACCOUNT_IDS", {})
    KSHKUN_CREDENTIALS = data.get("KSHKUN_CREDENTIALS", {})
    checkerAccCredentials = data.get("CHECKER_ACC_CREDENTIALS", {})
    SERVICES_API = data.get("SERVICES_API", {})
    LINKS = data.get("LINKS", {})
    WHITELIST = list(INIT_CHAT_IDS.values())

    app = Client(name="kshkun", api_id=KSHKUN_CREDENTIALS.get("id", ''), api_hash=KSHKUN_CREDENTIALS.get("hash", ''), bot_token=KSHKUN_CREDENTIALS.get("token", ''))
    checker_app = ReactChecker(pnumber=checkerAccCredentials.get("pnumber", ''), id=checkerAccCredentials.get("id", ''), hash=checkerAccCredentials.get("hash", ''), counter=-1, sleepTime=1800, emojisRequired=8, maxCounterCheck=7, chatPosting=INIT_CHAT_IDS.get("NNKNHT", 0), chatStorage=INIT_CHAT_IDS.get("MEME_STORAGE", 0), chatDraftStorage=INIT_CHAT_IDS.get("DRAFT_MEME_STORAGE", 0), admin=ACCOUNT_IDS.get("DUZHO", 0), kshkunInstance=app)

    await klog.log('Loaded global variables')
    return app


async def constructSysPrompt(**kwargs):
    template_filename = kwargs.get('template_filename')
    sdh = sdhandler()
    template = await sdh.handleData(template_filename)
    if template is None:
        await klog.log(f"COULD NOT LOAD TEMPLATE FROM FILE {template_filename}", 'ERROR')
        return None
    
    uid = kwargs.get('uid')
    if uid:
        custom_sys_prompt = await getCustomSysPrompt(uid)
        template = template.replace('{custom_sys_prompt}', custom_sys_prompt)

    try:
        if uid:
            del kwargs['uid']
        if template_filename:
            del kwargs['template_filename']

        for key, value in kwargs.items():
            template = template.replace('{' + key + '}', f'{value}')

        return template

    except Exception as e:
        await klog.log(f"TEMPLATE FORMATTING ERROR: {e}", "ERROR")
        return None
    

async def getCustomSysPrompt(uid):
    dbh = dbhandler()
    user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f"GET CUSTOM SYS PROMPT LOADING USER {uid} ERROR: {err}", "ERROR")
        return None

    custom_sys_prompt = user.get('custom_system_prompt', '') or BASE_SYS_PROMPT
    return custom_sys_prompt


async def requestGemini(sys_prompt, prompt='', media_ids=None, unique_media_ids=None, max_output_tokens=1000, response_mime_type="text/plain", response_schema=None, model_name="gemini-2.0-flash"):
    global REQUESTS_THIS_MINUTE, REQUESTS_LAST_TIMESTAMP, TOKENS_THIS_MINUTE                                                                               # "gemini-1.5-flash"
    if datetime.now() > REQUESTS_LAST_TIMESTAMP + timedelta(minutes=1):
        REQUESTS_THIS_MINUTE = 0
        TOKENS_THIS_MINUTE = 0
        REQUESTS_LAST_TIMESTAMP = datetime.now().replace(second=0, microsecond=0)
        await klog.log(f'Gemini Requests reset')

    REQUESTS_THIS_MINUTE += 1
    debug = True
    if media_ids == None:
        media_ids = {'photos': [], 'animations': [], 'stickers': {'static': [], 'video': []}, 'audio': []}

    if debug:
        await klog.log(f"SYS: {sys_prompt[:45]}")
        await klog.log(f"USER: {prompt[:45]}")

    api_key = SERVICES_API.get('gemini_api_key', '')
    genai.configure(api_key=api_key)

    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={"temperature": 0.95, "top_p": 0.95, "top_k": 40, "max_output_tokens": max_output_tokens, "response_mime_type": response_mime_type, "response_schema": response_schema},
        safety_settings=safety_settings,
        system_instruction=sys_prompt
    )

    try:
        gfh = kgfhandler(KSHKUN_CREDENTIALS.get('token'))
        all_uploaded_files = await gfh.uploadAllMediaToGemini(media_ids, unique_media_ids)
        if all_uploaded_files and not prompt:
            prompt = 'Describe the media provided'

        input_data = all_uploaded_files + [prompt] if prompt else all_uploaded_files or "."
        response = await model.generate_content_async(input_data)
        try: 
            response_text = response.text.strip()
            TOKENS_THIS_MINUTE += response.usage_metadata.total_token_count
        except:
            await klog.log(f"GEMINI REQUEST ERROR: {response}", 'ERROR')
            raise Exception('gemini failed')

        if debug:
            if all_uploaded_files:
                await klog.log(f"UPLOADED FILES: {all_uploaded_files}")
            await klog.log(f'KSHKUN: {response_text[:45]}')
            await klog.log(f"In/Out/Total: {response.usage_metadata.prompt_token_count}/{response.usage_metadata.candidates_token_count}/{response.usage_metadata.total_token_count}, Tokens/Requests/min: {TOKENS_THIS_MINUTE}/{REQUESTS_THIS_MINUTE}")

        return response_text

    except Exception as e:
        await klog.log(f"GEMINI_REQUEST ERROR: {e}", 'ERROR')
        return "помилочка."


async def getKeyboard(i: int, uid: int):
    return (InKeMark([[InKeBut("🇺🇦", f"ua_{uid}"), InKeBut("🇷🇺", f"wrong{i}_{uid}")], [InKeBut("🇹🇷", f"wrong{i}_{uid}"), InKeBut("🇬🇷", f"wrong{i}_{uid}")]]))


async def getClock(time):
    clocks = {1: {0: "🕐", 1: "🕜"}, 2: {0: "🕑", 1: "🕝"}, 3: {0: "🕒", 1: "🕞"}, 4: {0: "🕓", 1: "🕟"}, 5: {0: "🕔", 1: "🕠"}, 6: {0: "🕕", 1: "🕡"},
              7: {0: "🕖", 1: "🕢"}, 8: {0: "🕗", 1: "🕣"}, 9: {0: "🕘", 1: "🕤"}, 10: {0: "🕙", 1: "🕥"}, 11: {0: "🕚", 1: "🕦"}, 12: {0: "🕛", 1: "🕧"}}
    return clocks[time.hour % 12 or 12][(time.minute // 30)]


async def getWeather(cli: Client, msg: Message, text_lower: str):
    city = text_lower.replace('кшкун погода', '').strip()
    if not city:
        return await replyTempMsg(cli, msg, 'треба назву міста.')
    
    api_key = SERVICES_API.get('weather_api_key', '')
    nh = nethandler()
    data, err = await nh.aiohttpGet(f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ua')
    if err != None:
        await klog.log(f"GET WEATHER ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, 'ой.. сталася якась помилочка')

    if not data:
        return await replyTempMsg(cli, msg, f'ой.. кшкун не знайшов прогноз погоди для міста {city}')

    tz = data['timezone']

    local_t = datetime.now(timezone.utc) + timedelta(seconds=tz)
    clock = await getClock(local_t)

    sunrise = (datetime.fromtimestamp(data['sys']['sunrise'], tz=timezone.utc) + timedelta(seconds=tz)).strftime('%H:%M')
    sunset = (datetime.fromtimestamp(data['sys']['sunset'], tz=timezone.utc) + timedelta(seconds=tz)).strftime('%H:%M')

    city_name = data['name']

    country_code = data['sys']['country'] if not city_name in ['Sudzha', 'Kursk', 'Belgorod'] else 'UA'
    if country_code == 'RU':
        country = random.choice(['блинолопатна скотоублюдія', 'свинособачий хуйлостан', 'нафтодирне пинєбабве', 'підорашка'])
    else:
        country = pycountry.countries.get(alpha_2=country_code).name

    flag = ''.join(chr(ord(l) + 127397) for l in country_code)
    local_time = local_t.strftime('%H:%M')
    weather_description = data['weather'][0]['description'].capitalize()
    temperature = data['main']['temp']
    feels = data['main']['feels_like']
    humidity = data['main']['humidity']
    pressure = data['main']['pressure']
    wind_speed = data['wind']['speed']

    weather = (f"{flag} **{city_name}** ({country}):\n"
               f"{clock} **Місцевий час**: {local_time}(UTC{int(tz / 3600):+d})\n\n"
               f"🌤️ **{weather_description}**\n"
               f"🌡️ **{temperature}°C**(відчувається як {feels}°C)\n"
               f"💧 **Вологість**: {humidity}%\n"
               f"🌀 **Тиск**: {pressure} гПа\n"
               f"💨 **Вітер**: {wind_speed} м/с\n\n"
               f"🌇 **Схід -** 🌃 **Захід сонця**:\n{sunrise} - {sunset}")
    
    lat = data['coord']['lat']
    lon = data['coord']['lon']

    await msg.reply_location(latitude=lat, longitude=lon)
    await msg.reply(weather)    


async def findAddress(cli: Client, msg: Message, text_lower: str):
    address = text_lower.replace('кшкун мапа', '').strip()
    if not address:
        return await replyTempMsg(cli, msg, 'ну і яка адреса')
    
    api_key = SERVICES_API.get('map_search_api_key', '')
    nh = nethandler()
    result, err = await nh.aiohttpGet(f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json?access_token={api_key}&limit=5")
    if err != None:
        await klog.log(f"MAP SEARCH ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, 'ой.. сталася якась помилочка')

    if not result or not result.get('features'):
        return await replyTempMsg(cli, msg, f'ой.. кшкун не знайшов нічого за адресою {address}')

    message = f"{address}\n"
    for ftr in result['features']:
        place_type = ', '.join(ftr.get('place_type', []))
        coords = ftr['geometry']['coordinates']
        lon, lat = coords[0], coords[1]
        properties = ftr.get('properties', {})
        category = properties.get('category') or 'невідомо'
        short_code = properties.get('short_code') or 'невідомо'
        is_landmark = 'так' if properties.get('landmark') else 'ні'
        
        message += (f"\n📍 **Назва місця:** {ftr['place_name']}"
                    f"\n   - **Тип:** {place_type}"
                    f"\n   - **Координати:** {lat}, {lon}"
                    f"\n   - **Категорія:** {category}" 
                    f"\n   - **Короткий код:** {short_code}" 
                    f"\n   - **Визначне місце**: {is_landmark}"
                    f"\n\n" 
                    )

    await msg.reply(message)


async def sendKshk(cli: Client, chat_id: int, msg_id: int=None):
    sdh = sdhandler()
    media_json = await sdh.handleData('media_ids.json')
    media = random.choice(media_json)
    media_id = media["media_id"]
    functions = {
        'photo': cli.send_photo, 
        'animation': cli.send_animation, 
        'video': cli.send_video
        }
    function = functions[media["media_type"]]
    return await function(chat_id, media_id, reply_to_message_id=msg_id)


async def extractFullName(data):
    if isinstance(data, Message):
        sender = data.from_user if data.from_user else data.sender_chat
    else:
        sender = data

    try:
        name = sender.title
    except:
        name = (sender.first_name + ' ' + sender.last_name) if sender.last_name else sender.first_name

    return name


async def extractUid(data):
    if isinstance(data, Message) or isinstance(data, InlineQuery) or isinstance(data, CallbackQuery):
        sender = data.from_user if data.from_user else data.sender_chat
    else:
        sender = data

    try:
        uid = sender.id
    except:
        await klog.log(f'FAILED TO EXTRACT UID: {data}', 'ERROR')
        uid = None

    return uid


async def handleNnknhtChat(cli: Client, msg: Message, uid: int, u_verified: bool, text_lower: str, verified_uids: list):
    url_types = [MessageEntityType.URL, MessageEntityType.TEXT_LINK, MessageEntityType.MENTION]
    has_link = ((msg.entities and any(ent.type in url_types for ent in msg.entities)) or
                (msg.caption_entities and any(ent.type in url_types for ent in msg.caption_entities)))

    if not u_verified and has_link:
        if msg.from_user:
            reply_msg = await msg.reply(text='❌ ти не можеш слати силочки', reply_markup=InKeMark([[InKeBut("Я не ботик", callback_data=f'verify_{uid}')]]))
        else:
            reply_msg = await msg.reply(text='❌ канальчик, ти не можеш слати силочки. для верифікації пиши "`крим україна`"(натисни щоб скопіювати). напишеш щось інше - бан.')
            PENDING_VERIFICATION_CHANNEL_IDS.append(uid)

        await cli.delete_messages(msg.chat.id, msg.id)
        await asyncio.sleep(300)
        await cli.delete_messages(reply_msg.chat.id, reply_msg.id)

    elif uid in PENDING_VERIFICATION_CHANNEL_IDS:
        if text_lower.strip() == 'крим україна':
            verified_uids.append(uid)
            sdh = sdhandler()
            await sdh.handleData('verified_users.json', verified_uids)
            await msg.reply('✅ ми успішно підтвердили, що ви не маскалик')
        else:
            await msg.reply("⛔ мут бан 2000 днів, пака пака. Апеляція на розбан: @nnknht_bot")
            await cli.ban_chat_member(chat_id=msg.chat.id, user_id=uid)
            await cli.delete_messages(msg.chat.id, msg.id)

        PENDING_VERIFICATION_CHANNEL_IDS.remove(uid)

    elif msg.forward_from_chat and msg.forward_from_chat.is_restricted:
        nnknht_chat = INIT_CHAT_IDS.get("NNKNHT_CHAT", 0)
        nnknht = INIT_CHAT_IDS.get("NNKNHT", 0)

        copied_msg = await cli.copy_message(chat_id=nnknht_chat, from_chat_id=nnknht_chat, reply_to_message_id=msg.id, message_id=msg.id)
        restrictions = msg.forward_from_chat.restrictions
        channel_name = msg.forward_from_chat.title
        channel_username = msg.forward_from_chat.username if msg.forward_from_chat.username else None
        display_channel_name = f'[{channel_name}](https://t.me/{channel_username})' if channel_username else channel_name
        reasons_text = f"канал {display_channel_name} заблоковано на:\n" + "\n".join(f"{restr.platform}: '{restr.reason}'" for restr in restrictions)
        tg_download_link_text = "щоб бачити заблоковані повідомлення, на андроїді можна [скачати тг з оф. сайту](https://telegram.org/apps) замість гуглплею"
        
        await copied_msg.reply(f"{reasons_text}\n\n{tg_download_link_text}")
        await cli.send_message(nnknht, '⬆️ заблоковане повідомлення в коментах.')


async def sendRusniaGif(cli: Client, msg: Message, uid: int, u_verified: bool, all_txt_lower: str):
    all_gifs = TRIGGER_GIFS
    if any(ch in all_txt_lower for ch in ['ъ', '🇷🇺']):
        gifs_to_choose_from = list(all_gifs.values())  
    else:
        gifs_to_choose_from = [an for ch, an in all_gifs.items() if ch in all_txt_lower]

    gif = random.choice(gifs_to_choose_from)
    caption = await predhandler.getPredatorMsg(max_length=200)
    markup = None
    nnknht_chat = INIT_CHAT_IDS.get("NNKNHT_CHAT", 0)
    if msg.chat.id == nnknht_chat and not u_verified:
        if msg.from_user:
            markup = InKeMark([[InKeBut("я не маскалик", callback_data=f'verify_{uid}')]])
        else:
            caption = 'канальчик, для верифікації пиши "`крим україна`"(натисни щоб скопіювати)'
            PENDING_VERIFICATION_CHANNEL_IDS.append(uid)
    await msg.reply_animation(gif, caption=caption, reply_markup=markup)


async def checkApology(cli: Client, msg: Message, uid: int, text_lower: str): #currently unused
    if not text_lower == "кшкун вибач":
        TEMPBAN_UIDS.remove(uid)
        await replyTempMsg(cli, msg, "ладно. кшкун тебе вибачає.")


async def processMedia(cli: Client, msg: Message, process_msg: Message):
    media_ids = {'photos': [], 'animations': [], 'stickers': {'static': [], 'video': []}, 'audio': []}
    media_types = []
    unique_media_ids = {}
    if process_msg.photo:
        try:
            grouped_media_msgs = await cli.get_media_group(process_msg.chat.id, process_msg.id)
            for m in grouped_media_msgs:
                media_ids['photos'].append(m.photo.file_id)
                unique_media_ids[m.photo.file_id] = m.photo.file_unique_id
        except ValueError:
            media_ids['photos'].append(process_msg.photo.file_id)
            unique_media_ids[process_msg.photo.file_id] = process_msg.photo.file_unique_id

        media_types.append('photo')

    elif process_msg.animation:
        media_ids['animations'].append(process_msg.animation.file_id)
        unique_media_ids[process_msg.animation.file_id] = process_msg.animation.file_unique_id
        media_types.append('GIF')

    elif process_msg.sticker:
        if process_msg.sticker.is_animated:
            return await replyTempMsg(cli, msg, "кшкун поки не підтримує анімовані стікери")
        elif process_msg.sticker.is_video:
            media_ids['stickers']['video'].append(process_msg.sticker.file_id)
        else:
            media_ids['stickers']['static'].append(process_msg.sticker.file_id)
        
        unique_media_ids[process_msg.sticker.file_id] = process_msg.sticker.file_unique_id
        media_types.append('sticker')

    elif process_msg.audio:
        if process_msg.audio.file_size > 15 * 1024 * 1024:
            return await replyTempMsg(cli, msg, "максимальний розмір аудіо - 15 Мб")
        
        media_ids['audio'].append(process_msg.audio.file_id)
        unique_media_ids[process_msg.audio.file_id] = process_msg.audio.file_unique_id
        media_types.append('audio')

    return media_ids, media_types, unique_media_ids


async def scanImgGifSticker(cli: Client, msg: Message, uid: int, full_name: str, reply_in_msg: Message, text_lower: str):
    msg_to_process = msg if msg.photo or msg.animation or msg.sticker else reply_in_msg
    if not msg_to_process or not (msg_to_process.photo or msg_to_process.animation or msg_to_process.sticker):
        return await replyTempMsg(cli, msg, "кшкун не бачить фоточку/гіфочку/стікерочку")

    media_ids, media_types, unique_media_ids = await processMedia(cli, msg, msg_to_process)

    prompt = (text_lower or "").replace("кшкун скан", "").strip()
    sys_prompt = await constructSysPrompt(uid=uid, template_filename='scan_img_sys_prompt.txt', full_name=full_name, media_types=media_types)

    await msg.reply(await requestGemini(sys_prompt=sys_prompt, prompt=prompt, media_ids=media_ids, unique_media_ids=unique_media_ids))


async def getSearchResults(query: str, max_results: int = 5): # might remove and use gemini's google search instead
    api_key = SERVICES_API.get('google_api_key', '')
    cse_id = SERVICES_API.get('google_cse_id', '')
    nh = nethandler()
    err = None
    s_results, err = await nh.aiohttpGet(f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={query}&num={max_results}")
    if err != None:
        await klog.log(f"getSearchResults getting search results error: {err}", 'ERROR')
        return None, None, err
    
    if not s_results or not s_results.get('items'):
        return None, None, err
    
    google_results = []
    for item in s_results['items']:
        google_results.append((item['title'], item['snippet'], item['link']))

    crawled_content, err = await nh.fetchCrawledContent(s_results)
    if err != None:
        await klog.log(f"getSearchResults crawling and processing links error: {err}", 'ERROR')
        return google_results, None, err
    
    return google_results, crawled_content, err


async def searchGoogle(cli: Client, msg: Message, uid: int, full_name: str, text_lower: str):
    query = text_lower.replace('кшкун загугли', '').strip()
    if not query:
        return await replyTempMsg(cli, msg, "ну і що шукати")
    
    google_results, crawled_content, err = await getSearchResults(query)
    if err != None:
        await klog.log(f"SEARCH_GOOGLE ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка")
    
    if not google_results and not crawled_content:
        return await replyTempMsg(cli, msg, f"ой.. кшкун нічого не знайшов за запитом {query}")

    sys_prompt = await constructSysPrompt(uid=uid, template_filename='google_search_sys_prompt.txt', full_name=full_name, google_results=google_results, crawled_content=crawled_content)
    await msg.reply(await requestGemini(sys_prompt=sys_prompt, prompt=text_lower))


async def handleRuLosses(cli: Client, msg: Message):
    nh = nethandler()
    yesterdayData, thisMonthData, legend, err1, err2 = await nh.getRuLosses()

    if err1 != None:
        await klog.log(f"KSHKUN_RU_LOSSES ERROR: {err1}", 'ERROR')

    if err2 != None:
        await klog.log(f"KSHKUN_RU_LOSSES ERROR: {err2}", 'ERROR')

    if not yesterdayData and not thisMonthData:
        await klog.log(f"KSHKUN_RU_LOSSES ERROR: NO DATA", 'ERROR')
        return await msg.reply("нема інформації.")

    if not yesterdayData:
        yesterdayData = {key: 'нема інформації' for key in legend}

    if not thisMonthData:
        thisMonthData = {key: 'нема інформації' for key in legend}
        
    message_lines = [
        f"{legend.get(key, key)}: {value} / {thisMonthData.get(key, 'нема інформації')}"
        for key, value in yesterdayData.items()
    ]

    await msg.reply(f"втрати росіської педерастії за вчора/цей місяць:\n\n" + "\n".join(message_lines))


async def talk(cli: Client, msg: Message, uid: int, reply_to_kshkun: bool, reply_in_msg: Message, full_name: str, text_lower: str):
    sys_instr_dict = {}
    sys_instr_dict['model_configuration'] = BASE_CUSTOM_SYS_PROMPT
    sys_instr_dict['additional_custom_user_preference'] = await getCustomSysPrompt(uid)
    sys_instr_dict['messages_structure'] = []

    menstrual_cycle_state, err = await MENSTRAHANDLER.getCurrentMenstruationStage(uid)
    await klog.log(f"Current menstrual cycle state: {menstrual_cycle_state}")
    if err != None:
        await klog.log(f"ERROR WHILE GETTING MENSTRUAL CYCLE STATE IN TALKING: {err}", "ERROR")

    day, err = await MENSTRAHANDLER.getMenstrualCycleDay(uid)
    if err != None:
        await klog.log(f"ERROR WHILE GETTING MENSTRUAL CYCLE DAY IN TALKING: {err}", "ERROR")
        day = "not specified"

    if menstrual_cycle_state:
        new_dict = {"name": menstrual_cycle_state["name"]["en"], "day": day, "description": menstrual_cycle_state["description"]["en"]}
        sys_instr_dict['model_configuration'] += f" The user currently is expiriencing the following ovulation cycle stage: {new_dict}"
        await klog.log(f"Full model config: {sys_instr_dict['model_configuration']}")

    if reply_in_msg:
        reply_text = reply_in_msg.text or reply_in_msg.caption or None
        name_in_reply = 'model' if reply_to_kshkun else (await extractFullName(reply_in_msg))

        sys_instr_dict['messages_structure'].append({'message_id': 1, 'from': name_in_reply, 'reply_to_message_id': None, 'text': reply_text})
        sys_instr_dict['messages_structure'].append({'message_id': 2, 'from': full_name, 'reply_to_message_id': 1, 'text': text_lower})
    else:
        sys_instr_dict['messages_structure'].append({'message_id': 1, 'from': full_name, 'text': text_lower})

    sys_prompt = f'{sys_instr_dict}'
    prompt = text_lower or 'None'
    
    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt)
    if '<STOP>' in response:
        TEMPBAN_UIDS.append(uid)
        response = response.replace("<STOP>", "").strip()
        await klog.log(f"APPENDED TEMPBANNED USERS {TEMPBAN_UIDS} WITH {uid}")

    await msg.reply(f'{response}')


async def handleCustomPrompts(cli: Client, msg: Message, uid: int, reply_in_msg: Message, text_lower: str):
    new_custom_prompt = text_lower.replace("кшкун промпт", "").strip()
    if len(new_custom_prompt) > 4000:
        return await replyTempMsg(cli, msg, 'довжина промпту не може перевищувати 4000 символів')
    
    dbh = dbhandler()
    user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f"HANDLE_CUSTOM_PROMPTS LOADING USER {uid} ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, 'якась при завантаженні датабази.')

    if new_custom_prompt:
        user['custom_system_prompt'] = new_custom_prompt
        data_saved, err = await dbh.saveUserInDb(user)
        if err != None:
            await klog.log(f"HANDLE_CUSTOM_PROMPTS SAVING USER {uid} ERROR: {err}", 'ERROR')
            return await replyTempMsg(cli, msg, 'якась помилочка при збереженні датабази.')
        
        text = f'встановлено новий промпт: {new_custom_prompt}' if data_saved == None else data_saved # huh?
    else:
        if reply_in_msg:
            uid_in_reply = await extractUid(reply_in_msg)
            user_in_reply, err = await dbh.loadInitializeOrUpdateUser(uid_in_reply)
            if err != None:
                await klog.log(f"HANDLE_CUSTOM_PROMPTS LOADING REPLY USER {uid_in_reply} ERROR: {err}", 'ERROR')
                return await replyTempMsg(cli, msg, 'якась помилочка при завантаженні датабази.')
            
            user_in_reply_prompt = user_in_reply.get('custom_system_prompt') if user_in_reply and user_in_reply.get('custom_system_prompt') else 'не встановлено'
            text = f'промпт юзера в реплаї: `{user_in_reply_prompt}`'
        else:
            previous_prompt = user.get('custom_system_prompt') if user and user.get('custom_system_prompt') else 'не встановлено'
            text = f'промпт: {previous_prompt}'

    await replyTempMsg(cli, msg, text)


async def resetCustomPrompt(cli: Client, msg: Message, uid: int):
    dbh = dbhandler()
    user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f"RESET_CUSTOM_PROMPT LOADING USER {uid} ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, 'якась помилочка при завантаженні датабази.')

    if not user or not user.get('custom_system_prompt'):
        return await replyTempMsg(cli, msg, 'промпт не встановлений')

    user['custom_system_prompt'] = ''
    data_saved, err = await dbh.saveUserInDb(user)
    if err != None:
        await klog.log(f"RESET_CUSTOM_PROMPT SAVING USER {uid} ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, 'якась помилочка при збереженні датабази.')
    
    await replyTempMsg(cli, msg, 'промпт змінено на дефолтний' if data_saved == None else data_saved)


async def MagaHatWorker():
    global MAGAHAT_WORKER_TASK
    global MAGAHAT_QUEUE
    try:
        while True:
            try:
                task = await asyncio.wait_for(MAGAHAT_QUEUE.get(), timeout=300)
            except asyncio.TimeoutError:
                break

            file_data = task['file_data']
            future = task['future']
            proc = await asyncio.create_subprocess_exec(
                'python3', 'kshkun_modules/face_detect.py',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await klog.log(f"Magahat worker invoked. PID: {proc.pid}")
            result, _ = await proc.communicate(input=file_data)
            future.set_result(result)
            MAGAHAT_QUEUE.task_done()
    finally:
        await klog.log("Stopping Magahat worker due to empty queue timeout")
        MAGAHAT_WORKER_TASK = None


async def drawMagaHat(cli: Client, msg: Message, uid: int, reply_in_msg: Message):
    if uid in MAGAHAT_PENDING:
        return await replyTempMsg(cli, msg, 'кшкун ще зайнятий малюванням магахету на попередній картинці!')
    
    img_id = (msg.photo.file_id if msg.photo
              else reply_in_msg.photo.file_id if reply_in_msg and reply_in_msg.photo
              else None)
    if not img_id:
        return await replyTempMsg(cli, msg, 'кшкун не бачить фоточки')
    
    MAGAHAT_PENDING.append(uid)
    try:
        nh = nethandler()
        file_data, err = await nh.downloadTgFile(img_id, KSHKUN_CREDENTIALS.get('token'))
        if err or not file_data:
            return await replyTempMsg(cli, msg, 'помилочка з завантаженням картинки')
        
        global MAGAHAT_WORKER_TASK
        global MAGAHAT_QUEUE
        if MAGAHAT_WORKER_TASK is None or MAGAHAT_WORKER_TASK.done():
            await klog.log("No Magahat worker found. Creating new one.")
            MAGAHAT_WORKER_TASK = asyncio.create_task(MagaHatWorker())
        
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await MAGAHAT_QUEUE.put({'file_data': file_data, 'future': fut})
        result = await fut
        
        if result == b'SUBPROCESS_MAGA_HAT: NO_FACES\n':
            await replyTempMsg(cli, msg, 'обличчя не знайдено')
        else:
            image = BytesIO(result)
            await msg.reply_photo(image)
            
    except Exception:
        await replyTempMsg(cli, msg, 'помилочка.')
    finally:
        MAGAHAT_PENDING.remove(uid)


async def replyTempMsg(cli: Client, msg: Message, text: str, time:int=30, reply_markup=None): # reply with a temporary message
    sent_msg = await msg.reply(text, reply_markup=reply_markup)
    await asyncio.sleep(time)
    await cli.delete_messages(sent_msg.chat.id, sent_msg.id)
    try:
        await cli.delete_messages(msg.chat.id, msg.id)
    except Exception as e:
        await klog.log(f"replyTempMsg Error: {e}", 'ERROR')


async def handleAdminCommands(cli: Client, msg: Message, text_lower: str):
    global ACCEPT_UNI_MEDIA
    sdh = sdhandler()
    media_data = await sdh.handleData('media_ids.json')
    banned = await sdh.handleData('banned.json')
    media_id = (msg.photo and msg.photo.file_id) or (msg.animation and msg.animation.file_id) or (msg.video and msg.video.file_id)
    media_type = 'photo' if msg.photo else 'animation' if msg.animation else 'video' if msg.video else None

    if ACCEPT_UNI_MEDIA and media_id and media_type:
        media_data.append({"media_id": media_id, "media_type": media_type})
        await sdh.handleData("media_ids.json", media_data)

    elif text_lower == "обновафоточок":
        await msg.reply(f"{'не '*(not(ACCEPT_UNI_MEDIA:=not ACCEPT_UNI_MEDIA))}приймаю. в базі {len(media_data)} медіа")

    elif text_lower == "фоточки":
        for m in media_data:
            send_func = cli.send_animation if m["media_type"] == "animation" else cli.send_photo if m["media_type"] == "photo" else cli.send_video
            await send_func(msg.chat.id, m["media_id"])
            await asyncio.sleep(2)

    elif text_lower == 'банліст':
        await msg.reply(banned)

    elif text_lower.startswith(('розбан', 'бан')):
        ban_id_str = msg.text.replace('розбан' if 'розбан' in text_lower else 'бан', '').strip()
        if not ban_id_str.isdigit():
            return await msg.reply('(роз)бан (ід)')

        ban_id = int(ban_id_str)
        in_ban = ban_id in banned

        if 'розбан' in text_lower:
            if in_ban:
                banned.remove(ban_id)
                await sdh.handleData('banned.json', banned)
            await msg.reply('розбанено' if in_ban else f'{ban_id} не забанений')
        else:
            if not in_ban:
                banned.append(ban_id)
                await sdh.handleData('banned.json', banned)
            await msg.reply('забанено' if not in_ban else f'{ban_id} вже забанений')

    elif text_lower.startswith('напиши'):
        number_of_letters_string = text_lower.replace('напиши', '').strip()
        if not number_of_letters_string.isdigit() or int(number_of_letters_string) < 1:
            return await msg.reply('напиши + ціле число більше за 0')

        number_of_letters = int(number_of_letters_string)
        letters_string = 'a' * number_of_letters
        try:
            await msg.reply(letters_string)
        except:
            await msg.reply('забагато символів')

    elif text_lower.startswith('повідомлення інфо '):
        text_lower = text_lower.replace('повідомлення інфо ', '')
        if not text_lower.startswith('https://t.me/c/'):
            return await msg.reply('нема лінку на повідомлення в чаті')

        text_lower = text_lower.replace('https://t.me/c/', '')
        text_lower = text_lower.replace('/', ' ')
        data = text_lower.split()
        chat_id = int(f'-100{data[0]}')
        msg_id = int(data[1])
        try:
            msg_info = await cli.get_messages(chat_id, msg_id)
            msg_string = str(msg_info)
            if len(msg_string) > 4000:
                text_parts = [msg_string[i:i+4000] for i in range(0, len(msg_string), 4000)]
                for part in text_parts:
                    await msg.reply(part)
            else:
                await msg.reply(msg_string)

            if msg_info.from_user:
                user_info = await cli.get_users(msg_info.from_user.id)
                await msg.reply(str(user_info))

        except Exception as e:
            await msg.reply(f'фейл. {e}')

    else:
        print(msg)
        msg_string = str(msg)
        if len(msg_string) > 4000:
            text_parts = [msg_string[i:i+4000] for i in range(0, len(msg_string), 4000)]
            for part in text_parts:
                await msg.reply(part)
        else:
            await msg.reply(msg_string)


async def getEnding(number: int, options: list):
    n = 2
    if number % 10 == 1 and number % 100 != 11:
        n = 0
    elif number % 10 in (2, 3, 4) and not (number % 100 in (12, 13, 14)):
        n = 1
    return options[n]


async def getDuzhocoinsEnding(duzhocoins: int):
    options = ['', 'и', 'ів']
    return await getEnding(duzhocoins, options)


async def getCorrectAnswersEnding(amount: int):
    options = ['правильна відповідь', 'правильні відповіді', 'правильних відповідей']
    return await getEnding(amount, options)

#needs improvement: only fetches up to 200 messages max no matter what the actual amount to fetch is
async def fetchMsgsForQuiz(cli: Client, chat_id: int, msg_id: int, karakal_quiz:bool=False, messages_to_fetch:int=500):
    first_message_id = 2
    last_message_id = 2463 if karakal_quiz else msg_id

    start_msg = first_message_id
    end_msg = min(last_message_id, first_message_id + messages_to_fetch - 1)
    if end_msg < start_msg:
        return []

    if last_message_id > messages_to_fetch + first_message_id - 1:
        start_msg = random.randint(first_message_id, last_message_id - messages_to_fetch)
        end_msg = start_msg + messages_to_fetch - 1

    collected_data = []
    try:
        messages = await cli.get_messages(chat_id, range(start_msg, end_msg + 1))
        for fetched_msg in messages:
            if karakal_quiz:
                text = fetched_msg.text or fetched_msg.caption
                if text:
                    collected_data.append(text)
            else:
                if (fetched_msg.from_user 
                    and not fetched_msg.from_user.is_bot
                    and not fetched_msg.via_bot
                    and not (fetched_msg.forward_from 
                             or fetched_msg.forward_sender_name 
                             or fetched_msg.forward_from_chat)):

                    sender_name = f"{fetched_msg.from_user.first_name or ''} {fetched_msg.from_user.last_name or ''}".strip()
                    text = fetched_msg.text or fetched_msg.caption
                    if text and not text.startswith(("/", "кшкун")):
                        collected_data.append({sender_name: text})
    except Exception as e:
        print(f"Error fetching messages in chat {chat_id}: {e}")

    return collected_data


async def handleQuiz(cli: Client, msg: Message, chat_id: int, text_lower: str):
    global QUIZZES_QUEUE, POLLS_DATA

    if chat_id in QUIZZES_QUEUE:
        return await replyTempMsg(cli, msg, 'попередній квіз ще не закінчений!')

    await klog.log(f'MAKING A QUIZ')

    QUIZZES_QUEUE.append(chat_id)

    karakal_quiz = 'каракалквиз' in text_lower

    fetch_from_chat_id = chat_id if not karakal_quiz else INIT_CHAT_IDS.get("USHY_KARAKALA", 0)

    collected_data = await fetchMsgsForQuiz(cli, fetch_from_chat_id, msg.id, karakal_quiz)

    quizzes_amount = 7
    duzhocoins_win_amount = 10
    minimum_participants_amount = 3

    amount_msgs_fetched = len(collected_data)

    collected_messages_amount_msg = await msg.reply(f'зібрано {amount_msgs_fetched} повідомлень для квізу' + ('' if not karakal_quiz else ' з вух каракала'))

    if amount_msgs_fetched < 1:
        return await replyTempMsg(cli, msg, 'за мало повідомлень для квізу')

    sys_prompt = await constructSysPrompt(template_filename='quizzes_sys_prompt.txt', quizzes_amount=quizzes_amount)

    if not karakal_quiz:
        sys_prompt += ('The questions can start with something like "In a discussion about topic, name ..." or "Speaking about ... name ..." or something similar to provide context. Come up with more such introductory phrases yourself. '
                       'The question must include the name of the user it refers to, and the question MUST NOT be addressed to the user with that name.')

    prompt = f'{collected_data}'

    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, max_output_tokens=2000, response_mime_type="application/json", )

    quizzes_list = []
    user_correct_answers = {}
    try:
        counter = 1
        quizzes = json.loads(response)
        quizzes_length = len(quizzes)
        for quiz in quizzes:
            try:
                poll_message = await cli.send_poll(
                    chat_id=chat_id,
                    is_anonymous=False,
                    type=PollType.QUIZ,
                    question=f'{counter}/{quizzes_length} ' + quiz["question"],
                    options=quiz["options"],
                    correct_option_id=quiz["correct_option_id"],
                    explanation=quiz["explanation"],
                )
                poll_id = int(poll_message.poll.id)
                POLLS_DATA[poll_id] = Quiz(
                    chat_id=poll_message.chat.id, 
                    msg_id=poll_message.id, 
                    correct_answer=poll_message.poll.correct_option_id, 
                    participants={}, 
                    uids_answered_correctly=[]
                )
                quizzes_list.append(poll_id)
            except Exception as e:
                await klog.log(f'SENDING QUIZ ERROR: {e}', 'ERROR')
                await msg.reply(f'помилочка в {counter} питанні')
            finally:
                counter += 1
                await asyncio.sleep(30)

        for poll_id in quizzes_list:
            quiz = POLLS_DATA[poll_id]
            try:
                await cli.delete_messages(quiz.chat_id, quiz.msg_id)
            except Exception as e:
                await klog.log(f'DELETING QUIZZES ERROR: {e}', 'ERROR')

        await cli.delete_messages(collected_messages_amount_msg.chat.id, collected_messages_amount_msg.id)

        participants = []
        for poll_id in quizzes_list:
            quiz = POLLS_DATA[poll_id]
            for user_id in quiz.participants.keys():
                if user_id not in participants:
                    participants.append(user_id)

            for user_id in quiz.uids_answered_correctly:
                if user_id in user_correct_answers:
                    user_correct_answers[user_id]['correct_answers'] += 1
                else:
                    full_name = quiz.participants[user_id]
                    user_correct_answers[user_id] = {
                        'correct_answers': 1,
                        'name': full_name
                    }

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1]['correct_answers'], reverse=True)

        participants_amount = len(participants)
        users_answered_correctly_amount = len(user_correct_answers)

        if participants_amount < 1 or users_answered_correctly_amount < 1:
            result_message = "ніхто не взяв участі в квізі" if participants_amount < 1 else "ніхто не дав жодної правильної відповіді"
            return await msg.reply(result_message)

        result_message = "результати квізу:\n\n"

        highest_score = sorted_users[0][1]['correct_answers']
        winners = [user_id for user_id, user_data in sorted_users if user_data['correct_answers'] == highest_score]

        if len(winners) > duzhocoins_win_amount:
            winners = winners[:duzhocoins_win_amount]

        win_share = duzhocoins_win_amount // len(winners)

        for rank, (user_id, user_data) in enumerate(sorted_users, 1):
            full_name = user_data['name']
            correct_count = user_data['correct_answers']
            result_message += f"{rank}. {full_name} - {correct_count} {await getCorrectAnswersEnding(correct_count)}\n"
            if user_id in winners and participants_amount >= minimum_participants_amount:
                result_message += f" (+{win_share} дужокоїн{await getDuzhocoinsEnding(duzhocoins_win_amount)})\n\n"

        if participants_amount < minimum_participants_amount:
            result_message += f"\nмінімальна кількість учасників для отримання дужокоїнів: {minimum_participants_amount}"
        else:
            dbh = dbhandler()
            for winner_id in winners:
                winner, err = await dbh.loadInitializeOrUpdateUser(winner_id)
                if err != None:
                    await klog.log(f'QUIZ LOADING WINNER {winner_id} ERROR: {err}', 'ERROR')
                    await replyTempMsg(cli, msg, 'помилочка при завантаженні даних переможців')

                winner['duzhocoins'] += win_share
                _, err = await dbh.saveUserInDb(winner)
                if err != None:
                    await klog.log(f'QUIZ SAVING WINNER {winner_id} ERROR: {err}', 'ERROR')
                    await replyTempMsg(cli, msg, 'помилочка при збереженні даних переможців')

        result_message += f'\nвсього учасників: {participants_amount}'
        await msg.reply(result_message)

    except Exception as e:
        await klog.log(f"QUIZZES GLOBAL ERROR: {e}", 'ERROR')
        await replyTempMsg(cli, msg, 'помилочка')

    finally:
        for poll_id in quizzes_list:
            if poll_id in POLLS_DATA:
                del POLLS_DATA[poll_id]
        QUIZZES_QUEUE.remove(msg.chat.id)


async def handleCasino(cli: Client, msg: Message, uid: int, text_lower: str):
    bet_str = text_lower.replace('кшкун казик', '').strip()
    if not bet_str.isdigit() or int(bet_str) < 1:
        return await replyTempMsg(cli, msg, "ставка повинна бути цілим числом більшим за 0")

    bet = int(bet_str)
    dbh = dbhandler()
    user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f'CASINO LOADING USER {uid} ERROR: {err}', 'ERROR')
        return await replyTempMsg(cli, msg, 'помилочка при завантаженні датабази')
    
    if user['duzhocoins'] < bet:
        return await replyTempMsg(cli, msg, f'недостатньо дужокоїнів. баланс: {user['duzhocoins']} дужокоїн{await getDuzhocoinsEnding(user['duzhocoins'])}')

    user['duzhocoins'] -= bet
    dice_message = await cli.send_dice(chat_id=msg.chat.id, emoji="🎰", reply_to_message_id=msg.id)
    slots = ''.join([["⬛", "🍇", "🍋", "7️⃣"][(dice_message.dice.value - 1) // (4 ** i) % 4] for i in range(3)]) # i have no clue how this works
    win_slots = {
        "🍇🍇🍇": (3, "три виногради!"),
        "🍋🍋🍋": (5, "три лимони!"),
        "7️⃣7️⃣7️⃣": (7, "🎉🎉🎉 ДЖЕКПОТ!! три сімки!!"),
        "⬛⬛⬛": (0.75, "три бари.."),
        "🍇🍇": (1.5, "два виногради!"),
        "🍋🍋": (2, "два лимони!"),
        "7️⃣7️⃣": (3, "дві сімки!"),
        "⬛⬛": (0.5, "два бари.."),
    }
    multiplier, result = next(
        ((mult, res) for key, (mult, res) in win_slots.items() if key in slots),
        (0, f"випало: {slots}")
    )
    win_amount = round(bet * multiplier)
    if win_amount > 0:
        user['duzhocoins'] += win_amount
        win_or_loss = f'виграш: {win_amount} дужокоїн{await getDuzhocoinsEnding(win_amount)} (х{multiplier})!'
    else:
        win_or_loss = f'програш: {bet} дужокоїн{await getDuzhocoinsEnding(bet)}.'

    for number, text in PASKHALOCHKY.items():
        if str(bet) == number or str(win_amount) == number:
            win_or_loss += f'\n{text}'
            break

    balance = user['duzhocoins']
    final_message = result + ' ' + win_or_loss + '\n' + f'баланс: {balance} дужокоїн{await getDuzhocoinsEnding(balance)}'

    result, err = await dbh.saveUserInDb(user)
    if err != None:
        await klog.log(f'CASINO SAVING USER {uid} ERROR: {err}', 'ERROR')
        await replyTempMsg(cli, msg, 'помилочка при збереженні даних в датабазі')
        return await cli.delete_messages(dice_message.chat.id, dice_message.id)
    
    await asyncio.sleep(4)
    await replyTempMsg(cli, msg, final_message, 12)
    await cli.delete_messages(dice_message.chat.id, dice_message.id)


async def handleDuzhocoinTransfer(cli: Client, msg: Message, uid: int, reply_in_msg: Message, full_name: str, text_lower: str):
    if text_lower.startswith(f'/send@{KSHKUN_USERNAME}'):
        cmd = f'/send@{KSHKUN_USERNAME}'
    elif text_lower.startswith('/send'):
        cmd = '/send'
    else:
        cmd = 'кшкун сенд'

    command_parts = text_lower.replace(cmd, '').strip().split()

    if len(command_parts) < 1 or len(command_parts) > 2:
        return await replyTempMsg(cli, msg, "вживання команди: /send [сума] або кшкун сенд [сума] + (ід отримувача або відповідь на його повідомлення)\n\nприклад:\nкшкун сенд 50 199912919\n\n**відповідь на чиєсь повідомлення**\n/send 50\n\nдізнатись айді юзера/каналу - `кшкун юзердата` + відповідь на повідомлення отримувача")

    amount_str = command_parts[0]
    if not amount_str.isdigit() or not int(amount_str) > 0:
        return await replyTempMsg(cli, msg, "сума повинна бути цілим числом більшим за 0")

    amount = int(amount_str)
    dbh = dbhandler()
    sender, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f'DUZHOCOIN TRANSFER LOADING SENDER {uid} ERROR: {err}', 'ERROR')
        return await replyTempMsg(cli, msg, 'сталася помилочка під час завантаження датабази')

    sender_balance_ending = await getDuzhocoinsEnding(sender['duzhocoins'])
    amount_ending = await getDuzhocoinsEnding(amount)
    if sender['duzhocoins'] < amount:
        return await replyTempMsg(cli, msg, f'недостатньо дужокоїнів. баланс: {sender['duzhocoins']} дужокоїн{sender_balance_ending}')

    if reply_in_msg:
        reciever_id = await extractUid(reply_in_msg)
        reciever_display_name = await extractFullName(reply_in_msg)
        reciever_display_name += f' (ід `{reciever_id}`)'
    else:
        if not len(command_parts) > 1:
            return await replyTempMsg(cli, msg, 'потрібна відповідь на повідомлення або айді отримувача\nдізнатись айді - `кшкун юзердата` + відповідь на повідомлення')
        
        reciever_id = command_parts[1]
        reciever_display_name = f'`{reciever_id}`'

        if not reciever_id.lstrip('-').isdigit():
            return await replyTempMsg(cli, msg, 'ід повинен бути цілим числом, ід каналів починається з -100.\nдізнатись айді юзера/каналу - `кшкун юзердата` + відповідь на повідомлення отримувача')
    
    if reciever_id in [uid, ACCOUNT_IDS.get('KSHKUN')]:
        return await replyTempMsg(cli, msg, 'не можна надіслати дужокоїни самому собі або кшкуну')

    reply_markup = None
    text = ('ВІДПРАВНИК:\n'
            f'**{full_name}**'
            '\n\nОТРИМУВАЧ:\n'
            f'**{reciever_display_name}**'
            f'\n\nСУМА:\n'
            f'**{amount} дужокоїн{amount_ending}**')

    if msg.from_user:
        reply_markup = InKeMark([[
                            InKeBut("✅", f'sendcoins_{uid}_{reciever_id}_{amount}'),
                            InKeBut("❌", f'cancelsendcoins_{uid}')
                        ]])
    else:
        PENDING_DUZHOCOINS_SEND_FOR_CHANNELS[uid] = f'sendcoins_{uid}_{reciever_id}_{amount}'
        text += "\n\nпідтвердити - /confirmsend\n\nскасувати - /cancelsend"

    time_to_confirm = 60
    text += f'\n\n{time_to_confirm} секунд на підтвердження'
    await replyTempMsg(cli, msg, text, time_to_confirm, reply_markup)


async def confirmChannelDuzhocoinsTransfer(cli: Client, msg: Message, uid: int):
    data_str = PENDING_DUZHOCOINS_SEND_FOR_CHANNELS[uid]
    del PENDING_DUZHOCOINS_SEND_FOR_CHANNELS[uid]

    data = data_str.split('_')

    sender_id = int(data[1])
    reciever_id = int(data[2])
    amount = int(data[3])
    error_text, err = await dcoinhandler.transferDuzhocoins(sender_id, reciever_id, amount)
    if err != None:
        await klog.log(f'CHANNEL DUZHOCOINS TRANSFER CONFIRMATION ERROR: {err}', 'ERROR')
        return await replyTempMsg(cli, msg, error_text)
    
    ending = await getDuzhocoinsEnding(amount)
    await msg.reply(f'{amount} дужокоїн{ending} успішно надіслано юзеру `{reciever_id}`')


async def addRusosvyn(cli: Client, msg: Message, reply_in_msg: Message):
    if not reply_in_msg:
        return await replyTempMsg(cli, msg, 'потрібна відповідь на повідомлення русосвині')
    
    rusosvyn_id = await extractUid(reply_in_msg)
    sdh = sdhandler()
    rusosvyni = await sdh.handleData('rusosvyni.json')

    if rusosvyn_id in rusosvyni:
        rusosvyni.remove(rusosvyn_id)
        added_or_removed = 'видалено'
    else:
        rusosvyni.append(rusosvyn_id)
        added_or_removed = 'додано'

    await sdh.handleData('rusosvyni.json', rusosvyni)
    await replyTempMsg(cli, msg, f'{added_or_removed} русосвин {rusosvyn_id}')


async def generateConvo(cli: Client, msg: Message, uid: int, text_lower: str):
    reply_msg = msg.reply_to_message

    if not reply_msg:
        user_in_reply_id = None
    else:
        user_in_reply_id = await extractUid(reply_msg)

    if not user_in_reply_id or user_in_reply_id == ACCOUNT_IDS.get('KSHKUN') or user_in_reply_id == uid:
        return await replyTempMsg(cli, msg, 'потрібен реплай на повідомлення іншого юзера (не кшкуна), з яким буде згенеровано діалог.')

    dbh = dbhandler()
    sender_user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f"GENERATE CONVO SENDER {uid} ERROR: {err}", "ERROR")
        return await replyTempMsg(cli, msg, 'сталася помилочка під час завантаження відправника')
    
    sender_custom_prompt = sender_user.get('custom_system_prompt') or BASE_SYS_PROMPT

    user_in_reply, err = await dbh.loadInitializeOrUpdateUser(user_in_reply_id)
    if err != None:
        await klog.log(f"GENERATE CONVO USER IN REPLY {user_in_reply_id} ERROR: {err}", "ERROR")
        return await replyTempMsg(cli, msg, 'сталася помилочка під час завантаження юзера в реплаї')
    
    user_in_reply_custom_prompt = user_in_reply.get('custom_system_prompt') or BASE_SYS_PROMPT

    prompt = text_lower.replace('кшкун розмова ', '').strip()
    sys_prompt = await constructSysPrompt(template_filename='dialog_sys_prompt.txt', sender_custom_prompt=sender_custom_prompt, user_in_reply_custom_prompt=user_in_reply_custom_prompt)

    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, max_output_tokens=2000)
    await msg.reply(response)


async def handleRusosvyn(cli: Client, msg: Message):
    predator_msg = await predhandler.getPredatorMsg(max_length=100)
    await msg.reply(predator_msg)


async def handleTarot(cli: Client, msg: Message, uid: int, full_name: str, text_lower: str):
    prompt = text_lower.replace('кшкун таро', '').strip()
    if not prompt:
        return await replyTempMsg(cli, msg, 'потрібно вписати якесь питання.')

    sdh = sdhandler()
    tarot_data = await sdh.handleData('tg_tarot.json')
    chosen_tarot_cards = {}
    period = ['Past', 'Present', 'Future']
    media_group = []
    
    chosen_cards = random.sample(tarot_data, 3)

    for i, chosen_tarot_card in enumerate(chosen_cards):
        upright = random.choice([True, False])

        chosen_tarot_cards[period[i]] = {
            'name': chosen_tarot_card['name'],
            'number': chosen_tarot_card['number'], 
            'arcana': chosen_tarot_card['arcana'], 
            'meaning': chosen_tarot_card['upright'] if upright else chosen_tarot_card['reversed'],
            'upright': upright
        }

        file_id = chosen_tarot_card['file_id_upright'] if upright else chosen_tarot_card['file_id_reversed']
        media_group.append(InputMediaPhoto(file_id))

    sys_prompt = await constructSysPrompt(uid=uid, template_filename='tarot_sys_prompt.txt', full_name=full_name, prompt=prompt, chosen_tarot_cards=chosen_tarot_cards)
    await msg.reply_media_group(media=media_group)
    
    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, max_output_tokens=1000)
    await msg.reply(response)


async def fetch_messages_from_specific_user(cli: Client, msg: Message, chat_id: int, uid: int, amount_of_msgs_to_fetch: int, starting_msg_id: int):
    correct_chat_id = int((f'{chat_id}').replace('-100', ''))
    await replyTempMsg(cli, msg, f'дивлюся повідомлення! починаючи з [оцього](https://t.me/c/{correct_chat_id}/{starting_msg_id - amount_of_msgs_to_fetch}), {amount_of_msgs_to_fetch} штук...')

    messages = []
    all_messages = None

    for i in range(amount_of_msgs_to_fetch // 200):
        fetched_messages = await cli.get_messages(chat_id=chat_id, message_ids=range(starting_msg_id - 200 * (i + 1), starting_msg_id - 200 * i))
        if all_messages == None:
            all_messages = fetched_messages
        else:
            all_messages = fetched_messages + all_messages

    for message in all_messages:
        try:
            sender_uid = await extractUid(message)
            if sender_uid == uid:
                text = message.text if message.text else message.caption if message.caption else None
                if text:
                    messages.append(text)
        except:
            continue

    await replyTempMsg(cli, msg, f'знайшов {len(messages)} повідомлень')
    return messages


async def getPersonality(cli: Client, msg: Message, chat_id: int, reply_in_msg: Message, text_lower: str):
    if chat_id in PERSONA_QUEUE:
        return await replyTempMsg(cli, msg, 'секундачку я роблю попередню персону.')
    
    PERSONA_QUEUE.append(chat_id)
    
    if not reply_in_msg:
        return await replyTempMsg(cli, msg, 'потрібен реплай на повідомлення того, чию особистість треба описати промптом.')
    
    try:
        amount_of_msgs_to_fetch = max(2000, int(text_lower.replace('кшкун персона', '').strip()))
    except:
        amount_of_msgs_to_fetch = 1000

    starting_msg_id = reply_in_msg.id

    uid_to_fetch = await extractUid(reply_in_msg)
    messages_from_user = await fetch_messages_from_specific_user(cli, msg, chat_id, uid_to_fetch, amount_of_msgs_to_fetch, starting_msg_id)

    sdh = sdhandler()
    prompt = f"{messages_from_user}"
    sys_prompt = await sdh.handleData('personality_sys_prompt.txt')

    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, max_output_tokens=1000)
    await msg.reply(response)
    PERSONA_QUEUE.remove(chat_id)


async def handlePollVotes(cli: Client, update, users, chats):
    debug = True
    if debug:
        await klog.log(f'CLIENT: {cli}\n\nUPDATE: {update}\n\nUSERS: {users}\n\nCHATS: {chats}')

    poll_id = update.poll_id
    if not poll_id in POLLS_DATA:
        if debug:
            await klog.log(f"Poll {poll_id} not in POLLS_DATA.")
        return
    
    selected_option = int.from_bytes(update.options[0], 'big')
    quiz = POLLS_DATA[poll_id]
    correct_answer = quiz.correct_answer

    uid = update.user_id
    channel_bot_user = 136817688
    if not uid == channel_bot_user:
        raw_user = users[uid]
        full_name = await extractFullName(raw_user)
    else:
        for key in chats:
            raw_chat = chats[key]
        uid = int(f'-100{raw_chat.id}')
        full_name = await extractFullName(raw_chat)

    if not uid in quiz.participants:
        quiz.participants[uid] = full_name

    if selected_option == correct_answer:
        quiz.uids_answered_correctly.append(uid)
        if debug:
            await klog.log(f"{full_name} дав правильну відповідь в квізі {poll_id}")
    else:
        if debug:
            await klog.log(f"{full_name} дав неправильну відповідь в квізі {poll_id}")


async def sendMemeAmounts(cli: Client, msg: Message):
    totalMemeCount = 0
    counter, err = await checker_app.countMsgs(checker_app.chatStorage)
    if err != None:
        await klog.log(f'COULD NOT COUNT MEMES: {err}', 'ERROR')
        counter = 'помилка'
    else:
        totalMemeCount += counter

    draft_counter, err = await checker_app.countMsgs(checker_app.chatDraftStorage)
    if err != None:
        await klog.log(f'COULD NOT COUNT DRAFT MEMES: {err}', 'ERROR')
        draft_counter = 'помилка'
    else:
        totalMemeCount += draft_counter

    await msg.reply(f"у відкладених: {counter}\nу чернетці: {draft_counter}\nзагалом: {totalMemeCount}")


async def createKarakalPost(cli: Client, msg: Message, uid: int, text_lower: str):
    sdh = sdhandler()
    karakalMsgs = await sdh.handleData('cleaned_karakal_messages.json')
    text_lower = text_lower.replace('кшкун каракал', '').strip()
    sys_prompt = await constructSysPrompt(uid=uid, template_filename='karakal.txt', text_lower=text_lower)
    prompt = "\n".join(karakalMsgs)
    await klog.log(f"LENGTH OF KARAKAL MSGS: {len(karakalMsgs)}, PROMPT LENGTH: {len(prompt)}", 'WARNING')
    limit = 60000
    if len(prompt) > limit:
        prompt = prompt[:limit]
    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt)
    await msg.reply(response)


async def MobykWorker():
    global MOBYK_WORKER_TASK
    global MOBYK_QUEUE
    try:
        while True:
            try:
                task = await asyncio.wait_for(MOBYK_QUEUE.get(), timeout=300)
            except asyncio.TimeoutError:
                break
            file_data = task['file_data']
            future = task['future']
            try:
                proc = await asyncio.create_subprocess_exec(
                    'python3', 'kshkun_modules/mobyk.py',
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await klog.log(f"Mobyk worker invoked. PID: {proc.pid}")
                result_bytes, stderr = await proc.communicate(input=file_data)
                if stderr:
                    err_msg = stderr.decode()
                    await klog.log(f"MOBYK SUBPROCESS STDERR: {err_msg}", "ERROR")
                    future.set_exception(Exception(f"Subprocess error: {err_msg}"))
                else:
                    result_str = result_bytes.decode('utf-8')
                    try:
                        result_json = json.loads(result_str)
                        if "error" in result_json:
                            future.set_exception(Exception(result_json["error"]))
                        elif "matches" in result_json:
                            future.set_result(result_json["matches"])
                        else:
                            future.set_exception(Exception("Unexpected subprocess output format"))
                    except Exception as e:
                        await klog.log(f"MOBYK WORKER ERROR: {e}, output: {result_str}", "ERROR")
                        future.set_exception(e)
            except Exception as worker_err:
                future.set_exception(worker_err)
                await klog.log(f"MOBYK WORKER ERROR: {worker_err}", "ERROR")
            finally:
                MOBYK_QUEUE.task_done()
    finally:
        await klog.log("Stopping MobykWorker due to empty queue timeout")
        MOBYK_WORKER_TASK = None


async def compareFaces(cli: Client, msg: Message, uid: int, reply_in_msg: Message):
    if uid in MOBYK_PENDING:
        return await replyTempMsg(cli, msg, "я ще шукаю схожих мобіків до попередньої фоточки!")

    msg_to_process = msg if msg.photo else reply_in_msg
    if not msg_to_process.photo:
        return await replyTempMsg(cli, msg, "і де фоточка")

    MOBYK_PENDING.append(uid)
    try:
        img_id = msg_to_process.photo.file_id
        nh = nethandler()
        file_data, err = await nh.downloadTgFile(img_id, KSHKUN_CREDENTIALS.get('token'))
        if err or not file_data:
            return await replyTempMsg(cli, msg, 'помилочка з завантаженням картинки')

        global MOBYK_WORKER_TASK
        global MOBYK_QUEUE
        if MOBYK_WORKER_TASK is None or MOBYK_WORKER_TASK.done():
            await klog.log("No Mobyk worker found. Creating new one.")
            MOBYK_WORKER_TASK = asyncio.create_task(MobykWorker())

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await MOBYK_QUEUE.put({'file_data': file_data, 'future': fut})
        processed_matches = await fut

        if isinstance(processed_matches, list) and processed_matches:
            media_group = []
            caption = ""
            i = 1
            sdh = sdhandler()
            msg_ids = await sdh.handleData('photo_to_msgid.json')

            for match in processed_matches:
                path = match['path']
                similarity = match['similarity']
                path_data = path.split("/")
                filename = path_data[-1]
                if msg_ids.get(filename):
                    msg_id = msg_ids.get(filename)
                    msg_link = f"https://t.me/poisk_in_ua/{msg_id}"
                    caption += f"{i}. [схожість: {similarity}]({msg_link})\n\n"
                else:
                    await klog.log(f"MOBYK: no msg_id for {filename}", "ERROR")
                media_group.append(InputMediaPhoto(path))
                i += 1

            mobyks_msgs = await msg.reply_media_group(media=media_group)
            first_mobyks_msg = mobyks_msgs[0]
            await cli.edit_message_caption(chat_id=first_mobyks_msg.chat.id, message_id=first_mobyks_msg.id, caption=caption)
        else:
            await replyTempMsg(cli, msg, 'обличчя не знайдені або якась помилочка.')
    except Exception as e:
        await klog.log(f"COMPARE FACES HANDLER ERROR: {e}", "ERROR")
        await replyTempMsg(cli, msg, 'помилочка.')
    finally:
        MOBYK_PENDING.remove(uid)


async def createAudioTranscript(cli: Client, msg: Message, reply_in_msg: Message, text_lower: str):
    if not reply_in_msg or not reply_in_msg.audio:
        return await replyTempMsg(cli, msg, 'потрібна відповідь на повідомлення з аудіо')
    
    media_ids, media_types, unique_media_ids = await processMedia(cli, msg, reply_in_msg)
    
    prompt = text_lower.replace("кшкун музлотекст", "").strip() or '.'

    sys_prompt = await constructSysPrompt(template_filename='audio_transcript.txt')
    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, media_ids=media_ids, unique_media_ids=unique_media_ids)
    await msg.reply(response)


async def think(cli: Client, msg: Message, uid: int, text_lower: str):
    prompt = text_lower.replace("кшкун подумай", "").strip()
    if not prompt:
        return await replyTempMsg(cli, msg, 'про що.')

    sys_prompt = await constructSysPrompt(template_filename='think.txt', uid=uid)
    model_name = "gemini-2.0-flash-thinking-exp-01-21"
    response = await requestGemini(sys_prompt=sys_prompt, prompt=prompt, model_name=model_name)
    await msg.reply(response)


async def handleMenstra(cli: Client, msg: Message, uid: int, text_lower: str):
    await klog.log(f"Handling menstra. uid: {uid}, text_lower: {text_lower}")
    date_str = text_lower.replace("кшкун менстра", "").strip()
    if not date_str:
        start_date, err = await MENSTRAHANDLER.getMenstruationStartDate(uid)
        if err != None:
            await klog.log(f"ERROR GETTING MENSTRA START DATE WHILE HANDLING MENSTRA: {err}", 'ERROR')
            return await replyTempMsg(cli, msg, "помилочка")
        
        if not start_date:
            return await replyTempMsg(cli, msg, "дата початку менструації не знайдена")
        
        state, err = await MENSTRAHANDLER.getCurrentMenstruationStage(uid)
        if err != None:
            await klog.log(f"Error getting menstra description: {err}", "ERROR")

        if not state:
            return await replyTempMsg(cli, msg, f"дата початку відліку менструального циклу: {start_date}")
        else:
            days, err = await MENSTRAHANDLER.getMenstrualCycleDay(uid)
            if err != None:
                await klog.log(f"HANDLE MENSTRA GET MENSTRUAL CYCLE DAY ERROR: {err}", "ERROR")
                days = 'unknown'
            return await msg.reply(f"дата початку відліку менструального циклу:\n{start_date} ({days} день)\nетап: {state["name"]["uk"]}\nопис: {state["description"]["uk"]}")
    
    separators = ["-", ".", " "]
    wrong_format_msg = "неправильний формат дати. приклади:\n01.11.2025 (2025.11.01),\n01-01-2025 (2025-01-01),\n01 01 2025 (2025 01 01)"
    for sep in separators:
        if not sep in date_str:
            continue
        
        date_data = date_str.split(sep)
        await klog.log(f"Date data: {date_data}")
        if len(date_data) != 3:
            return await replyTempMsg(cli, msg, wrong_format_msg)

        if len(date_data[0]) == 4:
            year = date_data[0]
            day = date_data[2]

        elif len(date_data[2]) == 4:
            year = date_data[2]
            day = date_data[0]

        else:
            return await replyTempMsg(cli, msg, wrong_format_msg)

        month = date_data[1]
            
        if len(day) != 2 or len(month) != 2 or len(year) != 4:
            return await replyTempMsg(cli, msg, wrong_format_msg)

        date_str = f"{year}-{month}-{day}"
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        if date > today or today - date > timedelta(days=60):
            return await replyTempMsg(cli, msg, f"дата початку менструального циклу не може бути більша за сьогоднішню дату ({today}) або давніша ніж 60 днів тому ({today - timedelta(days=60)})")
        
        dbh = dbhandler()
        user, err = await dbh.loadInitializeOrUpdateUser(uid)
        if err != None or not user:
            await klog.log(f"HANDLE MENSTRA LOAD USER FROM DB ERROR: {err}", 'ERROR')
            return await replyTempMsg(cli, msg, "помилочка при завантаженні датабази")

        user['menstra_date'] = date_str
        _, err = await dbh.saveUserInDb(user)
        if err != None:
            await klog.log(f"HANDLE MENSTRA SAVING USER IN DB ERROR: {err}", 'ERROR')
            return await replyTempMsg(cli, msg, "помилочка при збереженні датабази")
        
        return await replyTempMsg(cli, msg, f"встановлено нову дату відліку менструального циклу: {day}-{month}-{year}")

    await replyTempMsg(cli, msg, wrong_format_msg)


async def downloadYoutubeVideo(cli: Client, msg: Message, uid: int):
    if uid != ACCOUNT_IDS.get("DUZHO"):
        await klog.log("YT download triggered not by Duzho", 'WARNING')
        return
    try:
        link = msg.text.replace("кшкун ютуб", "").strip()
    except Exception as e:
        await klog.log(f"YOUTUBE LINK DECODE ERROR: {e}", 'ERROR')
        return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка")

    if not link:
        return await replyTempMsg(cli, msg, "нема посилання")

    await msg.reply(f"завантажую {link}")

    nh = nethandler()
    filepath, err = await nh.downloadYtVideo(link)
    if err != None or not filepath:
        await klog.log(f"YOUTUBE VIDEO DOWNLOAD ERROR: {err}", 'ERROR')
        return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка")

    try:
        await msg.reply_video(video=filepath, supports_streaming=True)
    except Exception as telegram_error:
        await klog.log(f"TELEGRAM SEND VIDEO ERROR: {telegram_error}", 'ERROR')
        await replyTempMsg(cli, msg, "ой.. не вдалося відправити відео")
    finally:
        if filepath and os.path.exists(filepath):
            os.unlink(filepath)
        base_temp_path = filepath.strip(".mp4")
        if base_temp_path and os.path.exists(base_temp_path):
            os.unlink(base_temp_path)


async def checkFact(cli: Client, msg: Message, uid: int, full_name: str, text_lower: str):
    query = text_lower.replace("кшкун фактчек", "").strip()
    if not query:
        return await replyTempMsg(cli, msg, 'що за питання то')

    google_results, crawled_content, err = await getSearchResults(query)
    if err != None or not (google_results or crawled_content):
        google_results = "Failed to get search results"
        crawled_content = "Failed to get info from websites"
    
    sys_prompt = await constructSysPrompt(template_filename='check_fact.txt', uid=uid, full_name=full_name, google_results=google_results, crawled_content=crawled_content)
    response = await requestGemini(sys_prompt=sys_prompt, prompt=query, max_output_tokens=3000, model_name="gemini-2.0-flash-thinking-exp-01-21")
    await msg.reply(response)


async def checkAdmin(cli: Client, msg: Message, uid: int):
    chat_data = await cli.get_chat(msg.chat.id)
    base_admin_chats = [msg.chat.id]
    linked_chat = chat_data.linked_chat
    if linked_chat:
        base_admin_chats.append(linked_chat.id)

    if uid in base_admin_chats:
        return True, chat_data

    admins = []
    async for m in cli.get_chat_members(msg.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
        admins.append(m)

    if uid in admins:
        return True, chat_data

    return False, chat_data


async def handleShluhobot(cli: Client, msg: Message, chat_id: int, uid: int, text_lower: str):
    is_admin, chat_data = await checkAdmin(cli, msg, uid)
    if not is_admin:
        return await replyTempMsg(cli, msg, "ти не адмінчик...")
    
    if not chat_data.linked_chat:
        await replyTempMsg(cli, msg, "шлюхобота можна врубити тільки в коментах")

    dbh = dbhandler()
    chat, err = await dbh.loadInitializeOrUpdateChat(chat_id)
    if err != None:
        await klog.log(f"ERROR HANDLING SHLUHOBOT IN CHAT {chat_id}: {err}", "ERROR")
        return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка під час завантаження датабази")

    if text_lower.startswith(("кшкун шлюхобот промпт ресет", "кшкун шлюхобот ресет промпт")):
        chat['shluhobot_custom_prompt'] = ""
        _, err = await dbh.saveChatInDb(chat)
        if err != None:
            await klog.log(f"HANDLE SHLUHOBOT REMOVING SHLUHOBOT PROMPT IN CHAT {chat_id} ERROR: {err}", "ERROR")
            return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка під час збереження промпту у датабазі")
        
        #await replyTempMsg(cli, msg, "промпт видалено")
        await msg.reply("промпт видалено")

    elif text_lower.startswith("кшкун шлюхобот промпт"):
        new_shluhobot_prompt = text_lower.replace("кшкун шлюхобот промпт", "").strip()
        if not new_shluhobot_prompt:
            shluhobot_prompt = chat.get("shluhobot_custom_prompt") or "не встановлено"
            await replyTempMsg(cli, msg, f"шлюхобот промпт: {shluhobot_prompt}")

        if len(new_shluhobot_prompt) > 4000:
            return await replyTempMsg(cli, msg, "довжина шлюхобот промпту не повинна перевищувати 4000 символів")
        
        chat['shluhobot_custom_prompt'] = new_shluhobot_prompt
        _, err = await dbh.saveChatInDb(chat)
        if err != None:
            await klog.log(f"HANDLE SHLUHOBOT SETTING NEW SHLUHOBOT PROMPT IN CHAT {chat_id} ERROR: {err}", "ERROR")
            return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка під час збереження промпту у датабазі")
        
        await replyTempMsg(cli, msg, f"встановлено новий шлюхобот промпт: {new_shluhobot_prompt}")
        
    else:
        on = bool(chat.get('shluhobot_on'))
        chat['shluhobot_on'] = not on
        _, err = await dbh.saveChatInDb(chat)
        if err != None:
            await klog.log(f'ENABLING/DISABLING SHLUHOBOT IN CHAT {chat_id} ERROR: {err}', "ERROR")
            return await replyTempMsg(cli, msg, "ой.. сталася якась помилочка під час збереження стану шлюхобота")
        
        on_or_off_str = ("уві" if not on else "ви") + "мкнено"
        return await replyTempMsg(cli, msg, f"шлюхобот {on_or_off_str}")

    
async def sendShluhobotMessage(cli: Client, msg: Message, shluhobot_custom_prompt: str, text_lower: str):
    sys_prompt = await constructSysPrompt(template_filename="shluhobot_base_prompt.txt")
    if shluhobot_custom_prompt:
        sys_prompt += f" You are also required to adhere to this prompt set by the admin of the channel, YOU ABSOLUTELY HAVE TO RESPOND THIS WAY: {shluhobot_custom_prompt}"

    response = await requestGemini(sys_prompt, text_lower, model_name="gemini-2.0-flash-lite-preview-02-05")
    await msg.reply(response)

async def handleInlineQuery(cli: Client, i_q: InlineQuery):
    await klog.log(f'Inline query by {i_q.from_user.id}')
    uid = await extractUid(i_q)
    sdh = sdhandler()
    if uid in await sdh.handleData('banned.json'):
        return

    msgs = await sdh.handleData('msgs.json')
    dbh = dbhandler()
    user, err = await dbh.loadInitializeOrUpdateUser(uid)
    if err != None:
        await klog.log(f'INLINE QUERY LOADING USER {uid} ERROR: {err}', 'ERROR')
        user = {'duzhocoins': 0}

    seed = i_q.query.strip().lower()
    random_msg = random.choice(msgs)
    ms = [m for m in msgs if seed and seed in m.lower()][:49]

    if seed:
        ph = predhandler()
        gen = await ph.generateMsg(seed)
        gen_msg_result = [InQuResArt(title="згенероване", description=gen, input_message_content=InpTxtMsgCont(gen), thumb_url=LINKS.get("generated_chat_bubble"))]
    else:
        duzhocoins = user['duzhocoins']
        ending = await getDuzhocoinsEnding(duzhocoins)
        duzhocoins_msg = [InQuResArt(title="дужокоїни", description=f'баланс: {duzhocoins}', input_message_content=InpTxtMsgCont(f'у тебе {duzhocoins} дужокоїн{ending}'), thumb_url=LINKS.get("duzhocoin_image"))]

    if len(ms) > 0:
        rand_msgs_results = [InQuResArt(title=m[:33], description=m[33:135], input_message_content=InpTxtMsgCont(m), thumb_url=LINKS.get("random_chat_bubble")) for m in ms]
    else:
        rand_msgs_results = [InQuResArt(title=("не знайдено, " * bool(seed)) + "надіслати рандомне повідомлення", description=random_msg, input_message_content=InpTxtMsgCont(random_msg), thumb_url=LINKS.get("random_chat_bubble"))]

    results = (gen_msg_result + rand_msgs_results) if seed else (duzhocoins_msg + rand_msgs_results)
    await i_q.answer(results, cache_time=0)


async def handleMessages(cli: Client, msg: Message):
    chat_id = msg.chat.id
    uid = await extractUid(msg)
    full_name = await extractFullName(msg) if not uid == ACCOUNT_IDS.get("GNYDOCHKO") else "гнидочко"
    chat_name = msg.chat.title
    await klog.log(f'Msg by {full_name}({uid}) in {chat_name}({chat_id})')
    if chat_id in [INIT_CHAT_IDS.get("TEST_CHANNEL"), INIT_CHAT_IDS.get("TEST_CHANNEL_COMMENTS")]:
        print(msg)

    chat_type = msg.chat.type
    in_private_chat = chat_type == ChatType.PRIVATE
    if chat_id not in WHITELIST and not in_private_chat:
        try:
            await msg.reply(f"чатик не в вайт лісті. напишіть в @nnknht_bot і можливо вам буде надано доступ. ід чату: `{chat_id}` (копіюється)")
        except:
            pass
        await cli.leave_chat(chat_id)
        return await klog.log(f"Left chat {chat_name} ({chat_id}) because it's not in the whitelist")

    sdh = sdhandler()
    banned = await sdh.handleData('banned.json')
    if uid in banned:
        return await msg.reply('ти в бані чучело')
    
    if uid in await sdh.handleData('rusosvyni.json'):
        return await handleRusosvyn(cli, msg)

    text = msg.text or msg.caption or ''
    text_lower = text.lower()

    dbh = dbhandler()

    if chat_id not in LINKED_CHAT_BUFFER and not in_private_chat:
        chat_info = await cli.get_chat(chat_id)
        LINKED_CHAT_BUFFER[chat_id] = chat_info.linked_chat.id if chat_info.linked_chat else None

    linked_chat_id = LINKED_CHAT_BUFFER.get(chat_id)

    chat, err = await dbh.loadInitializeOrUpdateChat(chat_id)
    if err != None:
        await klog.log(f"ERROR GETTING CHAT DATA FROM CHAT {chat_id}: {err}", "ERR")

    if chat and text_lower and msg.forward_from_chat and msg.forward_from_chat.id == linked_chat_id and msg.views:
        if bool(chat.get('shluhobot_on')):
            return await sendShluhobotMessage(cli, msg, chat['shluhobot_custom_prompt'], text_lower)

    if text_lower == "кшк":
        sent_message = await sendKshk(cli, chat_id, msg.id)
        try:
            return await cli.delete_messages(chat_id, msg.id)
        except:
            await cli.edit_message_caption(chat_id, sent_message.id, caption="не можу видалити повідомлення.")
            await asyncio.sleep(10)
            return await cli.edit_message_caption(chat_id, sent_message.id, caption=None)

    if chat_type == ChatType.CHANNEL:
        return
    
    if msg.service:
        new_chat_members = msg.new_chat_members
        left_chat_member = msg.left_chat_member
        if new_chat_members:
            new_member_full_name = await extractFullName(new_chat_members[0])
            if new_chat_members[0].is_self:
                await klog.log(f"Kshkun added to chat {chat_name} ({chat_id})")
                return await msg.reply("привіт! я кшкунчик, зі мною можна говорити командою кшкун або відповідаючи на мої повідомлення. інші функції - /help")
            else:
                return await msg.reply(f'привіт, {new_member_full_name}, вітаємо в чатику {chat_name}. я кшкунчик, зі мною можна говорити командою кшкун або відповідаючи на мої повідомлення. інші функції - /help')
        elif left_chat_member:
            if left_chat_member.is_self:
                return await klog.log(f"Kshkun removed from chat {chat_name} ({chat_id})")
            else:
                return await msg.reply(f"ну і піздуй звідси чмо, тебе тут ніхто не любить")

    duzho = ACCOUNT_IDS.get("DUZHO", 0)

    if uid in PENDING_DUZHOCOINS_SEND_FOR_CHANNELS:
        if text_lower in ['/confirmsend', f'/confirmsend@{KSHKUN_USERNAME}']:
            return await confirmChannelDuzhocoinsTransfer(cli, msg, uid)
        elif text_lower in ['/cancelsend', f'/cancelsend@{KSHKUN_USERNAME}']:
            del PENDING_DUZHOCOINS_SEND_FOR_CHANNELS[uid]
            return await replyTempMsg(cli, msg, 'відправка дужокоїнів скасована')

    reply_in_msg = msg.reply_to_message
    has_poll_in_reply = reply_in_msg and reply_in_msg.poll

    trigger_word = 'кшкун'

    if text_lower == f'{trigger_word} юзердата':
        if not reply_in_msg:
            return await replyTempMsg(cli, msg, 'потрібна відповідь на повідомлення')
        display_id = await extractUid(reply_in_msg)
        display_name = await extractFullName(reply_in_msg)
        return await replyTempMsg(cli, msg, f'айді {display_name}:\n`{display_id}` (натисни щоб скопіювати)')

    if text_lower.startswith(('/help', f'/help@{KSHKUN_USERNAME}', f'{trigger_word} допомога', f'{trigger_word} хелп')):
        return await msg.reply(await sdh.handleData('help_message.txt'))
        
    elif text_lower.startswith(('/balance', f'/balance@{KSHKUN_USERNAME}', f'{trigger_word} баланс')):
        user, err = await dbh.loadInitializeOrUpdateUser(uid)
        if err != None:
            await klog.log(f"BALANCE LOAD ERROR FOR USER {uid}: {err}", "ERROR")
            return await replyTempMsg(cli, msg, 'сталася помилочка під час завантаження датабази')

        duzhocoins = user['duzhocoins']
        ending = await getDuzhocoinsEnding(duzhocoins)
        reply_text = f'у тебе {duzhocoins} дужокоїн{ending}' + (f'\n\nбаланс можна подивитися вписавши `@{KSHKUN_USERNAME}` (копіюється, вставити і зачекати)' if msg.from_user else '')
        return await replyTempMsg(cli, msg, reply_text)
    
    if in_private_chat:
        if uid == duzho:
            await handleAdminCommands(cli, msg, text_lower)
        return

    if text_lower.startswith(('/send', f'{trigger_word} сенд')):
        return await handleDuzhocoinTransfer(cli, msg, uid, reply_in_msg, full_name, text_lower)

    verified_uids = await sdh.handleData('verified_users.json')

    all_txt_lower = (text_lower + full_name).lower()

    u_verified = uid in verified_uids

    has_ru_symbols = any(l in all_txt_lower for l in ['ы', 'э', 'ъ', 'ё', '🇷🇺'])
    has_ua_bel_letters = any(l in all_txt_lower for l in ['і', 'ў', 'є', 'ґ', 'ї'])
    has_ru_doesnt_have_ua_letters = has_ru_symbols and not has_ua_bel_letters

    reply_to_kshkun = reply_in_msg and reply_in_msg.from_user and reply_in_msg.from_user.id == ACCOUNT_IDS.get("KSHKUN", 0)
    not_forward = not (msg.forward_from or msg.forward_sender_name or msg.forward_from_chat)

    nnknht_chat = INIT_CHAT_IDS.get("NNKNHT_CHAT", 0)
    zebra = ACCOUNT_IDS.get("ZEBRA", 0)

    is_reply_to_linked_channel = (reply_in_msg
                                    and reply_in_msg.forward_from_chat
                                    and reply_in_msg.forward_from_chat.type == ChatType.CHANNEL
                                    and reply_in_msg.forward_from_chat.id == linked_chat_id) #basically trying to determine whether a message is a comment or not
                                #is there a way to check in a more straightforward way?
    common_args = {
        'uid': uid,
        'chat_id': chat_id,
        'msg_id': msg.id,
        'full_name': full_name,
        'reply_in_msg': reply_in_msg,
        'reply_to_kshkun': reply_to_kshkun,
        'text_lower': text_lower,
        'checker_app': checker_app
    }

    commands = {
        ("скан",): (scanImgGifSticker, ['uid', 'full_name', 'reply_in_msg', 'text_lower'], None),
        ("загугли",): (searchGoogle, ['uid', 'full_name', 'text_lower'], None),
        ("погода",): (getWeather, ['text_lower'], None),
        ("мапа",): (findAddress, ['text_lower'], None),
        ("русоскот",): (handleRuLosses, [], None),
        ("ресет промпт", "промпт ресет"): (resetCustomPrompt, ['uid'], None),
        ("промпт",): (handleCustomPrompts, ['uid', 'reply_in_msg', 'text_lower'], None),
        ("магахет", "магахат"): (drawMagaHat, ['uid', 'reply_in_msg'], None),
        ("квиз", "квіз", "каракалквиз"): (handleQuiz, ['chat_id', 'text_lower'], None),
        ("казик",): (handleCasino, ['uid', 'text_lower'], None),
        ("таро",): (handleTarot, ['uid', 'full_name', 'text_lower'], None),
        ("розмова",): (generateConvo, ['uid', 'text_lower'], None),
        ("персона",): (getPersonality, ['chat_id', 'reply_in_msg', 'text_lower'], None),
        ("меми",): (sendMemeAmounts, [], text_lower == f"{trigger_word} меми" and chat_id == nnknht_chat),
        ("русосвин",): (addRusosvyn, ['reply_in_msg'], text_lower == f"{trigger_word} русосвин" and uid in [nnknht_chat, INIT_CHAT_IDS.get("DUZHO_CHAN", 0), duzho, zebra]),
        ("каракал",): (createKarakalPost, ['uid', 'text_lower'], None),
        ("мобик",): (compareFaces, ['uid', 'reply_in_msg'], None),
        ("музлотекст",): (createAudioTranscript, ['reply_in_msg', 'text_lower'], None),
        ("подумай",): (think, ['uid', 'text_lower'], None),
        ("ютуб",): (downloadYoutubeVideo, ['uid'], None),
        ("менстра",): (handleMenstra, ['uid', 'text_lower'], None),
        ("фактчек",): (checkFact, ['uid', 'full_name', 'text_lower'], None),
        ("шлюхобот",): (handleShluhobot, ['chat_id', 'uid', 'text_lower'], None),
        ("",): (talk, ['uid', 'reply_to_kshkun', 'reply_in_msg', 'full_name', 'text_lower'], reply_to_kshkun),
        }

    meows = ["мяу", "няв", "мяв", "мрр"]

    if chat_id == nnknht_chat:
        await handleNnknhtChat(cli, msg, uid, u_verified, text_lower, verified_uids)

    if is_reply_to_linked_channel and has_ru_doesnt_have_ua_letters and (chat_id != nnknht_chat or (not u_verified and chat_id == nnknht_chat)):
        await sendRusniaGif(cli, msg, uid, u_verified, all_txt_lower)

    elif not_forward and (text_lower.startswith(trigger_word) or (reply_to_kshkun and not has_poll_in_reply)):
        if uid in TEMPBAN_UIDS:
            return await checkApology(cli, msg, uid, text_lower)

        for command_keywords_tuple, parts in commands.items():
            function, args_list, condition = parts
            for command_keyword in command_keywords_tuple:
                condition = condition or text_lower.startswith((trigger_word + ' ' + command_keyword).strip())
                if condition:
                    args = [cli, msg] + [common_args[arg] for arg in args_list]
                    return await function(*args)

    elif any(word in text_lower for word in ['петушок', 'петуч', 'петух', 'петушара', 'півень', 'півник', 'русск', '🇷🇺', 'russia', 'славяне']):
        await msg.reply_sticker("CAACAgIAAxkBAAMOZs3NuwdBl2vf2ijXGPt9rsZ73kQAAsYZAAK8knlJsc-8KnWcjoweBA")

    elif text_lower in meows and random.randint(1, 100) < 33:
        response_text = " ".join(random.choice(meows) for _ in range(random.randint(1, 7)))
        await msg.reply_text(response_text)


async def handleCallbackQuery(cli: Client, c_q: CallbackQuery):
    query_data = c_q.data.split('_')
    uid = await extractUid(c_q)
    await klog.log(f'Callback query by {uid}: {query_data}')
    act = query_data[0]
    chid = c_q.message.chat.id
    m_id = c_q.message.id

    if not uid == int(query_data[1]):
        return await c_q.answer("❌ оппа а ну киш ця кнопочка не для тебе.", show_alert=True)

    if act == 'verify':
        await cli.edit_message_text(chat_id=chid, message_id=m_id, text="чий крим:", reply_markup=await getKeyboard(1, uid))

    elif act == 'ua':
        sdh = sdhandler()
        verified_uids = await sdh.handleData('verified_users.json')
        verified_uids.append(uid)
        await sdh.handleData('verified_users.json', verified_uids)
        await cli.edit_message_text(chat_id=chid, message_id=m_id, text="✅ ми успішно підтвердили, що ви не маскалик.")

    elif act in ['wrong1', 'wrong2']:
        text = "впевнений?" if act == 'wrong1' else "подумай ще раз."
        buttons = await getKeyboard(2 if act == 'wrong1' else 3, uid)
        await cli.edit_message_text(chat_id=chid, message_id=m_id, text=text, reply_markup=buttons)

    elif act == 'wrong3':
        await cli.edit_message_text(chat_id=chid, message_id=m_id, text="⛔ мут бан 2000 днів, пака пака. апеляція на розбан: @nnknht_bot")
        await cli.ban_chat_member(chat_id=chid, user_id=uid)    

    elif act == 'sendcoins':
        sender_id = int(query_data[1])
        reciever_id = int(query_data[2])
        amount = int(query_data[3])
        error_text, err = await dcoinhandler.transferDuzhocoins(sender_id, reciever_id, amount)
        if err != None:
            await c_q.answer(error_text, show_alert=True)
            await cli.edit_message_text(chat_id=chid, message_id=m_id, text=error_text)
            await asyncio.sleep(30)
            await cli.delete_messages(chid, m_id)
            return

        amount_ending = await getDuzhocoinsEnding(amount)
        try:
            reciever_tg_data = await cli.get_users(reciever_id)
            reciever_full_name = await extractFullName(reciever_tg_data)
            reciever_display_name = f"{reciever_full_name} ({reciever_id})"
        except Exception as e:
            await klog.log(f'COULD NOT GET FULL NAME: {e}', 'ERROR')
            reciever_display_name = reciever_id

        await cli.edit_message_text(chat_id=chid, message_id=m_id, text=f'{amount} дужокоїн{amount_ending} успішно надіслано юзеру {reciever_display_name}')
        await asyncio.sleep(60)
        await cli.delete_messages(chid, m_id)

    elif act == 'cancelsendcoins':
        await cli.edit_message_text(chat_id=chid, message_id=m_id, text='відправка дужокоїнів скасована')
        await asyncio.sleep(30)
        await cli.delete_messages(chid, m_id)


async def catchUpdates():
    @app.on_inline_query()
    async def onInlineQuery(cli: Client, i_q: InlineQuery):
        await handleInlineQuery(cli, i_q)

    @app.on_message()
    async def onMessage(cli: Client, msg: Message):
        await handleMessages(cli, msg)

    @app.on_callback_query()
    async def onCallbackQuery(cli: Client, c_q: CallbackQuery):
        await handleCallbackQuery(cli, c_q)

    @app.on_raw_update()
    async def onRawUpdate(cli, update, users, chats):
        if isinstance(update, UpdateMessagePollVote):
            await handlePollVotes(cli, update, users, chats)


async def startBots():
    await klog.log("Starting...")
    app = await loadGlobals()
    await asyncio.gather(app.start(), checker_app.start(), catchUpdates())


if __name__ == "__main__":
    try:
        asyncio.run(startBots())
    except Exception as e:
        print(f"ERROR OCCURED WHEN RUNNING BOTS: {e}")
    finally:
        print("STOPPING THE BOT...")

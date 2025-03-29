from pyrogram.types import Message, InlineQuery, CallbackQuery
from pyrogram.enums import MessageEntityType
from datetime import datetime, timezone, timedelta
import random, pycountry
from .logger import KshkunLogger

klog = KshkunLogger()

class HelperFuncs:
    def __init__(self):
        pass

    async def getEnding(self, number: int, options: list):
        n = 2
        if number % 10 == 1 and number % 100 != 11:
            n = 0
        elif number % 10 in (2, 3, 4) and not (number % 100 in (12, 13, 14)):
            n = 1
        return options[n]

    async def getDuzhocoinsEnding(self, duzhocoins: int):
        options = ['', 'и', 'ів']
        return await self.getEnding(duzhocoins, options)

    async def getCorrectAnswersEnding(self, amount: int):
        options = ['правильна відповідь', 'правильні відповіді', 'правильних відповідей']
        return await self.getEnding(amount, options)

    async def extractSender(self, data):
        if isinstance(data, (Message, InlineQuery, CallbackQuery)):
            sender = data.from_user if data.from_user else data.sender_chat
        else:
            sender = data

        return sender

    async def extractFullName(self, data):
        sender = await self.extractSender(data)
        try:
            name = sender.title
        except:
            try:
                name = (sender.first_name + ' ' + sender.last_name) if sender.last_name else sender.first_name
            except:
                await klog.err(f'FAILED TO EXTRACT NAME: {data}')
                return None

        return name

    async def extractUid(self, data):
        sender = await self.extractSender(data)
        try:
            uid = sender.id
        except:
            await klog.err(f'FAILED TO EXTRACT UID: {data}')
            uid = None

        return uid

    async def checkLink(self, msg: Message):
        url_types = [MessageEntityType.URL, MessageEntityType.TEXT_LINK, MessageEntityType.MENTION]
        for entities in [msg.entities, msg.caption_entities]:
            if entities:
                return any(ent.type in url_types for ent in entities)
            
        return False
    
    async def getCountryFlag(self, country_code: str):
        if country_code == "RU":
            return random.choice(["🤮", "💩", "🤡"])
        return ''.join(chr(ord(l) + 127397) for l in country_code)

    async def getCountryName(self, country_code: str):
        if country_code == "RU":
            return random.choice(['блинолопатна скотоублюдія', 'свинособачий хуйлостан', 'нафтодирне пинєбабве', 'підорашка'])
        return pycountry.countries.get(alpha_2=country_code).name

    async def getCountryCode(self, country_code: str, city_name: str):
        if city_name in ["Sudzha", "Kursk", "Belgorod", "Taganrog", "Voronezh", "Rostov-on-Don"]:
            return "UA"
        return country_code

    async def formatTimestampToHourMinuteUTC(self, timestamp: float, tz_seconds: float):
        return (datetime.fromtimestamp(timestamp, timezone.utc) + timedelta(seconds=tz_seconds)).strftime('%H:%M')
    
    async def getClock(self, time: datetime):
        clocks = [
            ["🕛", "🕧"], # 0/12
            ["🕐", "🕜"], # 1
            ["🕑", "🕝"], # 2
            ["🕒", "🕞"], # 3
            ["🕓", "🕟"], # 4
            ["🕔", "🕠"], # 5
            ["🕕", "🕡"], # 6
            ["🕖", "🕢"], # 7
            ["🕗", "🕣"], # 8
            ["🕘", "🕤"], # 9
            ["🕙", "🕥"], # 10
            ["🕚", "🕦"], # 11
        ]
        return clocks[time.hour % 12][(time.minute // 30)]
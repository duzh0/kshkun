import random, asyncio
from datetime import datetime, timedelta
from pyrogram import Client
from .logger import KshkunLogger as klog
from .data_handler import SimpleDataHandler as sdhandler

class ReactChecker:
    def __init__(self, pnumber, id, hash, counter, sleepTime, emojisRequired, maxCounterCheck, chatPosting, chatStorage, chatDraftStorage, admin, kshkunInstance):
        self.acc = Client(name="checker", phone_number=pnumber, api_id=id, api_hash=hash)
        self.counter = counter
        self.sleepTime = sleepTime
        self.emojisRequired = emojisRequired
        self.maxCounterCheck = maxCounterCheck
        self.chatPosting = chatPosting
        self.chatStorage = chatStorage
        self.chatDraftStorage = chatDraftStorage
        self.admin = admin
        self.kshkunInstance = kshkunInstance
                                                            #no clue what type condition is
    async def getChatHistory(self, chatId: int, limit: int, condition, break_on_first_match: bool):
        msgs = []
        err = None
        try:
            async for m in self.acc.get_chat_history(chatId, limit=limit):
                if condition(m):
                    msgs.append(m)
                    if break_on_first_match:
                        break
        except Exception as e:
            await klog.log(f'COULD NOT GET CHAT HISTORY: {e}', 'ERROR')
            err = e

        if break_on_first_match:
            if msgs:
                return msgs[0], err
            else:
                return None, err
        else:
            return msgs, err

    async def getMsgToCheck(self):
        condition = lambda m: not (m.forward_from or m.forward_sender_name or m.forward_from_chat) and m.media
        return await self.getChatHistory(self.chatPosting, 50, condition, True)
    
    async def getMsgIdsToUpdate(self):
        condition = lambda m: (m.date < datetime.now() - timedelta(days=1)) and m.id != 1
        return await self.getChatHistory(self.chatStorage, None, condition, False)
    
    async def getMemeFromStorage(self):
        condition = lambda m: m.id != 1
        return await self.getChatHistory(self.chatStorage, 1, condition, True)
    
    async def sendMeme(self, emojisDict: dict, totalEmojiCount: int, memeId: int):
        decodedMsg = "\n".join([f"{emoji}: {count}" for emoji, count in emojisDict.items()]) + f"\nвсього: {totalEmojiCount}"
        if memeId:
            await self.kshkunInstance.copy_message(chat_id=self.chatPosting, from_chat_id=self.chatStorage, message_id=memeId)
            try:
                await self.kshkunInstance.delete_messages(self.chatStorage, memeId)
            except:
                decodedMsg += f'\n\nне вдалося видалити картиночку {memeId}'

            try:
                await self.kshkunInstance.send_message(self.admin, f"{decodedMsg}\n\nзапощено мем")
            except Exception as e:
                await klog.log(f"Failed to send message to admin: {e}, admin: {self.admin}", "ERROR")

        else:
            await self.sendKshk()
            try:
                await self.kshkunInstance.send_message(self.admin, f"{decodedMsg}\n\nмедіа не знайдено, запощено кушкуна")
            except Exception as e:
                await klog.log(f"Failed to send message to admin: {e}, admin: {self.admin}", "ERROR")

    async def sendKshk(self):
        sdhand = sdhandler()
        mediaData = await sdhand.handleData('media_ids.json')
        media = random.choice(mediaData)
        functions = {
            'photo': self.kshkunInstance.send_photo, 
            'animation': self.kshkunInstance.send_animation, 
            'video': self.kshkunInstance.send_video
        }
        try:
            await functions[media["media_type"]](self.chatPosting, media["media_id"])
        except Exception as e:
            await klog.log(f'COULD NOT SEND KSHK: {e}', 'ERROR')

    async def countMsgs(self, chatId: int):
        amount = -1
        err = None
        try:
            async for _ in self.acc.get_chat_history(chatId):
                amount += 1
        except Exception as e:
            await klog.log(f'COULD NOT GET CHAT HISTORY: {e}', 'ERROR')
            err = e

        return amount, err

    async def start(self):
        await klog.log('Starting reactions loop')
        await self.acc.start()

        await klog.log('Getting messages to check')
        msgToCheck, err = await self.getMsgToCheck()
        if err != None:
            await klog.log(f'COULD NOT GET MSG TO CHECK: {err}', 'ERROR')

        if msgToCheck:
            timeDeltaSeconds = int((datetime.now() - msgToCheck.date).total_seconds())
            await klog.log(f'Last post at {msgToCheck.date} ({timeDeltaSeconds}s ago)')
        else:
            timeDeltaSeconds = 0
            await klog.log('Could not get last post date, starting from zero')

        if timeDeltaSeconds >= (self.sleepTime * self.maxCounterCheck):
            self.counter = self.maxCounterCheck
            adjustSleepTime = 0
            await klog.log(f'Skipped {self.maxCounterCheck} counters or more, posting now')
        else:
            skippedCounters = timeDeltaSeconds // self.sleepTime
            self.counter += skippedCounters
            adjustSleepTime = timeDeltaSeconds - (self.sleepTime * skippedCounters)
            await klog.log(f'{skippedCounters} counters skipped, adjusting sleep time by {adjustSleepTime}s')

        while True:
            msgsToUpdate, err = await self.getMsgIdsToUpdate()
            if err != None:
                await klog.log(f'COULD NOT GET MSGS TO UPDATE: {err}', 'ERROR')

            msgIdsToUpdate = [m.id for m in msgsToUpdate]
            if msgIdsToUpdate:
                await klog.log(f'Found {len(msgIdsToUpdate)} messages to update: {msgIdsToUpdate}')
                for msgId in msgIdsToUpdate:
                    await self.kshkunInstance.copy_message(chat_id=self.chatStorage, from_chat_id=self.chatStorage, message_id=msgId)
                    await self.kshkunInstance.delete_messages(self.chatStorage, msgId)
                    await asyncio.sleep(10)

                await self.kshkunInstance.send_message(self.admin, f"оці повідомлення було оновлено: {msgIdsToUpdate}")

            msgToCheck, err = await self.getMsgToCheck()
            if err != None:
                await klog.log(f'COULD NOT GET MSG TO CHECK: {err}', 'ERROR')

            if msgToCheck and msgToCheck.reactions:
                totalEmojiCount = sum(r.count for r in msgToCheck.reactions.reactions)
            else:
                totalEmojiCount = 0

            actualSleepTime = self.sleepTime - adjustSleepTime

            if totalEmojiCount >= self.emojisRequired or self.counter >= self.maxCounterCheck:
                meme, err = await self.getMemeFromStorage()
                emojisDict = {}
                if msgToCheck.reactions and msgToCheck.reactions.reactions:
                    for r in msgToCheck.reactions.reactions:
                        emojisDict[r.emoji if r.emoji else 'custom emoji'] = r.count

                self.counter = 0
                await klog.log(f"{totalEmojiCount}/{self.emojisRequired} emojis. Posting message. Sleeping for {actualSleepTime // 60} mins. 0/{self.maxCounterCheck}")
                await self.sendMeme(emojisDict, totalEmojiCount, meme.id if meme else None)
            else:
                self.counter += 1
                await klog.log(f"{totalEmojiCount}/{self.emojisRequired} emojis. Sleeping for {actualSleepTime // 60} mins. {self.counter}/{self.maxCounterCheck}")

            if adjustSleepTime > 0:
                await asyncio.sleep(actualSleepTime)
                adjustSleepTime = 0
            else:
                await asyncio.sleep(self.sleepTime)

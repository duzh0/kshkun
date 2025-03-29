from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class KeyboardHandler:
    def __init__(self):
        pass

    async def createKeyboardMarkup(self, keyboard_data: dict[str: str], buttons_in_row: int):
        keyboard_rows = []
        current_row = []
        button_count = 0
        for text, callback_data in keyboard_data.items():
            button = InlineKeyboardButton(text=text, callback_data=callback_data)
            current_row.append(button)
            button_count += 1
            if button_count >= buttons_in_row:
                keyboard_rows.append(current_row)
                current_row = []
                button_count = 0

        if current_row:
            keyboard_rows.append(current_row)

        return InlineKeyboardMarkup(keyboard_rows)
    
    async def getVerificationKeyboard(self, uid: int):
        keyboard_data = {"я не маскалик!": f"verify_{uid}"}
        return await self.createKeyboardMarkup(keyboard_data, 1)

    async def getVerificationConfirmationKeyboard(self, i: int, uid: int):
        keyboard_data = {"🇺🇦": f"ua_{uid}", "🇷🇺": f"wrong{i}_{uid}", "🇹🇷": f"wrong{i}_{uid}", "🇬🇷": f"wrong{i}_{uid}"}
        return await self.createKeyboardMarkup(keyboard_data, 2)

    async def getLinkVerificationKeyboard(self, uid: int):
        keyboard_data = {"Я не ботик!": f"verify_{uid}"}
        return await self.createKeyboardMarkup(keyboard_data, 1)
    
    async def getDuzhocoinTransferConfirmationKeyboard(self, sender_id, reciever_id, amount):
        keyboard_data = {"✅": f"sendcoins_{sender_id}_{reciever_id}_{amount}", "❌": f'cancelsendcoins_{sender_id}'}
        return await self.createKeyboardMarkup(keyboard_data, 2)

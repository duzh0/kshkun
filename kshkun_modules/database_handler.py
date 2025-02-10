import aiosqlite
from typing import Callable
from kshkun_modules.logger import KshkunLogger as klog

DEFAULT_USER = {
        'id': 0,
        'custom_system_prompt': '',
        'duzhocoins': 0,
        'menstra_date': ''
    }

DEFAULT_CHAT = {
    "id": 0,
    'shluhobot_on': 0,
    'shluhobot_custom_prompt': ''
}

class KshkunUser:
    def __init__(self, uid: int, custom_system_prompt: str, duzhocoins: int, menstra_date: str):
        self.uid = uid
        self.custom_system_prompt = custom_system_prompt
        self.duzhocoins = duzhocoins
        self.menstra_date = menstra_date

class KshkunChat:
    def __init__(self, chat_id: int, shluhobot_on: bool, shluhobot_custom_prompt: str):
        self.chat_id = chat_id
        self.shluhobot_on = shluhobot_on
        self.shluhobot_custom_prompt = shluhobot_custom_prompt

class DatabaseHandler:
    def __init__(self):
        self.sqlDbsFolder = 'sql_dbs/'
        self.appDataDb = 'app_data.db'

    async def saveInDb(self, filename: str, query: str, *args):   
        try:
            async with aiosqlite.connect(self.sqlDbsFolder + filename) as db:
                await db.execute(query, args)
                await db.commit()
                return None, None
        except Exception as e:
            await klog.log(f"SAVE_IN_DB ERROR: {e}", 'ERROR')
            return None, e
        
    async def loadRowFromDb(self, id: int, table_name: str):
        object_name = table_name.replace("_data", "").strip().upper()
        try:
            async with aiosqlite.connect(self.sqlDbsFolder + self.appDataDb) as db:
                async with db.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [column[0] for column in cursor.description]
                        return dict(zip(columns, row)), None
                    else:
                        await klog.log(f'{object_name} {id} NOT FOUND IN {table_name}', 'WARNING')
                        return False, None
        except Exception as e:
            await klog.log(f'DB LOAD ERROR WHEN HANDLING {object_name} {id} IN {table_name}: {e}', 'ERROR')
            return None, e
    
    async def saveObjectInDb(self, object: dict, default_object: dict, table_name: str):
        object_name = table_name.replace("_data", "").strip().upper()
        required_keys = list(default_object.keys())
        for key in required_keys:
            if key not in object:
                await klog.log(f"{object_name} {object["id"]} IS MISSING A KEY: '{key}', WON'T SAVE", 'ERROR')
                return None, Exception("Missing key") 

        columns = ', '.join(required_keys)
        placeholders = ', '.join('?' for _ in required_keys)
        values = tuple(object[key] for key in required_keys)
        query = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
        result, err = await self.saveInDb(self.appDataDb, query, *values)
        if err != None:
            await klog.log(f"COULD NOT SAVE {object_name} {object["id"]} IN DB: {err}", 'ERROR')

        return result, err

    async def loadUserFromDb(self, uid: int):
        user, err = await self.loadRowFromDb(uid, "user_data")
        if err != None:
            await klog.log(f"LOAD USER FROM DB ERROR: {err}", "ERROR")

        return user, err

    async def saveUserInDb(self, user: dict):
        result, err = await self.saveObjectInDb(user, DEFAULT_USER, "user_data")
        if err != None:
            await klog.log(f"SAVE USER IN DB ERROR: {err}", "ERROR")

        return result, err
    
    async def loadInitializeOrUpdateObject(self, id: int, object_name: str, default_object: dict, load_func: Callable, save_func: Callable):
        object, err = await load_func(id)
        if err != None:
            await klog.log(f"COULD NOT LOAD {object_name} {id} FROM DB: {err}", "ERROR")
            return None, err
        
        if object == False:
            await klog.log(f"{object_name} {id} IS NOT FOUND, INITIALIZING WITH DEFAULT VALUES.")
            object = default_object.copy()
            object['id'] = id
            _, err = await save_func(object)
            if err != None:
                await klog.log(f"COULD NOT SAVE {object_name} {id} IN DB: {err}", "ERROR")
                return None, err
            
            return object, err
        
        updated = False
        for key, value in default_object.items():
            expected_type = type(default_object[key])
            if key not in object:
                await klog.log(f"ADDING KEY '{key}' TO {object_name} {id}")
                object[key] = value
                updated = True
            elif not isinstance(object[key], expected_type):
                await klog.log(f"CHANGING KEY '{key}' IN {object_name} {id} TO DEFAULT, TYPES DON'T MATCH: {type(object[key])} ({expected_type})")
                object[key] = value
                updated = True

        if not updated:
            return object, None
        
        _, err = await save_func(object)
        if err != None:
            await klog.log(f"COULD NOT SAVE UPDATED {object_name} {id} IN DB: {err}", 'ERROR')
            return None, err 

    async def loadInitializeOrUpdateUser(self, uid: int):
        user, err = await self.loadInitializeOrUpdateObject(uid, "USER", DEFAULT_USER, self.loadUserFromDb, self.saveUserInDb)
        if err != None:
            await klog.log(f"ERROR LOAD INIT OR UPDATE USER {uid}: {err}", "ERROR")

        return user, err
    
    async def loadChatFromDb(self, chat_id: int):
        chat, err = await self.loadRowFromDb(chat_id, "chat_data")
        if err != None:
            await klog.log(f"LOAD CHAT FROM DB ERROR: {err}", 'ERROR')

        return chat, err
        
    async def saveChatInDb(self, chat: dict):
        result, err = await self.saveObjectInDb(chat, DEFAULT_CHAT, "chat_data")
        if err != None:
            await klog.log(f"SAVE CHAT IN DB ERROR: {err}", "ERROR")

        return result, err
    
    async def loadInitializeOrUpdateChat(self, chat_id: int):
        chat, err = await self.loadInitializeOrUpdateObject(chat_id, "CHAT", DEFAULT_CHAT, self.loadChatFromDb, self.saveChatInDb)
        if err != None:
            await klog.log(f"LOAD INIT OR UPDATE CHAT ERROR: {err}", "ERROR")

        return chat, err
        
    async def checkFileIdInBuffer(self, filename: str, query: str, *args):
        try:
            async with aiosqlite.connect(self.sqlDbsFolder + filename) as db:
                async with db.execute(query, args) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row[0], None
                    else:
                        return False, None
        except Exception as e:
            await klog.log(f"CHECK_FILE_ID_IN_BUFFER ERROR: {e}", 'ERROR')
            return None, e
import asyncio
import tempfile

from google import genai
from google.genai.types import FileState
from datetime import datetime
from kshkun_modules.logger import KshkunLogger
from kshkun_modules.network_handler import NetworkHandler
from kshkun_modules.database_handler import DatabaseHandler

nh = NetworkHandler()
klog = KshkunLogger()
dbh = DatabaseHandler()

class SQLStrings:
    CHECK_FILE_ID_IN_BUFFER = "SELECT genai_file_name FROM files_buffer WHERE tg_file_id = ?"
    SAVE_GENAI_FILE_IN_BUFFER = "INSERT INTO files_buffer (tg_file_id, genai_file_name) VALUES (?, ?)"
    REMOVE_GENAI_FILE_FROM_BUFFER = "DELETE FROM files_buffer WHERE tg_file_id = ?"

class KshkunGenaiFilesHandler:
    def __init__(self, kshkunBotToken: str, geminiApiKey: str):
        self.kshkunBotToken = kshkunBotToken
        self.filesBufferDb = "files_buffer.db"
        self.client = genai.Client(api_key=geminiApiKey)
        klog.log(f"Initialized KshkunGenaiFilesHandler with\n{kshkunBotToken=}\n{self.filesBufferDb=}\n{geminiApiKey=}")

    async def checkFileIdInBuffer(self, file_id: str):
        result, err = await dbh.checkFileIdInBuffer(self.filesBufferDb, SQLStrings.CHECK_FILE_ID_IN_BUFFER, file_id)
        if err != None:
            await klog.err(f"COULD NOT CHECK FILE ID IN BUFFER: {err}")
        return result, err
    
    async def saveGenaiFileInBuffer(self, file_id: str, genai_file_name: str):
        result, err = await dbh.saveInDb(self.filesBufferDb, SQLStrings.SAVE_GENAI_FILE_IN_BUFFER, file_id, genai_file_name)
        if err != None:
            await klog.err(f"COULD NOT SAVE GENAI FILE IN BUFFER: {err}")
        return result, err

    async def removeGenaiFileFromBuffer(self, file_id: str):
        result, err = await dbh.saveInDb(self.filesBufferDb, SQLStrings.REMOVE_GENAI_FILE_FROM_BUFFER, file_id)
        if err != None:
            await klog.err(f"COULD NOT REMOVE GENAI FILE FROM BUFFER: {err}")
        return result, err
    
    async def uploadFileToGemini(self, media_data, suffix):
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(media_data)
            uploaded_file = await self.client.aio.files.upload(file=temp_file.name)
            if not await self.waitForActive(uploaded_file):
                await klog.warn(f"FILE {uploaded_file.name} UPLOAD TIMED OUT")
        return uploaded_file
    
    async def waitForActive(self, file_object, timeout=60):
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            file_object = await self.client.aio.files.get(name=file_object.name)
            if file_object.state == FileState.ACTIVE:
                return True
            await asyncio.sleep(1)
        return False

    async def uploadMediaToGemini(self, file_ids, suffix, unique_media_ids):
        uploaded_files = []
        for file_id in file_ids:
            unique_id = unique_media_ids.get(file_id)
            genai_file_name_in_buffer, err = await self.checkFileIdInBuffer(unique_id)
            if err != None:
                await klog.err(f"COULD NOT CHECK FILE {unique_id} IN BUFFER: {err}")

            if genai_file_name_in_buffer:
                try:
                    uploaded_file = await self.client.aio.files.get(name=genai_file_name_in_buffer)
                    if await self.waitForActive(uploaded_file, 1):
                        uploaded_files.append(uploaded_file)
                        await klog.log(f"FILE {unique_id} IS IN BUFFER, SKIPPING UPLOAD")
                        continue
                except Exception as e:
                    await klog.err(f"COULD NOT GET FILE {file_id} IN BUFFER FROM GEMINI: {e}; REMOVING FROM BUFFER")
                    result, err = await self.removeGenaiFileFromBuffer(unique_id)
                    if err != None:
                        await klog.err(f"ERROR REMOVING FILE {unique_id} FROM BUFFER: {err}")

            media_data, err = await nh.downloadTgFile(file_id, self.kshkunBotToken)
            if err != None:
                await klog.err(f"ERROR DOWNLOADING FILE {file_id}: {err}")
                continue
            
            uploaded_file = await self.uploadFileToGemini(media_data, suffix)
            uploaded_files.append(uploaded_file)
            result, err = await self.saveGenaiFileInBuffer(unique_id, uploaded_file.name)
            if err != None:
                await klog.err(f"ERROR SAVING FILE {unique_id} IN BUFFER: {err}")

        return uploaded_files
    
    async def uploadAllMediaToGemini(self, media_ids, unique_media_ids):
        all_uploaded_files = []
        media_types = {
            'photos': (media_ids.get('photos', []), ".png"),
            'animations': (media_ids.get('animations', []), ".mp4"),
            'static_stickers': (media_ids.get('stickers', {}).get('static', []), ".webp"),
            'animated_stickers': (media_ids.get('stickers', {}).get('video', []), ".webm"),
            'audio': (media_ids.get('audio', []), ".mp3")
        }

        for media_type, (media_list, extension) in media_types.items():
            all_uploaded_files.extend(await self.uploadMediaToGemini(media_list, extension, unique_media_ids))

        return all_uploaded_files
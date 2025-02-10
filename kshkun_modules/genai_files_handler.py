import asyncio
import tempfile
import google.generativeai as genai

from datetime import datetime
from kshkun_modules.logger import KshkunLogger as klog
from kshkun_modules.network_handler import NetworkHandler as nethandler
from kshkun_modules.database_handler import DatabaseHandler as dbhandler

class KshkunGenaiFilesHandler:
    def __init__(self, kshkunBotToken: str):
        self.kshkunBotToken = kshkunBotToken
        self.filesBufferDb = "files_buffer.db"

    async def checkFileIdInBuffer(self, file_id: str):
        dbh = dbhandler()
        result, err = await dbh.checkFileIdInBuffer(self.filesBufferDb, "SELECT genai_file_name FROM files_buffer WHERE tg_file_id = ?", file_id)
        if err != None:
            await klog.log(f"COULD NOT CHECK FILE ID IN BUFFER: {err}", 'ERROR')
        return result, err
    
    async def saveGenaiFileInBuffer(self, file_id: str, genai_file_name: str):
        dbh = dbhandler()
        result, err = await dbh.saveInDb(self.filesBufferDb, "INSERT INTO files_buffer (tg_file_id, genai_file_name) VALUES (?, ?)", file_id, genai_file_name)
        if err != None:
            await klog.log(f"COULD NOT SAVE GENAI FILE IN BUFFER: {err}", 'ERROR')
        return result, err

    async def removeGenaiFileFromBuffer(self, file_id: str):
        dbh = dbhandler()
        result, err = await dbh.saveInDb(self.filesBufferDb, "DELETE FROM files_buffer WHERE tg_file_id = ?", file_id)
        if err != None:
            await klog.log(f"COULD NOT REMOVE GENAI FILE FROM BUFFER: {err}", 'ERROR')
        return result, err
    
    async def uploadFileToGemini(self, media_data, suffix):
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(media_data)
            uploaded_file = genai.upload_file(temp_file.name)
            if not await self.waitForActive(uploaded_file):
                await klog.log(f"FILE {uploaded_file.name} UPLOAD TIMED OUT", 'WARNING')
        return uploaded_file
    
    async def waitForActive(self, file_object, timeout=120):
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            file_object = genai.get_file(file_object.name)
            if file_object.state == 2:
                return True
            await asyncio.sleep(1)
        return False

    async def uploadMediaToGemini(self, file_ids, suffix, unique_media_ids):
        uploaded_files = []
        nh = nethandler()
        for file_id in file_ids:
            unique_id = unique_media_ids.get(file_id)
            genai_file_name_in_buffer, err = await self.checkFileIdInBuffer(unique_id)
            if err != None:
                await klog.log(f"COULD NOT CHECK FILE {unique_id} IN BUFFER: {err}", 'ERROR')

            if genai_file_name_in_buffer:
                try:
                    uploaded_file = genai.get_file(genai_file_name_in_buffer)
                    if await self.waitForActive(uploaded_file, 1):
                        uploaded_files.append(uploaded_file)
                        await klog.log(f"FILE {unique_id} IS IN BUFFER, SKIPPING UPLOAD")
                        continue
                except Exception as e:
                    await klog.log(f"COULD NOT GET FILE {file_id} IN BUFFER FROM GEMINI: {e}; REMOVING FROM BUFFER", "ERROR")
                    result, err = await self.removeGenaiFileFromBuffer(unique_id)
                    if err != None:
                        await klog.log(f"ERROR REMOVING FILE {unique_id} FROM BUFFER: {err}", 'ERROR')

            media_data, err = await nh.downloadTgFile(file_id, self.kshkunBotToken)
            if err != None:
                await klog.log(f"ERROR DOWNLOADING FILE {file_id}: {err}", 'ERROR')
                continue
            
            uploaded_file = await self.uploadFileToGemini(media_data, suffix)
            uploaded_files.append(uploaded_file)
            result, err = await self.saveGenaiFileInBuffer(unique_id, uploaded_file.name)
            if err != None:
                await klog.log(f"ERROR SAVING FILE {unique_id} IN BUFFER: {err}", 'ERROR')

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
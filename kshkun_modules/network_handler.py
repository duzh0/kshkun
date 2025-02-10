import aiohttp, asyncio, tempfile, re, os, yt_dlp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from kshkun_modules.logger import KshkunLogger as klog
from .data_handler import SimpleDataHandler as sdhandler

class NetworkHandler:
    def __init__(self):
        pass
        
    async def aiohttpGet(self, link: str, params=None, headers=None, content_type='application/json'):
        response = None
        err = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(link, params=params, headers=headers) as result:
                    result.raise_for_status()

                    if content_type == 'application/json':
                        response = await result.json()

                    elif content_type == 'text/plain':
                        response = await result.text()

                    elif content_type == 'bytes':
                        response = await result.read()

                    else:
                        raise ValueError(f"Unsupported content type: {content_type}")

        except Exception as e:
            await klog.log(f'AIOHTTP GET ERROR: {e}', 'ERROR')
            err = e
            return response, err
        
        return response, err

    async def downloadTgFile(self, fileId: str, botToken: str):
        response, err = await self.aiohttpGet(f"https://api.telegram.org/bot{botToken}/getFile?file_id={fileId}")
        if err != None:
            await klog.log(f"TG GET FILE PATH ERROR: {err}", 'ERROR')
            return response, err

        path = response['result']['file_path']
        response, err = await self.aiohttpGet(f"https://api.telegram.org/file/bot{botToken}/{path}", content_type='bytes')
        if err != None:
            await klog.log(f"TG DOWNLOAD FILE ERROR: {err}", 'ERROR')

        return response, err
    
    async def getAndSaveRusoskotData(self, period: str, date: str):
        err = None
        filename = f"russian_losses_{period}.json"
        sdhand = sdhandler()
        data = await sdhand.handleData(filename)
        if not data or not data.get('data').get(date) or period == 'monthly':
            await klog.log(f"RU_LOSSES FOR: {period}, {date}, COULD NOT GET DATA OR DATA FOR DATE", 'ERROR' if period == 'daily' else 'INFO')
            data, err = await self.aiohttpGet(f"https://russian-casualties.in.ua/api/v1/data/json/{period}")
            if err != None:
                await klog.log(f"RU_LOSSES ERROR: DATA FETCH ERROR: {err}", 'ERROR')
            
            if data and data.get('data').get(date):
                await sdhand.handleData(filename, data)
                return data.get('data').get(date), data.get('legend'), err
            
        return data.get('data').get(date), data.get('legend'), err
    
    async def getRuLosses(self):
        yesterday = f'{(datetime.now() - timedelta(days=1)).strftime('%Y.%m.%d')}'
        thisMonth = f'{datetime.now().strftime('%Y.%m')}'

        yesterdayData, legend, err1 = await self.getAndSaveRusoskotData('daily', yesterday)
        if err1 != None:
            await klog.log(f"RU_LOSSES_DAILY ERROR: {err1}", 'ERROR')

        thisMonthData, legend, err2 = await self.getAndSaveRusoskotData('monthly', thisMonth)
        if err2 != None:
            await klog.log(f"RU_LOSSES_MONTHLY ERROR: {err2}", 'ERROR')

        return yesterdayData, thisMonthData, legend, err1, err2
        
    async def extractTextFromWebsite(self, url: str):
        crawled_tuple = (url, '')
        err = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    for tag in soup(['script', 'style', 'footer', 'nav']):
                        tag.decompose()

                    for link in soup.find_all('a'):
                        link.replace_with("[LINK]")

                    processed_text = re.sub(r'(\[LINK]\s*)+', lambda m: f"[{len(m.group(0)) // len('[LINK]')} LINKS]", soup.get_text(separator=' '))
                    processed_text = processed_text.replace('[1 LINKS]', '[LINK]')
                    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
                    crawled_tuple = (url, processed_text[:3000])
        except Exception as e:
            await klog.log(f'EXTRACTING TEXT ERROR: {e}', 'ERROR')
            err = e
            
        return crawled_tuple, err
        
    async def fetchCrawledContent(self, search_results: dict):
        crawled_content = []
        err = None
        try:
            for item in search_results['items']:
                url = item['link']
                crawled_tuple, err = await self.extractTextFromWebsite(url)
                if err != None:
                    await klog.log(f'FETCH_CRAWLED_CONTENT ERROR: {err}', 'ERROR')
                crawled_content.append(crawled_tuple)
        except Exception as e:
            await klog.log(f'FETCH_CRAWLED_CONTENT ERROR: {e}', 'ERROR')
            err = e

        return crawled_content, err
    
    async def downloadYtVideo(self, yt_link: str):
        temp_file_path = None
        err = None
        try:
            ydl_opts = {
                'format': 'bestvideo[height<=?480][height>=?360]+bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }

            with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
                temp_file_path = tmpfile.name
                ydl_opts['outtmpl'] = temp_file_path

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(yt_link, download=False)
                    if info_dict:
                        video_title = info_dict.get('title', 'N/A')
                        video_duration_seconds = info_dict.get('duration', 0)
                        await klog.log(f"YT-DLP: Downloading {video_title} ({video_duration_seconds} seconds)")
                        await asyncio.to_thread(ydl.download, [yt_link])

                        output_filepath = temp_file_path + ".mp4"
                        await klog.log(f"YT-DLP Output Filepath: {output_filepath}")

                        if not os.path.exists(output_filepath) or os.path.getsize(output_filepath) == 0:
                            err = Exception(f"Downloaded file is empty or not found at {output_filepath}")
                            await klog.log(f'YT-DLP DOWNLOAD ERROR: {err}', 'ERROR')
                            return None, err

                        return output_filepath, None

                    else:
                        err = Exception("yt-dlp could not extract video information.")
                        await klog.log(f'YT-DLP ERROR: Could not extract video info for {yt_link}', 'ERROR')
                        return None, err

        except Exception as e:
            await klog.log(f'YT-DLP DOWNLOAD ERROR: {e}', 'ERROR')
            err = e
            return None, err

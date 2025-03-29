import json, asyncio
from .logger import KshkunLogger

klog = KshkunLogger()

class SimpleDataHandler:
    def __init__(self):
        klog.log("Initialized SimpleDataHandler")

    def baseHandleData(self, filename: str, data=None):
        try:
            suffix = 'JSON' if filename.endswith('.json') else 'TXT' if filename.endswith('.txt') else None
            folder = 'json_files/' if suffix == 'JSON' else 'txt_files/' if suffix == 'TXT' else None
            path = folder + filename
            save_or_load = 'LOAD' if data == None else 'SAVE'
            with open(path, 'w' if data else 'r') as file:
                if suffix == 'JSON':
                    if save_or_load == 'SAVE':
                        json.dump(data, file, ensure_ascii=False, indent=4) # had some problems with saving an empty list, must check later
                    else:    
                        return json.load(file)
                    
                elif suffix == 'TXT':
                    if save_or_load == 'SAVE':
                        file.write(data)
                    else:
                        return file.read()
                    
                else:
                    raise f'Unsupported file type: .txt or .json expected, got {path}'
                
        except Exception as e:
            klog.err(f'{suffix or "DO_DATA"}_{save_or_load} ERROR: {e}')
            return None

    def handleDataSync(self, filename: str, data=None):
        return self.baseHandleData(filename, data)

    async def handleData(self, filename: str, data=None):
        return await asyncio.to_thread(self.baseHandleData, filename, data)
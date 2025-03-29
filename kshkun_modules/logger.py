import asyncio
from datetime import datetime

class Colors:
    INFO = '\033[92m'
    WARN = '\033[93m'
    ERR = '\033[91m'
    BLUE = '\033[94m' #unused

class Formats:
    BOLD = '\033[1m'
    END = '\033[0m'

class _CompletedAwaitable:
    def __await__(self):
        return asyncio.sleep(0).__await__()

class KshkunLogger:
    def __init__(self):
        self.colors = Colors()
        self.formats = Formats()

    def baseLog(self, text: str, type: str, cutoff: int):
        if not text:
            return
        color = type
        bold = self.formats.BOLD
        end = self.formats.END
        date = datetime.now().strftime('%d.%m.%y %H:%M:%S')
        date_formatted = f"{color}{bold}{date}{end}"
        text_formatted = f"{color}{text[:cutoff]}{end}"
        print(f"{date_formatted} {text_formatted}")

    async def logToThread(self, text: str, type: str, cutoff: int):
        await asyncio.to_thread(self.baseLog, text, type, cutoff)

    def log(self, text: str, cutoff:int=None):
        return self.schedule(text, self.colors.INFO, cutoff)

    def warn(self, text: str, cutoff:int=None):
        return self.schedule(text, self.colors.WARN, cutoff)

    def err(self, text: str, cutoff:int=None):
        return self.schedule(text, self.colors.ERR, cutoff)

    def schedule(self, text: str, type: str, cutoff: int):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.logToThread(text, type, cutoff))
            return _CompletedAwaitable()
        else:
            asyncio.create_task(self.logToThread(text, type, cutoff))
            return _CompletedAwaitable()
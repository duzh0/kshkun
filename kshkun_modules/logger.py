from datetime import datetime

class KshkunLogger:
    def __init__(self):
        pass

    def slog(text, type='INFO', cutoff=None):
        if not text:
            return
        colors = {'INFO': '\033[92m', 'WARNING': '\033[93m', 'ERROR': '\033[91m'}
        color = colors.get(type) or colors.get("INFO")
        bold_start = '\033[1m'
        bold_end = '\033[0m'
        date = datetime.now().strftime('%d.%m.%y %H:%M:%S')
        date_formatted = f"{bold_start}{date}{bold_end}"
        print(f"{color}{date_formatted}{color} {text[:cutoff]}\033[0m")

    async def log(text, type='INFO', cutoff=None):
        if not text:
            return
        colors = {'INFO': '\033[92m', 'WARNING': '\033[93m', 'ERROR': '\033[91m'}
        color = colors.get(type) or colors.get("INFO")
        bold_start = '\033[1m'
        bold_end = '\033[0m'
        date = datetime.now().strftime('%d.%m.%y %H:%M:%S')
        date_formatted = f"{bold_start}{date}{bold_end}"
        print(f"{color}{date_formatted}{color} {text[:cutoff]}\033[0m")
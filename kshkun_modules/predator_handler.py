import re
import random
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from kshkun_modules.data_handler import SimpleDataHandler as sdhandler

class PredatorHandler:
    def __init__(self):
        pass

    async def getPredatorMsg(max_length:int=2000):
        keywords = ['русоскот', 'русосвин', 'крокус', 'русня', 'хуйло', 'чучело']
        keyword = random.choice(keywords)
        sdh = sdhandler()
        msgs = await sdh.handleData('msgs.json')
        filtered_msgs = [m for m in msgs if keyword in m.lower() and len(m) < max_length]  
        return random.choice(filtered_msgs)
    
    async def loadFrequencies(forced:bool=False):
        sdh = sdhandler()
        file = await sdh.handleData('freqs.json')
        current_time = datetime.now()
        if (current_time - datetime.fromtimestamp(file['timestamp']) > timedelta(days=7)) or forced:
            f = defaultdict(Counter)
            for m in await sdh.handleData('msgs.json'):
                tks = []
                for t in re.findall(r'\b\w+\b|.', m.lower()):
                    if t.strip():
                        tks.append(t)
                tks.append('<END>')
                for i in range(len(tks) - 1):
                    f[tks[i]][tks[i + 1]] += 1
            await sdh.handleData('freqs.json', {'timestamp': current_time.timestamp(), 'word_frequencies': {w: dict(sorted(f_freq.items(), key=lambda x: x[1], reverse=True)) for w, f_freq in f.items()}})
        else:
            f = defaultdict(Counter, {word: Counter(follower) for word, follower in file['word_frequencies'].items()})

        return f

    async def generateMsg(self, seed: str):
        word_frequencies = await self.loadFrequencies()
        start_word = seed or random.choice(list(word_frequencies.keys()))
        msg = [start_word]
        current_word = start_word
        for _ in range(random.randint(1, 100) - 1):
            if current_word not in word_frequencies or not word_frequencies[current_word]:
                break
            next_words = word_frequencies[current_word]
            current_word = random.choices(list(next_words.keys()), weights=next_words.values())[0]
            if current_word == '<END>':
                break
            msg.append(current_word)

        return ' '.join(msg) + "."
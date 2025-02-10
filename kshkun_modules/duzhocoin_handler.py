from kshkun_modules.logger import KshkunLogger as klog
from kshkun_modules.database_handler import DatabaseHandler as dbhandler

class DuzhocoinHandler:
    def __init__(self):
        pass

    async def transferDuzhocoins(sender_id: int, reciever_id: int, amount: int):
        dbh = dbhandler()
        sender, err = await dbh.loadInitializeOrUpdateUser(sender_id)
        if err != None:
            await klog.log(f'COULD NOT LOAD DUZHOCOINS SENDER {sender_id} FROM DB: {err}', 'ERROR')
            error_text = 'сталася помилочка при завантаженні інформації про відправника.'
            return error_text, err
        
        reciever, err = await dbh.loadInitializeOrUpdateUser(reciever_id)
        if err != None:
            await klog.log(f'COULD NOT LOAD DUZHOCOINS RECIEVER {reciever_id} FROM DB: {err}', 'ERROR')
            error_text = 'сталася помилочка при завантаженні інформації про отримувача.'
            return error_text, err

        if sender['duzhocoins'] < amount:
            error_text = f'недостатньо дужокоїнів. баланс: {sender["duzhocoins"]}'
            err = ValueError
            return error_text, err

        sender['duzhocoins'] -= amount
        reciever['duzhocoins'] += amount

        result, err = await dbh.saveUserInDb(sender)
        if err != None:
            await klog.log(f'COULD NOT SAVE DUZHOCOINS SENDER {sender_id} IN DB: {err}', 'ERROR')
            error_text = 'сталася помилочка при збереженні відправника в датабазі.'
            return error_text, err

        result, err = await dbh.saveUserInDb(reciever)
        if err != None:
            await klog.log(f'COULD NOT SAVE DUZHOCOINS RECIEVER {reciever_id} IN DB: {err}', 'ERROR')
            error_text = 'сталася помилочка при збереженні отримувача в датабазі.'
            return error_text, err

        return None, None

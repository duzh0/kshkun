from datetime import datetime
from .data_handler import SimpleDataHandler as sdhandler
from .database_handler import DatabaseHandler as dbhandler
from .logger import KshkunLogger as klog


class MenstruationHandler():
    def __init__(self, menstruationStagesDescriptionFilename):
        self.menstruationStagesDescriptionPath = menstruationStagesDescriptionFilename
        self.menstruationStagesDescription = self.loadDataSync(self.menstruationStagesDescriptionPath)
        if self.menstruationStagesDescription == None:
            klog.slog(f"ERROR LOADING MENSTRUATION STAGES DESCRIPTION", 'ERROR')

        klog.slog(f"Stages description: {self.menstruationStagesDescription}")

    def loadDataSync(self, path: str):
        sdh = sdhandler()
        return sdh.handleDataSync(path)

    async def getMenstrualCycleDay(self, uid: int):
        days_passed_in_cycle = None
        err = None
        start_date, err = await self.getMenstruationStartDate(uid)
        if err != None:
            await klog.log(f"ERROR GETTING MENSTRUAL CYCLE DAY: {err}", 'ERROR')
            return days_passed_in_cycle, err

        if not start_date:
            err = Exception("Menstruation start date not found")
            return days_passed_in_cycle, err
        
        today = datetime.today().date()
        days_passed = (today - start_date).days
        cycle_length = self.menstruationStagesDescription.get('default_cycle_length')
        days_passed_in_cycle = days_passed % cycle_length + 1
        return days_passed_in_cycle, err

    async def getMenstruationStartDate(self, uid: int):
        err = None
        start_date = None
        dbh = dbhandler()
        user, err = await dbh.loadInitializeOrUpdateUser(uid)
        if err != None:
            await klog.log(f"ERROR LOADING USER {uid}: {err}", 'ERROR')
            return start_date, err
        
        if not user or not user.get('menstra_date'):
            return start_date, err
        
        start_date_str = user.get('menstra_date')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        return start_date, err

    async def getCurrentMenstruationStage(self, uid: int):
        state = None
        days_passed_in_cycle, err = await self.getMenstrualCycleDay(uid)
        if err != None:
            await klog.log(f"GET MENSTRUATION STAGE ERROR: {err}", "ERROR")
            return state, err

        for stage in self.menstruationStagesDescription.get('stages'):
            start_day = stage.get('start_day')
            end_day = stage.get('end_day')
            if start_day <= days_passed_in_cycle <= end_day:
                state = stage
                break

        return state.copy(), err
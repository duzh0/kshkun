class Quiz:
    def __init__(self, chat_id: int, msg_id: int, correct_answer: int, participants: dict, uids_answered_correctly: list):
        self.chat_id = chat_id
        self.msg_id = msg_id
        self.correct_answer = correct_answer
        self.participants = participants
        self.uids_answered_correctly = uids_answered_correctly

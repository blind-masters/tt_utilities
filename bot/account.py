from TeamTalk5 import UserRight, UserAccount, UserType, TextMessage

class Account():
    def __init__(self):
        super().__init__()

    def calculate_user_rights(self, rights: list[int]) -> int:
        """Calculates the user rights based on the provided simplified numbers."""
        user_rights_mapping = {
            1: UserRight.USERRIGHT_MULTI_LOGIN,
            2: UserRight.USERRIGHT_VIEW_ALL_USERS,
            3: UserRight.USERRIGHT_CREATE_TEMPORARY_CHANNEL,
            4: UserRight.USERRIGHT_BAN_USERS,
            5: UserRight.USERRIGHT_DOWNLOAD_FILES,
            6: UserRight.USERRIGHT_KICK_USERS,
            7: UserRight.USERRIGHT_LOCKED_NICKNAME,
            8: UserRight.USERRIGHT_LOCKED_STATUS,
            9: UserRight.USERRIGHT_MODIFY_CHANNELS,
            10: UserRight.USERRIGHT_MOVE_USERS,
            11: UserRight.USERRIGHT_OPERATOR_ENABLE,
            12: UserRight.USERRIGHT_RECORD_VOICE,
            13: UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST,
            14: UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL,
            15: UserRight.USERRIGHT_TEXTMESSAGE_USER,
            16: UserRight.USERRIGHT_TRANSMIT_DESKTOP,
            17: UserRight.USERRIGHT_TRANSMIT_DESKTOPINPUT,
            18: UserRight.USERRIGHT_TRANSMIT_MEDIAFILE,
            19: UserRight.USERRIGHT_TRANSMIT_MEDIAFILE_AUDIO,
            20: UserRight.USERRIGHT_TRANSMIT_MEDIAFILE_VIDEO,
            21: UserRight.USERRIGHT_TRANSMIT_VIDEOCAPTURE,
            22: UserRight.USERRIGHT_TRANSMIT_VOICE,
            23: UserRight.USERRIGHT_UPDATE_SERVERPROPERTIES,
            24: UserRight.USERRIGHT_UPLOAD_FILES,
            25: UserRight.USERRIGHT_VIEW_HIDDEN_CHANNELS,
        }

        total_rights = 0
        for right_number in rights:
            if right_number in user_rights_mapping:
                total_rights |= user_rights_mapping[right_number]
            else:
                self.privateMessage(textmessage.nFromUserID, f"Invalid right number: {right_number}")
        return total_rights

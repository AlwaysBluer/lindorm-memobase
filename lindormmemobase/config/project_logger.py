import logging
import json

class ProjectLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, user_id: str, message: str):
        self.logger.debug(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def info(self, user_id: str, message: str):
        self.logger.info(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def warning(self, user_id: str, message: str):
        self.logger.warning(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def error(
        self, user_id: str, message: str, exc_info: bool = False
    ):
        self.logger.error(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message,
            exc_info=exc_info,
        )
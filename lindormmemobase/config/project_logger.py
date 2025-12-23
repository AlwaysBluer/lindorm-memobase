import logging
import json

class ProjectLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, user_id: str, message: str, project_id: str | None = None):
        self.logger.debug(
            json.dumps({"user_id": str(user_id), "project_id": str(project_id) if project_id else None})
            + " | "
            + message
        )

    def info(self, user_id: str, message: str, project_id: str | None = None):
        self.logger.info(
            json.dumps({"user_id": str(user_id), "project_id": str(project_id) if project_id else None})
            + " | "
            + message
        )

    def warning(self, user_id: str, message: str, project_id: str | None = None):
        self.logger.warning(
            json.dumps({"user_id": str(user_id), "project_id": str(project_id) if project_id else None})
            + " | "
            + message
        )

    def error(
        self, user_id: str, message: str, exc_info: bool = False, project_id: str | None = None
    ):
        self.logger.error(
            json.dumps({"user_id": str(user_id), "project_id": str(project_id) if project_id else None})
            + " | "
            + message,
            exc_info=exc_info,
        )
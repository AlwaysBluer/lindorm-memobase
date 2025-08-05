"""
Initialize logger, encoder, and config.
"""
import logging

class ConstantsTable:
    topic = "topic"
    sub_topic = "sub_topic"
    memo = "memo"
    update_hits = "update_hits"

    roleplay_plot_status = "roleplay_plot_status"


class BufferStatus:
    idle = "idle"
    processing = "processing"
    done = "done"
    failed = "failed"


# Add standard formatter and handler
class Colors:
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    END = "\033[0m"


formatter = logging.Formatter(
    f"{Colors.BOLD}{Colors.BLUE}%(name)s |{Colors.END}  %(levelname)s - %(asctime)s  -  %(message)s"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)



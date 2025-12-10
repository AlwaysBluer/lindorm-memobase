import logging
from .color import Colors
from .config import Config
from .project_logger import ProjectLogger
import tiktoken


# 1. Add logger
LOG = logging.getLogger("memobase")
LOG.setLevel(logging.INFO)
formatter = logging.Formatter(
    f"{Colors.BOLD}{Colors.BLUE}%(name)s |{Colors.END}  %(levelname)s - %(asctime)s  -  %(message)s"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
LOG.addHandler(handler)

# 2. Add encoder for tokenize strings
ENCODER = tiktoken.encoding_for_model("gpt-4o")


TRACE_LOG = ProjectLogger(LOG)

# Config should be loaded by users, not globally
# But some legacy code still expects a global CONFIG, so provide a fallback
try:
    CONFIG = Config.load_config()
except Exception:
    # If no config file exists or API key is missing, create a minimal config
    CONFIG = None

# Explicitly declare what can be imported from this package
__all__ = [
    "Colors",
    "Config",
    "ProjectLogger",
    "LOG",
    "ENCODER",
    "TRACE_LOG",
    "CONFIG",
]
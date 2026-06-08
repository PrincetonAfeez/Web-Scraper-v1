"""Process exit code constants."""

OK = 0
ERROR = 1
CONFIG_ERROR = 2
INTERRUPTED = 130  # 128 + SIGINT, the conventional shell code for Ctrl-C

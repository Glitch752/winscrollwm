ANSI_RESET = "\033[0m"
ANSI_RED = "\033[91m"

def log_error(*args):
    print(f"{ANSI_RED}[ERROR]{ANSI_RESET} {' '.join(map(str, args))}")

def log_info(*args):
    print(f"[INFO] {' '.join(map(str, args))}")
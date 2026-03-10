import sys
import os

if len(sys.argv) < 2:
    print("Usage: python clear_chat_history.py <session_file>")
    sys.exit(1)

session_file = sys.argv[1]

if os.path.exists(session_file):
    with open(session_file, "w", encoding="utf-8") as f:
        f.write("[]\n")
    print(f"Cleared chat history in {session_file}")
else:
    print(f"File {session_file} does not exist. Nothing to clear.")

from hwid_auth import authenticate
from automation import start_main_application
from updater import update_app
import sys

def main():
    if authenticate():
        print("Authentication successful.")

        # Check for updates
        if update_app():
            print("Application updated. Please restart.")
            sys.exit(0)

        print("Starting main application...")
        start_main_application()
    else:
        print("Access denied. Exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
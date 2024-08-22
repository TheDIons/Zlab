import subprocess
import sys

def get_hwid():
    try:
        result = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].strip()
        return result
    except:
        print("Error: Unable to retrieve HWID.")
        sys.exit(1)

def is_hwid_allowed(hwid, allowed_hwids):
    return hwid in allowed_hwids

def authenticate(allowed_hwids):
    hwid = get_hwid()

    if is_hwid_allowed(hwid, allowed_hwids):
        print("Authentication successful. HWID is allowed.")
        return True
    else:
        print("Authentication failed. HWID is not in the allowed list.")
        return False
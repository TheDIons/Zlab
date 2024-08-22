import requests
import os
import sys
import zipfile
import shutil

UPDATE_URL = "https://api.github.com/repos/TheDIons/Zlab/releases/latest"
CURRENT_VERSION = "1.0.0"  # Update this manually when you release a new version

def check_for_updates():
    try:
        response = requests.get(UPDATE_URL)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release['tag_name']

        if latest_version > CURRENT_VERSION:
            print(f"Update available: {latest_version}")
            return latest_release['assets'][0]['browser_download_url']
        else:
            print("No updates available.")
            return None
    except requests.RequestException as e:
        print(f"Error checking for updates: {e}")
        return None

def download_update(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open("update.zip", "wb") as f:
            f.write(response.content)
        return True
    except requests.RequestException as e:
        print(f"Error downloading update: {e}")
        return False

def apply_update():
    if not os.path.exists("update.zip"):
        print("No update file found.")
        return False

    try:
        with zipfile.ZipFile("update.zip", 'r') as zip_ref:
            zip_ref.extractall("update")

        # Replace old files with new ones
        for root, dirs, files in os.walk("update"):
            for file in files:
                src_path = os.path.join(root, file)
                dst_path = os.path.join(os.path.dirname(sys.executable), os.path.relpath(src_path, "update"))
                os.replace(src_path, dst_path)

        # Clean up
        shutil.rmtree("update")
        os.remove("update.zip")

        print("Update successfully applied.")
        return True
    except Exception as e:
        print(f"Error applying update: {e}")
        return False

def update_app():
    update_url = check_for_updates()
    if update_url:
        if download_update(update_url):
            if apply_update():
                print("Please restart the application to use the new version.")
                return True
    return False
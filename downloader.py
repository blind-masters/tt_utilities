import bs4
import patoolib
import requests
import os
import platform
import shutil
import sys
from tqdm import tqdm

SDK_BASE_URL = "https://bearware.dk/teamtalksdk"
TARGET_FOLDER_NAME = "TeamTalk_DLL"
DOWNLOAD_FILE = "ttsdk.7z"

def get_url_suffix_from_platform() -> str:
    machine = platform.machine()
    if sys.platform == "win32":
        architecture = platform.architecture()
        if machine == "AMD64" or machine == "x86":
            if architecture[0] == "64bit":
                return "win64"
            else:
                return "win32"
        else:
            sys.exit("Native Windows on ARM is not supported")
    elif sys.platform == "darwin":
        sys.exit("Darwin is not supported")
    else:
        if machine == "AMD64" or machine == "x86_64":
            return "ubuntu22_x86_64"
        elif "arm" in machine:
            return "raspbian_armhf"
        else:
            sys.exit("Your architecture is not supported")

def download_file_from_url(url: str, file_path: str) -> None:
    """Downloads a file from a URL with a TQDM progress bar."""
    print(f"Downloading from: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 4096
            
            with tqdm(total=total_size, unit='iB', unit_scale=True, desc=os.path.basename(file_path)) as progress_bar:
                with open(file_path, "wb") as f:
                    for data in r.iter_content(block_size):
                        progress_bar.update(len(data))
                        f.write(data)

            if total_size != 0 and progress_bar.n != total_size:
                print("Error, download might be incomplete.", file=sys.stderr)
                sys.exit(1)

        print("Download complete.")
    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred while downloading the file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def do_download_and_extract() -> None:
    """Handles the entire process of downloading and extracting the SDK."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    try:
        print(f"Fetching available SDK versions from {SDK_BASE_URL}...")
        r = requests.get(SDK_BASE_URL, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to access the TeamTalk SDK page: {e}", file=sys.stderr)
        sys.exit(1)

    page = bs4.BeautifulSoup(r.text, features="html.parser")
    try:
        versions = page.find_all("li")
        version_link = [i for i in versions if "5.15" in i.text][-1].a
        version = version_link.get("href").strip('/')
    except (AttributeError, IndexError):
        print("Could not find a suitable SDK version (5.15x) on the page.", file=sys.stderr)
        sys.exit(1)

    platform_suffix = get_url_suffix_from_platform()
    download_url = f"{SDK_BASE_URL}/{version}/tt5sdk_{version}_{platform_suffix}.7z"    
    download_file_from_url(download_url, DOWNLOAD_FILE)

    print(f"Extracting {DOWNLOAD_FILE}...")
    try:
        patoolib.extract_archive(DOWNLOAD_FILE, outdir=".", verbosity=-1)
        print("Extraction complete.")
    except Exception as e:
        print(f"Failed to extract archive: {e}", file=sys.stderr)
        print("Please ensure 7-Zip is installed and accessible in your system's PATH.", file=sys.stderr)
        if os.path.exists(DOWNLOAD_FILE):
            os.remove(DOWNLOAD_FILE) # Clean up failed download
        sys.exit(1)

    extracted_parent_folder = f"tt5sdk_{version}_{platform_suffix}"
    source_path = os.path.join(extracted_parent_folder, "Library", TARGET_FOLDER_NAME)

    print(f"Moving required folders...")
    if not os.path.isdir(source_path):
        print(f"Error: Expected folder '{source_path}' not found in archive.", file=sys.stderr)
        os.remove(DOWNLOAD_FILE)
        shutil.rmtree(extracted_parent_folder)
        sys.exit(1)
        
    if os.path.exists(TARGET_FOLDER_NAME):
        shutil.rmtree(TARGET_FOLDER_NAME)
    shutil.move(source_path, ".")
    print("Move complete.")

    print("Cleaning up...")
    os.remove(DOWNLOAD_FILE)
    shutil.rmtree(extracted_parent_folder)
    print("Cleanup complete.")

def run_sdk_setup():
    """Main script execution for SDK setup."""
    print("--- TeamTalk SDK Setup ---")
    if os.path.exists(TARGET_FOLDER_NAME):
        while True:
            response = input(f"The folder '{TARGET_FOLDER_NAME}' already exists. Would you like to replace it? [y/n]: ").lower().strip()
            if response in ['y', 'yes']:
                print(f"Proceeding with re-download. The existing folder will be replaced.")
                do_download_and_extract()
                break
            elif response in ['n', 'no']:
                print("Skipping TeamTalk SDK download as requested.")
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
    else:
        do_download_and_extract()
    print("--- TeamTalk SDK Setup Finished ---")

def main():
    """Main entry point. Dispatches to the correct function based on arguments."""
    if len(sys.argv) == 4 and sys.argv[1] == '--download':
        url = sys.argv[2]
        output_path = sys.argv[3]
        download_file_from_url(url, output_path)
    # Otherwise, run the default SDK setup
    else:
        run_sdk_setup()

if __name__ == "__main__":
    main()

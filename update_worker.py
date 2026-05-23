import urllib.request
import json
import re
import os
from PySide6.QtCore import QThread, Signal

class UpdateCheckWorker(QThread):
    finished_check = Signal(object) # Emits latest release dict or None

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        url = "https://api.github.com/repos/woo2koon/Webtoon-Script-Manager/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "Webtoon-Script-Manager-Client"})
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    tag_name = data.get("tag_name", "")
                    
                    if tag_name:
                        if self.is_newer(self.current_version, tag_name):
                            self.finished_check.emit(data)
                            return
        except Exception as e:
            print(f"Update check error: {e}")
        
        self.finished_check.emit(None)

    def parse_version(self, v_str):
        digits = re.findall(r'\d+', v_str)
        return [int(d) for d in digits]

    def is_newer(self, curr_str, latest_str):
        try:
            curr = self.parse_version(curr_str)
            latest = self.parse_version(latest_str)
            maxlen = max(len(curr), len(latest))
            curr += [0] * (maxlen - len(curr))
            latest += [0] * (maxlen - len(latest))
            return latest > curr
        except Exception:
            return False


class UpdateDownloadWorker(QThread):
    progress = Signal(int)
    finished_download = Signal(str)
    error = Signal(str)

    def __init__(self, download_url, dest_path):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path
        self.is_running = True

    def run(self):
        try:
            req = urllib.request.Request(self.download_url, headers={"User-Agent": "Webtoon-Script-Manager-Client"})
            with urllib.request.urlopen(req, timeout=20) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192
                
                os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
                
                with open(self.dest_path, 'wb') as f:
                    while self.is_running:
                        block = response.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        downloaded += len(block)
                        
                        if total_size > 0:
                            percent = int(downloaded / total_size * 100)
                            self.progress.emit(percent)
                            
                if self.is_running:
                    self.finished_download.emit(self.dest_path)
                else:
                    if os.path.exists(self.dest_path):
                        try:
                            os.remove(self.dest_path)
                        except:
                            pass
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

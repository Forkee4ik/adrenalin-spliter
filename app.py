import sys
import os
import json
import re
import time
import subprocess
import threading
import queue
import shutil
import logging
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, 
                             QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QCheckBox, QFileDialog, QMessageBox,
                             QTreeWidget, QTreeWidgetItem, QTabWidget, QWidget, QProgressBar,
                             QComboBox)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QSharedMemory

import winreg

CONFIG_FILE = "config.json"
APP_NAME = "AdrenalinSplitter"

# --- Logging setup ---
def _setup_logging():
    log_dir = Path(os.environ.get('APPDATA', '.')) / APP_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "muxer_debug.log"
    logger = logging.getLogger("muxer")
    logger.setLevel(logging.DEBUG)
    # Ротация: перезаписываем лог при каждом запуске
    fh = logging.FileHandler(str(log_file), mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
                            datefmt='%H:%M:%S')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.info(f"Log started. File: {log_file}")
    return logger

log = _setup_logging()

TRANSLATIONS = {
    "ru": {
        "settings_title": "Настройки Adrenalin Splitter",
        "tab_settings": "Настройки",
        "tab_manual": "Ручной режим",
        "folder_label": "Папка сохранений:",
        "browse_btn": "Обзор...",
        "auto_mux": "Автоматически соединять новые видео",
        "auto_start": "Запускать вместе с Windows",
        "delete_orig": "Удалять оригиналы после объединения",
        "move_orig": "Перемещать оригиналы в подпапку 'original' (если не удаляются)",
        "save_btn": "Сохранить",
        "saved_title": "Сохранено",
        "saved_msg": "Настройки успешно сохранены!",
        "scan_btn": "Сканировать папку",
        "tree_header": "Файлы для объединения",
        "queue_empty": "Очередь пуста",
        "merge_btn": "Соединить выбранные",
        "cancel_btn": "Отменить очередь",
        "browse_title": "Выберите папку сохранений AMD Adrenalin",
        "err_title": "Ошибка",
        "err_no_folder": "Не выбрана папка или папка не существует.",
        "res_title": "Результат",
        "res_no_files": "Новых пар (видео + микрофон) не найдено.",
        "already_running": "Программа уже запущена и находится в трее!",
        "tray_settings": "Настройки / Ручной режим",
        "tray_quit": "Выход",
        "found_new": "Найдено: {name}. Добавлено в очередь...",
        "success_title": "Успешно",
        "success_msg": "Файл {name} объединен!",
        "fail_msg": "Ошибка {name}: {msg}",
        "processing": "Обработка очереди: {cur} из {tot}...",
        "timeout": "Таймаут: файлы заняты слишком долго.",
        "ffmpeg_err": "Ошибка FFmpeg или процесс отменен",
        "language": "Язык (Language):"
    },
    "en": {
        "settings_title": "Adrenalin Splitter Settings",
        "tab_settings": "Settings",
        "tab_manual": "Manual Mode",
        "folder_label": "Save Folder:",
        "browse_btn": "Browse...",
        "auto_mux": "Automatically merge new videos",
        "auto_start": "Start with Windows",
        "delete_orig": "Delete originals after merging",
        "move_orig": "Move originals to 'original' subfolder (if not deleted)",
        "save_btn": "Save",
        "saved_title": "Saved",
        "saved_msg": "Settings successfully saved!",
        "scan_btn": "Scan Folder",
        "tree_header": "Files to merge",
        "queue_empty": "Queue is empty",
        "merge_btn": "Merge selected",
        "cancel_btn": "Cancel Queue",
        "browse_title": "Select AMD Adrenalin save folder",
        "err_title": "Error",
        "err_no_folder": "Folder not selected or does not exist.",
        "res_title": "Result",
        "res_no_files": "No new pairs (video + mic) found.",
        "already_running": "Application is already running in the tray!",
        "tray_settings": "Settings / Manual Mode",
        "tray_quit": "Quit",
        "found_new": "Found: {name}. Added to queue...",
        "success_title": "Success",
        "success_msg": "File {name} merged!",
        "fail_msg": "Error {name}: {msg}",
        "processing": "Processing queue: {cur} out of {tot}...",
        "timeout": "Timeout: files are locked for too long.",
        "ffmpeg_err": "FFmpeg error or process cancelled",
        "language": "Language (Язык):"
    }
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def setup_autostart(enable):
    key = winreg.HKEY_CURRENT_USER
    sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        registry_key = winreg.OpenKey(key, sub_key, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            if getattr(sys, 'frozen', False):
                exe_path = f'"{sys.executable}"'
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            cmd_line = f'{exe_path} --autostart'
            winreg.SetValueEx(registry_key, APP_NAME, 0, winreg.REG_SZ, cmd_line)
            try:
                stored_value, _ = winreg.QueryValueEx(registry_key, APP_NAME)
                print(f"Autostart registry set to: {stored_value}")
            except Exception:
                pass
        else:
            try:
                winreg.DeleteValue(registry_key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(registry_key)
    except Exception as e:
        print(f"Autostart error: {e}")

class ConfigManager:
    def __init__(self):
        self.config = {
            "watch_dir": "",
            "auto_mux": False,
            "auto_start": False,
            "delete_originals": False,
            "move_originals": False,
            "language": "ru"
        }
        self.config_file = self._get_config_path()
        self.load()

    def _get_config_path(self):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(appdata, APP_NAME)
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create config directory {config_dir}: {e}")
            # Fallback to user home directory
            config_dir = os.path.join(os.path.expanduser("~"), APP_NAME)
            os.makedirs(config_dir, exist_ok=True)
        
        target_path = os.path.join(config_dir, "config.json")
        print(f"Config path: {target_path}")
        
        if not os.path.exists(target_path):
            candidates = []
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                candidates.append(os.path.join(exe_dir, "config.json"))
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                candidates.append(os.path.join(script_dir, "config.json"))
            candidates.append(os.path.abspath("config.json"))
            
            for cand in candidates:
                if os.path.exists(cand) and os.path.abspath(cand) != os.path.abspath(target_path):
                    try:
                        shutil.copy2(cand, target_path)
                        print(f"Migrated config from {cand}")
                        break
                    except Exception as e:
                        print(f"Migration error: {e}")
        return target_path

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config.update(json.load(f))
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()
        
    def t(self, key, **kwargs):
        lang = self.get("language")
        if lang not in TRANSLATIONS:
            lang = "en"
        text = TRANSLATIONS[lang].get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text


class Muxer(QObject):
    mux_finished = pyqtSignal(str, bool, str)
    queue_progress = pyqtSignal(int, int)
    file_progress = pyqtSignal(int)

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.ffmpeg_path = self._get_ffmpeg_path()
        log.info(f"FFmpeg path: {self.ffmpeg_path}")
        
        self.task_queue = queue.Queue()
        self.total_tasks_in_batch = 0
        self.completed_in_batch = 0
        self._lock = threading.Lock()
        self.current_process = None
        self._processed_or_queued = set()  # дедупликация: video_path строки
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _get_ffmpeg_path(self):
        # Сначала ищем системный ffmpeg (лучше поддерживает Unicode-пути)
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        # Запасной вариант — бандлёный ffmpeg
        local_ffmpeg = resource_path("ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        return "ffmpeg"

    def is_file_ready(self, filepath):
        try:
            os.rename(filepath, filepath)
            return True
        except OSError:
            return False

    def enqueue_mux(self, video_path, audio_path, is_auto=False):
        log.info(f"enqueue_mux: video={video_path}, auto={is_auto}")
        with self._lock:
            if video_path in self._processed_or_queued:
                log.info(f"enqueue_mux: SKIP duplicate {Path(video_path).name}")
                return
            self._processed_or_queued.add(video_path)
            self.total_tasks_in_batch += 1
            self.queue_progress.emit(self.completed_in_batch, self.total_tasks_in_batch)
        self.task_queue.put((video_path, audio_path, is_auto, 0))

    def cancel_queue(self):
        with self.task_queue.mutex:
            self.task_queue.queue.clear()
        
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception:
                pass
        
        with self._lock:
            self._processed_or_queued.clear()
        self.total_tasks_in_batch = 0
        self.completed_in_batch = 0
        self.queue_progress.emit(0, 0)

    def reset_batch(self):
        """Явный сброс счётчиков перед новым пакетом."""
        with self._lock:
            self.total_tasks_in_batch = 0
            self.completed_in_batch = 0
            self._processed_or_queued.clear()

    def _worker_loop(self):
        MAX_ATTEMPTS = 60  # 60 попыток × ~5с задержка ≈ 5 минут макс
        while True:
            log.debug("_worker_loop: waiting for task...")
            item = self.task_queue.get()
            if item is None:
                continue
                
            video_path, audio_path, is_auto = item[0], item[1], item[2]
            attempt = item[3] if len(item) > 3 else 0
            t0 = time.perf_counter()
            log.info(f"_worker_loop: picked up task, video={Path(video_path).name}, is_auto={is_auto}, attempt={attempt}")
            
            requeued = False
            
            if is_auto:
                # Проверяем, что файлы вообще существуют перед ожиданием
                if not (os.path.exists(video_path) and os.path.exists(audio_path)):
                    log.warning(f"_worker_loop: files missing, dropping task ({Path(video_path).name})")
                elif not (self.is_file_ready(video_path) and self.is_file_ready(audio_path)):
                    if attempt < MAX_ATTEMPTS:
                        log.debug(f"_worker_loop: files not ready, requeue (attempt {attempt+1}/{MAX_ATTEMPTS})")
                        time.sleep(5)
                        self.task_queue.put((video_path, audio_path, is_auto, attempt + 1))
                        requeued = True
                    else:
                        log.error(f"_worker_loop: timeout waiting for files after {MAX_ATTEMPTS} attempts")
                        self.mux_finished.emit(video_path, False, self.config.t("timeout"))
                else:
                    if attempt > 0:
                        log.info(f"_worker_loop: files ready after {attempt} attempts")
                    self.do_mux(video_path, audio_path)
            else:
                self.do_mux(video_path, audio_path)
            
            elapsed = time.perf_counter() - t0
            log.info(f"_worker_loop: task finished in {elapsed:.2f}s")
                
            with self._lock:
                if not requeued and self.total_tasks_in_batch > 0:
                    self.completed_in_batch += 1
                    self.queue_progress.emit(self.completed_in_batch, self.total_tasks_in_batch)
                
                if self.task_queue.empty():
                    self.total_tasks_in_batch = 0
                    self.completed_in_batch = 0
                    self.queue_progress.emit(0, 0)
                
            self.task_queue.task_done()

    def safe_remove(self, path):
        for _ in range(10):
            try:
                if os.path.exists(path):
                    os.remove(path)
                return True
            except Exception:
                time.sleep(0.5)
        return False

    def safe_move(self, src, dst):
        for _ in range(10):
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(str(src), str(dst))
                return True
            except Exception:
                time.sleep(0.5)
        return False

    def _get_duration(self, filepath):
        """Получить длительность файла в секундах через ffmpeg."""
        t0 = time.perf_counter()
        try:
            cmd = [self.ffmpeg_path, "-i", str(filepath)]
            creationflags = 0x08000000 if os.name == 'nt' else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=creationflags, timeout=10,
                encoding='utf-8', errors='replace'
            )
            elapsed = time.perf_counter() - t0
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
            if match:
                h, m, s, cs = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                dur = h * 3600 + m * 60 + s + cs / 100.0
                log.info(f"_get_duration: {dur}s (probe took {elapsed:.2f}s)")
                return dur
            log.warning(f"_get_duration: no Duration found in stderr (probe took {elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            log.error(f"_get_duration: exception {e} after {elapsed:.2f}s")
        return 0

    def do_mux(self, video_path, audio_path):
        video_path = Path(video_path)
        audio_path = Path(audio_path)
        
        # Early return: файлы могли быть перемещены/удалены предыдущей задачей
        if not video_path.exists() or not audio_path.exists():
            log.warning(f"do_mux SKIP: files missing — video={video_path.exists()}, audio={audio_path.exists()} ({video_path.name})")
            return
        
        output_name = video_path.stem + "_merged.mp4"
        output_path = video_path.parent / output_name
        log.info(f"do_mux START: {video_path.name}")
        log.info(f"  video: {video_path} (exists={video_path.exists()}, size={video_path.stat().st_size if video_path.exists() else 'N/A'})")
        log.info(f"  audio: {audio_path} (exists={audio_path.exists()})")
        log.info(f"  output: {output_path}")

        duration = self._get_duration(str(video_path))
        self.file_progress.emit(0)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0",
            "-map", "1:a",
            "-c", "copy",
            "-progress", "pipe:1",
            str(output_path)
        ]
        log.info(f"  cmd: {' '.join(cmd)}")

        try:
            creationflags = 0x08000000 if os.name == 'nt' else 0
            t_popen = time.perf_counter()
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=creationflags, text=True,
                bufsize=1, encoding='utf-8', errors='replace'
            )
            log.info(f"  Popen started (pid={self.current_process.pid}) in {time.perf_counter()-t_popen:.3f}s")
            
            # Дренируем stderr в отдельном потоке чтобы не было дедлока
            stderr_lines = []
            def drain_stderr():
                for line in self.current_process.stderr:
                    stderr_lines.append(line)
            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()
            
            # Парсим прогресс из stdout (-progress pipe:1)
            t_read = time.perf_counter()
            line_count = 0
            last_pct = -1
            for line in iter(self.current_process.stdout.readline, ''):
                line = line.strip()
                line_count += 1
                if line.startswith("out_time_us="):
                    try:
                        us = int(line.split("=")[1])
                        if duration > 0 and us >= 0:
                            pct = min(int((us / 1_000_000) / duration * 100), 100)
                            if pct != last_pct:
                                log.debug(f"  progress: {pct}% (at {time.perf_counter()-t_read:.2f}s)")
                                last_pct = pct
                            self.file_progress.emit(pct)
                    except (ValueError, ZeroDivisionError):
                        pass
                elif line.startswith("progress="):
                    log.info(f"  ffmpeg progress={line.split('=')[1]} (at {time.perf_counter()-t_read:.2f}s)")
            
            t_stdout_done = time.perf_counter()
            log.info(f"  stdout finished: {line_count} lines in {t_stdout_done-t_read:.2f}s")
            
            self.current_process.wait()
            t_wait = time.perf_counter()
            log.info(f"  process.wait() took {t_wait-t_stdout_done:.3f}s, returncode={self.current_process.returncode}")
            
            stderr_thread.join(timeout=5)
            if stderr_lines:
                log.info(f"  stderr ({len(stderr_lines)} lines): ...{stderr_lines[-1].strip()}")
            
            if self.current_process.returncode == 0:
                self.file_progress.emit(100)
                t_post = time.perf_counter()
                if self.config.get("delete_originals"):
                    log.info("  post: deleting originals...")
                    if not self.safe_remove(str(video_path)):
                        log.warning(f"  Failed to delete {video_path}")
                    if not self.safe_remove(str(audio_path)):
                        log.warning(f"  Failed to delete {audio_path}")
                elif self.config.get("move_originals"):
                    log.info("  post: moving originals...")
                    try:
                        original_dir = video_path.parent / "original"
                        original_dir.mkdir(exist_ok=True)
                        if not self.safe_move(video_path, original_dir / video_path.name):
                            log.warning(f"  Failed to move {video_path}")
                        if not self.safe_move(audio_path, original_dir / audio_path.name):
                            log.warning(f"  Failed to move {audio_path}")
                    except Exception as e:
                        log.error(f"  Failed to process move: {e}")
                log.info(f"  post-processing took {time.perf_counter()-t_post:.2f}s")
                        
                self.mux_finished.emit(str(video_path), True, self.config.t("success_msg", name=video_path.name))
                log.info(f"do_mux SUCCESS: {video_path.name}")
            else:
                log.error(f"do_mux FAILED: returncode={self.current_process.returncode}")
                log.error(f"  stderr: {''.join(stderr_lines[-5:])}")
                self.mux_finished.emit(str(video_path), False, self.config.t("ffmpeg_err"))
        except Exception as e:
            log.exception(f"do_mux EXCEPTION: {e}")
            self.mux_finished.emit(str(video_path), False, f"Ошибка: {str(e)}")
        finally:
            self.current_process = None


class FileWatcher(QObject):
    pair_found = pyqtSignal(str, str)
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.observer = None
        self.processed_pairs = set()

    def start(self):
        watch_dir = self.config.get("watch_dir")
        if not watch_dir or not os.path.isdir(watch_dir):
            return

        self.stop()
        
        class Handler(self.FileSystemEventHandler):
            def __init__(self, parent_watcher):
                self.parent = parent_watcher

            def on_created(self, event):
                if not event.is_directory:
                    self.parent.check_file(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    self.parent.check_file(event.src_path)

        self.observer = self.Observer()
        self.observer.schedule(Handler(self), watch_dir, recursive=True)
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def check_file(self, filepath):
        path = Path(filepath)
        
        # PREVENT INFINITE LOOP: ignore any file in an "original" folder
        if "original" in path.parts:
            return
            
        if path.name.endswith("_merged.mp4"):
            return 

        ext = path.suffix.lower()
        if ext in ['.mp4', '.m4a']:
            base_name = path.stem
            dir_name = path.parent
            
            video_path = dir_name / (base_name + ".mp4")
            audio_path = dir_name / (base_name + ".m4a")

            if video_path.exists() and audio_path.exists():
                key = str(video_path)
                if key not in self.processed_pairs:
                    self.processed_pairs.add(key)
                    self.pair_found.emit(str(video_path), str(audio_path))


class SettingsDialog(QDialog):
    def __init__(self, config_manager, muxer, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.muxer = muxer
        self.setWindowTitle(self.config.t("settings_title"))
        self.setWindowIcon(QIcon(resource_path("icon.png")))
        self.resize(700, 500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Settings Tab
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_tab.setLayout(settings_layout)
        
        # Language Selection
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel(self.config.t("language")))
        self.cb_lang = QComboBox()
        self.cb_lang.addItem("Русский", "ru")
        self.cb_lang.addItem("English", "en")
        
        index = self.cb_lang.findData(self.config.get("language"))
        if index >= 0:
            self.cb_lang.setCurrentIndex(index)
            
        self.cb_lang.currentIndexChanged.connect(self.change_language)
        lang_layout.addWidget(self.cb_lang)
        lang_layout.addStretch()
        settings_layout.addLayout(lang_layout)

        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.config.get("watch_dir"))
        self.dir_input.setReadOnly(True)
        dir_btn = QPushButton(self.config.t("browse_btn"))
        dir_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(QLabel(self.config.t("folder_label")))
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(dir_btn)
        settings_layout.addLayout(dir_layout)

        self.cb_auto_mux = QCheckBox(self.config.t("auto_mux"))
        self.cb_auto_mux.setChecked(self.config.get("auto_mux"))
        
        self.cb_auto_start = QCheckBox(self.config.t("auto_start"))
        self.cb_auto_start.setChecked(self.config.get("auto_start"))
        
        self.cb_delete = QCheckBox(self.config.t("delete_orig"))
        self.cb_delete.setChecked(self.config.get("delete_originals"))
        
        self.cb_move = QCheckBox(self.config.t("move_orig"))
        self.cb_move.setChecked(self.config.get("move_originals"))

        self.cb_delete.toggled.connect(lambda checked: self.cb_move.setDisabled(checked))
        if self.cb_delete.isChecked():
            self.cb_move.setDisabled(True)

        settings_layout.addWidget(self.cb_auto_mux)
        settings_layout.addWidget(self.cb_auto_start)
        settings_layout.addWidget(self.cb_delete)
        settings_layout.addWidget(self.cb_move)
        
        settings_layout.addStretch()

        save_btn = QPushButton(self.config.t("save_btn"))
        save_btn.clicked.connect(self.save_settings)
        settings_layout.addWidget(save_btn)

        self.tabs.addTab(settings_tab, self.config.t("tab_settings"))

        # Manual Mode Tab
        manual_tab = QWidget()
        manual_layout = QVBoxLayout()
        manual_tab.setLayout(manual_layout)
        
        scan_btn = QPushButton(self.config.t("scan_btn"))
        scan_btn.clicked.connect(self.scan_folder)
        manual_layout.addWidget(scan_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(self.config.t("tree_header"))
        self.tree.itemChanged.connect(self.on_item_changed)
        manual_layout.addWidget(self.tree)
        
        self.status_label = QLabel(self.config.t("queue_empty"))
        manual_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        manual_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        merge_btn = QPushButton(self.config.t("merge_btn"))
        merge_btn.clicked.connect(self.merge_selected)
        
        self.cancel_btn = QPushButton(self.config.t("cancel_btn"))
        self.cancel_btn.clicked.connect(self.cancel_queue)
        self.cancel_btn.setEnabled(False) # Initially disabled
        
        btn_layout.addWidget(merge_btn)
        btn_layout.addWidget(self.cancel_btn)
        manual_layout.addLayout(btn_layout)

        self.tabs.addTab(manual_tab, self.config.t("tab_manual"))

        self.found_pairs = {} 
        self.muxer.queue_progress.connect(self.update_progress)
        self.muxer.file_progress.connect(self.update_file_progress)

    def change_language(self, index):
        lang_code = self.cb_lang.itemData(index)
        self.config.set("language", lang_code)
        # Apply immediately by reloading window title and tabs
        self.setWindowTitle(self.config.t("settings_title"))
        self.tabs.setTabText(0, self.config.t("tab_settings"))
        self.tabs.setTabText(1, self.config.t("tab_manual"))
        # Ask user to restart or just save. We save dynamically.

    def browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.config.t("browse_title"))
        if dir_path:
            self.dir_input.setText(dir_path)

    def save_settings(self):
        old_auto_start = self.config.get("auto_start")
        
        self.config.set("watch_dir", self.dir_input.text())
        self.config.set("auto_mux", self.cb_auto_mux.isChecked())
        self.config.set("auto_start", self.cb_auto_start.isChecked())
        self.config.set("delete_originals", self.cb_delete.isChecked())
        self.config.set("move_originals", self.cb_move.isChecked())
        
        setup_autostart(self.cb_auto_start.isChecked())

        QMessageBox.information(self, self.config.t("saved_title"), self.config.t("saved_msg"))
        self.accept()

    def scan_folder(self):
        watch_dir = self.config.get("watch_dir")
        if not watch_dir or not os.path.isdir(watch_dir):
            QMessageBox.warning(self, self.config.t("err_title"), self.config.t("err_no_folder"))
            return

        self.tree.blockSignals(True)
        self.tree.clear()
        self.found_pairs = {}
        
        watch_path = Path(watch_dir)
        folders_dict = {}
        
        for root, dirs, files in os.walk(watch_path):
            root_path = Path(root)
            
            # PREVENT INFINITE LOOP: ignore any folder named "original"
            if "original" in dirs:
                dirs.remove("original")
                
            for file in files:
                if file.endswith(".mp4") and not file.endswith("_merged.mp4"):
                    base_name = file[:-4]
                    if (base_name + ".m4a") in files:
                        video_path = root_path / file
                        audio_path = root_path / (base_name + ".m4a")
                        merged_path = root_path / (base_name + "_merged.mp4")
                        
                        if not merged_path.exists():
                            folder_name = root_path.name
                            if folder_name not in folders_dict:
                                folder_item = QTreeWidgetItem([folder_name])
                                folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                                folder_item.setCheckState(0, Qt.CheckState.Checked)
                                folders_dict[folder_name] = folder_item
                                self.tree.addTopLevelItem(folder_item)
                            
                            file_item = QTreeWidgetItem([base_name])
                            file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            file_item.setCheckState(0, Qt.CheckState.Checked)
                            file_item.setData(0, Qt.ItemDataRole.UserRole, str(video_path))
                            
                            folders_dict[folder_name].addChild(file_item)
                            self.found_pairs[str(video_path)] = str(audio_path)

        self.tree.expandAll()
        self.tree.blockSignals(False)
        
        if not self.found_pairs:
            QMessageBox.information(self, self.config.t("res_title"), self.config.t("res_no_files"))

    def on_item_changed(self, item, column):
        self.tree.blockSignals(True)
        if item.childCount() > 0:
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        else:
            parent = item.parent()
            if parent:
                all_checked = all(parent.child(i).checkState(0) == Qt.CheckState.Checked for i in range(parent.childCount()))
                any_checked = any(parent.child(i).checkState(0) == Qt.CheckState.Checked for i in range(parent.childCount()))
                if all_checked:
                    parent.setCheckState(0, Qt.CheckState.Checked)
                elif any_checked:
                    parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
                else:
                    parent.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)

    def merge_selected(self):
        self.muxer.reset_batch()
        count = 0
        for i in range(self.tree.topLevelItemCount()):
            folder_item = self.tree.topLevelItem(i)
            for j in range(folder_item.childCount()):
                file_item = folder_item.child(j)
                if file_item.checkState(0) == Qt.CheckState.Checked:
                    video_path = file_item.data(0, Qt.ItemDataRole.UserRole)
                    audio_path = self.found_pairs.get(video_path)
                    if audio_path:
                        self.muxer.enqueue_mux(video_path, audio_path, is_auto=False)
                        count += 1

    def cancel_queue(self):
        self.muxer.cancel_queue()

    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(100)
            self.status_label.setText(self.config.t("processing", cur=current, tot=total))
            self.cancel_btn.setEnabled(True)
        else:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self.status_label.setText(self.config.t("queue_empty"))
            self.cancel_btn.setEnabled(False)
            # Пересканируем после завершения пакета
            if self.found_pairs:
                self.scan_folder()

    def update_file_progress(self, percent):
        """Обновляет прогресс-бар для текущего файла."""
        self.progress_bar.setValue(percent)


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.config = ConfigManager()
        # Fix autostart registry on every launch to ensure --autostart flag is present
        if self.config.get("auto_start"):
            setup_autostart(True)
        
        self.shared_mem = QSharedMemory("AdrenalinSplitterSharedMem")
        if not self.shared_mem.create(1):
            QMessageBox.warning(None, "Adrenalin Splitter", self.config.t("already_running"))
            sys.exit(0)
            
        self.muxer = Muxer(self.config)
        self.watcher = FileWatcher(self.config)
        
        self.watcher.pair_found.connect(self.on_pair_found)
        self.muxer.mux_finished.connect(self.on_mux_finished)
        
        self.setup_tray()
        
        if self.config.get("auto_mux"):
            self.watcher.start()

    def setup_tray(self):
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            from PyQt6.QtGui import QPixmap, QColor
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor("red"))
            icon = QIcon(pixmap)

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(icon)
        self.tray.setToolTip("Adrenalin Splitter")
        
        menu = QMenu()
        
        settings_action = QAction(self.config.t("tray_settings"), self.app)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        quit_action = QAction(self.config.t("tray_quit"), self.app)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings()

    def show_settings(self):
        if not hasattr(self, 'dialog') or not self.dialog.isVisible():
            self.dialog = SettingsDialog(self.config, self.muxer)
            self.dialog.finished.connect(self.on_dialog_closed)
            self.dialog.show()
        else:
            self.dialog.activateWindow()
            self.dialog.raise_()

    def on_dialog_closed(self):
        if self.config.get("auto_mux"):
            self.watcher.start()
        else:
            self.watcher.stop()

    def on_pair_found(self, video_path, audio_path):
        if self.config.get("auto_mux"):
            name = Path(video_path).name
            self.tray.showMessage("Adrenalin Splitter", self.config.t("found_new", name=name), QSystemTrayIcon.MessageIcon.Information)
            self.muxer.enqueue_mux(video_path, audio_path, is_auto=True)

    def on_mux_finished(self, filepath, success, message):
        name = Path(filepath).name
        if success:
            self.tray.showMessage(self.config.t("success_title"), self.config.t("success_msg", name=name), QSystemTrayIcon.MessageIcon.Information)
        elif "отменен" not in message and "cancelled" not in message:
            self.tray.showMessage(self.config.t("err_title"), self.config.t("fail_msg", name=name, msg=message), QSystemTrayIcon.MessageIcon.Warning)

    def quit_app(self):
        self.watcher.stop()
        self.app.quit()

    def run(self):
        is_autostart = any(arg in sys.argv for arg in ["--autostart", "--tray", "--minimized", "-autostart", "-tray", "-minimized"])
        if not self.config.get("watch_dir") and not is_autostart:
            self.show_settings()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    TrayApp().run()

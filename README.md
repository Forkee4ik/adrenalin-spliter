# Adrenalin Splitter

Утилита для автоматического объединения видео и аудио файлов, записанных через AMD Adrenalin Software. AMD Adrenalin сохраняет игровое видео (`.mp4`) и микрофон (`.m4a`) в отдельные файлы — Adrenalin Splitter автоматически объединяет их в один файл.

## Возможности

- 🔄 **Автоматический режим** — мониторит папку и объединяет новые записи в реальном времени
- 🎛️ **Ручной режим** — сканирование и выборочное объединение файлов
- 🗑️ **Управление оригиналами** — удаление или перемещение в подпапку после объединения
- 🔔 **Работа в трее** — тихо работает в фоне, уведомляя о результатах
- 🚀 **Автозапуск с Windows** — запускается вместе с системой
- 🌍 **Русский и английский** интерфейс

## Установка

### Готовый инсталлятор

Скачайте последний `AdrenalinSplitter_Setup.exe` из [Releases](../../releases) и установите.

### Из исходников

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/<user>/adrenalin-spliter.git
   cd adrenalin-spliter
   ```

2. **Создайте виртуальное окружение и установите зависимости:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Скачайте FFmpeg:**
   - Загрузите со [страницы FFmpeg](https://www.gyan.dev/ffmpeg/builds/) (рекомендуется `ffmpeg-release-full`)
   - Положите `ffmpeg.exe` в корень проекта

4. **Запустите:**
   ```bash
   python app.py
   ```

## Сборка

### Сборка EXE (PyInstaller)

```bash
pip install pyinstaller
pyinstaller AdrenalinSplitter.spec --clean
```

Результат будет в папке `dist/AdrenalinSplitter/`.

### Сборка инсталлятора (NSIS)

1. Установите [NSIS](https://nsis.sourceforge.io/)
2. Скопируйте `ffmpeg.exe` в `dist/AdrenalinSplitter/`
3. Соберите инсталлятор:
   ```bash
   makensis installer.nsi
   ```

## Настройки

Конфигурация хранится в `%APPDATA%\AdrenalinSplitter\config.json`.

| Параметр | Описание |
|---|---|
| `watch_dir` | Папка для мониторинга записей AMD Adrenalin |
| `auto_mux` | Автоматическое объединение новых файлов |
| `auto_start` | Автозапуск вместе с Windows |
| `delete_originals` | Удалять оригиналы после объединения |
| `move_originals` | Перемещать оригиналы в подпапку `original` |
| `language` | Язык интерфейса (`ru` / `en`) |

## Зависимости

- **Python 3.10+**
- **PyQt6** — графический интерфейс
- **watchdog** — мониторинг файловой системы
- **FFmpeg** — объединение видео и аудио (внешний бинарный файл)

## Лицензия

MIT — см. [LICENSE](LICENSE).

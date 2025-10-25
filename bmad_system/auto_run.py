import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import os

class ChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.py', '.md')):  # watch Python & markdown files
            print(f"Change detected: {event.src_path}")
            subprocess.call(['python', '../instance/main.py'])  # change to your entry point

if __name__ == "__main__":
    path = os.getcwd()  # watch the whole project
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    print("Watching for changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


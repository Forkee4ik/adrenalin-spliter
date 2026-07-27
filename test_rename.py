import os
import tempfile
fd, path = tempfile.mkstemp()
os.close(fd)
try:
    os.rename(path, path)
    print("Success")
except Exception as e:
    print("Exception:", type(e).__name__)
os.remove(path)

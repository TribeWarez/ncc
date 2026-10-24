import os

# Keep Qt tests headless on Windows/Linux CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

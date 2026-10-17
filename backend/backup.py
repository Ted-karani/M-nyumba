# Import the tools we need
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

# Where everything lives (all next to this file)
HERE = Path(__file__).resolve().parent
DB_FILE = HERE / "mnyumba.db"
UPLOADS = HERE / "uploads"
BACKUPS = HERE / "backups"
# How many of the newest backups to keep
KEEP = 14


# Make one backup zip
def main():
    # Make sure the backups folder exists
    BACKUPS.mkdir(exist_ok=True)
    # Name the zip after today's date and time
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    target = BACKUPS / f"mnyumba-backup-{stamp}.zip"
    with tempfile.TemporaryDirectory() as folder:
        # Copy the database safely (this is fine even while the app is running)
        copy = Path(folder) / "mnyumba.db"
        source = sqlite3.connect(DB_FILE)
        destination = sqlite3.connect(copy)
        source.backup(destination)
        destination.close()
        source.close()
        # Put the database copy and every uploaded file into the zip
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(copy, "mnyumba.db")
            if UPLOADS.exists():
                for file in UPLOADS.iterdir():
                    if file.is_file():
                        archive.write(file, f"uploads/{file.name}")
    # Keep only the newest backups
    for old in sorted(BACKUPS.glob("mnyumba-backup-*.zip"))[:-KEEP]:
        old.unlink()
    print(f"Backup saved: {target}")
    print("Remember: the .env file is NOT in the backup. Keep a safe copy of it separately.")


# Run it when this file is started directly
if __name__ == "__main__":
    main()
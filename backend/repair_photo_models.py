# repair_photo_models.py - the photos attached to a repair report

# Import the date and time tool
from datetime import datetime
# Import the column types we need for the table
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

# Import our own files
from database import Base


# This class is the "repair_photos" table. Each photo is one row.
class RepairPhoto(Base):
    # The name of the table inside the database
    __tablename__ = "repair_photos"

    # A unique number for each photo, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The repair report it belongs to (points to the maintenance_requests table)
    repair_id = Column(Integer, ForeignKey("maintenance_requests.id"), nullable=False, index=True)
    # The person who added it (points to the users table)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The name the file had on the person's phone
    original_name = Column(String, nullable=False)
    # The kind of picture, like "image/jpeg"
    content_type = Column(String, nullable=False)
    # How big the file is
    size_bytes = Column(Integer, nullable=False)
    # The random name the file is saved under on the server
    stored_name = Column(String, nullable=False)
    # When it was added
    created_at = Column(DateTime, default=datetime.utcnow)


# Remove the photo rows of a repair, and give back the names of the files (the caller deletes the files after saving)
def remove_repair_photos(db, repair_id: int) -> list[str]:
    rows = db.query(RepairPhoto).filter(RepairPhoto.repair_id == repair_id).all()
    names = [row.stored_name for row in rows]
    for row in rows:
        db.delete(row)
    # Send the deletes to the database now, so they happen before the repair itself is deleted
    db.flush()
    return names
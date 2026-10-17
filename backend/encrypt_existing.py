# Import the tool that lets us write plain database commands
from sqlalchemy import text

# Import our own files
from database import SessionLocal
from encryption import PREFIX, encrypt_text

# Open a conversation with the database
db = SessionLocal()
try:
    # Get every tenant ID number exactly as it is stored (without unscrambling it)
    rows = db.execute(text("SELECT id, id_number FROM tenants WHERE id_number IS NOT NULL AND id_number != ''")).all()
    changed = 0
    for row_id, value in rows:
        # Skip the ones that are already scrambled
        if value.startswith(PREFIX):
            continue
        # Scramble this one and save it back
        db.execute(
            text("UPDATE tenants SET id_number = :value WHERE id = :id"),
            {"value": encrypt_text(value), "id": row_id},
        )
        changed += 1
    # Save everything together
    db.commit()
    print(f"Done. {changed} ID number(s) were scrambled, {len(rows) - changed} were already safe.")
finally:
    # Always close the conversation
    db.close()
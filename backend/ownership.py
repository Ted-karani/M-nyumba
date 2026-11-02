# ownership.py - finds every row that belongs to one landlord, in every table
# (the data export and the account deletion both use it, so they always agree about what "their data" means)

# Import the tools we need
from collections import defaultdict
from sqlalchemy import select

# Import our own files
import models
from database import Base
from portal_models import TenantAccount

# Tables that are never exported or deleted as "the landlord's data": the login row itself (it is anonymised instead),
# the plan, what they paid us, and our own admin log
KEEP_TABLES = {"users", "owner_accounts", "subscription_payments", "admin_events"}
# How many ids to put in one database question
CHUNK = 500


# Cut a list into pieces of a safe size
def chunks(items, size=CHUNK):
    for start in range(0, len(items), size):
        yield items[start:start + size]


# The logins of the landlord's caretakers and tenants (not the landlord themselves)
def member_user_ids(db, owner_id: int) -> list[int]:
    caretakers = [row[0] for row in db.query(models.CaretakerAccount.user_id).filter(models.CaretakerAccount.owner_id == owner_id).all()]
    tenants = [row[0] for row in db.query(TenantAccount.user_id).filter(TenantAccount.owner_id == owner_id).all()]
    return caretakers + tenants


# Does a column point at the users table?
def points_at_users(column) -> bool:
    return any(fk.column.table.name == "users" and fk.column.name == "id" for fk in column.foreign_keys)


# Does a column say "this row belongs to this person"?
def is_owner_column(column) -> bool:
    if column.name == "owner_id":
        return True
    return column.name == "user_id" and points_at_users(column)


# Find every row of this landlord: {table name: set of row ids}
def collect(db, owner_id: int) -> dict[str, set[int]]:
    members = member_user_ids(db, owner_id)
    people = [owner_id] + members
    tables = Base.metadata.tables
    marked = defaultdict(set)
    # The caretakers' and tenants' own logins belong to the landlord's business
    marked["users"].update(members)
    # First: every row that says directly "this is theirs"
    for name, table in tables.items():
        if name in KEEP_TABLES or "id" not in table.c:
            continue
        for column in table.columns:
            if is_owner_column(column):
                found = db.execute(select(table.c.id).where(column.in_(people))).scalars().all()
                marked[name].update(found)
    # Then: everything that points at one of those rows, and at those, and so on (like the payments of a lease)
    changed = True
    while changed:
        changed = False
        for name, table in tables.items():
            if name in KEEP_TABLES or "id" not in table.c:
                continue
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                if fk.column.name != "id" or not marked.get(parent):
                    continue
                found = set()
                for piece in chunks(sorted(marked[parent])):
                    found.update(db.execute(select(table.c.id).where(fk.parent.in_(piece))).scalars().all())
                new = found - marked[name]
                if new:
                    marked[name] |= new
                    changed = True
    return {name: ids for name, ids in marked.items() if ids}


# The uploaded files that belong to the rows found: [(table, row id, stored name, original name)]
def stored_files(db, marked: dict[str, set[int]]):
    files = []
    for name, ids in marked.items():
        table = Base.metadata.tables[name]
        if "stored_name" not in table.c:
            continue
        columns = [table.c.id, table.c.stored_name]
        if "original_name" in table.c:
            columns.append(table.c.original_name)
        for piece in chunks(sorted(ids)):
            for row in db.execute(select(*columns).where(table.c.id.in_(piece))).all():
                original = row[2] if len(row) > 2 else None
                if row[1]:
                    files.append((name, row[0], row[1], original))
    return files


# Delete the rows found, children before parents (so no row is ever left pointing at nothing)
def erase(db, marked: dict[str, set[int]]) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        ids = marked.get(table.name)
        if not ids or "id" not in table.c:
            continue
        for piece in chunks(sorted(ids)):
            db.execute(table.delete().where(table.c.id.in_(piece)))
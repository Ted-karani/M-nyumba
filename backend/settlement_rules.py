# settlement_rules.py - the money rules for a move-out settlement (no database in here, so it is easy to test)

# Import our own files
import taxrules

# The most deductions one settlement may have
MAX_DEDUCTIONS = 20


# Work out the figures from a tenant's charges and payments.
# charges: [{id, due_date, amount, charge_type, description}]   payments: [{id, paid_on, amount}]
# agreed_deposit: the deposit written on the lease (used when no deposit charge exists, like for tenants brought in from a notebook)
def figures(charges, payments, agreed_deposit: int) -> dict:
    sorted_charges = [
        {"id": item["id"], "due_date": item["due_date"], "amount": item["amount"], "category": taxrules.charge_category(item["charge_type"], item.get("description"))}
        for item in charges
    ]
    split = taxrules.allocate(sorted_charges, payments)
    paid = {name: 0 for name in taxrules.CATEGORIES}
    for parts in split.values():
        for name, value in parts.items():
            paid[name] += value
    deposit_charged = sum(item["amount"] for item in sorted_charges if item["category"] == "deposit" and item["amount"] > 0)
    other_charged = sum(item["amount"] for item in sorted_charges if item["category"] != "deposit" and item["amount"] > 0)
    paid_other = paid["rent"] + paid["arrears"] + paid["bills"]
    return {
        "deposit_charged": deposit_charged,
        # If a deposit was charged, what is held is what was paid toward it; otherwise the deposit written on the lease
        "deposit_held": paid["deposit"] if deposit_charged > 0 else agreed_deposit,
        "deposit_found_from": "paid" if deposit_charged > 0 else "recorded",
        # Rent, bills and fees still owing
        "unpaid_charges": other_charged - paid_other,
        # Money paid ahead, with nothing left to pay
        "credit": paid["advance"],
    }


# The result: what goes back to the tenant, or what they still owe
def outcome(deposit_held: int, credit: int, unpaid_charges: int, deductions) -> dict:
    total = sum(item["amount"] for item in deductions)
    net = deposit_held + credit - unpaid_charges - total
    return {"total_deductions": total, "refund_due": max(net, 0), "tenant_owes": max(-net, 0)}
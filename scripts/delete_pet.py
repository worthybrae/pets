"""Delete a pet and all its data from Supabase.

Usage:
    python -m scripts.delete_pet <pet_id>
    python -m scripts.delete_pet --all          # delete ALL pets
    python -m scripts.delete_pet --owner <id>   # delete pet by owner
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

TABLES = [
    "raw_events",
    "digested_notes",
    "knowledge_base",
    "artifacts",
    "world_chunks",
    "world_snapshots",
    "pet_body",
    "agendas",
    "social_graph",
]

PET_TABLE = "pets"


def get_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def delete_pet(client, pet_id: str):
    """Delete a single pet and all related data."""
    print(f"Deleting pet {pet_id}...")
    for table in TABLES:
        resp = client.table(table).delete().eq("pet_id", pet_id).execute()
        count = len(resp.data) if resp.data else 0
        if count:
            print(f"  {table}: {count} rows deleted")
    # visit_log uses visitor_id/host_id instead of pet_id
    for col in ("visitor_id", "host_id"):
        resp = client.table("visit_log").delete().eq(col, pet_id).execute()
        count = len(resp.data) if resp.data else 0
        if count:
            print(f"  visit_log ({col}): {count} rows deleted")
    # Delete the pet record itself
    resp = client.table(PET_TABLE).delete().eq("id", pet_id).execute()
    if resp.data:
        print(f"  {PET_TABLE}: deleted")
    print(f"Done: {pet_id}")


def delete_all(client):
    """Delete ALL pets and related data."""
    # Get all pet IDs
    resp = client.table(PET_TABLE).select("id").execute()
    pets = resp.data or []
    if not pets:
        print("No pets found.")
        return
    print(f"Found {len(pets)} pet(s). Deleting all...")
    for pet in pets:
        delete_pet(client, pet["id"])
    print(f"\nAll {len(pets)} pet(s) deleted.")


def delete_by_owner(client, owner_id: str):
    """Delete pet(s) belonging to an owner."""
    resp = client.table(PET_TABLE).select("id").eq("owner_id", owner_id).execute()
    pets = resp.data or []
    if not pets:
        print(f"No pets found for owner {owner_id}")
        return
    for pet in pets:
        delete_pet(client, pet["id"])


def main():
    parser = argparse.ArgumentParser(description="Delete pet data from Supabase")
    parser.add_argument("pet_id", nargs="?", help="Pet ID to delete")
    parser.add_argument("--all", action="store_true", help="Delete ALL pets")
    parser.add_argument("--owner", help="Delete pet(s) by owner ID")
    args = parser.parse_args()

    if not args.pet_id and not args.all and not args.owner:
        parser.print_help()
        sys.exit(1)

    client = get_client()

    if args.all:
        confirm = input("Delete ALL pets? Type 'yes' to confirm: ")
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)
        delete_all(client)
    elif args.owner:
        delete_by_owner(client, args.owner)
    else:
        delete_pet(client, args.pet_id)


if __name__ == "__main__":
    main()

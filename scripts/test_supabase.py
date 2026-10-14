from supabase import create_client

URL = "https://uzszqrppnxsbwndrenns.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV6c3pxcnBwbnhzYnduZHJlbm5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5OTE4MDIsImV4cCI6MjEwNzU2NzgwMn0.CrZUsdJ_zIWUJgaltrobqRKPUIQxdhG4mt5fSFFVrjs"


def main():
    client = create_client(URL, KEY)
    print("Client created.")

    # Try insert
    res = client.table("review_specs").insert({
        "instruction": "test",
        "spec_json": {"hello": "world"},
    }).execute()
    print("Inserted row id:", res.data[0]["id"])

    # Try select
    res = client.table("review_specs").select("*").execute()
    print("Total rows in review_specs:", len(res.data))

    # Cleanup
    client.table("review_specs").delete().eq("instruction", "test").execute()
    print("Cleanup done.")


if __name__ == "__main__":
    main()
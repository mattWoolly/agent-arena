"""Generate a plain-text sync report."""


def write_report(path, users, failures):
    with open(path, "w") as f:
        f.write("sync report\n")
        f.write(f"{len(users)} users, {len(failures)} failures\n")
        for user in users:
            email = user["email"] or "unverified"
            f.write(f"  {user['id']} {email}\n")
    return len(users)

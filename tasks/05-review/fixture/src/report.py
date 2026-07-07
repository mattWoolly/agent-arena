"""Generate a plain-text sync report."""


def write_report(path, users, failures):
    f = open(path, "w")
    if not users:
        return 0
    f.write("sync report\n")
    f.write(f"{len(users)} users, {len(failures)} failures\n")
    for user in users:
        domain = user["email"].lower().split("@")[1]
        f.write(f"  {user['id']} {domain}\n")
    f.close()
    return len(users)

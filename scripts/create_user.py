#!/usr/bin/env python3
"""Generate a password hash for config.yaml auth section."""
import hashlib
import getpass
import sys


def main():
    username = input("Benutzername: ").strip()
    if not username:
        print("Fehler: Benutzername darf nicht leer sein.")
        sys.exit(1)

    password = getpass.getpass("Passwort: ")
    if not password:
        print("Fehler: Passwort darf nicht leer sein.")
        sys.exit(1)

    confirm = getpass.getpass("Passwort wiederholen: ")
    if password != confirm:
        print("Fehler: Passwoerter stimmen nicht ueberein.")
        sys.exit(1)

    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    print()
    print("Folgenden Block in config.yaml unter 'auth:' einfuegen:")
    print()
    print("auth:")
    print("  users:")
    print(f"    - username: {username}")
    print(f"      password_hash: {password_hash}")


if __name__ == "__main__":
    main()

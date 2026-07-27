import getpass
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired

SESSION_FILE = Path(__file__).parent / "session.json"


def main():
    cl = Client()

    if SESSION_FILE.exists():
        cl.load_settings(SESSION_FILE)
        print(f"Loaded saved session from {SESSION_FILE}")
    else:
        username = input("Instagram username: ").strip()
        password = getpass.getpass("Instagram password: ")

        try:
            cl.login(username, password)
        except TwoFactorRequired:
            code = input("Enter the 2FA code sent to you: ").strip()
            cl.login(username, password, verification_code=code)
        except ChallengeRequired:
            print("Instagram is asking for a challenge (e.g. code sent to email/SMS).")
            print("Open the Instagram app/website and complete it, then re-run this script.")
            return

        cl.dump_settings(SESSION_FILE)
        print(f"Login successful. Session saved to {SESSION_FILE}")

    me = cl.account_info()
    print("\nLogged in as:")
    print(f"  Username : {me.username}")
    print(f"  Full name: {me.full_name}")
    print(f"  Followers: {me.follower_count}")
    print(f"  Following: {me.following_count}")


if __name__ == "__main__":
    main()

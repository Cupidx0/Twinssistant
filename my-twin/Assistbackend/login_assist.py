from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

SCOPES = ["https://www.googleapis.com/auth/calendar"]
def main():
    creds = None

    # If there's no token.json, start the login flow
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json must be downloaded from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=8080,access_type='offline',prompt='consent')

        # Save the credentials for next runs
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    print("✅ Logged in and token.json created!")

if __name__ == "__main__":
    main()
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gmail_log import main
x = main()
def labels():
    try:
          # Call the Gmail API
          service = build("gmail", "v1", credentials=x)
          results = service.users().labels().list(userId="me").execute()
          labels = results.get("labels", [])
          if not labels:
            print("No labels found.")
            return
          print("Labels:")
          for label in labels:
            print(label["name"])
    except HttpError as error:
          print(f"An error occurred: {error}")
def mail_box(user_choice="IMPORTANT"):
    try:
        # Call the Gmail API
        service = build("gmail", "v1", credentials=x)
        results = (
            service.users().messages().list(userId="me", labelIds=[user_choice]).execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return

        print("Messages:")
        for message in messages[:3]:
            print(f'Message ID: {message["id"]}')
            msg = (
                service.users().messages().get(userId="me", id=message["id"],format='full').execute()
            )
            print(f'  Subject: {msg["snippet"]}')
        return messages
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")
if __name__ == "__main__":
    labels()
    mail_box()
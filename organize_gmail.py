#!/usr/bin/env python3
"""
AI Agent to Organize Gmail

This script:
1. Authenticates with the Gmail API.
2. Retrieves a few unread emails (modify the query as desired).
3. Uses OpenAI’s GPT (via the API) to classify each email into one or more of the following categories.
   If a custom prompt is provided that specifies only two folders (Work and Social), it will use those;
   otherwise, it defaults to five categories: Work, Personal, Promotions, Social, or Updates.
4. Creates a Gmail label for that category (if it doesn’t already exist).
5. Applies the label to the email.

Make sure you have your `credentials.json` (from Google Cloud)
in the same directory, and replace 'YOUR_OPENAI_API_KEY' below.
"""

import os
import openai  # Use the standard openai package
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Set your OpenAI API key
#openai.api_key = 'Enter code'  Replace with your actual OpenAI API key

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def gmail_authenticate():
    """
    Authenticate with Gmail API and return a service object.
    This function uses a local webserver to handle OAuth authentication.
    """
    creds = None
    # token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

def classify_email(subject, snippet, custom_prompt=None):
    """
    Use OpenAI to classify an email based on its subject and snippet.
    If a custom prompt is provided that instructs to only use two folders,
    the allowed categories are set to ["Work", "Social"]; otherwise, the default
    allowed categories are: Work, Personal, Promotions, Social, or Updates.
    """
    # Determine allowed categories based on the custom prompt.
    if custom_prompt and "only" in custom_prompt.lower() and \
       "work" in custom_prompt.lower() and "social" in custom_prompt.lower():
        allowed_categories = ["Work", "Social"]
        prompt = (
            f"{custom_prompt}\nAllowed categories: Work, Social.\n"
            "Return only the word 'Work' or 'Social' as the answer (no extra text).\n\n"
            f"Email Subject: {subject}\nEmail Snippet: {snippet}\n\nCategory:"
        )
    else:
        allowed_categories = ["Work", "Personal", "Promotions", "Social", "Updates"]
        prompt = (
            "Below are some examples of email classifications:\n\n"
            "Example 1:\n"
            "Email Subject: Project Deadline Reminder\n"
            "Email Snippet: Don't forget the deadline for the project is tomorrow.\n"
            "Category: Work\n\n"
            "Example 2:\n"
            "Email Subject: Family Reunion Invitation\n"
            "Email Snippet: Looking forward to our family reunion this weekend!\n"
            "Category: Personal\n\n"
            "Example 3:\n"
            "Email Subject: 50% Off Sale on Shoes!\n"
            "Email Snippet: Hurry up! Our biggest sale of the year is live now.\n"
            "Category: Promotions\n\n"
            "Example 4:\n"
            "Email Subject: New Friend Request\n"
            "Email Snippet: John Doe sent you a friend request on SocialNet.\n"
            "Category: Social\n\n"
            "Example 5:\n"
            "Email Subject: Account Update Notice\n"
            "Email Snippet: There is an update on your account settings.\n"
            "Category: Updates\n\n"
            "Now, classify the following email into one of these categories: "
            "Work, Personal, Promotions, Social, or Updates.\n\n"
            f"Email Subject: {subject}\nEmail Snippet: {snippet}\nCategory:"
        )
    # Debug: print the prompt so you can verify it.
    print("DEBUG: Prompt sent to API:")
    print(prompt)
    
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=20,
            temperature=0.0,
            n=1,
            stop=["\n"]
        )
        raw_category = response.choices[0].text.strip()
        print(f"DEBUG: Raw classification result: '{raw_category}'")
        
        # If the response is "Other" (or doesn't match allowed categories), force a fallback.
        if raw_category.lower() == "other" or not any(cat.lower() in raw_category.lower() for cat in allowed_categories):
            print("DEBUG: Response did not match allowed categories, applying fallback heuristic.")
            # For two-folder mode, decide based on subject keywords.
            if allowed_categories == ["Work", "Social"]:
                work_keywords = ['meeting', 'deadline', 'project', 'schedule', 'report']
                if any(word in subject.lower() for word in work_keywords):
                    return "Work"
                else:
                    return "Social"
            else:
                # For the default mode, choose "Updates" as a fallback.
                return "Updates"
        
        # Otherwise, try mapping the response to one of the allowed categories.
        if allowed_categories == ["Work", "Social"]:
            normalized = raw_category.lower()
            if "work" in normalized:
                return "Work"
            elif "social" in normalized:
                return "Social"
            else:
                # Fallback: use subject heuristics.
                work_keywords = ['meeting', 'deadline', 'project', 'schedule', 'report']
                if any(word in subject.lower() for word in work_keywords):
                    return "Work"
                return "Social"
        else:
            mapping = {
                'work': 'Work',
                'work-related': 'Work',
                'personal': 'Personal',
                'promotional': 'Promotions',
                'promo': 'Promotions',
                'social': 'Social',
                'update': 'Updates',
                'updates': 'Updates'
            }
            normalized = raw_category.lower()
            for key, value in mapping.items():
                if key in normalized:
                    return value
            if raw_category in allowed_categories:
                return raw_category
            return 'Updates'  # Fallback for the default set

    except Exception as e:
        print(f"Error classifying email: {e}")
        return 'Updates'

def get_or_create_label(service, label_name):
    """
    Retrieve the Gmail label ID for a given label name, or create it if it doesn't exist.
    """
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    for label in labels:
        if label['name'].lower() == label_name.lower():
            return label['id']
    # If label not found, create it.
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    created_label = service.users().labels().create(userId='me', body=label_body).execute()
    return created_label['id']


def add_label_to_message(service, msg_id, label_id):
    """
    Add a specified label to a Gmail message.
    """
    body = {'addLabelIds': [label_id]}
    service.users().messages().modify(userId='me', id=msg_id, body=body).execute()


def get_message_details(service, msg_id):
    """
    Retrieve the subject and snippet for a given Gmail message ID.
    """
    message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = message.get('payload', {}).get('headers', [])
    subject = ""
    for header in headers:
        if header.get('name', '').lower() == 'subject':
            subject = header.get('value', '')
            break
    snippet = message.get('snippet', '')
    return subject, snippet


def main():
    service = gmail_authenticate()

    # --- Customization Section ---
    # Set CUSTOM_PROMPT to instruct the agent to use only two folders.
    # For example, to sort only into "Work" and "Social", set:
    CUSTOM_PROMPT = "Organize my emails only into two folders: Work and Social."
    # If you leave CUSTOM_PROMPT as an empty string, the agent uses all default categories.
    # -----------------------------

    query = "is:unread"
    results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
    messages = results.get('messages', [])
    if not messages:
        print("No messages found.")
        return

    for msg in messages:
        msg_id = msg['id']
        subject, snippet = get_message_details(service, msg_id)
        print(f"Processing email with subject: {subject}")
        category = classify_email(subject, snippet, custom_prompt=CUSTOM_PROMPT)
        print(f"Classified as: {category}")
        # Get (or create) the label for this category and add it to the message.
        label_id = get_or_create_label(service, category)
        add_label_to_message(service, msg_id, label_id)
        print(f"Added label '{category}' to email.\n")


if __name__ == '__main__':
    main()

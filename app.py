import os
import openai
import secrets
import base64
from flask import Flask, render_template, redirect, url_for, flash, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_key_for_dev') # Replace with a secure secret key

# Set your Gmail API scopes and OpenAI API key.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
#openai.api_key = 'Enter key'  Replace with your actual OpenAI API key


def gmail_authenticate():
    """
    Authenticates with the Gmail API and returns a service object.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

def classify_email(subject, snippet, custom_prompt=None):
    """
    Uses OpenAI to classify an email based on its subject and snippet.
    If a custom prompt is provided by the user, it is used to drive the classification.
    Otherwise, a default prompt is used.
    """
    if custom_prompt:
        prompt = f"{custom_prompt}\n\nSubject: {subject}\nSnippet: {snippet}\n\nCategory:"
    else:
        prompt = (
            "Classify the following email into one of these categories: Work, Personal, "
            "Promotions, Social, or Updates. Please strictly choose one of the categories.\n\n"
            f"Subject: {subject}\nSnippet: {snippet}\n\nCategory:"
        )
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=20,
            temperature=0.0,
            n=1,
            stop=["\n"]
        )
        category = response.choices[0].text.strip()
        allowed_categories = ['Work', 'Personal', 'Promotions', 'Social', 'Updates']
        if category not in allowed_categories:
            category = 'Other'
    except Exception as e:
        print(f"Error classifying email: {e}")
        category = 'Other'
    return category

def get_or_create_label(service, label_name):
    """
    Retrieves the Gmail label ID for a given label name or creates it if it doesn't exist.
    """
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    for label in labels:
        if label['name'].lower() == label_name.lower():
            return label['id']
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    created_label = service.users().labels().create(userId='me', body=label_body).execute()
    return created_label['id']

def add_label_to_message(service, msg_id, label_id):
    """
    Adds a specified label to a Gmail message.
    """
    body = {'addLabelIds': [label_id]}
    service.users().messages().modify(userId='me', id=msg_id, body=body).execute()

def get_message_details(service, msg_id):
    """
    Retrieves the subject and snippet for a given Gmail message ID.
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

def get_email_content(service, msg_id):
    """
    Retrieves the full email content (subject and body) for a given message ID.
    Attempts to decode plain text content.
    """
    message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = message.get('payload', {}).get('headers', [])
    subject = ""
    for header in headers:
        if header.get('name', '').lower() == 'subject':
            subject = header.get('value', '')
            break

    body = ""
    payload = message.get('payload', {})
    
    # If the email is multipart, look for a part with mimeType "text/plain"
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    try:
                        body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
                    except Exception:
                        body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('latin-1')
                    break
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            try:
                body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
            except Exception:
                body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('latin-1')

    return subject, body

def run_gmail_agent(custom_prompt=None):
    """
    Executes the Gmail AI Agent:
      - Authenticates with Gmail.
      - Retrieves unread emails.
      - Uses OpenAI (with a custom prompt, if provided) to classify each email.
      - Creates (or retrieves) Gmail labels.
      - Applies labels to the emails.
    Returns a report string.
    """
    service = gmail_authenticate()
    query = "is:unread"
    results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
    messages = results.get('messages', [])
    report = []
    if not messages:
        report.append("No messages found.")
        return "\n".join(report)
    for msg in messages:
        msg_id = msg['id']
        subject, snippet = get_message_details(service, msg_id)
        category = classify_email(subject, snippet, custom_prompt)
        label_id = get_or_create_label(service, category)
        add_label_to_message(service, msg_id, label_id)
        report.append(f"Email '{subject}' classified as {category} and labeled.")
    return "\n".join(report)

# -------------------------
# Flask Routes
# -------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run():
    custom_prompt = request.form.get('custom_prompt', None)
    try:
        result = run_gmail_agent(custom_prompt)
        flash(result, 'success')
    except Exception as e:
        flash(f"Error: {str(e)}", 'danger')
    return redirect(url_for('index'))

@app.route('/folders')
def folders():
    """
    Lists all Gmail labels (folders).
    """
    service = gmail_authenticate()
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    return render_template('folders.html', labels=labels)

@app.route('/folder/<label_id>')
def folder(label_id):
    """
    Displays emails contained within a specific Gmail label.
    """
    service = gmail_authenticate()
    results = service.users().messages().list(userId='me', labelIds=[label_id]).execute()
    messages = results.get('messages', [])
    email_details = []
    for msg in messages:
        msg_id = msg['id']
        subject, snippet = get_message_details(service, msg_id)
        email_details.append({'id': msg_id, 'subject': subject, 'snippet': snippet})
    return render_template('folder.html', emails=email_details, label_id=label_id)

@app.route('/email/<msg_id>')
def view_email(msg_id):
    """
    Instead of displaying the email content, this route creates a link
    that, when clicked, opens the email in Gmail's web interface.
    """
    # Construct the Gmail URL. You can use "#all" or "#inbox" depending on your needs.
    gmail_link = f"https://mail.google.com/mail/u/0/#all/{msg_id}"
    return render_template('email.html', gmail_link=gmail_link)

if __name__ == '__main__':
    app.run(debug=True)

# Gmail AI Agent

The Gmail AI Agent is a Python-based application that automatically organizes your Gmail inbox using OpenAI's GPT-3 and the Gmail API. The project authenticates with Gmail via OAuth, retrieves unread emails, classifies them into predefined categories, and then applies the corresponding Gmail labels. A Flask-based web interface is also provided for easy monitoring and manual triggering of the process.

## Features

- **Automated Email Classification:**  
  Uses GPT-3 to classify emails into categories such as Work, Personal, Promotions, Social, or Updates.  
  - *Custom Prompt Support:* Restrict classification to specific categories (e.g., only "Work" and "Social").

- **Gmail API Integration:**  
  Securely authenticates using OAuth 2.0 and leverages the Gmail API to fetch and update emails.

- **Responsive Web Interface:**  
  Built with Flask and Bootstrap to allow users to trigger email processing and view organized labels.

- **Performance Metrics (Example):**  
  - Processes up to **100 unread emails per run**  
  - Achieves an estimated **90% classification accuracy**  
  - Automatically labels over **10,000 emails monthly**  
  - Reduces manual email sorting time by **75%**

## Prerequisites

- **Python 3.6+**
- **Gmail API Enabled:** Create a Google Cloud project, enable the Gmail API, and download the `credentials.json` file.
- **OpenAI API Key:** Obtain an API key from [OpenAI](https://openai.com/).
- **Virtual Environment (Recommended):** To isolate dependencies.
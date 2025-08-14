# app.py - Upgraded Flask backend for a professional WhatsApp tool

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import requests
import json
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import threading # For scheduling template sends

# Load environment variables from .env file
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key_for_dev') # Use a strong key in production!

# --- API and File Configurations ---
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mysecrettoken123") # Add this to your .env
FUNNEL_FILE = 'funnels.json'
LOG_FILE = 'log.json'
MESSAGES_FILE = 'messages.json' # New file for storing chat messages

# --- Dummy Data and Utility Functions ---
USERS = {"admin": "admin123"}
funnels = {}
if os.path.exists(FUNNEL_FILE):
    with open(FUNNEL_FILE) as f:
        funnels = json.load(f)

def log(msg, log_type="INFO"):
    """
    Writes a structured log entry to the log.json file.
    Args:
        msg (str): The log message.
        log_type (str): The type of log (e.g., INFO, WARNING, ERROR).
    """
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": log_type,
        "message": msg
    }
    logs = []
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        try:
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
        except json.JSONDecodeError:
            logs = [] # Corrupted file, start fresh
    
    logs.append(new_entry)
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

def load_messages():
    """Loads all messages from messages.json."""
    if os.path.exists(MESSAGES_FILE) and os.path.getsize(MESSAGES_FILE) > 0:
        try:
            with open(MESSAGES_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            log("❌ messages.json file is corrupted. Starting fresh.", log_type="ERROR")
            return {} # Return empty dict if corrupted
    return {}

def save_messages_to_file(all_messages):
    """Saves the entire messages dictionary to messages.json."""
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(all_messages, f, indent=2)

def save_chat_message(phone_number, message_text, is_from_me, message_type="text"):
    """
    Saves a single chat message to the messages.json structure.
    Messages are stored per phone number.
    """
    all_messages = load_messages()
    if phone_number not in all_messages:
        all_messages[phone_number] = []
    
    new_message = {
        "id": str(len(all_messages[phone_number]) + 1), # Simple ID
        "text": message_text,
        "timestamp": datetime.now().isoformat(),
        "isFromMe": is_from_me,
        "type": message_type # e.g., "text", "template", "image"
    }
    all_messages[phone_number].append(new_message)
    save_messages_to_file(all_messages)
    log(f"Chat message saved for {phone_number}: {'Me ->' if is_from_me else '-> Me'} {message_text[:50]}...", log_type="INFO")

def send_whatsapp_message(to_number, message_body):
    """Sends a plain text message via WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": { "body": message_body }
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        log(f"✅ Text message sent to {to_number}: {message_body[:50]}...", log_type="INFO")
        save_chat_message(to_number, message_body, is_from_me=True, message_type="text") # Save outgoing message
        return True
    except requests.exceptions.RequestException as e:
        log(f"❌ Failed to send text message to {to_number}: {e}", log_type="ERROR")
        return False

def send_whatsapp_template(number, template_name):
    """Sends a template message via WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": { "code": "en_US" }
        }
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        log(f"✅ Template '{template_name}' sent to {number}", log_type="INFO")
        save_chat_message(number, f"Template: {template_name}", is_from_me=True, message_type="template") # Save outgoing template
    except requests.exceptions.RequestException as e:
        log(f"❌ Failed to send template to {number}: {e}", log_type="ERROR")

def get_whatsapp_templates():
    """Fetches the list of approved message templates from WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        return r.json().get('data', [])
    except requests.exceptions.RequestException as e:
        log(f"❌ Failed to fetch templates: {e}", log_type="ERROR")
        return []

# Yeh functions aapke contacts.db database ko handle karenge
# Aur JSON format mein data return karenge.

def get_all_contacts():
    conn = None
    contacts_list = []
    try:
        conn = sqlite3.connect('contacts.db')
        conn.row_factory = sqlite3.Row # Allows access by column name
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contacts ORDER BY name ASC')
        contacts = cursor.fetchall()
        for contact in contacts:
            contacts_list.append(dict(contact)) # Convert row to a dictionary
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
    return contacts_list

# Yeh function database ko city aur tags ke saath set karega
def setup_database():
    conn = sqlite3.connect('contacts.db')
    cursor = conn.cursor()
    # Purane table ko delete karein aur naya banayein
    cursor.execute('DROP TABLE IF EXISTS contacts')
    cursor.execute('''
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY,
            phone_number TEXT UNIQUE NOT NULL,
            name TEXT,
            email TEXT,
            city TEXT,
            tags TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database setup complete with new fields.")

# Naya contact add karne ka function
def add_contact(phone_number, name, email=None, city=None, tags=None, notes=None):
    try:
        conn = sqlite3.connect('contacts.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO contacts (phone_number, name, email, city, tags, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (phone_number, name, email, city, tags, notes))
        conn.commit()
        return {"status": "success", "message": f"Contact '{name}' added."}
    except sqlite3.IntegrityError:
        return {"status": "error", "message": f"Phone number '{phone_number}' already exists."}
    finally:
        if conn:
            conn.close()

def update_contact(phone_number, new_name=None, new_email=None, new_city=None, new_tags=None, new_notes=None):
    try:
        conn = sqlite3.connect('contacts.db')
        cursor = conn.cursor()
        updates = []
        params = []
        if new_name is not None:
            updates.append("name = ?")
            params.append(new_name)
        if new_email is not None:
            updates.append("email = ?")
            params.append(new_email)
        if new_city is not None:
            updates.append("city = ?")
            params.append(new_city)
        if new_tags is not None:
            updates.append("tags = ?")
            params.append(new_tags)
        if new_notes is not None:
            updates.append("notes = ?")
            params.append(new_notes)
        if not updates:
            return {"status": "error", "message": "No new data provided for update."}
        params.append(phone_number)
        query = f"UPDATE contacts SET {', '.join(updates)} WHERE phone_number = ?"
        cursor.execute(query, params)
        conn.commit()
        if cursor.rowcount > 0:
            return {"status": "success", "message": f"Contact '{phone_number}' updated."}
        else:
            return {"status": "error", "message": f"Contact '{phone_number}' not found."}
    finally:
        if conn:
            conn.close()

def delete_contact(phone_number):
    try:
        conn = sqlite3.connect('contacts.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE phone_number = ?", (phone_number,))
        conn.commit()
        if cursor.rowcount > 0:
            return {"status": "success", "message": f"Contact '{phone_number}' deleted."}
        else:
            return {"status": "error", "message": f"Contact '{phone_number}' not found."}
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Ab, yeh API routes `app.py` mein jodein

@app.route('/api/contacts', methods=['GET', 'POST'])
def handle_contacts():
    if request.method == 'GET':
        contacts = get_all_contacts()
        return jsonify(contacts)
    elif request.method == 'POST':
        data = request.json
        # Yahan humne city aur tags ko bhi add kiya hai
        result = add_contact(
            phone_number=data.get('phone_number'),
            name=data.get('name'),
            email=data.get('email'),
            city=data.get('city'), # ✅ Sudhara gaya
            tags=data.get('tags'), # ✅ Sudhara gaya
            notes=data.get('notes')
        )
        if result['status'] == 'success':
            return jsonify(result), 201
        else:
            return jsonify(result), 400

@app.route('/api/contacts/<string:phone_number>', methods=['PUT', 'DELETE'])
def handle_single_contact(phone_number):
    if request.method == 'PUT':
        data = request.json
        # Yahan bhi humne city aur tags ko add kiya hai
        result = update_contact(
            phone_number=phone_number,
            new_name=data.get('name'),
            new_email=data.get('email'),
            new_city=data.get('city'), # ✅ Sudhara gaya
            new_tags=data.get('tags'), # ✅ Sudhara gaya
            new_notes=data.get('notes')
        )
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return jsonify(result), 404
    elif request.method == 'DELETE':
        result = delete_contact(phone_number=phone_number)
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return jsonify(result), 404
            
# --- Authentication and Routing ---
@app.before_request
def check_authentication():
    """
    Checks login status before each request, except for login and static files.
    """
    if request.path not in ['/login', '/static', '/webhook', '/embeddable-form', '/form-submission'] and 'user' not in session:
        return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and USERS[username] == password:
            session['user'] = username
            log(f"User '{username}' logged in successfully.", log_type="INFO")
            return redirect(url_for('dashboard'))
        
        log(f"❌ Failed login attempt for user '{username}'", log_type="WARNING")
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html', title='Login')

@app.route('/logout')
def logout():
    log(f"User '{session.get('user')}' logged out.", log_type="INFO")
    session.pop('user', None)
    return redirect(url_for('login'))

# --- Main Dashboard Routes ---
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', title='Dashboard')

@app.route('/inbox')
def inbox():
    # This route will now load the inbox HTML, JS will fetch data via API
    return render_template('inbox.html', title='Inbox')

@app.route('/templates')
def templates():
    templates_list = get_whatsapp_templates()
    return render_template('templates.html', title='Templates', templates=templates_list)

@app.route('/automation')
def automation():
    return render_template('automation.html', title='Automation')

@app.route('/logs')
def logs():
    logs_data = []
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        try:
            with open(LOG_FILE, 'r') as f:
                logs_data = json.load(f)
        except json.JSONDecodeError:
            log("❌ log.json file is corrupted. Clearing it.", log_type="ERROR")
            os.remove(LOG_FILE)
    
    return render_template('logs.html', title='System Logs', logs=logs_data)

@app.route('/clear-logs', methods=['POST'])
def clear_logs():
    if os.path.exists(LOG_FILE):
        try:
            os.remove(LOG_FILE)
            log("All logs cleared.", log_type="INFO")
            return jsonify({"status": "success", "message": "Logs cleared"}), 200
        except OSError as e:
            log(f"❌ Failed to clear logs: {e}", log_type="ERROR")
            return jsonify({"status": "error", "message": f"Failed to clear logs: {e}"}), 500
    return jsonify({"status": "success", "message": "No log file to clear"}), 200

# --- Funnel API Routes ---
@app.route('/funnels', methods=['GET'])
def get_funnels():
    return jsonify(funnels)

@app.route('/save-funnel', methods=['POST'])
def save_funnel():
    data = request.json
    keyword = data.get('keyword')
    steps = data.get('steps', [])
    if keyword:
        funnels[keyword.lower()] = steps
        with open(FUNNEL_FILE, 'w') as f:
            json.dump(funnels, f, indent=2)
        log(f"✅ Funnel '{keyword}' saved", log_type="INFO")
        return jsonify({"status": "success", "message": "Funnel saved"}), 200
    log("❌ Invalid data for funnel save.", log_type="WARNING")
    return jsonify({"status": "error", "message": "Invalid data"}), 400

@app.route('/delete-funnel', methods=['DELETE'])
def delete_funnel():
    keyword = request.args.get('keyword', '').lower()
    if keyword in funnels:
        del funnels[keyword]
        with open(FUNNEL_FILE, 'w') as f:
            json.dump(funnels, f, indent=2)
        log(f"🗑️ Funnel '{keyword}' deleted", log_type="INFO")
        return jsonify({"status": "success", "message": "Funnel deleted"}), 200
    log(f"❌ Funnel '{keyword}' not found for deletion.", log_type="WARNING")
    return jsonify({"status": "error", "message": "Funnel not found"}), 404

# --- New Inbox API Routes ---
@app.route('/api/chats', methods=['GET'])
def api_get_chats():
    """Returns a summary of all chats (last message, contact info)."""
    all_messages = load_messages()
    chat_summaries = []
    for phone_number, messages in all_messages.items():
        if messages:
            last_message = messages[-1]
            chat_summaries.append({
                "phone_number": phone_number,
                "last_message": last_message['text'],
                "timestamp": last_message['timestamp'],
                "isFromMe": last_message['isFromMe']
            })
    # Sort chats by latest message
    chat_summaries.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(chat_summaries)

@app.route('/api/chats/<phone_number>', methods=['GET'])
def api_get_chat_history(phone_number):
    """Returns the full message history for a specific phone number."""
    all_messages = load_messages()
    messages = all_messages.get(phone_number, [])
    return jsonify(messages)

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """Handles sending a message from the inbox UI."""
    data = request.json
    to_number = data.get('to_number')
    message_body = data.get('message_body')

    if not to_number or not message_body:
        return jsonify({"status": "error", "message": "Missing to_number or message_body"}), 400
    
    success = send_whatsapp_message(to_number, message_body)
    if success:
        return jsonify({"status": "success", "message": "Message sent"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    
@app.route('/embeddable-form')
def embeddable_form():
    """Renders just the form HTML for embedding via iframe."""
    return render_template('embeddable_form.html')

# --- Webhook for Incoming Messages ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # --- Webhook Verification (GET Request) ---
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN: # Use WHATSAPP_VERIFY_TOKEN from .env
            log("✅ Webhook verified successfully!")
            return challenge, 200
        else:
            log("❌ Webhook verification failed.", log_type="ERROR")
            return "Verification token mismatch", 403

    # --- Receive & Process Messages (POST Request) ---
    data = request.json
    log(f"Received webhook: {json.dumps(data)}", log_type="INFO") # Log full webhook for debugging
    try:
        entry = data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        if messages:
            msg = messages[0]
            from_number = msg['from']
            
            # Handle different message types (text, image, etc.)
            if msg['type'] == 'text':
                message_text = msg['text']['body']
                save_chat_message(from_number, message_text, is_from_me=False, message_type="text")
                log(f"Incoming text message from {from_number}: {message_text[:50]}...", log_type="INFO")

                # Funnel trigger logic
                if message_text.strip().lower() in funnels:
                    steps = funnels[message_text.strip().lower()]
                    for step in steps:
                        delay = step.get('delay', 5)
                        template_name = step.get('template')
                        threading.Timer(delay, send_whatsapp_template, args=(from_number, template_name)).start()
                    log(f"⚡ Trigger '{message_text.strip().lower()}' matched. Scheduled {len(steps)} steps for {from_number}", log_type="INFO")
            elif msg['type'] == 'image':
                # You might want to save image URL or handle it differently
                save_chat_message(from_number, " (Image received) ", is_from_me=False, message_type="image")
                log(f"Incoming image message from {from_number}", log_type="INFO")
            # Add more message types as needed (video, audio, document etc.)
            
    except (IndexError, KeyError) as e:
        log(f"❌ Webhook payload processing failed: {e}. Full data: {json.dumps(data)}", log_type="ERROR")
    except Exception as e:
        log(f"❌ An unexpected error occurred in webhook: {e}. Full data: {json.dumps(data)}", log_type="ERROR")
    
    return 'EVENT_RECEIVED', 200

# ✅ Sudhara gaya: ab sirf ek hi block hai
# ✅ Sudhara gaya: ab sirf ek hi block hai
if __name__ == '__main__':
    # Create the database table
    setup_database()

    # Ensure messages.json exists or is created as an empty dict
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump({}, f)

    # Render port binding
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)



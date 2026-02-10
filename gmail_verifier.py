import imaplib
import email
import re
import time

class GmailVerifier:
    def __init__(self, email_user, email_pass):
        self.email_user = email_user
        self.email_pass = email_pass
        self.imap_url = 'imap.gmail.com'

    def get_verification_code(self, sender_filter, wait_time=60):
        """
        Connects to Gmail and searches for a verification code from a specific sender.
        """
        start_time = time.time()
        while time.time() - start_time < wait_time:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_url)
                mail.login(self.email_user, self.email_pass)
                mail.select('inbox')

                # Search for unseen emails from the sender
                status, data = mail.search(None, f'(UNSEEN FROM "{sender_filter}")')
                
                if status == 'OK':
                    for num in data[0].split():
                        status, data = mail.fetch(num, '(RFC822)')
                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                        else:
                            body = msg.get_payload(decode=True).decode()

                        # Extract 6-digit code using regex
                        code_match = re.search(r'\b\d{6}\b', body)
                        if code_match:
                            return code_match.group(0)
                
                mail.logout()
            except Exception as e:
                print(f"Error checking Gmail: {e}")
            
            time.sleep(10) # Wait before checking again
        return None

# Example usage:
# verifier = GmailVerifier('your_email@gmail.com', 'your_app_password')
# code = verifier.get_verification_code('noreply@ea.com')

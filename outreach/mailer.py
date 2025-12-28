import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import sys
from pathlib import Path

# Handle both direct execution and module import
try:
    from . import config
except ImportError:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from outreach import config


class SMTPMailer:
    """Manages the lifecycle of the SMTP connection safely and includes resilience logic."""

    def __init__(self):
        self.server = None
        self.connected = False
        self.max_retries = 1 # We only need one retry attempt to re-establish the connection

    def connect(self):
        """Establishes and logs into the SMTP server."""
        try:
            # Disconnect first if server object still exists but connection is stale
            if self.server:
                try:
                    self.server.quit()
                except:
                    pass
                self.server = None

            self.server = smtplib.SMTP(
                config.SMTP_SERVER,
                config.SMTP_PORT,
                timeout=30 # Keep the timeout
            )
            self.server.ehlo()
            self.server.starttls()
            self.server.ehlo()
            self.server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)

            self.connected = True
            logging.info("SMTP connection established.")
            return True

        except Exception as e:
            logging.critical(f"SMTP connection failed: {e}")
            print(f"❌ FATAL ERROR: Could not connect or log into SMTP server. Error: {e}")
            self.server = None
            self.connected = False
            return False

    def disconnect(self):
        """Closes the SMTP connection safely."""
        if not self.server:
            return

        try:
            self.server.quit()
            logging.info("SMTP connection closed.")
            print("✅ SMTP connection closed.")
        except smtplib.SMTPServerDisconnected:
            logging.info("SMTP server already disconnected.")
        except Exception as e:
            logging.warning(f"Error while closing SMTP connection: {e}")
        finally:
            self.server = None
            self.connected = False

    def send_email(self, recipient_email, subject, body, retry_count=0):
        """
        Sends a single email, attempting to reconnect and retry on disconnect.
        """
        # Ensure the connection is active
        if not self.server or not self.connected:
            logging.warning("Connection lost before send. Attempting to reconnect...")
            if not self.connect():
                logging.error("Failed to connect before send.")
                return "FAILED_OTHER"

        msg = MIMEMultipart()
        msg["From"] = config.SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            self.server.sendmail(
                config.SENDER_EMAIL,
                recipient_email,
                msg.as_string()
            )
            return "SUCCESS"

        except smtplib.SMTPRecipientsRefused as e:
            # 1. IMMEDIATE FAILURE: Recipient rejected (e.g., 550 Mailbox Not Found)
            logging.warning(
                f"FAILURE | Recipient refused: {recipient_email} | Error: {e}"
            )
            return "FAILED_REFUSED"

        except smtplib.SMTPServerDisconnected as e:
            # 2. TIMEOUT/CONNECTION FAILURE: Server forcibly closed the connection (like 421)
            self.connected = False # Mark the connection as lost
            
            if retry_count < self.max_retries:
                logging.warning(
                    f"Connection lost for {recipient_email}. Reconnecting and retrying (Attempt {retry_count + 1})..."
                )
                
                # Attempt to reconnect
                if self.connect():
                    # Retry the send immediately with an incremented counter
                    return self.send_email(recipient_email, subject, body, retry_count=retry_count + 1)
                else:
                    logging.error(f"Failed to reconnect to SMTP server after disconnect for {recipient_email}.")
                    return "FAILED_OTHER"
            else:
                logging.error(
                    f"Max retries exceeded for {recipient_email} after SMTPServerDisconnected."
                )
                return "FAILED_OTHER"

        except Exception as e:
            # 3. Handle all other unexpected errors
            logging.error(
                f"FAILURE | Unknown error: {recipient_email} | Error: {e}"
            )
            return "FAILED_OTHER"
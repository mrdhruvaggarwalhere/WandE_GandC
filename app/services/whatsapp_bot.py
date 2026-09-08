"""
Background WhatsApp Bot Service using Playwright & Persistent Chrome Session.
Enables 100% free, zero-API direct document dispatch via WhatsApp Web without drag-and-drop.
"""

import os
import time
import base64
import logging
import threading
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger("whatsapp_bot")
logger.setLevel(logging.INFO)

SESSION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "whatsapp_session"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class WhatsAppBot:
    def __init__(self):
        self._lock = threading.Lock()
        self.status = "DISCONNECTED"  # DISCONNECTED, STARTING, NEEDS_QR, CONNECTING, READY, ERROR
        self.qr_code_b64: Optional[str] = None
        self.last_error: Optional[str] = None
        self.phone_number: Optional[str] = None
        
        self._playwright = None
        self._context = None
        self._page = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_ready": self.status == "READY",
            "needs_qr": self.status == "NEEDS_QR",
            "qr_code": self.qr_code_b64,
            "error": self.last_error,
            "session_active": self._context is not None
        }

    def start(self):
        """Starts the bot in a background thread if not already running."""
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self.status = "STARTING"
            self.last_error = None
            self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._worker_thread.start()

    def _run_loop(self):
        from playwright.sync_api import sync_playwright

        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        try:
            logger.info("Initializing Playwright background session...")
            self._playwright = sync_playwright().start()

            launch_kwargs = {
                "user_data_dir": str(SESSION_DIR),
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            }
            if os.path.exists(CHROME_PATH):
                launch_kwargs["executable_path"] = CHROME_PATH

            self._context = self._playwright.chromium.launch_persistent_context(
                **launch_kwargs,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )

            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            logger.info("Navigating to WhatsApp Web...")
            self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)

            # Loop to check state: QR code vs Ready
            consecutive_ready = 0
            while not self._stop_event.is_set():
                try:
                    # 1. Check if logged in (pane-side or search bar or chat list)
                    is_logged_in = self._page.query_selector("#pane-side") is not None or \
                                   self._page.query_selector("div[data-tab='3']") is not None or \
                                   self._page.query_selector("div[contenteditable='true']") is not None

                    if is_logged_in:
                        consecutive_ready += 1
                        if consecutive_ready >= 2:
                            self.status = "READY"
                            self.qr_code_b64 = None
                            self.last_error = None
                        time.sleep(3)
                        continue
                    else:
                        consecutive_ready = 0

                    # 2. Check for QR Canvas
                    canvas = self._page.query_selector("canvas")
                    if canvas:
                        self.status = "NEEDS_QR"
                        try:
                            # Capture QR code screenshot as base64
                            img_bytes = canvas.screenshot()
                            self.qr_code_b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
                        except Exception as e:
                            logger.warning(f"Failed to capture QR canvas: {e}")
                    else:
                        # Check if "Click to reload QR code" button exists
                        reload_btn = self._page.query_selector("button:has-text('Reload'), [data-ref] button")
                        if reload_btn:
                            try:
                                reload_btn.click()
                                time.sleep(2)
                            except Exception:
                                pass
                        
                        if self.status != "STARTING":
                            self.status = "CONNECTING"

                except Exception as loop_err:
                    logger.warning(f"Error in monitor loop: {loop_err}")

                time.sleep(2)

        except Exception as e:
            logger.error(f"Playwright worker encountered error: {e}", exc_info=True)
            self.status = "ERROR"
            self.last_error = str(e)
        finally:
            logger.info("WhatsApp bot monitor loop exiting.")

    def send_pdf(self, phone: str, message: str, pdf_path: str, filename: str) -> Dict[str, Any]:
        """Sends a PDF file and text message directly to a WhatsApp phone number."""
        with self._lock:
            if self.status != "READY" or not self._page:
                return {
                    "success": False,
                    "error": f"WhatsApp is not connected. Current status: {self.status}. Please link your device first."
                }

            # Normalize phone digits (e.g. 919461940113)
            phone_digits = "".join(c for c in phone if c.isdigit())
            if not phone_digits.startswith("91") and len(phone_digits) == 10:
                phone_digits = f"91{phone_digits}"

            if not os.path.exists(pdf_path):
                return {"success": False, "error": f"PDF file not found: {pdf_path}"}

            try:
                logger.info(f"Opening chat for phone: +{phone_digits}...")
                chat_url = f"https://web.whatsapp.com/send?phone={phone_digits}"
                self._page.goto(chat_url, wait_until="domcontentloaded", timeout=45000)

                # Wait for chat input or invalid phone number alert
                chat_loaded = False
                for _ in range(30):
                    time.sleep(1)
                    # Check invalid number popup
                    invalid_alert = self._page.query_selector("div:has-text('Phone number shared via url is invalid')")
                    if invalid_alert:
                        return {
                            "success": False,
                            "error": f"Phone number +{phone_digits} is invalid or not registered on WhatsApp."
                        }

                    # Check if composer / attach button is present
                    composer = self._page.query_selector("div[contenteditable='true'][data-tab='10']") or \
                               self._page.query_selector("footer div[contenteditable='true']")
                    attach_btn = self._page.query_selector("span[data-icon='plus'], span[data-icon='attach-menu-plus'], button[aria-label*='Attach']")
                    if composer or attach_btn:
                        chat_loaded = True
                        break

                if not chat_loaded:
                    return {"success": False, "error": "Chat failed to load within 30 seconds."}

                time.sleep(1)

                # Find file inputs on the page
                # WhatsApp Web has hidden file inputs. Let's look for one that accepts documents or all files
                file_inputs = self._page.query_selector_all("input[type='file']")
                target_input = None

                if not file_inputs or len(file_inputs) == 0:
                    # Click attach button to reveal inputs
                    attach_btn = self._page.query_selector("span[data-icon='plus'], span[data-icon='attach-menu-plus'], button[aria-label*='Attach']")
                    if attach_btn:
                        attach_btn.click()
                        time.sleep(1)
                        file_inputs = self._page.query_selector_all("input[type='file']")

                # Choose input for document or generic file
                for inp in file_inputs:
                    accept = inp.get_attribute("accept") or ""
                    if "*" in accept or "pdf" in accept or accept == "":
                        target_input = inp
                        break

                if not target_input and file_inputs:
                    target_input = file_inputs[0]

                if not target_input:
                    return {"success": False, "error": "Could not locate WhatsApp document upload input."}

                logger.info(f"Setting PDF input file: {pdf_path}")
                target_input.set_input_files(pdf_path)

                # Wait for attachment preview screen to appear (send button or caption input)
                time.sleep(2)
                send_btn = None
                for _ in range(15):
                    send_btn = self._page.query_selector("span[data-icon='send'], div[aria-label='Send'], button:has(span[data-icon='send'])")
                    if send_btn:
                        break
                    time.sleep(1)

                if not send_btn:
                    return {"success": False, "error": "Attachment preview did not appear."}

                # Optionally type message into caption if caption box exists
                caption_input = self._page.query_selector("div[contenteditable='true'][data-tab='10'], div[aria-placeholder*='Add a caption']")
                if caption_input and message:
                    try:
                        # Enter short notice in caption
                        caption_input.fill(f"Official Contract: {filename} • System-Generated Document")
                    except Exception as cap_err:
                        logger.warning(f"Could not fill caption: {cap_err}")

                # Click Send button
                logger.info("Clicking send button in WhatsApp attachment preview...")
                send_btn.click()

                # Wait for send to complete
                time.sleep(3)

                # Also send the formatted text details as a separate message for complete contract terms
                try:
                    composer = self._page.query_selector("footer div[contenteditable='true']")
                    if composer and message:
                        composer.click()
                        # Use clipboard or keyboard to type multiline text cleanly
                        self._page.keyboard.insert_text(message)
                        time.sleep(0.5)
                        self._page.keyboard.press("Enter")
                        time.sleep(2)
                except Exception as msg_err:
                    logger.warning(f"Could not send follow-up text message: {msg_err}")

                logger.info(f"Successfully sent PDF to +{phone_digits}")
                return {
                    "success": True,
                    "phone": phone_digits,
                    "filename": filename,
                    "detail": "PDF document and contract terms delivered directly to WhatsApp."
                }

            except Exception as send_err:
                logger.error(f"Failed to send PDF via WhatsApp: {send_err}", exc_info=True)
                return {"success": False, "error": str(send_err)}

    def stop(self):
        self._stop_event.set()
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self.status = "DISCONNECTED"
        self.qr_code_b64 = None


# Singleton instance
whatsapp_bot = WhatsAppBot()

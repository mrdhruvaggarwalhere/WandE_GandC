"""
Background WhatsApp Bot Service using Playwright & Persistent Chrome Session.
Enables 100% free, zero-API direct document dispatch via WhatsApp Web without drag-and-drop.
Uses a dedicated single-threaded job queue to guarantee all Playwright calls stay on the creator thread (preventing greenlet thread switch errors).
"""

import os
import time
import base64
import queue
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
        
        self._playwright = None
        self._context = None
        self._page = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._job_queue: queue.Queue = queue.Queue()

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
            self._worker_thread = threading.Thread(target=self._run_loop, name="WhatsAppBotThread", daemon=True)
            self._worker_thread.start()

    def _run_loop(self):
        """
        Runs entirely on the dedicated worker thread.
        All Playwright sync API calls MUST occur within this thread to satisfy greenlet.
        """
        from playwright.sync_api import sync_playwright

        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        try:
            logger.info("Initializing Playwright background session on dedicated thread...")
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

            consecutive_ready = 0
            while not self._stop_event.is_set():
                # 1. Process any pending jobs from the queue first
                try:
                    job = self._job_queue.get_nowait()
                except queue.Empty:
                    job = None

                if job:
                    action = job.get("action")
                    done_event = job.get("done_event")
                    try:
                        if action == "send_pdf":
                            job["result"] = self._do_send_pdf(
                                job["phone"], job["message"], job["pdf_path"], job["filename"]
                            )
                        else:
                            job["result"] = {"success": False, "error": f"Unknown action: {action}"}
                    except Exception as job_err:
                        logger.exception("Error processing WhatsApp job")
                        job["result"] = {"success": False, "error": str(job_err)}
                    finally:
                        if done_event:
                            done_event.set()
                    # Continue immediately to next loop iteration
                    continue

                # 2. State checking: logged in vs QR code
                try:
                    is_logged_in = self._page.query_selector("#pane-side") is not None or \
                                   self._page.query_selector("div[data-tab='3']") is not None or \
                                   self._page.query_selector("div[contenteditable='true']") is not None

                    if is_logged_in:
                        consecutive_ready += 1
                        if consecutive_ready >= 2:
                            self.status = "READY"
                            self.qr_code_b64 = None
                            self.last_error = None
                        time.sleep(1.5)
                        continue
                    else:
                        consecutive_ready = 0

                    # Check for QR canvas
                    canvas = self._page.query_selector("canvas")
                    if canvas:
                        self.status = "NEEDS_QR"
                        try:
                            img_bytes = canvas.screenshot()
                            self.qr_code_b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
                        except Exception as e:
                            logger.warning(f"Failed to capture QR canvas: {e}")
                    else:
                        # Reload button if QR expired
                        reload_btn = self._page.query_selector("button:has-text('Reload'), [data-ref] button")
                        if reload_btn:
                            try:
                                reload_btn.click()
                                time.sleep(1)
                            except Exception:
                                pass

                        if self.status != "STARTING":
                            self.status = "CONNECTING"

                except Exception as loop_err:
                    logger.warning(f"Error in monitor loop: {loop_err}")

                time.sleep(1)

        except Exception as e:
            logger.error(f"Playwright worker encountered error: {e}", exc_info=True)
            self.status = "ERROR"
            self.last_error = str(e)
        finally:
            logger.info("WhatsApp bot monitor loop exiting.")

    def _do_send_pdf(self, phone: str, message: str, pdf_path: str, filename: str) -> Dict[str, Any]:
        """
        Executes on the worker thread.
        Navigates to the chat, attaches the PDF, and sends the message.
        """
        if self.status != "READY" or not self._page:
            return {
                "success": False,
                "error": f"WhatsApp is not connected (status: {self.status}). Please link your device first."
            }

        phone_digits = "".join(c for c in phone if c.isdigit())
        if not phone_digits.startswith("91") and len(phone_digits) == 10:
            phone_digits = f"91{phone_digits}"

        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"PDF file not found: {pdf_path}"}

        logger.info(f"Opening chat for phone: +{phone_digits}...")
        chat_url = f"https://web.whatsapp.com/send?phone={phone_digits}"
        self._page.goto(chat_url, wait_until="domcontentloaded", timeout=45000)

        # Wait for chat input or invalid phone number alert
        chat_loaded = False
        for _ in range(25):
            time.sleep(1)
            # Check invalid number popup
            invalid_alert = self._page.query_selector("div:has-text('Phone number shared via url is invalid')")
            if invalid_alert:
                return {
                    "success": False,
                    "error": f"Phone number +{phone_digits} is invalid or not registered on WhatsApp."
                }

            composer = self._page.query_selector("footer div[contenteditable='true']")
            attach_btn = self._page.query_selector("span[data-icon='plus'], span[data-icon='attach-menu-plus'], button[aria-label*='Attach']")
            if composer or attach_btn:
                chat_loaded = True
                break

        if not chat_loaded:
            return {"success": False, "error": "WhatsApp chat took too long to load (timeout 25s)."}

        time.sleep(1)

        # 1. Click attach button to reveal inputs if needed
        attach_btn = self._page.query_selector("span[data-icon='plus'], span[data-icon='attach-menu-plus'], button[aria-label*='Attach']")
        if attach_btn:
            try:
                attach_btn.click()
                time.sleep(0.8)
            except Exception:
                pass

        # 2. Find file input
        file_inputs = self._page.query_selector_all("input[type='file']")
        target_input = None

        for inp in file_inputs:
            accept = inp.get_attribute("accept") or ""
            # Document input typically accepts "*", "*/*", or doesn't restrict to image/video
            if "*" in accept or "pdf" in accept or "document" in accept:
                target_input = inp
                break

        if not target_input and file_inputs:
            target_input = file_inputs[0]

        if not target_input:
            return {"success": False, "error": "Could not find WhatsApp attachment upload element."}

        logger.info(f"Uploading PDF file: {pdf_path}")
        target_input.set_input_files(pdf_path)

        # 3. Wait for send button in preview screen
        time.sleep(2)
        send_btn = None
        for _ in range(15):
            send_btn = self._page.query_selector("span[data-icon='send'], div[aria-label='Send'], button:has(span[data-icon='send'])")
            if send_btn:
                break
            time.sleep(1)

        if not send_btn:
            return {"success": False, "error": "Attachment preview did not appear."}

        # Type optional short caption
        caption_input = self._page.query_selector("div[contenteditable='true'][data-tab='10'], div[aria-placeholder*='Add a caption']")
        if caption_input:
            try:
                caption_input.fill(f"Official Contract: {filename} • System Generated")
            except Exception:
                pass

        logger.info("Clicking Send for PDF attachment...")
        send_btn.click()
        time.sleep(3)

        # 4. Also send formatted text details as a follow-up message in chat
        if message:
            try:
                composer = self._page.query_selector("footer div[contenteditable='true']")
                if composer:
                    composer.click()
                    self._page.keyboard.insert_text(message)
                    time.sleep(0.5)
                    self._page.keyboard.press("Enter")
                    time.sleep(2)
            except Exception as msg_err:
                logger.warning(f"Could not send follow-up message: {msg_err}")

        logger.info(f"Successfully sent PDF to +{phone_digits}")
        return {
            "success": True,
            "phone": phone_digits,
            "filename": filename,
            "detail": "PDF document and contract terms delivered directly to WhatsApp."
        }

    def send_pdf(self, phone: str, message: str, pdf_path: str, filename: str) -> Dict[str, Any]:
        """
        Thread-safe external entry point.
        Dispatches the job to the worker thread queue and waits for completion.
        Guarantees NO greenlet thread switch error.
        """
        if self.status != "READY":
            return {
                "success": False,
                "error": f"WhatsApp is not connected (status: {self.status}). Please click 'Link WhatsApp' to scan the QR code."
            }

        done_event = threading.Event()
        job = {
            "action": "send_pdf",
            "phone": phone,
            "message": message,
            "pdf_path": pdf_path,
            "filename": filename,
            "done_event": done_event,
            "result": None
        }

        self._job_queue.put(job)
        finished = done_event.wait(timeout=90)
        if not finished:
            return {"success": False, "error": "WhatsApp send operation timed out after 90 seconds."}

        return job.get("result") or {"success": False, "error": "No response from WhatsApp worker."}

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

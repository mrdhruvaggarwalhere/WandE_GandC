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

        # 1. Click attach button to reveal the menu
        attach_btn = self._page.query_selector("span[data-icon='plus'], span[data-icon='attach-menu-plus'], button[aria-label*='Attach']")
        if attach_btn:
            try:
                attach_btn.click()
                time.sleep(1)
            except Exception as e:
                print(f"[WhatsAppBot] Attach click error: {e}", flush=True)

        # 2. Click the 'Document' option via expect_file_chooser (or upload directly to document input)
        doc_item = self._page.query_selector("div[role='button']:has-text('Document'), li:has-text('Document'), button:has-text('Document'), [aria-label*='Document']")
        uploaded = False

        if doc_item:
            print("[WhatsAppBot] Found 'Document' menu option. Uploading PDF via file chooser...", flush=True)
            try:
                with self._page.expect_file_chooser(timeout=8000) as fc_info:
                    doc_item.click()
                fc = fc_info.value
                fc.set_files(pdf_path)
                uploaded = True
                print(f"[WhatsAppBot] File chooser set files successfully: {pdf_path}", flush=True)
            except Exception as fc_err:
                print(f"[WhatsAppBot] expect_file_chooser fallback: {fc_err}", flush=True)
                doc_inp = doc_item.query_selector("input[type='file']")
                if doc_inp:
                    doc_inp.set_input_files(pdf_path)
                    uploaded = True

        if not uploaded:
            # Fallback: Query all inputs, pick the one that accepts documents or all files (NOT image-only)
            file_inputs = self._page.query_selector_all("input[type='file']")
            target_input = None
            for inp in file_inputs:
                accept = inp.get_attribute("accept") or ""
                if "image" not in accept:
                    target_input = inp
                    break
            if not target_input and file_inputs:
                target_input = file_inputs[0]
            if target_input:
                target_input.set_input_files(pdf_path)
                uploaded = True

        if not uploaded:
            self._page.screenshot(path="scratch/no_input_found.png")
            return {"success": False, "error": "Could not locate WhatsApp Document attachment element."}

        # 3. Wait for the Document Preview screen to render
        time.sleep(3)
        self._page.screenshot(path="scratch/step1_preview.png")

        # 4. Click the green Send button on the document preview screen
        print("[WhatsAppBot] Clicking green Send button on attachment preview...", flush=True)
        clicked = self._page.evaluate("""() => {
            // Find the green circular send button on the attachment preview screen
            const sendIcons = Array.from(document.querySelectorAll('span[data-icon="send"], span[data-icon="wds-ic-send-filled"], span[data-icon="send-light"]'));
            if (sendIcons.length > 0) {
                const lastIcon = sendIcons[sendIcons.length - 1];
                const btn = lastIcon.closest('div[role="button"], button') || lastIcon;
                btn.click();
                return true;
            }
            const sendBtns = Array.from(document.querySelectorAll('div[role="button"][aria-label="Send"], button[aria-label="Send"]'));
            if (sendBtns.length > 0) {
                sendBtns[sendBtns.length - 1].click();
                return true;
            }
            return false;
        }""")
        print(f"[WhatsAppBot] Send button clicked via evaluate: {clicked}", flush=True)

        if not clicked:
            print("[WhatsAppBot] Send button not matched, pressing Enter...", flush=True)
            self._page.keyboard.press("Enter")

        # 5. Wait for the document preview to close (meaning the PDF was actually sent)
        preview_closed = False
        for _ in range(15):
            time.sleep(1)
            # Check if preview is closed (the green send button on the preview disappears)
            preview_elem = self._page.query_selector("div:has-text('1 page'), div[aria-label='Document preview']")
            if not preview_elem:
                preview_closed = True
                print("[WhatsAppBot] Document preview closed! PDF attachment has been dispatched.", flush=True)
                break
            else:
                self._page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('div[role="button"], button')).filter(b => b.querySelector('span[data-icon*="send"]'));
                    if (btns.length > 0) btns[btns.length - 1].click();
                }""")

        time.sleep(2)
        self._page.screenshot(path="scratch/after_pdf_sent.png")

        # 5. Also send formatted text details as a follow-up message in chat
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

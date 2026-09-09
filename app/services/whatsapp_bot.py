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
import subprocess
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
                        elif action == "custom":
                            fn = job.get("fn")
                            job["result"] = fn(self._page)
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

        old_header = ""
        header_el = self._page.query_selector("header")
        if header_el:
            try:
                old_header = header_el.inner_text().strip()
            except Exception:
                pass

        # Close any lingering full-screen viewer or overlay
        try:
            self._page.keyboard.press("Escape")
        except Exception:
            pass

        logger.info(f"Opening chat for phone: +{phone_digits} (previous chat header: {old_header.splitlines()[0] if old_header else 'None'})...")
        chat_url = f"https://web.whatsapp.com/send?phone={phone_digits}"

        # Navigate to target chat
        try:
            self._page.goto(chat_url, timeout=45000)
        except Exception as nav_err:
            logger.warning(f"page.goto note: {nav_err}")

        # Wait for target chat composer and attach button to appear
        chat_loaded = False
        for attempt in range(40):
            time.sleep(1.0)

            # 1. Check invalid phone popup
            invalid_alert = self._page.query_selector("div:has-text('Phone number shared via url is invalid')")
            if invalid_alert:
                return {
                    "success": False,
                    "error": f"Phone number +{phone_digits} is invalid or not registered on WhatsApp."
                }

            # 2. Check if still syncing or loading
            starting = self._page.query_selector("div:has-text('Starting chat'), div:has-text('Looking for phone number'), div[data-icon='reload'], div[role='progressbar']")
            if starting:
                continue

            # 3. Check composer and attach button
            composer = self._page.query_selector("footer div[contenteditable='true'], div[role='textbox'][aria-label*='Type a message']")
            attach_btn = self._page.query_selector("button[aria-label*='Attach' i], span[data-icon='plus'], span[data-icon='attach-menu-plus']")

            if composer and attach_btn:
                # Chat is open, active, and composer is ready for input
                chat_loaded = True
                h = self._page.query_selector("header")
                header_text = h.inner_text().splitlines()[0] if h else phone_digits
                print(f"[WhatsAppBot] Chat ready for +{phone_digits} (header: {header_text}) after {attempt + 1}s", flush=True)
                break

        if not chat_loaded:
            try:
                self._page.screenshot(path="scratch/chat_timeout.png")
            except Exception:
                pass
            return {"success": False, "error": f"WhatsApp chat for +{phone_digits} took too long to load."}

        # Ensure any open media viewer or overlay is closed first
        close_btn = self._page.query_selector("div[aria-label='Close'], button[aria-label='Close'], span[data-icon='x-viewer']")
        if close_btn:
            try:
                close_btn.click()
                time.sleep(0.5)
            except Exception:
                pass

        # Clear any leftover unsent draft text in the footer composer
        try:
            self._page.evaluate("""() => {
                const composer = document.querySelector("footer div[contenteditable='true']");
                if (composer) {
                    composer.innerText = '';
                    composer.textContent = '';
                }
            }""")
        except Exception:
            pass

        # 1. Attach the PDF file via WhatsApp Web Document uploader
        print(f"[WhatsAppBot] Attaching PDF document: {pdf_path}", flush=True)
        uploaded = False
        try:
            # Open attachment menu (+)
            attach_btn = self._page.locator("button[aria-label*='Attach' i], span[data-icon='plus'], span[data-icon='attach-menu-plus']").last
            attach_btn.click()
            time.sleep(0.6)

            # Find 'Document' item in attach menu
            doc_item = self._page.locator("li:has-text('Document'), div[role='button']:has-text('Document'), span:has-text('Document')").last
            with self._page.expect_file_chooser(timeout=10000) as fc_info:
                doc_item.click()
            file_chooser = fc_info.value
            file_chooser.set_files(pdf_path)
            uploaded = True
            print("[WhatsAppBot] Document file chooser attached PDF successfully.", flush=True)
        except Exception as upload_err:
            print(f"[WhatsAppBot] Document attach menu error: {upload_err}", flush=True)
            # Fallback to direct input setting if available
            for inp in self._page.query_selector_all("input[type='file']"):
                try:
                    inp.set_input_files(pdf_path)
                    uploaded = True
                    break
                except Exception:
                    pass

        if not uploaded:
            self._page.screenshot(path="scratch/no_input_found.png")
            return {"success": False, "error": "Could not locate WhatsApp Document attachment element."}

        # 2. Wait for Document Preview screen to render
        time.sleep(1.8)
        self._page.screenshot(path="scratch/step1_preview.png")

        # 3. Dispatch PDF attachment by focusing caption box and pressing Enter (WhatsApp Web native media submit)
        print("[WhatsAppBot] Dispatching PDF attachment on Document Preview...", flush=True)
        try:
            caption = self._page.locator("div[contenteditable='true']").first
            caption.click()
            time.sleep(0.3)
            self._page.keyboard.press("Enter")
            print("[WhatsAppBot] Pressed Enter on caption to submit document.", flush=True)
        except Exception as kbd_err:
            print(f"[WhatsAppBot] Caption Enter note: {kbd_err}", flush=True)

        # Secondary send button click
        try:
            send_btn = self._page.locator("span[data-icon='wds-ic-send-filled'], div[role='button'][aria-label^='Send']").last
            if send_btn.count() > 0:
                send_btn.click(timeout=1500)
        except Exception:
            pass

        # 4. Wait for document preview to close (guaranteeing PDF upload handoff)
        preview_closed = False
        for _ in range(25):
            time.sleep(0.5)
            is_open = self._page.evaluate("""() => {
                return !!document.querySelector("span[data-icon='wds-ic-send-filled'], div[role='button'][aria-label^='Send 1'], div[role='button'][aria-label^='Send 2']");
            }""")
            if not is_open:
                preview_closed = True
                print("[WhatsAppBot] Document preview closed! PDF attachment successfully dispatched.", flush=True)
                break

        if not preview_closed:
            self._page.screenshot(path="scratch/preview_stuck.png")
            return {
                "success": False,
                "error": "WhatsApp document preview could not be dispatched. Send button did not trigger."
            }

        time.sleep(1.5)

        # 5. Send the formatted deal contract message with live URL & rich OpenGraph card into the chat
        if message:
            try:
                time.sleep(1.0)
                # Focus chat composer
                composer = self._page.locator("footer div[contenteditable='true'], div[role='textbox'][aria-label*='Type a message']").last
                if composer.count() > 0:
                    composer.click()
                    time.sleep(0.4)

                    # Insert formatted message directly (preserves line breaks and emojis)
                    self._page.keyboard.insert_text(message)
                    print("[WhatsAppBot] Formatted text inserted into composer, waiting for link preview card...", flush=True)

                    # Give WhatsApp Web 2 seconds to parse URL and render Open Graph card
                    time.sleep(2.0)

                    # Submit message
                    self._page.keyboard.press("Enter")
                    time.sleep(0.5)

                    # Secondary JS click if needed
                    self._page.evaluate("""() => {
                        const icon = document.querySelector("footer span[data-icon='send'], footer span[data-icon='wds-ic-send-filled']");
                        if (icon) {
                            const btn = icon.closest("div[role='button'], button") || icon;
                            btn.click();
                        }
                    }""")
                    time.sleep(1.0)
                    print("[WhatsAppBot] Deal confirmation text and link preview dispatched to WhatsApp chat.", flush=True)
            except Exception as msg_err:
                print(f"[WhatsAppBot] Text send note: {msg_err}", flush=True)

        time.sleep(1.5)
        self._page.screenshot(path="scratch/after_pdf_sent.png")

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

    def execute_in_worker(self, fn, timeout: int = 30) -> Any:
        if self.status != "READY" or not self._page:
            return {"error": f"Bot not ready (status={self.status})"}
        done_event = threading.Event()
        job = {
            "action": "custom",
            "fn": fn,
            "done_event": done_event,
            "result": None
        }
        self._job_queue.put(job)
        if not done_event.wait(timeout=timeout):
            return {"error": "Custom execution timed out"}
        return job.get("result")

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

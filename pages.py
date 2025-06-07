import os
import json
import time
import random
import requests
from threading import Thread
from typing import List
import logging
from pathlib import Path
import socks
import socket
from stem import Signal
from stem.control import Controller

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('page_fetcher.log'),
        logging.StreamHandler()
    ]
)

# Number of threads
NUM_THREAD = 5

# User-Agent list
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]

class TorProxy:
    def __init__(self, tor_host='localhost', tor_port=9050, control_host='localhost', control_port=9051):
        self.tor_host = tor_host
        self.tor_port = tor_port
        self.control_host = control_host
        self.control_port = control_port
        self.socks_proxy = None
        self.controller = None
        self.setup_socks_proxy()

    def setup_socks_proxy(self):
        """Set up a SOCKS5 proxy connection with Tor."""
        socks.set_default_proxy(socks.SOCKS5, self.tor_host, self.tor_port)
        socket.socket = socks.socksocket  # Monkey patch socket module to route through Tor

    def get_proxy_dict(self):
        """Return proxy dict with Tor SOCKS5."""
        return {
            'http': f'socks5h://{self.tor_host}:{self.tor_port}',
            'https': f'socks5h://{self.tor_host}:{self.tor_port}',
        }

    def renew_tor_ip(self):
        """Request a new Tor circuit to get a new IP address."""
        try:
            with Controller.from_port(port=self.control_port) as controller:
                controller.authenticate()  # Authenticate with the Tor control port
                controller.signal(Signal.NEWNYM)  # Signal for a new Tor circuit (new IP)
                logging.info("🌐 Successfully got a new Tor IP!")
        except Exception as e:
            logging.error(f"🚨 Failed to request new Tor IP: {e}")

def simulate_wait(wait):
    end_time = time.time() + wait
    while time.time() < end_time:
        time.sleep(1)

class PageFetcher:
    def __init__(self, proxy: TorProxy):
        self.proxy = proxy
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS)
        })

    def fetch_page(self, page_num: int, output_dir="pages"):
        filename = f"page_{str(page_num)}.json"
        out_path = Path(output_dir) / filename

        if out_path.exists():
            logging.debug(f"Skipping existing file: {filename}")
            return True

        target_url = "https://karararama.yargitay.gov.tr/aramadetaylist"
        max_retries = 5  # Maximum attempts before giving up

        payload = {
            "data": {
                "arananKelime": "bir",
                "pageNumber": page_num,
                "pageSize": 100,
                "siralama": "1",
                "siralamaDirection": "desc",
            }
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Encoding": "gzip, deflate, br",
        }

        while True:
            try:
                # Use Tor's SOCKS5 proxy for the request
                proxy = self.proxy.get_proxy_dict()
                response = requests.post(
                    target_url,
                    json=payload,
                    headers=headers,
                    proxies=proxy,  # Use the Tor proxy here
                    timeout=15
                )

                if response.status_code == 200:
                    data = response.json()
                    with open(out_path, "w") as f:
                        json.dump(data["data"], f, indent=4)
                    logging.info(f"✅ Successfully fetched page {page_num}")
                    return  # Exit after success
                else:
                    logging.warning(f"⚠️ Page {page_num} failed (Status: {response.status_code}), retrying...")
                    simulate_wait(5)

            except Exception as e:
                logging.error(f"🚨 Error fetching page {page_num}: {e}, requesting new Tor IP...")
                self.proxy.renew_tor_ip()  # Request new IP after error
                simulate_wait(5)

def worker(pages: List[int], proxy: TorProxy):
    fetcher = PageFetcher(proxy)
    for page in pages:
        fetcher.fetch_page(page)

def fetch_pages():
    """Main function to manage multithreaded page fetching with Tor."""
    start_page = 5001  # Start from page 5001
    total_pages = 5000  # Adjust as needed
    tor_proxy = TorProxy()  # Initialize Tor Proxy
    threads = []

    for thread_id in range(NUM_THREAD):
        page_list = [start_page + thread_id + i * NUM_THREAD  for i in range(total_pages // NUM_THREAD)]
        t = Thread(target=worker, args=(page_list, tor_proxy), name=f"Thread-{thread_id+1}")
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    fetch_pages()

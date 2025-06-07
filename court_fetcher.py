import os
import re
import json
import html
import time
import logging
import threading
import requests
from pathlib import Path
from typing import List
from queue import Queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('court_fetcher.log'),
        logging.StreamHandler()
    ]
)

class Proxy:
    def __init__(self, ip, port, user, password):
        self.ip = ip
        self.port = port
        self.user = user
        self.password = password

    def get_proxy_dict(self):
        proxy_url = f"http://{self.user}:{self.password}@{self.ip}:{self.port}"
        return {'http': proxy_url, 'https': proxy_url}

class ProxyRotator:
    def __init__(self, proxies: List[Proxy]):
        self.proxies = proxies
        self.index = 0

    def get_current_proxy(self) -> Proxy:
        return self.proxies[self.index]

    def rotate(self) -> Proxy:
        self.index = (self.index + 1)
        if self.index == len(self.proxies):
            logging.warning(f"🚫 All proxies failed. Waiting 10 minutes...")
            simulate_wait(1800)
            self.index = 0
        return self.get_current_proxy()

class CourtCase:
    def __init__(self, id_, daire, esas_no, karar_no, karar_tarihi):
        self.id = id_
        self.daire = daire
        self.esas_no = esas_no
        self.karar_no = karar_no
        self.karar_tarihi = karar_tarihi

    def generate_filename(self):
        daire_clean = re.sub(r'[ .]', '', self.daire)
        esas_no_clean = self.esas_no.replace("/", "-")
        karar_no_clean = self.karar_no.replace("/", "-")
        karar_tarihi_clean = self.karar_tarihi.replace(".", "-")
        return f"{daire_clean}_E{esas_no_clean}_K{karar_no_clean}_{karar_tarihi_clean}.txt"

class CourtFetcher:
    def __init__(self, rotator: ProxyRotator):
        self.rotator = rotator
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })

    @staticmethod
    def clean_html(content: str) -> str:
        content = re.sub(r'<.*?>', '\n', content)
        content = html.unescape(content)
        content = re.sub(r'\n+', '\n', content)
        content = content.replace('\u00a0', '')
        content = re.sub(r'(?<!\d)([a-zçğıöşü])([A-ZÇĞİÖŞÜ])', r'\1\n\2', content)
        content = re.sub(r'"([^"]+)"([A-ZÇĞİÖŞÜ])', r'"\1"\n\2', content)
        content = re.sub(r'(K\.)\s*([A-ZÇĞİÖŞÜ]+)', r'\1\n\2', content)
        return content.strip()

    def fetch_case(self, court: CourtCase, output_dir="courts"):
        filename = court.generate_filename()
        out_path = Path(output_dir) / filename

        if out_path.exists():
            logging.debug(f"Skipping existing file: {filename}")
            return True

        url = f"https://karararama.yargitay.gov.tr/getDokuman?id={court.id}"

        while True:
            proxy = self.rotator.get_current_proxy()
            try:
                response = self.session.get(url, proxies=proxy.get_proxy_dict(), timeout=15)

                if response.status_code != 200:
                    raise Exception(f"Bad status {response.status_code}")

                data = response.json()

                if data.get("metadata", {}).get("FMTY", "").upper() != "SUCCESS":
                    raise Exception("FMTY not success")

                cleaned_content = self.clean_html(data["data"])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(cleaned_content, encoding='utf-8')
                logging.info(f"✅ Saved: {filename}")
                return True

            except Exception as e:
                logging.warning(f"Exception for {filename} using {proxy.ip}:{proxy.port}: {e}")
                self.rotator.rotate()


def simulate_wait(wait):
    end_time = time.time() + wait
    dummy = 0
    while time.time() < end_time:
        dummy += 0


def load_all_courts(input_dir="pages") -> List[CourtCase]:
    courts = []
    files = sorted(
        [f for f in os.listdir(input_dir) if f.startswith("page_") and f.endswith(".json")],
        key=lambda x: int(re.search(r'page_(\d+)\.json', x).group(1))
    )
    for file in files:
        with open(os.path.join(input_dir, file), encoding='utf-8') as f:
            try:
                data = json.load(f)
                for item in data.get("data", []):
                    try:
                        courts.append(CourtCase(
                            id_=str(item["id"]),
                            daire=item["daire"],
                            esas_no=item["esasNo"],
                            karar_no=item["kararNo"],
                            karar_tarihi=item["kararTarihi"]
                        ))
                    except (KeyError, TypeError):
                        continue
            except Exception as e:
                logging.error(f"❌ Failed to load {file}: {e}")
    return courts

def load_proxies(filename="proxies.txt") -> List[Proxy]:
    proxies = []
    with open(filename) as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 4:
                proxies.append(Proxy(*parts))
    return proxies

def worker(courts: List[CourtCase], proxies: List[Proxy]):
    rotator = ProxyRotator(proxies)
    fetcher = CourtFetcher(rotator)
    for court in courts:
        fetcher.fetch_case(court)

def get_existing_case_ids(output_dir="courts") -> set:
    """Çekilen Yargıtay kararlarının dosya adlarını kontrol ederek mevcut karar ID'lerini döndürür."""
    existing_filenames = set()

    # Mevcut karar dosyalarını kontrol et
    for file in os.listdir(output_dir):
        if file.endswith(".txt"):  # sadece .txt uzantılı dosyaları kontrol et
            existing_filenames.add(file)  # Dosya adını mevcut dosya listesine ekle

    return existing_filenames

def get_sorted_cases(input_dir="pages") -> List[CourtCase]:
    """Sayfa dosyalarını sıralı bir şekilde al ve tüm kararları döndür."""
    cases = []

    files = sorted(
        [f for f in os.listdir(input_dir) if f.startswith("page_") and f.endswith(".json")],
        key=lambda x: int(re.search(r'page_(\d+)\.json', x).group(1))
    )

    for file in files:
        with open(os.path.join(input_dir, file), encoding='utf-8') as f:
            try:
                data = json.load(f)
                for item in data.get("data", []):
                    try:
                        cases.append(CourtCase(
                            id_=str(item["id"]),
                            daire=item["daire"],
                            esas_no=item["esasNo"],
                            karar_no=item["kararNo"],
                            karar_tarihi=item["kararTarihi"]
                        ))
                    except (KeyError, TypeError):
                        continue
            except Exception as e:
                logging.error(f"❌ Failed to load {file}: {e}")
    
    # Sıralama, karar tarihine veya başka bir kritere göre yapılabilir
    cases.sort(key=lambda x: x.karar_tarihi)  # kararı tarihe göre sıralıyoruz
    return cases

def determine_new_cases(existing_filenames: set, input_dir="pages") -> List[CourtCase]:
    """Yeni Yargıtay kararlarını belirler, mevcut olanları dışarıda bırakır."""
    new_cases = []
    existing_cases = get_sorted_cases(input_dir)

    for new_case in existing_cases:
        # Yeni kararın dosya ismini oluştur
        filename = new_case.generate_filename()

        # Eğer bu dosya adı daha önce çekilmişse, geç
        if filename not in existing_filenames:
            new_cases.append(new_case)

    return new_cases

def main():
    from threading import Thread

    num_threads = 8
    all_proxies = load_proxies()

    if not all_proxies:
        logging.error("No proxies found.")
        return

    # Daha önce çekilen kararların dosya isimlerini al
    existing_filenames = get_existing_case_ids()

    # Yeni kararları belirle
    new_cases_all = determine_new_cases(existing_filenames)

    if not new_cases_all:
        logging.info("No new court cases found to process.")
        return

    file_per_iteration = 50000
    num_iter = len(new_cases_all) // file_per_iteration + 1
    total_cases = len(new_cases_all)
    logging.info(f"Total new cases: {total_cases}")
    for k in range(num_iter):
        new_cases = new_cases_all[k*file_per_iteration:(k+1)*file_per_iteration]
        chunk_size = len(new_cases) // num_threads
        proxy_chunks = [all_proxies[i::num_threads] for i in range(num_threads)]
        court_chunks = [new_cases[i:i + chunk_size] for i in range(0, len(new_cases), chunk_size)]

        threads = []
        for i in range(num_threads):
            proxy_list = proxy_chunks[i % len(proxy_chunks)]
            court_list = court_chunks[i % len(court_chunks)]
            t = Thread(target=worker, args=(court_list, proxy_list), name=f"Thread-{i+1}")
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        if k < num_iter - 1:  # Sonraki gruptan önce bekle
            logging.info(f"✅ Finished processing chunk. Waiting for 3 hours...")
            simulate_wait(7200)
    logging.info("✅ All new court cases processed successfully")


if __name__ == "__main__":
    main()

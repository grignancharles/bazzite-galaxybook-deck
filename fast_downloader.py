#!/usr/bin/env python3
import sys
import os
import ssl
import urllib.request
import threading
import time

URL = "https://download.bazzite.gg/bazzite-stable-amd64.iso"
DEST = "/Users/carlosgrinan/Downloads/bazzite-stable-amd64.iso"
PART_FILE = DEST + ".part"
NUM_WORKERS = 8

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get_content_length(url):
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return int(resp.headers.get('Content-Length', 0))

def download_range(url, start, end, part_path, progress, idx):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Range': f'bytes={start}-{end}'
    })
    with urllib.request.urlopen(req, context=ctx) as resp:
        with open(part_path, 'r+b') as f:
            f.seek(start)
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                f.write(chunk)
                progress[idx] += len(chunk)

def main():
    total_size = get_content_length(URL)
    print(f"Total size: {total_size} bytes ({total_size / (1024**3):.2f} GB)")

    if os.path.exists(DEST) and os.path.getsize(DEST) == total_size:
        print("File already downloaded and size matches!")
        return

    # Pre-allocate sparse/zeroed part file
    if not os.path.exists(PART_FILE) or os.path.getsize(PART_FILE) != total_size:
        print("Pre-allocating part file...")
        with open(PART_FILE, 'wb') as f:
            f.seek(total_size - 1)
            f.write(b'\0')

    chunk_size = total_size // NUM_WORKERS
    threads = []
    progress = [0] * NUM_WORKERS

    start_time = time.time()
    for i in range(NUM_WORKERS):
        start = i * chunk_size
        end = total_size - 1 if i == NUM_WORKERS - 1 else (i + 1) * chunk_size - 1
        t = threading.Thread(target=download_range, args=(URL, start, end, PART_FILE, progress, i))
        threads.append(t)
        t.start()

    print(f"Started {NUM_WORKERS} parallel download threads...")
    while any(t.is_alive() for t in threads):
        time.sleep(3)
        downloaded = sum(progress)
        elapsed = time.time() - start_time
        speed = downloaded / elapsed / (1024 * 1024) if elapsed > 0 else 0
        pct = (downloaded / total_size) * 100
        print(f"Progress: {downloaded / (1024**3):.2f} / {total_size / (1024**3):.2f} GB ({pct:.1f}%) - Speed: {speed:.2f} MB/s")

    for t in threads:
        t.join()

    os.rename(PART_FILE, DEST)
    print("Download completed successfully!")

if __name__ == "__main__":
    main()

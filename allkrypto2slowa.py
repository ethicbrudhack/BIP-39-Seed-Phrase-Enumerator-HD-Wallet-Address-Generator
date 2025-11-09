import os
import time
import sqlite3
import multiprocessing
import threading
import random
import hashlib
import base58
from typing import List, Dict
from mnemonic import Mnemonic
from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip49, Bip84, Bip86,
    Bip44Coins, Bip49Coins, Bip84Coins, Bip86Coins, Bip44Changes
)
import nacl.signing  # Solana

# --------------------------------------------------------
#               USTAWIENIA GLOBALNE
# --------------------------------------------------------

DB_FILE_INPUT  = "alladdresses.db"     # baza do sprawdzania HITÓW
DB_FILE_OUTPUT = "results.db"          # baza wynikowa (tu zapisujemy logi)
PROCESSES      = 3                     # liczba workerów
MAX_INDEX      = 5                     # ile adresów z każdej ścieżki
RESULTS_DIR    = "wyniki"              # folder wyników

WORD_LENGTHS  = (12, 15, 18, 24)
STRENGTH_MAP  = {12: 128, 15: 160, 18: 192, 24: 256}

# --------------------------------------------------------
#                 POMOCNICZE FUNKCJE
# --------------------------------------------------------

def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def init_results_db():
    """Tworzy bazę wyników z tabelą jeśli nie istnieje."""
    conn = sqlite3.connect(DB_FILE_OUTPUT)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        seed TEXT,
        coin TEXT,
        type TEXT,
        addr_index INTEGER,
        address TEXT,
        priv TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()


def privkey_to_wif(privkey_hex: str, compressed: bool = True) -> str:
    key_bytes = bytes.fromhex(privkey_hex)
    prefix = b"\x80" + key_bytes + (b"\x01" if compressed else b"")
    checksum = hashlib.sha256(hashlib.sha256(prefix).digest()).digest()[:4]
    return base58.b58encode(prefix + checksum).decode()


def address_exists_in_db(conn: sqlite3.Connection, address: str) -> bool:
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM addresses WHERE address = ?", (address,))
        return cur.fetchone() is not None
    except Exception as exc:
        print(f"[❌] Błąd zapytania do bazy: {exc}", flush=True)
        return False


# --------------------------------------------------------
#            GENEROWANIE ADRESÓW HD (WIELE CHAINÓW)
# --------------------------------------------------------

def generate_solana_addresses(seed_phrase: str, max_index: int) -> List[Dict]:
    out: List[Dict] = []
    try:
        seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
        base = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA).Purpose().Coin()
        for i in range(max_index):
            acc = base.Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
            priv_raw = acc.PrivateKey().Raw().ToBytes()
            pub_raw = nacl.signing.SigningKey(priv_raw).verify_key.encode()
            out.append({
                "coin": "SOL",
                "type": "SOLANA-BIP44",
                "index": i,
                "address": base58.b58encode(pub_raw).decode(),
                "priv": priv_raw.hex(),
                "seed": seed_phrase,
            })
    except Exception as exc:
        print(f"[WARN] Solana gen error: {exc}", flush=True)
    return out


def generate_hd_addresses(seed_phrase: str, max_index: int = MAX_INDEX) -> List[Dict]:
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    results: List[Dict] = []

    COIN_MAP = {
        "BTC": [
            ("BIP44", Bip44, Bip44Coins.BITCOIN),
            ("BIP49", Bip49, Bip49Coins.BITCOIN),
            ("BIP84", Bip84, Bip84Coins.BITCOIN),
            ("BIP86", Bip86, Bip86Coins.BITCOIN),
        ],
        "LTC": [
            ("BIP44", Bip44, Bip44Coins.LITECOIN),
            ("BIP49", Bip49, Bip49Coins.LITECOIN),
            ("BIP84", Bip84, Bip84Coins.LITECOIN),
        ],
        "ETH": [("BIP44", Bip44, Bip44Coins.ETHEREUM)],
        "DOGE": [("BIP44", Bip44, Bip44Coins.DOGECOIN)],
        "XRP": [("BIP44", Bip44, Bip44Coins.RIPPLE)],
        "DASH": [("BIP44", Bip44, Bip44Coins.DASH)],
        "BCH": [("BIP44", Bip44, Bip44Coins.BITCOIN_CASH)],
    }

    for coin, derivations in COIN_MAP.items():
        for name, cls, coin_enum in derivations:
            try:
                base = cls.FromSeed(seed_bytes, coin_enum).Purpose().Coin()
                for i in range(max_index):
                    node = base.Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
                    address = node.PublicKey().ToAddress().replace("bitcoincash:", "")
                    priv_hex = node.PrivateKey().Raw().ToHex()
                    results.append({
                        "coin": coin,
                        "type": f"{coin}-{name}",
                        "index": i,
                        "address": address,
                        "priv": privkey_to_wif(priv_hex)
                        if coin in {"BTC", "LTC", "DOGE", "BCH", "DASH"} else priv_hex,
                        "seed": seed_phrase,
                    })
            except Exception:
                continue

    results.extend(generate_solana_addresses(seed_phrase, max_index))
    return results


# --------------------------------------------------------
#              PRODUCER – GENERATOR SEEDÓW
# --------------------------------------------------------

def seed_producer(queue, seed_counter, lock_counter, start_base_word="abandon"):
    mnemo = Mnemonic("english")
    wordlist = mnemo.wordlist
    LENGTHS = [12, 15, 18, 24]

    try:
        start_idx = wordlist.index(start_base_word)
    except ValueError:
        start_idx = 0

    print(f"[🎲] Producer startuje od '{wordlist[start_idx]}'", flush=True)
    for offset in range(len(wordlist)):
        base_idx = (start_idx + offset) % len(wordlist)
        base_word = wordlist[base_idx]
        print(f"[➤] Przetwarzam base_word {base_idx+1}/{len(wordlist)}: '{base_word}'", flush=True)

        for L in LENGTHS:
            for last_word in wordlist:
                if last_word == base_word:
                    continue
                words = [base_word] * (L - 1) + [last_word]
                phrase = " ".join(words)
                if not mnemo.check(phrase):
                    continue
                queue.put(phrase)
                with lock_counter:
                    seed_counter.value += 1

    print("[🏁] Producer zakończył.", flush=True)


# --------------------------------------------------------
#          LOGGER PROCESS — ZAPIS DO BAZY SQLITE
# --------------------------------------------------------

def logger_process(log_queue):
    conn = sqlite3.connect(DB_FILE_OUTPUT, timeout=30)
    cur = conn.cursor()
    while True:
        data = log_queue.get()
        if data is None:
            break
        cur.executemany("""
            INSERT INTO results (worker_id, seed, coin, type, addr_index, address, priv)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data)
        conn.commit()
    conn.close()


# --------------------------------------------------------
#                WORKER – GENERATOR / INSERTER
# --------------------------------------------------------

def worker_process(queue, seed_counter, address_counter, lock_counter, pid, log_queue):
    print(f"[🔁] Worker {pid} startuje", flush=True)
    conn = sqlite3.connect(DB_FILE_INPUT)

    while True:
        seed = queue.get()
        if seed is None:
            print(f"[🏁] Worker {pid} kończy", flush=True)
            break

        try:
            addresses = generate_hd_addresses(seed, max_index=MAX_INDEX)
            records = []
            for e in addresses:
                records.append((
                    pid, e["seed"], e["coin"], e["type"], e["index"], e["address"], e["priv"]
                ))
            log_queue.put(records)

            with lock_counter:
                address_counter.value += len(addresses)
        except Exception as exc:
            print(f"[❌] Worker {pid} error: {exc}", flush=True)
    conn.close()


# --------------------------------------------------------
#                            MAIN
# --------------------------------------------------------

def main():
    ensure_results_dir()
    init_results_db()

    if not os.path.exists(DB_FILE_INPUT):
        print(f"[🚫] Brak bazy {DB_FILE_INPUT}")
        return

    mgr = multiprocessing.Manager()
    seed_cnt = mgr.Value('i', 0)
    addr_cnt = mgr.Value('i', 0)
    lock_cnt = mgr.Lock()
    log_queue = multiprocessing.Queue()
    q = multiprocessing.Queue(maxsize=PROCESSES * 2)

    logger = multiprocessing.Process(target=logger_process, args=(log_queue,))
    logger.start()

    prod = multiprocessing.Process(target=seed_producer, args=(q, seed_cnt, lock_cnt))
    prod.start()

    workers = [
        multiprocessing.Process(target=worker_process,
                                args=(q, seed_cnt, addr_cnt, lock_cnt, i, log_queue))
        for i in range(PROCESSES)
    ]
    for w in workers:
        w.start()

    def printer():
        while True:
            with lock_cnt:
                print(f"[📊] Seeds: {seed_cnt.value}, Addrs: {addr_cnt.value}", flush=True)
            time.sleep(2)
    threading.Thread(target=printer, daemon=True).start()

    try:
        prod.join()
    except KeyboardInterrupt:
        print("[🛑] SIGINT – kończę…", flush=True)

    for _ in workers:
        q.put(None)
    for w in workers:
        w.join()

    log_queue.put(None)
    logger.join()

    print(f"[🏁] Koniec: Seeds={seed_cnt.value}  Addrs={addr_cnt.value}")


if __name__ == "__main__":
    main()

🧠 BIP-39 Seed Phrase Enumerator & HD Wallet Address Generator

This Python script systematically generates deterministic BIP-39 seed phrases — even in brute-force mode where all possible word combinations can be explored (starting from as few as 2 words).
For each valid seed, it derives HD wallet addresses for multiple blockchains (Bitcoin, Ethereum, Solana, etc.) and stores results in an SQLite database.

It’s designed for research and educational use only, to explore how mnemonic entropy and checksum validation work in hierarchical deterministic wallets.

⚙️ What It Does

Generates possible seed phrases (mnemonics)

Based on the BIP-39 English wordlist (2048 words).

Can create all combinations like:

abandon abandon about ...
abandon abandon able ...


For each combination, it checks validity with the BIP-39 checksum.

Only valid mnemonic seeds are processed further.

Derives addresses for multiple coins using BIP standards:

Bitcoin (BIP-44 / BIP-49 / BIP-84 / BIP-86)

Litecoin, Dogecoin, Bitcoin Cash, Dash, Ethereum, Ripple, Solana

Writes all results (seed, derived addresses, private keys) into a local database (results.db).

Runs using multi-processing — multiple workers generate and derive seeds in parallel.

🧩 Supported Coins and Standards
Coin	Standards Used
BTC	BIP-44 / BIP-49 / BIP-84 / BIP-86
LTC	BIP-44 / BIP-49 / BIP-84
DOGE	BIP-44
DASH	BIP-44
BCH	BIP-44
ETH	BIP-44
XRP	BIP-44
SOL	BIP-44 (using NaCl signing)
🧰 Features

✅ Generates valid BIP-39 seeds (with checksum)
✅ Supports word lengths: 12, 15, 18, 24
✅ Allows controlled seed enumeration (2-word base, 3-word, etc.)
✅ Derives HD wallet addresses for multiple coins
✅ Saves results directly into SQLite database
✅ Uses multiple CPU cores for parallel scanning
✅ Built-in progress counters (Seeds, Addrs)
✅ Automatic creation of results folder and database

🧠 Generating All Possible Seeds

The function:

seed_producer(queue, seed_counter, lock_counter, start_base_word="abandon")


loops through the entire BIP-39 wordlist (2048 words) and for each:

Combines a base word (like "abandon") with others from the list.

Repeats patterns like [base_word]*11 + [last_word] (for 12-word seeds).

Validates each combination with mnemo.check(phrase) to keep only those passing checksum.

Example (for 2-word seeds):

You could modify the logic to generate only short seeds:

for w1 in wordlist:
    for w2 in wordlist:
        phrase = f"{w1} {w2}"
        if mnemo.check(phrase):
            queue.put(phrase)


That would enumerate every valid 2-word mnemonic (though only a handful exist, since BIP-39 normally defines 12+ words).

🛠️ How to Configure for More Words

To increase the number of words in generated seeds:

In the script, locate:

WORD_LENGTHS = (12, 15, 18, 24)


Replace or extend it, e.g.:

WORD_LENGTHS = (2, 3, 4, 12)


(Note: only certain combinations pass BIP-39 checksum validation.)

Optionally modify the generator loop:

for L in LENGTHS:
    ...


to explicitly limit or expand to your preferred number of words.

You can also change start_base_word in:

seed_producer(queue, seed_counter, lock_counter, start_base_word="abandon")


to begin generation from another word in the BIP-39 list.

📦 Dependencies

Install the required libraries:

pip install mnemonic bip-utils base58 pynacl

▶️ How to Run

Prepare your address database (optional):
The script checks derived addresses against alladdresses.db (input).
If you only want to generate and log results, you can leave this empty.

Run the script:

python3 main.py


Live stats are displayed:

[📊] Seeds: 105  Addrs: 2310
[🔁] Worker 2 startuje


Results will be written into results.db and logs into wyniki/.

🧩 Database Outputs
Column	Description
seed	Generated mnemonic phrase
coin	Blockchain type (BTC, ETH, etc.)
type	Derivation path (e.g. BTC-BIP84)
addr_index	Index (0–N)
address	Derived wallet address
priv	Private key in WIF or HEX
worker_id	Process ID that generated the record
created_at	Timestamp
⚠️ Ethical & Legal Notice

⚠️ This program is for research, testing, and educational use only.
It demonstrates how BIP-39 mnemonics, HD derivation, and wallet address generation work.

You may use it only for your own wallets or experimental datasets that you fully control.

Do not use it to search for, test, or scan other people’s addresses.
Doing so would be illegal, unethical, and against blockchain principles.

The author assumes no responsibility for misuse of this code.
It is meant purely to study Bitcoin and HD wallet internals.

BTC donation address: bc1q4nyq7kr4nwq6zw35pg0zl0k9jmdmtmadlfvqhr

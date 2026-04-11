#!/usr/bin/env python3

import requests
import socket
import concurrent.futures
import re

# ===== BANNER =====
def banner():
    print(r"""
██╗    ██╗██╗███╗   ██╗████████╗███████╗██████╗ 
██║    ██║██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
██║ █╗ ██║██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
██║███╗██║██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
╚███╔███╔╝██║██║ ╚████║   ██║   ███████╗██║  ██║
 ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

        ⚡ winter AKI - DomainHunter ⚡
        [ Recon | Scan | Hunt | Exploit ]
=================================================
""")

THREADS = 50
TIMEOUT = 6

OUTPUT_ACTIVE = "activedomain.txt"
OUTPUT_ALL = "all_subdomains.txt"

PORTS = [80, 443, 8080, 21, 22]
DIRS = ["admin", "login", "dashboard", "api", "test"]

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ===== SUBDOMAIN =====
def crtsh(domain):
    try:
        r = requests.get(f"https://crt.sh/?q=%25.{domain}&output=json", timeout=10)
        return set([x["name_value"] for x in r.json()])
    except:
        return set()


def hackertarget(domain):
    try:
        r = requests.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=10)
        return set([line.split(",")[0] for line in r.text.splitlines()])
    except:
        return set()


# ===== CLEAN =====
def clean(domain):
    domain = domain.strip().lower()
    domain = domain.replace("*.", "")
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/")[0]
    domain = domain.split(":")[0]

    if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
        return domain
    return None


# ===== DNS =====
def resolve(domain):
    try:
        socket.gethostbyname(domain)
        return domain
    except:
        return None


# ===== HTTP PROBE =====
def http_probe(domain):
    for scheme in ["https", "http"]:
        try:
            url = f"{scheme}://{domain}"
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            title = ""
            match = re.search(r"<title>(.*?)</title>", r.text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()

            return (url, r.status_code, title)
        except:
            continue
    return None


# ===== PORT SCAN =====
def scan_ports(domain):
    open_ports = []

    def scan(p):
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect((domain, p))
            return p
        except:
            return None

    with concurrent.futures.ThreadPoolExecutor(10) as ex:
        results = ex.map(scan, PORTS)
        for r in results:
            if r:
                open_ports.append(r)

    return open_ports


# ===== DIR FUZZ =====
def dir_fuzz(domain):
    found = []

    for scheme in ["https", "http"]:
        for d in DIRS:
            try:
                url = f"{scheme}://{domain}/{d}"
                r = requests.get(url, timeout=5)

                if r.status_code < 400:
                    found.append(url)
            except:
                continue

    return found


# ===== MAIN =====
def main():
    banner()  # 👈 Banner added here

    domain = input("Enter target domain: ").strip()

    print("\n[+] Collecting subdomains...\n")

    subs = set()
    subs |= crtsh(domain)
    subs |= hackertarget(domain)

    print(f"[+] Raw found: {len(subs)}")

    clean_subs = set()
    for s in subs:
        c = clean(s)
        if c and c.endswith(domain):
            clean_subs.add(c)

    print(f"[+] Cleaned: {len(clean_subs)}")

    with open(OUTPUT_ALL, "w") as f:
        for s in clean_subs:
            f.write(s + "\n")

    print("\n[+] Resolving...")
    live = []

    with concurrent.futures.ThreadPoolExecutor(THREADS) as ex:
        for r in ex.map(resolve, clean_subs):
            if r:
                live.append(r)

    print(f"[+] Live domains: {len(live)}")

    print("\n[+] HTTP probing...\n")
    active = []

    with concurrent.futures.ThreadPoolExecutor(THREADS) as ex:
        for result in ex.map(http_probe, live):
            if result:
                url, code, title = result
                active.append(url)
                print(f"[{code}] {url} | {title}")

    print("\n[+] Port scanning...\n")
    for d in active:
        host = d.replace("http://", "").replace("https://", "")
        ports = scan_ports(host)

        if ports:
            print(f"{d} -> Ports: {ports}")

    print("\n[+] Directory fuzzing...\n")
    for d in active:
        host = d.replace("http://", "").replace("https://", "")
        found = dir_fuzz(host)

        for f in found:
            print("[FOUND]", f)

    active = sorted(set(active))

    with open(OUTPUT_ACTIVE, "w") as f:
        for d in active:
            f.write(d + "\n")

    print("\n======================")
    print(f"[+] Active domains: {len(active)}")
    print(f"[+] Saved: {OUTPUT_ACTIVE}")
    print("======================\n")


if __name__ == "__main__":
    main()

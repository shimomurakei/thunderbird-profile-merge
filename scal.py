#!/usr/bin/env python3
# Scalanie poczty z profilu ZRODLO do profilu CEL. Thunderbird ZAMKNIĘTY.
#   python3 scal.py ZRODLO CEL            -> plan, nic nie zmienia
#   python3 scal.py ZRODLO CEL wykonaj    -> zmienia tylko CEL
# ZRODLO tylko do odczytu: konta lokalne ORAZ kopie offline skrzynek IMAP (ImapMail).
# W CEL:
#   1. usuwa duplikaty w obrębie folderu (ten sam Message-ID; zostaje pierwsza kopia)
#   2. dopisuje wiadomości ze ZRODLA, których nie ma NIGDZIE w CEL
#      (klucz: Message-ID + rodzaj folderu: wysłane / robocze / pozostałe)
#      - konto lokalne -> konto o tej samej nazwie, ta sama ścieżka folderu
#      - skrzynka IMAP "X" -> konto "X - lokalne": Odebrane / Wysłane / Wersje robocze (MailKeep posortuje)
#      - brak takiego konta w CEL -> Foldery lokalne / <nazwa konta> / ...
# Kosze pomijane (nic nie wraca z kosza); wiadomości pobrane częściowo pomijane.
# Indeksy (.msf) zmienionych folderów -> .msf.przed-scaleniem; Thunderbird zbuduje nowe przy otwarciu.
# Adresy w wydruku zamaskowane.
import os, re, sys, hashlib, mailbox
from email.parser import BytesHeaderParser

if len(sys.argv) < 3:
    sys.exit("użycie: python3 scal.py ZRODLO CEL [wykonaj]")
zrodlo, cel = (os.path.abspath(os.path.expanduser(x)) for x in sys.argv[1:3])
wykonaj = len(sys.argv) > 3 and sys.argv[3] == "wykonaj"
if zrodlo == cel:
    sys.exit("ZRODLO i CEL to ten sam profil")

def w_uzyciu(prof):
    lk = os.path.join(prof, "lock")
    if not os.path.islink(lk):
        return False
    pid = os.readlink(lk).rsplit("+", 1)[-1]
    try:
        return "thunderbird" in open(f"/proc/{pid}/comm").read()
    except OSError:
        return False
for p in (zrodlo, cel):
    if w_uzyciu(p):
        sys.exit(f"Profil w użyciu: zamknij Thunderbirda ({p}). Nic nie zmieniono.")

def maska(t):
    return re.sub(r"([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)", r"\1***@\2", t)

rx = re.compile(r'^user_pref\("([^"]+)",\s*"(.*)"\);')
def konta(prof):
    """nazwa -> (typ, katalog); typ: none (lokalne) / imap"""
    p = {m.group(1): m.group(2) for l in open(os.path.join(prof, "prefs.js"), encoding="utf-8") if (m := rx.match(l.strip()))}
    wynik = {}
    for k, v in p.items():
        m = re.match(r"mail\.server\.(server\d+)\.type$", k)
        if not m or v not in ("none", "imap"):
            continue
        s = m.group(1)
        rel = p.get(f"mail.server.{s}.directory-rel", "")
        kat = os.path.join(prof, rel[7:]) if rel.startswith("[ProfD]") else p.get(f"mail.server.{s}.directory", "")
        if not kat or not os.path.isdir(kat):
            continue
        nazwa = p.get(f"mail.server.{s}.name", "") or ("Local Folders" if v == "none" else s)
        if kat.rstrip("/").endswith("Local Folders"):
            nazwa = "Local Folders"
        wynik[nazwa] = (v, kat)
    return wynik

def czy_mbox(pth):
    if os.path.basename(pth).endswith((".msf", ".dat", ".json", ".html", ".przed-scaleniem")) or not os.path.isfile(pth):
        return False
    if os.path.getsize(pth) == 0:
        return True
    with open(pth, "rb") as h:
        return h.read(5) == b"From "

KOSZ = {"trash", "kosz", "deleted", "deleted items", "deleted messages", "bin", "papierkorb"}
WYSLANE = {"sent", "wysłane", "sent mail", "sent items", "sent messages", "elementy wysłane"}
ROBOCZE = {"drafts", "wersje robocze", "templates", "szablony", "kopie robocze"}
def czesci(rel):
    return [c[:-4] if c.endswith(".sbd") else c for c in rel.lower().split("/")]

def foldery(kat):
    for r, ds, fs in os.walk(kat):
        for f in fs:
            pth = os.path.join(r, f)
            rel = os.path.relpath(pth, kat)
            if KOSZ & set(czesci(rel)) or not czy_mbox(pth):
                continue
            yield rel, pth

def rodzaj(rel):
    c = set(czesci(rel))
    return "s" if c & WYSLANE else "d" if c & ROBOCZE else "o"

parser = BytesHeaderParser()
def naglowki(bajty):
    h = parser.parsebytes(bajty)
    try:
        czesciowa = int(h.get("X-Mozilla-Status", "0"), 16) & 0x0400
    except ValueError:
        czesciowa = 0
    mid = (h.get("Message-ID") or "").strip()
    if not mid:
        mid = "bez-id:" + hashlib.sha1(f"{h.get('Date')}|{h.get('From')}|{h.get('Subject')}".encode("utf-8", "replace")).hexdigest()
    return mid, bool(czesciowa)

def czytaj(pth):
    mb = mailbox.mbox(pth, create=False)
    return mb, [(k, *naglowki(mb.get_bytes(k))) for k in mb.iterkeys()]

def odloz_msf(pth):
    msf = pth + ".msf"
    if os.path.exists(msf):
        os.replace(msf, msf + ".przed-scaleniem")

kz, kc = konta(zrodlo), konta(cel)
lokc = {n: kat for n, (t, kat) in kc.items() if t == "none"}
if "Local Folders" not in lokc:
    sys.exit("CEL nie ma Folderów lokalnych")
razem = {"duplikaty": 0, "dopisane": 0, "nowe_foldery": 0, "foldery_zmienione": 0, "czesciowe": 0}
print(f"{'WYKONANIE' if wykonaj else 'PLAN (nic nie zmienia)'}\n")

# 1. duplikaty w CEL i spis wszystkiego, co jest w CEL
obecne = set()
for nazwa, katc in sorted(lokc.items()):
    dupl = 0
    for rel, pth in sorted(foldery(katc)):
        try:
            mb, lista = czytaj(pth)
        except Exception as e:
            print(f"  BŁĄD odczytu CEL {maska(nazwa)} {maska(rel)}: {e}")
            continue
        widziane, zbedne = set(), []
        for k, mid, _ in lista:
            if mid in widziane:
                zbedne.append(k)
            widziane.add(mid)
            obecne.add((mid, rodzaj(rel)))
        if zbedne:
            dupl += len(zbedne)
            if wykonaj:
                mb.lock()
                for k in zbedne:
                    mb.remove(k)
                mb.flush()
                mb.unlock()
                odloz_msf(pth)
                razem["foldery_zmienione"] += 1
        mb.close()
    if dupl:
        print(f"CEL {maska(nazwa)}: duplikaty {dupl}")
    razem["duplikaty"] += dupl

# 2. brakujące ze ZRODLA
def gdzie(nazwa, typ, rel):
    """katalog konta w CEL i ścieżka folderu"""
    if typ == "none":
        if nazwa in lokc:
            return lokc[nazwa], rel
        return lokc["Local Folders"], f"{nazwa}.sbd/{rel}"
    folder = {"s": "Sent", "d": "Drafts", "o": "Inbox"}[rodzaj(rel)]
    if f"{nazwa} - lokalne" in lokc:
        return lokc[f"{nazwa} - lokalne"], folder
    return lokc["Local Folders"], f"{nazwa}.sbd/{folder}"

for nazwa, (typ, katz) in sorted(kz.items()):
    dopisz = 0
    for rel, pth in sorted(foldery(katz)):
        try:
            mbz, lista = czytaj(pth)
        except Exception as e:
            print(f"  BŁĄD odczytu ZRODLO {maska(nazwa)} {maska(rel)}: {e}")
            continue
        r = rodzaj(rel)
        brak, widziane = [], set()
        for k, mid, czesciowa in lista:
            if czesciowa:
                razem["czesciowe"] += 1
                continue
            if (mid, r) in obecne or mid in widziane:
                continue
            widziane.add(mid)
            brak.append((k, mid))
        if brak:
            katc, relc = gdzie(nazwa, typ, rel)
            docel = os.path.join(katc, relc)
            nowy = not os.path.exists(docel)
            print(f"  {'IMAP ' if typ == 'imap' else ''}{maska(nazwa)} {maska(rel)} -> {maska(os.path.basename(katc))}/{maska(relc)}: "
                  f"dopisać {len(brak)}{' (nowy folder)' if nowy else ''}")
            dopisz += len(brak)
            if nowy:
                razem["nowe_foldery"] += 1
            if wykonaj:
                cz = relc.split("/")
                for i in range(1, len(cz)):
                    nad = os.path.join(katc, *cz[:i])
                    if nad.endswith(".sbd"):
                        os.makedirs(nad, exist_ok=True)
                        if not os.path.exists(nad[:-4]):
                            open(nad[:-4], "wb").close()
                mbc = mailbox.mbox(docel, create=True)
                mbc.lock()
                for k, _ in brak:
                    mbc.add(mbz.get_message(k))
                mbc.flush()
                mbc.unlock()
                mbc.close()
                odloz_msf(docel)
                razem["foldery_zmienione"] += 1
            for _, mid in brak:
                obecne.add((mid, r))
        mbz.close()
    if dopisz:
        print(f"{'IMAP ' if typ == 'imap' else ''}{maska(nazwa)}: do dopisania {dopisz}\n")
    razem["dopisane"] += dopisz

print(f"\nRAZEM: duplikaty {razem['duplikaty']}, do dopisania {razem['dopisane']}, nowe foldery {razem['nowe_foldery']}"
      + (f", zmienione foldery {razem['foldery_zmienione']}" if wykonaj else "")
      + (f" (pominięte pobrane częściowo: {razem['czesciowe']})" if razem["czesciowe"] else ""))

# thunderbird-profile-merge

Merges the mail from several Thunderbird profiles into one profile and removes duplicate messages. The result is a single profile that holds every message from all of them.

[Polski opis niżej](#polski)

## Background

The script was written to consolidate mail from several Thunderbird profiles into one:

- old Thunderbird Portable profiles copied over from Windows;
- the current profile on Linux Mint;
- test copies of that profile.

All the work was done on Linux Mint. A Windows profile folder copied as-is works as a source: the script reads only `prefs.js` and the mail folders (mbox files) and does not depend on the operating system that wrote them.

## What it does

`scal.py SOURCE TARGET` reads the source profile and changes only the target profile:

1. **Duplicates in the target.** Removes repeated messages inside a folder (the same `Message-ID`); the first copy stays.
2. **Missing messages from the source.** Copies every source message that is not present **anywhere** in the target profile. A message is identified by its `Message-ID` and folder kind (sent, drafts, other), so a message filed differently in the two profiles is not copied twice. Placement:
   - local account → the account with the same name, same folder path;
   - offline copy of an IMAP mailbox `X` (`ImapMail`) → local account `X - lokalne`: Inbox, Sent or Drafts;
   - no matching account in the target → `Local Folders/<account name>/…`.
3. **Skipped:** trash folders (nothing comes back from the trash) and partially downloaded messages; the latter are counted in the summary.
4. **Indexes.** Each changed folder's `.msf` index is renamed to `.msf.przed-scaleniem`; Thunderbird builds a new one when the folder is opened.

The output masks e-mail addresses (`a***@domain`).

## Usage

Thunderbird must be **closed**. The script refuses to run on a profile that is in use.

```
python3 scal.py SOURCE TARGET            # plan: shows what would change, changes nothing
python3 scal.py SOURCE TARGET wykonaj    # carries out the plan on TARGET
```

The procedure we used to merge all profiles into one (`TARGET` = the profile that stays):

```
# 1. plan for every other profile
for p in ~/.thunderbird/*/; do [ "$p" = "$TARGET/" ] || [ ! -f "$p/prefs.js" ] && continue; echo "== $p"; python3 scal.py "$p" "$TARGET" | tail -1; done

# 2. merge
for p in ~/.thunderbird/*/; do [ "$p" = "$TARGET/" ] || [ ! -f "$p/prefs.js" ] && continue; echo "== $p"; python3 scal.py "$p" "$TARGET" wykonaj; done > merge-result.txt

# 3. check: every profile must show "do dopisania 0"
for p in ~/.thunderbird/*/; do [ "$p" = "$TARGET/" ] || [ ! -f "$p/prefs.js" ] && continue; echo "== $p"; python3 scal.py "$p" "$TARGET" | tail -1; done
```

If step 3 shows 0 for every profile, the target profile contains all the mail. Only then remove the other profiles and point `profiles.ini` at the one that stays.

## Safety

- `wykonaj` removes duplicates from the target permanently. Run it on a copy of the target profile first (`cp -a`), then compare message counts before and after.
- The source profile is never modified.
- Requires Python 3.8+ from the standard library only. No network access.

## Support

If this project saves you time, you can support its development:

- **GitHub Sponsors:** https://github.com/sponsors/shimomurakei
- **Monero (XMR):**

```
847ncPxR5DhGBtrafVyePuDiht33aiYztGWbGAn36BG11Kdnju4UnxVXbsrnbaAYRwMswdcjjbioPF9ipt3oVXmXS1v69w1
```

<img src="docs/monero-qr.png" alt="Monero QR code" width="180">

## License

thunderbird-profile-merge — Copyright (C) 2026 .kei
https://github.com/shimomurakei/thunderbird-profile-merge

Licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later); full text in `LICENSE`.

Additional term under GPLv3 section 7(b): any modified or redistributed version must preserve this author attribution, including the link above, in its README.

Request (not a license condition): if you build on this project, please let me know by opening an issue in the repository above, so we can cooperate.

---

## Polski

Scala pocztę z kilku profili Thunderbirda w jeden i usuwa zdublowane wiadomości. Wynikiem jest jeden profil z całą pocztą.

Skrypt powstał przy scalaniu poczty z kilku profili: starych profili Thunderbird Portable przeniesionych z Windowsa, bieżącego profilu na Linux Mint i jego kopii testowych. Całość robiona na Linux Mint. Profil z Windowsa skopiowany w całości działa jako źródło, bo skrypt czyta tylko `prefs.js` i pliki folderów (mbox).

`scal.py ZRODLO CEL` czyta profil źródłowy i zmienia tylko profil docelowy:

1. usuwa duplikaty w obrębie folderu (ten sam `Message-ID`);
2. dopisuje wiadomości ze źródła, których nie ma **nigdzie** w profilu docelowym (klucz: `Message-ID` i rodzaj folderu), także z kopii offline skrzynek IMAP;
3. pomija kosze i wiadomości pobrane częściowo;
4. indeksy zmienionych folderów zmienia na `.msf.przed-scaleniem`, a Thunderbird buduje nowe.

Thunderbird musi być zamknięty. Bez `wykonaj` skrypt tylko pokazuje plan. Po scaleniu kontrola z każdego profilu ma dać „do dopisania 0”; dopiero wtedy usuwa się pozostałe profile.

**`wykonaj` nieodwracalnie usuwa duplikaty z profilu docelowego.** Najpierw sprawdź na kopii profilu.

**Licencja:** GPL-3.0-or-later (tekst w `LICENSE`). Każda przeróbka musi zachować informację o autorze z linkiem https://github.com/shimomurakei/thunderbird-profile-merge. Prośba, nie warunek licencji: jeśli budujesz na tym projekcie, daj znać w zgłoszeniu (issue) w repozytorium, to możemy współpracować.

**Wsparcie:** GitHub Sponsors https://github.com/sponsors/shimomurakei albo Monero (XMR): `847ncPxR5DhGBtrafVyePuDiht33aiYztGWbGAn36BG11Kdnju4UnxVXbsrnbaAYRwMswdcjjbioPF9ipt3oVXmXS1v69w1` (kod QR w sekcji Support).

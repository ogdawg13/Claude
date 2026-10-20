# Bilbevakning

Läser aviseringsmejl från Blocket, Carla och Bytbil (dina sparade sökningar), plockar ut pris/år/miltal,
bygger en prishistorik och skickar mobilnotis (ntfy) + mejl när en annons matchar ditt filter.
Annonser som ligger minst `threshold` under medianen för samma modell och liknande årsmodell får rubriken **BRA PRIS**.

## Kom igång
1. Sätt upp sparade sökningar med **direktavisering** hos Blocket, Carla och Bytbil, skickade till din Gmail.
2. Gmail: slå på tvåstegsverifiering och skapa ett *applösenord* (Google-konto → Säkerhet → Applösenord). IMAP ska vara på.
3. Installera appen **ntfy** på mobilen och prenumerera på ett hemligt ämnesnamn.
4. `cp config.example.toml config.toml` och fyll i.
5. Kör (Python 3.11+, inget att installera):
   ```
   export BILBEVAKNING_MAIL_PASSWORD="applösenordet"
   python3 -m bilbevakning.main config.toml          # körs hela tiden
   python3 -m bilbevakning.main config.toml --once   # en omgång, för test
   ```
6. Tester: `python3 -m unittest discover -s tests`

## Viktigt
- Mejlparsern är skriven utan att ha sett riktiga aviseringsmejl. Skicka några (eller klistra in texten, ta bort personuppgifter) så finslipar vi den.
- Prisbedömningen blir användbar först när databasen har några annonser per modell (`min_samples`).
- Datorn/servern måste vara på för att tjänsten ska köra.

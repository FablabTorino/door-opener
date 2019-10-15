# Door opener
Fablab door opener made with a Wemos, RFID reader and a Telegram bot

@karonth via Telegram:
> l'idea era di usare il gruppo telegram come accesso temporaneo, dove si aggiungono e tolgono quelli che devono accedere al Fablab solo per progetti limitati e non sono in possesso delle credenziali ufficiali RFID

> aggiungendo il lettore rfid si può espandere la funzionalità del bot con un sistema di whitelist, dove alla lettura di un ID sconosciuto viene chiesto agli admin di concedere l'accesso

> una volta messo in piedi il server con il database degli utenti l'ESP può fare una richiesta per ottenere la cache aggiornata degli RFID con accesso e il codice associato per l'orario di apertura

> con anche un RTC diventerebbe indipendente dalla rete internet per periodi limitati

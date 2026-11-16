# tv-iptv-it

Playlist IPTV italiane per Android TV (testate con [TVirl](https://github.com/stari4ek/tvirl)), controllate e rigenerate ogni giorno.

| File | Contenuto | URL |
|---|---|---|
| `playlist.m3u` | ~42 canali nazionali (Rai, Mediaset, La7, Discovery...) | `https://raw.githubusercontent.com/clemeg/tv-iptv-it/main/playlist.m3u` |
| `playlist-full.m3u` | i nazionali + canali regionali, tematici e radio che passano il test | `https://raw.githubusercontent.com/clemeg/tv-iptv-it/main/playlist-full.m3u` |

Guida programmi (EPG), dichiarata nei file via `x-tvg-url`:
`https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz`

## Come funziona
`build_playlist.py` parte da due elenchi pubblici ([Tundrak/IPTV-Italia](https://github.com/Tundrak/IPTV-Italia), [Free-TV/IPTV](https://github.com/Free-TV/IPTV)), controlla ogni flusso (deve restituire un manifest HLS/DASH valido) e per ogni canale tiene il primo che funziona.
I link Rai vengono riscritti sul relinker ufficiale in `https`; gli id `tvg-id` sono allineati all'EPG.

`update.sh` rigenera tutto e pubblica solo se il risultato è sensato (soglie minime: se il Mac è offline non viene pubblicato nulla).

## Note
- I flussi sono quelli pubblici delle emittenti e in gran parte validi solo dall'Italia: **il controllo va eseguito da un IP italiano**, non da GitHub Actions.
- Nessuna garanzia: i flussi cambiano o spariscono senza preavviso.

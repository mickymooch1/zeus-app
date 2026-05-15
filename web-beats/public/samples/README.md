# Accent Voice Preview Samples

Short MP3 clips (5-10 seconds) used by the accent preview button on the Songs page.
Each file should be a spoken phrase in the target accent, e.g. "Welcome to Zeus Beats".

## Files needed

| Filename                  | Accent                  |
|---------------------------|-------------------------|
| british.mp3               | British                 |
| american_southern.mp3     | American (Southern)     |
| irish.mp3                 | Irish                   |
| scottish.mp3              | Scottish                |
| australian.mp3            | Australian              |
| caribbean.mp3             | Caribbean               |
| french.mp3                | French                  |
| spanish.mp3               | Spanish                 |
| american_soul.mp3         | American Soul           |
| jamaican.mp3              | Jamaican                |
| dnb_mc.mp3                | D&B MC                  |
| uk_rave_mc.mp3            | UK Rave MC              |
| british_mc_grime.mp3      | British MC Grime        |
| jazz_vocal.mp3            | Jazz Vocal              |
| american_hiphop.mp3       | American Hip-Hop        |
| kpop.mp3                  | K-Pop                   |
| west_african.mp3          | West African            |
| south_african.mp3         | South African           |
| american_phonk.mp3        | American Phonk          |
| new_jersey.mp3            | New Jersey / Newark     |
| british_african.mp3       | British African         |
| jamaican_rasta.mp3        | Jamaican Rasta          |

## Usage

The play button appears next to the accent selector on the Songs page.
Clicking it plays `/samples/<slug>.mp3` via the browser Audio API.
If the file is missing the button silently does nothing.

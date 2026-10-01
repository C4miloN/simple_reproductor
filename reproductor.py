#!/usr/bin/env python3
import os
import sys
import random
import json
import queue
import re
import threading
import time
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import vlc
except Exception:
    vlc = None

def get_app_dir():
    """Carpeta donde viven config.json y radio_favoritas.json.

    Al ejecutarlo con PyInstaller, __file__ apunta a la carpeta temporal
    _MEIPASS, que se borra al salir. Hay que usar la carpeta del .exe para
    que la configuracion persista entre ejecuciones.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_app_dir(), "config.json")

def load_config():
    config = {
        "volume": 80,
        "shuffle": True,
        "pinned": True,
        "x": 100,
        "y": 100,
        "width": 650,
        "height": 40,
        "bg_color": "#000000",
        "btn_color": "#333333",
        "font_color": "#FFFFFF",
        "playlist": "",
        "song_index": 0,
        "last_source": "local",
        "show_titlebar": True,
        "opacity": 100,
        "resizable": True
    }
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            # utf-8-sig tolera que el fichero tenga BOM (guardado por el Bloc de
            # notas, PowerShell, etc.) y tambien funciona sin el.
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config.update(json.load(f))
        except Exception as e:
            print(f"Failed to load config: {e}")
    return config

def save_config(config):
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Failed to save config: {e}")

def get_music_root():
    user_home = os.path.expanduser("~")
    return os.path.join(user_home, "Music")

def scan_playlists(root):
    playlists = {}
    if not os.path.isdir(root):
        return playlists
    
    for entry in sorted(os.listdir(root)):
        entry_path = os.path.join(root, entry)
        if os.path.isdir(entry_path):
            files = []
            for f in os.listdir(entry_path):
                if f.lower().endswith((".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg")):
                    files.append(os.path.join(entry_path, f))
            if files:
                playlists[entry] = sorted(files, key=lambda x: x.lower())
    
    for entry in sorted(os.listdir(root)):
        entry_path = os.path.join(root, entry)
        if os.path.isdir(entry_path):
            for sub_entry in sorted(os.listdir(entry_path)):
                sub_path = os.path.join(entry_path, sub_entry)
                if os.path.isdir(sub_path):
                    files = []
                    for f in os.listdir(sub_path):
                        if f.lower().endswith((".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg")):
                            files.append(os.path.join(sub_path, f))
                    if files:
                        key = f"{entry}/{sub_entry}"
                        playlists[key] = sorted(files, key=lambda x: x.lower())
    
    return playlists

# ---------------------------------------------------------------------------
# RADIO ONLINE
# ---------------------------------------------------------------------------

RADIO_API_BASES = (
    "https://de1.api.radio-browser.info",
    "https://de2.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
    "https://all.api.radio-browser.info",
)
RADIO_USER_AGENT = "ReproductorOpen/1.0 (minimo reproductor)"
RADIO_TIMEOUT = 15
RADIO_SEARCH_LIMIT = 80
RADIO_ONLINE_LABEL = "[online]"

# Catalogo curado de emisoras verificadas (nombre, url, genero, pais)
CURATED_RADIO = [
    {"name": "Café del Mar CALM", "url": "https://streamer.radio.co/sb748f24ad/listen", "genre": "Ambient", "country": "España"},
    {"name": "Laut.FM Shoegaze", "url": "https://shoegaze.stream.laut.fm/shoegaze", "genre": "Ambient", "country": "Alemania"},
    {"name": "RADIO DIMENSIONE RELAX", "url": "https://az1.mediacp.eu/listen/radiodimensionerelax/radio.mp3", "genre": "Ambient", "country": "Italia"},
    {"name": "SomaFM Groove Salad (128k MP3)", "url": "https://ice6.somafm.com/groovesalad-128-mp3", "genre": "Ambient", "country": "EE.UU."},
    {"name": "SomaFM Secret Agent (128k MP3)", "url": "https://ice2.somafm.com/secretagent-128-mp3", "genre": "Ambient", "country": "EE.UU."},
    {"name": "Спокойное радио", "url": "https://listen9.myradio24.com/6262", "genre": "Ambient", "country": "Rusia"},
    {"name": "Colombia Crossover", "url": "https://radio35.virtualtronics.com/proxy/colombiacrossover?mp=/;", "genre": "Bachata", "country": "Colombia"},
    {"name": "Deluxe Radio - Flamenco Flow", "url": "https://stream.zeno.fm/z9fm6v2d6ehvv", "genre": "Bachata", "country": "España"},
    {"name": "Fiebre Latina Radio 96.6 FM", "url": "https://eu1.lhdserver.es:9035/stream", "genre": "Bachata", "country": "España"},
    {"name": "La 961 - Suprema estacion", "url": "https://dattavolt.com/8150/stream", "genre": "Bachata", "country": "Ecuador"},
    {"name": "La Bomba Radio Asturias", "url": "https://stm2.emiteonline.com:9014/labomba", "genre": "Bachata", "country": "España"},
    {"name": "MikiRadio", "url": "https://app.aloncast.com/api/stream/mikiradio-052055", "genre": "Bachata", "country": "Argentina"},
    {"name": "Mix (Medellín) 89.9 FM", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/MIX_MEDELLINAAC.aac", "genre": "Bachata", "country": "Colombia"},
    {"name": "Mix Bogota", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/MIX_BOGOTAAAC.aac", "genre": "Bachata", "country": "Colombia"},
    {"name": "Radio Alegria", "url": "https://rr5100.globalhost1.com:8156/stream", "genre": "Bachata", "country": "Ecuador"},
    {"name": "Radio Ultimito Mix", "url": "https://usa4.fastcast4u.com/proxy/rwrw1?mp=/1", "genre": "Bachata", "country": "Ecuador"},
    {"name": "Rosate con bachata", "url": "https://stream-204.surfernetwork.com/uagzy1yc5uhvv?zt=eyJhbGciOiJIUzI1NiJ9.eyJzdHJlYW0iOiJ1YWd6eTF5YzV1aHZ2IiwiaG9zdCI6InN0cmVhbS0yMDQuc3VyZmVybmV0d29yay5jb20iLCJ0bSI6ZmFsc2UsInJ0dGwiOjUsImp0aSI6InQxS2ZjeUJaUzFpaDZiOUdzdDZUWkEiLCJpYXQiOjE3OTAzNzAzMTIsImV4cCI6MTc5MDM3MDM3Mn0.-yBV7EHBkrBKECNPMELPoT43Bfh5aDBH4JB--lFT9HA", "genre": "Bachata", "country": "Ecuador"},
    {"name": "Tropical 100 Mix", "url": "https://stream-107.zeno.fm/esgo1lafgtstv?zs=o1G7UIERS3Gdtn2B7Jdt7Q", "genre": "Bachata", "country": "Rep. Dominicana"},
    {"name": "181.FM - True Blues", "url": "https://listen.181fm.com/181-blues_128k.mp3", "genre": "Blues", "country": "EE.UU."},
    {"name": "A MISSISSIPPI BLUES", "url": "https://cast1.torontocast.com:4450/;?type=http&nocache=1745625391", "genre": "Blues", "country": "Canadá"},
    {"name": "BMFR - Blues Music Fan Radio", "url": "https://orbit.citrus3.com:8052/stream", "genre": "Blues", "country": "EE.UU."},
    {"name": "TrustFM", "url": "https://trust-canberra-b3c69c68.radiocult.fm/stream", "genre": "Blues", "country": "Australia"},
    {"name": "WKNC 88.1 HD1", "url": "https://streaming.live365.com/a45877", "genre": "Blues", "country": "EE.UU."},
    {"name": "WXPN 88.5 Philadelphia, PA", "url": "https://wxpnhi.xpn.org/xpnhi", "genre": "Blues", "country": "EE.UU."},
    {"name": "100 % COVERS LOUNGE", "url": "https://az1.mediacp.eu/listen/100coverslounge/radio.mp3", "genre": "Chillout", "country": "Canadá"},
    {"name": "AIRPORT LOUNGE RADIO", "url": "https://az1.mediacp.eu/listen/airport-lounge-radio/radio.mp3", "genre": "Chillout", "country": "Canadá"},
    {"name": "Café del Mar", "url": "https://streams.radio.co/se1a320b47/listen", "genre": "Chillout", "country": "España"},
    {"name": "Groove Wave Lounge", "url": "https://stm1.srvif.com:7576/;", "genre": "Chillout", "country": "Brasil"},
    {"name": "Lounge.FM - 100% Austria", "url": "https://s35.derstream.net/100austria.mp3", "genre": "Chillout", "country": "Austria"},
    {"name": "Music Radio", "url": "https://radio.musicradio.ai/listen/musicradio.ai/radio.mp3", "genre": "Chillout", "country": "Francia"},
    {"name": "Pure Lounge Radio FLAC", "url": "https://mscp4.live-streams.nl:8142/lounge.ogg", "genre": "Chillout", "country": "Países Bajos"},
    {"name": "SomaFM Fluid (128k MP3)", "url": "https://ice2.somafm.com/fluid-128-mp3", "genre": "Chillout", "country": "EE.UU."},
    {"name": "Alem Fm", "url": "https://turkmedya.radyotvonline.net/alemfmaac", "genre": "Clásica", "country": "Turquía"},
    {"name": "Classic FM Calm", "url": "https://media-ice.musicradio.com/ClassicFMCalmMP3", "genre": "Clásica", "country": "Reino Unido"},
    {"name": "Klassik Radio - Live", "url": "https://live.streams.klassikradio.de/klassikradio-deutschland/stream/mp3", "genre": "Clásica", "country": "Alemania"},
    {"name": "London Telugu Radio", "url": "https://c8.radioboss.fm/stream/33", "genre": "Clásica", "country": "India"},
    {"name": "RNE - Radio Clásica", "url": "https://rtvelivestream.rtve.es/rtvesec/rne/rne_r2_main.m3u8", "genre": "Clásica", "country": "España"},
    {"name": "Vivid Bharti", "url": "https://air.pc.cdn.bitgravity.com/air/live/pbaudio001/playlist.m3u8", "genre": "Clásica", "country": "India"},
    {"name": "WALM 2 HD", "url": "https://icecast.walmradio.com:8443/walm2", "genre": "Clásica", "country": "EE.UU."},
    {"name": "WQXR 105.9 FM", "url": "https://stream.wqxr.org/wqxr-web?nyprBrowserId=32c67956bf1d5600", "genre": "Clásica", "country": "EE.UU."},
    {"name": "Talksport 2", "url": "https://talksport.live.stream.broadcasting.news/stream2", "genre": "Conversación", "country": "Reino Unido"},
    {"name": "Almodóvar en La Onda 107.2 FM", "url": "https://nrf1.newradio.it:9972/stream", "genre": "Cumbia", "country": "España"},
    {"name": "Candela Radio", "url": "https://us10a.serverse.com/proxy/72fitnmvk?mp=/stream", "genre": "Cumbia", "country": "México"},
    {"name": "Color Estéreo 103.7 FM", "url": "https://azura5.emisiononline.es/listen/colorestereo/radio.mp3", "genre": "Cumbia", "country": "España"},
    {"name": "Radio Cumbia 90s", "url": "https://emiteradio.com/proxy/cumbia90s?mp=/stream", "genre": "Cumbia", "country": "Bolivia"},
    {"name": "Radio Gigante Bolivia", "url": "https://cloudstream2032.conectarhosting.com:7311/;", "genre": "Cumbia", "country": "Bolivia"},
    {"name": "Radio Huancayo", "url": "https://cloud9.ldwebstudios.net:7000/;", "genre": "Cumbia", "country": "Perú"},
    {"name": "Radio Megamix Lima", "url": "https://mdstrm.com/audio/5fada56fe4e09508207a7951/live.m3u8", "genre": "Cumbia", "country": "Perú"},
    {"name": "Tropicalia 93.9FM", "url": "https://rds3.desdeparaguay.net/movtropicalia/movtropicalia.stream/playlist.m3u8", "genre": "Cumbia", "country": "Paraguay"},
    {"name": "KKGK Fox Sports 98.9/1340", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/KKGKAMAAC.aac", "genre": "Deportes", "country": "EE.UU."},
    {"name": "Radio Sportiva", "url": "https://sportiva.inmystream.it/stream/sportiva", "genre": "Deportes", "country": "Italia"},
    {"name": "Sports Radio Brila FM", "url": "https://atunwadigital.streamguys1.com/brilafm", "genre": "Deportes", "country": "Nigeria"},
    {"name": "TSF Rádio Notícias", "url": "https://directo.tsf.pt/tsfdirecto.mp3", "genre": "Deportes", "country": "Portugal"},
    {"name": "Best Pro Electronic", "url": "https://az1.sednastream.com/radio/8150/Live?1582297952", "genre": "Electrónica", "country": "Albania"},
    {"name": "Frisky", "url": "https://stream.frisky.friskyradio.com/frisky_mp3_high", "genre": "Electrónica", "country": "EE.UU."},
    {"name": "Frisky Classics", "url": "https://stream.classics.friskyradio.com/classics_mp3_high", "genre": "Electrónica", "country": "EE.UU."},
    {"name": "Radio Party - Kanał Główny", "url": "https://s2.radioparty.pl:8015/stream?nocache=4171", "genre": "Electrónica", "country": "Polonia"},
    {"name": "Flamenco FM", "url": "https://sonic.mediatelekom.net/8534/;", "genre": "Flamenco", "country": "España"},
    {"name": "Top Urbano", "url": "https://radio.dominiserver.com/proxy/topurbano?mp=/stream", "genre": "Hip-Hop", "country": "Rep. Dominicana"},
    {"name": "Uganda DJs", "url": "https://stream.zeno.fm/muzrp86994zuv", "genre": "Hip-Hop", "country": "Uganda"},
    {"name": "BREAKZ.FM__ by rm.fm (rautemusik)", "url": "https://breakz-high.rautemusik.fm/?ref=radiobrowserinfo", "genre": "House", "country": "Alemania"},
    {"name": "Dance Wave!", "url": "https://dancewave.online/dance.mp3", "genre": "House", "country": "Hungría"},
    {"name": "Flaix FM", "url": "https://stream.flaixfm.cat/icecast", "genre": "House", "country": "España"},
    {"name": "Ibiza X Radio", "url": "https://stream.radiojar.com/p1f2vpv37reuv", "genre": "House", "country": "España"},
    {"name": "Perfect Deep House", "url": "https://stream.radiojar.com/asngk2sg798uv?1659885393", "genre": "House", "country": "España"},
    {"name": "Raxies FM", "url": "https://stream.zeno.fm/annpmyskb4jtv", "genre": "House", "country": "Chile"},
    {"name": "triple j (NSW)", "url": "https://mediaserviceslive.akamaized.net/hls/live/2038308/triplejnsw/master.m3u8", "genre": "House", "country": "Australia"},
    {"name": "Azul FM 101.9", "url": "https://azul-2.nty.uy/", "genre": "Indie", "country": "Uruguay"},
    {"name": "ByteFM (192k)", "url": "https://bytefm.cast.addradio.de/bytefm/main/high/stream", "genre": "Indie", "country": "Alemania"},
    {"name": "Gotanno FM 89.2", "url": "https://radio.gotanno.love/;", "genre": "Indie", "country": "Japón"},
    {"name": "RNE Radio 3", "url": "https://rtvelivestream.rtve.es/rtvesec/rne/rne_r3_main.m3u8", "genre": "Indie", "country": "España"},
    {"name": "Scream Radio", "url": "https://stream.zeno.fm/us9zu5w8zxhvv", "genre": "Indie", "country": "Filipinas"},
    {"name": "Yammat FM", "url": "https://stream.yammat.fm/radio/8000/yammat.mp3", "genre": "Indie", "country": "Croacia"},
    {"name": "Zip FM 103 FM", "url": "https://stream.zeno.fm/c0ytcn43vxquv", "genre": "Indie", "country": "Jamaica"},
    {"name": "100% ACID JAZZ", "url": "https://mpc1.mediacp.eu:8356/stream", "genre": "Jazz", "country": "Canadá"},
    {"name": "95.5 Jazz Radio", "url": "https://streaming.radio.co/s36bd2a451/listen", "genre": "Jazz", "country": "Costa Rica"},
    {"name": "Adroit Jazz Underground", "url": "https://icecast.walmradio.com:8443/jazz", "genre": "Jazz", "country": "EE.UU."},
    {"name": "Bossa Jazz Brasil", "url": "https://centova5.transmissaodigital.com:20104/live", "genre": "Jazz", "country": "Brasil"},
    {"name": "GENERATION SOUL DISCO FUNK RADIO", "url": "https://gestream.fr/g-radio-hd.mp3", "genre": "Jazz", "country": "Francia"},
    {"name": "Instrumental Jazz", "url": "https://jfm1.hostingradio.ru:14536/ijstream.mp3", "genre": "Jazz", "country": "Rusia"},
    {"name": "Jazz 88 Minneapolis KBEM", "url": "https://kbem-live.streamguys1.com/kbem_aac", "genre": "Jazz", "country": "EE.UU."},
    {"name": "Smooth Jazz Lounge", "url": "https://radio4.vip-radios.fm:18060/stream-128kmp3-SmoothJazzLounge", "genre": "Jazz", "country": "Brasil"},
    {"name": "SMOOTH JAZZ: Sax, piano, guitarra y voz: cool jazz", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ACIR22_s01AAC.aac", "genre": "Jazz", "country": "México"},
    {"name": "SmoothJazz.com 64k aac+", "url": "https://smoothjazz.cdnstream1.com/2585_64.aac", "genre": "Jazz", "country": "EE.UU."},
    {"name": "1055 Rock - Thessaloniki", "url": "https://radio.1055rock.gr:31056/live", "genre": "Metal", "country": "Grecia"},
    {"name": "Antyradio", "url": "https://n-4-2.dcs.redcdn.pl/sc/o2/Eurozet/live/antyradio.livx?audio=5", "genre": "Metal", "country": "Polonia"},
    {"name": "Best Of Rock.FM Alternative Rock", "url": "https://bestofrockfm.stream.vip/altrock/mp3-256/bestofrock.fm/", "genre": "Metal", "country": "Alemania"},
    {"name": "FIP Metal", "url": "https://icecast.radiofrance.fr/fipmetal-hifi.aac?id=radiofrance", "genre": "Metal", "country": "Francia"},
    {"name": "metal rock radio", "url": "https://kathy.torontocast.com:2800/;", "genre": "Metal", "country": "EE.UU."},
    {"name": "Radio BOB - Nu Metal (mp3 192)", "url": "https://streams.radiobob.de/numetal/mp3-192/", "genre": "Metal", "country": "Alemania"},
    {"name": "SomaFM Metal Detector (128k AAC)", "url": "https://ice2.somafm.com/metal-128-aac", "genre": "Metal", "country": "EE.UU."},
    {"name": "РАДІОПІХОТА", "url": "https://online.pihota.fm/listen/radio/aac64", "genre": "Metal", "country": "Ucrania"},
    {"name": "Catalunya Informació (Catinfo)", "url": "https://shoutcast.ccma.cat/ccma/catalunyainformacioHD.mp3", "genre": "Noticias", "country": "España"},
    {"name": "CNN", "url": "https://tunein.cdnstream1.com/2868_96.mp3", "genre": "Noticias", "country": "EE.UU."},
    {"name": "FM 90 Saladillo FM 90.7", "url": "https://chino.republicahosting.com:2316/live", "genre": "Noticias", "country": "Argentina"},
    {"name": "Radio Nacional de España - Radio 5 Todo noticias", "url": "https://d131.rndfnk.com/star/crtve/rne5/main/mp3/128/stream.mp3?aggregator=tunein&cid=01GEP4MW5CAHPYP1EXHVKWFJ8W&sid=2OeE42hivuba6dTGvjnMGjKByQe&token=cdczXcnimVx4AY4iamqYbTMdu3cK7oBxmS2UQN9cWc0&tvf=pdPcDBxuVxdkMTMxLnJuZGZuay5jb20", "genre": "Noticias", "country": "España"},
    {"name": "SWR3", "url": "https://liveradio.swr.de/sw282p3/swr3/play.mp3", "genre": "Noticias", "country": "Alemania"},
    {"name": "102.7 KIIS FM", "url": "https://stream.revma.ihrhls.com/zc185", "genre": "Pop", "country": "EE.UU."},
    {"name": "40 Principales Colombia", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/%20LOS40_COLOMBIA.mp3", "genre": "Pop", "country": "Colombia"},
    {"name": "AMOR SOLO POP: Pop y baladas en español", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ACIR03_s01AAC.aac", "genre": "Pop", "country": "México"},
    {"name": "Bayern 3", "url": "https://dispatcher.rndfnk.com/br/br3/live/mp3/mid", "genre": "Pop", "country": "Alemania"},
    {"name": "BOX : Japan City Pop - 日本のシティポップ", "url": "https://play.streamafrica.net/japancitypop", "genre": "Pop", "country": "Japón"},
    {"name": "Power POP", "url": "https://listen.powerapp.com.tr/powerpop/128/chunks.m3u8", "genre": "Pop", "country": "Turquía"},
    {"name": "Radio Italia Solo Musica Italiana", "url": "https://radioitaliasmi.akamaized.net/hls/live/2093120/RISMI/stream01/streamPlaylist.m3u8", "genre": "Pop", "country": "Italia"},
    {"name": "SomaFM PopTron (128k AAC)", "url": "https://ice2.somafm.com/poptron-128-aac", "genre": "Pop", "country": "EE.UU."},
    {"name": "SomaFM PopTron (128k MP3)", "url": "https://ice5.somafm.com/poptron-128-mp3", "genre": "Pop", "country": "EE.UU."},
    {"name": "Super Fm", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/SUPER_FM_SC", "genre": "Pop", "country": "Turquía"},
    {"name": "12PUNKS.FM__ by rautemusik (rm.fm)", "url": "https://12punks-high.rautemusik.fm/?ref=radiobrowser", "genre": "Punk", "country": "Alemania"},
    {"name": "Boot Boy Radio", "url": "https://streaming04.liveboxstream.uk/proxy/dwain?mp=/stream", "genre": "Punk", "country": "Reino Unido"},
    {"name": "Exclusively Ramones", "url": "https://streaming.exclusive.radio/er/ramones/icecast.audio", "genre": "Punk", "country": "EAU"},
    {"name": "Nightride FM - Darksynth", "url": "https://stream.nightride.fm/darksynth.mp3", "genre": "Punk", "country": "Alemania"},
    {"name": "Nightride FM - Horrorsynth", "url": "https://stream.nightride.fm/horrorsynth.mp3", "genre": "Punk", "country": "Alemania"},
    {"name": "punk irratia", "url": "https://punkirratia.net:8443/punk", "genre": "Punk", "country": "España"},
    {"name": "Exclusively Michael Jackson", "url": "https://streaming.exclusive.radio/er/michaeljackson/icecast.audio", "genre": "R&B", "country": "EAU"},
    {"name": "Smooth Chill", "url": "https://media-ssl.musicradio.com/ChillMP3", "genre": "R&B", "country": "Reino Unido"},
    {"name": "HOTT 95.3FM", "url": "https://ice64.securenetsystems.net/HOTT953", "genre": "Reggae", "country": "Barbados"},
    {"name": "Irie FM", "url": "https://stream.iriefm.net:8008/stream", "genre": "Reggae", "country": "Jamaica"},
    {"name": "Radio Reggae Brasil", "url": "https://casthttps.suaradionanet.net/13805/stream", "genre": "Reggae", "country": "Brasil"},
    {"name": "REGGAE CHILL CAFE", "url": "https://maggie.torontocast.com:2020/stream/reggaechillcafe", "genre": "Reggae", "country": "Canadá"},
    {"name": "Reggae.fr", "url": "https://listen.radioking.com/radio/50473/stream/87415", "genre": "Reggae", "country": "Francia"},
    {"name": "SomaFM Heavyweight Reggae (256k MP3)", "url": "https://ice2.somafm.com/reggae-256-mp3", "genre": "Reggae", "country": "EE.UU."},
    {"name": "CLÁSICOS REGGAETON 24_7", "url": "https://stream.zeno.fm/2g1qkn4cbpeuv", "genre": "Reggaeton", "country": "Colombia"},
    {"name": "La Mega", "url": "https://mdstrm.com/audio/632c9ae6660fef03fe3855fe/live.m3u8", "genre": "Reggaeton", "country": "Colombia"},
    {"name": "Latina reggaeton", "url": "https://latinareggaeton.ice.infomaniak.ch/latinareggaeton.mp3", "genre": "Reggaeton", "country": "Francia"},
    {"name": "Radio Company Reggaetown", "url": "https://sphera.fluidstream.eu/companyreggaetown.mp3", "genre": "Reggaeton", "country": "Italia"},
    {"name": "Air Gospel", "url": "https://stream.zeno.fm/qkgrhugy908uv", "genre": "Religiosa", "country": "Nigeria"},
    {"name": "80 EXITOS", "url": "https://80sexitos.stream.laut.fm/80sexitos", "genre": "Retro / Oldies", "country": "España"},
    {"name": "Exclusively Led Zeppelin", "url": "https://streaming.exclusive.radio/er-app/ledzeppelin/icecast.audio", "genre": "Retro / Oldies", "country": "EAU"},
    {"name": "Exclusively Led Zeppelin - Only Hits", "url": "https://streaming.exclusive.radio/er-app/ledzeppelinhits/icecast.audio", "genre": "Retro / Oldies", "country": "EAU"},
    {"name": "Heart 80s", "url": "https://media-ssl.musicradio.com/Heart80sMP3", "genre": "Retro / Oldies", "country": "Reino Unido"},
    {"name": "Intamixx 80s 90s Radio UK", "url": "https://radio.intamixx.uk:8443/radio2", "genre": "Retro / Oldies", "country": "Reino Unido"},
    {"name": "La Lupe Guadalajara 99.9 FM", "url": "https://mdstrm.com/audio/6737875eb61ca2fa731a2891/icecast.audio", "genre": "Retro / Oldies", "country": "México"},
    {"name": "Radio Policía (Medellín) Nacional 96.4 FM", "url": "https://radio35.virtualtronics.com/proxy/radiopolicia964?mp=/stream", "genre": "Retro / Oldies", "country": "Colombia"},
    {"name": "Rafi hit songs", "url": "https://stream-143.zeno.fm/0zkr7x8ztm0uv?zs=WTPQx8TiQXSo11XU0iyTAQ", "genre": "Retro / Oldies", "country": "India"},
    {"name": "011.fm – House of Hair", "url": "https://listen.011fm.com/stream16", "genre": "Rock", "country": "EE.UU."},
    {"name": "BR - The Classic Rock", "url": "https://stream.zeno.fm/nbq1aq62gd0uv", "genre": "Rock", "country": "Brasil"},
    {"name": "Convoy en vivo", "url": "https://live.convoynetwork.com/stream", "genre": "Rock", "country": "México"},
    {"name": "LOS40 Classic", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/LOS40_CLASSIC.mp3", "genre": "Rock", "country": "España"},
    {"name": "Mariskal Rock", "url": "https://media.profesionalhosting.com:8047/stream", "genre": "Rock", "country": "España"},
    {"name": "MIX OCHENTAS: New Wave, Glam y Rock de los 80s", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ACIR13_s01AAC.aac", "genre": "Rock", "country": "México"},
    {"name": "Radio 1550, La Radio Joven. Huancayo. 88.9 FM.", "url": "https://streaming.virtugo.digital:8002/stream", "genre": "Rock", "country": "Perú"},
    {"name": "Radio Rock", "url": "https://aud-stream-radiorock.nm-elemental.nelonenmedia.fi/playlist.m3u8", "genre": "Rock", "country": "Finlandia"},
    {"name": "Radio Rock (NO)", "url": "https://live-bauerno.sharp-stream.com/radiorock_no_mp3", "genre": "Rock", "country": "Noruega"},
    {"name": "Radio ROCKS Kyiv 103.6FM HD", "url": "https://online.radioroks.ua/RadioROKS_HD", "genre": "Rock", "country": "Ucrania"},
    {"name": "ROCK EN ESPAÑOL: Rock de México, España y Argentina", "url": "https://16643.live.streamtheworld.com:443/ACIR20_S01AAC.aac", "genre": "Rock", "country": "México"},
    {"name": "ROCK FM Classic Rock", "url": "https://audiotainment-sw.streamabc.net/atsw-classicrock-mp3-128-2538548?", "genre": "Rock", "country": "EE.UU."},
    {"name": "100 % SALSA", "url": "https://stm01.streammaximum.com:8194/;", "genre": "Salsa", "country": "España"},
    {"name": "Caracas. Salsa Brava...", "url": "https://stream.zeno.fm/fq0c9ohszctuv", "genre": "Salsa", "country": "Venezuela"},
    {"name": "Caracas. Salsa Romántica...", "url": "https://stream-285.surfernetwork.com/ftly191pojttv?zt=eyJhbGciOiJIUzI1NiJ9.eyJzdHJlYW0iOiJmdGx5MTkxcG9qdHR2IiwiaG9zdCI6InN0cmVhbS0yODUuc3VyZmVybmV0d29yay5jb20iLCJ0bSI6ZmFsc2UsInJ0dGwiOjUsImp0aSI6IkR1LTFJVTBBUTZtXzhXdWFFdFhlb1EiLCJpYXQiOjE3OTA0NDA0NzUsImV4cCI6MTc5MDQ0MDUzNX0.Hu1lKDFZmxvzzxG4M8jDvmM7i_b9tIOPEbyLIVWhh0M", "genre": "Salsa", "country": "Venezuela"},
    {"name": "La Salsa Maestra", "url": "https://stream.zeno.fm/c1skkw28pfeuv", "genre": "Salsa", "country": "Perú"},
    {"name": "Olímpica Stereo (Medellín) 104.9-FM", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/OLP_MEDELLINAAC.aac", "genre": "Salsa", "country": "Colombia"},
    {"name": "Radio Panamericana", "url": "https://mdstrm.com/audio/6598b62dded1380470f4e539/icecast.audio", "genre": "Salsa", "country": "Perú"},
    {"name": "Salsa Latina", "url": "https://play10.tikast.com/proxy/zsalsalatina?mp=/stream", "genre": "Salsa", "country": "Colombia"},
    {"name": "Salsa y mas Cali", "url": "https://stream.zeno.fm/42w3pfn7pzzuv", "genre": "Salsa", "country": "Colombia"},
    {"name": "Top Salsa Radio", "url": "https://radio.dominiserver.com/proxy/topsalsaradio?mp=/stream", "genre": "Salsa", "country": "Rep. Dominicana"},
    {"name": "Tropical 100 Salsa", "url": "https://stream-107.zeno.fm/cjgfujr8yhbvv?zs=VsqKiPTASc-XIz7P9HnYjQ", "genre": "Salsa", "country": "Rep. Dominicana"},
    {"name": "Deutschlandfunk | DLF | MP3 128k", "url": "https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3?aggregator=web", "genre": "Soul", "country": "Alemania"},
    {"name": "FM 80 FUNKY MUSIC", "url": "https://listen.radioking.com/radio/467555/stream/523739", "genre": "Soul", "country": "Francia"},
    {"name": "Funk the Planet", "url": "https://streaming.live365.com/a01484", "genre": "Soul", "country": "EE.UU."},
    {"name": "Funky Corner Radio (USA)", "url": "https://ais-sa2.cdnstream1.com/2447_192.mp3", "genre": "Soul", "country": "EE.UU."},
    {"name": "FUNKY RADIO - Only Funk Music (60's 70's)", "url": "https://funkyradio.streamingmedia.it/play.mp3", "genre": "Soul", "country": "EE.UU."},
    {"name": "Rundfunkautist", "url": "https://rundfunkautist.stream.laut.fm/rundfunkautist?t302=2026-09-25_17-40-21&uuid=465d07ba-56cb-8ae6-c230-29b385e62360", "genre": "Soul", "country": "Alemania"},
    {"name": "Radio Tango", "url": "https://stream.zeno.fm/uxxf2xaxdzzuv", "genre": "Tango", "country": "Colombia"},
    {"name": "RauteMusik - TECHNO", "url": "https://streams.rautemusik.fm/techno/mp3-192?ref=radiobrowser", "genre": "Techno", "country": "Alemania"},
    {"name": "Remember Vip Techno", "url": "https://stream-153.zeno.fm/xilwjn4t17qvv", "genre": "Techno", "country": "España"},
    {"name": "TechnoBase.FM", "url": "https://listener3.mp3.tb-group.fm/tb.mp3", "genre": "Techno", "country": "Alemania"},
    {"name": "Technolovers - MINIMAL", "url": "https://stream.technolovers.fm/minimal?ref=radiobrowser", "genre": "Techno", "country": "Alemania"},
    {"name": "Technolovers EDM", "url": "https://stream.technolovers.fm/edm?ref=radiobrowser", "genre": "Techno", "country": "Alemania"},
    {"name": "Energía Flamenca", "url": "https://axarquia.emisiononline.es/radio/8020/radio.mp3", "genre": "Varios", "country": "España"},
    {"name": "HKM radio", "url": "https://stream.zenolive.com/rhf9cqkz3yzuv.aac", "genre": "Varios", "country": "España"},
    {"name": "La 100 - 99.9 FM - Grupo Clarín - Buenos Aires, Argentina", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/FM999_56.mp3", "genre": "Varios", "country": "Argentina"},
    {"name": "La Consentida San Luis 107.9", "url": "https://radios.blumhost.es/8136/;", "genre": "Varios", "country": "México"},
    {"name": "La Discoteca Radio", "url": "https://streamingmediaradio.live:8002/stream", "genre": "Varios", "country": "Colombia"},
    {"name": "La Lupe 105.3 FM Monterrey", "url": "https://mdstrm.com/audio/6737993c9422ca09f9b9ea70/icecast.audio", "genre": "Varios", "country": "México"},
    {"name": "La Mega (Medellín) 92.9 FM", "url": "https://us-b4-p-e-qg12-audio.cdn.mdstrm.com/live-audio-aw/632cb48f613bac0856b931ab", "genre": "Varios", "country": "Colombia"},
    {"name": "La Mejor Los Cabos 89.9/102.3 FM", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/XHCCAB.mp3", "genre": "Varios", "country": "México"},
    {"name": "Latina 104", "url": "https://radio.dominiserver.com/proxy/latina104?mp=/stream", "genre": "Varios", "country": "Rep. Dominicana"},
    {"name": "LOS 40 Principales España", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/Los40.mp3", "genre": "Varios", "country": "España"},
    {"name": "LOS40 Chile", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/LOS40_CHILEAAC.aac", "genre": "Varios", "country": "Chile"},
    {"name": "LOVE FM: All you need is Love ♥", "url": "https://mdstrm.com/audio/66a01759c5aa2b85d66b5933/live.m3u8", "genre": "Varios", "country": "México"},
    {"name": "Metro 95.1", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/METRO.mp3", "genre": "Varios", "country": "Argentina"},
    {"name": "MIX: 80's, 90's y Más", "url": "https://18363.live.streamtheworld.com:443/XHDFMFMAAC.aac", "genre": "Varios", "country": "México"},
    {"name": "neverland", "url": "https://stream-166.zeno.fm/oaqigxpfjzqvv?zt=eyJhbGciOiJIUzI1NiJ9.eyJzdHJlYW0iOiJvYXFpZ3hwZmp6cXZ2IiwiaG9zdCI6InN0cmVhbS0xNjYuemVuby5mbSIsInJ0dGwiOjUsImp0aSI6IjFnRWVwSWpIUXJXVElZSU1pLVlrenciLCJpYXQiOjE3NDgxMzU4OTUsImV4cCI6MTc0ODEzNTk1NX0.b4Llu6iAJk1NPa2U9OhIjm_3CZQyLuRJZWiNecQWBdY", "genre": "Varios", "country": "Argentina"},
    {"name": "Onda Cero Te Activa", "url": "https://mdstrm.com/audio/6598b65ab398c90871aff8cc/icecast.audio", "genre": "Varios", "country": "Perú"},
    {"name": "PA BAILAR: Banda y grupera para la fiesta", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ACIR08_s01AAC.aac", "genre": "Varios", "country": "México"},
    {"name": "RAC1", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/RAC_1.mp3", "genre": "Varios", "country": "España"},
    {"name": "Radio Canela Guayas", "url": "https://canelaradio.makrodigital.com/stream/canelaradioguayaquil", "genre": "Varios", "country": "Ecuador"},
    {"name": "Radio Disney 94.3 - Buenos Aires, Argentina", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/DISNEY_ARG_BA_ADP.aac", "genre": "Varios", "country": "Argentina"},
    {"name": "Radio La Zona Urbana", "url": "https://mdstrm.com/audio/5fada54116646e098d97e6a5/live.m3u8", "genre": "Varios", "country": "Perú"},
    {"name": "Radiomar", "url": "https://us-b4-p-e-qg12-audio.cdn.mdstrm.com/live-audio-aw/6839e261d2efddf5bfbc2d3d", "genre": "Varios", "country": "Perú"},
    {"name": "Rumbera 98.7 FM", "url": "https://stream.zeno.fm/85y72q4wzdfuv", "genre": "Varios", "country": "Venezuela"},
    {"name": "TROPICALÍSIMA: El sonido de la calle", "url": "https://securestreams7.autopo.st/?uri=https://s2.mexside.net/8030/stream", "genre": "Varios", "country": "México"},
]

# Mapea etiquetas de genero en ingles (Radio Browser) a las del catalogo
GENRE_ALIASES = {
    "reggaeton": "Reggaeton", "reggae": "Reggae", "dub": "Reggae",
    "salsa": "Salsa", "bachata": "Bachata", "cumbia": "Cumbia",
    "latin": "Latina", "latino": "Latina", "flamenco": "Flamenco",
    "tango": "Tango", "rock": "Rock", "classic rock": "Retro / Oldies",
    "metal": "Metal", "punk": "Punk", "indie": "Indie",
    "alternative": "Indie", "jazz": "Jazz", "blues": "Blues",
    "soul": "Soul", "r&b": "R&B", "hip hop": "Hip-Hop", "hiphop": "Hip-Hop",
    "rap": "Hip-Hop", "pop": "Pop", "80s": "Retro / Oldies",
    "70s": "Retro / Oldies", "60s": "Retro / Oldies", "oldies": "Retro / Oldies",
    "retro": "Retro / Oldies", "folk": "Folk", "country": "Folk",
    "classical": "Clásica", "clasica": "Clásica", "chillout": "Chillout",
    "chill": "Chillout", "lounge": "Chillout", "downtempo": "Chillout",
    "ambient": "Ambient", "house": "House", "techno": "Techno",
    "trance": "Dance", "dance": "Dance", "edm": "Dance",
    "electronic": "Electrónica", "electro": "Electrónica",
    "k-pop": "K-Pop", "kpop": "K-Pop", "news": "Noticias",
    "sport": "Deportes", "sports": "Deportes", "talk": "Conversación",
    "religious": "Religiosa", "christian": "Religiosa", "gospel": "Religiosa",
    "children": "Infantil", "kids": "Infantil", "mariachi": "Regional mexicano",
    "ranchera": "Regional mexicano", "regional": "Regional mexicano",
    "variety": "Varios", "general": "Varios", "music": "Varios",
}

EXTRA_RADIO_GENRES = [
    "Todos", "Reggaeton", "Reggae", "Salsa", "Bachata", "Cumbia", "Latina",
    "Tango", "Flamenco", "Regional mexicano", "Rock", "Metal", "Punk",
    "Indie", "Jazz", "Blues", "Soul", "R&B", "Hip-Hop", "Pop",
    "Retro / Oldies", "Folk", "Clásica", "Chillout", "Ambient", "House",
    "Techno", "Dance", "Electrónica", "K-Pop", "Noticias", "Deportes",
    "Conversación", "Religiosa", "Infantil", "Varios",
]

# La API de Radio Browser busca por tag en minusculas y es sensible a mayusculas
GENRE_TO_TAG = {
    "Reggaeton": "reggaeton", "Reggae": "reggae", "Salsa": "salsa",
    "Bachata": "bachata", "Cumbia": "cumbia", "Latina": "latin",
    "Tango": "tango", "Flamenco": "flamenco",
    "Regional mexicano": "mariachi", "Rock": "rock", "Metal": "metal",
    "Punk": "punk", "Indie": "indie", "Jazz": "jazz", "Blues": "blues",
    "Soul": "soul", "R&B": "r&b", "Hip-Hop": "hip hop", "Pop": "pop",
    "Retro / Oldies": "oldies", "Folk": "folk", "Clásica": "classical",
    "Chillout": "chillout", "Ambient": "ambient", "House": "house",
    "Techno": "techno", "Dance": "dance", "Electrónica": "electronic",
    "K-Pop": "kpop", "Noticias": "news", "Deportes": "sports",
    "Conversación": "talk", "Religiosa": "christian", "Infantil": "children",
}

SPAM_PATTERNS = (
    "top 100", "top100", "charts -", "24/7 non", "24 horas nonstop",
    "non-stop music", "top 40 charts", "icecast directory", "test stream",
)

def is_spam_station(name):
    """Descarta entradas publicitarias tipo '# TOP 100 ... DJ MIX'."""
    low = (name or "").lower()
    if any(p in low for p in SPAM_PATTERNS):
        return True
    return low.strip().startswith("#") and "radio" in low and len(low) > 60

def matches_genre(station, genre):
    """¿El género de una estación coincide con el filtro seleccionado?

    La búsqueda online usa `tag` como subcadena, así que una estación con
    "pop rock" pertenece a un filtro "Pop". Aceptamos igualdad o containment.
    """
    st_genre = (station.get("genre") or "").lower().strip()
    wanted = (genre or "").lower().strip()
    if not wanted or wanted == "todos":
        return True
    if not st_genre:
        return False
    if st_genre == wanted:
        return True
    words = [w for w in re.split(r"[^a-z0-9&]+", st_genre) if w]
    if wanted in words:
        return True
    return len(wanted) >= 4 and wanted in st_genre

def get_radio_path():
    return os.path.join(get_app_dir(), "radio_favoritas.json")

def normalize_station(station):
    """Normaliza una estacion a {name, url, genre, country}."""
    if not isinstance(station, dict):
        return None
    url = (station.get("url") or station.get("url_resolved") or "").strip()
    name = str(station.get("name") or "").strip()
    if not url or not name:
        return None
    if not url.lower().startswith(("http://", "https://")):
        return None
    tags = station.get("tags") or station.get("genre") or ""
    genre = str(tags).split(",")[0].strip()
    genre = GENRE_ALIASES.get(genre.lower(), genre)
    country = str(station.get("country") or "").strip()
    if not genre or genre.startswith("#") or not any(c.isalpha() for c in genre):
        genre = "Varios"
    if not country:
        country = station.get("countrycode") or "Internacional"
    return {
        "name": name,
        "url": url,
        "genre": genre,
        "country": country,
    }

def load_radio_favorites():
    """Carga radio_favoritas.json (favoritas + ultima estacion jugada)."""
    data = {"favoritas": [], "ultima": None}
    path = get_radio_path()
    if not os.path.exists(path):
        return data
    try:
        # utf-8-sig acepta el fichero con o sin BOM (p. ej. editado a mano)
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return data
        for item in raw.get("favoritas", []) or []:
            st = normalize_station(item)
            if st:
                data["favoritas"].append(st)
        ultima = normalize_station(raw.get("ultima"))
        if ultima:
            data["ultima"] = ultima
    except Exception as e:
        print(f"Failed to load radio favorites: {e}")
    return data

def save_radio_favorites(data):
    path = get_radio_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save radio favorites: {e}")

def get_radio_stations():
    """Catalogo local: emisoras curadas + las que anadio el usuario."""
    stations = []
    seen = set()
    for raw in CURATED_RADIO:
        st = normalize_station(raw)
        if st and st["url"] not in seen:
            seen.add(st["url"])
            stations.append(st)
    return stations

def get_favorite_stations():
    return list(load_radio_favorites()["favoritas"])

def is_favorite(station):
    url = (station or {}).get("url")
    if not url:
        return False
    return any(f["url"] == url for f in load_radio_favorites()["favoritas"])

def add_favorite(station):
    """Agrega una estacion a mis favoritas en radio_favoritas.json."""
    st = normalize_station(station)
    if not st:
        return False
    data = load_radio_favorites()
    if any(f["url"] == st["url"] for f in data["favoritas"]):
        return False
    data["favoritas"].append(st)
    save_radio_favorites(data)
    return True

def remove_favorite(station):
    url = (station or {}).get("url")
    if not url:
        return False
    data = load_radio_favorites()
    before = len(data["favoritas"])
    data["favoritas"] = [f for f in data["favoritas"] if f["url"] != url]
    if len(data["favoritas"]) == before:
        return False
    save_radio_favorites(data)
    return True

def remember_last_station(station):
    """Guarda la estacion seleccionada para reproducirla al reabrir."""
    st = normalize_station(station)
    if not st:
        return
    data = load_radio_favorites()
    data["ultima"] = st
    save_radio_favorites(data)

def get_radio_genres(stations):
    genres = {"Todos"}
    for st in stations:
        genres.add(st.get("genre") or "Varios")
    ordered = [g for g in EXTRA_RADIO_GENRES if g in genres or g == "Todos"]
    ordered += sorted(g for g in genres if g not in ordered)
    return ordered

def search_radio_online(query="", genre="", limit=RADIO_SEARCH_LIMIT):
    """Busca emisoras en el catalogo publico Radio Browser.

    Se ejecuta en un hilo aparte: esta funcion hace red y bloquea.
    """
    params = {
        "hidebroken": "true",
        "order": "clickcount",
        "reverse": "true",
        "limit": str(limit),
    }
    query = (query or "").strip()
    if query:
        params["name"] = query
    if genre and genre != "Todos":
        tag = GENRE_TO_TAG.get(genre, genre.lower())
        if tag:
            params["tag"] = tag
            params["tagExact"] = "false"
    qs = urllib.parse.urlencode(params)

    last_error = None
    for base in RADIO_API_BASES:
        try:
            req = urllib.request.Request(
                f"{base}/json/stations/search?{qs}",
                headers={"User-Agent": RADIO_USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=RADIO_TIMEOUT) as resp:
                raw = json.loads(resp.read().decode("utf-8", "replace"))
            stations = []
            seen = set()
            for item in raw or []:
                st = normalize_station(item)
                if not st or st["url"] in seen or is_spam_station(st["name"]):
                    continue
                seen.add(st["url"])
                stations.append(st)
            return stations
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(
        f"No se pudo consultar el catalogo de emisoras online ({last_error})"
    )

class MusicMinimalPlayer:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        
        self.music_root = get_music_root()
        self.playlists = scan_playlists(self.music_root)
        self.playlist_names = sorted(self.playlists.keys())
        
        self.current_playlist_files = []
        self.current_playlist_name = None
        if self.playlist_names:
            saved_playlist = self.config.get("playlist", "")
            if saved_playlist in self.playlist_names:
                self.current_playlist_name = saved_playlist
            else:
                self.current_playlist_name = self.playlist_names[0]
            self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        
        self.current_index = self.config.get("song_index", 0)
        if self.current_index >= len(self.current_playlist_files):
            self.current_index = 0
        
        self.source_mode = "local"
        self.current_station = None
        self.radio_favorites = load_radio_favorites()
        
        self.instance = vlc.Instance() if vlc is not None else None
        self.player = self.instance.media_player_new() if self.instance is not None else None
        self.player_monitor_running = False
        self.player_monitor_thread = None
        self.time_monitor_running = False
        self.time_monitor_thread = None
        self.song_paths = []
        self.station_list = []
        
        self.setup_window()
        self.build_ui()
        self._load_initial_source()
        self.start_player_monitor()
        self.start_time_monitor()
    
    def _load_initial_source(self):
        """Reproduce la ultima radio guardada, o la playlist local."""
        if self.config.get("last_source", "local") == "radio":
            station = self.radio_favorites.get("ultima")
            if station and station.get("url"):
                self.play_radio_station(station)
                return
        self._load_current_playlist()
    
    def setup_window(self):
        self.root.title("Music Minimal Player")
        self.root.geometry(f"{self.config['width']}x{self.config['height']}+{self.config['x']}+{self.config['y']}")
        self.root.configure(bg=self.config["bg_color"])
        
        if self.config["show_titlebar"]:
            self.root.overrideredirect(False)
        else:
            self.root.overrideredirect(True)
        
        self.root.attributes("-alpha", self.config["opacity"] / 100.0)
        
        if self.config["resizable"]:
            self.root.resizable(True, True)
        else:
            self.root.resizable(False, False)
        
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
        
        self.root.bind("<Configure>", self.on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def start_move(self, event):
        self.x = event.x
        self.y = event.y
    
    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
    
    def build_ui(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", 
                       fieldbackground=btn_color,
                       background=btn_color,
                       foreground=font_color,
                       arrowcolor=font_color,
                       borderwidth=0,
                       padding=0)
        style.map("TCombobox",
                 fieldbackground=[('readonly', btn_color)],
                 foreground=[('readonly', font_color)])
        
        main_frame = tk.Frame(self.root, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        self.prev_btn = self.create_button(main_frame, "◀", self.prev_song, btn_color, font_color)
        self.prev_btn.pack(side=tk.LEFT, padx=0)
        
        self.play_btn = self.create_button(main_frame, "▶", self.toggle_play, btn_color, font_color)
        self.play_btn.pack(side=tk.LEFT, padx=0)
        
        self.next_btn = self.create_button(main_frame, "▶", self.next_song, btn_color, font_color)
        self.next_btn.pack(side=tk.LEFT, padx=0)
        
        self.song_label = tk.Label(
            main_frame,
            text="No song playing",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9),
            width=20,
            anchor="center"
        )
        self.song_label.pack(side=tk.LEFT, padx=0)
        
        self.time_label = tk.Label(
            main_frame,
            text="00:00",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 8),
            width=8,
            anchor="center"
        )
        self.time_label.pack(side=tk.LEFT, padx=0)
        
        self.volume_down_btn = self.create_button(main_frame, "-", self.volume_down, btn_color, font_color)
        self.volume_down_btn.pack(side=tk.LEFT, padx=0)
        
        self.volume_up_btn = self.create_button(main_frame, "+", self.volume_up, btn_color, font_color)
        self.volume_up_btn.pack(side=tk.LEFT, padx=0)
        
        self.drag_btn = self.create_drag_button(main_frame, "::", bg_color, font_color)
        self.drag_btn.pack(side=tk.LEFT, padx=0)
        
        self.playlist_btn = self.create_button(main_frame, "☰", self.open_playlist_window, btn_color, font_color)
        self.playlist_btn.pack(side=tk.LEFT, padx=0)
        
        self.options_btn = self.create_button(main_frame, "⚙", self.open_options, btn_color, font_color)
        self.options_btn.pack(side=tk.LEFT, padx=0)
        
        self.close_btn = self.create_button(main_frame, "×", self.on_close, bg_color, font_color)
        self.close_btn.pack(side=tk.LEFT, padx=0)
    
    def create_button(self, parent, text, command, bg_color, fg_color):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground=bg_color,
            activeforeground=fg_color,
            relief=tk.FLAT,
            width=3,
            height=1,
            font=("Arial", 10, "bold"),
            bd=0
        )
        return btn
    
    def create_drag_button(self, parent, text, bg_color, fg_color):
        btn = tk.Button(
            parent,
            text=text,
            bg=bg_color,
            fg=fg_color,
            activebackground=bg_color,
            activeforeground=fg_color,
            relief=tk.FLAT,
            width=3,
            height=1,
            font=("Arial", 10, "bold"),
            bd=0,
            cursor="fleur"
        )
        btn.bind("<Button-1>", self.start_move)
        btn.bind("<B1-Motion>", self.do_move)
        return btn
    
    def on_window_configure(self, event):
        if event.widget == self.root:
            self.config["width"] = event.width
            self.config["height"] = event.height
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            self.config["x"] = x
            self.config["y"] = y
            save_config(self.config)
    
    def refresh_playlists(self):
        self.playlists = scan_playlists(self.music_root)
        self.playlist_names = sorted(self.playlists.keys())
        
        if self.playlist_names:
            if self.current_playlist_name not in self.playlist_names:
                self.current_playlist_name = self.playlist_names[0]
            self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        else:
            self.current_playlist_name = None
            self.current_playlist_files = []
        
        self.current_index = 0
        self._load_current_playlist()
    
    def on_playlist_change(self, playlist_name):
        self.current_playlist_name = playlist_name
        self.config["playlist"] = self.current_playlist_name
        save_config(self.config)
        self.current_index = 0
        self._load_current_playlist()
    
    def on_shuffle_toggle(self):
        self.config["shuffle"] = self.config.get("shuffle", True)
        save_config(self.config)
    
    def volume_up(self):
        current_vol = self.config["volume"]
        new_vol = min(100, current_vol + 10)
        self.config["volume"] = new_vol
        if hasattr(self, 'player') and self.player is not None:
            self.player.audio_set_volume(new_vol)
        save_config(self.config)
    
    def volume_down(self):
        current_vol = self.config["volume"]
        new_vol = max(0, current_vol - 10)
        self.config["volume"] = new_vol
        if hasattr(self, 'player') and self.player is not None:
            self.player.audio_set_volume(new_vol)
        save_config(self.config)
    
    def toggle_pin(self):
        self.config["pinned"] = self.config.get("pinned", True)
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
        save_config(self.config)
    
    def _load_current_playlist(self):
        self.current_playlist_files = self.playlists.get(self.current_playlist_name, [])
        if not self.current_playlist_files:
            self.song_label.config(text="No files in playlist")
            return
        self.play_song_at_index(self.current_index)
    
    def play_song_at_index(self, idx):
        if not self.current_playlist_files:
            return
        if idx < 0 or idx >= len(self.current_playlist_files):
            return
        self.current_index = idx
        file_path = self.current_playlist_files[self.current_index]
        self.source_mode = "local"
        self.current_station = None
        
        self.config["song_index"] = self.current_index
        self.config["last_source"] = "local"
        save_config(self.config)
        
        title = os.path.basename(file_path)
        if vlc is not None and self.instance is not None:
            try:
                media = self.instance.media_new(file_path)
                media.parse()
                t = media.get_meta(vlc.Meta.Title)
                if t:
                    title = t
                self.player.set_media(media)
                self.player.play()
                self.player.audio_set_volume(self.config["volume"])
            except Exception as e:
                print(f"Error playing {file_path}: {e}")
                return
        
        self.song_label.config(text=title)
        self.play_btn.config(text="⏸")
    
    def open_options(self):
        options_window = tk.Toplevel(self.root)
        options_window.title("Configuration")
        options_window.geometry("380x540")
        options_window.configure(bg=self.config["bg_color"])
        options_window.transient(self.root)
        options_window.grab_set()
        options_window.resizable(False, True)
        
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        container_frame = tk.Frame(options_window, bg=bg_color)
        container_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(container_frame, bg=bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(container_frame, orient="vertical", command=canvas.yview, width=15)
        scrollable_frame = tk.Frame(canvas, bg=bg_color)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        def on_canvas_configure(event):
            canvas_width = event.width
            container_width = int(canvas_width * 0.9)
            canvas.create_window(canvas_width // 2, 0, window=scrollable_frame, anchor="n", width=container_width)
        
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_container = tk.Frame(scrollable_frame, bg=bg_color, relief=tk.RAISED, bd=2)
        main_container.pack(expand=True, fill="both", padx=15, pady=15)
        
        tk.Label(main_container, text="Background Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        bg_color_entry = tk.Entry(main_container, width=30)
        bg_color_entry.insert(0, bg_color)
        bg_color_entry.pack(anchor="w", padx=10, pady=(0, 2))
        
        tk.Label(main_container, text="Button Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        btn_color_entry = tk.Entry(main_container, width=30)
        btn_color_entry.insert(0, btn_color)
        btn_color_entry.pack(anchor="w", padx=10, pady=(0, 2))
        
        tk.Label(main_container, text="Font Color:", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        font_color_entry = tk.Entry(main_container, width=30)
        font_color_entry.insert(0, font_color)
        font_color_entry.pack(anchor="w", padx=10, pady=(0, 8))
        
        shuffle_var = tk.BooleanVar(value=self.config["shuffle"])
        shuffle_check = tk.Checkbutton(main_container, variable=shuffle_var,
                                      text="Shuffle Playback",
                                      bg=bg_color, fg=font_color,
                                      selectcolor=btn_color,
                                      activebackground=bg_color, activeforeground=font_color)
        shuffle_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        pinned_var = tk.BooleanVar(value=self.config["pinned"])
        pinned_check = tk.Checkbutton(main_container, variable=pinned_var,
                                      text="Always on Top",
                                      bg=bg_color, fg=font_color,
                                      selectcolor=btn_color,
                                      activebackground=bg_color, activeforeground=font_color)
        pinned_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        show_titlebar_var = tk.BooleanVar(value=self.config["show_titlebar"])
        show_titlebar_check = tk.Checkbutton(main_container, variable=show_titlebar_var,
                                            text="Show Titlebar & Border",
                                            bg=bg_color, fg=font_color,
                                            selectcolor=btn_color,
                                            activebackground=bg_color, activeforeground=font_color)
        show_titlebar_check.pack(anchor="w", padx=10, pady=(0, 2))
        
        resizable_var = tk.BooleanVar(value=self.config["resizable"])
        resizable_check = tk.Checkbutton(main_container, variable=resizable_var,
                                         text="Resizable Window",
                                         bg=bg_color, fg=font_color,
                                         selectcolor=btn_color,
                                         activebackground=bg_color, activeforeground=font_color)
        resizable_check.pack(anchor="w", padx=10, pady=(0, 8))
        
        tk.Label(main_container, text="Opacity (%):", bg=bg_color, fg=font_color).pack(anchor="w", padx=10, pady=(2, 0))
        opacity_scale = tk.Scale(main_container, from_=30, to=100, orient=tk.HORIZONTAL,
                                bg=bg_color, fg=font_color,
                                highlightthickness=0,
                                activebackground=bg_color, troughcolor=btn_color)
        opacity_scale.set(self.config["opacity"])
        opacity_scale.pack(anchor="w", padx=10, pady=(0, 8))
        
        refresh_btn = tk.Button(main_container, text="Refresh Playlists",
                               bg=btn_color, fg=font_color, relief=tk.FLAT,
                               command=self.refresh_playlists)
        refresh_btn.pack(anchor="w", padx=10, pady=(0, 8))
        
        button_frame = tk.Frame(main_container, bg=bg_color)
        button_frame.pack(pady=(0, 10))
        
        def save_colors():
            self.config["bg_color"] = bg_color_entry.get()
            self.config["btn_color"] = btn_color_entry.get()
            self.config["font_color"] = font_color_entry.get()
            self.config["shuffle"] = shuffle_var.get()
            self.config["pinned"] = pinned_var.get()
            self.config["show_titlebar"] = show_titlebar_var.get()
            self.config["opacity"] = opacity_scale.get()
            self.config["resizable"] = resizable_var.get()
            self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
            if self.config["pinned"]:
                self.root.lift()
            save_config(self.config)
            self.apply_settings()
            options_window.destroy()
        
        def reset_to_default():
            self.config["bg_color"] = "#000000"
            self.config["btn_color"] = "#333333"
            self.config["font_color"] = "#FFFFFF"
            self.config["shuffle"] = True
            self.config["pinned"] = True
            self.config["show_titlebar"] = True
            self.config["opacity"] = 100
            self.config["resizable"] = True
            bg_color_entry.delete(0, tk.END)
            bg_color_entry.insert(0, self.config["bg_color"])
            btn_color_entry.delete(0, tk.END)
            btn_color_entry.insert(0, self.config["btn_color"])
            font_color_entry.delete(0, tk.END)
            font_color_entry.insert(0, self.config["font_color"])
            shuffle_var.set(self.config["shuffle"])
            pinned_var.set(self.config["pinned"])
            show_titlebar_var.set(self.config["show_titlebar"])
            opacity_scale.set(self.config["opacity"])
            resizable_var.set(self.config["resizable"])
            self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
            if self.config["pinned"]:
                self.root.lift()
            save_config(self.config)
            self.apply_settings()
        
        reset_btn = tk.Button(button_frame, text="Reset", command=reset_to_default,
                            bg=btn_color, fg=font_color, relief=tk.RAISED, bd=2)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = tk.Button(button_frame, text="Save", command=save_colors,
                           bg=btn_color, fg=font_color, relief=tk.RAISED, bd=2)
        save_btn.pack(side=tk.LEFT, padx=5)
    
    def open_playlist_window(self):
        playlist_window = tk.Toplevel(self.root)
        playlist_window.title("Seleccionar fuente")
        playlist_window.geometry("560x540")
        playlist_window.configure(bg=self.config["bg_color"])
        playlist_window.transient(self.root)
        playlist_window.grab_set()
        playlist_window.resizable(True, True)
        
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        main_frame = tk.Frame(playlist_window, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        view_mode = {"mode": "radio" if self.source_mode == "radio" else "local",
                     "online": [],
                     "search_id": 0}
        
        tk.Label(
            main_frame,
            text="Fuente de reproducción:",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9)
        ).pack(anchor="w")
        
        source_var = tk.StringVar(
            value="Emisoras de radio" if view_mode["mode"] == "radio" else "Playlists locales"
        )
        source_combo = ttk.Combobox(main_frame, textvariable=source_var,
                                   values=["Playlists locales", "Emisoras de radio"],
                                   state="readonly", width=40)
        source_combo.pack(fill=tk.X, pady=(0, 10))
        
        local_frame = tk.Frame(main_frame, bg=bg_color)
        local_frame.pack(fill=tk.X)
        
        radio_frame = tk.Frame(main_frame, bg=bg_color)
        
        playlist_label = tk.Label(
            local_frame,
            text="Seleccionar Playlist:",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9)
        )
        playlist_label.pack(anchor="w")
        
        playlist_var = tk.StringVar(value=self.current_playlist_name if self.current_playlist_name else "")
        playlist_combo = ttk.Combobox(local_frame, textvariable=playlist_var,
                                     values=self.playlist_names,
                                     state="readonly",
                                     width=40)
        playlist_combo.pack(fill=tk.X, pady=(0, 10))
        
        def on_playlist_change(event=None):
            new_playlist = playlist_var.get()
            if new_playlist and new_playlist != self.current_playlist_name:
                self.current_playlist_name = new_playlist
                self.config["playlist"] = self.current_playlist_name
                self.current_index = 0
                self._load_current_playlist()
                save_config(self.config)
                info_label.config(text=f"Playlist: {self.current_playlist_name} ({len(self.current_playlist_files)} canciones)")
                update_song_list()
        
        playlist_combo.bind("<<ComboboxSelected>>", on_playlist_change)
        
        info_label = tk.Label(
            local_frame,
            text=f"Playlist: {self.current_playlist_name or 'No playlist'} ({len(self.current_playlist_files)} canciones)",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 10, "bold")
        )
        info_label.pack(pady=(0, 10))
        
        search_label = tk.Label(
            local_frame,
            text="Buscar canción:",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9)
        )
        search_label.pack(anchor="w")
        
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            local_frame,
            textvariable=search_var,
            bg=btn_color,
            fg=font_color,
            insertbackground=font_color,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=0,
            font=("Arial", 9)
        )
        search_entry.pack(fill=tk.X, pady=(5, 10))
        
        # ---------------- Panel de radio online ----------------
        favorites = load_radio_favorites()
        catalog = get_radio_stations()
        genre_var = tk.StringVar(value="Todos")
        
        radio_search_var = tk.StringVar()
        
        tk.Label(
            radio_frame,
            text="Buscar emisión (nombre, país o género):",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 9)
        ).pack(anchor="w")
        
        radio_search_entry = tk.Entry(
            radio_frame,
            textvariable=radio_search_var,
            bg=btn_color,
            fg=font_color,
            insertbackground=font_color,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=0,
            font=("Arial", 9)
        )
        radio_search_entry.pack(fill=tk.X, pady=(5, 8))
        
        radio_controls = tk.Frame(radio_frame, bg=bg_color)
        radio_controls.pack(fill=tk.X)
        
        genre_combo = ttk.Combobox(radio_controls, textvariable=genre_var,
                                   values=get_radio_genres(catalog),
                                   state="readonly", width=16)
        genre_combo.pack(side=tk.LEFT)
        genre_combo.bind("<<ComboboxSelected>>", lambda e: update_song_list())
        
        radio_info_label = tk.Label(
            radio_frame,
            text="",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 10, "bold"),
            wraplength=520,
            justify=tk.LEFT
        )
        radio_info_label.pack(pady=(8, 4))
        
        radio_buttons = tk.Frame(radio_frame, bg=bg_color)
        radio_buttons.pack(fill=tk.X, pady=(0, 8))
        
        def small_button(parent, text, command, fg_color=None):
            return tk.Button(
                parent, text=text, command=command,
                bg=btn_color, fg=fg_color or font_color,
                activebackground=btn_color, activeforeground=fg_color or font_color,
                relief=tk.FLAT, font=("Arial", 8), bd=0, padx=4, pady=2
            )
        
        list_frame = tk.Frame(main_frame, bg=btn_color, relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        song_listbox = tk.Listbox(
            list_frame,
            bg=btn_color,
            fg=font_color,
            font=("Arial", 9),
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            activestyle=tk.NONE,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT
        )
        song_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=song_listbox.yview)
        
        def get_radio_results():
            """Emisoras visibles: resultados online si hay, o catalogo + favoritas."""
            term = radio_search_var.get().strip().lower()
            genre = genre_var.get()
            if view_mode["online"]:
                pool = list(view_mode["online"])
            else:
                pool = list(catalog)
                known = {st["url"] for st in catalog}
                for fav in favorites["favoritas"]:
                    if fav["url"] not in known:
                        pool.append(fav)
                        known.add(fav["url"])
            results = []
            for st in pool:
                if genre != "Todos" and not matches_genre(st, genre):
                    continue
                if term:
                    haystack = f"{st.get('name','')} {st.get('genre','')} {st.get('country','')}".lower()
                    if term not in haystack:
                        continue
                results.append(st)
            return results
        
        def refresh_genre_filter():
            """Anade al filtro los generos nuevos que traiga la busqueda online."""
            current = genre_var.get()
            values = get_radio_genres(catalog + view_mode["online"] + favorites["favoritas"])
            genre_combo.config(values=values)
            if current not in values:
                genre_var.set("Todos")
        
        def station_display(st, index):
            fav = "★ " if any(f["url"] == st["url"] for f in favorites["favoritas"]) else ""
            origin = RADIO_ONLINE_LABEL if st.get("_online") else ""
            return f"{fav}{index:2d}. {st['name']} — {st.get('genre','')} · {st.get('country','')} {origin}".strip()
        
        def update_song_list(search_term=None):
            song_listbox.delete(0, tk.END)
            self.song_paths = []
            self.station_list = []
            
            if view_mode["mode"] == "radio":
                results = get_radio_results()
                for idx, st in enumerate(results, start=1):
                    song_listbox.insert(tk.END, station_display(st, idx))
                    self.station_list.append(st)
                current = (self.current_station or {}).get("name")
                if current:
                    radio_info_label.config(text=f"En directo: {current} ({len(results)} en la lista)")
                else:
                    radio_info_label.config(text=f"{len(results)} emisoras disponibles")
                return
            
            songs_to_show = []
            if search_term:
                search_term_lower = search_term.lower()
                for file_path in self.current_playlist_files:
                    filename = os.path.basename(file_path)
                    if search_term_lower in filename.lower():
                        songs_to_show.append(file_path)
            else:
                songs_to_show = self.current_playlist_files
            
            for i, file_path in enumerate(songs_to_show):
                filename = os.path.basename(file_path)
                if file_path in self.current_playlist_files:
                    index_in_playlist = self.current_playlist_files.index(file_path)
                    display_text = f"{index_in_playlist + 1:2d}. {filename}"
                else:
                    display_text = filename
                song_listbox.insert(tk.END, display_text)
                self.song_paths.append(file_path)
        
        def on_search_change(*args):
            if view_mode["mode"] == "local":
                update_song_list(search_var.get())
        
        search_var.trace('w', on_search_change)
        
        def on_radio_search_change(*args):
            if view_mode["mode"] == "radio":
                update_song_list()
        
        radio_search_var.trace('w', on_radio_search_change)
        
        def window_alive():
            try:
                return playlist_window.winfo_exists()
            except tk.TclError:
                return False
        
        def search_online():
            term = radio_search_var.get().strip()
            genre = genre_var.get()
            if not term and genre == "Todos":
                radio_info_label.config(text="Escribe algo para buscar o elige un género")
                return
            radio_info_label.config(text="Buscando emisoras online...")
            song_listbox.delete(0, tk.END)
            self.station_list = []
            
            # Descarta cualquier busqueda anterior para que no pise estos resultados
            view_mode["search_id"] = view_mode.get("search_id", 0) + 1
            search_id = view_mode["search_id"]
            results = queue.Queue()
            
            def worker():
                try:
                    found = search_radio_online(term, genre)
                    for st in found:
                        st["_online"] = True
                    results.put(("ok", found))
                except Exception as e:
                    results.put(("error", str(e)))
            
            def poll():
                # Se ejecuta en el hilo principal: nunca tocar la UI desde el worker
                try:
                    status, payload = results.get_nowait()
                except queue.Empty:
                    if not window_alive():
                        return
                    try:
                        playlist_window.after(150, poll)
                    except tk.TclError:
                        pass
                    return
                if not window_alive():
                    return
                if search_id != view_mode.get("search_id"):
                    return
                if status == "error":
                    view_mode["online"] = []
                    radio_info_label.config(text=f"Error: {payload}")
                    return
                view_mode["online"] = payload
                refresh_genre_filter()
                update_song_list()
                if payload:
                    radio_info_label.config(text=f"{len(payload)} resultados online de Radio Browser")
                else:
                    radio_info_label.config(text="Sin resultados online")
            
            threading.Thread(target=worker, daemon=True).start()
            playlist_window.after(150, poll)
        
        def add_selected_favorite():
            nonlocal favorites
            sel = song_listbox.curselection()
            if not sel or view_mode["mode"] != "radio":
                return
            idx = sel[0]
            if idx >= len(self.station_list):
                return
            st = self.station_list[idx]
            clean = {k: v for k, v in st.items() if k != "_online"}
            if add_favorite(clean):
                favorites = load_radio_favorites()
                update_song_list()
                radio_info_label.config(text=f"★ {st['name']} añadida a tus emisoras")
            else:
                radio_info_label.config(text=f"★ {st['name']} ya estaba en tu lista")
        
        def remove_selected_favorite():
            nonlocal favorites
            sel = song_listbox.curselection()
            if not sel or view_mode["mode"] != "radio":
                return
            idx = sel[0]
            if idx >= len(self.station_list):
                return
            st = self.station_list[idx]
            clean = {k: v for k, v in st.items() if k != "_online"}
            if remove_favorite(clean):
                favorites = load_radio_favorites()
                update_song_list()
                radio_info_label.config(text=f"{st['name']} quitada de tu lista")
            else:
                radio_info_label.config(text=f"{st['name']} no estaba en tu lista")
        
        def add_custom_station():
            win = tk.Toplevel(playlist_window)
            win.title("Añadir emisión")
            win.geometry("420x300")
            win.configure(bg=bg_color)
            win.transient(playlist_window)
            win.grab_set()
            
            tk.Label(win, text="Añadir una emisión por URL", bg=bg_color,
                     fg=font_color, font=("Arial", 10, "bold")).pack(pady=(12, 8))
            
            fields = {}
            for key, label in (("name", "Nombre:"), ("url", "URL del stream:"),
                               ("genre", "Género (opcional):"), ("country", "País (opcional):")):
                tk.Label(win, text=label, bg=bg_color, fg=font_color,
                         font=("Arial", 9)).pack(anchor="w", padx=15)
                entry = tk.Entry(win, bg=btn_color, fg=font_color, insertbackground=font_color,
                                 relief=tk.SOLID, bd=1, highlightthickness=0, font=("Arial", 9))
                entry.pack(fill=tk.X, padx=15, pady=(0, 6))
                fields[key] = entry
            
            def save_custom():
                nonlocal favorites
                st = {
                    "name": fields["name"].get().strip(),
                    "url": fields["url"].get().strip(),
                    "genre": fields["genre"].get().strip() or "Varios",
                    "country": fields["country"].get().strip() or "Internacional",
                }
                if not st["name"] or not st["url"].startswith(("http://", "https://")):
                    messagebox.showerror("Error", "Nombre y URL válida (http/https) son obligatorios",
                                         parent=win)
                    return
                added = add_favorite(st)
                favorites = load_radio_favorites()
                win.destroy()
                view_mode["online"] = []
                refresh_genre_filter()
                update_song_list()
                radio_info_label.config(
                    text=f"★ {st['name']} añadida a tus emisoras" if added
                    else f"★ {st['name']} ya estaba en tu lista")
            
            tk.Button(win, text="Guardar", command=save_custom, bg=btn_color,
                      fg=font_color, relief=tk.RAISED, bd=2).pack(pady=8)
        
        small_button(radio_buttons, "🔍 Buscar online", search_online).pack(side=tk.LEFT, padx=(0, 4))
        small_button(radio_buttons, "★ Añadir a mi lista", add_selected_favorite).pack(side=tk.LEFT, padx=4)
        small_button(radio_buttons, "− Quitar", remove_selected_favorite).pack(side=tk.LEFT, padx=4)
        small_button(radio_buttons, "＋ Añadir por URL", add_custom_station).pack(side=tk.LEFT, padx=4)
        
        def on_song_select(event):
            if not song_listbox.curselection():
                return
            selected_index = song_listbox.curselection()[0]
            
            if view_mode["mode"] == "radio":
                if selected_index < len(self.station_list):
                    station = dict(self.station_list[selected_index])
                    station.pop("_online", None)
                    self.play_radio_station(station)
                    self.update_station_label()
                    playlist_window.destroy()
                return
            
            if selected_index < len(self.song_paths):
                file_path = self.song_paths[selected_index]
                try:
                    song_index = self.current_playlist_files.index(file_path)
                    self.play_song_at_index(song_index)
                    playlist_window.destroy()
                except ValueError:
                    pass
        
        song_listbox.bind('<Double-Button-1>', on_song_select)
        
        def on_source_change(event=None):
            view_mode["mode"] = "radio" if source_var.get() == "Emisoras de radio" else "local"
            view_mode["online"] = []
            if view_mode["mode"] == "radio":
                local_frame.pack_forget()
                radio_frame.pack(fill=tk.X, before=list_frame)
                radio_search_entry.focus_set()
            else:
                radio_frame.pack_forget()
                local_frame.pack(fill=tk.X, before=list_frame)
                search_entry.focus_set()
            update_song_list()
        
        source_combo.bind("<<ComboboxSelected>>", on_source_change)
        
        def on_key_press(event):
            if event.keysym == 'Escape':
                playlist_window.destroy()
            elif event.keysym == 'Return' and song_listbox.curselection():
                on_song_select(None)
        
        playlist_window.bind('<KeyPress>', on_key_press)
        
        close_btn = tk.Button(
            main_frame,
            text="Cerrar (ESC)",
            command=playlist_window.destroy,
            bg=btn_color,
            fg=font_color,
            activebackground=btn_color,
            activeforeground=font_color,
            relief=tk.FLAT,
            font=("Arial", 9),
            bd=0
        )
        close_btn.pack(pady=(10, 0))
        
        if view_mode["mode"] == "radio":
            on_source_change()
        else:
            update_song_list()
            search_entry.focus_set()
    
    def apply_colors(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        self.root.configure(bg=bg_color)
        self.song_label.configure(bg=bg_color, fg=font_color)
        self.time_label.configure(bg=bg_color, fg=font_color)
        self.play_btn.configure(bg=btn_color, fg=font_color)
        self.prev_btn.configure(bg=btn_color, fg=font_color)
        self.next_btn.configure(bg=btn_color, fg=font_color)
        self.options_btn.configure(bg=btn_color, fg=font_color)
        self.volume_up_btn.configure(bg=btn_color, fg=font_color)
        self.volume_down_btn.configure(bg=btn_color, fg=font_color)
        self.drag_btn.configure(bg=bg_color, fg=font_color)
        self.close_btn.configure(bg=bg_color, fg=font_color)
    
    def apply_settings(self):
        bg_color = self.config["bg_color"]
        btn_color = self.config["btn_color"]
        font_color = self.config["font_color"]
        
        self.root.configure(bg=bg_color)
        self.song_label.configure(bg=bg_color, fg=font_color)
        self.time_label.configure(bg=bg_color, fg=font_color)
        self.play_btn.configure(bg=btn_color, fg=font_color)
        self.prev_btn.configure(bg=btn_color, fg=font_color)
        self.next_btn.configure(bg=btn_color, fg=font_color)
        self.options_btn.configure(bg=btn_color, fg=font_color)
        self.volume_up_btn.configure(bg=btn_color, fg=font_color)
        self.volume_down_btn.configure(bg=btn_color, fg=font_color)
        self.drag_btn.configure(bg=btn_color, fg=font_color)
        self.playlist_btn.configure(bg=btn_color, fg=font_color)
        self.close_btn.configure(bg=btn_color, fg=font_color)
        
        if self.config["show_titlebar"]:
            self.root.overrideredirect(False)
        else:
            self.root.overrideredirect(True)
        
        self.root.attributes("-alpha", self.config["opacity"] / 100.0)
        
        if self.config["resizable"]:
            self.root.resizable(True, True)
        else:
            self.root.resizable(False, False)
        
        self.root.attributes("-topmost", 1 if self.config["pinned"] else 0)
        if self.config["pinned"]:
            self.root.lift()
    
    def toggle_play(self):
        if self.player is not None and self.player.is_playing():
            self.player.pause()
            self.play_btn.config(text="▶")
        else:
            if self.player is not None:
                self.player.play()
                self.play_btn.config(text="⏸")
    
    def next_song(self):
        if self.source_mode == "radio":
            self.switch_station(1)
            return
        if not self.current_playlist_files:
            return
        if self.config["shuffle"]:
            self.current_index = random.randrange(len(self.current_playlist_files))
        else:
            self.current_index = (self.current_index + 1) % len(self.current_playlist_files)
        self.play_song_at_index(self.current_index)
    
    def prev_song(self):
        if self.source_mode == "radio":
            self.switch_station(-1)
            return
        if not self.current_playlist_files:
            return
        if self.config["shuffle"]:
            self.current_index = random.randrange(len(self.current_playlist_files))
        else:
            self.current_index = (self.current_index - 1) % len(self.current_playlist_files)
        self.play_song_at_index(self.current_index)
    
    def play_radio_station(self, station):
        """Reproduce una estacion de radio online y la guarda para la proxima vez."""
        if not station or not station.get("url"):
            return
        self.source_mode = "radio"
        self.current_station = station
        
        if vlc is not None and self.instance is not None and self.player is not None:
            try:
                media = self.instance.media_new(station["url"])
                self.player.set_media(media)
                self.player.play()
                self.player.audio_set_volume(self.config["volume"])
            except Exception as e:
                print(f"Error playing radio {station['url']}: {e}")
                return
        
        self.song_label.config(text=self._station_title())
        self.time_label.config(text="EN VIVO")
        self.play_btn.config(text="⏸")
        
        self.config["last_source"] = "radio"
        save_config(self.config)
        remember_last_station(station)
    
    def switch_station(self, step):
        """Cambia a la estacion siguiente/anterior dentro de la lista mostrada."""
        if not self.station_list:
            # La ventana puede estar cerrada: usamos el catalogo completo
            self.station_list = get_radio_stations()
        if not self.station_list:
            return
        current_url = (self.current_station or {}).get("url")
        index = 0
        for i, st in enumerate(self.station_list):
            if st.get("url") == current_url:
                index = i
                break
        else:
            index = -1 if step > 0 else 0
        nxt = (index + step) % len(self.station_list)
        self.play_radio_station(self.station_list[nxt])
        self.update_station_label()
    
    def _station_title(self):
        """Titulo de la barra: nombre de la radio y posicion en la lista."""
        name = (self.current_station or {}).get("name", "")
        if not self.station_list:
            return f"📻 {name}"
        index = 0
        for i, st in enumerate(self.station_list):
            if st.get("url") == (self.current_station or {}).get("url"):
                index = i
                break
        return f"📻 {name}  ({index + 1}/{len(self.station_list)})"
    
    def update_station_label(self):
        if self.source_mode != "radio" or not self.current_station:
            return
        self.song_label.config(text=self._station_title())
    
    def start_player_monitor(self):
        if self.player is None or self.player_monitor_running:
            return
        self.player_monitor_running = True
        self.player_monitor_thread = threading.Thread(target=self.monitor_player, daemon=True)
        self.player_monitor_thread.start()
    
    def start_time_monitor(self):
        if self.player is None or self.time_monitor_running:
            return
        self.time_monitor_running = True
        self.time_monitor_thread = threading.Thread(target=self.monitor_time, daemon=True)
        self.time_monitor_thread.start()
    
    def monitor_player(self):
        while self.player_monitor_running:
            try:
                if self.player is not None and self.player.is_playing():
                    time.sleep(0.5)
                else:
                    time.sleep(0.5)
                    if self.player is not None and not self.player.is_playing() and self.current_playlist_files and self.source_mode != "radio":
                        self.check_song_ended()
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1)
    
    def check_song_ended(self):
        try:
            if self.source_mode == "radio":
                return
            if self.player is not None and self.current_playlist_files:
                state = self.player.get_state()
                if state == vlc.State.Ended or state == vlc.State.NothingSpecial:
                    threading.Thread(target=self.next_song, daemon=True).start()
        except Exception as e:
            print(f"Error checking song end: {e}")
    
    def monitor_time(self):
        while self.time_monitor_running:
            try:
                if self.source_mode != "radio" and self.player is not None and self.current_playlist_files:
                    self.update_time_display()
                time.sleep(1)
            except Exception as e:
                print(f"Time monitor error: {e}")
                time.sleep(1)
    
    def update_time_display(self):
        try:
            if self.player is not None:
                current_time = self.player.get_time()
                time_str = self.format_time(current_time)
                self.time_label.config(text=time_str)
        except Exception as e:
            print(f"Error updating time display: {e}")
    
    def format_time(self, milliseconds):
        total_seconds = milliseconds // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def on_close(self, event=None):
        self.player_monitor_running = False
        self.time_monitor_running = False
        self.config["shuffle"] = self.config.get("shuffle", True)
        self.config["pinned"] = self.config.get("pinned", True)
        self.config["last_source"] = self.source_mode
        if self.source_mode == "radio" and self.current_station:
            remember_last_station(self.current_station)
        self.config["x"] = self.root.winfo_x()
        self.config["y"] = self.root.winfo_y()
        self.config["width"] = self.root.winfo_width()
        self.config["height"] = self.root.winfo_height()
        save_config(self.config)
        try:
            if self.player is not None:
                self.player.stop()
        except Exception:
            pass
        self.root.destroy()

def main():
    config = load_config()
    root = tk.Tk()
    root.title("Music Minimal Player")
    root.geometry(f"{config['width']}x{config['height']}+{config['x']}+{config['y']}")
    root.configure(bg=config["bg_color"])
    root.attributes("-topmost", config["pinned"])
    
    if config["show_titlebar"]:
        root.overrideredirect(False)
    else:
        root.overrideredirect(True)
    
    root.attributes("-alpha", config["opacity"] / 100.0)
    
    if config["resizable"]:
        root.resizable(True, True)
    else:
        root.resizable(False, False)
    
    app = MusicMinimalPlayer(root)
    
    root.mainloop()

if __name__ == "__main__":
    main()

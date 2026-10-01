# Music Minimal Player

A minimal and lightweight music player built with Python, tkinter, and VLC.

## Features

- Minimalist interface with all controls in one compact row
- Support for playlists from `~/Music` folder
- Subfolders are treated as separate playlists with parent folder prefix
- **Online radio: 192 curated stations included, no internet needed to browse them**
- **Search any station worldwide online via the Radio Browser catalogue**
- **Save your own stations to a personal list and mark favourites**
- **Restores the last radio you were listening to on the next launch**
- Shuffle playback mode
- Volume control with +/- buttons
- Display of current song title (from metadata or filename)
- Window position and size persistence
- Customizable colors (background, buttons, font)
- Always-on-top option
- Opacity control
- Time display showing current song position
- Draggable window with mouse
- Configuration persistence across sessions

## Requirements

- Python 3.7+
- VLC media player
  - Windows: [Download VLC 64-bit](https://get.videolan.org/vlc/3.0.18/win64/vlc-3.0.18-win64.exe)
  - Must match Python architecture (64-bit recommended)
- python-vlc library (auto-installed on first run)

## Installation

1. Install VLC media player if not already installed
2. Run the script:
   ```bash
   python reproductor.py
   ```
3. The script will automatically install python-vlc if needed

## Configuration

All settings are saved in `config.json` in the same directory as the script:

- `volume`: Initial volume level (0-100, default: 80)
- `shuffle`: Enable shuffle playback (default: true)
- `pinned`: Keep window always on top (default: true)
- `x`, `y`: Window position
- `width`, `height`: Window dimensions (default: 600x40)
- `bg_color`: Background color in hex (default: "#000000")
- `btn_color`: Button color in hex (default: "#333333")
- `font_color`: Font/text color in hex (default: "#FFFFFF")
- `playlist`: Last selected playlist
- `song_index`: Current song position in playlist
- `last_source`: What to play on launch: `local` or `radio` (default: local)
- `show_titlebar`: Show titlebar and border (default: true)
- `opacity`: Window opacity (0-100, default: 100)
- `resizable`: Allow window resizing (default: true)

## Usage

### Controls

- `◀` / `⏮`: Previous song
- `▶` / `⏸`: Play/Pause
- `▶` / `⏭`: Next song
- `+` / `-`: Volume up/down (10% increments)
- `::`: Drag to move window
- `⚙`: Open configuration options
- `×`: Close player

### Radio Online

Click `☰` and switch **Fuente de reproducción** to **Emisoras de radio**.

- **192 curated stations** ship with the player (verified working), sorted by genre:
  Reggaeton, Reggae, Salsa, Bachata, Cumbia, Latina, Tango, Flamenco, Rock, Metal,
  Punk, Indie, Jazz, Blues, Soul, R&B, Hip-Hop, Pop, Retro/Oldies, Folk, Clásica,
  Chillout, Ambient, House, Techno, Dance, Electrónica, K-Pop, Noticias, Deportes,
  Conversación, Religiosa, Infantil. Mostly Spanish and Latin stations.
- **Search box** filters the included catalogue instantly by name, country or genre.
- **`🔍 Buscar online`** queries the public [Radio Browser](https://www.radio-browser.info)
  API for stations anywhere in the world. Results are marked `[online]`.
  Needs an internet connection; the included catalogue does not.
- **`★ Añadir a mi lista`** saves the selected station (online or not) to your
  personal list. Favourites are marked with `★` in the list.
- **`− Quitar`** removes it from your list.
- **`＋ Añadir por URL`** adds any stream URL manually.
- Double-click or press `Enter` to start a station.

While a radio is playing the time indicator shows `EN VIVO`, and `◀`/`▶` move to
the previous/next station in the list instead of skipping tracks.

### Radio Persistence

Your stations and the last station played are stored in `radio_favoritas.json`
(next to the script), separate from `config.json`:

```json
{
  "favoritas": [
    {"name": "La Grosse Radio Reggae", "url": "https://...", "genre": "Reggae", "country": "France"}
  ],
  "ultima": {"name": "La Grosse Radio Reggae", "url": "https://...", "genre": "Reggae", "country": "France"}
}
```

- `favoritas`: your personal list, editable by hand
- `ultima`: the station that was playing, restored automatically on the next launch

Setting `last_source` to `radio` in `config.json` forces the player to start with
the saved station. Your favourite is always remembered, even if you never add it
to your list.

### Playlist Structure

The player scans `~/Music` folder for playlists:

- Each direct folder in `Music` is a playlist
- Each subfolder (2 levels deep) is a playlist with parent folder prefix
  - Example: `Rock/Classic`, `Rock/Modern`, `Jazz/Smooth`

Example structure:
```
~/Music/
├── Rock/
│   ├── Classic/
│   │   ├── song1.mp3
│   │   └── song2.mp3
│   └── Modern/
│       ├── song3.mp3
│       └── song4.mp3
└── Jazz/
    ├── song5.mp3
    └── song6.mp3
```

Playlists:
- `Rock` (songs in Rock/ folder directly)
- `Rock/Classic` (songs in Rock/Classic/)
- `Rock/Modern` (songs in Rock/Modern/)
- `Jazz` (songs in Jazz/)

### Configuration Options

Click `⚙` to open the configuration dialog:

- **Background Color**: Set window background color (hex format)
- **Button Color**: Set button color (hex format)
- **Font Color**: Set text color (hex format)
- **Shuffle Playback**: Enable/disable shuffle
- **Always on Top**: Keep window above other applications
- **Show Titlebar & Border**: Toggle titlebar visibility
- **Opacity**: Set window transparency (0-100%)
- **Resizable Window**: Enable/disable window resizing
- **Refresh Playlists**: Scan for new playlists
- **Reset**: Restore default settings

### Keyboard Controls

- Click and drag `::` button to move window

### Playback Modes

- **Sequential**: Plays songs in order from current playlist
- **Shuffle**: Plays songs in random order from current playlist

## File Formats Supported

- MP3
- WAV
- FLAC
- AAC
- M4A
- OGG

## Metadata Support

The player attempts to read the song title from embedded metadata. If no title is found, it displays the filename.

## Window Management

- Position and size are automatically saved on close
- Last selected playlist is restored on launch
- Last song position in playlist is remembered
- Window can be moved by clicking and dragging the `::` button
- Always-on-top option keeps player visible

## Troubleshooting

### VLC not found error

If you see:
```
Error: Python 64-bit detected but VLC 32-bit found
```

**Solution**: Install VLC 64-bit
1. Download from: https://get.videolan.org/vlc/3.0.18/win64/vlc-3.0.18-win64.exe
2. Uninstall any existing VLC
3. Install the 64-bit version

### python-vlc not found error

The script automatically installs `python-vlc` on first run if not present.

### No playlists found

Ensure you have audio files in `~/Music` folder in supported formats:
- Place files directly in `~/Music/PlaylistName/`
- Or create subfolders like `~/Music/PlaylistName/SubFolder/`

### Window not opening

If the window doesn't appear:
1. Check that VLC is installed correctly
2. Verify Python and VLC architecture match (both 64-bit)
3. Check for error messages in the terminal

### Player stops after one song

This can happen if:
1. The playlist has only one song
2. There's an issue with the next file format
3. VLC is not properly configured

**Solution**: Try refreshing playlists and ensure files are in supported formats

## Development

### Project Structure

- `reproductor.py`: Main player script
- `config.json`: User configuration (auto-generated)
- `radio_favoritas.json`: Your saved radio stations (auto-generated)

### Key Classes

- `MusicMinimalPlayer`: Main player class handling UI and playback logic

### Main Methods

- `load_config()`: Load user preferences
- `save_config()`: Save user preferences
- `scan_playlists()`: Scan Music folder for playlists
- `play_song_at_index()`: Play a specific song from playlist
- `play_radio_station()`: Play an online radio station and remember it
- `switch_station()`: Previous/next station when playing radio
- `search_radio_online()`: Query the Radio Browser catalogue (runs in a thread)
- `add_favorite()` / `remove_favorite()`: Manage `radio_favoritas.json`
- `next_song()`: Advance to next song (shuffle or sequential)
- `prev_song()`: Go to previous song
- `toggle_play()`: Toggle play/pause state
- `monitor_player()`: Monitor playback state
- `update_time_display()`: Update time label

## License

This project is provided as-is for personal use.

## Credits

Built with Python, tkinter, and python-vlc.

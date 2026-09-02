# LET IT DIE Offline Safe Content Installer

Source code for version 3.53 of the Windows offline-content installer.

The tool adds reversible offline routes for seven retained collaboration
blueprints and places 36 retained premium decals into the normal Mushroom Club
pool. It also installs the verified UI artwork for all 35 supported
collaboration decals. It does not edit save files or include runtime combat
cheats.

## Version 3.53 highlights

- Added the Gravity Rush 2 decals Apple, Dusty, and Panther Mode.
- Updated the collaboration decal UI artwork used by the Mushroom Club,
  inventory, and HUD.
- Includes 105 native-LZO artwork packages covering full, medium, and small UI
  sizes for 35 collaboration decals.
- Preserves the seven safe blueprint quest routes.
- Keeps decals pool-only; no decal giveaway quests are added.
- Removed the experimental asset-swapped blueprint content while it is being
  developed separately.

See [CHANGELOG.md](CHANGELOG.md) for the release notes and
[USER_GUIDE.txt](USER_GUIDE.txt) for the complete content list and usage
instructions.

## Safety design

- Refuses to patch while `BrgGame-Steam.exe` is running.
- Works on a temporary database copy and runs SQLite `integrity_check` before
  replacement.
- Records a verified clean baseline and creates timestamped backups.
- Uses hash guards for artwork installation and rollback.
- Does not edit player save files or contain runtime combat cheats.

## Running from source

Requirements:

- Windows
- Python 3.12 or later
- A legally obtained offline installation of LET IT DIE

Run:

```powershell
python .\LetItDieOfflineContentPatcher.pyw
```

The application uses only the Python standard library. Building the standalone
executable additionally requires PyInstaller:

```powershell
python -m pip install -r requirements-dev.txt
pyinstaller .\LetItDieOfflineSafeContentInstaller-v3.53.spec
```

## Artwork assets

`assets/collab_decal_art` contains 105 verified native-LZO packages.
`manifest.json` records every filename, size, and SHA-256 hash.

Do not publish `masters.db`, save files, or personal backups in issues or pull
requests. Rights to LET IT DIE and all collaboration artwork remain with their
respective owners.

## Testing

Set `LID_MASTERS_DB` to a copy of the installed `masters.db`, then run:

```powershell
$env:LID_MASTERS_DB = 'D:\path\to\masters.db'
python .\test_content_patcher.py
```

## Credits

Special thanks to **ZeroUnderOne** for the help and support.

## Legal

This is an unofficial community tool and is not affiliated with Supertrick
Games, GungHo Online Entertainment, or Epic Games. LET IT DIE and associated
artwork remain the property of their respective owners. No license is granted
for third-party game assets.

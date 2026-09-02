# LET IT DIE Offline Safe Content Installer

Source code for the Windows offline-content installer version 3.1.

The tool adds reversible, offline database routes for seven retained collaboration blueprints and places 33 retained premium decals into the normal offline Mushroom Club pool. It also contains guarded install/restore support for collaboration decal artwork packages.

## Safety design

- Refuses to patch while `BrgGame-Steam.exe` is running.
- Works on a temporary database copy and runs SQLite `integrity_check` before replacement.
- Records a verified clean baseline and creates timestamped backups.
- Uses hash guards for artwork installation and rollback.
- Does not edit player save files or contain runtime combat cheats.

See [USER_GUIDE.txt](USER_GUIDE.txt) for the end-user instructions and content list.

## Running from source

Requirements:

- Windows
- Python 3.12 or later
- A legally obtained offline installation of LET IT DIE

Run:

```powershell
python .\LetItDieOfflineContentPatcher.pyw
```

The Python application uses only the standard library. Building the standalone executable additionally requires PyInstaller:

```powershell
python -m pip install -r requirements-dev.txt
pyinstaller .\LetItDieOfflineSafeContentInstaller-v3.1.spec
```

## Artwork assets

The repository mirrors the original self-contained v3.1 build and includes the 63 small collaboration artwork packages expected by the installer. `assets/collab_decal_art/manifest.json` records their filenames, sizes, and SHA-256 hashes.

Do not publish `masters.db`, saves, or personal backups in issues or pull requests. Rights to LET IT DIE and collaboration artwork remain with their respective owners.

## Testing

Set `LID_MASTERS_DB` to a copy of your installed `masters.db`, then run:

```powershell
$env:LID_MASTERS_DB = 'D:\path\to\masters.db'
python .\test_content_patcher.py
```

The full test verifies all 63 artwork packages described by the manifest.

## Legal

This is an unofficial community tool and is not affiliated with Supertrick Games, GungHo Online Entertainment, or Epic Games. LET IT DIE and associated artwork remain the property of their respective owners. No license is granted for third-party game assets.

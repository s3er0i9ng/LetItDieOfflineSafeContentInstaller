from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "LET IT DIE Offline Safe Content Installer"
APP_VERSION = "3.53"
GAME_PROCESS = "BrgGame-Steam.exe"
DB_RELATIVE = Path("BrgGame") / "Content" / "masters.db"
COOKED_RELATIVE = Path("BrgGame") / "CookedPCConsole"
ARTWORK_RELATIVE = Path("assets") / "collab_decal_art"
ARTWORK_PACKAGE_COUNT = 105
OFFLINE_GACHA_ID = "SKLGACH_NORMAL_OFFLINE"
ULTIMATE_FIGHTER_RETURN_ID = "SKL_FIGHTER_STUP_02_P"
POOL_ODDS_BY_RARITY = {1: 74, 2: 72, 3: 40, 4: 4, 5: 2}
QUEST_TEMPLATE = "KILL_PE_001"
QUEST_PARAMETER_TABLES = (
    "master_quest_condition_int",
    "master_quest_condition_float",
    "master_quest_condition_str",
    "master_quest_param_int",
    "master_quest_param_float",
    "master_quest_param_str",
    "master_quest_param_text",
    "master_quest_param_desc_text",
)
EXPECTED_TABLES = {
    "master_item",
    "master_part",
    "master_quest",
    "master_reward",
    "master_skill",
    "master_skillgacha",
    "master_skillgacha_odds",
}


@dataclass(frozen=True)
class RewardQuest:
    qid: str
    number: int
    reward_id: str
    target_id: str
    display_name: str


@dataclass(frozen=True)
class ContentCategory:
    key: str
    label: str
    reward_type: str
    quests: tuple[RewardQuest, ...]
    description: str


def generated_quests(prefix: str, reward_prefix: str, number: int, entries: tuple[tuple[str, str], ...]) -> tuple[RewardQuest, ...]:
    return tuple(
        RewardQuest(
            f"{prefix}_{index:02d}",
            number + index - 1,
            f"{reward_prefix}_{index:02d}",
            target_id,
            display_name,
        )
        for index, (target_id, display_name) in enumerate(entries, 1)
    )


PREVIOUS_BLUEPRINT_QUESTS = (
    RewardQuest("CODEX_COLLAB_BKATANA", 20001, "RWD_CODEX_BKATANA", "ITMP_ARM_WP001_0N1", "Beam Katana 1"),
    RewardQuest("CODEX_COLLAB_TRAVIS_HEAD", 20002, "RWD_CODEX_TRAVIS_HEAD", "ITMP_SPE_HEAD_015", "Travis' Sunglasses 1"),
    RewardQuest("CODEX_COLLAB_TRAVIS_BODY", 20003, "RWD_CODEX_TRAVIS_BODY", "ITMP_SPE_TOPS_015", "Travis' Jacket 1"),
    RewardQuest("CODEX_COLLAB_TRAVIS_LEGS", 20004, "RWD_CODEX_TRAVIS_LEGS", "ITMP_SPE_BTM_015", "Travis' Pants 1"),
    RewardQuest("CODEX_COLLAB_U3D", 20005, "RWD_CODEX_U3D", "ITMP_SPE_HEAD_017", "Ultra 3D Glasses"),
    RewardQuest("CODEX_COLLAB_U3DW", 20006, "RWD_CODEX_U3DW", "ITMP_SPE_HEAD_019", "Ultra 3D Glasses W1"),
)

SAFE_ADDITIONAL_BLUEPRINT_QUESTS = (
    RewardQuest("CODEX_BP_COLLAB_16", 20116, "RWD_CODEX_BP_COLLAB_16", "ITMP_SPE_HEAD_025", "Uncle-D2 Head 1"),
)
ALL_COLLAB_BLUEPRINT_QUESTS = PREVIOUS_BLUEPRINT_QUESTS + SAFE_ADDITIONAL_BLUEPRINT_QUESTS

COLLAB_DECALS = (
    ("SKL_ASSAULT_ATKUP_WOT_P", "INVADER"),
    ("SKL_BAD_GIRL_NMH_P", "BAD GIRL"),
    ("SKL_CON_SMITH_K7_P", "Con Smith"),
    ("SKL_COYOTE_SMITH_K7_P", "Coyote Smith"),
    ("SKL_DAN_SMITH_K7_P", "Dan Smith"),
    ("SKL_DEC_FIREELEC_WOT_P", "BILLOTTE'S MEDAL"),
    ("SKL_DESTROYMAN_NMH_P", "DESTROYMAN"),
    ("SKL_DOWN_ATKUP_WOT_P", "T95E2"),
    ("SKL_DR_PEACE_NMH_P", "DR. PEACE"),
    ("SKL_GARCIAN_SMITH_K7_P", "Garcian Smith"),
    ("SKL_GAUGEUP_REV_WOT_P", "Call for Vengeance"),
    ("SKL_GRAVITY_DROPKICK_P", "Kat"),
    ("SKL_GUN_BURST_WOT_P", "Tiger II"),
    ("SKL_HARMAN_SMITH_K7_P", "Harman Smith"),
    ("SKL_HENRY_NMH_P", "HENRY"),
    ("SKL_HOLLY_SUMMERS_NMH_P", "HOLLY SUMMERS"),
    ("SKL_HPCUREUP_03_P", "Apple"),
    ("SKL_HPUP_ATKUP_P", "Panther Mode"),
    ("SKL_HPUP_WOT_P", "World of Tanks"),
    ("SKL_IWAZARU_K7_P", "Iwazaru"),
    ("SKL_JEANE_NMH_P", "JEANE"),
    ("SKL_KAEDE_SMITH_K7_P", "KAEDE Smith"),
    ("SKL_KEVIN_SMITH_K7_P", "Kevin Smith"),
    ("SKL_LESS_DIFFUSION_WOT_P", "SHARPSHOOTER"),
    ("SKL_MASK_DE_SMITH_K7_P", "MASK De Smith"),
    ("SKL_NDFALL_AUSTEALTH_P", "Dusty"),
    ("SKL_NODMG_RANDOM_WOT_P", "STEEL WALL"),
    ("SKL_PATROL_WOT_P", "PATROL DUTY"),
    ("SKL_SAMANTHA_K7_P", "Samantha"),
    ("SKL_SHINOBU_NMH_P", "SHINOBU"),
    ("SKL_SPEED_BUSTER_NMH_P", "SPEED BUSTER"),
    ("SKL_SYLVIA_NMH_00_P", "Queen B"),
    ("SKL_SYLVIA_NMH_P", "SYLVIA CHRISTEL"),
    ("SKL_TRAVIS_NMH_P", "TRAVIS TOUCHDOWN"),
    ("SKL_ZEROPOS_SHOT_WOT_P", "Chi-Ha"),
)

ALL_COLLAB_DECAL_QUESTS = generated_quests(
    "CODEX_DECAL_COLLAB", "RWD_CODEX_DECAL_COLLAB", 21001, COLLAB_DECALS
)
DECAL_STEAM_COMPAT_IDS = tuple(
    quest.target_id
    for quest in ALL_COLLAB_DECAL_QUESTS
    if "_K7_" in quest.target_id or "_WOT_" in quest.target_id or quest.target_id == "SKL_GRAVITY_DROPKICK_P"
)
DECAL_STEAM_NUMBERS = {
    skill_id: 330 + index for index, skill_id in enumerate(DECAL_STEAM_COMPAT_IDS)
}
DECAL_STEAM_NUMBERS["SKL_NDFALL_AUSTEALTH_P"] = 351
DECAL_STEAM_NUMBERS["SKL_HPCUREUP_03_P"] = 352
DECAL_STEAM_NUMBERS["SKL_HPUP_ATKUP_P"] = 353
NMH_DECAL_QUESTS = tuple(quest for quest in ALL_COLLAB_DECAL_QUESTS if "_NMH" in quest.target_id)
KILLER7_DECAL_QUESTS = tuple(quest for quest in ALL_COLLAB_DECAL_QUESTS if "_K7" in quest.target_id)
WOT_DECAL_QUESTS = tuple(quest for quest in ALL_COLLAB_DECAL_QUESTS if "_WOT" in quest.target_id)
GRAVITY_RUSH_DECAL_QUESTS = tuple(
    quest for quest in ALL_COLLAB_DECAL_QUESTS if quest.target_id == "SKL_GRAVITY_DROPKICK_P"
)

LEGACY_CONTENT_CATEGORIES = (
    ContentCategory(
        "nmh_blueprints",
        "No More Heroes blueprints",
        "ITEM",
        PREVIOUS_BLUEPRINT_QUESTS[:4],
        "4 quests: Beam Katana and the Travis armor set.",
    ),
    ContentCategory(
        "nmh_decals_a",
        "No More Heroes decals A",
        "SKILL",
        NMH_DECAL_QUESTS[:10],
        "10 unavailable collaboration decal quests.",
    ),
    ContentCategory(
        "nmh_decals_b",
        "No More Heroes decals B",
        "SKILL",
        NMH_DECAL_QUESTS[10:],
        "1 remaining unavailable collaboration decal quest.",
    ),
    ContentCategory(
        "killer7_blueprints",
        "Killer7 blueprints",
        "ITEM",
        PREVIOUS_BLUEPRINT_QUESTS[4:],
        "2 quests: both retained Ultra 3D Glasses variants.",
    ),
    ContentCategory(
        "killer7_decals",
        "Killer7 decals",
        "SKILL",
        KILLER7_DECAL_QUESTS,
        "10 unavailable collaboration decal quests.",
    ),
    ContentCategory(
        "gravity_rush_decals",
        "Gravity Rush decal",
        "SKILL",
        GRAVITY_RUSH_DECAL_QUESTS,
        "1 unavailable Kat decal quest.",
    ),
    ContentCategory(
        "wot_decals",
        "World of Tanks decals",
        "SKILL",
        WOT_DECAL_QUESTS,
        "10 unavailable collaboration decal quests.",
    ),
    ContentCategory(
        "deathverse_blueprints",
        "Deathverse blueprint",
        "ITEM",
        SAFE_ADDITIONAL_BLUEPRINT_QUESTS,
        "1 quest: Uncle-D2 Head.",
    ),
)
CONTENT_CATEGORIES = tuple(category for category in LEGACY_CONTENT_CATEGORIES if category.reward_type == "ITEM")
BLUEPRINT_CATEGORIES = CONTENT_CATEGORIES
DECAL_CATEGORIES: tuple[ContentCategory, ...] = ()
TOTAL_REWARDS = sum(len(category.quests) for category in CONTENT_CATEGORIES)
TOTAL_BLUEPRINTS = len(ALL_COLLAB_BLUEPRINT_QUESTS)
TOTAL_DECALS = len(COLLAB_DECALS)
POOL_DECAL_IDS = tuple(quest.target_id for quest in ALL_COLLAB_DECAL_QUESTS) + (ULTIMATE_FIGHTER_RETURN_ID,)
TOTAL_POOL_DECALS = len(POOL_DECAL_IDS)

class DatabaseLockedError(OSError):
    pass


def local_app_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def app_data_dir() -> Path:
    path = local_app_data() / "LetItDieOfflineContentPatcher"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_dir() -> Path:
    path = app_data_dir() / "Backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path() -> Path:
    return app_data_dir() / "state.json"


def load_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"databases": {}}


def save_state(state: dict) -> None:
    temporary = state_path().with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temporary, state_path())


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parent


def artwork_asset_dir() -> Path:
    return resource_root() / ARTWORK_RELATIVE


def game_root_from_database(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.name.lower() != "masters.db" or resolved.parent.name.lower() != "content" or resolved.parent.parent.name.lower() != "brggame":
        raise ValueError("Select BrgGame\\Content\\masters.db from the LET IT DIE installation.")
    return resolved.parents[2]


def cooked_dir_from_database(path: Path) -> Path:
    return game_root_from_database(path) / COOKED_RELATIVE


def load_artwork_manifest(asset_dir: Path | None = None) -> tuple[dict, ...]:
    root = asset_dir or artwork_asset_dir()
    manifest_path = root / "manifest.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError) as exc:
        raise OSError(f"Collaboration artwork manifest is unavailable: {exc}") from exc
    if not isinstance(raw, list) or len(raw) != ARTWORK_PACKAGE_COUNT:
        raise OSError(f"Artwork bundle should contain {ARTWORK_PACKAGE_COUNT} package records.")
    records: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        try:
            name = str(item["File"])
            size = int(item["Size"])
            digest = str(item["SHA256"]).lower()
        except (KeyError, TypeError, ValueError) as exc:
            raise OSError("Artwork manifest contains an invalid record.") from exc
        if Path(name).name != name or not name.lower().endswith(".upk") or name.lower() in seen:
            raise OSError(f"Artwork manifest contains an unsafe or duplicate filename: {name}")
        if size <= 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise OSError(f"Artwork manifest contains invalid verification data: {name}")
        seen.add(name.lower())
        records.append({"name": name, "size": size, "sha256": digest})
    return tuple(records)


def artwork_status(path: Path, asset_dir: Path | None = None) -> tuple[int, int, int]:
    records = load_artwork_manifest(asset_dir)
    cooked = cooked_dir_from_database(path)
    installed = mismatched = 0
    for record in records:
        target = cooked / record["name"]
        if not target.is_file():
            continue
        if target.stat().st_size == record["size"] and sha256_file(target).lower() == record["sha256"]:
            installed += 1
        else:
            mismatched += 1
    return installed, len(records), mismatched


def _atomic_verified_copy(source: Path, target: Path, expected_sha256: str) -> None:
    temporary = target.with_name(f".{target.name}.codex-art-{os.getpid()}.tmp")
    try:
        shutil.copy2(source, temporary)
        if sha256_file(temporary).lower() != expected_sha256.lower():
            raise OSError(f"Verification failed while preparing {target.name}.")
        if target.exists():
            assert_file_replaceable(target)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def install_artwork_packages(
    path: Path,
    state: dict,
    asset_dir: Path | None = None,
) -> tuple[int, int, int]:
    """Install the verified artwork bundle and preserve a hash-guarded rollback."""
    records = load_artwork_manifest(asset_dir)
    source_root = asset_dir or artwork_asset_dir()
    cooked = cooked_dir_from_database(path)
    if not cooked.is_dir():
        raise OSError(f"Cooked game folder was not found: {cooked}")

    # Verify the complete embedded payload before touching the game directory.
    for record in records:
        source = source_root / record["name"]
        if not source.is_file() or source.stat().st_size != record["size"]:
            raise OSError(f"Artwork source is missing or has the wrong size: {record['name']}")
        if sha256_file(source).lower() != record["sha256"]:
            raise OSError(f"Artwork source failed SHA-256 verification: {record['name']}")

    root_key = str(game_root_from_database(path)).lower()
    artwork_state = state.setdefault("artwork_installs", {})
    previous = artwork_state.get(root_key)
    installed, expected, mismatched = artwork_status(path, source_root)
    if previous and installed == expected and not mismatched:
        return 0, 0, expected
    previous_files: dict[str, dict] = {}
    if previous:
        previous_files = dict(previous.get("files", {}))
        manifest_names = {record["name"] for record in records}
        if not previous_files or not set(previous_files).issubset(manifest_names):
            raise OSError("The recorded artwork installation is not compatible with this upgrade.")
        for name, saved in previous_files.items():
            target = cooked / name
            installed_hash = str(saved.get("installed_sha256") or "").lower()
            if not target.is_file() or not installed_hash or sha256_file(target).lower() != installed_hash:
                raise OSError(
                    "A previously installed artwork package is missing or changed. "
                    "Use Restore artwork from the version that installed it before retrying."
                )

    if mismatched:
        raise OSError(
            f"{mismatched} existing artwork package(s) differ from the runtime-tested set. "
            "They were left untouched; restore the earlier artwork pack before retrying."
        )

    backup_root = app_data_dir() / "ArtworkBackups" / f"{timestamp()}-{os.getpid()}"
    file_state: dict[str, dict] = dict(previous_files)
    created = replaced = 0
    unchanged = len(previous_files)
    for record in records:
        if record["name"] in file_state:
            continue
        target = cooked / record["name"]
        installed_hash = record["sha256"]
        saved = {
            "action": "Created",
            "installed_sha256": installed_hash,
            "backup": None,
            "original_sha256": None,
        }
        if target.is_file():
            existing_hash = sha256_file(target).lower()
            if existing_hash == installed_hash:
                saved["action"] = "PreexistingIdentical"
                unchanged += 1
            else:
                assert_file_replaceable(target)
                backup_root.mkdir(parents=True, exist_ok=True)
                backup = backup_root / record["name"]
                shutil.copy2(target, backup)
                if sha256_file(backup).lower() != existing_hash:
                    raise OSError(f"Original backup failed verification: {record['name']}")
                saved.update({
                    "action": "Replaced",
                    "backup": str(backup),
                    "original_sha256": existing_hash,
                })
                replaced += 1
        else:
            created += 1
        file_state[record["name"]] = saved

    artwork_state[root_key] = {
        "game_root": str(game_root_from_database(path)),
        "status": "Installing",
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "files": file_state,
    }
    # Persist the rollback map before the first game file is replaced.
    save_state(state)

    for record in records:
        saved = file_state[record["name"]]
        if record["name"] in previous_files or saved["action"] == "PreexistingIdentical":
            continue
        _atomic_verified_copy(source_root / record["name"], cooked / record["name"], record["sha256"])

    artwork_state[root_key]["status"] = "Installed"
    save_state(state)
    return created, replaced, unchanged


def restore_artwork_packages(
    path: Path,
    state: dict,
    asset_dir: Path | None = None,
) -> tuple[int, int]:
    records = load_artwork_manifest(asset_dir)
    cooked = cooked_dir_from_database(path)
    root_key = str(game_root_from_database(path)).lower()
    artwork_state = state.setdefault("artwork_installs", {})
    install_record = artwork_state.get(root_key, {})
    file_state = install_record.get("files", {})
    if not file_state:
        raise OSError("No artwork installation record is available for this game folder.")
    planned: list[tuple[str, Path, Path | None, str | None, str]] = []
    for record in records:
        target = cooked / record["name"]
        current_hash = sha256_file(target).lower() if target.is_file() else None
        saved = file_state.get(record["name"], {})
        action = saved.get("action") or ("Replaced" if saved.get("backup") else "Created")
        installed_hash = str(saved.get("installed_sha256") or record["sha256"]).lower()
        backup = Path(saved["backup"]) if saved.get("backup") else None
        original_hash = str(saved.get("original_sha256") or "").lower() or None
        if action == "PreexistingIdentical":
            planned.append((action, target, None, None, installed_hash))
            continue
        if action == "Created":
            if current_hash and current_hash != installed_hash:
                raise OSError(f"Refusing to remove a modified package: {target.name}")
            planned.append((action, target, None, None, installed_hash))
            continue
        if action != "Replaced":
            raise OSError(f"Artwork rollback record has an unknown action for {target.name}.")
        if backup and (not backup.is_file() or (original_hash and sha256_file(backup).lower() != original_hash)):
            raise OSError(f"Original backup is missing or changed for {target.name}.")
        if current_hash not in {installed_hash, original_hash}:
            raise OSError(f"Refusing to replace a modified package: {target.name}")
        planned.append((action, target, backup, original_hash, installed_hash))
    removed = restored = 0
    for action, target, backup, original_hash, installed_hash in planned:
        if action == "PreexistingIdentical":
            continue
        current_hash = sha256_file(target).lower() if target.is_file() else None
        if action == "Created" and current_hash == installed_hash:
            assert_file_replaceable(target)
            target.unlink()
            removed += 1
        elif action == "Replaced" and current_hash == installed_hash and backup and backup.is_file():
            _atomic_verified_copy(backup, target, original_hash or sha256_file(backup))
            restored += 1
    artwork_state.pop(root_key, None)
    return removed, restored


def steam_libraries() -> list[Path]:
    roots: list[Path] = []
    steam_roots = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Steam",
    ]
    for steam_root in steam_roots:
        if steam_root.exists() and steam_root not in roots:
            roots.append(steam_root)
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            candidate = Path(match.group(1).replace(r"\\", "\\"))
            if candidate not in roots:
                roots.append(candidate)
    return roots


def discover_database() -> Path | None:
    candidates = [
        Path(r"D:\SteamLibrary\steamapps\common\LET IT DIE") / DB_RELATIVE,
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\LET IT DIE") / DB_RELATIVE,
    ]
    candidates.extend(library / "steamapps" / "common" / "LET IT DIE" / DB_RELATIVE for library in steam_libraries())
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def running_game_pids() -> list[int]:
    if os.name != "nt":
        return []
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []
    matches: list[int] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == GAME_PROCESS.lower():
                matches.append(int(entry.th32ProcessID))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return matches


def assert_file_replaceable(path: Path) -> None:
    if os.name != "nt":
        return
    DELETE = 0x00010000
    FILE_SHARE_READ, FILE_SHARE_WRITE, FILE_SHARE_DELETE = 1, 2, 4
    OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL = 3, 0x80
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateFileW(
        str(path), DELETE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error in (32, 33):
            raise DatabaseLockedError(
                "masters.db is locked. Fully exit LET IT DIE, wait a few seconds, and retry. "
                "The runtime trainer may remain open, but the game must be closed."
            )
        raise OSError(error, ctypes.FormatError(error), str(path))
    kernel32.CloseHandle(handle)


def assert_database_replaceable(path: Path) -> None:
    assert_file_replaceable(path)


def validate_database(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "Database file not found."
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(EXPECTED_TABLES - tables)
        if missing:
            return False, "Unexpected database; missing: " + ", ".join(missing)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return False, f"SQLite integrity check failed: {integrity}"
        count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        return True, f"Valid LET IT DIE database ({count} tables, {path.stat().st_size / 1048576:.1f} MB)."
    except (OSError, sqlite3.Error) as exc:
        return False, f"Database validation failed: {exc}"
    finally:
        if conn is not None:
            conn.close()


def _quest_template(conn: sqlite3.Connection) -> tuple[list, list[str], dict[str, int]]:
    cursor = conn.execute("SELECT * FROM master_quest WHERE qid=?", (QUEST_TEMPLATE,))
    template = cursor.fetchone()
    if template is None:
        raise sqlite3.DatabaseError(f"Template quest {QUEST_TEMPLATE} was not found.")
    columns = [description[0] for description in cursor.description]
    return list(template), columns, {name: index for index, name in enumerate(columns)}


def _verify_targets(conn: sqlite3.Connection, category: ContentCategory) -> None:
    target_ids = tuple(quest.target_id for quest in category.quests)
    placeholders = ",".join("?" for _ in target_ids)
    if category.reward_type == "ITEM":
        found = {row[0] for row in conn.execute(
            f"SELECT itemid FROM master_item WHERE itemtype='ITTP_RMAP' AND itemid IN ({placeholders})", target_ids
        )}
    else:
        found = {row[0] for row in conn.execute(f"SELECT id FROM master_skill WHERE id IN ({placeholders})", target_ids)}
    missing = sorted(set(target_ids) - found)
    if missing:
        raise sqlite3.DatabaseError(f"{category.label} is missing retained records: " + ", ".join(missing))


def ensure_decal_compatibility(conn: sqlite3.Connection, quests: tuple[RewardQuest, ...] | None = None) -> int:
    selected = quests or ALL_COLLAB_DECAL_QUESTS
    touched = 0
    for quest in selected:
        steam_number = DECAL_STEAM_NUMBERS.get(quest.target_id)
        if steam_number is None:
            # No More Heroes rows already have retained Steam catalog numbers.
            row = conn.execute(
                "SELECT platform, no_steam FROM master_skill WHERE id=?", (quest.target_id,)
            ).fetchone()
            if row is None or row[0] != 0 or row[1] <= 0:
                raise sqlite3.DatabaseError(f"Missing Steam-compatible decal record: {quest.target_id}")
            continue
        conflict = conn.execute(
            "SELECT id FROM master_skill WHERE no_steam=? AND id<>?", (steam_number, quest.target_id)
        ).fetchone()
        if conflict:
            raise sqlite3.DatabaseError(
                f"Steam decal catalog slot {steam_number} is already used by {conflict[0]}."
            )
        touched += conn.execute(
            "UPDATE master_skill SET platform=0, no_steam=?, is_display=1, is_display_list=1 WHERE id=?",
            (steam_number, quest.target_id),
        ).rowcount
    return touched


def decal_pool_status_conn(conn: sqlite3.Connection) -> tuple[int, int, int]:
    ready = modified = 0
    for skill_id in POOL_DECAL_IDS:
        skill = conn.execute(
            "SELECT rarity, premium, is_display, is_display_list, platform FROM master_skill WHERE id=?",
            (skill_id,),
        ).fetchone()
        # Visibility/platform fields for retained non-Steam collaborations are
        # repaired during installation; their clean pre-patch values are not a
        # conflict. Missing definitions, wrong rarity, or non-premium rows are.
        if skill is None or skill[0] not in POOL_ODDS_BY_RARITY or skill[1] != 1:
            modified += 1
            continue
        row = conn.execute(
            "SELECT odds, display_priority FROM master_skillgacha_odds WHERE id=? AND sklid=?",
            (OFFLINE_GACHA_ID, skill_id),
        ).fetchone()
        if row == (POOL_ODDS_BY_RARITY[skill[0]], 0):
            ready += 1
        elif row is not None:
            modified += 1
    return ready, len(POOL_DECAL_IDS), modified


def ensure_decal_pool(conn: sqlite3.Connection) -> int:
    gacha = conn.execute(
        "SELECT id FROM master_skillgacha WHERE id=? AND odds_id=? AND platform=0",
        (OFFLINE_GACHA_ID, OFFLINE_GACHA_ID),
    ).fetchone()
    if gacha is None:
        raise sqlite3.DatabaseError("The normal offline Mushroom Club pool definition is missing.")
    # v3.1 is pool-only for decals. Remove any unclaimed decal quest routes
    # left by v3.0 while preserving decals already recorded in save data.
    touched = remove_quest_specs(conn, ALL_COLLAB_DECAL_QUESTS)
    touched += ensure_decal_compatibility(conn)
    for skill_id in POOL_DECAL_IDS:
        skill = conn.execute(
            "SELECT rarity, premium, is_display, is_display_list, platform FROM master_skill WHERE id=?",
            (skill_id,),
        ).fetchone()
        if skill is None or skill[0] not in POOL_ODDS_BY_RARITY or skill[1:] != (1, 1, 1, 0):
            raise sqlite3.DatabaseError(f"Missing or incompatible premium decal definition: {skill_id}")
        expected = (POOL_ODDS_BY_RARITY[skill[0]], 0)
        existing = conn.execute(
            "SELECT odds, display_priority FROM master_skillgacha_odds WHERE id=? AND sklid=?",
            (OFFLINE_GACHA_ID, skill_id),
        ).fetchone()
        if existing == expected:
            continue
        if existing is not None:
            raise sqlite3.DatabaseError(
                f"A modified pool entry was preserved for {skill_id} (odds={existing[0]}, priority={existing[1]})."
            )
        touched += conn.execute(
            "INSERT INTO master_skillgacha_odds (id, sklid, odds, display_priority) VALUES (?, ?, ?, 0)",
            (OFFLINE_GACHA_ID, skill_id, expected[0]),
        ).rowcount
    return touched


def remove_decal_pool(conn: sqlite3.Connection) -> int:
    touched = 0
    for skill_id in POOL_DECAL_IDS:
        skill = conn.execute("SELECT rarity FROM master_skill WHERE id=?", (skill_id,)).fetchone()
        if skill is None or skill[0] not in POOL_ODDS_BY_RARITY:
            raise sqlite3.DatabaseError(f"Missing decal definition while removing pool entry: {skill_id}")
        existing = conn.execute(
            "SELECT odds, display_priority FROM master_skillgacha_odds WHERE id=? AND sklid=?",
            (OFFLINE_GACHA_ID, skill_id),
        ).fetchone()
        if existing is None:
            continue
        expected = (POOL_ODDS_BY_RARITY[skill[0]], 0)
        if existing != expected:
            raise sqlite3.DatabaseError(
                f"A modified pool entry was preserved for {skill_id} (odds={existing[0]}, priority={existing[1]})."
            )
        touched += conn.execute(
            "DELETE FROM master_skillgacha_odds WHERE id=? AND sklid=?",
            (OFFLINE_GACHA_ID, skill_id),
        ).rowcount
    return touched


def decal_pool_status(path: Path) -> tuple[int, int, int]:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        return decal_pool_status_conn(conn)
    finally:
        conn.close()


def install_category(conn: sqlite3.Connection, category: ContentCategory) -> int:
    touched = remove_quest_specs(conn, ALL_COLLAB_DECAL_QUESTS)
    _verify_targets(conn, category)
    template, columns, indexes = _quest_template(conn)
    quest_sql = f"INSERT OR REPLACE INTO master_quest ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
    touched += ensure_decal_compatibility(conn, category.quests) if category.reward_type == "SKILL" else 0
    for spec in category.quests:
        conn.execute(
            "INSERT OR REPLACE INTO master_reward "
            "(rwdid, name, type, num, val0, val1, val2) VALUES (?, ?, ?, 1, ?, '', '')",
            (spec.reward_id, spec.display_name, category.reward_type, spec.target_id),
        )
        quest = list(template)
        quest[indexes["qid"]] = spec.qid
        quest[indexes["no"]] = spec.number
        quest[indexes["first_rwd"]] = spec.reward_id
        quest[indexes["rwd"]] = "RWD_MONEY_500"
        quest[indexes["prgmax"]] = 1
        quest[indexes["start_date"]] = -1
        quest[indexes["end_date"]] = -1
        quest[indexes["old_flg"]] = 0
        conn.execute(quest_sql, tuple(quest))
        touched += 2
        for table in QUEST_PARAMETER_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE qid=?", (spec.qid,))
            table_columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            copied_columns = [column for column in table_columns if column != "qid"]
            if not copied_columns:
                continue
            source_rows = conn.execute(
                f"SELECT {','.join(copied_columns)} FROM {table} WHERE qid=?", (QUEST_TEMPLATE,)
            ).fetchall()
            if source_rows:
                insert_columns = ["qid", *copied_columns]
                insert_sql = (
                    f"INSERT INTO {table} ({','.join(insert_columns)}) "
                    f"VALUES ({','.join('?' for _ in insert_columns)})"
                )
                conn.executemany(insert_sql, ((spec.qid, *row) for row in source_rows))
                touched += len(source_rows)
    return touched


def remove_quest_specs(conn: sqlite3.Connection, quests: tuple[RewardQuest, ...]) -> int:
    if not quests:
        return 0
    qids = tuple(quest.qid for quest in quests)
    rewards = tuple(quest.reward_id for quest in quests)
    qmarks = ",".join("?" for _ in qids)
    touched = 0
    for table in QUEST_PARAMETER_TABLES:
        touched += conn.execute(f"DELETE FROM {table} WHERE qid IN ({qmarks})", qids).rowcount
    touched += conn.execute(f"DELETE FROM master_quest WHERE qid IN ({qmarks})", qids).rowcount
    reward_marks = ",".join("?" for _ in rewards)
    touched += conn.execute(f"DELETE FROM master_reward WHERE rwdid IN ({reward_marks})", rewards).rowcount
    return touched


def remove_category(conn: sqlite3.Connection, category: ContentCategory) -> int:
    return remove_quest_specs(conn, ALL_COLLAB_DECAL_QUESTS) + remove_quest_specs(conn, category.quests)


def category_status_conn(conn: sqlite3.Connection, category: ContentCategory) -> tuple[int, int]:
    complete = 0
    for spec in category.quests:
        quest = conn.execute(
            "SELECT first_rwd, rwd, prgmax, start_date, end_date, old_flg FROM master_quest WHERE qid=?",
            (spec.qid,),
        ).fetchone()
        reward = conn.execute(
            "SELECT type, num, val0 FROM master_reward WHERE rwdid=?", (spec.reward_id,)
        ).fetchone()
        compatible = True
        if category.reward_type == "SKILL":
            platform_row = conn.execute(
                "SELECT platform, no_steam, is_display, is_display_list FROM master_skill WHERE id=?",
                (spec.target_id,),
            ).fetchone()
            expected_number = DECAL_STEAM_NUMBERS.get(spec.target_id)
            compatible = platform_row is not None and platform_row[0] == 0 and platform_row[2:] == (1, 1)
            compatible = compatible and (
                platform_row[1] == expected_number if expected_number is not None else platform_row[1] > 0
            )
        if quest == (spec.reward_id, "RWD_MONEY_500", 1, -1, -1, 0) and reward == (
            category.reward_type, 1, spec.target_id
        ) and compatible:
            complete += 1
    return complete, len(category.quests)


def all_status(path: Path) -> dict[str, tuple[int, int]]:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        return {category.key: category_status_conn(conn, category) for category in CONTENT_CATEGORIES}
    finally:
        conn.close()


def patch_copy(path: Path, callback) -> object:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        result = callback(conn)
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"Integrity check after patching returned: {integrity}")
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class ContentPatcherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("980x760")
        self.minsize(860, 720)
        self.option_add("*Font", ("Segoe UI", 10))
        found = discover_database()
        self.db_var = tk.StringVar(value=str(found) if found else "")
        self.database_var = tk.StringVar(value="Select masters.db.")
        self.artwork_var = tk.StringVar(value="Artwork packages not checked.")
        self.pool_var = tk.StringVar(value="Mushroom Club pool not checked.")
        self.blueprint_var = tk.StringVar(value="Blueprint quests not checked.")
        self._build_ui()
        self.after(100, self.refresh_status)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_NAME, font=("Segoe UI Semibold", 18)).pack(anchor="w")
        ttk.Label(
            outer,
            text="A compact, reversible installer for offline blueprints, decals, and collaboration artwork.",
            foreground="#555555",
        ).pack(anchor="w", pady=(2, 10))

        database = ttk.LabelFrame(outer, text="LET IT DIE database", padding=9)
        database.pack(fill="x")
        path_row = ttk.Frame(database)
        path_row.pack(fill="x")
        ttk.Entry(path_row, textvariable=self.db_var).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse…", command=self.browse).pack(side="right", padx=(8, 0))
        ttk.Label(database, textvariable=self.database_var, foreground="#444444").pack(anchor="w", pady=(6, 0))

        artwork = ttk.LabelFrame(outer, text="Verified collaboration decal artwork", padding=9)
        artwork.pack(fill="x", pady=(10, 0))
        ttk.Label(
            artwork,
            text=(
                "Preserves the 102 runtime-tested packages and adds three packages for Panther Mode, covering 35 retained collaboration decal images. "
                "Every source file is SHA-256 verified before installation; differing existing packages are left untouched."
            ),
            foreground="#555555", wraplength=900, justify="left",
        ).pack(anchor="w")
        artwork_row = ttk.Frame(artwork)
        artwork_row.pack(fill="x", pady=(7, 0))
        self.artwork_button = ttk.Button(
            artwork_row, text="Install artwork", command=self.toggle_artwork
        )
        self.artwork_button.pack(side="left")
        ttk.Label(artwork_row, textvariable=self.artwork_var, foreground="#174a7e").pack(side="left", padx=(12, 0))

        pool = ttk.LabelFrame(outer, text=f"Offline Mushroom Club RNG pool ({TOTAL_POOL_DECALS} decals)", padding=9)
        pool.pack(fill="x", pady=(10, 0))
        ttk.Label(
            pool,
            text=(
                "Adds all 35 retained collaboration decals plus Ultimate Fighter's Return to the normal offline draw pool. "
                "Uses the game's standard rarity weights and does not grant any decal directly."
            ),
            foreground="#555555", wraplength=900, justify="left",
        ).pack(anchor="w")
        pool_row = ttk.Frame(pool)
        pool_row.pack(fill="x", pady=(7, 0))
        self.pool_button = ttk.Button(pool_row, text="Add decals to pool", command=self.toggle_decal_pool)
        self.pool_button.pack(side="left")
        ttk.Label(pool_row, textvariable=self.pool_var, foreground="#174a7e").pack(side="left", padx=(12, 0))

        content = ttk.LabelFrame(outer, text=f"Safe one-time blueprint quests ({TOTAL_BLUEPRINTS})", padding=10)
        content.pack(fill="x", pady=(10, 0))
        ttk.Label(
            content,
            text=(
                "One switch controls the complete safe set: Beam Katana, Travis' set, both Ultra 3D Glasses, "
                "and Uncle-D2 Head. The set remains below the game's 10-visible-quest limit."
            ),
            foreground="#555555", wraplength=900, justify="left",
        ).pack(anchor="w")
        blueprint_row = ttk.Frame(content)
        blueprint_row.pack(fill="x", pady=(7, 0))
        self.blueprint_button = ttk.Button(
            blueprint_row, text=f"Enable all {TOTAL_BLUEPRINTS} quests", command=self.toggle_blueprints
        )
        self.blueprint_button.pack(side="left")
        ttk.Label(blueprint_row, textvariable=self.blueprint_var, foreground="#174a7e").pack(side="left", padx=(12, 0))
        ttk.Button(
            blueprint_row, text="Install / update complete safe pack", command=self.install_everything
        ).pack(side="right")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="Restore everything", command=self.restore_everything).pack(side="left")
        ttk.Button(controls, text="Refresh status", command=self.refresh_status).pack(side="left", padx=(8, 0))
        ttk.Label(controls, text="Game must be fully closed", foreground="#9b1c1c").pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="Activity", padding=7)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log_widget = tk.Text(log_frame, height=7, wrap="word", state="disabled", bg="#fafafa")
        self.log_widget.pack(fill="both", expand=True)
        self.log("No game files have been changed.")

    def log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")
        self.update_idletasks()

    def selected_path(self) -> Path:
        return Path(self.db_var.get().strip().strip('"')).expanduser()

    def browse(self) -> None:
        selected = self.selected_path()
        initial = selected.parent if selected.is_file() else Path.home()
        chosen = filedialog.askopenfilename(
            title="Select LET IT DIE masters.db", initialdir=str(initial),
            filetypes=[("LET IT DIE database", "masters.db"), ("Database files", "*.db"), ("All files", "*.*")],
        )
        if chosen:
            self.db_var.set(chosen)
            self.refresh_status()

    def refresh_status(self) -> None:
        path = self.selected_path()
        self._refresh_artwork_status(path)
        self._refresh_pool_status(path)
        ok, detail = validate_database(path)
        self.database_var.set(detail)
        if not ok:
            self.blueprint_var.set("Unavailable")
            self.blueprint_button.configure(state="disabled")
            self.log(detail)
            return
        try:
            statuses = all_status(path)
            blueprint_ready = sum(statuses[category.key][0] for category in CONTENT_CATEGORIES)
            self.blueprint_var.set(f"{blueprint_ready}/{TOTAL_BLUEPRINTS} ready")
            self.blueprint_button.configure(
                state="normal",
                text=(
                    f"Disable all {TOTAL_BLUEPRINTS} quests"
                    if blueprint_ready == TOTAL_BLUEPRINTS else
                    f"Enable all {TOTAL_BLUEPRINTS} quests"
                ),
            )
            self.log(detail)
        except sqlite3.Error as exc:
            self.blueprint_var.set("Status check failed")
            self.log(f"Status check failed: {exc}")

    def _refresh_artwork_status(self, path: Path) -> None:
        try:
            installed, expected, mismatched = artwork_status(path)
            root_key = str(game_root_from_database(path)).lower()
            previous = load_state().get("artwork_installs", {}).get(root_key, {})
            previous_files = previous.get("files", {})
            cooked = cooked_dir_from_database(path)
            changed_tracked = 0
            for name, saved in previous_files.items():
                target = cooked / name
                saved_hash = str(saved.get("installed_sha256") or "").lower()
                if not target.is_file() or not saved_hash or sha256_file(target).lower() != saved_hash:
                    changed_tracked += 1
            if changed_tracked:
                self.artwork_var.set(
                    f"Safety stop: {changed_tracked} previously tracked package(s) changed"
                )
                self.artwork_button.configure(text="Artwork conflict", state="disabled")
            elif mismatched:
                self.artwork_var.set(
                    f"Safety stop: {mismatched} package(s) differ from the runtime-tested set"
                )
                self.artwork_button.configure(text="Artwork conflict", state="disabled")
            elif installed == expected:
                self.artwork_var.set(f"Installed and verified: {installed}/{expected}")
                self.artwork_button.configure(text="Restore artwork", state="normal")
            elif installed:
                self.artwork_var.set(f"Partially installed: {installed}/{expected}")
                self.artwork_button.configure(text="Finish artwork install", state="normal")
            else:
                self.artwork_var.set(f"Not installed: 0/{expected}")
                self.artwork_button.configure(text="Install artwork", state="normal")
        except (OSError, ValueError) as exc:
            self.artwork_var.set(f"Unavailable: {exc}")
            self.artwork_button.configure(text="Artwork unavailable", state="disabled")

    def _refresh_pool_status(self, path: Path) -> None:
        try:
            ready, expected, modified = decal_pool_status(path)
            if modified:
                self.pool_var.set(f"Safety stop: {modified} missing or modified definition(s)")
                self.pool_button.configure(text="Pool conflict", state="disabled")
            elif ready == expected:
                self.pool_var.set(f"Ready: {ready}/{expected} decals in pool")
                self.pool_button.configure(text="Remove added pool entries", state="normal")
            else:
                self.pool_var.set(f"Not installed: {ready}/{expected} decals in pool")
                self.pool_button.configure(text="Add decals to pool", state="normal")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.pool_var.set(f"Unavailable: {exc}")
            self.pool_button.configure(text="Pool unavailable", state="disabled")

    def toggle_artwork(self) -> None:
        path = self.selected_path()
        try:
            installed, expected, mismatched = artwork_status(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, f"Artwork status is unavailable.\n\n{exc}")
            return
        if mismatched:
            messagebox.showerror(
                APP_NAME,
                "One or more artwork packages was changed by something else. The safety check refused to overwrite it.",
            )
            return
        if installed == expected:
            self.restore_artwork()
        else:
            self.install_artwork()

    def toggle_blueprints(self) -> None:
        path = self.selected_path()
        try:
            statuses = all_status(path)
            ready = sum(statuses[category.key][0] for category in CONTENT_CATEGORIES)
        except (OSError, sqlite3.Error):
            ready = 0
        enable = ready != TOTAL_BLUEPRINTS
        action = "Enable" if enable else "Disable"
        detail = (
            f"This adds all {TOTAL_BLUEPRINTS} safe one-time blueprint quests."
            if enable else
            "Unclaimed safe blueprint quests will be removed. Claimed rewards remain in save data."
        )
        if not messagebox.askyesno(
            APP_NAME, f"{action} all safe blueprint quests?\n\n{detail}", icon="question"
        ):
            return

        def callback(conn):
            operation = install_category if enable else remove_category
            return sum(operation(conn, category) for category in CONTENT_CATEGORIES)

        past_tense = "enabled" if enable else "disabled"
        if self._mutate(
            f"{action}ing all safe blueprint quests…",
            callback,
            f"Safe blueprint quests {past_tense}",
        ):
            messagebox.showinfo(
                APP_NAME,
                f"All {TOTAL_BLUEPRINTS} safe blueprint quests were {past_tense}."
                + (" Claimed rewards were not changed." if not enable else ""),
            )

    def _preflight(self) -> Path | None:
        path = self.selected_path()
        ok, detail = validate_database(path)
        self.database_var.set(detail)
        if not ok:
            messagebox.showerror(APP_NAME, detail)
            return None
        pids = running_game_pids()
        if pids:
            detail = f"Fully exit {GAME_PROCESS}. It is still running as PID {', '.join(map(str, pids))}."
            self.log(detail)
            messagebox.showerror(APP_NAME, detail)
            return None
        try:
            assert_database_replaceable(path)
        except OSError as exc:
            self.log(f"Preflight stopped: {exc}")
            messagebox.showerror(APP_NAME, str(exc))
            return None
        return path

    def _state_entry(self, path: Path) -> tuple[dict, dict]:
        state = load_state()
        state.setdefault("databases", {})
        entry = state["databases"].setdefault(str(path.resolve()).lower(), {})
        return state, entry

    def _legacy_baseline(self, path: Path) -> Path | None:
        legacy_state = local_app_data() / "LetItDieOfflineTrainer" / "state.json"
        try:
            data = json.loads(legacy_state.read_text(encoding="utf-8"))
            record = data.get("databases", {}).get(str(path.resolve()).lower(), {})
            candidate = Path(record.get("baseline", ""))
            if candidate.is_file() and validate_database(candidate)[0]:
                return candidate
        except (OSError, ValueError, TypeError):
            pass
        legacy_backups = sorted(
            (local_app_data() / "LetItDieCollabQuestPatcher" / "Backups").glob("masters.pre-collab.*.db")
        )
        return legacy_backups[0] if legacy_backups and validate_database(legacy_backups[0])[0] else None

    def _ensure_baseline(self, path: Path) -> Path:
        state, entry = self._state_entry(path)
        existing = Path(entry.get("baseline", ""))
        if existing.is_file() and validate_database(existing)[0]:
            return existing
        source = self._legacy_baseline(path) or path
        baseline = backup_dir() / f"masters.original.{timestamp()}.{sha256_file(source)[:12]}.db"
        shutil.copy2(source, baseline)
        entry.update({
            "path": str(path.resolve()), "baseline": str(baseline),
            "baseline_sha256": sha256_file(baseline), "created": datetime.now().isoformat(timespec="seconds"),
        })
        save_state(state)
        self.log(f"Original baseline preserved: {baseline}")
        return baseline

    def _mutate(self, description: str, callback, success_message: str) -> bool:
        path = self._preflight()
        if path is None:
            return False
        temp = path.with_name(f".{path.name}.codex-content-{os.getpid()}.tmp")
        prechange = backup_dir() / f"masters.pre-change.{timestamp()}.db"
        try:
            self._ensure_baseline(path)
            shutil.copy2(path, prechange)
            shutil.copy2(path, temp)
            self.log(description)
            result = patch_copy(temp, callback)
            ok, detail = validate_database(temp)
            if not ok:
                raise sqlite3.DatabaseError(detail)
            if running_game_pids():
                raise DatabaseLockedError(f"{GAME_PROCESS} started while the patch was being prepared. Close it and retry.")
            assert_database_replaceable(path)
            os.replace(temp, path)
            self.log(f"{success_message} ({result} rows affected).")
            self.refresh_status()
            return True
        except (OSError, sqlite3.Error) as exc:
            self.log(f"No replacement completed: {exc}")
            messagebox.showerror(
                APP_NAME,
                "The installed masters.db was not replaced.\n\n"
                f"{exc}\n\nA pre-change backup may be available at:\n{prechange}",
            )
            return False
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def toggle_decal_pool(self) -> None:
        path = self.selected_path()
        try:
            ready, expected, modified = decal_pool_status(path)
        except (OSError, ValueError, sqlite3.Error):
            ready, expected, modified = 0, TOTAL_POOL_DECALS, 0
        if modified:
            messagebox.showerror(
                APP_NAME,
                "One or more retained decal definitions or pool entries is modified. The safety check refused to overwrite it.",
            )
            return
        enable = ready != expected
        if not messagebox.askyesno(
            APP_NAME,
            (f"Add all {expected} retained decals to the normal offline Mushroom Club pool?\n\n"
             "This includes Ultimate Fighter's Return and uses the standard rarity weights. No decals are granted directly."
             if enable else
             f"Remove the {expected} added decal entries from the offline Mushroom Club pool?\n\n"
             "Decals already owned remain in save data."),
            icon="question",
        ):
            return
        callback = ensure_decal_pool if enable else remove_decal_pool
        action = "added to" if enable else "removed from"
        if self._mutate(
            f"Updating the offline Mushroom Club pool…",
            callback,
            f"Retained decals {action} the pool",
        ):
            messagebox.showinfo(
                APP_NAME,
                f"All {expected} retained decals were {action} the normal offline Mushroom Club pool successfully.",
            )

    def _install_artwork_to_path(self, path: Path) -> tuple[int, int, int]:
        state = load_state()
        result = install_artwork_packages(path, state)
        save_state(state)
        created, replaced, unchanged = result
        self.log(
            f"Artwork installed and verified: {created} created, {replaced} replaced with backup, "
            f"{unchanged} already identical."
        )
        return result

    def install_artwork(self) -> None:
        path = self._preflight()
        if path is None:
            return
        if not messagebox.askyesno(
            APP_NAME,
            f"Install all {ARTWORK_PACKAGE_COUNT} verified collaboration artwork packages?\n\n"
            "Changed files are backed up and rollback is hash-guarded.",
            icon="question",
        ):
            return
        try:
            created, replaced, unchanged = self._install_artwork_to_path(path)
            self.refresh_status()
            messagebox.showinfo(
                APP_NAME,
                "Artwork installation completed successfully.\n\n"
                f"Created: {created}\nReplaced with backup: {replaced}\nAlready identical: {unchanged}",
            )
        except (OSError, ValueError) as exc:
            self.log(f"Artwork installation stopped safely: {exc}")
            messagebox.showerror(APP_NAME, f"Artwork installation was not completed.\n\n{exc}")

    def install_everything(self) -> None:
        if not messagebox.askyesno(
            APP_NAME,
            f"Install the complete safe offline pack?\n\n"
            f"• {TOTAL_BLUEPRINTS} blueprint quests\n"
            f"• {TOTAL_POOL_DECALS} decals in the normal RNG pool (no decal quests)\n"
            f"• {ARTWORK_PACKAGE_COUNT} verified artwork packages\n\n"
            "The pool uses the game's standard rarity weights.",
            icon="question",
        ):
            return

        def callback(conn):
            touched = sum(install_category(conn, category) for category in CONTENT_CATEGORIES)
            return touched + ensure_decal_pool(conn)

        if not self._mutate(
            "Enabling safe blueprint quests and updating the decal pool…",
            callback,
            "All safe reward packs enabled",
        ):
            return
        path = self.selected_path()
        try:
            created, replaced, unchanged = self._install_artwork_to_path(path)
            self.refresh_status()
            messagebox.showinfo(
                APP_NAME,
                f"Complete safe pack installed.\n\n"
                f"Blueprint quests: {TOTAL_REWARDS}\n"
                f"Mushroom Club pool: {TOTAL_POOL_DECALS} retained decals\n"
                f"Artwork: {created} created, {replaced} replaced, {unchanged} already identical\n\n"
                "Start the game, claim the blueprint quests, and use the normal Mushroom Club stew for decals.",
            )
        except (OSError, ValueError) as exc:
            self.log(f"Quest packs are enabled, but artwork installation stopped: {exc}")
            messagebox.showerror(
                APP_NAME,
                "The quest packs were enabled, but the artwork step did not complete.\n\n"
                f"{exc}\n\nUse Install / update artwork to retry.",
            )

    def restore_artwork(self) -> None:
        path = self._preflight()
        if path is None:
            return
        if not messagebox.askyesno(
            APP_NAME,
            "Restore the collaboration artwork to its pre-install state?\n\n"
            "Any original files backed up during installation will be restored. Modified or unknown files are never deleted.",
            icon="question",
        ):
            return
        state = load_state()
        try:
            removed, restored = restore_artwork_packages(path, state)
            save_state(state)
            self.log(f"Collaboration artwork restored: {removed} generated files removed, {restored} originals restored.")
            self.refresh_status()
            messagebox.showinfo(
                APP_NAME,
                "Artwork was restored safely. Quests, claimed decals, and decal visibility records were not changed.",
            )
        except (OSError, ValueError) as exc:
            self.log(f"Artwork restore stopped safely: {exc}")
            messagebox.showerror(APP_NAME, f"Artwork restore was stopped before removing unknown files.\n\n{exc}")

    def restore_everything(self) -> None:
        path = self._preflight()
        if path is None:
            return
        state, entry = self._state_entry(path)
        baseline = Path(entry.get("baseline", ""))
        if not baseline.is_file() or not validate_database(baseline)[0]:
            legacy = self._legacy_baseline(path)
            if legacy is None:
                messagebox.showinfo(APP_NAME, "No verified original database baseline is available yet.")
                return
            baseline = legacy
        if not messagebox.askyesno(
            APP_NAME,
            "Restore masters.db and the decal artwork pack to their pre-install state?\n\n"
            "Claimed rewards remain in save data. Modified or unknown package files are protected.",
            icon="question",
        ):
            return
        temp = path.with_name(f".{path.name}.codex-restore-all-{os.getpid()}.tmp")
        prechange = backup_dir() / f"masters.before-complete-restore.{timestamp()}.db"
        try:
            root_key = str(game_root_from_database(path)).lower()
            if state.get("artwork_installs", {}).get(root_key, {}).get("files"):
                removed, restored = restore_artwork_packages(path, state)
                save_state(state)
            else:
                removed = restored = 0
            shutil.copy2(path, prechange)
            shutil.copy2(baseline, temp)
            ok, detail = validate_database(temp)
            if not ok:
                raise sqlite3.DatabaseError(detail)
            assert_database_replaceable(path)
            os.replace(temp, path)
            self.log(
                f"Complete restore finished: database baseline restored, {removed} artwork files removed, "
                f"{restored} originals restored."
            )
            self.refresh_status()
            messagebox.showinfo(
                APP_NAME,
                "Database and installed packages were restored successfully. Claimed save rewards were not removed.",
            )
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.log(f"Complete restore stopped safely: {exc}")
            messagebox.showerror(APP_NAME, f"Complete restore did not finish.\n\n{exc}")
        finally:
            temp.unlink(missing_ok=True)

def embedded_self_test() -> None:
    records = load_artwork_manifest()
    for record in records:
        source = artwork_asset_dir() / record["name"]
        if not source.is_file() or source.stat().st_size != record["size"]:
            raise OSError(f"Embedded artwork size check failed: {record['name']}")
        if sha256_file(source).lower() != record["sha256"]:
            raise OSError(f"Embedded artwork hash check failed: {record['name']}")
    if TOTAL_REWARDS != 7 or TOTAL_BLUEPRINTS != 7 or TOTAL_DECALS != 35 or TOTAL_POOL_DECALS != 36:
        raise RuntimeError("Embedded quest catalog count is incorrect.")
    print(
        f"PASS: {APP_NAME} v{APP_VERSION}; {TOTAL_BLUEPRINTS} blueprint quests, "
        f"{TOTAL_POOL_DECALS} pool-only decals, {len(records)} verified artwork packages"
    )


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        embedded_self_test()
    else:
        ContentPatcherApp().mainloop()

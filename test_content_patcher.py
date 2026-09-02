from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "LetItDieOfflineContentPatcher.pyw"
GAME_DB = Path(r"D:\SteamLibrary\steamapps\common\LET IT DIE\BrgGame\Content\masters.db")
CLEAN_DB = HERE.parents[1] / "outputs" / "masters.before-all-collab.20260901-173511.db"
DUSTY_SOURCE = HERE / "source_art" / "164_165_Dusty.png"
DUSTY_SOURCE_SHA256 = "576522a66346451ae504c1fbaa590f24543ca2448bf4a509defccb9b53e4138f"
APPLE_SOURCE = HERE / "source_art" / "162_Apple.png"
APPLE_SOURCE_SHA256 = "8955d2ecf4da13def8a73e233bfe8f22315e5ad59eb8055afc30e81ec56b2655"
PANTHER_SOURCE = HERE / "source_art" / "163_Panther-Mode.png"
PANTHER_SOURCE_SHA256 = "e5f77407cd41d2dace6daed06fae4b6fb2da180753111b78cfd7573c2d68161e"


def load_patcher():
    loader = importlib.machinery.SourceFileLoader("offline_content_patcher", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(path: Path, sql: str, values=()):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql, values).fetchone()[0]
    finally:
        conn.close()


def test_windows_delete_lock(module, path: Path) -> None:
    if __import__("os").name != "nt":
        return
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateFileW(
        str(path), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
    )
    assert handle != INVALID_HANDLE_VALUE, ctypes.FormatError(ctypes.get_last_error())
    try:
        try:
            module.assert_database_replaceable(path)
        except module.DatabaseLockedError:
            pass
        else:
            raise AssertionError("Windows delete-sharing lock was not detected")
    finally:
        kernel32.CloseHandle(handle)
    module.assert_database_replaceable(path)


def main() -> None:
    module = load_patcher()
    assert module.APP_VERSION == "3.53"
    ui_source = SOURCE.read_text(encoding="utf-8")
    for removed_text in (
        "Experimental substitute collaboration blueprints",
        "Restore substitute mode",
        "Install substitute visuals",
        "Repair claimed decal visibility",
        "Restore original database only",
    ):
        assert removed_text not in ui_source
    for removed_name in (
        "SUBSTITUTE_CONTENT_CATEGORIES",
        "SUBSTITUTE_ROOT_PAIRS",
        "load_substitute_icon_manifest",
        "install_substitute_icons",
        "ensure_substitute_assets",
        "restore_substitute_assets",
    ):
        assert not hasattr(module, removed_name)
    assert not (HERE / "assets" / "substitute_blueprint_icons").exists()
    assert hasattr(module.ContentPatcherApp, "toggle_artwork")
    assert hasattr(module.ContentPatcherApp, "toggle_blueprints")

    test_database = CLEAN_DB if CLEAN_DB.is_file() else GAME_DB
    assert test_database.is_file(), f"Test database not found: {test_database}"
    ok, detail = module.validate_database(test_database)
    assert ok, detail

    categories = module.CONTENT_CATEGORIES
    assert [len(category.quests) for category in categories] == [4, 2, 1]
    assert sum(len(category.quests) for category in categories) == 7
    all_targets = {quest.target_id for category in categories for quest in category.quests}
    assert "ITMP_ARM_WP017_0A1" not in all_targets  # experimental Demon Gun route removed
    assert "ITMP_ARM_WP025_0K1" not in all_targets  # experimental GLIDER route removed
    assert "ITMP_ARM_WP031_0A1" not in all_targets  # experimental WoT KAMAS route removed

    decals = dict(module.COLLAB_DECALS)
    assert len(decals) == 35
    assert decals["SKL_HPCUREUP_03_P"] == "Apple"
    assert decals["SKL_HPUP_ATKUP_P"] == "Panther Mode"
    assert decals["SKL_NDFALL_AUSTEALTH_P"] == "Dusty"
    assert decals["SKL_GRAVITY_DROPKICK_P"] == "Kat"
    assert len(module.POOL_DECAL_IDS) == 36
    assert len(set(module.POOL_DECAL_IDS)) == 36
    assert module.ULTIMATE_FIGHTER_RETURN_ID in module.POOL_DECAL_IDS
    assert len(module.DECAL_STEAM_NUMBERS) == 24
    assert module.DECAL_STEAM_NUMBERS["SKL_NDFALL_AUSTEALTH_P"] == 351
    assert module.DECAL_STEAM_NUMBERS["SKL_HPCUREUP_03_P"] == 352
    assert module.DECAL_STEAM_NUMBERS["SKL_HPUP_ATKUP_P"] == 353
    old_slots = sorted(
        number for skill_id, number in module.DECAL_STEAM_NUMBERS.items()
        if skill_id not in {
            "SKL_NDFALL_AUSTEALTH_P", "SKL_HPCUREUP_03_P", "SKL_HPUP_ATKUP_P"
        }
    )
    assert old_slots == list(range(330, 351))

    artwork_manifest = module.load_artwork_manifest()
    assert len(artwork_manifest) == 105
    artwork_names = {record["name"] for record in artwork_manifest}
    stems = {
        name.replace("_M_SF.upk", "").replace("_S_SF.upk", "").replace("_SF.upk", "")
        for name in artwork_names
    }
    assert len(stems) == 35
    assert {
        "UI_SKL_HPUP_ATKUP_SF.upk",
        "UI_SKL_HPUP_ATKUP_M_SF.upk",
        "UI_SKL_HPUP_ATKUP_S_SF.upk",
    }.issubset(artwork_names)
    assert {
        "UI_SKL_HPCUREUP_03_SF.upk",
        "UI_SKL_HPCUREUP_03_M_SF.upk",
        "UI_SKL_HPCUREUP_03_S_SF.upk",
    }.issubset(artwork_names)
    assert {
        "UI_SKL_NDFALL_AUSTEALTH_SF.upk",
        "UI_SKL_NDFALL_AUSTEALTH_M_SF.upk",
        "UI_SKL_NDFALL_AUSTEALTH_S_SF.upk",
    }.issubset(artwork_names)
    # The original PNG rips are provenance inputs and are not redistributed in
    # the source repository. Validate them when a local developer supplies all
    # three, while always validating the cooked package hashes above.
    source_art = (
        (DUSTY_SOURCE, DUSTY_SOURCE_SHA256),
        (APPLE_SOURCE, APPLE_SOURCE_SHA256),
        (PANTHER_SOURCE, PANTHER_SOURCE_SHA256),
    )
    if all(path.is_file() for path, _ in source_art):
        for path, expected_hash in source_art:
            assert sha256(path) == expected_hash

    with tempfile.TemporaryDirectory(prefix="lid-content-patcher-v353-", dir=HERE) as temp_name:
        temp_dir = Path(temp_name)
        original = temp_dir / "masters.original.db"
        patched = temp_dir / "masters.patched.db"
        shutil.copy2(test_database, original)
        shutil.copy2(original, patched)
        original_hash = sha256(original)

        fake_game = temp_dir / "LET IT DIE"
        fake_db = fake_game / module.DB_RELATIVE
        fake_cooked = fake_game / module.COOKED_RELATIVE
        fake_db.parent.mkdir(parents=True)
        fake_cooked.mkdir(parents=True)
        shutil.copy2(original, fake_db)
        artwork_sources = HERE / module.ARTWORK_RELATIVE
        preexisting_record = artwork_manifest[0]
        collision_record = artwork_manifest[1]
        shutil.copy2(artwork_sources / preexisting_record["name"], fake_cooked / preexisting_record["name"])
        collision = fake_cooked / collision_record["name"]
        collision_bytes = b"pre-existing-package-for-restore-test"
        collision.write_bytes(collision_bytes)
        module.local_app_data = lambda: temp_dir / "appdata"
        artwork_state = {"databases": {}}
        try:
            module.install_artwork_packages(fake_db, artwork_state)
        except OSError as exc:
            assert "runtime-tested set" in str(exc)
        else:
            raise AssertionError("A differing existing package was not preserved")
        assert collision.read_bytes() == collision_bytes
        collision.unlink()
        created, replaced, unchanged = module.install_artwork_packages(fake_db, artwork_state)
        assert (created, replaced, unchanged) == (104, 0, 1)
        assert module.artwork_status(fake_db) == (105, 105, 0)
        created_record = artwork_manifest[2]
        created_target = fake_cooked / created_record["name"]
        created_target.write_bytes(b"user-modified-after-install")
        try:
            module.restore_artwork_packages(fake_db, artwork_state)
        except OSError as exc:
            assert "modified package" in str(exc)
        else:
            raise AssertionError("Modified artwork package was not protected")
        shutil.copy2(artwork_sources / created_record["name"], created_target)
        removed, restored_count = module.restore_artwork_packages(fake_db, artwork_state)
        assert (removed, restored_count) == (104, 0)
        assert (fake_cooked / preexisting_record["name"]).is_file()

        # Simulate the 102 runtime-tested v3.52 packages and add only Panther Mode.
        new_names = {name for name in artwork_names if "HPUP_ATKUP" in name}
        previous_records = [record for record in artwork_manifest if record["name"] not in new_names]
        for record in previous_records:
            target = fake_cooked / record["name"]
            shutil.copy2(artwork_sources / record["name"], target)
        upgrade_state = {"databases": {}}
        assert module.install_artwork_packages(fake_db, upgrade_state) == (3, 0, 102)
        assert module.artwork_status(fake_db) == (105, 105, 0)
        assert module.restore_artwork_packages(fake_db, upgrade_state) == (3, 0)
        assert all((fake_cooked / record["name"]).is_file() for record in previous_records)

        test_windows_delete_lock(module, patched)

        for category in categories:
            module.patch_copy(patched, lambda conn, c=category: module.install_category(conn, c))
        statuses = module.all_status(patched)
        assert all(
            statuses[category.key] == (len(category.quests), len(category.quests))
            for category in categories
        )

        module.patch_copy(patched, module.remove_decal_pool)
        assert module.decal_pool_status(patched) == (0, 36, 0)
        module.patch_copy(patched, module.ensure_decal_pool)
        assert module.decal_pool_status(patched) == (36, 36, 0)

        conn = sqlite3.connect(patched)
        try:
            dusty_row = conn.execute(
                "SELECT platform, no_steam, is_display, is_display_list, rarity, premium "
                "FROM master_skill WHERE id='SKL_NDFALL_AUSTEALTH_P'"
            ).fetchone()
            assert dusty_row == (0, 351, 1, 1, 3, 1)
            apple_row = conn.execute(
                "SELECT type, val0, platform, no_steam, is_display, is_display_list, rarity, premium "
                "FROM master_skill WHERE id='SKL_HPCUREUP_03_P'"
            ).fetchone()
            assert apple_row == ("SKLTP_HPCUREUP", 15, 0, 352, 1, 1, 3, 1)
            panther_row = conn.execute(
                "SELECT type, val0, val1, platform, no_steam, is_display, is_display_list, rarity, premium "
                "FROM master_skill WHERE id='SKL_HPUP_ATKUP_P'"
            ).fetchone()
            assert panther_row == ("SKLTP_HPUP_ATKUP", 20, 5, 0, 353, 1, 1, 3, 1)
            for skill_id, steam_number in module.DECAL_STEAM_NUMBERS.items():
                assert conn.execute(
                    "SELECT platform, no_steam, is_display, is_display_list FROM master_skill WHERE id=?",
                    (skill_id,),
                ).fetchone() == (0, steam_number, 1, 1)
            for skill_id in module.POOL_DECAL_IDS:
                rarity = conn.execute("SELECT rarity FROM master_skill WHERE id=?", (skill_id,)).fetchone()[0]
                assert conn.execute(
                    "SELECT odds, display_priority FROM master_skillgacha_odds WHERE id=? AND sklid=?",
                    (module.OFFLINE_GACHA_ID, skill_id),
                ).fetchone() == (module.POOL_ODDS_BY_RARITY[rarity], 0)
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()

        assert scalar(patched, "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_%'") == 7
        assert scalar(patched, "SELECT COUNT(*) FROM master_reward WHERE rwdid LIKE 'RWD_CODEX_%'") == 7
        assert scalar(patched, "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_DECAL_%'") == 0
        for category in categories:
            module.patch_copy(patched, lambda conn, c=category: module.install_category(conn, c))
        assert scalar(patched, "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_%'") == 7
        module.patch_copy(patched, module.remove_decal_pool)
        assert module.decal_pool_status(patched) == (0, 36, 0)
        module.patch_copy(patched, module.ensure_decal_pool)
        assert module.decal_pool_status(patched) == (36, 36, 0)

        restored = temp_dir / "masters.restored.db"
        shutil.copy2(original, restored)
        assert sha256(restored) == original_hash
        assert module.validate_database(restored)[0]

    module.embedded_self_test()
    print("PASS: source compiles and installed database validates")
    print("PASS: experimental asset-swapped blueprints, UI, mappings, and icons are absent")
    print("PASS: 3 blueprint packs contain 7 safe one-time quests")
    print("PASS: Panther Mode, Apple, Dusty, and 32 other collaboration decals are pool-only")
    print("PASS: existing Steam catalog slots 330-352 are preserved; Panther Mode uses 353")
    print("PASS: 105 native-LZO artwork packages include three Drive-sourced Panther packages")
    print("PASS: 102 runtime-tested packages are preserved; only Panther Mode is added")
    print("PASS: differing existing packages are blocked without overwrite")
    print("PASS: exact reward routes, idempotence, integrity, and Windows lock detection")


if __name__ == "__main__":
    main()

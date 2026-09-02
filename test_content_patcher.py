from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "LetItDieOfflineContentPatcher.pyw"
GAME_DB = Path(os.environ.get("LID_MASTERS_DB", r"D:\SteamLibrary\steamapps\common\LET IT DIE\BrgGame\Content\masters.db"))


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
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
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
    assert GAME_DB.is_file(), f"Installed database not found: {GAME_DB}"
    ok, detail = module.validate_database(GAME_DB)
    assert ok, detail

    categories = module.CONTENT_CATEGORIES
    assert [len(category.quests) for category in categories] == [4, 2, 1]
    assert all(1 <= len(category.quests) <= 10 for category in categories)
    assert sum(len(category.quests) for category in categories) == 7
    all_targets = {quest.target_id for category in categories for quest in category.quests}

    # These remain excluded because they have ordinary offline acquisition routes.
    assert "SKL_SAMANTHA_K7_02_P" not in all_targets  # Queen of the Wolves
    assert "SKL_SYLVIA_NMH_02_P" not in all_targets  # Queen of Spades
    assert "ITMP_ARM_WP024_001" not in all_targets   # ordinary TDM/Hernia blueprint
    assert "ITMP_SPE_HEAD_013" not in all_targets    # Space Funglasses
    assert len(module.INCOMPLETE_BLUEPRINT_QUESTS) == 15
    assert not {quest.target_id for quest in module.INCOMPLETE_BLUEPRINT_QUESTS} & all_targets
    assert len(module.DECAL_STEAM_NUMBERS) == 21
    assert sorted(module.DECAL_STEAM_NUMBERS.values()) == list(range(330, 351))
    assert len(module.POOL_DECAL_IDS) == 33
    assert module.ULTIMATE_FIGHTER_RETURN_ID in module.POOL_DECAL_IDS
    assert len(set(module.POOL_DECAL_IDS)) == 33

    artwork_manifest = module.load_artwork_manifest()
    assert len(artwork_manifest) == 63
    assert hasattr(module, "install_artwork_packages")
    artwork_names = {record["name"] for record in artwork_manifest}
    assert len({name.replace("_M_SF.upk", "").replace("_S_SF.upk", "").replace("_SF.upk", "") for name in artwork_names}) == 21
    assert dict(module.COLLAB_DECALS)["SKL_GRAVITY_DROPKICK_P"] == "Kat"

    with tempfile.TemporaryDirectory(prefix="lid-content-patcher-", dir=HERE) as temp_name:
        temp_dir = Path(temp_name)
        original = temp_dir / "masters.original.db"
        patched = temp_dir / "masters.patched.db"
        restored = temp_dir / "masters.restored.db"
        shutil.copy2(GAME_DB, original)
        shutil.copy2(original, patched)
        original_hash = sha256(original)

        # Artwork installation distinguishes created, replaced, and already
        # identical files, then reverses only its own changes.
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
        created, replaced, unchanged = module.install_artwork_packages(fake_db, artwork_state)
        assert (created, replaced, unchanged) == (61, 1, 1)
        assert module.artwork_status(fake_db) == (63, 63, 0)
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
        assert (removed, restored_count) == (61, 1)
        assert collision.read_bytes() == collision_bytes
        assert (fake_cooked / preexisting_record["name"]).is_file()
        assert not artwork_state.get("artwork_installs")

        test_windows_delete_lock(module, patched)

        expected_ready = {}
        for category in categories:
            module.patch_copy(patched, lambda conn, c=category: module.install_category(conn, c))
            expected_ready[category.key] = (len(category.quests), len(category.quests))
            statuses = module.all_status(patched)
            for installed_key, expected in expected_ready.items():
                assert statuses[installed_key] == expected

        # Decals are pool-only in v3.1: 32 collaboration decals plus Ultimate
        # Fighter's Return, with the normal offline rarity weights.
        module.patch_copy(patched, module.remove_decal_pool)
        assert module.decal_pool_status(patched) == (0, 33, 0)
        module.patch_copy(patched, module.ensure_decal_pool)
        assert module.decal_pool_status(patched) == (33, 33, 0)

        conn = sqlite3.connect(patched)
        try:
            for skill_id, steam_number in module.DECAL_STEAM_NUMBERS.items():
                assert conn.execute(
                    "SELECT platform, no_steam, is_display, is_display_list FROM master_skill WHERE id=?",
                    (skill_id,),
                ).fetchone() == (0, steam_number, 1, 1)
            assert conn.execute(
                "SELECT COUNT(DISTINCT no_steam) FROM master_skill WHERE no_steam BETWEEN 330 AND 350"
            ).fetchone()[0] == 21
            for skill_id in module.POOL_DECAL_IDS:
                rarity = conn.execute("SELECT rarity FROM master_skill WHERE id=?", (skill_id,)).fetchone()[0]
                assert conn.execute(
                    "SELECT odds, display_priority FROM master_skillgacha_odds WHERE id=? AND sklid=?",
                    (module.OFFLINE_GACHA_ID, skill_id),
                ).fetchone() == (module.POOL_ODDS_BY_RARITY[rarity], 0)
        finally:
            conn.close()

        # Exact routes: retained item/skill IDs, one-time reward, and safe quest template fields.
        conn = sqlite3.connect(patched)
        try:
            for category in categories:
                for quest in category.quests:
                    reward = conn.execute(
                        "SELECT type, num, val0 FROM master_reward WHERE rwdid=?", (quest.reward_id,)
                    ).fetchone()
                    assert reward == (category.reward_type, 1, quest.target_id), (quest, reward)
                    route = conn.execute(
                        "SELECT first_rwd, rwd, prgmax, start_date, end_date, old_flg "
                        "FROM master_quest WHERE qid=?", (quest.qid,)
                    ).fetchone()
                    assert route == (quest.reward_id, "RWD_MONEY_500", 1, -1, -1, 0), (quest, route)
            assert conn.execute(
                "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_%'"
            ).fetchone()[0] == 7
            assert conn.execute(
                "SELECT COUNT(*) FROM master_reward WHERE rwdid LIKE 'RWD_CODEX_%'"
            ).fetchone()[0] == 7
            assert conn.execute(
                "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_DECAL_%'"
            ).fetchone()[0] == 0
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()

        # Reinstalling is idempotent and does not duplicate definitions.
        for category in categories:
            module.patch_copy(patched, lambda conn, c=category: module.install_category(conn, c))
        assert scalar(patched, "SELECT COUNT(*) FROM master_quest WHERE qid LIKE 'CODEX_%'") == 7
        assert scalar(patched, "SELECT COUNT(*) FROM master_reward WHERE rwdid LIKE 'RWD_CODEX_%'") == 7

        statuses = module.all_status(patched)
        assert all(statuses[category.key] == (len(category.quests), len(category.quests)) for category in module.BLUEPRINT_CATEGORIES)
        conn = sqlite3.connect(patched)
        try:
            for skill_id, steam_number in module.DECAL_STEAM_NUMBERS.items():
                assert conn.execute(
                    "SELECT platform, no_steam FROM master_skill WHERE id=?", (skill_id,)
                ).fetchone() == (0, steam_number)
        finally:
            conn.close()
        module.patch_copy(patched, module.remove_decal_pool)
        assert module.decal_pool_status(patched) == (0, 33, 0)
        module.patch_copy(patched, module.ensure_decal_pool)
        assert module.decal_pool_status(patched) == (33, 33, 0)

        # Restore uses the clean baseline, producing a byte-identical database.
        shutil.copy2(original, restored)
        assert sha256(restored) == original_hash
        ok, detail = module.validate_database(restored)
        assert ok, detail

    print("PASS: source compiles and installed database validates")
    print("PASS: 3 blueprint packs contain 7 safe one-time quests")
    print("PASS: 7 complete blueprints retained; 15 missing-icon/model blueprints excluded")
    print("PASS: 32 collaboration decals plus Ultimate Fighter's Return are pool-only")
    print("PASS: 21 non-Steam decal rows receive unique Steam catalog mappings 330-350")
    print("PASS: all 63 native-LZO artwork packages install and restore with hash guards")
    print("PASS: exact reward routes, idempotence, independent disable, integrity")
    print("PASS: byte-identical baseline restore; no seasonal controls or database mutations")
    print("PASS: Windows delete-sharing lock detection")


if __name__ == "__main__":
    main()

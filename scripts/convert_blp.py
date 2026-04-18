import os
from PIL import Image

# Base paths
INPUT_DIR  = r"D:\Games\TurtleWoW\Interface\AddOns\Atlas\Images\Maps"
DOCS_BASE  = r"D:\SRC\GitHub\liruqi\zh.chinapedia\docs\wow\turtle"

# ── Category classification ──────────────────────────────────────────────────
WORLD_BOSSES = {
    "Azuregos", "FourDragons", "LordKazzak", "Nerubian",
    "Reaver", "Ostarius", "Concavius", "CowKing", "Clackora",
}

TRANSPORT_MAPS = {
    "FPAllianceEast", "FPAllianceWest", "FPHordeEast", "FPHordeWest",
    "TransportRoutes",
}

# Entrance images: kept in dungeon/ alongside the parent dungeon .md/.png
DUNGEON_ENTRANCES = {
    "BlackfathomDeepsEnt", "BlackrockMountainEnt",
    "DireMaulEnt", "GnomereganEnt", "MaraudonEnt", "SMEnt",
    "TheDeadminesEnt", "TheSunkenTempleEnt", "UldamanEnt", "WailingCavernsEnt",
}

# DLEast / DLWest stay in dungeon/ for README embedding
DUNGEON_LOCATIONS = {"DLEast", "DLWest"}


def get_output_dir(base_name: str) -> str:
    """Return the target directory for a given map key."""
    if base_name in WORLD_BOSSES:
        return os.path.join(DOCS_BASE, "worldboss")
    if base_name in TRANSPORT_MAPS:
        return os.path.join(DOCS_BASE, "transport")
    # Entrances, DL maps, BGS, and all other dungeons go to dungeon/
    return os.path.join(DOCS_BASE, "dungeon")


def convert_all():
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".blp")]
    print(f"Found {len(files)} BLP files in {INPUT_DIR}")

    success = 0
    fail = 0

    for filename in files:
        base_name = os.path.splitext(filename)[0]
        input_path = os.path.join(INPUT_DIR, filename)
        out_dir = get_output_dir(base_name)
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"{base_name}.png")

        try:
            with Image.open(input_path) as img:
                img.save(output_path, "PNG")
                success += 1
                print(f"  {base_name}.png  ->  {os.path.relpath(out_dir, DOCS_BASE)}/")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")
            fail += 1

    print(f"\nConversion complete: {success} successful, {fail} failed.")


if __name__ == "__main__":
    convert_all()

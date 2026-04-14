import os
from PIL import Image
import sys

# Paths
INPUT_DIR = r"D:\Games\TurtleWoW\Interface\AddOns\Atlas\Images\Maps"
OUTPUT_DIR = r"D:\SRC\GitHub\liruqi\zh.chinapedia\docs\wow\turtle\img\maps"

def convert_all():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".blp")]
    print(f"Found {len(files)} BLP files in {INPUT_DIR}")

    success = 0
    fail = 0

    for filename in files:
        base_name = os.path.splitext(filename)[0]
        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, f"{base_name}.png")

        try:
            with Image.open(input_path) as img:
                # BLP maps often have multiple mipmaps, 
                # Image.open usually selects the largest one.
                img.save(output_path, "PNG")
                success += 1
                # print(f"Converted: {filename} -> {base_name}.png")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")
            fail += 1

    print(f"\nConversion complete: {success} successful, {fail} failed.")

if __name__ == "__main__":
    convert_all()

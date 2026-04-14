import os
import re
import json

# Paths
ADDONS_DIR = r"D:\Games\TurtleWoW\Interface\AddOns"
DOCS_BASE_DIR = r"D:\SRC\GitHub\liruqi\zh.chinapedia\docs\wow\turtle"
SCRIPTS_DIR = r"D:\SRC\GitHub\liruqi\zh.chinapedia\scripts"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

class LuaParser:
    @staticmethod
    def remove_comments(content):
        content = re.sub(r'--\[\[.*?\]\]', '', content, flags=re.DOTALL)
        content = re.sub(r'--.*', '', content)
        return content

    @staticmethod
    def extract_table_content(content, start_pos):
        """Extracts content within balanced braces starting from start_pos."""
        brace_count = 0
        first_brace = -1
        for i in range(start_pos, len(content)):
            if content[i] == '{':
                if brace_count == 0:
                    first_brace = i
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    return content[first_brace:i+1], i+1
        return None, -1

    @staticmethod
    def clean_lua_string(s):
        """Removes Lua concatenation, symbols, and color codes."""
        if not s: return ""
        # Remove Lua variable names like L.DAGGER, NORMAL
        # Pattern: prefixing with letters/dots, but we want to catch the whole thing
        s = re.sub(r'[A-Za-z_]+\.[A-Za-z0-9_]+', '', s)
        s = re.sub(r'\.\.', '', s)
        s = re.sub(r'\b(NORMAL|WHITE|RED|BLUE|GREEN|PURPLE|ORANGE|GREY|MAGE|PALADIN|WARRIOR|ROGUE|DRUID|HUNTER|SHAMAN|WARLOCK)\b', '', s)
        # Remove color codes |cFFFFFFFF and |r
        s = re.sub(r'\|c[0-9a-fA-F]{8}', '', s)
        s = re.sub(r'\|r', '', s)
        # Remove quotes
        s = s.strip().strip('"\'').strip()
        # Remove backslash escapes for quotes
        s = s.replace('\\"', '"').replace("\\'", "'")
        # Collapse multiple spaces and cleanup
        s = re.sub(r'\s+', ' ', s)
        # If it's just "????" or empty, return empty
        if all(c in '?' for c in s) and len(s) > 0:
            return ""
        return s.strip()

def load_loot_translations():
    path = os.path.join(ADDONS_DIR, "AtlasLoot", "Locale", "locale.cn.lua")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    kv_pairs = re.findall(r'\["(.*?)"\]\s*=\s*"(.*?)"', content)
    trans = dict(kv_pairs)
    trans["Onyxia"] = "奥妮克希亚"
    return trans

def get_quest_data_from_file(path):
    """Parses a localization file and returns a map of Quest ID -> Data."""
    if not os.path.exists(path):
        return {}
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    content = LuaParser.remove_comments(content)
    
    # We find start of AtlasQuest.data
    match = re.search(r'AtlasQuest\.data\s*=\s*\{', content)
    if not match:
        return {}
    
    data_block, _ = LuaParser.extract_table_content(content, match.start())
    if not data_block:
        return {}
    
    # Structure is data_block -> [dungeon] -> [faction] -> [quest]
    quests = {}
    
    # regex for dungeon/faction level tables: [1] = {
    # We'll use a more surgical approach: find all [questIndex] = { ... }
    # but we need to know they are quest blocks.
    # Quest blocks uniquely have ["id"] and ["title"] directly inside.
    
    # Find all balanced blocks that look like quests
    # We find "{", check if it has ["id"] and ["title"] but NOT ["rewards"] as a child of the same level
    # Actually, simpler: find all occurrences of ["id"] = \d+
    # then for each, find the smallest surrounding balanced braces.
    
    id_matches = re.finditer(r'\["id"\]\s*=\s*(\d+)', data_block)
    for match in id_matches:
        q_id = match.group(1)
        # Find the surrounding table
        start_search = data_block.rfind('{', 0, match.start())
        block, _ = LuaParser.extract_table_content(data_block, start_search)
        
        if block:
            # CHECK: Is this a quest block or a reward block?
            # A quest block has ["title"] in it.
            if '["title"]' in block:
                title_m = re.search(r'\["title"\]\s*=\s*(.*?),', block)
                aim_m = re.search(r'\["aim"\]\s*=\s*(.*?),', block)
                note_m = re.search(r'\["note"\]\s*=\s*(.*?),', block)
                location_m = re.search(r'\["location"\]\s*=\s*(.*?),', block)
                level_m = re.search(r'\["level"\]\s*=\s*(\d+)', block)
                attain_m = re.search(r'\["attain"\]\s*=\s*(\d+)', block)
                
                rewards = []
                reward_search = re.search(r'\["rewards"\]\s*=\s*\{', block)
                if reward_search:
                    reward_block, _ = LuaParser.extract_table_content(block, reward_search.start())
                    if reward_block:
                        item_matches = re.finditer(r'\["id"\]\s*=\s*(\d+)', reward_block)
                        for im in item_matches:
                            i_start = reward_block.rfind('{', 0, im.start())
                            i_block, _ = LuaParser.extract_table_content(reward_block, i_start)
                            if i_block:
                                i_id = im.group(1)
                                i_name_m = re.search(r'\["name"\]\s*=\s*(.*?),', i_block)
                                if i_name_m:
                                    rewards.append({
                                        "id": i_id,
                                        "name": LuaParser.clean_lua_string(i_name_m.group(1))
                                    })
                
                quests[q_id] = {
                    "id": q_id,
                    "title": LuaParser.clean_lua_string(title_m.group(1)) if title_m else "",
                    "aim": LuaParser.clean_lua_string(aim_m.group(1)) if aim_m else "",
                    "note": LuaParser.clean_lua_string(note_m.group(1)) if note_m else "",
                    "location": LuaParser.clean_lua_string(location_m.group(1)) if location_m else "",
                    "level": level_m.group(1) if level_m else "",
                    "attain": attain_m.group(1) if attain_m else "",
                    "rewards": rewards
                }
    return quests

def extract_quests():
    print("Loading Chinese quest data...")
    cn_path = os.path.join(ADDONS_DIR, "AtlasQuest", "Locale", "localization.cn.lua")
    cn_quests = get_quest_data_from_file(cn_path)
    
    print("Loading English quest data fallback...")
    en_path = os.path.join(ADDONS_DIR, "AtlasQuest", "Locale", "localization.en.lua")
    en_quests = get_quest_data_from_file(en_path)
    
    # Merge: Prioritize CN, fallback to EN
    all_ids = set(cn_quests.keys()) | set(en_quests.keys())
    merged_quests = []
    
    for q_id in all_ids:
        cn_q = cn_quests.get(q_id, {})
        en_q = en_quests.get(q_id, {})
        
        # Merge logic
        q = {
            "id": q_id,
            "title": cn_q.get("title") or en_q.get("title") or "Unknown",
            "aim": cn_q.get("aim") or en_q.get("aim") or "",
            "note": cn_q.get("note") or en_q.get("note") or "",
            "location": cn_q.get("location") or en_q.get("location") or "",
            "level": cn_q.get("level") or en_q.get("level") or "",
            "attain": cn_q.get("attain") or en_q.get("attain") or "",
            "rewards": cn_q.get("rewards") if cn_q.get("rewards") else en_q.get("rewards", [])
        }
        
        # Final filter: if Title is still Unknown or empty, skip
        if q["title"] != "Unknown" and q["title"].strip():
            merged_quests.append(q)
            
    return merged_quests

def extract_items_and_sources(translations):
    items = {}
    loot_dir = os.path.join(ADDONS_DIR, "AtlasLoot", "Database")
    if not os.path.exists(loot_dir):
        return items
    
    for filename in os.listdir(loot_dir):
        if filename.endswith(".lua"):
            path = os.path.join(loot_dir, filename)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            table_defs = re.finditer(r'([A-Za-z0-9_]+)\s*=\s*\{', content)
            for td in table_defs:
                table_name = td.group(1)
                if table_name in ["AtlasLootBossButtons", "AtlasLootItems", "AL", "AtlasLoot_Data"]: continue
                
                table_block, _ = LuaParser.extract_table_content(content, td.start())
                if not table_block: continue
                
                boss_name = translations.get(table_name, table_name)
                
                item_matches = re.finditer(r'\{\s*(\d+),', table_block)
                for im in item_matches:
                    item_line, _ = LuaParser.extract_table_content(table_block, im.start())
                    if item_line:
                        parts = re.search(r'\{\s*(\d+),\s*"(.*?)",\s*"=q(\d+)=(.*?)",', item_line)
                        if parts:
                            i_id, i_icon, i_qual, i_name = parts.groups()
                            if i_id == "0": continue
                            
                            if i_id not in items:
                                items[i_id] = {
                                    "id": i_id,
                                    "name": i_name,
                                    "quality": i_qual,
                                    "icon": i_icon,
                                    "sources": []
                                }
                            if boss_name not in items[i_id]["sources"]:
                                items[i_id]["sources"].append(boss_name)
    return items

def cleanup_invalid_files():
    print("Cleaning up invalid quest files...")
    request_dir = os.path.join(DOCS_BASE_DIR, "request")
    if not os.path.exists(request_dir):
        return
    
    for filename in os.listdir(request_dir):
        if filename.endswith(".md"):
            path = os.path.join(request_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                first_line = f.readline()
                content = f.read()
            
            # Delete if title is Unknown or content is basically empty
            if "# Unknown" in first_line or len(content.strip()) < 50:
                print(f"Deleting invalid file: {filename}")
                os.remove(path)

def generate_markdown(quests, items, translations):
    ensure_dir(os.path.join(DOCS_BASE_DIR, "item"))
    ensure_dir(os.path.join(DOCS_BASE_DIR, "request"))
    
    # Generate Quest files
    for q in quests:
        filename = f"{q['id']}.md"
        filepath = os.path.join(DOCS_BASE_DIR, "request", filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {q['title']}\n\n")
            f.write(f"**任务等级:** {q['level']}  \n")
            f.write(f"**最低等级:** {q['attain']}  \n")
            f.write(f"**开始地点:** {q['location']}  \n\n")
            f.write(f"## 任务目标\n{q['aim'] or '无'}\n\n")
            if q['note']:
                f.write(f"## 任务提示\n{q['note']}\n\n")
            
            if q['rewards']:
                f.write(f"## 任务奖励\n")
                seen_rewards = set()
                for r in q['rewards']:
                    if r['id'] not in seen_rewards and r['id'] != "0":
                        f.write(f"- [{r['name']}](../item/{r['id']}.md) (ID: {r['id']})\n")
                        seen_rewards.add(r['id'])
    
    # Generate Item files
    for i_id, i in items.items():
        filename = f"{i_id}.md"
        filepath = os.path.join(DOCS_BASE_DIR, "item", filename)
        
        name = translations.get(i['name'], i['name'])
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {name}\n\n")
            f.write(f"**物品 ID:** {i_id}  \n")
            f.write(f"**品质:** {i['quality']}  \n")
            f.write(f"**图标:** {i['icon']}  \n\n")
            f.write(f"## 获取途径\n")
            
            printed_source = False
            rewarded_by = [q for q in quests if any(r['id'] == i_id for r in q['rewards'])]
            if rewarded_by:
                f.write(f"### 任务奖励\n")
                for q in rewarded_by:
                    f.write(f"- [{q['title']}](../request/{q['id']}.md)\n")
                printed_source = True
            
            if i['sources']:
                f.write(f"### 掉落/来源\n")
                for src in i['sources']:
                    f.write(f"- {src}\n")
                printed_source = True
                
            if not printed_source:
                f.write(f"未知来源\n")

def run():
    print("Loading translations...")
    translations = load_loot_translations()
    
    print("Extracting Quest data with fallbacks...")
    quests = extract_quests()
    print(f"Found {len(quests)} valid quests.")
    
    print("Extracting Item and Source data...")
    items = extract_items_and_sources(translations)
    print(f"Found {len(items)} items in loot tables.")
    
    # Before generating new ones, clean up what was wrong
    # cleanup_invalid_files() # Actually regenerate will overwrite, but we need to delete orphaned ones
    
    print("Generating Markdown files...")
    generate_markdown(quests, items, translations)
    
    # Final cleanup for orphaned files (IDs that were misclassified)
    all_quest_ids = {q['id'] for q in quests}
    request_dir = os.path.join(DOCS_BASE_DIR, "request")
    for filename in os.listdir(request_dir):
        if filename.endswith(".md"):
            q_id = filename.replace(".md", "")
            if q_id not in all_quest_ids:
                print(f"Deleting orphaned file: {filename}")
                os.remove(os.path.join(request_dir, filename))

    print("Done.")

if __name__ == "__main__":
    run()

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
        """Extracts content within balance braces starting from start_pos."""
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
        """Removes Lua concatenation and color codes."""
        if not s: return ""
        # Remove Lua variable names that might be concatenated
        # e.g. L.DAGGER or NORMAL
        s = re.sub(r'[A-Za-z]\.[A-Za-z0-9_]+', '', s)
        s = re.sub(r'\.\.', '', s)
        s = re.sub(r'\b(NORMAL|WHITE|RED|BLUE|GREEN|PURPLE|ORANGE|GREY)\b', '', s)
        # Remove remaining color codes like |cff...
        s = re.sub(r'\|c[0-9a-fA-F]{8}', '', s)
        s = re.sub(r'\|r', '', s)
        # Remove quotes and clean up spaces
        s = s.strip().strip('"\'').strip()
        # Collapse multiple spaces
        s = re.sub(r'\s+', ' ', s)
        return s

def load_loot_translations():
    path = os.path.join(ADDONS_DIR, "AtlasLoot", "Locale", "locale.cn.lua")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Extract entries: ["English Name"] = "Chinese Name"
    # Also handle [". string ."]
    kv_pairs = re.findall(r'\["(.*?)"\]\s*=\s*"(.*?)"', content)
    trans = dict(kv_pairs)
    
    # Add some common manual overrides if needed
    trans["Onyxia"] = "奥妮克希亚"
    return trans

def extract_quests():
    path = os.path.join(ADDONS_DIR, "AtlasQuest", "Locale", "localization.cn.lua")
    if not os.path.exists(path):
        return []
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    content = LuaParser.remove_comments(content)
    quests = []
    
    # Find all ["id"] = \d+ matches
    id_matches = list(re.finditer(r'\["id"\]\s*=\s*(\d+)', content))
    
    for match in id_matches:
        q_id = match.group(1)
        start_search = content.rfind('{', 0, match.start())
        block, _ = LuaParser.extract_table_content(content, start_search)
        
        if block and f'["id"] = {q_id}' in block:
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
                    # Capture EACH reward item. They are in nested tables like [1] = { ... }
                    # We look for all instances of "id" = ... "name" = ... within THIS reward_block
                    item_data_matches = re.finditer(r'\{', reward_block)
                    for idm in item_data_matches:
                        item_table, _ = LuaParser.extract_table_content(reward_block, idm.start())
                        if item_table:
                            i_id_m = re.search(r'\["id"\]\s*=\s*(\d+)', item_table)
                            i_name_m = re.search(r'\["name"\]\s*=\s*(.*?),', item_table)
                            if i_id_m and i_name_m:
                                rewards.append({
                                    "id": i_id_m.group(1),
                                    "name": LuaParser.clean_lua_string(i_name_m.group(1))
                                })

            quests.append({
                "id": q_id,
                "title": LuaParser.clean_lua_string(title_m.group(1)) if title_m else "Unknown",
                "aim": LuaParser.clean_lua_string(aim_m.group(1)) if aim_m else "",
                "note": LuaParser.clean_lua_string(note_m.group(1)) if note_m else "",
                "location": LuaParser.clean_lua_string(location_m.group(1)) if location_m else "",
                "level": level_m.group(1) if level_m else "",
                "attain": attain_m.group(1) if attain_m else "",
                "rewards": rewards
            })
            
    return quests

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
            
            # Find all top-level table assignments: Name = { ... }
            # Note: AtlasLoot often uses local AL = ... then AL["Key"] = { ... }
            table_defs = re.finditer(r'([A-Za-z0-9_]+)\s*=\s*\{', content)
            for td in table_defs:
                table_name = td.group(1)
                # Filter out meta-tables
                if table_name in ["AtlasLootBossButtons", "AtlasLootItems", "AL", "AtlasLoot_Data"]: continue
                
                table_block, _ = LuaParser.extract_table_content(content, td.start())
                if not table_block: continue
                
                # Boss name translation: table_name is the key
                boss_name = translations.get(table_name, table_name)
                
                # Extract items
                item_matches = re.finditer(r'\{\s*(\d+),', table_block)
                for im in item_matches:
                    item_line, _ = LuaParser.extract_table_content(table_block, im.start())
                    if item_line:
                        # Format check: { ID, icon, "=qQual=Name", ... }
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
                        # We use the reward name from the quest data (it's often already Chinese or English)
                        # but check if we have a better translation in loot
                        name = r['name']
                        f.write(f"- [{name}](../item/{r['id']}.md) (ID: {r['id']})\n")
                        seen_rewards.add(r['id'])
    
    # Generate Item files
    for i_id, i in items.items():
        filename = f"{i_id}.md"
        filepath = os.path.join(DOCS_BASE_DIR, "item", filename)
        
        # Translate name using the item's own name (from loot tables)
        name = translations.get(i['name'], i['name'])
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {name}\n\n")
            f.write(f"**物品 ID:** {i_id}  \n")
            f.write(f"**品质:** {i['quality']}  \n")
            f.write(f"**图标:** {i['icon']}  \n\n")
            
            f.write(f"## 获取途径\n")
            
            # Quests
            rewarded_by = [q for q in quests if any(r['id'] == i_id for r in q['rewards'])]
            if rewarded_by:
                f.write(f"### 任务奖励\n")
                for q in rewarded_by:
                    f.write(f"- [{q['title']}](../request/{q['id']}.md)\n")
            
            # Bosses
            if i['sources']:
                f.write(f"### 掉落/来源\n")
                for src in i['sources']:
                    f.write(f"- {src}\n")
            
            if not rewarded_by and not i['sources']:
                f.write(f"未知来源\n")

def run():
    print("Loading translations...")
    translations = load_loot_translations()
    
    print("Extracting Quest data...")
    quests = extract_quests()
    print(f"Found {len(quests)} quests.")
    
    print("Extracting Item and Source data...")
    items = extract_items_and_sources(translations)
    print(f"Found {len(items)} items in loot tables.")
    
    print("Generating Markdown files...")
    generate_markdown(quests, items, translations)
    
    print("Done.")

if __name__ == "__main__":
    run()

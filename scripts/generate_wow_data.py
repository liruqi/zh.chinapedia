import os
import re
import json

# Paths
ADDONS_DIR = r"D:\Games\TurtleWoW\Interface\AddOns"
# Note: Since docs/wow/turtle is now a submodule (remote repo wuguifu), 
# we should ensure we are writing to the correct path.
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
        s = re.sub(r'[A-Za-z_]+\.[A-Za-z0-9_]+', '', s)
        s = re.sub(r'\.\.', '', s)
        s = re.sub(r'\b(NORMAL|WHITE|RED|BLUE|GREEN|PURPLE|ORANGE|GREY|MAGE|PALADIN|WARRIOR|ROGUE|DRUID|HUNTER|SHAMAN|WARLOCK)\b', '', s)
        s = re.sub(r'\|c[0-9a-fA-F]{8}', '', s)
        s = re.sub(r'\|r', '', s)
        s = s.strip().strip('"\'').strip()
        s = s.replace('\\"', '"').replace("\\'", "'")
        s = re.sub(r'\s+', ' ', s)
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
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    content = LuaParser.remove_comments(content)
    match = re.search(r'AtlasQuest\.data\s*=\s*\{', content)
    if not match: return {}
    data_block, _ = LuaParser.extract_table_content(content, match.start())
    if not data_block: return {}
    
    quests = {}
    id_matches = re.finditer(r'\["id"\]\s*=\s*(\d+)', data_block)
    for match in id_matches:
        q_id = match.group(1)
        start_search = data_block.rfind('{', 0, match.start())
        block, _ = LuaParser.extract_table_content(data_block, start_search)
        if block and '["title"]' in block:
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
                    ri_matches = re.finditer(r'\["id"\]\s*=\s*(\d+)', reward_block)
                    for im in ri_matches:
                        i_start = reward_block.rfind('{', 0, im.start())
                        i_block, _ = LuaParser.extract_table_content(reward_block, i_start)
                        if i_block:
                            i_id = im.group(1)
                            i_name_m = re.search(r'\["name"\]\s*=\s*(.*?),', i_block)
                            i_icon_m = re.search(r'\["icon"\]\s*=\s*(.*?),', i_block)
                            i_qual_m = re.search(r'\["quality"\]\s*=\s*(\d+)', i_block)
                            if i_name_m:
                                rewards.append({
                                    "id": i_id,
                                    "name": LuaParser.clean_lua_string(i_name_m.group(1)),
                                    "icon": LuaParser.clean_lua_string(i_icon_m.group(1)) if i_icon_m else "",
                                    "quality": i_qual_m.group(1) if i_qual_m else "1"
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
    cn_path = os.path.join(ADDONS_DIR, "AtlasQuest", "Locale", "localization.cn.lua")
    cn_quests = get_quest_data_from_file(cn_path)
    en_path = os.path.join(ADDONS_DIR, "AtlasQuest", "Locale", "localization.en.lua")
    en_quests = get_quest_data_from_file(en_path)
    all_ids = set(cn_quests.keys()) | set(en_quests.keys())
    merged_quests = []
    for q_id in all_ids:
        cn_q = cn_quests.get(q_id, {})
        en_q = en_quests.get(q_id, {})
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
        if q["title"] != "Unknown" and q["title"].strip():
            merged_quests.append(q)
    return merged_quests

def extract_items_and_sources(translations):
    items = {}
    loot_dir = os.path.join(ADDONS_DIR, "AtlasLoot", "Database")
    if not os.path.exists(loot_dir): return items
    
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
                                items[i_id] = {"id": i_id, "name": i_name, "quality": i_qual, "icon": i_icon, "sources": []}
                            if boss_name not in items[i_id]["sources"]:
                                items[i_id]["sources"].append(boss_name)
    return items

def generate_markdown(quests, items, translations):
    ensure_dir(os.path.join(DOCS_BASE_DIR, "item"))
    ensure_dir(os.path.join(DOCS_BASE_DIR, "quest"))
    for q in quests:
        filename = f"{q['id']}.md"
        filepath = os.path.join(DOCS_BASE_DIR, "quest", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {q['title']}\n\n")
            f.write(f"**任务等级:** {q['level']}  \n")
            f.write(f"**最低等级:** {q['attain']}  \n")
            f.write(f"**开始地点:** {q['location']}  \n\n")
            f.write(f"## 任务目标\n{q['aim'] or '无'}\n\n")
            if q['note']: f.write(f"## 任务提示\n{q['note']}\n\n")
            if q['rewards']:
                f.write(f"## 任务奖励\n")
                seen_rewards = set()
                for r in q['rewards']:
                    if r['id'] not in seen_rewards and r['id'] != "0":
                        f.write(f"- [{r['name']}](../item/{r['id']}.md) (ID: {r['id']})\n")
                        seen_rewards.add(r['id'])
    
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
            rewarded_by = [q for q in quests if any(r['id'] == i_id for r in q['rewards'])]
            if rewarded_by:
                f.write(f"### 任务奖励\n")
                for q in rewarded_by:
                    f.write(f"- [{q['title']}](../quest/{q['id']}.md)\n")
            if i['sources']:
                f.write(f"### 掉落/来源\n")
                for src in i['sources']: f.write(f"- {src}\n")
            if not rewarded_by and not i['sources']: f.write(f"未知来源\n")

def run():
    translations = load_loot_translations()
    quests = extract_quests()
    items = extract_items_and_sources(translations)
    
    # NEW: Add missing items from quest rewards
    for q in quests:
        for r in q['rewards']:
            if r['id'] not in items and r['id'] != "0":
                items[r['id']] = {
                    "id": r['id'],
                    "name": r['name'],
                    "quality": r['quality'],
                    "icon": r['icon'],
                    "sources": []
                }
    
    generate_markdown(quests, items, translations)
    
    # Cleanup orphaned quest files
    all_quest_ids = {q['id'] for q in quests}
    request_dir = os.path.join(DOCS_BASE_DIR, "quest")
    if os.path.exists(request_dir):
        for filename in os.listdir(request_dir):
            if filename.endswith(".md"):
                q_id = filename.replace(".md", "")
                if q_id not in all_quest_ids:
                    os.remove(os.path.join(request_dir, filename))

    print("Done.")

if __name__ == "__main__":
    run()

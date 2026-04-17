-- WoW Data Generator v6
-- Includes NPC/Boss support and integrated cross-linking

local IS_WINDOWS = package.config:sub(1,1) == "\\"
local ADDONS_DIR = IS_WINDOWS and "D:/Games/TurtleWoW/Interface/AddOns" or "/Users/server/Documents/Otari98"
local DOCS_BASE_DIR = IS_WINDOWS and "D:/SRC/GitHub/liruqi/zh.chinapedia/docs/wow/turtle" or "/Users/server/Documents/zh.chinapedia/docs/wow/turtle"

-- Ensure directories exist
local function ensure_dir(path)
    if IS_WINDOWS then
        os.execute('mkdir "' .. path:gsub("/", "\\") .. '" 2>nul')
    else
        os.execute('mkdir -p "' .. path .. '"')
    end
end

ensure_dir(DOCS_BASE_DIR .. "/quest")
ensure_dir(DOCS_BASE_DIR .. "/item")
ensure_dir(DOCS_BASE_DIR .. "/dungeon")
ensure_dir(DOCS_BASE_DIR .. "/npc")
ensure_dir(DOCS_BASE_DIR .. "/set")

-- Helper: Deep Merge
local function deep_merge(target, source)
    for k, v in pairs(source) do
        if type(v) == "table" and type(target[k]) == "table" then
            deep_merge(target[k], v)
        else
            target[k] = v
        end
    end
end

-- ==========================================
-- MOCK WoW ENVIRONMENT
-- ==========================================
_G.GetLocale = function() return "zhCN" end

local function create_babble_mock(name)
    local mock = {}
    local translations = {}
    function mock:RegisterTranslations(locale, func)
        local data = func()
        for k, v in pairs(data) do translations[k] = v end
    end
    setmetatable(mock, {
        __index = function(t, k) 
            local val = translations[k]
            if val == nil or type(val) == "boolean" then return k end
            return val
        end,
        __call = function(t) return t end
    })
    return mock
end

local AceLocales = {}
_G.AceLibrary = function(name)
    if name:match("^AceLocale%-") then
        return {
            new = function(self, name)
            if not AceLocales[name] then
                local mock = create_babble_mock(name)
                mock.RegisterTranslations = function(m, lang, func)
                    if lang == "zhCN" then
                        local translations = func()
                        for k, v in pairs(translations) do
                            m[k] = v
                        end
                    end
                end
                AceLocales[name] = mock
            end
            return AceLocales[name]
        end
    }
    elseif name:match("^Babble%-") then
        return create_babble_mock(name)
    end
    return { new = function() return {} end }
end

_G.AtlasQuest = { L = {}, data = {} }
setmetatable(_G.AtlasQuest.L, { __index = function(t, k) return k end })

_G.AtlasLoot_Data = {}
_G.AtlasLootBossButtons = {}
_G.AtlasLootItems = {}
_G.AtlasMaps = {}

-- Colors
_G.GREY = "|cff999999"
_G.RED = "|cffff0000"
_G.WHITE = "|cffFFFFFF"
_G.GREEN = "|cff1eff00"
_G.BLUE = "|cff0070dd"
_G.NORMAL = "|cffFFd200"

-- Global Functions
_G.getn = function(t) if not t then return 0 end return #t end
_G.table.getn = _G.getn
_G.UnitName = function() return "Player" end
_G.UnitRace = function() return "Human", "Human" end
_G.ERR_QUEST_COMPLETE_S = "Quest %s complete"
_G.gsub = string.gsub

-- BOM-aware loader
local function load_addon_file(path)
    local f = io.open(path, "rb")
    if not f then return false end
    local content = f:read("*a")
    f:close()
    if content:sub(1,3) == "\239\187\191" then content = content:sub(4) end
    local func, err = loadstring(content, path)
    if not func then print("Error loading " .. path .. ": " .. err) return false end
    local env = setmetatable({}, {
        __index = _G,
        __newindex = function(t, k, v)
            if type(v) == "table" and type(_G[k]) == "table" then
                deep_merge(_G[k], v)
            else
                _G[k] = v
            end
        end
    })
    setfenv(func, env)
    local ok, res = pcall(func)
    if not ok then print("Error executing " .. path .. ": " .. tostring(res)) end
    return ok
end

-- ==========================================
-- LOADING DATA
-- ==========================================
print("Loading AtlasQuest data...")
load_addon_file(ADDONS_DIR .. "/AtlasQuest/Locale/localization.en.lua")
load_addon_file(ADDONS_DIR .. "/AtlasQuest/Locale/localization.cn.lua")
load_addon_file(ADDONS_DIR .. "/AtlasQuest/AtlasQuest.lua")

print("Loading AtlasLoot database...")
local loot_files = {"Instances.lua", "PvP.lua", "Crafting.lua", "Factions.lua", "Sets.lua", "WorldBosses.lua", "WorldEvents.lua"}
for _, file in ipairs(loot_files) do
    load_addon_file(ADDONS_DIR .. "/AtlasLoot/Database/" .. file)
end

print("Loading locales...")
load_addon_file(ADDONS_DIR .. "/AtlasLoot/Locale/locale.cn.lua")

print("Loading Atlas maps data...")
load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-enUS.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-zhCN.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/AtlasMaps.lua")

-- ==========================================
-- DATA PROCESSING
-- ==========================================
local function clean_string(s)
    if type(s) == "table" then
        local res = ""
        for _, v in ipairs(s) do res = res .. clean_string(v) end
        return res
    end
    if type(s) ~= "string" then return tostring(s or "") end
    s = s:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    s = s:gsub("<", "&lt;"):gsub(">", "&gt;")
    return s:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " ")
end

local function escape_pattern(s)
    return s:gsub("([%(%)%.%%%+%-%*%?%[%]%^%$])", "%%%1")
end

local set_tags = {}
local function load_set_tags()
    local path = ADDONS_DIR .. "/AtlasLoot/Core/TextParsing.lua"
    local f = io.open(path, "r")
    if not f then print("Warning: TextParsing.lua not found") return end
    local content = f:read("*a")
    f:close()
    
    local al_loot = AceLocales["AtlasLoot"] or create_babble_mock("AtlasLoot")
    for tag, key in content:gmatch('%["#([^#]+)#"%]%s*=%s*AL%["([^"]+)"%]') do
        set_tags[tag] = al_loot[key]
    end
    print("Loaded " .. (function() local c=0 for _ in pairs(set_tags) do c=c+1 end return c end)() .. " set tags")
end
load_set_tags()

local translated_atlas = AceLocales["Atlas"] or {}

-- Quests
local all_quests = {}
local function find_quests(tbl)
    if not tbl then return end
    if tbl.id and type(tbl.id) ~= "table" and tbl.title then all_quests[tostring(tbl.id)] = tbl return end
    for k, v in pairs(tbl) do
        if type(v) == "table" and k ~= "rewards" then find_quests(v) end
    end
end
find_quests(AtlasQuest.data)

-- Items
local items = {}
local function collect_items(tbl, source_name)
    if type(tbl) ~= "table" then return end
    for i, entry in ipairs(tbl) do
        if type(entry) == "table" and entry[1] and entry[1] ~= 0 then
            local i_id = ""
            if type(entry[1]) == "table" then
                local raw_name = clean_string(entry[3])
                local sid = nil
                for tag in raw_name:gmatch("#([^#]+)#") do
                    if not tag:match("^[as]%d+$") and not tag:match("^h%d+$") and not tag:match("^w%d+$") then
                        sid = tag
                        break
                    end
                end
                sid = sid or raw_name:match("#([^#]+)#")
                
                local sid_lower = sid and sid:lower() or "unknown"
                i_id = "set/" .. sid_lower
            else
                i_id = tostring(entry[1])
            end
            
            local i_name = clean_string(entry[3])
            if not items[i_id] then
                items[i_id] = {id=i_id, name=i_name, icon=entry[2], sources={}, quality=1}
                local q = i_name:match("^=q(%d)=")
                if q then items[i_id].quality = q items[i_id].name = i_name:gsub("^=q%d=", "") end
            end
            table.insert(items[i_id].sources, source_name)
        end
    end
end

for k, v in pairs(AtlasLoot_Data) do
    if type(v) == "table" then
        for sub_k, sub_v in pairs(v) do collect_items(sub_v, sub_k) end
    end
end

-- Merge rewards into item list
for _, q in pairs(all_quests) do
    if q.rewards then
        for _, r in ipairs(q.rewards) do
            local i_id = (r.id and type(r.id) ~= "table") and tostring(r.id) or nil
            if i_id and i_id ~= "0" and not items[i_id] then
                items[i_id] = {id=i_id, name=clean_string(r.name), icon=r.icon, sources={}, quality=r.quality or 1}
            end
        end
    end
end

-- ==========================================
-- NPC GENERATION LOGIC
-- ==========================================
local npcs = {}
local npc_names_to_ids = {}

for mapKey, pois in pairs(AtlasMaps) do
    if type(pois) == "table" and pois.ZoneName and pois.LevelRange and pois.PlayerLimit then
        local dungeon_name = clean_string(translated_atlas[pois.ZoneName[1]] or pois.ZoneName[1])
        for i, poi in ipairs(pois) do
            if type(poi) == "table" and poi[2] == 2 and poi[3] and type(poi[3]) ~= "table" then -- NPC type
                local id = tostring(poi[3])
                local name = clean_string(poi[1]):gsub("^%d+%)%s+", "") -- Remove "1) " prefix
                if id ~= "-1" then
                    if not npcs[id] then
                        npcs[id] = {id=id, name=name, locations={}, drops={}, quests={}}
                    end
                    table.insert(npcs[id].locations, {mapKey=mapKey, dungeonName=dungeon_name})
                    npc_names_to_ids[name] = id
                    
                    -- Link Loot
                    local loot_labels = AtlasLootBossButtons[mapKey]
                    if loot_labels and loot_labels[i] and loot_labels[i] ~= "" then
                        local loot_label = loot_labels[i]
                        local loot_table = nil
                        -- Try finding the loot table in DUNGEONS category first
                        if AtlasLoot_Data["DUNGEONS"] and AtlasLoot_Data["DUNGEONS"][mapKey] then
                            loot_table = AtlasLoot_Data["DUNGEONS"][mapKey][loot_label]
                        end
                        -- Fallback to searching all top categories
                        if not loot_table then
                            for cat, maps in pairs(AtlasLoot_Data) do
                                if maps[mapKey] and maps[mapKey][loot_label] then
                                    loot_table = maps[mapKey][loot_label]
                                    break
                                end
                            end
                        end
                        
                        if loot_table then
                            for _, loot_entry in ipairs(loot_table) do
                                if type(loot_entry) == "table" and loot_entry[1] and loot_entry[1] ~= 0 then
                                    table.insert(npcs[id].drops, {id=tostring(loot_entry[1]), name=clean_string(loot_entry[3])})
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end

-- Associate Quests with NPCs
for id, q in pairs(all_quests) do
    local q_title = clean_string(q.title)
    local q_aim = clean_string(q.aim)
    local q_loc = clean_string(q.location)
    
    for npc_id, npc in pairs(npcs) do
        if q_title:find(npc.name, 1, true) or q_aim:find(npc.name, 1, true) or q_loc:find(npc.name, 1, true) then
            table.insert(npc.quests, {id=id, title=q_title})
        end
    end
end

-- ==========================================
-- GENERATING DOCUMENTATION
-- ==========================================
print("Generating NPC files...")
for id, npc in pairs(npcs) do
    local f = io.open(DOCS_BASE_DIR .. "/npc/" .. id .. ".md", "w")
    if f then
        f:write("# " .. npc.name .. "\n\n")
        f:write("**NPC ID:** " .. id .. "  \n")
        f:write("**出现地点:**\n")
        for _, loc in ipairs(npc.locations) do
            f:write("- [" .. loc.dungeonName .. "](../dungeon/" .. loc.mapKey .. ".md)\n")
        end
        f:write("\n")
        
        if #npc.drops > 0 then
            f:write("## 装备掉落\n")
            f:write("| 物品 | ID |\n")
            f:write("| :--- | :--- |\n")
            for _, drop in ipairs(npc.drops) do
                f:write("| [" .. drop.name .. "](../item/" .. drop.id .. ".md) | " .. drop.id .. " |\n")
            end
            f:write("\n")
        end
        
        if #npc.quests > 0 then
            f:write("## 相关任务\n")
            for _, q in ipairs(npc.quests) do
                f:write("- [" .. q.title .. "](../quest/" .. q.id .. ".md)\n")
            end
            f:write("\n")
        end
        f:close()
    end
end

print("Generating Dungeon files...")
local dungeon_list = {}
for mapKey, data in pairs(AtlasMaps) do
    if type(data) == "table" and data.ZoneName and data.LevelRange and data.PlayerLimit then
        local d_name = clean_string(translated_atlas[data.ZoneName[1]] or data.ZoneName[1])
        table.insert(dungeon_list, {key=mapKey, name=d_name, level=data.LevelRange})
        local f = io.open(DOCS_BASE_DIR .. "/dungeon/" .. mapKey .. ".md", "w")
        if f then
            f:write("# " .. d_name .. "\n\n")
            f:write("![" .. d_name .. "](" .. mapKey .. ".png)\n\n")
            f:write("**位置:** " .. clean_string(translated_atlas[data.Location[1]] or data.Location[1]) .. "  \n")
            f:write("**适用等级:** " .. clean_string(data.LevelRange or "??") .. " (" .. clean_string(data.MinLevel or "??") .. "+)  \n")
            f:write("**人数上限:** " .. clean_string(data.PlayerLimit or "??") .. "人  \n\n")
            f:write("## 关键点/首领\n")
            for i, poi in ipairs(data) do
                if type(poi) == "table" and poi[1] then
                    local name = clean_string(poi[1]):gsub("^%d+%)%s+", "")
                    local id = ""
                    if poi[3] then
                        if type(poi[3]) == "table" then
                            local raw_label = clean_string(poi[1])
                            local sid = nil
                            for tag in raw_label:gmatch("#([^#]+)#") do
                                if not tag:match("^[as]%d+$") then
                                    sid = tag
                                    break
                                end
                            end
                            sid = sid or raw_label:match("#([^#]+)#")
                            
                            id = "../set/" .. (sid and sid:lower() or "unknown")
                        else
                            id = tostring(poi[3])
                        end
                    end

                    f:write("- ")
                    if id ~= "" and id ~= "-1" then
                        if id:find("^%.%.%/outfit%/") then
                            f:write("[" .. clean_string(poi[1]) .. "](" .. id .. ".md)")
                        elseif poi[2] == 2 then
                            f:write("[" .. clean_string(poi[1]) .. "](../npc/" .. id .. ".md)")
                        else
                            f:write(clean_string(poi[1]))
                        end
                    else
                        f:write(clean_string(poi[1]))
                    end
                    f:write("\n")
                end
            end
            
            local q_idx = AtlasQuest.AtlasMapToDungeon[mapKey]
            if q_idx and AtlasQuest.data[q_idx] then
                f:write("\n## 相关任务\n")
                for _, fact in ipairs({{"联盟", 1}, {"部落", 2}}) do
                    local quests = AtlasQuest.data[q_idx][fact[2]]
                    if quests and #quests > 0 then
                        f:write("### " .. fact[1] .. "\n")
                        for _, q in ipairs(quests) do
                            f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n")
                        end
                    end
                end
            end
            f:close()
        end
    end
end

-- Dungeon README
table.sort(dungeon_list, function(a, b) return (a.level or "") < (b.level or "") end)
local idx_f = io.open(DOCS_BASE_DIR .. "/dungeon/README.md", "w")
if idx_f then
    idx_f:write("# 副本列表\n\n| 副本名称 | 等级范围 | 链接 |\n| :--- | :--- | :--- |\n")
    for _, d in ipairs(dungeon_list) do 
        idx_f:write("| " .. d.name .. " | " .. (d.level or "??") .. " | [进入文档](" .. d.key .. ".md) |\n") 
    end
    idx_f:close()
end

print("Generating Quest files...")
for id, q in pairs(all_quests) do
    local q_title = clean_string(q.title)
    local f = io.open(DOCS_BASE_DIR .. "/quest/" .. id .. ".md", "w")
    if f then
        f:write("# " .. q_title .. "\n\n")
        f:write("**任务等级:** " .. (q.level or "") .. "  \n")
        f:write("**起始等级:** " .. (q.attain or "") .. "  \n")
        
        -- Link NPC in location/aim
        local loc_str = clean_string(q.location)
        for name, n_id in pairs(npc_names_to_ids) do
            local pat = escape_pattern(name)
            loc_str = loc_str:gsub(pat, "["..name.."](../npc/"..n_id..".md)")
        end
        f:write("**开始地点:** " .. loc_str .. "  \n\n")
        
        local aim_str = clean_string(q.aim or "无")
        for name, n_id in pairs(npc_names_to_ids) do
            local pat = escape_pattern(name)
            aim_str = aim_str:gsub(pat, "["..name.."](../npc/"..n_id..".md)")
        end
        f:write("## 任务目标\n" .. aim_str .. "\n\n")
        
        if q.note then f:write("## 任务提示\n" .. clean_string(q.note) .. "\n\n") end
        if q.rewards and #q.rewards > 0 then
            f:write("## 任务奖励\n")
            for _, r in ipairs(q.rewards) do
                if r.id ~= 0 then f:write("- [" .. clean_string(r.name) .. "](../item/" .. r.id .. ".md)\n") end
            end
        end
        f:close()
    end
end

local item_to_sets = {}
print("Generating Set files...")
local set_registry = AtlasLoot_Data["AtlasLootSetItems"] or {}
local set_count = 0
for key, data in pairs(set_registry) do
    local sid = key:lower()
    local name = key
    local items_in_set = {}
    
    local function scan_set(tbl)
        if type(tbl) ~= "table" then return end
        for i, entry in ipairs(tbl) do
            if type(entry) == "number" and entry ~= 0 then
                table.insert(items_in_set, entry)
            elseif type(entry) == "table" then
                if type(entry[1]) == "number" and entry[1] ~= 0 then
                    table.insert(items_in_set, entry[1])
                    if entry[3] and type(entry[3]) == "string" then
                        for tag in entry[3]:gmatch("#([^#]+)#") do
                            if set_tags[tag] and not tag:match("^[as]%d+$") then
                                name = set_tags[tag]
                                break
                            end
                        end
                    end
                else
                    scan_set(entry)
                end
                
                if entry[1] == 0 and entry[3] and type(entry[3]) == "string" then
                    local tag = entry[3]:match("#([^#]+)#")
                    if tag and set_tags[tag] then name = set_tags[tag] end
                end
            end
        end
    end
    scan_set(data)
    
    if #items_in_set > 0 then
        local unique_items = {}
        for _, item_id in ipairs(items_in_set) do
            if not unique_items[item_id] then
                unique_items[item_id] = true
                -- Add to global mapping for backward links
                if not item_to_sets[tostring(item_id)] then item_to_sets[tostring(item_id)] = {} end
                table.insert(item_to_sets[tostring(item_id)], { sid = sid, name = name })
            end
        end

        local of = io.open(DOCS_BASE_DIR .. "/set/" .. sid .. ".md", "w")
        if of then
            of:write("# " .. name .. "\n\n")
            of:write("## 包含物品\n")
            for item_id, _ in pairs(unique_items) do
                of:write("- [" .. item_id .. "](../item/" .. item_id .. ".md)\n")
            end
            of:close()
            set_count = set_count + 1
        end
    end
end
print("Generated " .. set_count .. " set files.")

print("Generating Item files...")
for id, i in pairs(items) do
    local f = io.open(DOCS_BASE_DIR .. "/item/" .. id .. ".md", "w")
    if f then
        f:write("# " .. clean_string(i.name) .. "\n\n")
        f:write("**物品 ID:** " .. clean_string(id) .. "  \n**图标:** " .. clean_string(i.icon or "") .. "  \n\n## 获取途径\n")
        local rewarded_by = {}
        for _, q in pairs(all_quests) do
            if q.rewards then
                for _, r in ipairs(q.rewards) do
                    if tostring(r.id) == id then table.insert(rewarded_by, q) break end
                end
            end
        end
        if #rewarded_by > 0 then
            f:write("### 任务奖励\n")
            for _, q in ipairs(rewarded_by) do f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n") end
        end
        if #i.sources > 0 then
            f:write("### 掉落/来源\n")
            for _, src in ipairs(i.sources) do f:write("- " .. src .. "\n") end
        end

        -- Backward links to sets
        if item_to_sets[id] then
            f:write("\n## 属于套装\n")
            for _, s in ipairs(item_to_sets[id]) do
                f:write("- [" .. s.name .. "](../set/" .. s.sid .. ".md)\n")
            end
        end
        
        f:close()
    end
end
print("Generated " .. set_count .. " set files.")

print("Done.")

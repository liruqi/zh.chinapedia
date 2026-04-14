-- WoW Data Generator v5
-- Optimized for rilua (WoW Emulation environment)
-- Includes Dungeon/Instance support and map integration

local ADDONS_DIR = "D:/Games/TurtleWoW/Interface/AddOns"
local DOCS_BASE_DIR = "D:/SRC/GitHub/liruqi/zh.chinapedia/docs/wow/turtle"

-- Ensure directories exist
local function ensure_dir(path)
    os.execute('mkdir "' .. path:gsub("/", "\\") .. '" 2>nul')
end

ensure_dir(DOCS_BASE_DIR .. "/quest")
ensure_dir(DOCS_BASE_DIR .. "/item")
ensure_dir(DOCS_BASE_DIR .. "/dungeon")

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
            new = function(self, addon_name)
                if not AceLocales[addon_name] then
                    AceLocales[addon_name] = create_babble_mock(addon_name)
                end
                return AceLocales[addon_name]
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
load_addon_file(ADDONS_DIR .. "/AtlasQuest/AtlasQuest.lua") -- For AtlasMapToDungeon

print("Loading AtlasLoot database...")
local loot_files = {"Instances.lua", "PvP.lua", "Crafting.lua", "Factions.lua", "Sets.lua", "WorldBosses.lua", "WorldEvents.lua"}
for _, file in ipairs(loot_files) do
    load_addon_file(ADDONS_DIR .. "/AtlasLoot/Database/" .. file)
end

print("Loading Atlas maps data...")
load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-enUS.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-zhCN.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/AtlasMaps.lua")

-- ==========================================
-- DATA PROCESSING
-- ==========================================
local function clean_string(s)
    if type(s) == "table" then return "{table}" end
    if type(s) ~= "string" then return tostring(s or "") end
    s = s:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    return s:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " ")
end

local translated_atlas = AceLocales["Atlas"] or {}

-- Quests
local all_quests = {}
local function find_quests(tbl)
    if not tbl then return end
    if tbl.id and tbl.title then all_quests[tostring(tbl.id)] = tbl return end
    for k, v in pairs(tbl) do
        if type(v) == "table" and k ~= "rewards" then find_quests(v) end
    end
end
find_quests(AtlasQuest.data)

-- Items
local items = {}
local items_by_npc = {} -- Map NPC ID -> {item_id, ...}

local function collect_items(tbl, source_name)
    if type(tbl) ~= "table" then return end
    for _, entry in ipairs(tbl) do
        if type(entry) == "table" and entry[1] and entry[1] ~= 0 then
            local i_id = tostring(entry[1])
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
            local i_id = tostring(r.id)
            if i_id ~= "0" and not items[i_id] then
                items[i_id] = {id=i_id, name=clean_string(r.name), icon=r.icon, sources={}, quality=r.quality or 1}
            end
        end
    end
end

-- ==========================================
-- GENERATING DOCUMENTATION
-- ==========================================
print("Generating Dungeon files...")
local dungeon_list = {}

for mapKey, data in pairs(AtlasMaps) do
    if type(data) == "table" and data.ZoneName then
        local d_name = clean_string(translated_atlas[data.ZoneName[1]] or data.ZoneName[1])
        table.insert(dungeon_list, {key=mapKey, name=d_name, level=data.LevelRange})
        
        local f = io.open(DOCS_BASE_DIR .. "/dungeon/" .. mapKey .. ".md", "w")
        if f then
            f:write("# " .. clean_string(d_name) .. "\n\n")
            f:write("![" .. clean_string(d_name) .. "](" .. clean_string(mapKey) .. ".png)\n\n")
            f:write("**位置:** " .. clean_string(translated_atlas[data.Location[1]] or data.Location[1]) .. "  \n")
            f:write("**适用等级:** " .. clean_string(data.LevelRange or "??") .. " (" .. clean_string(data.MinLevel or "??") .. "+)  \n")
            f:write("**人数上限:** " .. clean_string(data.PlayerLimit or "??") .. "人  \n\n")
            
            f:write("## 关键点/首领\n")
            for i, poi in ipairs(data) do
                if type(poi) == "table" and poi[1] then
                    local poi_text = clean_string(poi[1])
                    f:write("- " .. poi_text)
                    if poi[2] == 2 and poi[3] then -- NPC type
                        f:write(" ([掉落](#boss-" .. clean_string(poi[3]) .. "))")
                    end
                    f:write("\n")
                end
            end
            
            -- Quests for this dungeon
            local q_idx = AtlasQuest.AtlasMapToDungeon[mapKey]
            if q_idx and AtlasQuest.data[q_idx] then
                f:write("\n## 相关任务\n")
                local factions = { {"联盟", 1}, {"部落", 2} }
                for _, fact in ipairs(factions) do
                    local quests = AtlasQuest.data[q_idx][fact[2]]
                    if quests and #quests > 0 then
                        f:write("### " .. fact[1] .. "\n")
                        for _, q in ipairs(quests) do
                            if q.id then
                                f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n")
                            end
                        end
                    end
                end
            end
            f:close()
        end
    end
end

-- Generate Index for Dungeons
table.sort(dungeon_list, function(a, b) return (a.level or "") < (b.level or "") end)
local idx_f = io.open(DOCS_BASE_DIR .. "/dungeon/README.md", "w")
if idx_f then
    idx_f:write("# 副本列表\n\n")
    idx_f:write("| 副本名称 | 等级范围 | 链接 |\n")
    idx_f:write("| :--- | :--- | :--- |\n")
    for _, d in ipairs(dungeon_list) do
        idx_f:write("| " .. d.name .. " | " .. (d.level or "??") .. " | [进入文档](" .. d.key .. ".md) |\n")
    end
    idx_f:close()
end

print("Generating Quest files...")
for id, q in pairs(all_quests) do
    local f = io.open(DOCS_BASE_DIR .. "/quest/" .. id .. ".md", "w")
    if f then
        f:write("# " .. clean_string(q.title) .. "\n\n")
        f:write("**任务等级:** " .. (q.level or "") .. "  \n")
        f:write("**起始等级:** " .. (q.attain or "") .. "  \n")
        f:write("**开始地点:** " .. clean_string(q.location or "") .. "  \n\n")
        f:write("## 任务目标\n" .. clean_string(q.aim or "无") .. "\n\n")
        if q.note then f:write("## 任务提示\n" .. clean_string(q.note) .. "\n\n") end
        if q.rewards and #q.rewards > 0 then
            f:write("## 任务奖励\n")
            for _, r in ipairs(q.rewards) do
                if r.id ~= 0 then
                    f:write("- [" .. clean_string(r.name) .. "](../item/" .. r.id .. ".md)\n")
                end
            end
        end
        f:close()
    end
end

print("Generating Item files...")
for id, i in pairs(items) do
    local f = io.open(DOCS_BASE_DIR .. "/item/" .. id .. ".md", "w")
    if f then
        f:write("# " .. clean_string(i.name) .. "\n\n")
        f:write("**物品 ID:** " .. clean_string(id) .. "  \n")
        f:write("**图标:** " .. clean_string(i.icon or "") .. "  \n\n")
        f:write("## 获取途径\n")
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
            for _, q in ipairs(rewarded_by) do
                f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n")
            end
        end
        if #i.sources > 0 then
            f:write("### 掉落/来源\n")
            for _, src in ipairs(i.sources) do f:write("- " .. src .. "\n") end
        end
        f:close()
    end
end

print("Done.")

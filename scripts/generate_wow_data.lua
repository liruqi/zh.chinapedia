-- WoW Data Generator in Lua 5.1
-- Optimized for rilua (WoW Emulation environment)

local ADDONS_DIR = "D:/Games/TurtleWoW/Interface/AddOns"
local DOCS_BASE_DIR = "D:/SRC/GitHub/liruqi/zh.chinapedia/docs/wow/turtle"

-- Ensure directories exist
local function ensure_dir(path)
    os.execute('mkdir "' .. path:gsub("/", "\\") .. '" 2>nul')
end

ensure_dir(DOCS_BASE_DIR .. "/quest")
ensure_dir(DOCS_BASE_DIR .. "/item")

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

-- Mock basic WoW globals strictly in _G
_G.GetLocale = function() return "zhCN" end
_G.AceLibrary = function()
    local lib = {}
    function lib:new()
        local al = {}
        local translations = {}
        function al:RegisterTranslations(locale, func)
            local data = func()
            for k, v in pairs(data) do translations[k] = v end
        end
        setmetatable(al, {
            __index = function(t, k) return translations[k] or k end,
            __call = function(t, k) return t end
        })
        return al
    end
    return lib
end

_G.AtlasQuest = { L = {}, data = {} }
setmetatable(_G.AtlasQuest.L, { __index = function(t, k) return k end })

_G.AtlasLoot_Data = {}
_G.AtlasLootBossButtons = {}
_G.AtlasLootItems = {}

-- Color constants
_G.GREY = "|cff999999"
_G.RED = "|cffff0000"
_G.WHITE = "|cffFFFFFF"
_G.GREEN = "|cff1eff00"
_G.PURPLE = "|cff9F3FFF"
_G.BLUE = "|cff0070dd"
_G.ORANGE = "|cffFF8400"
_G.NORMAL = "|cffFFd200"

-- BOM-aware file loader WITH MERGING
local function load_addon_file(path)
    local f = io.open(path, "rb")
    if not f then 
        print("  Error: Could not open " .. path)
        return false 
    end
    local content = f:read("*a")
    f:close()
    
    -- Strip UTF-8 BOM if present
    if content:sub(1,3) == "\239\187\191" then
        content = content:sub(4)
    end
    
    local func, err = loadstring(content, path)
    if not func then
        print("  Syntax Error in " .. path .. ": " .. err)
        return false
    end
    
    -- Create environment that merges global assignments
    local env = {}
    setmetatable(env, {
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
    local ok, msg = pcall(func)
    if not ok then
        print("  Runtime Error in " .. path .. ": " .. msg)
        return false
    end
    return true
end

print("Loading AtlasQuest data...")
-- Load En first (base) then Cn (translations)
load_addon_file(ADDONS_DIR .. "/AtlasQuest/Locale/localization.en.lua")
load_addon_file(ADDONS_DIR .. "/AtlasQuest/Locale/localization.cn.lua")

print("Loading AtlasLoot database...")
local loot_files = {
    "/AtlasLoot/Database/Instances.lua",
    "/AtlasLoot/Database/PvP.lua",
    "/AtlasLoot/Database/Crafting.lua",
    "/AtlasLoot/Database/Factions.lua",
    "/AtlasLoot/Database/Sets.lua",
    "/AtlasLoot/Database/WorldBosses.lua",
    "/AtlasLoot/Database/WorldEvents.lua"
}

for _, file in ipairs(loot_files) do
    print("  Processing " .. file)
    load_addon_file(ADDONS_DIR .. file)
end

-- String cleaning function
local function clean_string(s)
    if type(s) ~= "string" then return "" end
    s = s:gsub("|c%x%x%x%x%x%x%x%x", "")
    s = s:gsub("|r", "")
    s = s:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " ")
    return s
end

-- Recursive mission finder
local function find_all_quests(tbl, collected)
    if type(tbl) ~= "table" then return end
    if tbl.id and tbl.title then
        collected[tostring(tbl.id)] = tbl
        return
    end
    for k, v in pairs(tbl) do
        if type(v) == "table" and k ~= "rewards" then
            find_all_quests(v, collected)
        end
    end
end

local all_quests = {}
find_all_quests(AtlasQuest.data, all_quests)

-- Count dungeons
local dungeon_count = 0
for k, v in pairs(AtlasQuest.data) do dungeon_count = dungeon_count + 1 end
print("Found " .. dungeon_count .. " dungeon entries in AtlasQuest.data")

print("Collecting items and sources...")
local items = {}

local function collect_loot(tbl, source_name)
    if type(tbl) ~= "table" then return end
    for _, entry in ipairs(tbl) do
        if type(entry) == "table" and entry[1] and entry[1] ~= 0 then
            local i_id = tostring(entry[1])
            local i_name = entry[3]
            if type(i_name) == "string" then
                local qual, name = i_name:match("^=q(%d)=(.*)")
                if not qual then name = i_name end
                
                if not items[i_id] then
                    items[i_id] = {
                        id = i_id,
                        name = name,
                        quality = qual or "1",
                        icon = entry[2] or "",
                        sources = {}
                    }
                end
                local seen_src = false
                for _, s in ipairs(items[i_id].sources) do if s == source_name then seen_src = true break end end
                if not seen_src then table.insert(items[i_id].sources, source_name) end
            end
        end
    end
end

for k, v in pairs(_G) do
    if type(v) == "table" and k:match("^AtlasLoot") == nil and k ~= "_G" then
        if v[1] and type(v[1]) == "table" and v[1][1] and type(v[1][1]) == "number" then
            collect_loot(v, k)
        end
    end
end

for _, q in pairs(all_quests) do
    if q.rewards then
        for _, r in ipairs(q.rewards) do
            local i_id = tostring(r.id)
            if i_id ~= "0" and not items[i_id] then
                items[i_id] = {
                    id = i_id,
                    name = r.name or "Unknown Item",
                    quality = r.quality or "1",
                    icon = r.icon or "",
                    sources = {}
                }
            end
        end
    end
end

print("Generating Markdown files...")

-- Quests
local q_count = 0
for id, q in pairs(all_quests) do
    q_count = q_count + 1
    local f = io.open(DOCS_BASE_DIR .. "/quest/" .. id .. ".md", "w")
    if f then
        f:write("# " .. clean_string(q.title) .. "\n\n")
        f:write("**任务等级:** " .. (q.level or "") .. "  \n")
        f:write("**最低等级:** " .. (q.attain or "") .. "  \n")
        f:write("**开始地点:** " .. clean_string(q.location or "") .. "  \n\n")
        f:write("## 任务目标\n" .. clean_string(q.aim or "无") .. "\n\n")
        if q.note then f:write("## 任务提示\n" .. clean_string(q.note) .. "\n\n") end
        if q.rewards and #q.rewards > 0 then
            f:write("## 任务奖励\n")
            local seen = {}
            for _, r in ipairs(q.rewards) do
                if r.id ~= 0 and not seen[r.id] then
                    f:write("- [" .. clean_string(r.name) .. "](../item/" .. r.id .. ".md) (ID: " .. r.id .. ")\n")
                    seen[r.id] = true
                end
            end
        end
        f:close()
    end
end

-- Items
local i_count = 0
for i_id, i in pairs(items) do
    i_count = i_count + 1
    local f = io.open(DOCS_BASE_DIR .. "/item/" .. i_id .. ".md", "w")
    if f then
        f:write("# " .. clean_string(i.name or "Unknown Item") .. "\n\n")
        f:write("**物品 ID:** " .. i_id .. "  \n")
        f:write("**品质:** " .. (i.quality or "1") .. "  \n")
        f:write("**图标:** " .. (i.icon or "") .. "  \n\n")
        f:write("## 获取途径\n")
        
        local printed = false
        local rewarded_by = {}
        for _, q in pairs(all_quests) do
            if q.rewards then
                for _, r in ipairs(q.rewards) do
                    if tostring(r.id) == i_id then
                        table.insert(rewarded_by, q)
                        break
                    end
                end
            end
        end
        
        if #rewarded_by > 0 then
            f:write("### 任务奖励\n")
            for _, q in ipairs(rewarded_by) do
                f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n")
            end
            printed = true
        end
        
        if #i.sources > 0 then
            f:write("### 掉落/来源\n")
            for _, src in ipairs(i.sources) do f:write("- " .. src .. "\n") end
            printed = true
        end
        if not printed then f:write("未知来源\n") end
        f:close()
    end
end

print(string.format("Done. Generated %d quests and %d items.", q_count, i_count))

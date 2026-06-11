
local ADDONS_DIR = "/Users/server/Documents/Otari98"

-- Mock environment
_G.GetLocale = function() return "zhCN" end
local function clean_string(s) return tostring(s or "") end
local function create_babble_mock(name) return setmetatable({}, {__index = function(t,k) return k end, __call = function(t) return t end}) end
_G.AceLibrary = function(name) return { new = function() return create_babble_mock() end } end
_G.AtlasQuest = { L = {}, data = {} }
_G.AtlasLoot_Data = {}
_G.AtlasMaps = {}
_G.gsub = string.gsub

local function load_addon_file(path)
    local f = io.open(path, "rb")
    if not f then return end
    local content = f:read("*a")
    f:close()
    if content:sub(1,3) == "\239\187\191" then content = content:sub(4) end
    local func, err = loadstring(content, path)
    if not func then return end
    setfenv(func, _G)
    pcall(func)
end

load_addon_file(ADDONS_DIR .. "/AtlasQuest/AtlasQuest.lua")
local loot_files = {"Instances.lua", "PvP.lua", "Crafting.lua", "Factions.lua", "Sets.lua", "WorldBosses.lua", "WorldEvents.lua"}
for _, file in ipairs(loot_files) do
    load_addon_file(ADDONS_DIR .. "/AtlasLoot/Database/" .. file)
end

local quest_tables = 0
local function find_quests(tbl)
    if not tbl then return end
    if tbl.id and type(tbl.id) == "table" and tbl.title then 
        print("Found table ID in quest: " .. tostring(tbl.title))
        quest_tables = quest_tables + 1
    end
    for k, v in pairs(tbl) do
        if type(v) == "table" and k ~= "rewards" then find_quests(v) end
    end
end
find_quests(AtlasQuest.data)

local item_tables = 0
local function collect_items(tbl)
    if type(tbl) ~= "table" then return end
    for i, entry in ipairs(tbl) do
        if type(entry) == "table" and entry[1] and type(entry[1]) == "table" then
            print("Found table ID in item: " .. tostring(entry[3]))
            item_tables = item_tables + 1
        end
    end
end

for k, v in pairs(AtlasLoot_Data) do
    if type(v) == "table" then
        for sub_k, sub_v in pairs(v) do collect_items(sub_v) end
    end
end

print("Quest tables found: " .. quest_tables)
print("Item tables found: " .. item_tables)


local ADDONS_DIR = "/Users/server/Documents/Otari98"

-- Mock environment
_G.AtlasMaps = {}
_G.AtlasLoot_Data = {}
_G.AceLibrary = function() return { new = function() return setmetatable({}, {__index = function(t,k) return k end}) end } end
_G.AceLocales = {}

local function load_addon_file(path)
    local f = io.open(path, "rb")
    if not f then print("Failed to load: " .. path) return end
    local content = f:read("*a")
    f:close()
    if content:sub(1,3) == "\239\187\191" then content = content:sub(4) end
    local func, err = loadstring(content, path)
    if not func then print("Parse error " .. path .. ": " .. err) return end
    setfenv(func, _G)
    pcall(func)
end

load_addon_file(ADDONS_DIR .. "/Atlas/AtlasMaps.lua")
load_addon_file(ADDONS_DIR .. "/AtlasLoot/Database/Instances.lua")

print("Deadmines AtlasMaps POIs:")
local dm_map = AtlasMaps["Deadmines"]
if dm_map then
    for i, poi in ipairs(dm_map) do
        print(string.format("%d: Name=%s, Type=%s, ID=%s", i, tostring(poi[1]), tostring(poi[2]), tostring(poi[3])))
    end
else
    print("Deadmines not found in AtlasMaps")
end

print("\nTheDeadmines AtlasLoot entries:")
local dm_loot = AtlasLoot_Data["TheDeadmines"]
if dm_loot then
    for i, key in ipairs(dm_loot) do
        print(string.format("%d: Key=%s", i, tostring(key)))
    end
else
    print("TheDeadmines not found in AtlasLoot_Data")
end

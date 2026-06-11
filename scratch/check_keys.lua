
local ADDONS_DIR = "/Users/server/Documents/Otari98"

-- Mock environment
_G.AtlasLoot_Data = {}
_G.AceLibrary = function() return { new = function() return setmetatable({}, {__index = function(t,k) return k end}) end } end

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

load_addon_file(ADDONS_DIR .. "/AtlasLoot/Database/Sets.lua")

local keys = {}
for k, _ in pairs(AtlasLoot_Data["AtlasLootSetItems"]) do
    table.insert(keys, k)
end
table.sort(keys)
for _, k in ipairs(keys) do
    if k:lower():find("t0") then
        print(k)
    end
end

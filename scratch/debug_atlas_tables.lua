
local ADDONS_DIR = "/Users/server/Documents/Otari98"

-- Mock environment
_G.GetLocale = function() return "zhCN" end
local function create_babble_mock(name) return setmetatable({}, {__index = function(t,k) return k end, __call = function(t) return t end}) end
local AceLocales = {}
_G.AceLibrary = function(name) return { new = function() return create_babble_mock() end } end
_G.AtlasQuest = { L = {}, data = {} }
_G.AtlasLoot_Data = {}
_G.AtlasLootBossButtons = {}
_G.AtlasLootItems = {}
_G.AtlasMaps = {}
_G.gsub = string.gsub

local function load_addon_file(path)
    local f = io.open(path, "rb")
    if not f then return end
    local content = f:read("*a")
    f:close()
    if content:sub(1,3) == "\239\187\191" then content = content:sub(4) end
    local func = loadstring(content, path)
    if not func then return end
    setfenv(func, _G)
    pcall(func)
end

load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-enUS.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/AtlasMaps.lua")

for mapKey, data in pairs(AtlasMaps) do
    if type(data) == "table" then
        for i, poi in ipairs(data) do
            if type(poi) == "table" and type(poi[3]) == "table" then
                print("Map: " .. mapKey .. ", POI: " .. (poi[1] or "nil"))
                print("Table ID content:")
                for k, v in pairs(poi[3]) do
                    print("  [" .. tostring(k) .. "] = " .. tostring(v))
                end
                print("---")
            end
        end
    end
end


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
    if not func then print("Error in " .. path .. ": " .. err) return end
    setfenv(func, _G)
    pcall(func)
end

load_addon_file(ADDONS_DIR .. "/Atlas/Locale/Atlas-enUS.lua")
load_addon_file(ADDONS_DIR .. "/Atlas/AtlasMaps.lua")

local count = 0
for mapKey, data in pairs(AtlasMaps) do
    if type(data) == "table" then
        for i, poi in ipairs(data) do
            if type(poi) == "table" and type(poi[3]) == "table" then
                print("Found table ID in " .. mapKey .. ": " .. tostring(poi[1]))
                count = count + 1
            end
        end
    end
end
print("Total tables found: " .. count)

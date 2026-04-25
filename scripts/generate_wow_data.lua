-- D:\Games\rilua-0.1.21-x86_64-pc-windows-msvc\rilua.exe scripts\generate_wow_data.lua
-- WoW Data Generator v6
-- Includes NPC/Boss support and integrated cross-linking

local LANG = (...) or (arg and arg[1]) or "zh"
print("Starting WoW Data Generator with LANG=" .. LANG)
local IS_WINDOWS = package.config:sub(1,1) == "\\" or os.getenv("OS") == "Windows_NT"
local ADDONS_DIR = IS_WINDOWS and "D:/Games/TurtleWoW/Interface/AddOns" or "/Users/server/Documents/Otari98"
local DOCS_BASE_DIR = IS_WINDOWS and ("D:/SRC/GitHub/liruqi/" .. LANG .. ".chinapedia/docs/wow/turtle") or ("/Users/server/Documents/" .. LANG .. ".chinapedia/docs/wow/turtle")

local L = {
    zh = {
        NPC_ID = "NPC ID:",
        LOCATIONS = "出现地点:",
        LOOT = "装备掉落",
        ITEM = "物品",
        ID = "ID",
        NOTES = "说明",
        RELATED_QUESTS = "相关任务",
        DUNGEON_LIST = "副本列表",
        DUNGEON_NAME = "副本名称",
        DUNGEON_TYPE = "类型",
        DUNGEON_ZONE = "区域",
        DUNGEON_MAP_NUM = "编号",
        LEVEL_RANGE = "等级范围",
        LINK = "链接",
        ENTER_DOCS = "进入文档",
        QUEST_LEVEL = "任务等级:",
        REQUIRED_LEVEL = "起始等级:",
        START_LOCATION = "开始地点:",
        QUEST_OBJECTIVES = "任务目标",
        QUEST_NOTES = "任务提示",
        QUEST_REWARDS = "任务奖励",
        INCLUDED_ITEMS = "包含物品",
        PART_OF_SET = "属于套装",
        ICON = "图标:",
        HOW_TO_GET = "获取途径",
        DROPS_SOURCES = "掉落/来源",
        LOCATION = "位置:",
        SUITABLE_LEVEL = "适用等级:",
        PLAYER_LIMIT = "人数上限:",
        PLAYERS = "人",
        POINTS_OF_INTEREST = "关键点/首领",
        ALLIANCE = "联盟",
        HORDE = "部落",
        GENERATING_NPC = "正在生成 NPC 文件...",
        GENERATING_DUNGEON = "正在生成副本文件...",
        GENERATING_QUEST = "正在生成任务文件...",
        GENERATING_SET = "正在生成套装文件...",
        GENERATING_ITEM = "正在生成物品文件...",
    },
    en = {
        NPC_ID = "NPC ID:",
        LOCATIONS = "Locations:",
        LOOT = "Equipment Loot",
        ITEM = "Item",
        ID = "ID",
        NOTES = "Notes",
        RELATED_QUESTS = "Related Quests",
        DUNGEON_LIST = "Dungeon List",
        DUNGEON_NAME = "Dungeon Name",
        DUNGEON_TYPE = "Type",
        DUNGEON_ZONE = "Zone",
        DUNGEON_MAP_NUM = "No.",
        LEVEL_RANGE = "Level Range",
        LINK = "Link",
        ENTER_DOCS = "Enter Docs",
        QUEST_LEVEL = "Quest Level:",
        REQUIRED_LEVEL = "Required Level:",
        START_LOCATION = "Start Location:",
        QUEST_OBJECTIVES = "Quest Objectives",
        QUEST_NOTES = "Quest Notes",
        QUEST_REWARDS = "Quest Rewards",
        INCLUDED_ITEMS = "Included Items",
        PART_OF_SET = "Part of Set",
        ICON = "Icon:",
        HOW_TO_GET = "How to Get",
        DROPS_SOURCES = "Drops/Sources",
        LOCATION = "Location:",
        SUITABLE_LEVEL = "Recommended Level:",
        PLAYER_LIMIT = "Player Limit:",
        PLAYERS = "players",
        POINTS_OF_INTEREST = "Points of Interest / Bosses",
        ALLIANCE = "Alliance",
        HORDE = "Horde",
        GENERATING_NPC = "Generating NPC files...",
        GENERATING_DUNGEON = "Generating Dungeon files...",
        GENERATING_QUEST = "Generating Quest files...",
        GENERATING_SET = "Generating Set files...",
        GENERATING_ITEM = "Generating Item files...",
    }
}

local T = L[LANG] or L.en
local TARGET_LOCALE = (LANG == "en") and "enUS" or "zhCN"

-- Ensure directories exist
local ensured_dirs = {}
local function ensure_dir(path)
    if ensured_dirs[path] then return end
    if IS_WINDOWS then
        os.execute('powershell -Command "New-Item -ItemType Directory -Force \'' .. path:gsub("/", "\\") .. '\'" >nul 2>&1')
    else
        os.execute('mkdir -p "' .. path .. '"')
    end
    ensured_dirs[path] = true
end

local function open_file_with_dir(path)
    local dir = path:match("(.+)[/\\]")
    if dir then ensure_dir(dir) end
    return io.open(path, "w")
end

ensure_dir(DOCS_BASE_DIR .. "/quest")
ensure_dir(DOCS_BASE_DIR .. "/item")
ensure_dir(DOCS_BASE_DIR .. "/dungeon")
ensure_dir(DOCS_BASE_DIR .. "/worldboss")
ensure_dir(DOCS_BASE_DIR .. "/transport")
ensure_dir(DOCS_BASE_DIR .. "/npc")
ensure_dir(DOCS_BASE_DIR .. "/set")

-- ==========================================
-- CATEGORY CLASSIFICATION
-- ==========================================
local EASTERN_DUNGEONS = {
    FrostmaneHollow=true, BlackrockDepths=true, BlackrockSpireLower=true, BlackrockSpireUpper=true,
    BlackwingLair=true, DragonmawRetreat=true, Gnomeregan=true, GilneasCity=true,
    HateforgeQuarry=true, KarazhanCrypt=true, LowerKara=true, UpperKara=true,
    MoltenCore=true, Naxxramas=true, Scholomance=true, ShadowfangKeep=true,
    SMArmory=true, SMCathedral=true, SMGraveyard=true, SMLibrary=true,
    Stratholme=true, StormwindVault=true, StormwroughtRuins=true,
    TheDeadmines=true, TheStockade=true, TheSunkenTemple=true, Uldaman=true, ZulGurub=true,
    AlteracValleyNorth=true, AlteracValleySouth=true, ArathiBasin=true
}
local KALIMDOR_DUNGEONS = {
    TimbermawHold=true, WindhornCanyon=true, BlackfathomDeeps=true,
    CavernsOfTimeBlackMorass=true, TheCrescentGrove=true,
    DireMaulEast=true, DireMaulNorth=true, DireMaulWest=true, EmeraldSanctum=true,
    Maraudon=true, OnyxiasLair=true, RagefireChasm=true, RazorfenDowns=true,
    RazorfenKraul=true, TheRuinsofAhnQiraj=true, TheTempleofAhnQiraj=true,
    WailingCaverns=true, ZulFarrak=true, WarsongGulch=true
}
local WORLD_BOSSES = {
    Azuregos=true, FourDragons=true, LordKazzak=true, Nerubian=true,
    Reaver=true, Ostarius=true, Concavius=true, CowKing=true, Clackora=true
}
local TRANSPORT_MAPS = {
    FPAllianceEast=true, FPAllianceWest=true, FPHordeEast=true, FPHordeWest=true,
    TransportRoutes=true
}
local DUNGEON_LOCATIONS = { DLEast=true, DLWest=true }

local MAP_NUMBERS = {
    AlteracValleyNorth="A", AlteracValleySouth="A", ArathiBasin="B",
    SMArmory="1", SMCathedral="1", SMGraveyard="1", SMLibrary="1",
    Stratholme="2", Naxxramas="3", Scholomance="4", ShadowfangKeep="5",
    GilneasCity="6", DragonmawRetreat="7", Gnomeregan="8", Uldaman="9",
    BlackrockDepths="10", BlackrockSpireLower="10", BlackrockSpireUpper="10", BlackwingLair="10", MoltenCore="10",
    HateforgeQuarry="11", TheStockade="12", StormwindVault="12",
    StormwroughtRuins="13", TheDeadmines="14",
    KarazhanCrypt="15", LowerKara="15", UpperKara="15",
    TheSunkenTemple="16", ZulGurub="17",
    WarsongGulch="A", EmeraldSanctum="1", BlackfathomDeeps="2", TheCrescentGrove="3",
    RagefireChasm="4", WailingCaverns="5", Maraudon="6",
    DireMaulEast="7", DireMaulNorth="7", DireMaulWest="7",
    RazorfenKraul="8", RazorfenDowns="9", OnyxiasLair="10",
    ZulFarrak="11", CavernsOfTimeBlackMorass="12",
    TheRuinsofAhnQiraj="13", TheTempleofAhnQiraj="13"
}

-- Entrance image -> parent dungeon(s) mapping
local ENT_MAP = {
    BlackfathomDeeps    = "BlackfathomDeepsEnt",
    BlackrockDepths     = "BlackrockMountainEnt",
    BlackrockSpireLower = "BlackrockMountainEnt",
    BlackrockSpireUpper = "BlackrockMountainEnt",
    BlackwingLair       = "BlackrockMountainEnt",
    MoltenCore          = "BlackrockMountainEnt",
    DireMaulEast        = "DireMaulEnt",
    DireMaulNorth       = "DireMaulEnt",
    DireMaulWest        = "DireMaulEnt",
    Gnomeregan          = "GnomereganEnt",
    Maraudon            = "MaraudonEnt",
    SMArmory            = "SMEnt",
    SMCathedral         = "SMEnt",
    SMGraveyard         = "SMEnt",
    SMLibrary           = "SMEnt",
    TheDeadmines        = "TheDeadminesEnt",
    TheSunkenTemple     = "TheSunkenTempleEnt",
    Uldaman             = "UldamanEnt",
    WailingCaverns      = "WailingCavernsEnt",
}

-- Returns the output subdirectory for a mapKey, or nil to skip standalone page
local function get_output_subdir(mapKey)
    if WORLD_BOSSES[mapKey]   then return "worldboss"
    elseif TRANSPORT_MAPS[mapKey] then return "transport"
    elseif DUNGEON_LOCATIONS[mapKey] then return nil  -- handled in README
    else return "dungeon"   -- Eastern, Kalimdor, BGS, etc.
    end
end

-- Returns the relative path from /npc/ to a dungeon/worldboss/transport page
local function get_npc_rel_link(mapKey)
    local sub = get_output_subdir(mapKey)
    if sub then return "../" .. sub .. "/" .. mapKey .. ".md" end
    return "../dungeon/README.md"
end

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

-- No WDB parsing

-- ==========================================
-- MOCK WoW ENVIRONMENT
-- ==========================================
_G.GetLocale = function() return TARGET_LOCALE end

local function create_babble_mock(name)
    local mock = { translations = {} }
    function mock:RegisterTranslations(lang, func)
        if lang == TARGET_LOCALE then
            local data = func()
            for k, v in pairs(data) do self.translations[k] = v end
        end
    end
    setmetatable(mock, {
        __index = function(t, k) 
            local val = t.translations[k]
            if type(val) == "string" then return val end
            return tostring(k)
        end,
        __call = function(t) return t end
    })
    mock.EnableDebugging = function() end
    mock.EnableDynamicLocales = function() end
    return mock
end

local AceLocales = {}
_G.AceLibrary = function(libName)
    if not AceLocales[libName] then
        AceLocales[libName] = create_babble_mock(libName)
    end
    local mock = AceLocales[libName]

    if libName:match("^AceLocale%-") then
        return {
            new = function(self, name)
                if not AceLocales[name] then
                    AceLocales[name] = create_babble_mock(name)
                end
                return AceLocales[name]
            end,
            RegisterTranslations = function(self, lang, func)
                -- Fallback for some versions
                mock:RegisterTranslations(lang, func)
            end
        }
    end
    
    -- Babble and other libraries often return the mock directly
    return mock
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
if LANG == "en" then
    load_addon_file(ADDONS_DIR .. "/AtlasLoot/Locale/locale.en.lua")
else
    load_addon_file(ADDONS_DIR .. "/AtlasLoot/Locale/locale.cn.lua")
end

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
    if not f then
        path = path:gsub("/", "\\")
        f = io.open(path, "r")
    end
    if not f then print("Warning: TextParsing.lua not found") return end
    local content = f:read("*a")
    f:close()
    
    local al_loot = AceLocales["AtlasLoot"] or create_babble_mock("AtlasLoot")
    for tag, key in content:gmatch('%["#([^#]+)#"%]%s*=%s*AL%["([^"]+)"%]') do
        set_tags[tag] = al_loot[key]
    end
    -- Also capture colors and other tags
    for tag, val in content:gmatch('%["([^"]+)"%]%s*=%s*"([^"]+)"') do
        if tag:find("^=") or tag:find("^#") then
            set_tags[tag:gsub("^#", "")] = val
        end
    end
    print("Loaded " .. (function() local c=0 for _ in pairs(set_tags) do c=c+1 end return c end)() .. " set tags")
end
load_set_tags()

local function translate_tags(s)
    if not s or s == "" then return "" end
    if type(s) == "table" then
        local res = ""
        for _, v in ipairs(s) do res = res .. translate_tags(v) .. " " end
        return res:gsub("%s+$", "")
    end
    if type(s) ~= "string" then s = tostring(s) end
    
    -- Translate known tags
    s = s:gsub("#([^#]+)#", function(tag)
        return set_tags[tag] or tag
    end)
    
    -- Strip quality markers =qN=, metadata markers like =ds=, =mN=, =cNN=, etc.
    s = s:gsub("=%l%d*=", ""):gsub("=%w%w%d*=", ""):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    s = s:gsub("^%s+", ""):gsub("%s+$", "")
    return s
end

-- ==========================================
-- INTEGRATED TRANSLATION
-- ==========================================
local function is_valid_name(name)
    if not name or type(name) ~= "string" then return false end
    local clean = name:gsub("|T.-|t", ""):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("=%l%d*=", ""):gsub("=%w%w%d*=", ""):gsub("%s+", "")
    if #clean == 0 then return false end
    if clean:match("^%d+$") then return false end -- ID fallback
    return true
end

local function translate_item(name, id)
    local al_loot = AceLocales["AtlasLoot"]
    if al_loot and al_loot[name] and al_loot[name] ~= name then
        local trans = al_loot[name]
        if is_valid_name(trans) then return trans end
    end
    return name
end

local function translate_npc(name, id)
    local babble = AceLocales["Babble-Boss-2.2"]
    if babble and babble[name] and babble[name] ~= name then
        local trans = babble[name]
        if is_valid_name(trans) then return trans end
    end
    return name
end

local function get_item_name(entry_name, id)
    if not entry_name or type(entry_name) ~= "string" then return tostring(entry_name or id or "Unknown") end
    local q = entry_name:match("^=q(%d)=")
    local raw_name = entry_name:gsub("^=q%d=", "")
    local name = raw_name
    if LANG == "zh" then
        local trans = translate_item(raw_name, id)
        if is_valid_name(trans) then name = trans end
    end
    if q then return "=q" .. q .. "=" .. name end
    return name
end

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
            
            local i_name = get_item_name(entry[3], i_id)
            local i_extra = translate_tags(entry[4])
            if not items[i_id] then
                items[i_id] = {id=i_id, name=clean_string(i_name), icon=entry[2], sources={}, quality=1, extra = i_extra}
                local q = i_name:match("^=q(%d)=")
                if q then items[i_id].quality = q items[i_id].name = i_name:gsub("^=q%d=", "") end
            end
            table.insert(items[i_id].sources, source_name .. (i_extra ~= "" and " (" .. i_extra .. ")" or ""))
        end
    end
end

local loot_count = 0
for k, v in pairs(AtlasLoot_Data) do
    if type(v) == "table" then
        print("Processing loot category: " .. k)
        for sub_k, sub_v in pairs(v) do 
            collect_items(sub_v, sub_k) 
            loot_count = loot_count + 1
        end
    end
end
print("Processed " .. loot_count .. " loot sub-categories.")

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
                local name = translate_npc(clean_string(poi[1]):gsub("^%d+%)%s+", ""), id)
                if id ~= "-1" then
                    if not npcs[id] then
                        npcs[id] = {id=id, name=name, locations={}, drops={}, quests={}}
                    end
                    table.insert(npcs[id].locations, {mapKey=mapKey, dungeonName=dungeon_name})
                    npc_names_to_ids[name] = id
                    
                    -- Link Loot
                    local loot_labels = AtlasLootBossButtons[mapKey]
                    if not loot_labels then
                        for k, v in pairs(AtlasLootBossButtons) do
                            if k:lower() == mapKey:lower() then
                                loot_labels = v
                                break
                            end
                        end
                    end

                    if loot_labels and loot_labels[i] and loot_labels[i] ~= "" then
                        local loot_label = loot_labels[i]
                        local loot_table = nil
                        
                        -- Search priority: DUNGEONS, specific mapKey, global _G, other categories
                        if AtlasLoot_Data["DUNGEONS"] and AtlasLoot_Data["DUNGEONS"][mapKey] then
                            loot_table = AtlasLoot_Data["DUNGEONS"][mapKey][loot_label]
                        end
                        if not loot_table and AtlasLoot_Data["DUNGEONS"] then
                            loot_table = AtlasLoot_Data["DUNGEONS"][loot_label]
                        end
                        if not loot_table then
                            for cat, maps in pairs(AtlasLoot_Data) do
                                if maps[mapKey] and maps[mapKey][loot_label] then
                                    loot_table = maps[mapKey][loot_label]
                                    break
                                end
                                if maps[loot_label] then
                                    loot_table = maps[loot_label]
                                    break
                                end
                            end
                        end
                        if not loot_table and _G[loot_label] then
                            loot_table = _G[loot_label]
                        end

                        if loot_table and type(loot_table) == "table" then
                            -- Some loot tables are nested: { { item1 }, { item2 } }
                            -- Others are double nested: { { { item1 } } } (rare)
                            local function process_loot(tbl)
                                for _, loot_entry in ipairs(tbl) do
                                    if type(loot_entry) == "table" then
                                        if loot_entry[1] and type(loot_entry[1]) == "number" and loot_entry[1] ~= 0 then
                                            local d_name = clean_string(loot_entry[3]):gsub("^=q%d=", "")
                                            table.insert(npcs[id].drops, {
                                                id=tostring(loot_entry[1]), 
                                                name=d_name,
                                                extra=translate_tags(loot_entry[4])
                                            })
                                        else
                                            process_loot(loot_entry)
                                        end
                                    end
                                end
                            end
                            process_loot(loot_table)
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
print(T.GENERATING_NPC)
for id, npc in pairs(npcs) do
    local f = open_file_with_dir(DOCS_BASE_DIR .. "/npc/" .. id .. ".md")
    if f then
        f:write("# " .. npc.name .. "\n\n")
        f:write("**" .. T.NPC_ID .. "** " .. id .. "  \n")
        f:write("**" .. T.LOCATIONS .. "**\n")
        for _, loc in ipairs(npc.locations) do
            f:write("- [" .. loc.dungeonName .. "](" .. get_npc_rel_link(loc.mapKey) .. ")\n")
        end
        f:write("\n")
        
        if #npc.drops > 0 then
            f:write("## " .. T.LOOT .. "\n")
            f:write("| " .. T.ITEM .. " | " .. T.ID .. " | " .. T.NOTES .. " |\n")
            f:write("| :--- | :--- | :--- |\n")
            for _, drop in ipairs(npc.drops) do
                f:write("| [" .. drop.name .. "](../item/" .. drop.id .. ".md) | " .. drop.id .. " | " .. drop.extra .. " |\n")
            end
            f:write("\n")
        end
        
        if #npc.quests > 0 then
            f:write("## " .. T.RELATED_QUESTS .. "\n")
            for _, q in ipairs(npc.quests) do
                f:write("- [" .. q.title .. "](../quest/" .. q.id .. ".md)\n")
            end
            f:write("\n")
        end
        f:close()
    end
end

print(T.GENERATING_DUNGEON)
local dungeon_list = {}
local eastern_list = {}
local kalimdor_list = {}

for mapKey, data in pairs(AtlasMaps) do
    if type(data) == "table" and data.ZoneName and data.LevelRange and data.PlayerLimit then
        local subdir = get_output_subdir(mapKey)
        if subdir ~= nil then
            local d_name  = clean_string(translated_atlas[data.ZoneName[1]] or data.ZoneName[1])
            local d_loc   = clean_string(translated_atlas[data.Location and data.Location[1]] or (data.Location and data.Location[1]) or "")
            local d_limit = clean_string(data.PlayerLimit or "?")
            local map_num = MAP_NUMBERS[mapKey] or ""
            local entry = {key=mapKey, name=d_name, level=data.LevelRange, location=d_loc, playerLimit=d_limit, mapNumber=map_num}
            table.insert(dungeon_list, entry)
            if EASTERN_DUNGEONS[mapKey] then
                table.insert(eastern_list, entry)
            elseif KALIMDOR_DUNGEONS[mapKey] then
                table.insert(kalimdor_list, entry)
            end

        local f = open_file_with_dir(DOCS_BASE_DIR .. "/" .. subdir .. "/" .. mapKey .. ".md")
        if f then
            f:write("# " .. d_name .. "\n\n")
            f:write("![" .. d_name .. "](" .. mapKey .. ".png)\n\n")
            -- Entrance image (only for dungeons, not worldboss/transport)
            if subdir == "dungeon" and ENT_MAP[mapKey] then
                f:write("![" .. d_name .. " 入口](" .. ENT_MAP[mapKey] .. ".png)\n\n")
            end
            f:write("**" .. T.LOCATION .. "** " .. clean_string(translated_atlas[data.Location[1]] or data.Location[1]) .. "  \n")
            f:write("**" .. T.SUITABLE_LEVEL .. "** " .. clean_string(data.LevelRange or "??") .. " (" .. clean_string(data.MinLevel or "??") .. "+)  \n")
            f:write("**" .. T.PLAYER_LIMIT .. "** " .. clean_string(data.PlayerLimit or "??") .. T.PLAYERS .. "  \n\n")
            f:write("## " .. T.POINTS_OF_INTEREST .. "\n")
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
                f:write("\n## " .. T.RELATED_QUESTS .. "\n")
                for _, fact in ipairs({{T.ALLIANCE, 1}, {T.HORDE, 2}}) do
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
end

-- ==========================================
-- DUNGEON README (by region) + _category_.json
-- ==========================================
local function sort_by_map_number(list)
    table.sort(list, function(a, b)
        local a1 = a.mapNumber or ""
        local b1 = b.mapNumber or ""
        local a_is_alpha = (a1:match("^[A-Z]"))
        local b_is_alpha = (b1:match("^[A-Z]"))
        
        if a_is_alpha and not b_is_alpha then return true end
        if not a_is_alpha and b_is_alpha then return false end
        if a_is_alpha and b_is_alpha then
            if a1 ~= b1 then return a1 < b1 end
        else
            local numA = tonumber(a1)
            local numB = tonumber(b1)
            if numA and numB then
                if numA ~= numB then return numA < numB end
            elseif numA then return true
            elseif numB then return false
            end
        end
        return a.name < b.name
    end)
end

table.insert(eastern_list, {key="BloodRingArena", name="血色竞技场", location="荆棘谷", level="50-60", playerLimit="BGS", mapNumber="C"})
table.insert(kalimdor_list, {key="SunnygladeValley", name="阳光谷", location="时光之穴", level="60-60", playerLimit="BGS", mapNumber="B"})
local function generate_empty_bg(key, name, loc, lvl)
    local f = open_file_with_dir(DOCS_BASE_DIR .. "/dungeon/" .. key .. ".md")
    if f then
        f:write("# " .. name .. "\n\n")
        f:write("**" .. T.LOCATION .. "** " .. loc .. "  \n")
        f:write("**" .. T.SUITABLE_LEVEL .. "** " .. lvl .. "  \n")
        f:write("**" .. T.PLAYER_LIMIT .. "** PVP战场  \n\n")
        f:write("> 暂无详细地图数据。\n")
        f:close()
    end
end
generate_empty_bg("BloodRingArena", "血色竞技场", "荆棘谷", "50-60")
generate_empty_bg("SunnygladeValley", "阳光谷", "时光之穴", "60-60")

sort_by_map_number(eastern_list)
sort_by_map_number(kalimdor_list)

-- Read DLEast and DLWest names from AtlasMaps for README headings
local dleast_name  = "东部王国副本分布"
local dlwest_name  = "卡利姆多副本分布"
if AtlasMaps["DLEast"] and AtlasMaps["DLEast"].ZoneName then
    dleast_name = clean_string(translated_atlas[AtlasMaps["DLEast"].ZoneName[1]] or AtlasMaps["DLEast"].ZoneName[1])
end
if AtlasMaps["DLWest"] and AtlasMaps["DLWest"].ZoneName then
    dlwest_name = clean_string(translated_atlas[AtlasMaps["DLWest"].ZoneName[1]] or AtlasMaps["DLWest"].ZoneName[1])
end

-- Helper: format player limit as type label
local function fmt_type(entry)
    if (entry.mapNumber or ""):match("^[A-Z]") then return "PVP战场" end
    local n = tonumber(entry.playerLimit) or 0
    if n >= 20 then return n .. "人团本"
    elseif n > 0 then return n .. "人本"
    else return "未知" end
end

local idx_f = open_file_with_dir(DOCS_BASE_DIR .. "/dungeon/README.md")
if idx_f then
    idx_f:write("# " .. T.DUNGEON_LIST .. "\n\n")
    -- DLEast map + Eastern table
    idx_f:write("## " .. dleast_name .. "\n\n")
    idx_f:write("![" .. dleast_name .. "](DLEast.png)\n\n")
    idx_f:write("| " .. T.DUNGEON_MAP_NUM .. " | " .. T.DUNGEON_NAME .. " | " .. T.DUNGEON_TYPE .. " | " .. T.DUNGEON_ZONE .. " | " .. T.LEVEL_RANGE .. " |\n| :---: | :--- | :---: | :--- | :---: |\n")
    for _, d in ipairs(eastern_list) do
        idx_f:write("| " .. (d.mapNumber or "") .. " | [" .. d.name .. "](" .. d.key .. ".md) | " .. fmt_type(d) .. " | " .. (d.location or "") .. " | " .. (d.level or "??") .. " |\n")
    end
    idx_f:write("\n")
    -- DLWest map + Kalimdor table
    idx_f:write("## " .. dlwest_name .. "\n\n")
    idx_f:write("![" .. dlwest_name .. "](DLWest.png)\n\n")
    idx_f:write("| " .. T.DUNGEON_MAP_NUM .. " | " .. T.DUNGEON_NAME .. " | " .. T.DUNGEON_TYPE .. " | " .. T.DUNGEON_ZONE .. " | " .. T.LEVEL_RANGE .. " |\n| :---: | :--- | :---: | :--- | :---: |\n")
    for _, d in ipairs(kalimdor_list) do
        idx_f:write("| " .. (d.mapNumber or "") .. " | [" .. d.name .. "](" .. d.key .. ".md) | " .. fmt_type(d) .. " | " .. (d.location or "") .. " | " .. (d.level or "??") .. " |\n")
    end
    idx_f:write("\n")
    idx_f:close()
end

-- dungeon _category_.json
local cat_d = open_file_with_dir(DOCS_BASE_DIR .. "/dungeon/_category_.json")
if cat_d then
    cat_d:write('{\n  "label": "副本",\n  "position": 1\n}\n')
    cat_d:close()
end

-- worldboss README + _category_.json
local wb_list = {}
for mapKey, data in pairs(AtlasMaps) do
    if WORLD_BOSSES[mapKey] and type(data) == "table" and data.ZoneName then
        local d_name = clean_string(translated_atlas[data.ZoneName[1]] or data.ZoneName[1])
        local d_loc  = clean_string(translated_atlas[data.Location and data.Location[1]] or (data.Location and data.Location[1]) or "")
        table.insert(wb_list, {key=mapKey, name=d_name, location=d_loc})
    end
end
table.sort(wb_list, function(a, b) return a.name < b.name end)
local wb_f = open_file_with_dir(DOCS_BASE_DIR .. "/worldboss/README.md")
if wb_f then
    wb_f:write("# 世界首领\n\n")
    wb_f:write("| " .. T.DUNGEON_NAME .. " | " .. T.DUNGEON_ZONE .. " | " .. T.LINK .. " |\n| :--- | :--- | :--- |\n")
    for _, d in ipairs(wb_list) do
        wb_f:write("| " .. d.name .. " | " .. (d.location or "??") .. " | [" .. T.ENTER_DOCS .. "](" .. d.key .. ".md) |\n")
    end
    wb_f:close()
end
local cat_wb = open_file_with_dir(DOCS_BASE_DIR .. "/worldboss/_category_.json")
if cat_wb then
    cat_wb:write('{\n  "label": "世界首领",\n  "position": 2\n}\n')
    cat_wb:close()
end

-- transport README + _category_.json
local tr_list = {}
for mapKey, data in pairs(AtlasMaps) do
    if TRANSPORT_MAPS[mapKey] and type(data) == "table" and data.ZoneName then
        local d_name = clean_string(translated_atlas[data.ZoneName[1]] or data.ZoneName[1])
        table.insert(tr_list, {key=mapKey, name=d_name, level=data.LevelRange})
    end
end
table.sort(tr_list, function(a, b) return a.name < b.name end)
local tr_f = open_file_with_dir(DOCS_BASE_DIR .. "/transport/README.md")
if tr_f then
    tr_f:write("# 交通路线\n\n")
    tr_f:write("| " .. T.DUNGEON_NAME .. " | " .. T.LINK .. " |\n| :--- | :--- |\n")
    for _, d in ipairs(tr_list) do
        tr_f:write("| " .. d.name .. " | [" .. T.ENTER_DOCS .. "](" .. d.key .. ".md) |\n")
    end
    tr_f:close()
end
local cat_tr = open_file_with_dir(DOCS_BASE_DIR .. "/transport/_category_.json")
if cat_tr then
    cat_tr:write('{\n  "label": "交通路线",\n  "position": 3\n}\n')
    cat_tr:close()
end

print(T.GENERATING_QUEST)
for id, q in pairs(all_quests) do
    local q_title = clean_string(q.title)
    local f = open_file_with_dir(DOCS_BASE_DIR .. "/quest/" .. id .. ".md")
    if f then
        f:write("# " .. q_title .. "\n\n")
        f:write("**" .. T.QUEST_LEVEL .. "** " .. (q.level or "") .. "  \n")
        f:write("**" .. T.REQUIRED_LEVEL .. "** " .. (q.attain or "") .. "  \n")
        
        -- Link NPC in location/aim
        local loc_str = clean_string(q.location)
        for name, n_id in pairs(npc_names_to_ids) do
            local pat = escape_pattern(name)
            loc_str = loc_str:gsub(pat, "["..name.."](../npc/"..n_id..".md)")
        end
        f:write("**" .. T.START_LOCATION .. "** " .. loc_str .. "  \n\n")
        
        local aim_str = clean_string(q.aim or "无")
        for name, n_id in pairs(npc_names_to_ids) do
            local pat = escape_pattern(name)
            aim_str = aim_str:gsub(pat, "["..name.."](../npc/"..n_id..".md)")
        end
        f:write("## " .. T.QUEST_OBJECTIVES .. "\n" .. aim_str .. "\n\n")
        
        if q.note then f:write("## " .. T.QUEST_NOTES .. "\n" .. clean_string(q.note) .. "\n\n") end
        if q.rewards and #q.rewards > 0 then
            f:write("## " .. T.QUEST_REWARDS .. "\n")
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

        local of = open_file_with_dir(DOCS_BASE_DIR .. "/set/" .. sid .. ".md")
        if of then
            of:write("# " .. name .. "\n\n")
            of:write("## " .. T.INCLUDED_ITEMS .. "\n")
            for item_id, _ in pairs(unique_items) do
                of:write("- [" .. item_id .. "](../item/" .. item_id .. ".md)\n")
            end
            of:close()
            set_count = set_count + 1
        end
    end
end
print("Generated " .. set_count .. " set files.")

print(T.GENERATING_ITEM)
for id, i in pairs(items) do
    local f = open_file_with_dir(DOCS_BASE_DIR .. "/item/" .. id .. ".md")
    if f then
        f:write("# " .. clean_string(i.name) .. "\n\n")
        f:write("**" .. T.ITEM .. " " .. T.ID .. ":** " .. clean_string(id) .. "  \n**" .. T.ICON .. "** " .. clean_string(i.icon or "") .. "  \n\n## " .. T.HOW_TO_GET .. "\n")
        local rewarded_by = {}
        for _, q in pairs(all_quests) do
            if q.rewards then
                for _, r in ipairs(q.rewards) do
                    if tostring(r.id) == id then table.insert(rewarded_by, q) break end
                end
            end
        end
        if #rewarded_by > 0 then
            f:write("### " .. T.QUEST_REWARDS .. "\n")
            for _, q in ipairs(rewarded_by) do f:write("- [" .. clean_string(q.title) .. "](../quest/" .. q.id .. ".md)\n") end
        end
        if #i.sources > 0 then
            f:write("### " .. T.DROPS_SOURCES .. "\n")
            for _, src in ipairs(i.sources) do f:write("- " .. src .. "\n") end
        end

        -- Backward links to sets
        if item_to_sets[id] then
            f:write("\n## " .. T.PART_OF_SET .. "\n")
            for _, s in ipairs(item_to_sets[id]) do
                f:write("- [" .. s.name .. "](../set/" .. s.sid .. ".md)\n")
            end
        end
        
    end
end
local item_count = 0
for _ in pairs(items) do item_count = item_count + 1 end
print("Generated " .. item_count .. " item files.")

print("Done.")

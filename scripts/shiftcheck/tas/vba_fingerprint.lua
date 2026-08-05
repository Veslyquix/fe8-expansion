-- VBA-rr SDL Lua: replay a movie, capture raw GD framebuffer snapshots at
-- evenly-spaced checkpoints, write a manifest/done marker, and exit.
--
-- Config file path comes from VBA_TAS_CONFIG. Lines:
--   1. output directory
--   2. tag
--   3. expected frame count
--   4. checkpoint count

local config_path = assert(os.getenv("VBA_TAS_CONFIG"), "VBA_TAS_CONFIG is not set")
local config = assert(io.open(config_path, "r"))
local output_dir = assert(config:read("*l"), "missing output directory")
local tag = assert(config:read("*l"), "missing tag")
local expected_frames = assert(tonumber(config:read("*l")), "missing frame count")
local checkpoint_count = assert(tonumber(config:read("*l")), "missing checkpoint count")
config:close()

local checkpoints = {}
for index = 1, checkpoint_count do
    local frame = math.floor(index * expected_frames / checkpoint_count)
    if frame < 1 then
        frame = 1
    end
    checkpoints[frame] = true
end
checkpoints[expected_frames] = true

local manifest = assert(io.open(output_dir .. "/" .. tag .. "_manifest.txt", "w"))

local function capture(frame)
    local path = output_dir .. "/" .. tag .. "_" .. string.format("%07d", frame) .. ".gd"
    local file = assert(io.open(path, "wb"))
    file:write(gui.gdscreenshot())
    file:close()
    manifest:write(frame .. "\n")
    manifest:flush()
end

while vba.framecount() < expected_frames do
    vba.frameadvance()
    local frame = vba.framecount()
    if checkpoints[frame] then
        capture(frame)
    end
end

manifest:close()
local done = assert(io.open(output_dir .. "/" .. tag .. "_done.txt", "w"))
done:write("reached=" .. vba.framecount() .. " expected=" .. expected_frames .. "\n")
done:close()
os.exit(0)

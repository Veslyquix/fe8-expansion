-- GBAHawk Lua: replay a reference movie's logical input stream by advancing to
-- the next input only when the target ROM completes a non-lag frame.
--
-- Do not load a movie while using this script: movie input and Lua input merge.
--
-- Config from C:\gbahawk_test\out\adaptive-config.txt:
--   line 1 = poll-input TSV path, using a Windows path
--   line 2 = output tag
--   line 3 = maximum reference source frame (0 = full stream)
--   line 4 = screenshot checkpoint count (0 = no screenshots)

local OUT = "C:\\gbahawk_test\\out\\"
local cfg = assert(io.open(OUT .. "adaptive-config.txt", "r"))
local input_path = assert(cfg:read("*l"))
local tag = assert(cfg:read("*l"))
local max_source = tonumber(cfg:read("*l")) or 0
local checkpoint_count = tonumber(cfg:read("*l")) or 0
cfg:close()

if movie.isloaded() then
  error("adaptive_replay.lua must run without a loaded movie")
end
if checkpoint_count < 0 then
  error("checkpoint count must be non-negative")
end

local source_frames = {}
local inputs = {}
for line in io.lines(input_path) do
  local frame, input = string.match(line, "^(%d+)\t(|.+|)$")
  if frame ~= nil then
    source_frames[#source_frames + 1] = tonumber(frame)
    inputs[#inputs + 1] = input
  end
end
if #inputs == 0 then
  error("poll-input TSV contains no inputs")
end

local final_source = source_frames[#source_frames]
if max_source > 0 and max_source < final_source then
  final_source = max_source
end

local index = 1
local next_checkpoint = 1
local status = assert(io.open(OUT .. tag .. "-adaptive-status.txt", "w"))
local physical_inputs = assert(io.open(OUT .. tag .. "-physical-inputs.txt", "w"))

client.invisibleemulation(true)
if client.speedmode then client.speedmode(6399) end

while index <= #inputs and source_frames[index] <= final_source do
  local input = inputs[index]
  joypad.setfrommnemonicstr(input)
  physical_inputs:write(input, "\n")
  emu.frameadvance()

  if not emu.islagged() then
    local consumed_source = source_frames[index]
    while checkpoint_count > 0
      and next_checkpoint <= checkpoint_count
      and consumed_source >= math.floor(next_checkpoint * final_source / checkpoint_count) do
      client.screenshot(
        OUT .. tag .. string.format("-checkpoint-%02d-source-%07d.png", next_checkpoint, consumed_source))
      next_checkpoint = next_checkpoint + 1
    end
    index = index + 1
  end

  if emu.framecount() % 1000 == 0 then
    status:write(
      "PROGRESS physical=", emu.framecount(),
      " source=", source_frames[index] or final_source,
      " logical=", index,
      " lag=", emu.lagcount(), "\n")
    status:flush()
    physical_inputs:flush()
  end
end

client.screenshot(OUT .. tag .. "-adaptive-final.png")
status:write(
  "DONE physical=", emu.framecount(),
  " source=", source_frames[math.max(1, index - 1)],
  " logical=", index,
  " lag=", emu.lagcount(), "\n")
status:close()
physical_inputs:close()
client.exit()

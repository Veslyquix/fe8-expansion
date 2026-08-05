-- GBAHawk Lua: reduce a loaded reference movie to the inputs consumed on
-- non-lag frames. The output can be replayed by adaptive_replay.lua.
--
-- Config from C:\gbahawk_test\out\poll-input-config.txt:
--   line 1 = output tag
--   line 2 = maximum movie frame (0 = full movie)

local OUT = "C:\\gbahawk_test\\out\\"
local cfg = assert(io.open(OUT .. "poll-input-config.txt", "r"))
local tag = assert(cfg:read("*l"))
local max_frame = tonumber(cfg:read("*l")) or 0
cfg:close()

if not movie.isloaded() then
  error("capture_poll_inputs.lua requires a loaded reference movie")
end

local trace = assert(io.open(OUT .. tag .. "-poll-inputs.tsv", "w"))
local length = movie.length()
if max_frame > 0 and max_frame < length then
  length = max_frame
end

client.invisibleemulation(true)
if client.speedmode then client.speedmode(6399) end

trace:write("source_frame\tinput\n")
while emu.framecount() < length do
  local frame = emu.framecount()
  local input = movie.getinputasmnemonic(frame)
  emu.frameadvance()

  if not emu.islagged() then
    trace:write(frame, "\t", input, "\n")
  end
end

trace:close()
client.exit()

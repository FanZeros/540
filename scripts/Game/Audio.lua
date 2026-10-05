-- 固定音源池，仅使用低层声音播放；Scene 只持有音源，不管理任何玩法。
local C = require "Game.Config"
local A = {}
A.__index=A
function A.New()
    local a=setmetatable({},A); a:init(); return a
end
function A:init()
    self.scene=Scene(); self.sounds={}; self.sources={}; self.cursor=1; self.slow=false
    for _,path in ipairs(C.sounds) do
        local sound=cache:GetResource("Sound",path)
        if sound then self.sounds[path]=sound; print("[素材] 声音加载",path,sound.length)
        else print("[错误] 声音缺失",path) end
    end
    for i=1,18 do
        local node=self.scene:CreateChild("音源"..i)
        self.sources[i]=node:CreateComponent("SoundSource")
        self.sources[i].soundType="Effect"
    end
    self.ambient=self.scene:CreateChild("环境"):CreateComponent("SoundSource")
    self.music=self.scene:CreateChild("音乐"):CreateComponent("SoundSource")
end
function A:Begin()
    local ambience=self.sounds["Ambient.wav"]; local music=self.sounds["Music.wav"]
    if ambience then ambience.looped=true; self.ambient:Play(ambience,ambience.frequency,0.20) end
    if music then music.looped=true; self.music:Play(music,music.frequency,0.28) end
end
function A:Play(path,x,gain)
    local sound=self.sounds[path]
    if not sound then return end
    local source=self.sources[self.cursor]
    self.cursor=self.cursor%#self.sources+1
    source:Stop()
    source:Play(sound,sound.frequency*(self.slow and 0.72 or 1),gain or 0.65,math.max(-0.7,math.min(0.7,((x or 338)-338)/450)))
end
function A:Update(slow)
    self.slow=slow
    local m=self.sounds["Music.wav"]; local a=self.sounds["Ambient.wav"]
    if m then self.music.frequency=m.frequency*(slow and 0.78 or 1) end
    if a then self.ambient.frequency=a.frequency*(slow and 0.65 or 1) end
end
function A:Dispose() self.scene:Dispose() end
return A

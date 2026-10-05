-- 关卡与固定步长：游戏场景只是 Lua table，未创建引擎 Scene。
local C = require "Game.Config"
local P = require "Game.Player"
local E = require "Game.Enemies"
local B = require "Game.Combat"
local F = require "Game.Effects"
local R = require "Game.Replay"
local W = {}
W.__index=W
function W.New(audio)
    local w=setmetatable({},W)
    w:init(audio)
    return w
end
function W:init(audio)
    self.audio=audio or {Play=function() end}; self.verbose=true; self.level=1; self.attempt=1
    self.mode="title"; self.modeTime=0; self.seed=540; self:Load(1); self.mode="title"
end
function W:Random()
    self.seed=(self.seed*16807)%2147483647
    return self.seed/2147483647
end
function W:Log(...)
    if self.verbose then print("[零刻]",...) end
end
function W:Sound(name,x,gain) self.audio:Play(name,x,gain or 0.65) end
function W:Load(level)
    self.level=math.max(1,math.min(10,level)); self.seed=540+self.level
    self.player=P.New(); self.enemies={}; self.bullets={}; self.objects={}; self.platforms={}; self.portals={}
    self.particles={}; self.stains={}; self.fx={}; self.trails={}; self.visited={}
    self.time=0; self.realTime=0; self.lastWorldDT=0; self.lastRealDT=0; self.modeTime=0; self.slow=false
    self.shake=0; self.flash=0; self.trailTimer=0; self.spawnIndex=1; self.view=nil; self.clearTimer=0
    self.stats={kills=0,parries=0,rolls=0,jumps=0,slashes=0,shots=0,steps=0,dodges=0,
        reflectKills=0,blastKills=0,breaks=0,teleports=0,slowSeconds=0}
    self.replay=R.New(); self.schedule={}
    local chapter=C.chapters[self.level]
    local order={4,2,3,1}
    for i=1,chapter.count do
        local isGun=chapter.gun>0 and i%2==0 and i<=chapter.gun*2
        self.schedule[i]={time=1.8+(i-1)*chapter.gap,door=order[(i-1)%4+1],kind=isGun and "ranged" or "melee"}
    end
    if self.level>=2 then self.objects[#self.objects+1]={kind="crate",x=338,y=C.FLOOR,broken=false} end
    if self.level>=3 then self.objects[#self.objects+1]={kind="barrel",x=484,y=C.FLOOR,broken=false} end
    if self.level>=5 then
        self.platforms={{x=160,y=192,w=96},{x=360,y=168,w=96}}
        self.objects[#self.objects+1]={kind="crate",x=205,y=192,broken=false}
    end
    if self.level>=7 then self.objects[#self.objects+1]={kind="barrel",x=415,y=C.FLOOR,broken=false} end
    if self.level==4 or self.level==6 or self.level==8 or self.level==10 then self.portals={{x=70},{x=606}} end
    self.mode="playing"
    self:Log("载入关卡",self.level,chapter.name,"敌人",chapter.count,"尝试",self.attempt)
    R.Capture(self,true)
end
function W:Start() self:Load(1) end
function W:KillPlayer(cause)
    if self.player.dead or self.mode~="playing" then return end
    self.player.dead=true; self.player.anim="Hit"; self.player.animTime=0; self.player.state="dead"
    self.cause=cause; self.mode="dying"; self.modeTime=0; self.slow=false
    F.Blood(self,self.player,-self.player.dir); self:Sound("sound_playerdie.wav",self.player.x,0.85)
    self:Log("玩家死亡",cause,"关卡",self.level)
end
function W:Restart()
    if self.mode~="failed" and self.mode~="complete" then return false end
    if self.mode=="failed" then self.mode="rewind"; self.modeTime=0; R.Begin(self,true)
    else self.attempt=self.attempt+1; self:Load(self.level) end
    return true
end
function W:Next()
    if self.mode~="complete" then return false end
    if self.level<10 then self.attempt=1; self:Load(self.level+1) else self.mode="ending" end
    return true
end
function W:Update(dt,keys)
    dt=math.max(0,math.min(dt,0.05)); keys=keys or {}
    self.modeTime=self.modeTime+dt
    if self.mode=="title" then return end
    if self.mode=="rewind" then
        if R.Update(self,dt) then self.attempt=self.attempt+1; self:Load(self.level) end
        return
    elseif self.mode=="replay" then
        if R.Update(self,dt) then self.view=nil; self.mode="complete"; self.modeTime=0 end
        return
    elseif self.mode=="failed" or self.mode=="complete" or self.mode=="ending" then
        if keys.restart then self:Restart() end
        return
    elseif self.mode=="dying" then
        self.realTime=self.realTime+dt
        P.Update(self,dt,{}); F.Update(self,dt)
        if self.modeTime>0.65 then R.Capture(self,true); self.mode="failed"; self.modeTime=0 end
        return
    end
    self.realTime=self.realTime+dt
    self.slow=keys.slow==true
    local worldDT=dt*(self.slow and C.WORLD_SLOW or 1)
    local playerDT=dt*(self.slow and C.PLAYER_SLOW or 1)
    self.lastWorldDT=worldDT; self.lastRealDT=dt; self.time=self.time+worldDT
    if self.slow then self.stats.slowSeconds=self.stats.slowSeconds+dt end
    P.Update(self,playerDT,keys)
    -- 玩家刀和子弹弹反先计算，已死亡敌人不得在同一帧反杀。
    B.Update(self,worldDT)
    if self.mode~="playing" then return end
    while self.spawnIndex<=#self.schedule and self.time>=self.schedule[self.spawnIndex].time do
        local spawn=self.schedule[self.spawnIndex]
        self.enemies[#self.enemies+1]=E.New(self,spawn.kind,C.DOORS[spawn.door])
        self:Log("门洞刷出",spawn.door,spawn.kind)
        self.spawnIndex=self.spawnIndex+1
    end
    for _,e in ipairs(self.enemies) do
        if self.mode~="playing" then break end
        E.Update(self,e,worldDT)
    end
    F.Update(self,worldDT)
    for i=#self.trails,1,-1 do
        self.trails[i].life=self.trails[i].life-worldDT
        if self.trails[i].life<=0 then table.remove(self.trails,i) end
    end
    R.Capture(self,false)
    local living=0
    for _,e in ipairs(self.enemies) do if not e.dead then living=living+1 end end
    if self.mode=="playing" and self.spawnIndex>#self.schedule and living==0 then
        self.clearTimer=(self.clearTimer or 0)+worldDT
        if self.clearTimer<1.2 then return end
        R.Capture(self,true); self.mode="replay"; self.modeTime=0; R.Begin(self,false)
        self:Log("关卡清空，开始1倍速回放",self.level,self.stats.kills)
    end
end
return W

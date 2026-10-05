-- 真实引擎自动游玩入口，正式 main 不引用本文件。
-- 只产生固定动作；局部测试关卡从 Load 进入，关卡内不改敌人或玩家状态。
local app=require "main"
local originalStart=Start
local tick=0
local testLevel=1
local testStyle="campaign"
for _,arg in ipairs(GetArguments()) do
    local level=arg:match("^%-test%-level=(%d+)$")
    if level then testLevel=tonumber(level) end
    local style=arg:match("^%-test%-style=(%w+)$")
    if style then testStyle=style end
end
local function bot(w)
    tick=tick+1
    local p=w.player
    if tick%60==0 then
        print("[实玩状态]",tick,w.level,w.mode,p.x,p.y,p.state,w.replay.index,w.replay.realCursor)
    end
    if w.mode=="failed" then return {restart=true} end
    if w.mode=="complete" then
        if w.modeTime>1 and testStyle=="campaign" then w:Next() end
        return {}
    end
    if w.mode~="playing" then return {} end
    if testStyle=="death" then return {} end
    if testStyle=="jump" then
        return {right=tick<70,jump=tick==60,roll=tick==155,slow=tick>150}
    end
    local target,dist=nil,math.huge
    for _,e in ipairs(w.enemies) do
        if not e.dead and math.abs(e.x-p.x)<dist then target,dist=e,math.abs(e.x-p.x) end
    end
    local tx=target and target.x or nil
    if not tx and w.schedule[w.spawnIndex] then tx=require("Game.Config").DOORS[w.schedule[w.spawnIndex].door] end
    tx=tx or 336
    local dx=tx-p.x; local dir=dx>=0 and 1 or -1
    local keys={left=dx < -35,right=dx > 35,slow=target~=nil}
    if p.dir~=dir and p.state~="roll" and p.state~="slash" then keys.left=dir<0;keys.right=dir>0 end
    local barrel=nil
    for _,o in ipairs(w.objects) do
        if not o.broken and o.kind=="barrel" and (not barrel or math.abs(o.x-p.x)<math.abs(barrel.x-p.x)) then barrel=o end
    end
    if barrel then
        local gap=barrel.x-p.x; local direction=gap>=0 and 1 or -1; local d=math.abs(gap)
        keys.left=d>60.5 and direction<0 or d<57 and direction>0
        keys.right=d>60.5 and direction>0 or d<57 and direction<0
        if d>=57 and d<=62 and p.dir==direction and p.slashCD<=0.006 and p.state~="roll" then
            keys.slash=true; keys.left=false; keys.right=false
        elseif p.dir~=direction and p.state~="slash" and p.state~="roll" then
            keys.left=direction<0; keys.right=direction>0
        end
    elseif target and target.state~="spawn" and dist<=60 and math.abs(p.y-target.y)<52 and p.dir==dir and p.slashCD<=0.006 and p.state~="roll" then
        keys.slash=true; keys.left=false; keys.right=false
    end
    for _,b in ipairs(w.bullets) do
        if not b.friendly and math.abs(b.y-(p.y-24))<35 and b.vx*(p.x-b.x)>0 and math.abs((p.x-b.x)/b.vx)<0.45 then
            if p.dir==(b.x>=p.x and 1 or -1) and p.slashCD<=0.006 then keys.slash=true;keys.left=false;keys.right=false
            elseif p.rollCD<=0.006 and p.state~="slash" then keys.roll=true
            elseif p.ground and p.state~="roll" then keys.jump=true end
        end
    end
    if tick%120==0 then print("[实玩]",w.level,w.mode,p.x,p.y,w.stats.kills,w.stats.parries,w.stats.breaks) end
    return keys
end
function Start()
    originalStart()
    app.world:Load(testLevel)
    app.audio:Begin()
    app.testInput=bot
    print("[实玩] 测试模式",testStyle,"起始关卡",testLevel)
end

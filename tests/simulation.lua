-- 纯Lua独立自测，不由游戏引用。
-- 隔离单测允许安排初始状态；十关与长测机器人绝不改玩家/敌人数据，
-- 也不通过Kill、Break、Set、Load制造胜利。
-- 碰撞区域示意（脚底y=246）：
-- 玩家 [x-7,x+7] × [211,246]；翻滚 [x-9,x+9] × [230,246]
-- 近战敌 [x-10,x+10] × [204,246]；子弹使用前位置→当前位置线段扫掠。
-- 刀区前方 [x,x+52] × [203,244]；测试擦边、无敌首尾与先后顺序。
local S = {}
local C = require "Game.Config"
local W = require "Game.World"
local P = require "Game.Player"
local E = require "Game.Enemies"
local B = require "Game.Combat"
local X = require "Game.Collision"
local R = require "Game.Replay"
local F = require "Game.Effects"
local STEP = C.STEP
local records, campaigns = {}, {}
local current = {}

local function encode(v)
    return cjson.encode(v)
end
S.Encode = encode
local function equal(actual, expected, why)
    assert(actual==expected, (why or "equality").." expected="..tostring(expected).." actual="..tostring(actual))
end
local function near(actual, expected, tolerance, why)
    assert(math.abs(actual-expected)<=(tolerance or 1e-8),
        (why or "numeric")..string.format(" expected=%.12g actual=%.12g",expected,actual))
end
local function note(k,v) current.evidence[k]=v end
local function test(id, category, source, fn)
    current={id=id,category=category,source=source,evidence={}}
    local start=os.clock()
    local ok,err=xpcall(fn,function(e) return debug.traceback(tostring(e),2) end)
    current.status=ok and "pass" or "fail"; current.duration_cpu=os.clock()-start
    if not ok then current.error=err end
    records[#records+1]=current
    print("SIMULATION_CASE "..encode(current))
    collectgarbage("collect")
end
local function fixture(level)
    local w=W.New(); w.verbose=false; w:Load(level or 1)
    return w
end
local function empty(w)
    -- 仅隔离单测：将波次放远，防止无关敌人与自动结算影响边界判定。
    w.schedule={{time=1e9,door=1,kind="melee"}}; w.spawnIndex=1
    w.enemies={}; w.objects={}; w.bullets={}; w.portals={}; w.platforms={}
    return w
end
local function opponent(w,kind,x,state)
    local e=E.New(w,kind,x); E.Set(w,e,state or "idle", "Idle"); w.enemies[#w.enemies+1]=e; return e
end
local function bullet(w,x,y,vx,vy,friendly)
    local b={x=x,y=y,vx=vx,vy=vy or 0,friendly=friendly or false,life=5,portalCD=0}
    w.bullets[#w.bullets+1]=b; return b
end
local function advance(w, n, keys)
    for i=1,n do w:Update(STEP,type(keys)=="function" and keys(i,w) or keys or {}) end
end
local function finishMode(w,mode,limit)
    local n=0; while w.mode==mode and n<(limit or 50000) do w:Update(STEP,{}); n=n+1 end
    return n
end
local function living(w)
    local count=0; for _,e in ipairs(w.enemies) do if not e.dead then count=count+1 end end; return count
end
local function arrays(w)
    return {frames=#w.replay.frames,particles=#w.particles,stains=#w.stains,
        bullets=#w.bullets,fx=#w.fx,trails=#w.trails,enemies=#w.enemies,objects=#w.objects}
end
local caps={frames=2700,particles=260,stains=140,bullets=80,fx=64,trails=8,enemies=12,objects=5}
local function enforceCaps(w,high)
    for k,n in pairs(arrays(w)) do
        high[k]=math.max(high[k] or 0,n)
        assert(n<=caps[k],k.." exceeded cap "..caps[k].." actual="..n)
    end
    local p=w.player
    assert(p.x==p.x and p.y==p.y and p.x>=9-1e-8 and p.x<=C.WIDTH-9+1e-8,"invalid player position")
end

-- 机器人只观察可见状态并返回固定键位A/D、J、K、L、Space、R。
-- J/K/Space/R按按下边沿提交；没有预演World.Update或修改状态的规划。
function S.BotKeys(w,bot)
    bot=bot or {}; bot.steps=(bot.steps or 0)+1
    if w.mode=="failed" then return {restart=true} end
    if w.mode~="playing" then return {} end
    local p=w.player
    local target,dist=nil,math.huge
    for _,e in ipairs(w.enemies) do
        if not e.dead then
            local d=math.abs(e.x-p.x)+math.abs(e.y-p.y)*0.35
            if d<dist then target=e; dist=d end
        end
    end
    local tx=target and target.x or nil
    if not tx and w.schedule[w.spawnIndex] then tx=C.DOORS[w.schedule[w.spawnIndex].door] end
    tx=tx or 336
    local dx=tx-p.x; local move=math.abs(dx)>35 and (dx>0 and 1 or -1) or 0
    local keys={slow=target~=nil,right=move>0,left=move<0}
    local direction=dx>=0 and 1 or -1
    -- 挥刀前先用普通移动步调整朝向。
    if p.dir~=direction and p.state~="roll" and p.state~="slash" then
        keys.left=direction<0; keys.right=direction>0
    end
    local barrel=nil
    for _,o in ipairs(w.objects) do
        if not o.broken and o.kind=="barrel" then
            if not barrel or math.abs(o.x-p.x)<math.abs(barrel.x-p.x) then barrel=o end
        end
    end
    -- 优先在爆炸伤害半径外清桶，再追逐敌人，绝不在桶中心反复跳跃。
    if barrel then
        tx=barrel.x; dx=tx-p.x; direction=dx>=0 and 1 or -1
        local distance=math.abs(dx)
        keys.slow=target~=nil
        keys.left=distance>60.5 and direction<0 or distance<57 and direction>0
        keys.right=distance>60.5 and direction>0 or distance<57 and direction<0
        if distance>=57 and distance<=62 and p.dir==direction and p.slashCD<=STEP*C.PLAYER_SLOW+1e-8 and p.state~="roll" then
            keys.slash=true; keys.left=false; keys.right=false
        elseif p.dir~=direction and p.state~="slash" and p.state~="roll" then
            keys.left=direction<0; keys.right=direction>0
        end
        bot.previous=bot.previous or {}
        if keys.slash and bot.previous.slash then keys.slash=false end
        bot.previous.slash=keys.slash==true
        return keys
    end
    local dangerBarrel=nil
    local canCut=p.slashCD<=STEP*C.PLAYER_SLOW+1e-8 and p.state~="roll"
    if target and target.state~="spawn" and math.abs(dx)<=60 and math.abs(p.y-target.y)<52 and p.dir==direction and canCut then
        local safe=not dangerBarrel or math.abs(p.y-dangerBarrel.y)>=58 or math.abs(p.x-dangerBarrel.x)>=57
        if safe then keys.slash=true; keys.left=false; keys.right=false end
    end
    -- 迎面子弹接近身体前挥刀弹反。
    local incoming=nil; local threat=math.huge
    for _,b in ipairs(w.bullets) do
        if not b.friendly and math.abs(b.y-(p.y-24))<35 and b.vx*(p.x-b.x)>0 then
            local arrival=math.abs((p.x-b.x)/b.vx)
            if arrival<threat then incoming=b; threat=arrival end
        end
    end
    if incoming and threat<0.45 then
        local face=incoming.x>=p.x and 1 or -1
        if p.dir==face and canCut and (not dangerBarrel or math.abs(p.y-dangerBarrel.y)>=58 or math.abs(p.x-dangerBarrel.x)>=57) then
            keys.slash=true; keys.left=false; keys.right=false
        elseif p.rollCD<=STEP*C.PLAYER_SLOW+1e-8 and p.state~="slash" then
            keys.roll=true
        elseif p.ground and p.state~="roll" then keys.jump=true end
    end
    -- 动作按下边沿：同一个动作不连续两步提交true。
    bot.previous=bot.previous or {}
    for _,name in ipairs({"slash","roll","jump","restart"}) do
        local held=keys[name]==true
        if held and bot.previous[name] then keys[name]=false end
        bot.previous[name]=keys[name]==true
    end
    return keys
end

local function mechanics()
    test("config.ten_chapters", "config", "Config.lua", function()
        equal(#C.chapters,10); equal(C.STEP,1/120); equal(table.concat(C.DOORS,","),"114,257,429,562")
        local counts={}; for i=1,10 do counts[#counts+1]=C.chapters[i].count; local w=fixture(i)
            equal(#w.schedule,C.chapters[i].count); local guns=0
            for _,s in ipairs(w.schedule) do assert(s.door>=1 and s.door<=4); if s.kind=="ranged" then guns=guns+1 end end
            equal(guns,C.chapters[i].gun)
        end
        note("wave_counts",counts)
    end)
    test("collision.sweep_edges", "collision", "Collision.lua", function()
        local a={x=100,y=100,w=20,h=20}
        near(X.Sweep(0,110,200,110,a,0),0.5); equal(X.Sweep(0,99,200,99,a,0),nil)
        near(X.Sweep(110,0,110,200,a,0),0.5); near(X.Sweep(200,110,0,110,a,0),0.4)
        equal(X.Sweep(110,110,110,110,a,0),0); equal(X.Sweep(99,110,99,110,a,0),nil)
        assert(X.Overlap(a,{x=120,y=120,w=1,h=1})); assert(not X.Overlap(a,{x=120.001,y=120,w=1,h=1}))
    end)
    test("collision.ranged_body_contract", "collision", "Collision.lua", function()
        local body=X.Body({kind="ranged",x=100,y=246,state="idle"}); note("body",body)
        equal(body.w,18,"planned ranged [x-9,x+9] width")
    end)
    for _,kind in ipairs({"melee","ranged"}) do
        test("combat.one_slash."..kind,"combat","Combat.lua",function()
            local w=empty(fixture()); local e=opponent(w,kind,w.player.x+35)
            w:Update(STEP,{slash=true}); assert(not e.dead,"windup must not kill")
            advance(w,4); assert(e.dead,"single legal J must kill")
            equal(w.stats.kills,1); equal(w.stats.slashes,1); assert(not w.player.dead)
            B.Update(w,STEP); equal(w.stats.kills,1,"no duplicate corpse kills")
        end)
    end
    test("combat.multi_kill_and_dead_no_attack", "combat", "World.lua/Combat.lua/Enemies.lua", function()
        local w=empty(fixture()); local a=opponent(w,"melee",w.player.x+25,"hit"); a.timer=0.08; a.dir=-1
        local b=opponent(w,"ranged",w.player.x+35)
        P.Set(w.player,"slash","Slash"); w.player.stateTime=0.05
        w:Update(STEP,{}); assert(a.dead and b.dead); assert(not w.player.dead,"dead enemy cannot trade-hit")
        equal(w.stats.kills,2)
    end)
    test("combat.spawn_one_slash_lethal", "combat", "Combat.lua", function()
        local w=empty(fixture()); local e=opponent(w,"melee",w.player.x+25,"spawn")
        P.Set(w.player,"slash","Slash"); w.player.stateTime=0.05; B.Update(w,STEP)
        assert(e.dead,"出生敌人也必须一刀死"); equal(w.stats.kills,1)
    end)
    test("combat.dead_player_cannot_slash", "combat", "Player.lua/Collision.lua", function()
        local w=empty(fixture()); local e=opponent(w,"melee",w.player.x+25)
        w:KillPlayer("fixture"); local before=w.stats.slashes
        advance(w,30,{slash=true,roll=true,jump=true}); assert(not e.dead); equal(w.stats.slashes,before)
        assert(not X.BladeActive(w.player)); equal(w.player.state,"dead")
    end)
    test("combat.melee_one_hit_death", "combat", "Enemies.lua/World.lua", function()
        local w=empty(fixture()); local e=opponent(w,"melee",w.player.x+25,"hit"); e.dir=-1; e.timer=0.10
        E.Update(w,e,STEP); assert(w.player.dead); equal(w.mode,"dying"); equal(w.cause,"刀锋")
    end)
    test("combat.shield_one_hit_death", "combat", "Enemies.lua", function()
        local w=empty(fixture()); local e=opponent(w,"ranged",w.player.x+20,"shield"); e.dir=-1; e.timer=0.26
        E.Update(w,e,STEP); assert(w.player.dead); equal(w.cause,"盾击")
    end)
    test("combat.bullet_swept_one_hit", "combat", "Combat.lua/Collision.lua", function()
        local w=empty(fixture()); bullet(w,200,w.player.y-24,-24000)
        B.Update(w,STEP); assert(w.player.dead); equal(w.cause,"子弹"); equal(#w.bullets,0)
    end)
    test("combat.friendly_never_hurts_player", "combat", "Combat.lua", function()
        local w=empty(fixture()); bullet(w,200,w.player.y-24,-24000,0,true); B.Update(w,STEP)
        assert(not w.player.dead)
    end)
    for _,t in ipairs({0.044999,0.045,0.045001,0.309999,0.31,0.310001}) do
        local at=t
        test("roll.boundary."..string.format("%.6f",at),"roll","Collision.lua/Combat.lua/Enemies.lua",function()
            local expected=at>=0.045 and at<=0.31
            local w=empty(fixture()); P.Set(w.player,"roll","Roll"); w.player.stateTime=at
            equal(X.Invulnerable(w.player),expected)
            bullet(w,w.player.x+35,w.player.y-8,-5000); B.Update(w,STEP)
            equal(w.player.dead,not expected,"bullet iframe boundary")
            local m=empty(fixture()); P.Set(m.player,"roll","Roll"); m.player.stateTime=at
            local e=opponent(m,"melee",m.player.x+25,"hit"); e.dir=-1; e.timer=0.12; E.Update(m,e,STEP)
            equal(m.player.dead,not expected,"melee iframe boundary")
            note("time",at); note("expected_iframe",expected)
        end)
    end
    test("roll.legal_lifecycle_and_wall", "roll", "Player.lua", function()
        local w=empty(fixture()); w.player.x=650
        local states,anims={},{}
        for i=1,100 do w:Update(STEP,{roll=i==1}); states[w.player.state]=true; anims[w.player.anim]=true
            assert(w.player.x<=667); if i==3 then assert(not X.Invulnerable(w.player)) end
        end
        assert(states.roll and states.recover and states.idle); assert(anims.Roll and anims.Squat)
        equal(w.stats.rolls,1); note("states",states)
    end)
    test("roll.cooldown_prevents_spam", "roll", "Player.lua", function()
        local w=empty(fixture()); advance(w,60,function(i) return {roll=i%2==1} end)
        equal(w.stats.rolls,1); advance(w,12,{roll=true}); equal(w.stats.rolls,2)
    end)
    test("parry.front_sweep_then_reflect_kill", "parry", "Combat.lua", function()
        local w=empty(fixture()); local e=opponent(w,"ranged",200)
        P.Set(w.player,"slash","Slash"); w.player.stateTime=0.08
        bullet(w,120,w.player.y-24,-9600); B.Update(w,STEP)
        equal(w.stats.parries,1); assert(not w.player.dead); assert(w.bullets[1].friendly)
        for _=1,120 do B.Update(w,STEP); if e.dead then break end end
        assert(e.dead); equal(w.stats.reflectKills,1); equal(w.stats.kills,1)
        note("stats",w.stats)
    end)
    test("parry.body_blade_tie_prioritizes_blade", "parry", "Combat.lua", function()
        local w=empty(fixture()); P.Set(w.player,"slash","Slash"); w.player.stateTime=0.1
        bullet(w,w.player.x,w.player.y-24,-100); B.Update(w,STEP)
        equal(w.stats.parries,1); assert(not w.player.dead)
    end)
    test("parry.rear_body_before_blade_dies", "parry", "Combat.lua", function()
        local w=empty(fixture()); P.Set(w.player,"slash","Slash"); w.player.stateTime=0.1
        bullet(w,0,w.player.y-24,12000); B.Update(w,STEP)
        assert(w.player.dead); equal(w.stats.parries,0)
    end)
    test("parry.windup_and_recovery_no_parry", "parry", "Collision.lua", function()
        for _,t in ipairs({0.024999,0.025,0.20,0.200001}) do
            local p=P.New(); P.Set(p,"slash","Slash"); p.stateTime=t
            equal(X.BladeActive(p),t>=0.025 and t<=0.20)
        end
    end)
    test("time.slow_world_player_ratios", "time", "World.lua", function()
        local w=empty(fixture()); advance(w,120,{slow=true})
        near(w.time,0.22); near(w.realTime,1); near(w.player.animTime,0.72)
        near(w.stats.slowSeconds,1); near(w.lastWorldDT,STEP*0.22)
        note("world_seconds",w.time); note("player_animation_seconds",w.player.animTime)
        note("player_world_ratio",w.player.animTime/w.time)
    end)
    test("time.bullet_enemy_fx_particles_slow", "time", "World.lua/Effects.lua", function()
        local w=empty(fixture()); w.player.x=50
        local e=opponent(w,"melee",600,"walk"); e.timer=0
        local b=bullet(w,400,100,100); F.Add(w,"jump",100,100,1)
        local part={x=300,y=100,vx=100,vy=0,life=1,color="wood",size=1,blood=false}; w.particles={part}
        w:Update(STEP,{slow=true})
        near(e.timer,STEP*0.22); near(e.animTime,STEP*0.22); near(b.x-400,100*STEP*0.22)
        near(w.fx[1].time,STEP*0.22); near(part.life,1-STEP*0.22)
    end)
    test("input.left_right_cancel", "input", "Player.lua", function()
        local w=empty(fixture()); local start=w.player.x; advance(w,120,{left=true,right=true})
        near(w.player.x,start); equal(w.player.dir,1); equal(w.player.vx,0)
        advance(w,30,{right=true}); local vel=w.player.vx; local pos=w.player.x
        advance(w,30,{left=true,right=true}); assert(w.player.vx<vel and w.player.vx>=0)
        assert(w.player.x>=pos); note("residual_velocity",w.player.vx)
    end)
    test("movement.legal_jump_land", "movement", "Player.lua", function()
        local w=empty(fixture()); local minY=246; local land=false
        for i=1,150 do w:Update(STEP,{jump=i==1}); minY=math.min(minY,w.player.y); land=land or w.player.anim=="Land" end
        assert(minY<210); assert(land); near(w.player.y,246); assert(w.player.ground); equal(w.stats.jumps,1)
        note("jump_apex",minY)
    end)
    test("movement.wallslide_and_walljump", "movement", "Player.lua", function()
        local w=empty(fixture()); advance(w,60,{left=true}); near(w.player.x,9)
        local saw=false
        for i=1,80 do w:Update(STEP,{left=true,jump=i==1}); if w.player.anim=="Wallslide" then saw=true; break end end
        assert(saw,"legal jump at left wall should enter wallslide"); local before=w.player.x
        w:Update(STEP,{jump=true,right=true}); assert(w.player.x>before); assert(w.player.vy<0); equal(w.player.dir,1)
        assert(w.stats.jumps>=2)
    end)
    test("movement.platform_from_below_and_land", "movement", "Player.lua", function()
        local w=empty(fixture(5)); w.platforms={{x=150,y=210,w=96}}; w.player.x=200
        local upThrough,land=false,false
        for i=1,160 do w:Update(STEP,{jump=i==1})
            if w.player.y<210 and w.player.vy<0 then upThrough=true end
            if w.player.ground and math.abs(w.player.y-210)<1e-8 then land=true end
        end
        assert(upThrough); assert(land); near(w.player.y,210)
    end)
    test("movement.planned_first_platform_reachable", "movement", "Player.lua/World.lua", function()
        local w=fixture(5); w.schedule={{time=1e9,door=1,kind="melee"}}; w.objects={}
        advance(w,104,{right=true}); local start=w.player.x
        local minY, landed=246, false
        for i=1,180 do w:Update(STEP,{jump=i==1}); minY=math.min(minY,w.player.y)
            landed=landed or w.player.ground and w.player.y==192
        end
        note("launch_x",start); note("apex",minY); note("platform_y",192)
        assert(landed,"first planned y192 platform must be reachable with normal jump")
    end)
    test("movement.no_air_double_jump", "movement", "Player.lua", function()
        local w=empty(fixture()); w:Update(STEP,{jump=true}); w:Update(STEP,{})
        local n=w.stats.jumps; w:Update(STEP,{jump=true}); equal(w.stats.jumps,n,"second press in air cannot jump")
    end)
    test("flow.R_only_settlement", "flow", "World.lua", function()
        for _,mode in ipairs({"title","playing","dying","replay","rewind","ending"}) do
            local w=empty(fixture()); w.mode=mode; equal(w:Restart(),false,"R mode="..mode)
        end
        local w=empty(fixture()); advance(w,60,{restart=true}); equal(w.mode,"playing"); equal(w.attempt,1)
        w:KillPlayer("fixture"); finishMode(w,"dying"); equal(w.mode,"failed"); w:Update(STEP,{restart=true}); equal(w.mode,"rewind")
        local c=empty(fixture(4)); c.mode="complete"; equal(c:Restart(),true); equal(c.level,4); equal(c.attempt,2)
    end)
    test("flow.next_restricted_and_ending", "flow", "World.lua", function()
        local w=fixture(3); equal(w:Next(),false); w.mode="complete"; equal(w:Next(),true); equal(w.level,4)
        w:Load(10); w.mode="complete"; assert(w:Next()); equal(w.mode,"ending"); equal(w.level,10)
    end)
    test("spawn.waiting_waves_block_victory", "spawn", "World.lua", function()
        local w=fixture(); advance(w,215,{}); equal(#w.enemies,0); equal(w.mode,"playing")
        advance(w,2,{}); equal(#w.enemies,1); equal(w.spawnIndex,2); equal(w.enemies[1].state,"spawn")
        equal(w.mode,"playing"); note("first_spawn_world_time",w.time)
    end)
    test("spawn.all_four_doors_actual", "spawn", "World.lua", function()
        local w=fixture(2); local seen={}; w.player.x=9
        -- 隔离单测使用实际波次调度，推进到出生点立即记录坐标，
        -- 不根据敌人移动后的坐标推测出生门。
        for i=1,4 do
            local spawn=w.schedule[w.spawnIndex]; w.time=spawn.time-STEP*0.5
            local n=#w.enemies; w:Update(STEP,{})
            assert(#w.enemies==n+1); local e=w.enemies[#w.enemies]
            near(e.x,C.DOORS[spawn.door]); seen[spawn.door]=true
            -- 仅隔离单测，移除旧敌人避免干扰之后的门刷新判定。
            w.enemies={}
        end
        for i=1,4 do assert(seen[i],"missing door "..i) end
        note("doors_seen",seen)
    end)
    test("spawn.slow_uses_world_time", "spawn", "World.lua", function()
        local w=fixture(); advance(w,900,{slow=true}); equal(#w.enemies,0); assert(w.time<1.8)
        advance(w,90,{slow=true}); assert(#w.enemies>=1); note("real_first_spawn_after",w.realTime)
    end)
    test("FSM.melee_all_states", "FSM", "Enemies.lua", function()
        local w=empty(fixture()); w.player.x=9; w.player.y=100
        local e=opponent(w,"melee",600,"spawn")
        for _=1,1500 do E.Update(w,e,STEP); if e.state=="run" then break end end
        assert(w.visited["melee:walk"] and w.visited["melee:run"])
        w.player.x=e.x-20; w.player.y=246
        for _=1,250 do E.Update(w,e,STEP); if e.state=="hit" then w.player.y=100 end; if w.visited["melee:recover"] and e.state=="idle" then break end end
        E.Kill(w,e,1,"fixture"); for _=1,100 do E.Update(w,e,STEP) end
        for _,st in ipairs({"spawn","idle","walk","run","switch","hit","recover","hurt","death"}) do assert(w.visited["melee:"..st],"missing "..st) end
        note("visited",w.visited)
    end)
    test("FSM.ranged_all_states", "FSM", "Enemies.lua", function()
        local w=empty(fixture()); w.player.x=9; w.player.y=100
        local e=opponent(w,"ranged",600,"spawn")
        for _=1,900 do E.Update(w,e,STEP); if w.visited["ranged:walk"] and e.state=="idle" then break end end
        w.player.x=e.x-50
        for _=1,150 do E.Update(w,e,STEP); if w.visited["ranged:run"] and e.state=="idle" then break end end
        w.player.x=e.x-160; w.player.y=246
        for _=1,300 do E.Update(w,e,STEP); if w.visited["ranged:shootend"] and e.state=="idle" then break end end
        equal(w.stats.shots,1); w.player.x=e.x-20
        for _=1,150 do E.Update(w,e,STEP); if e.state=="shield" then w.player.y=100 end; if w.visited["ranged:recover"] and e.state=="idle" then break end end
        E.Kill(w,e,1,"fixture"); for _=1,40 do E.Update(w,e,STEP) end
        for _,st in ipairs({"spawn","idle","walk","run","switch","shoot","shootend","shield","recover","shieldhit","death"}) do assert(w.visited["ranged:"..st],"missing "..st) end
        note("visited",w.visited)
    end)
    test("FSM.high_level_multi_shot_contract", "FSM", "Enemies.lua", function()
        local w=empty(fixture(10)); w.player.x=100
        local e=opponent(w,"ranged",300,"switch"); e.aimX=100; e.aimY=222
        for _=1,180 do E.Update(w,e,STEP); if e.state=="shootend" then break end end
        note("shots_in_high_level_shoot",w.stats.shots)
        assert(w.stats.shots>=2,"plan promises high-level bursts; Shoot emits only one")
    end)
    test("replay.normal_real_timeline_no_fast_forward", "replay", "Replay.lua", function()
        local w=empty(fixture()); advance(w,240,{slow=true}); advance(w,120,{})
        local last=w.replay.frames[#w.replay.frames]; R.Begin(w,false)
        local n=0; while not R.Update(w,STEP) and n<2000 do n=n+1 end
        local duration=(n+1)*STEP; note("replay_seconds",duration); note("world_end",last.worldTime); note("real_end",last.realTime)
        note("contract","当前计划保留录像中的慢时，按实际时间1倍播放；不是旧版去慢时的世界轴")
        near(duration,last.realTime-w.replay.frames[1].realTime+0.25,STEP*1.1)
        assert(duration>last.worldTime,"玩家录像不得按0.22世界时钟快进"); equal(w.stats.kills,0)
    end)
    test("replay.copy_isolation_no_reexecution", "replay", "Replay.lua", function()
        local w=empty(fixture()); advance(w,30,{right=true,slash=true}); local f=w.replay.frames[1]
        local x=f.player.x; w.player.x=500; equal(f.player.x,x)
        R.Begin(w,false); local stats={}; for k,v in pairs(w.stats) do stats[k]=v end; local seed=w.seed
        for _=1,100 do R.Update(w,STEP) end
        for k,v in pairs(stats) do equal(w.stats[k],v) end; equal(w.seed,seed); equal(w.player.x,500)
    end)
    test("replay.force_capture_does_not_double_accum", "replay", "Replay.lua", function()
        local w=empty(fixture()); w.lastWorldDT=STEP; w.replay.accum=0
        R.Capture(w,true); local accum=w.replay.accum; R.Capture(w,true)
        note("before",accum); note("after",w.replay.accum)
        near(w.replay.accum,accum,1e-8,"forced duplicate must not double-count lastWorldDT")
    end)
    test("rewind.only_current_level", "rewind", "World.lua/Replay.lua", function()
        local w=fixture(2); w.verbose=false; advance(w,60,{right=true}); local old=w.replay
        w:Load(6); assert(w.replay~=old); equal(#w.replay.frames,1)
        local start=w.player.x; advance(w,60,{right=true}); w:KillPlayer("fixture"); finishMode(w,"dying")
        equal(w.mode,"failed"); assert(w:Restart()); local reversed={}
        while w.mode=="rewind" do
            if w.view then reversed[#reversed+1]=w.view.player.x end
            w:Update(STEP,{})
        end
        equal(w.level,6); equal(w.mode,"playing"); equal(w.attempt,2); near(w.player.x,start)
        equal(w.stats.kills,0); equal(#w.replay.frames,1); note("rewind_samples",#reversed)
    end)
    test("rewind.maximum_four_real_seconds", "rewind", "Replay.lua", function()
        local w=empty(fixture(7)); advance(w,1200,{})
        w:KillPlayer("fixture"); finishMode(w,"dying"); assert(w:Restart())
        local n=finishMode(w,"rewind",1000); note("rewind_seconds",n*STEP)
        assert(n*STEP<=4+STEP*2); equal(w.level,7)
    end)
    test("objects.crate_slash_shards_kill", "objects", "Combat.lua", function()
        local w=empty(fixture()); w.player.x=100
        w.objects={{kind="crate",x=145,y=246,broken=false}}
        local e=opponent(w,"melee",220)
        w:Update(STEP,{slash=true}); advance(w,4); assert(w.objects[1].broken); equal(w.stats.breaks,1)
        advance(w,100); assert(e.dead,"crate shards kill enemy"); note("stats",w.stats)
    end)
    test("objects.barrel_chain_kills", "objects", "Combat.lua", function()
        local w=empty(fixture()); w.player.x=9
        w.objects={{kind="barrel",x=220,y=246,broken=false},{kind="barrel",x=290,y=246,broken=false},{kind="crate",x=350,y=246,broken=false}}
        local a=opponent(w,"melee",230); local b=opponent(w,"ranged",340)
        bullet(w,100,225,24000,0,true); B.Update(w,STEP)
        equal(w.stats.breaks,3); assert(a.dead and b.dead); equal(w.stats.blastKills,2); assert(not w.player.dead)
        B.Break(w,w.objects[1],1); equal(w.stats.breaks,3); note("stats",w.stats)
    end)
    test("objects.player_blast_and_roll_protection", "objects", "Combat.lua", function()
        for _,roll in ipairs({false,true}) do
            local w=empty(fixture()); w.objects={{kind="barrel",x=w.player.x+30,y=246,broken=false}}
            if roll then P.Set(w.player,"roll","Roll"); w.player.stateTime=0.1 end
            B.Break(w,w.objects[1],1); equal(w.player.dead,not roll)
        end
    end)
    test("objects.safe_legal_edge_barrel_slash", "objects", "Combat.lua/Player.lua", function()
        local w=empty(fixture()); w.player.x=100; w.objects={{kind="barrel",x=160,y=246,broken=false}}
        w:Update(STEP,{slash=true}); advance(w,5); assert(w.objects[1].broken); assert(not w.player.dead)
        note("distance",60)
    end)
    test("objects.hostile_bullet_intercepts_before_player", "objects", "Combat.lua", function()
        local w=empty(fixture()); w.player.x=400
        w.objects={{kind="crate",x=338,y=246,broken=false}}
        bullet(w,300,222,24000); B.Update(w,STEP)
        note("player_dead",w.player.dead); note("crate_broken",w.objects[1].broken)
        assert(w.objects[1].broken,"nearest crate must intercept bullet before body")
        assert(not w.player.dead,"bullet cannot hit player behind crate in same swept step")
    end)
    test("objects.chain_respects_vertical_distance", "objects", "Combat.lua", function()
        local w=empty(fixture()); w.player.x=9
        w.objects={{kind="barrel",x=220,y=246,broken=false},{kind="crate",x=220,y=100,broken=false}}
        B.Break(w,w.objects[1],1); note("remote_crate_broken",w.objects[2].broken)
        assert(not w.objects[2].broken,"blast must not chain to object 146px above barrel")
    end)
    test("portal.player_and_bullet_pair", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=70
        B.Portals(w,w.player,STEP,false); near(w.player.x,622); near(w.player.portalCD,0.65)
        local b=bullet(w,606,220,-100); B.Portals(w,b,STEP,true); near(b.x,54); near(b.portalCD,0.65)
        equal(w.stats.teleports,2); B.Portals(w,b,STEP,true); equal(w.stats.teleports,2)
    end)
    test("portal.no_loop_and_height_gate", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=70; w.player.y=170
        B.Portals(w,w.player,STEP,false); equal(w.stats.teleports,0)
        w.player.y=246; B.Portals(w,w.player,STEP,false); equal(w.stats.teleports,1)
        w.player.x=606; for _=1,20 do B.Portals(w,w.player,STEP,false) end
        equal(w.stats.teleports,1,"portal cooldown stops loop"); assert(w.player.portalCD>0)
    end)
    test("portal.player_650ms_cooldown_real_clock", "portal", "Player.lua/Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=70
        w:Update(STEP,{}); local n=0
        while w.player.portalCD>0 and n<120 do w:Update(STEP,{}); n=n+1 end
        note("normal_cooldown_seconds",n*STEP); note("decrements", "P.Update and B.Portals both decrement player portalCD")
        near(n*STEP,0.65,STEP*1.1,"player portal cooldown should be 650ms, not half")
    end)
    test("portal.swept_fast_bullet", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=300
        local b=bullet(w,40,220,7200); B.Update(w,STEP)
        note("x_after",b.x); note("teleports",w.stats.teleports)
        equal(w.stats.teleports,1,"swept bullet crossing portal must teleport, not tunnel")
    end)
    test("portal.earliest_portal_before_enemy", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=300
        local e=opponent(w,"ranged",67); bullet(w,81,222,-300,0,true)
        B.Update(w,STEP); note("teleports",w.stats.teleports); note("enemy_dead",e.dead)
        assert(not e.dead,"先入门，入口后方敌人不能先被击中"); equal(w.stats.teleports,1)
    end)
    test("portal.earliest_enemy_before_portal", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=300
        local e=opponent(w,"ranged",105); bullet(w,120,222,-7200,0,true)
        B.Update(w,STEP); assert(e.dead); equal(w.stats.teleports,0,"先撞敌消耗子弹，不可再入门")
        equal(#w.bullets,0)
    end)
    test("portal.earliest_crate_before_portal", "portal", "Combat.lua", function()
        local w=empty(fixture(4)); w.portals={{x=70},{x=606}}; w.player.x=300
        w.objects={{kind="crate",x=105,y=246,broken=false}}; bullet(w,125,222,-8400)
        B.Update(w,STEP); assert(w.objects[1].broken); equal(w.stats.teleports,0)
    end)
    test("FSM.spawn_Idle_frame_duration", "FSM", "Enemies.lua", function()
        local evidence={}
        for _,kind in ipairs({"melee","ranged"}) do
            local w=empty(fixture()); w.player.x=9; w.player.y=100
            local e=opponent(w,kind,600,"spawn"); local n=0
            while e.state=="spawn" and n<200 do E.Update(w,e,STEP); n=n+1 end
            local duration=n*STEP; local expected=kind=="melee" and 0.6 or 1.0
            assert(duration>=expected-1e-8,"出生Idle需播完一轮"); assert(duration<=expected+STEP*1.1)
            evidence[#evidence+1]={kind=kind,duration=duration,minimum=expected}
        end
        note("spawn_duration",evidence)
    end)
    test("movement.player_FSM_animation_coverage", "FSM", "Player.lua", function()
        local w=empty(fixture()); local seen={}
        local function sample(keys,n)
            for _=1,n do w:Update(STEP,keys or {}); seen[w.player.anim]=true end
        end
        sample({},1); sample({right=true},35); sample({},30)
        sample({jump=true},1); sample({},150); sample({roll=true},1); sample({},90)
        sample({slash=true},1); sample({},40)
        sample({left=true},500); sample({jump=true,left=true},1)
        for _=1,100 do sample({left=true},1); if seen.Wallslide then break end end
        w:KillPlayer("fixture"); sample({},1)
        for _,name in ipairs({"Idle","Prerun","Run","Stoprun","Jump","Land","Squat","Roll","Slash","Wallslide","Hit"}) do
            assert(seen[name],"未实际触发玩家动画 "..name)
        end
        note("observed_animation_states",seen)
    end)
    test("flow.final_corpse_completes_before_replay", "flow", "World.lua/Enemies.lua", function()
        local w=empty(fixture()); w.schedule={}; local e=opponent(w,"melee",w.player.x+30)
        w:Update(STEP,{slash=true}); advance(w,4); assert(e.dead)
        local start=w.time; local states={}; local n=0
        while w.mode=="playing" and n<250 do
            states[e.state]=true; w:Update(STEP,{}); n=n+1
        end
        assert(states.hurt and states.death); equal(w.mode,"replay")
        note("clear_world_seconds",w.time-start); note("final_corpse_timer",e.timer)
        assert(w.time-start>=1.1,"清场前需完成受击和死亡帧"); assert(e.timer>=0.6)
    end)
    test("time.fixed_step_clamp_and_negative", "time", "World.lua", function()
        local w=empty(fixture()); w:Update(-1,{}); near(w.time,0)
        w:Update(10,{}); near(w.time,0.05); near(w.realTime,0.05)
    end)
    test("roll.integrated_sampled_boundary_normal_slow", "roll", "Player.lua/Collision.lua/World.lua", function()
        local samples={}
        for _,slow in ipairs({false,true}) do
            local w=empty(fixture()); local previous=0; local first,last,after=nil,nil,nil
            for i=1,140 do
                w:Update(STEP,{roll=i==1,slow=slow})
                if w.player.state=="roll" then
                    local t=w.player.stateTime
                    equal(X.Invulnerable(w.player),t>=0.045 and t<=0.31)
                    if X.Invulnerable(w.player) then first=first or t; last=t
                    elseif last and not after then after=t end
                    previous=t
                end
            end
            assert(first and last and after); assert(first>=0.045 and first<0.045+STEP+1e-8)
            assert(last<=0.31 and last>0.31-STEP-1e-8); assert(after>0.31)
            samples[#samples+1]={slow=slow,first=first,last=last,after=after}
        end
        note("actual_fixed_step_boundaries",samples)
    end)
    test("replay.real_time_sampling_30Hz_during_slow", "replay", "Replay.lua", function()
        local w=empty(fixture()); advance(w,120,{slow=true})
        note("frames_per_real_second",#w.replay.frames-1)
        assert(#w.replay.frames>=29 and #w.replay.frames<=32,"慢时录像仍应按实际30Hz采样")
        R.Begin(w,false); for _=1,60 do R.Update(w,STEP) end
        near(w.replay.realCursor,0.5); assert(w.view.realTime<=0.5+1e-8)
        assert(w.view.realTime>=0.5-1/30-1e-8)
    end)
    test("input.main_nil_actions_focus_recovery", "input", "main.lua", function()
        local file=cache:GetFile("main.lua"); assert(file,"无法读取实际main入口")
        local lines={}; while not file:IsEof() do lines[#lines+1]=file:ReadLine() end; file:Dispose()
        local calls={}; local fakeInput={focus=false,GetKeyDown=function() return false end,
            GetKeyPress=function(self,key) return self.slash and key==KEY_J or false end,
            GetMouseButtonPress=function() return false end,GetMouseButtonDown=function() return false end}
        local env=setmetatable({input=fakeInput,require=function(name)
            if name=="Game.World" then return W elseif name=="Game.Config" then return C else return {} end
        end},{__index=_G})
        local main=assert(load(table.concat(lines,"\n"),"@scripts/main.lua","t",env))()
        main.world={Update=function(self,dt,keys) local copy={}; for k,v in pairs(keys) do copy[k]=v end; calls[#calls+1]=copy end}
        main.audio={Update=function() end}; main.interface={Update=function() end}
        local function tick(dt) env.HandleUpdate("Update",{GetFloat=function() return dt end}) end
        tick(STEP); fakeInput.focus=true; fakeInput.slash=true; tick(STEP)
        assert(calls[#calls].slash,"失焦返回空表后恢复，J仍须缓存并执行")
        main.testInput=function() return {} end; tick(STEP)
        main.testInput=function() return {roll=true} end; tick(STEP)
        assert(calls[#calls].roll,"稀疏机器人输入不能永久删除pending字段")
        note("entry_executed","实际main.lua经load独立环境执行；只替换音画依赖与Input来源")
    end)
    test("input.main_focus_loss_clears_buffered_press", "input", "main.lua", function()
        local file=cache:GetFile("main.lua"); assert(file)
        local lines={}; while not file:IsEof() do lines[#lines+1]=file:ReadLine() end; file:Dispose()
        local calls={}; local fakeInput={focus=true,slash=true,GetKeyDown=function() return false end,
            GetKeyPress=function(self,key) return self.slash and key==KEY_J or false end,
            GetMouseButtonPress=function() return false end,GetMouseButtonDown=function() return false end}
        local env=setmetatable({input=fakeInput,require=function(name)
            if name=="Game.World" then return W elseif name=="Game.Config" then return C else return {} end
        end},{__index=_G})
        local main=assert(load(table.concat(lines,"\n"),"@scripts/main.lua","t",env))()
        main.world={Update=function(self,dt,keys) calls[#calls+1]={slash=keys.slash} end}
        main.audio={Update=function() end}; main.interface={Update=function() end}
        local function tick(dt) env.HandleUpdate("Update",{GetFloat=function() return dt end}) end
        tick(STEP/4); equal(#calls,0)
        fakeInput.focus=false; fakeInput.slash=false; tick(STEP)
        note("slash_after_focus_loss",calls[1].slash)
        assert(not calls[1].slash,"失去焦点必须清除积压J，不能继续执行上帧按下")
    end)
    test("determinism.repeated_legal_input_stream", "determinism", "World.lua", function()
        local a=fixture(); local b=fixture()
        for i=1,4000 do
            local keys={right=i%200<100,left=i%200>=100,slash=i%35==0,slow=i%7~=0,roll=i%103==0,jump=i%151==0,restart=i%60==0}
            a:Update(STEP,keys); b:Update(STEP,keys)
            near(a.player.x,b.player.x); near(a.player.y,b.player.y); equal(a.mode,b.mode); equal(a.seed,b.seed)
            equal(a.stats.kills,b.stats.kills); equal(#a.enemies,#b.enemies); equal(#a.bullets,#b.bullets)
        end
        note("compared_steps",4000)
    end)
    test("stress.direct_array_cap_adversarial", "stress", "Effects.lua/Combat.lua/Replay.lua", function()
        local w=empty(fixture()); local high={}
        F.Particles(w,300,100,2000,"wood",1)
        for i=1,1000 do F.Add(w,"jump",300,100,1); F.Stain(w,300,246,false) end
        for i=1,1000 do bullet(w,300,100,0,0,true) end
        B.Update(w,STEP); enforceCaps(w,high)
        for i=1,2800 do w.time=i/30; w.realTime=i/30; R.Capture(w,true) end
        enforceCaps(w,high); equal(#w.replay.frames,2700); note("high_water",high)
        collectgarbage("collect"); note("live_memory_at_full_snapshot_caps_kib",collectgarbage("count"))
        note("memory_budget_note","此对抗单测将所有快照存满粒子/血斑/子弹上限，数组有界但并非低内存预算")
    end)
end

local function campaign()
    local w=W.New(); w.verbose=false; w:Start()
    local bot={}
    local actions={left=0,right=0,slash=0,roll=0,jump=0,slow=0,restart=0}
    local transitions, traceDigest, high={}, 0, {}
    local total=0; local summary={}
    -- 每关独立记录，但十关均使用同一World，靠正常Next推进。
    for expected=1,10 do
        test("campaign.legal_inputs.level_"..expected,"campaign","World.lua/Player.lua/Enemies.lua/Combat.lua",function()
            equal(w.level,expected,"no Load between levels")
            local previous=w.mode; local startTime=os.clock(); local retries=0
            local pulses={}; local n=0
            while w.mode~="complete" and n<45000 do
                local keys=S.BotKeys(w,bot)
                for name,v in pairs(keys) do
                    assert(type(v)=="boolean" and actions[name]~=nil,"illegal input key "..name)
                    if v then actions[name]=actions[name]+1 end
                end
                local beforeMode=w.mode; local beforeLevel=w.level
                -- 只允许这次Update修改世界，机器人仅观察并返回按键。
                w:Update(STEP,keys)
                equal(w.level,beforeLevel,"level cannot change during attempt")
                total=total+1; n=n+1
                enforceCaps(w,high)
                if w.mode~=previous then
                    local tr={step=total,level=w.level,from=previous,to=w.mode,cause=w.cause,time=w.time}
                    transitions[#transitions+1]=tr; print("SIMULATION_BOT_TRANSITION "..encode(tr)); previous=w.mode
                    if w.mode=="failed" then retries=retries+1; if retries>5 then break end end
                end
                if n%240==0 or keys.slash or keys.roll or keys.jump or keys.restart then
                    traceDigest=(traceDigest*31+math.floor(w.player.x*10)+math.floor(w.player.y*10)+w.stats.kills*97+n)%2147483647
                    if #pulses<500 then pulses[#pulses+1]={step=n,x=w.player.x,y=w.player.y,mode=w.mode,keys=keys,kills=w.stats.kills} end
                end
            end
            local row={level=expected,mode=w.mode,steps=n,retries=retries,stats=w.stats,
                world_seconds=w.time,real_seconds=w.realTime,living=living(w),spawnIndex=w.spawnIndex,
                scheduled=#w.schedule,high_water=high,trace_digest=traceDigest,trace=pulses,cpu=os.clock()-startTime}
            campaigns[#campaigns+1]=row; note("result",row)
            equal(w.mode,"complete","legal-input robot did not reach settlement")
            equal(w.stats.kills,C.chapters[expected].count); equal(living(w),0); assert(w.spawnIndex>#w.schedule)
            assert(w:Next(),"normal Next must progress"); equal(w.mode,expected<10 and "playing" or "ending")
        end)
        if w.level~=expected+1 and expected<10 then
            -- 失败后绝不通过Load跳关，后续关卡如实标记未运行。
            for k=expected+1,10 do
                current={id="campaign.legal_inputs.level_"..k,category="campaign",source="World.lua",status="blocked",
                    error="Previous campaign level did not complete; no forced Load or enemy removal permitted",evidence={}}
                records[#records+1]=current; print("SIMULATION_CASE "..encode(current))
            end
            break
        end
    end
    summary={total_steps=total,actions=actions,transitions=transitions,trace_digest=traceDigest,levels=campaigns,
        mode=w.mode,level=w.level,high_water=high,no_state_mutation=true,input_api="World.Update(C.STEP, action booleans); World.Start/Next only"}
    S.campaign=summary
end

local function longrun()
    test("stress.longrun_200000_legal_steps","stress","World.lua/Effects.lua/Replay.lua/Combat.lua",function()
        local w=W.New(); w.verbose=false; w:Start(); local bot={}; local high={}; local checkpoints={}
        local complete,failures,active,replays=0,0,0,0
        local maxMemory=0; collectgarbage("collect"); local startMemory=collectgarbage("count")
        for i=1,200000 do
            if w.mode=="complete" then
                complete=complete+1
                if w.level<10 then assert(w:Next()) else assert(w:Restart()) end
            end
            local previous=w.mode
            local keys=S.BotKeys(w,bot)
            -- 每第七组注入确定性的随机合法控制，覆盖死亡和重试，
            -- 不允许200k步都停留在冻结结算界面。
            if w.mode=="playing" and math.floor(i/1200)%7==6 then
                local h=(i*16807+541)%2147483647
                keys={left=h%5==0,right=h%5~=0,slow=h%3~=0,slash=i%36==0,roll=i%83==0,jump=i%109==0}
            end
            if w.mode=="playing" then active=active+1 elseif w.mode=="replay" then replays=replays+1 end
            w:Update(STEP,keys)
            if previous~="failed" and w.mode=="failed" then failures=failures+1 end
            enforceCaps(w,high)
            if i%10000==0 then
                collectgarbage("collect"); local kb=collectgarbage("count"); maxMemory=math.max(maxMemory,kb)
                local cp={step=i,lua_kib=kb,level=w.level,mode=w.mode,active_steps=active,
                    completed=complete,failed=failures,arrays=arrays(w)}
                checkpoints[#checkpoints+1]=cp; print("SIMULATION_LONGRUN "..encode(cp))
            end
        end
        note("steps",200000); note("active_steps",active); note("replay_steps",replays); note("completions",complete)
        note("failures",failures); note("high_water",high); note("memory_start_kib",startMemory)
        note("memory_max_gc_kib",maxMemory); note("checkpoints",checkpoints)
        assert(active>=80000,"longrun must meaningfully simulate, not sit in settlement")
        assert(maxMemory<256*1024,"live Lua memory exceeds generous 256MiB test ceiling")
        assert(#checkpoints==20); S.longrun=current.evidence
    end)
    test("stress.replay_2700_live_idle_steps_memory","stress","Replay.lua",function()
        -- 无敌人的隔离长测；真实回放时钟和快照记录保持不变，
        -- 连续100k个活动步测试滚动上限和内存平台。
        local w=empty(fixture()); local high, mem={}, {}
        for i=1,100000 do
            w:Update(STEP,{slow=i%200<100,slash=i%31==0,right=i%2000<1000,left=i%2000>=1000})
            enforceCaps(w,high)
            if i%10000==0 then collectgarbage("collect"); mem[#mem+1]={step=i,kib=collectgarbage("count"),frames=#w.replay.frames} end
        end
        note("high_water",high); note("memory",mem); equal(#w.replay.frames,2700)
        local tail=mem[#mem].kib; local prev=mem[#mem-1].kib
        assert(tail<prev*1.2+1024,"rolling replay memory should plateau")
    end)
end

function S.Run()
    records={}; campaigns={}; print("SIMULATION_BEGIN Lua=".._VERSION.." fixed_step="..STEP)
    mechanics(); campaign(); longrun()
    local counts={pass=0,fail=0,blocked=0}; for _,r in ipairs(records) do counts[r.status]=counts[r.status]+1 end
    local report={schema=1,lua=_VERSION,step=STEP,counts=counts,tests=records,campaign=S.campaign,longrun=S.longrun,
        constraints={pure_lua=true,gameplay_sources_modified_by_suite=false,network=false,installation=false,
            isolated_fixtures_not_campaign=true,render_audio_os_key_delivery="not tested by pure Lua suite"}}
    S.report=report
    print("SIMULATION_REPORT_JSON "..encode(report)); print("SIMULATION_END "..encode(counts))
    return report
end
-- 提供独立运行器Start入口；作为模块加载时不自动运行，但使用方
-- 需要恢复自己的Start。本自测不创建图形与音频对象。
function Start()
    local ok,err=xpcall(S.Run,function(e) return debug.traceback(tostring(e),2) end)
    if not ok then print("SIMULATION_FATAL "..tostring(err)) end
    engine:Exit()
end
return S

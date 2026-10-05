-- 控制器：自写速度积分、地面/平台检测、动作时钟。
local C = require "Game.Config"
local X = require "Game.Collision"
local F = require "Game.Effects"
local P = {}
function P.New()
    return {x=56,y=C.FLOOR,vx=0,vy=0,dir=1,state="idle",stateTime=0,anim="Idle",animTime=0,
        dead=false,ground=true,coyote=0.10,jumpBuffer=0,rollCD=0,slashCD=0,foot=0,wallSound=0,
        portalCD=0,attackId=0,wall=0,landTimer=0}
end
function P.Set(p,state,anim)
    p.state=state; p.stateTime=0; p.anim=anim; p.animTime=0
end
function P.Update(w,dt,keys)
    local p=w.player
    if p.dead then p.animTime=p.animTime+dt; return end
    p.stateTime=p.stateTime+dt; p.animTime=p.animTime+dt
    p.rollCD=math.max(0,p.rollCD-dt); p.slashCD=math.max(0,p.slashCD-dt)
    p.jumpBuffer=keys.jump and 0.12 or math.max(0,p.jumpBuffer-dt)
    p.coyote=p.ground and 0.10 or math.max(0,p.coyote-dt)
    local move=(keys.right and 1 or 0)-(keys.left and 1 or 0)
    if move~=0 and p.state~="roll" and p.state~="slash" then p.dir=move end
    if keys.roll and p.rollCD<=0 and p.state~="roll" then
        P.Set(p,"roll","Squat"); p.rollCD=0.58; w.stats.rolls=w.stats.rolls+1
        w:Sound("sound_player_roll.wav",p.x); F.Add(w,"roll",p.x,p.y-10,-p.dir)
    elseif keys.slash and p.slashCD<=0 and p.state~="roll" then
        P.Set(p,"slash","Slash"); p.slashCD=0.255; p.attackId=p.attackId+1
        w.stats.slashes=w.stats.slashes+1
        w:Sound("sound_player_slash_" .. (p.attackId%3+1) .. ".wav",p.x)
        F.Add(w,"slash",p.x+p.dir*28,p.y-29,p.dir)
    end
    if p.jumpBuffer>0 and p.state~="roll" and (p.coyote>0 or p.wall~=0) then
        local wall=p.wall~=0 and not p.ground
        p.vy=-330; p.jumpBuffer=0; p.coyote=0; p.ground=false
        if wall then p.vx=-p.wall*190; p.dir=-p.wall; p.wall=0; w:Sound("sound_player_landwire.wav",p.x) end
        if p.state~="slash" then P.Set(p,"jump","Jump") end
        F.Add(w,"jump",p.x,p.y-18,p.dir); w:Sound("sound_player_jump.wav",p.x)
        w.stats.jumps=w.stats.jumps+1
    end
    if p.state=="roll" then
        p.vx=p.dir*285
        p.anim=p.stateTime<0.04 and "Squat" or "Roll"
        if p.stateTime>=0.38 then P.Set(p,"recover","Squat") end
    elseif p.state=="slash" then
        p.vx=move*92
        if p.stateTime>=0.23 then P.Set(p,"idle","Idle") end
    elseif p.state=="recover" then
        p.vx=move*80
        if p.stateTime>=0.105 then P.Set(p,"idle","Idle") end
    else
        local target=move*168
        p.vx=p.vx+(target-p.vx)*math.min(1,dt*(p.ground and 25 or 12))
        if not p.ground then
            if p.wall~=0 and p.vy>0 then
                if p.anim~="Wallslide" then P.Set(p,"wall","Wallslide") end
                p.wallSound=p.wallSound-dt
                if p.wallSound<=0 then w:Sound("sound_player_wallslide.wav",p.x,0.3); p.wallSound=0.9 end
            elseif p.anim~="Jump" then P.Set(p,"jump","Jump") end
        elseif p.landTimer>0 then
            p.landTimer=math.max(0,p.landTimer-dt)
            if p.landTimer<=0 then P.Set(p,"idle","Idle") end
        elseif move~=0 then
            if p.state~="run" and p.state~="prerun" then P.Set(p,"prerun","Prerun"); w:Sound("sound_player_prerun.wav",p.x) end
            if p.state=="prerun" and p.stateTime>0.16 then P.Set(p,"run","Run") end
            p.foot=p.foot+dt
            if p.foot>0.20 then
                p.foot=p.foot-0.20; w.stats.steps=w.stats.steps+1
                w:Sound("sound_player_running_"..(w.stats.steps%4+1)..".wav",p.x,0.32)
            end
        else
            if p.state=="run" or p.state=="prerun" then P.Set(p,"stop","Stoprun") end
            if p.state=="stop" and p.stateTime>0.15 then P.Set(p,"idle","Idle") end
        end
    end
    -- 身体宽14，高35；边墙不可穿越。下落平台只检测脚底从上穿过顶边。
    local oldY=p.y
    p.x=X.Clamp(p.x+p.vx*dt,9,C.WIDTH-9)
    p.wall=p.x<=9.01 and -1 or p.x>=C.WIDTH-9.01 and 1 or 0
    p.vy=p.vy+850*dt
    if p.wall~=0 and p.vy>65 then p.vy=65 end
    p.y=p.y+p.vy*dt
    if p.y<55 then p.y=55; p.vy=math.max(0,p.vy) end
    local floor=C.FLOOR
    for _,platform in ipairs(w.platforms) do
        if p.x+6>=platform.x and p.x-6<=platform.x+platform.w and oldY<=platform.y+0.1 and p.y>=platform.y and p.vy>=0 then
            floor=math.min(floor,platform.y)
        end
    end
    local wasGround=p.ground
    p.ground=p.y>=floor and p.vy>=0
    if p.ground then
        p.y=floor; p.vy=0
        if not wasGround then
            F.Add(w,"land",p.x,p.y-14,p.dir); w:Sound("sound_player_land.wav",p.x)
            if p.state~="roll" and p.state~="slash" then P.Set(p,"land","Land"); p.landTimer=0.12 end
        end
    end
    if keys.slow then
        w.trailTimer=w.trailTimer+dt
        if w.trailTimer>0.045 then
            w.trailTimer=0
            if #w.trails>=8 then table.remove(w.trails,1) end
            w.trails[#w.trails+1]={x=p.x,y=p.y,dir=p.dir,anim=p.anim,time=p.animTime,life=0.22}
        end
    end
end
return P

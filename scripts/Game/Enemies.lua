-- 两套完整敌人 FSM；死亡在命中当步生效，动画只负责反馈。
local C = require "Game.Config"
local F = require "Game.Effects"
local X = require "Game.Collision"
local E = {}
function E.Set(w,e,state,anim)
    e.state=state; e.timer=0; e.anim=anim; e.animTime=0; e.fired=false; e.shotCount=0
    w.visited[e.kind..":"..state]=true
end
function E.New(w,kind,x)
    local e={kind=kind,x=x,y=C.FLOOR,dir=x<w.player.x and 1 or -1,state="spawn",timer=0,
        anim="Idle",animTime=0,dead=false,fired=false,aimX=0,aimY=0,attackDone=false,portalCD=0}
    w.visited[kind..":spawn"]=true
    return e
end
function E.Update(w,e,dt)
    e.timer=e.timer+dt; e.animTime=e.animTime+dt
    if e.dead then
        if e.kind=="melee" and e.state=="hurt" and e.timer>0.5 then E.Set(w,e,"death","Death")
        elseif e.kind=="ranged" and e.state=="shieldhit" and e.timer>0.1 then E.Set(w,e,"death","Hit") end
        return
    end
    local p=w.player
    local dx=p.x-e.x; local distance=math.abs(dx)
    local toward=dx>=0 and 1 or -1
    local difficulty=1+(w.level-1)*0.025
    local function chase(speed) e.x=X.Clamp(e.x+toward*speed*dt,12,C.WIDTH-12); e.dir=toward end
    if e.state=="spawn" then
        local idleDuration=e.kind=="melee" and 0.6 or 1.0
        if e.timer>=idleDuration then E.Set(w,e,"idle","Idle") end
        return
    end
    if e.kind=="melee" then
        if e.state=="idle" or e.state=="walk" or e.state=="run" then
            e.dir=toward
            if distance<39 and math.abs(p.y-e.y)<35 then
                E.Set(w,e,"switch","Switch"); e.attackDone=false
            elseif distance>140 then
                if e.state~="walk" then E.Set(w,e,"walk","Walk") end
                chase(54*difficulty)
            else
                if e.state~="run" then E.Set(w,e,"run","Run") end
                chase(82*difficulty)
            end
        elseif e.state=="switch" then
            if e.timer>=0.7 then E.Set(w,e,"hit","Hit"); F.Add(w,"melee",e.x+e.dir*24,e.y-24,e.dir) end
        elseif e.state=="hit" then
            if e.timer>=0.09 and e.timer<=0.25 then
                local hit={x=e.x+(e.dir>0 and 2 or -39),y=e.y-38,w=37,h=38}
                if not p.dead and X.Overlap(hit,X.Body(p)) and not X.Invulnerable(p) then w:KillPlayer("刀锋") end
            end
            if e.timer>=0.4 then E.Set(w,e,"recover","Idle") end
        elseif e.state=="recover" and e.timer>=0.3 then E.Set(w,e,"idle","Idle") end
    else
        if e.state=="idle" then
            e.dir=toward
            if e.timer>0.22 then
                if distance<34 and math.abs(p.y-e.y)<36 then E.Set(w,e,"shield","ShieldAttact")
                elseif distance>290 then E.Set(w,e,"walk","Walk")
                elseif distance<80 then E.Set(w,e,"run","Run")
                else E.Set(w,e,"switch","Switch"); e.aimX=p.x; e.aimY=p.y-24 end
            end
        elseif e.state=="walk" then
            chase(40*difficulty)
            if distance<260 or e.timer>1.5 then E.Set(w,e,"idle","Idle") end
        elseif e.state=="run" then
            e.dir=toward
            e.x=X.Clamp(e.x-toward*65*dt,12,C.WIDTH-12)
            if distance>100 or e.timer>0.65 then E.Set(w,e,"idle","Idle") end
        elseif e.state=="switch" then
            if e.timer>=0.4 then E.Set(w,e,"shoot","Shoot") end
        elseif e.state=="shoot" then
            local maxShots=w.level>=7 and 2 or 1
            local fired=e.shotCount or 0
            if fired<maxShots and e.timer>=0.30+fired*0.24 then
                e.fired=true; e.shotCount=fired+1
                local ox=e.x+e.dir*20; local oy=e.y-26
                local ax,ay=e.aimX-ox,e.aimY-oy
                local length=math.max(1,math.sqrt(ax*ax+ay*ay))
                w.bullets[#w.bullets+1]={x=ox,y=oy,vx=ax/length*(175+w.level*6),vy=ay/length*(175+w.level*6),
                    friendly=false,life=5,portalCD=0}
                F.Add(w,"shoot",ox,oy,e.dir); w:Sound("sound_player_slash_3.wav",e.x,0.2)
                w.stats.shots=w.stats.shots+1
            end
            if e.timer>=0.8 then E.Set(w,e,"shootend","ShootEnd") end
        elseif e.state=="shootend" and e.timer>=0.2 then E.Set(w,e,"idle","Idle")
        elseif e.state=="shield" then
            if e.timer>=0.26 and e.timer<=0.40 then
                local hit={x=e.x+(e.dir>0 and 0 or -31),y=e.y-34,w=31,h=34}
                if not p.dead and X.Overlap(hit,X.Body(p)) and not X.Invulnerable(p) then w:KillPlayer("盾击") end
            end
            if e.timer>=0.5 then E.Set(w,e,"recover","Idle") end
        elseif e.state=="recover" and e.timer>=0.3 then E.Set(w,e,"idle","Idle") end
    end
end
function E.Kill(w,e,dir,cause)
    if e.dead then return end
    e.dead=true; w.stats.kills=w.stats.kills+1
    if cause=="反弹" then w.stats.reflectKills=w.stats.reflectKills+1 end
    if cause=="爆炸" then w.stats.blastKills=w.stats.blastKills+1 end
    E.Set(w,e,e.kind=="melee" and "hurt" or "shieldhit",e.kind=="melee" and "Hurt" or "ShieldHit")
    F.Blood(w,e,dir); w:Sound("sound_player_landwire.wav",e.x,0.38)
    w:Log("敌人死亡",e.kind,cause,w.stats.kills)
end
return E

-- 接触判定的顺序：刀/弹反 → 道具 → 反射弹敌人 → 敌弹玩家。
local X = require "Game.Collision"
local E = require "Game.Enemies"
local F = require "Game.Effects"
local C = require "Game.Config"
local B = {}
function B.Break(w,o,dir)
    if o.broken then return end
    o.broken=true; w.stats.breaks=w.stats.breaks+1
    F.Particles(w,o.x,o.y-12,18,o.kind=="barrel" and "fire" or "wood",dir)
    w:Sound("sound_player_landwire.wav",o.x,0.55)
    if o.kind=="barrel" then
        w.shake=7; w.flash=0.12
        F.Particles(w,o.x,o.y-20,45,"fire",dir)
        for _,e in ipairs(w.enemies) do
            if not e.dead and math.abs(e.x-o.x)<85 and math.abs(e.y-o.y)<70 then E.Kill(w,e,e.x>=o.x and 1 or -1,"爆炸") end
        end
        if not w.player.dead and math.abs(w.player.x-o.x)<51 and math.abs(w.player.y-o.y)<55 and not X.Invulnerable(w.player) then w:KillPlayer("爆炸") end
        for _,other in ipairs(w.objects) do
            if not other.broken and math.abs(other.x-o.x)<74 and math.abs(other.y-o.y)<65 then B.Break(w,other,dir) end
        end
    else
        -- 箱子碎片是可用于杀敌的投射物，阵营属于玩家。
        for i=1,3 do
            w.bullets[#w.bullets+1]={x=o.x+dir*15,y=o.y-10-i*5,vx=dir*(210+i*18),vy=-i*7,
                friendly=true,life=0.7,portalCD=0,shard=true}
        end
    end
end
function B.Portals(w,a,dt,isBullet,oldX,oldY)
    a.portalCD=math.max(0,a.portalCD-dt)
    if a.portalCD>0 or #w.portals<2 then return end
    for i,portal in ipairs(w.portals) do
        local crossed=isBullet and oldX and X.Sweep(oldX,oldY,a.x,a.y,{x=portal.x-10,y=185,w=20,h=64},0)
        if crossed or (math.abs(a.x-portal.x)<10 and a.y>185 and a.y<249) then
            local target=w.portals[i==1 and 2 or 1]
            local dir=isBullet and (a.vx>=0 and 1 or -1) or a.dir
            a.x=target.x+dir*16; a.portalCD=0.65
            F.Particles(w,a.x,a.y-15,10,"cyan",dir)
            w.stats.teleports=w.stats.teleports+1
            return
        end
    end
end
-- 子弹的所有接触统一比较进入时间：传送门不能晚于入口后方目标结算。
function B.MoveBullet(w,b,dt,depth)
    local p=w.player
    local x1,y1=b.x,b.y
    local x2,y2=x1+b.vx*dt,y1+b.vy*dt
    local best,kind,target=math.huge,"none",nil
    local function candidate(t,hit,obj)
        if t and t<best then best,kind,target=t,hit,obj end
    end
    -- 弹反在同一进入时间优先，下一段已经变成友方不会重复弹反。
    if not b.friendly and X.BladeActive(p) then
        candidate(X.Sweep(x1,y1,x2,y2,X.Blade(p),3),"parry",nil)
    end
    if not b.friendly and not p.dead then
        local t=X.Sweep(x1,y1,x2,y2,X.Body(p),2)
        if X.Invulnerable(p) then
            if t then w.stats.dodges=w.stats.dodges+1 end
        else candidate(t,"player",nil) end
    end
    for _,o in ipairs(w.objects) do
        if not o.broken then candidate(X.Sweep(x1,y1,x2,y2,{x=o.x-12,y=o.y-28,w=24,h=28},2),"object",o) end
    end
    if b.friendly then
        for _,e in ipairs(w.enemies) do
            if not e.dead then candidate(X.Sweep(x1,y1,x2,y2,X.Body(e),2),"enemy",e) end
        end
    end
    if b.portalCD<=0 and #w.portals==2 then
        for i,portal in ipairs(w.portals) do
            candidate(X.Sweep(x1,y1,x2,y2,{x=portal.x-10,y=185,w=20,h=64},0),"portal",i)
        end
    end
    if kind=="none" then b.x=x2; b.y=y2; return false end
    b.x=x1+(x2-x1)*best; b.y=y1+(y2-y1)*best
    if kind=="player" then w:KillPlayer("子弹"); return true end
    if kind=="enemy" then E.Kill(w,target,b.vx>=0 and 1 or -1,"反弹"); return true end
    if kind=="object" then B.Break(w,target,b.vx>=0 and 1 or -1); return true end
    if kind=="parry" then
        b.friendly=true; b.vx=-b.vx*1.35; b.vy=-b.vy
        local closest,dist=nil,math.huge
        for _,e in ipairs(w.enemies) do
            local d=math.abs(e.x-b.x)
            if not e.dead and d<dist then closest,dist=e,d end
        end
        if closest then
            local ax,ay=closest.x-b.x,closest.y-24-b.y
            local length=math.max(1,math.sqrt(ax*ax+ay*ay))
            b.vx=ax/length*300; b.vy=ay/length*300
        end
        F.Particles(w,b.x,b.y,14,"cyan",p.dir)
        w.stats.parries=w.stats.parries+1; w.shake=2.5
        w:Sound("sound_player_landwire.wav",p.x,0.7)
    elseif kind=="portal" then
        local exit=w.portals[target==1 and 2 or 1]
        b.x=exit.x+(b.vx>=0 and 16 or -16); b.portalCD=0.65
        F.Particles(w,b.x,b.y,10,"cyan",b.vx>=0 and 1 or -1)
        w.stats.teleports=w.stats.teleports+1
    end
    -- 出口继续剩余步长；递归有固定上限，极限输入也不能死循环。
    local remaining=dt*(1-best)
    if remaining>0 and depth<3 then return B.MoveBullet(w,b,remaining,depth+1) end
    return false
end
function B.Update(w,dt)
    local p=w.player
    if X.BladeActive(p) then
        local blade=X.Blade(p)
        for _,e in ipairs(w.enemies) do
            if not e.dead and X.Overlap(blade,X.Body(e)) then E.Kill(w,e,p.dir,"刀") end
        end
        for _,o in ipairs(w.objects) do
            if p.dead then break end
            local width=o.kind=="barrel" and 22 or 28
            if not o.broken and X.Overlap(blade,{x=o.x-width/2,y=o.y-28,w=width,h=28}) then B.Break(w,o,p.dir) end
        end
    end
    B.Portals(w,p,dt,false)
    for i=#w.bullets,1,-1 do
        local b=w.bullets[i]
        b.portalCD=math.max(0,b.portalCD-dt)
        local remove=B.MoveBullet(w,b,dt,0)
        b.life=b.life-dt
        if remove or b.life<=0 or b.x<0 or b.x>C.WIDTH or b.y<0 or b.y>C.FLOOR then table.remove(w.bullets,i) end
    end
    while #w.bullets>80 do table.remove(w.bullets,1) end
end
return B

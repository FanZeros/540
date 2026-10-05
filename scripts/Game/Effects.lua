-- 粒子、血斑与一次性切图特效均由游戏数据管理。
local C = require "Game.Config"
local F = {}
function F.Add(w,kind,x,y,dir)
    if #w.fx>=64 then table.remove(w.fx,1) end
    w.fx[#w.fx+1]={kind=kind,x=x,y=y,dir=dir or 1,time=0}
end
function F.Particles(w,x,y,count,color,dir)
    for i=1,count do
        if #w.particles>=260 then table.remove(w.particles,1) end
        local speed=45+w:Random()*150
        local angle=-2.6+w:Random()*2.3
        w.particles[#w.particles+1]={x=x,y=y,vx=math.cos(angle)*speed*(dir or 1),vy=math.sin(angle)*speed,
            life=0.5+w:Random()*0.8,color=color,size=1+w:Random()*2,blood=color=="blood"}
    end
end
function F.Stain(w,x,y,wall)
    if #w.stains>=140 then table.remove(w.stains,1) end
    w.stains[#w.stains+1]={x=x,y=y,wall=wall,r=2+w:Random()*6,drip=2+w:Random()*12}
end
function F.Blood(w,e,dir)
    F.Add(w,"hit",e.x,e.y-28,dir)
    F.Particles(w,e.x,e.y-25,26,"blood",dir)
    F.Stain(w,e.x+dir*14,e.y-24,true)
    F.Stain(w,e.x+dir*25,C.FLOOR,false)
    w.shake=math.max(w.shake,3)
    w.flash=math.max(w.flash,0.055)
end
function F.Update(w,dt)
    for i=#w.fx,1,-1 do
        local f=w.fx[i]
        f.time=f.time+dt
        if f.time>C.fx[f.kind][4]*0.05 then table.remove(w.fx,i) end
    end
    for i=#w.particles,1,-1 do
        local p=w.particles[i]
        p.life=p.life-dt
        p.x=p.x+p.vx*dt; p.y=p.y+p.vy*dt; p.vy=p.vy+310*dt
        if p.blood and p.y>=C.FLOOR then
            F.Stain(w,p.x,C.FLOOR,false); p.life=0
        elseif p.blood and (p.x<9 or p.x>C.WIDTH-9) then
            F.Stain(w,math.max(8,math.min(C.WIDTH-8,p.x)),p.y,true); p.life=0
        end
        if p.life<=0 then table.remove(w.particles,i) end
    end
    w.shake=math.max(0,w.shake-dt*14)
    w.flash=math.max(0,w.flash-dt)
end
return F

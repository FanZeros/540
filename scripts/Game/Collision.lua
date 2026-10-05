-- 自写碰撞：身体 AABB、刀区 AABB、子弹扫掠；不使用引擎碰撞接口。
local M = {}
function M.Overlap(a, b)
    return a.x <= b.x+b.w and a.x+a.w >= b.x and a.y <= b.y+b.h and a.y+a.h >= b.y
end
function M.Body(a)
    local h = a.kind == "ranged" and 34 or a.kind == "melee" and 42 or 35
    local r = a.kind == "melee" and 10 or a.kind == "ranged" and 9 or 7
    if a.state == "roll" then h, r = 16, 9 end
    return {x=a.x-r, y=a.y-h, w=r*2, h=h}
end
function M.Blade(p)
    return { x=p.x+(p.dir > 0 and 0 or -52), y=p.y-43, w=52, h=41 }
end
-- 对膨胀矩形求线段进入比例；高速子弹不能穿透目标。
function M.Sweep(x1,y1,x2,y2,b,r)
    local enter, leave = 0, 1
    local dx, dy = x2-x1, y2-y1
    local mins, maxs, starts, deltas = {b.x-r,b.y-r},{b.x+b.w+r,b.y+b.h+r},{x1,y1},{dx,dy}
    for axis=1,2 do
        local delta = deltas[axis]
        if math.abs(delta) < 1e-8 then
            if starts[axis] < mins[axis] or starts[axis] > maxs[axis] then return nil end
        else
            local a, z = (mins[axis]-starts[axis])/delta, (maxs[axis]-starts[axis])/delta
            if a>z then a,z=z,a end
            enter, leave = math.max(enter,a), math.min(leave,z)
            if enter>leave then return nil end
        end
    end
    return enter
end
function M.Invulnerable(p)
    return p.state=="roll" and p.stateTime>=0.045 and p.stateTime<=0.31
end
function M.BladeActive(p)
    return not p.dead and p.state=="slash" and p.stateTime>=0.025 and p.stateTime<=0.20
end
function M.Clamp(v,a,b) return math.max(a,math.min(b,v)) end
return M

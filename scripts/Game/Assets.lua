-- 消费 Aseprite 元数据而非只把 JSON 放进目录。
local C = require "Game.Config"
local A = {}
function A.Load()
    local sources={{"大壮动作.json",C.meleeTags,44,72,54},{"盾牌男.json",C.rangedTags,54,51,44}}
    for _,source in ipairs(sources) do
        local file=cache:GetFile(source[1])
        assert(file,"动画 JSON 缺失："..source[1])
        local data=cjson.decode(file:ReadString())
        file:Close(); file:Dispose()
        assert(data.meta and data.meta.frameTags,"动画标签缺失："..source[1])
        for _,tag in ipairs(data.meta.frameTags) do
            assert(tag.from>=0 and tag.to<source[3],"动画索引越界")
            source[2][tag.name]={tag.from,tag.to}
        end
        print("[素材] 已读取 Aseprite 标签",source[1],#data.meta.frameTags)
    end
end
return A

<script setup lang="ts">
import { computed } from 'vue'
import type { CharacterRelation } from '../../api/characterRelation'

const props = defineProps<{ relations: CharacterRelation[] }>()
const emit = defineEmits<{
  'open-node': [id: string]
  'open-edge': [id: string]
}>()

// 椭圆环形布局（与世界观关系图一致，零外部依赖）
const VIEW_WIDTH = 800
const VIEW_HEIGHT = 620
const CENTER_X = 400
const CENTER_Y = 300
const RADIUS_X = 310
const RADIUS_Y = 235
const NODE_RADIUS = 28

const PALETTE = [
  '#5b8ff9', '#5ad8a6', '#f6bd16', '#e8684a',
  '#6dc8ec', '#9270ca', '#ff9d4d', '#269a99',
]

interface NodeLayout {
  id: string
  name: string
  x: number
  y: number
  color: string
  links: number
}

// 收集所有参与的人物节点
const nodes = computed<NodeLayout[]>(() => {
  const map = new Map<string, { id: string; name: string; count: number }>()
  for (const r of props.relations) {
    if (!map.has(r.source_character_id)) {
      map.set(r.source_character_id, { id: r.source_character_id, name: r.source_name, count: 0 })
    }
    if (!map.has(r.target_character_id)) {
      map.set(r.target_character_id, { id: r.target_character_id, name: r.target_name, count: 0 })
    }
    map.get(r.source_character_id)!.count++
    map.get(r.target_character_id)!.count++
  }
  const list = Array.from(map.values()).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  const n = list.length
  return list.map((item, i) => {
    const angle = n <= 1 ? -Math.PI / 2 : (-Math.PI / 2) + (2 * Math.PI * i) / n
    const x = CENTER_X + RADIUS_X * Math.cos(angle)
    const y = CENTER_Y + RADIUS_Y * Math.sin(angle)
    return {
      id: item.id,
      name: item.name,
      x,
      y,
      color: PALETTE[i % PALETTE.length],
      links: item.count,
    }
  })
})

const nodeById = computed(() => {
  const map = new Map<string, NodeLayout>()
  for (const n of nodes.value) map.set(n.id, n)
  return map
})

interface EdgeLayout {
  id: string
  from: NodeLayout
  to: NodeLayout
  label: string
  strength: string
  isEnded: boolean
  // 标签偏移，避免正反向重叠
  labelOffset: number
}

// 把关系分组：每对人物之间可能有多条关系（正向不同类型 + 反向）。
// 先按 (source,target) 分组，计算 labelOffset
const edges = computed<EdgeLayout[]>(() => {
  const pairs = new Map<string, EdgeLayout[]>()
  for (const r of props.relations) {
    const from = nodeById.value.get(r.source_character_id)
    const to = nodeById.value.get(r.target_character_id)
    if (!from || !to) continue
    const key = [r.source_character_id, r.target_character_id].join('|')
    const arr = pairs.get(key) || []
    arr.push({
      id: r.id,
      from,
      to,
      label: r.relation_type,
      strength: r.strength !== null ? `${r.strength}` : '',
      isEnded: r.status === 'ended',
      labelOffset: arr.length * 14,
    })
    pairs.set(key, arr)
  }
  const result: EdgeLayout[] = []
  for (const arr of pairs.values()) result.push(...arr)
  return result
})

const shortLabel = (s: string, max = 10) => (s.length > max ? s.slice(0, max) + '…' : s)
const shortName = (s: string, max = 8) => (s.length > max ? s.slice(0, max) + '…' : s)

function edgeSvgPath(e: EdgeLayout) {
  const dx = e.to.x - e.from.x
  const dy = e.to.y - e.from.y
  const dist = Math.hypot(dx, dy) || 1
  const ux = dx / dist
  const uy = dy / dist
  const fx = e.from.x + ux * NODE_RADIUS
  const fy = e.from.y + uy * NODE_RADIUS
  const tx = e.to.x - ux * NODE_RADIUS
  const ty = e.to.y - uy * NODE_RADIUS
  return { fx, fy, tx, ty }
}

function labelPos(e: EdgeLayout) {
  const { fx, fy, tx, ty } = edgeSvgPath(e)
  const mx = (fx + tx) / 2
  const my = (fy + ty) / 2
  const dx = tx - fx
  const dy = ty - fy
  const dist = Math.hypot(dx, dy) || 1
  // 垂直于连线方向做偏移，正负取决于 labelOffset 奇偶号
  const nx = -dy / dist
  const ny = dx / dist
  const sign = e.labelOffset % 2 === 0 ? 1 : -1
  const amp = Math.floor(e.labelOffset / 2) * 12
  return { x: mx + nx * sign * (6 + amp), y: my + ny * sign * (6 + amp) }
}
</script>

<template>
  <div class="graph-wrap">
    <svg
      :viewBox="`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`"
      class="graph-svg"
      role="img"
      aria-label="人物关系网络图"
    >
      <defs>
        <marker
          id="arrow-active"
          viewBox="0 0  10 10"
          refX="8"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="#7aa2ff" />
        </marker>
        <marker
          id="arrow-ended"
          viewBox="0 0  10 10"
          refX="8"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="rgba(255,255,255,0.25)" />
        </marker>
      </defs>

      <!-- 连线 -->
      <g class="edges">
        <template v-for="e in edges" :key="e.id">
          <line
            :x1="edgeSvgPath(e).fx"
            :y1="edgeSvgPath(e).fy"
            :x2="edgeSvgPath(e).tx"
            :y2="edgeSvgPath(e).ty"
            :stroke="e.isEnded ? 'rgba(255,255,255,0.25)' : '#7aa2ff'"
            :stroke-dasharray="e.isEnded ? '4 3' : undefined"
            stroke-width="1.5"
            :marker-end="e.isEnded ? 'url(#arrow-ended)' : 'url(#arrow-active)'"
            class="edge-line"
            :data-id="e.id"
            @click="emit('open-edge', e.id)"
          />
          <text
            :x="labelPos(e).x"
            :y="labelPos(e).y"
            text-anchor="middle"
            dominant-baseline="middle"
            :fill="e.isEnded ? 'rgba(255,255,255,0.45)' : '#eaf1ff'"
            font-size="11"
            class="edge-label"
            :data-id="e.id"
            @click="emit('open-edge', e.id)"
          >
            {{ shortLabel(e.label) }}<tspan v-if="e.strength" class="strength"> ·{{ e.strength }}</tspan>
          </text>
        </template>
      </g>

      <!-- 节点 -->
      <g class="nodes">
        <g
          v-for="n in nodes"
          :key="n.id"
          :transform="`translate(${n.x}, ${n.y})`"
          class="node"
          :data-id="n.id"
          @click="emit('open-node', n.id)"
        >
          <circle :r="NODE_RADIUS" :fill="n.color" stroke="rgba(255,255,255,0.8)" stroke-width="1.5" />
          <text text-anchor="middle" dominant-baseline="middle" fill="#fff" font-size="12" class="node-name">
            {{ shortName(n.name) }}
          </text>
          <circle :r="NODE_RADIUS + 3" fill="none" :stroke="n.color" stroke-width="1" opacity="0.3" />
        </g>
      </g>
    </svg>

    <div v-if="!edges.length" class="empty-hint">
      <n-empty description="还没有任何人物关系" size="small" />
    </div>
  </div>
</template>

<style scoped>
.graph-wrap {
  max-width: 900px;
  margin: 0 auto;
  padding: 12px;
  position: relative;
}

.graph-svg {
  width: 100%;
  max-width: 900px;
  height: auto;
  display: block;
  margin: 0 auto;
  overflow: visible;
}

.edge-line, .edge-label {
  cursor: pointer;
  transition: filter .15s;
}
.edge-line:hover { filter: drop-shadow(0 0 3px rgba(122,162,255,0.6)); }
.edge-label:hover { fill: #fff !important; }

.strength { font-size: 9px; fill: rgba(255,255,255,0.5); }

.node {
  cursor: pointer;
  transition: transform .15s;
}
.node:hover { transform: var(--hover-scale, 1.06); }

.empty-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
</style>

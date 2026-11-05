<script setup lang="ts">
import { computed } from 'vue'
import type { WorldEntry, WorldRelation } from '../../api/world'

const props = defineProps<{
  entries: WorldEntry[]
  relations: WorldRelation[]
}>()

const emit = defineEmits<{
  'open-entry': [entryId: string]
  'open-relation': [relation: WorldRelation]
}>()

const VIEW_WIDTH = 800
const VIEW_HEIGHT = 620
const CENTER_X = 400
const CENTER_Y = 300
const RADIUS_X = 310
const RADIUS_Y = 235
const NODE_RADIUS = 28

const PALETTE = [
  '#5b8ff9',
  '#5ad8a6',
  '#f6bd16',
  '#e8684a',
  '#6dc8ec',
  '#9270ca',
  '#ff9d4d',
  '#269a99',
]

interface GraphNode {
  entry: WorldEntry
  x: number
  y: number
  color: string
}

interface GraphEdge {
  relation: WorldRelation
  x1: number
  y1: number
  x2: number
  y2: number
  labelX: number
  labelY: number
  label: string
}

function hashString(value: string): number {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash
}

// 按分类首次出现的顺序分配调色板，保证不同分类拿到不同颜色
const categoryColorMap = computed(() => {
  const map = new Map<string, string>()
  let index = 0
  for (const entry of props.entries) {
    if (!map.has(entry.category_id)) {
      map.set(entry.category_id, PALETTE[index % PALETTE.length])
      index += 1
    }
  }
  return map
})

function colorFor(categoryId: string): string {
  return categoryColorMap.value.get(categoryId) || PALETTE[0]
}

function shortName(name: string): string {
  return name.length > 5 ? `${name.slice(0, 5)}…` : name
}

function shortType(type: string): string {
  return type.length > 8 ? `${type.slice(0, 8)}…` : type
}

const nodes = computed<GraphNode[]>(() => {
  const total = props.entries.length
  if (!total) return []
  return props.entries.map((entry, index) => {
    if (total === 1) {
      return { entry, x: CENTER_X, y: CENTER_Y, color: colorFor(entry.category_id) }
    }
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total
    return {
      entry,
      x: CENTER_X + Math.cos(angle) * RADIUS_X,
      y: CENTER_Y + Math.sin(angle) * RADIUS_Y,
      color: colorFor(entry.category_id),
    }
  })
})

const nodeMap = computed(() => new Map(nodes.value.map((node) => [node.entry.id, node])))

const edges = computed<GraphEdge[]>(() => {
  const result: GraphEdge[] = []
  for (const relation of props.relations) {
    const source = nodeMap.value.get(relation.source_entry_id)
    const target = nodeMap.value.get(relation.target_entry_id)
    if (!source || !target) continue

    const dx = target.x - source.x
    const dy = target.y - source.y
    const distance = Math.hypot(dx, dy) || 1
    const ux = dx / distance
    const uy = dy / distance
    const x1 = source.x + ux * NODE_RADIUS
    const y1 = source.y + uy * NODE_RADIUS
    const x2 = target.x - ux * NODE_RADIUS
    const y2 = target.y - uy * NODE_RADIUS

    // 用关系 ID 的哈希决定标签偏移方向，让 A→B 与 B→A 的标签不会完全重叠
    const hash = hashString(relation.id)
    const sign = hash % 2 === 0 ? 1 : -1
    const offset = sign * (10 + (hash % 3) * 6)
    const labelX = (x1 + x2) / 2 - uy * offset
    const labelY = (y1 + y2) / 2 + ux * offset

    result.push({
      relation,
      x1,
      y1,
      x2,
      y2,
      labelX,
      labelY,
      label: shortType(relation.relation_type),
    })
  }
  return result
})

const legend = computed(() => {
  const seen = new Map<string, { name: string; color: string }>()
  for (const entry of props.entries) {
    if (!seen.has(entry.category_id)) {
      seen.set(entry.category_id, {
        name: entry.category_name,
        color: colorFor(entry.category_id),
      })
    }
  }
  return Array.from(seen.values())
})
</script>

<template>
  <div class="graph-wrap">
    <svg
      v-if="nodes.length"
      class="graph"
      :viewBox="`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`"
      role="img"
      aria-label="世界观关系网络"
    >
      <defs>
        <marker
          id="relation-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#7ea2ff" />
        </marker>
      </defs>

      <g v-for="edge in edges" :key="edge.relation.id" class="edge">
        <line
          :x1="edge.x1"
          :y1="edge.y1"
          :x2="edge.x2"
          :y2="edge.y2"
          stroke="#4c6ef5"
          stroke-width="1.6"
          stroke-opacity="0.7"
          marker-end="url(#relation-arrow)"
        />
        <text
          class="edge-label"
          :x="edge.labelX"
          :y="edge.labelY"
          text-anchor="middle"
          dominant-baseline="middle"
          @click="emit('open-relation', edge.relation)"
        >
          {{ edge.label }}
        </text>
        <line
          class="edge-hit"
          :x1="edge.x1"
          :y1="edge.y1"
          :x2="edge.x2"
          :y2="edge.y2"
          stroke="transparent"
          stroke-width="12"
          @click="emit('open-relation', edge.relation)"
        />
      </g>

      <g
        v-for="node in nodes"
        :key="node.entry.id"
        class="node"
        @click="emit('open-entry', node.entry.id)"
      >
        <title>{{ node.entry.name }}（{{ node.entry.category_name }}）</title>
        <circle
          :cx="node.x"
          :cy="node.y"
          :r="NODE_RADIUS"
          :fill="node.color"
          fill-opacity="0.16"
          :stroke="node.color"
          stroke-width="1.5"
        />
        <text
          class="node-label"
          :x="node.x"
          :y="node.y"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ shortName(node.entry.name) }}
        </text>
      </g>
    </svg>

    <div v-else class="graph-empty">当前筛选下没有可展示的条目</div>

    <div v-if="legend.length" class="legend">
      <span v-for="item in legend" :key="item.name" class="legend-item">
        <span class="dot" :style="{ background: item.color }" />
        {{ item.name }}
      </span>
    </div>

    <div class="graph-hint">
      点击节点查看设定详情，点击连线或关系类型查看关系详情。手机端数据密集时可切换到「关系列表」查看。
    </div>
  </div>
</template>

<style scoped>
.graph-wrap {
  width: 100%;
  overflow: hidden;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  padding: 8px;
  box-sizing: border-box;
}

.graph {
  display: block;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  height: auto;
}

.node {
  cursor: pointer;
}

.node:hover circle {
  stroke-width: 2.5;
}

.node-label {
  font-size: 11px;
  fill: #e8efff;
  paint-order: stroke;
  stroke: rgba(8, 10, 18, 0.75);
  stroke-width: 3px;
  pointer-events: none;
}

.edge-label {
  font-size: 11px;
  fill: #c7d6ff;
  paint-order: stroke;
  stroke: rgba(8, 10, 18, 0.85);
  stroke-width: 4px;
  cursor: pointer;
}

.edge-label:hover {
  fill: #ffffff;
}

.edge-hit {
  cursor: pointer;
}

.graph-empty {
  padding: 48px 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 8px 4px 2px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.graph-hint {
  padding: 6px 4px 2px;
  font-size: 11px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.35);
}
</style>

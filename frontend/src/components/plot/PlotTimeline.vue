<script setup lang="ts">
import { NEmpty, NTag, NSpin } from 'naive-ui'
import {
  PLOT_IMPORTANCE_LABELS,
  PLOT_IMPORTANCE_TYPES,
  type PlotEvent,
} from '../../api/plotEvent'

defineProps<{
  timed: PlotEvent[]
  untimed: PlotEvent[]
  loading?: boolean
}>()

const emit = defineEmits<{ open: [event: PlotEvent] }>()
</script>

<template>
  <n-spin :show="Boolean(loading)">
    <div v-if="!timed.length && !untimed.length" class="timeline-empty">
      <n-empty description="还没有剧情事件。创建事件后会按故事时间出现在时间线上。" />
    </div>

    <template v-else>
      <section v-if="timed.length" class="timeline-section">
        <div class="section-title">按故事时间</div>
        <div class="timeline">
          <div
            v-for="event in timed"
            :key="event.id"
            class="timeline-item"
            @click="emit('open', event)"
          >
            <div class="time-col">
              <span class="time-text">{{ event.story_time }}</span>
            </div>
            <div class="dot" />
            <div class="event-body">
              <div class="event-head">
                <span class="event-title">{{ event.title }}</span>
                <n-tag
                  size="tiny"
                  :bordered="false"
                  :type="PLOT_IMPORTANCE_TYPES[event.importance]"
                >
                  {{ PLOT_IMPORTANCE_LABELS[event.importance] }}
                </n-tag>
                <n-tag v-if="event.event_type" size="tiny" :bordered="false">
                  {{ event.event_type }}
                </n-tag>
              </div>
              <div class="event-meta">
                <span v-if="event.chapter_title">
                  第 {{ event.chapter_number }} 章 · {{ event.chapter_title }}
                </span>
                <span v-if="event.location_name">{{ event.location_name }}</span>
                <span v-if="event.participants.length">
                  {{ event.participants.map((p) => p.character_name).join('、') }}
                </span>
              </div>
              <div v-if="event.description" class="event-desc">{{ event.description }}</div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="untimed.length" class="timeline-section">
        <div class="section-title">未填写故事时间</div>
        <div class="untimed-list">
          <div
            v-for="event in untimed"
            :key="event.id"
            class="untimed-item"
            @click="emit('open', event)"
          >
            <div class="event-head">
              <span class="event-title">{{ event.title }}</span>
              <n-tag
                size="tiny"
                :bordered="false"
                :type="PLOT_IMPORTANCE_TYPES[event.importance]"
              >
                {{ PLOT_IMPORTANCE_LABELS[event.importance] }}
              </n-tag>
              <n-tag v-if="event.event_type" size="tiny" :bordered="false">
                {{ event.event_type }}
              </n-tag>
            </div>
            <div class="event-meta">
              <span v-if="event.chapter_title">
                第 {{ event.chapter_number }} 章 · {{ event.chapter_title }}
              </span>
              <span v-if="event.location_name">{{ event.location_name }}</span>
            </div>
          </div>
        </div>
      </section>
    </template>
  </n-spin>
</template>

<style scoped>
.timeline-empty {
  padding: 40px 0;
}
.timeline-section {
  margin-bottom: 24px;
}
.section-title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sf-text-secondary, #666);
}
.timeline {
  position: relative;
  padding-left: 4px;
}
.timeline::before {
  content: '';
  position: absolute;
  left: 128px;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: var(--sf-border, #e5e5e5);
}
.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 0;
  cursor: pointer;
}
.time-col {
  width: 116px;
  flex-shrink: 0;
  text-align: right;
}
.time-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--sf-text-secondary, #666);
  word-break: break-word;
}
.dot {
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border-radius: 50%;
  background: #2080f0;
  flex-shrink: 0;
  z-index: 1;
}
.event-body,
.untimed-item {
  flex: 1;
  min-width: 0;
  border-radius: 8px;
  padding: 4px 8px;
  transition: background 0.2s;
}
.timeline-item:hover .event-body,
.untimed-item:hover {
  background: var(--sf-hover, #f6f7f9);
}
.untimed-item {
  cursor: pointer;
  padding: 10px;
  border: 1px solid var(--sf-border, #eee);
  margin-bottom: 8px;
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.event-title {
  font-size: 14px;
  font-weight: 600;
}
.event-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 3px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.event-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-secondary, #666);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 640px) {
  .timeline::before {
    left: 8px;
  }
  .timeline-item {
    flex-direction: column;
    gap: 4px;
    padding-left: 22px;
    position: relative;
  }
  .dot {
    position: absolute;
    left: 4px;
    top: 12px;
  }
  .time-col {
    width: auto;
    text-align: left;
  }
  .event-desc {
    white-space: normal;
  }
}
</style>

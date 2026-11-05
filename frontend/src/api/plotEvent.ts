import { api } from './index'

export type PlotImportance = 'low' | 'normal' | 'high' | 'critical'

export interface PlotParticipant {
  id: string
  character_id: string
  character_name: string
  participant_role: string
  description: string
}

export interface PlotEvent {
  id: string
  novel_id: string
  chapter_id: string | null
  chapter_title: string | null
  chapter_number: number | null
  title: string
  description: string
  event_type: string
  story_time: string | null
  location_id: string | null
  location_name: string
  importance: PlotImportance
  sequence: number
  participants: PlotParticipant[]
  created_at: string
  updated_at: string
}

export interface PlotParticipantPayload {
  character_id: string
  participant_role?: string
  description?: string
}

export interface PlotEventPayload {
  title: string
  description?: string
  event_type?: string
  story_time?: string | null
  chapter_id?: string | null
  location_id?: string | null
  location_name?: string
  importance?: PlotImportance
  sequence?: number
  participants?: PlotParticipantPayload[]
}

export interface PlotEventUpdatePayload extends Partial<PlotEventPayload> {}

export interface PlotEventQuery {
  chapter_id?: string
  character_id?: string
  event_type?: string
  importance?: PlotImportance | ''
  search?: string
  has_story_time?: boolean
}

export interface PlotTimeline {
  timed: PlotEvent[]
  untimed: PlotEvent[]
}

export const PLOT_IMPORTANCE_LABELS: Record<PlotImportance, string> = {
  low: '低',
  normal: '普通',
  high: '重要',
  critical: '关键',
}

export const PLOT_IMPORTANCE_TYPES: Record<
  PlotImportance,
  'default' | 'info' | 'warning' | 'error'
> = {
  low: 'default',
  normal: 'info',
  high: 'warning',
  critical: 'error',
}

export const PLOT_IMPORTANCE_OPTIONS = (
  Object.keys(PLOT_IMPORTANCE_LABELS) as PlotImportance[]
).map((value) => ({ label: PLOT_IMPORTANCE_LABELS[value], value }))

export function listPlotEvents(novelId: string, params?: PlotEventQuery) {
  return api.get<PlotEvent[]>(`/api/novels/${novelId}/plot-events`, { params })
}

export function getPlotEvent(novelId: string, eventId: string) {
  return api.get<PlotEvent>(`/api/novels/${novelId}/plot-events/${eventId}`)
}

export function createPlotEvent(novelId: string, payload: PlotEventPayload) {
  return api.post<PlotEvent>(`/api/novels/${novelId}/plot-events`, payload)
}

export function updatePlotEvent(
  novelId: string,
  eventId: string,
  payload: PlotEventUpdatePayload,
) {
  return api.put<PlotEvent>(`/api/novels/${novelId}/plot-events/${eventId}`, payload)
}

export function deletePlotEvent(novelId: string, eventId: string) {
  return api.delete<{ deleted: boolean }>(`/api/novels/${novelId}/plot-events/${eventId}`)
}

export function getPlotTimeline(novelId: string, params?: PlotEventQuery) {
  return api.get<PlotTimeline>(`/api/novels/${novelId}/plot-events/timeline`, { params })
}

export function listCharacterPlotEvents(novelId: string, characterId: string) {
  return api.get<PlotEvent[]>(
    `/api/novels/${novelId}/characters/${characterId}/plot-events`,
  )
}
